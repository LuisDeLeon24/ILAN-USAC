import hashlib
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("sentinel.agent")

RATE_LIMIT_MESSAGE = "Senti está recibiendo muchas consultas. Espera un momento e inténtalo de nuevo."
MODEL_UNAVAILABLE_MESSAGE = "El modelo configurado no está disponible. Revisa LLM_MODEL en la configuración."
NOT_CONFIGURED_MESSAGE = "Senti no está configurado."
AUTH_MESSAGE = "No se pudo usar la clave de Senti. Revisa LLM_API_KEY en la configuración."
PROVIDER_MESSAGE = "No se pudo consultar a Senti. Inténtalo de nuevo."

_DEPRIORITIZE = {
    "preview",
    "experimental",
    "exp",
    "omni",
    "live",
    "native",
    "audio",
    "image",
    "tts",
}
_ATTEMPTS = 4
_BACKOFF_SECONDS = (2.0, 4.0, 8.0)
_MAX_RETRY_AFTER = 20.0
_cache: dict[tuple[str, str, str], str] = {}


class RateLimited(Exception):
    pass


class ModelUnavailable(Exception):
    pass


class ProviderAuth(Exception):
    pass


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class ListedModel:
    id: str
    supports_function_calling: bool
    prefer: bool = False
    deprioritize: bool = False


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    signature: str = ""


@dataclass
class LlmTurn:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class TurnMessage:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""


def segments(value: str) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", value.casefold()) if part}


def deprioritize(value: str) -> bool:
    return bool(segments(value) & _DEPRIORITIZE)


def _version_key(model_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", model_id.split("/")[-1]))


def clear_model_cache() -> None:
    _cache.clear()


def _cache_key(provider_name: str, api_key: str, configured: str) -> tuple[str, str, str]:
    fingerprint = hashlib.sha256(api_key.encode()).hexdigest()[:12]
    return provider_name, configured, fingerprint


def plain_text(value: str) -> str:
    text = value.replace("**", "")
    text = text.replace("*", "")
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return text.strip()


def _flash_lite(model: ListedModel) -> bool:
    parts = segments(model.id)
    return "flash" in parts and "lite" in parts


def choose_model(models: list[ListedModel], configured: str, *, prefer_flash: bool) -> str:
    by_id: dict[str, ListedModel] = {}
    for model in models:
        by_id[model.id] = model
        by_id.setdefault(model.id.split("/")[-1], model)
    if configured:
        found = by_id.get(configured) or by_id.get(configured.split("/")[-1])
        if found is None or not found.supports_function_calling:
            raise ModelUnavailable()
        return found.id
    usable = [model for model in models if model.supports_function_calling]
    if not usable:
        raise ModelUnavailable()
    if prefer_flash:
        flash = [model for model in usable if model.prefer]
        if flash:
            lite = [model for model in flash if _flash_lite(model) and not model.deprioritize]
            plain = [model for model in flash if not model.deprioritize]
            pool = lite or plain or flash
            pool.sort(key=lambda model: (_version_key(model.id), model.id), reverse=True)
            return pool[0].id
    return usable[0].id


def resolve_model(provider: object, *, provider_name: str, api_key: str, configured: str) -> str:
    key = _cache_key(provider_name, api_key, configured)
    cached = _cache.get(key)
    if cached:
        return cached
    chosen = choose_model(provider.list_models(), configured, prefer_flash=provider_name == "gemini")
    _cache[key] = chosen
    logger.info("llm model selected provider=%s model=%s", provider_name, chosen)
    return chosen


def forget_model(*, provider_name: str, api_key: str, configured: str) -> None:
    _cache.pop(_cache_key(provider_name, api_key, configured), None)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _retry_delay(response: object, attempt: int) -> float:
    headers = getattr(response, "headers", None)
    raw = ""
    if headers is not None and hasattr(headers, "get"):
        raw = str(headers.get("retry-after") or headers.get("Retry-After") or "")
    if raw:
        try:
            parsed = float(raw)
        except ValueError:
            parsed = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
        return min(_MAX_RETRY_AFTER, max(0.0, parsed))
    return _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict | None = None,
    body: dict | None = None,
) -> dict:
    response = None
    try:
        with httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            for attempt in range(_ATTEMPTS):
                response = client.request(method, url, headers=headers, params=params, json=body)
                if response.status_code != 429:
                    break
                if attempt == _ATTEMPTS - 1:
                    raise RateLimited()
                delay = _retry_delay(response, attempt)
                logger.info("llm rate limited attempt=%s wait=%.1f", attempt + 1, delay)
                _sleep(delay)
    except httpx.HTTPError as exc:
        logger.warning("llm transport failed")
        raise ProviderError() from exc
    if response is None:
        raise ProviderError()
    if response.status_code == 429:
        raise RateLimited()
    if response.status_code == 404:
        raise ModelUnavailable()
    if response.status_code in {401, 403}:
        raise ProviderAuth()
    if response.status_code >= 400:
        logger.warning("llm http status=%s detail=%s", response.status_code, _error_detail(response))
        raise ProviderError()
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError() from exc
    if not isinstance(payload, dict):
        raise ProviderError()
    return payload


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    message = error.get("message") if isinstance(error, dict) else payload.get("message")
    return str(message or "")[:240]
