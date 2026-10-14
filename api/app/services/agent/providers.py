"""LLM adapters. Model ids come from each provider's list endpoint."""

import json
import uuid
from collections.abc import Callable

from app.services.agent.llm import (
    ListedModel,
    LlmTurn,
    ToolCall,
    TurnMessage,
    deprioritize,
    request_json,
    segments,
)

Request = Callable[..., dict]
GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_ROOT = "https://api.openai.com/v1"
ANTHROPIC_ROOT = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
_GEMINI_EXCLUDED = {"embedding", "embed", "aqa", "imagen", "veo", "image", "tts", "live", "audio", "native"}
_OPENAI_EXCLUDED = {
    "whisper",
    "tts",
    "dall",
    "dalle",
    "embedding",
    "embed",
    "moderation",
    "transcribe",
    "realtime",
    "audio",
    "image",
    "imagen",
}
_MAX_PAGES = 10


def build_provider(name: str, api_key: str, request: Request | None = None):
    if name == "openai":
        return OpenAiProvider(api_key, request=request)
    if name == "anthropic":
        return AnthropicProvider(api_key, request=request)
    return GeminiProvider(api_key, request=request)


def _capability(item: dict, keys: tuple[str, ...]) -> bool | None:
    caps = item.get("capabilities")
    if not isinstance(caps, dict):
        return None
    for key in keys:
        if key not in caps:
            continue
        value = caps[key]
        if isinstance(value, dict):
            return bool(value.get("supported"))
        return bool(value)
    return None


class GeminiProvider:
    def __init__(self, api_key: str, request: Request | None = None) -> None:
        self.api_key = api_key
        self._request = request or request_json

    def list_models(self) -> list[ListedModel]:
        models: list[ListedModel] = []
        page_token = ""
        for _ in range(_MAX_PAGES):
            params = {"pageSize": "100"}
            if page_token:
                params["pageToken"] = page_token
            payload = self._request(
                "GET",
                f"{GEMINI_ROOT}/models",
                headers={"x-goog-api-key": self.api_key},
                params=params,
            )
            for item in payload.get("models") or []:
                if isinstance(item, dict) and item.get("name"):
                    models.append(_gemini_model(item))
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                break
        return models

    def complete(self, *, model: str, system: str, messages: list[TurnMessage], tools: list[dict]) -> LlmTurn:
        model_id = model if "/" in model else f"models/{model}"
        payload = self._request(
            "POST",
            f"{GEMINI_ROOT}/{model_id}:generateContent",
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            body={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": _gemini_contents(messages),
                "tools": [{"functionDeclarations": tools}],
            },
        )
        return _gemini_turn(payload)


class OpenAiProvider:
    def __init__(self, api_key: str, request: Request | None = None) -> None:
        self.api_key = api_key
        self._request = request or request_json

    def list_models(self) -> list[ListedModel]:
        payload = self._request(
            "GET",
            f"{OPENAI_ROOT}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        ranked: list[tuple[int, ListedModel]] = []
        for item in payload.get("data") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            created = int(item.get("created") or 0)
            ranked.append((created, _openai_model(item)))
        ranked.sort(key=lambda row: row[0], reverse=True)
        return [model for _created, model in ranked]

    def complete(self, *, model: str, system: str, messages: list[TurnMessage], tools: list[dict]) -> LlmTurn:
        payload = self._request(
            "POST",
            f"{OPENAI_ROOT}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            body={
                "model": model,
                "messages": [{"role": "system", "content": system}, *_openai_messages(messages)],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["parameters"],
                        },
                    }
                    for tool in tools
                ],
            },
        )
        return _openai_turn(payload)


class AnthropicProvider:
    def __init__(self, api_key: str, request: Request | None = None) -> None:
        self.api_key = api_key
        self._request = request or request_json

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def list_models(self) -> list[ListedModel]:
        models: list[ListedModel] = []
        after_id = ""
        for _ in range(_MAX_PAGES):
            params = {"limit": "100"}
            if after_id:
                params["after_id"] = after_id
            payload = self._request("GET", f"{ANTHROPIC_ROOT}/models", headers=self._headers(), params=params)
            page = [item for item in payload.get("data") or [] if isinstance(item, dict) and item.get("id")]
            models.extend(_anthropic_model(item) for item in page)
            if not payload.get("has_more") or not page:
                break
            after_id = str(page[-1]["id"])
        return models

    def complete(self, *, model: str, system: str, messages: list[TurnMessage], tools: list[dict]) -> LlmTurn:
        payload = self._request(
            "POST",
            f"{ANTHROPIC_ROOT}/messages",
            headers=self._headers(),
            body={
                "model": model,
                "max_tokens": 1024,
                "system": system,
                "messages": _anthropic_messages(messages),
                "tools": [
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": tool["parameters"],
                    }
                    for tool in tools
                ],
            },
        )
        return _anthropic_turn(payload)


def _gemini_model(item: dict) -> ListedModel:
    name = str(item["name"])
    display = str(item.get("displayName") or "")
    methods = {str(method).casefold() for method in item.get("supportedGenerationMethods") or []}
    actions = {str(action).casefold() for action in item.get("supportedActions") or []}
    generates = "generatecontent" in methods or "generatecontent" in actions
    excluded = bool(segments(name) & _GEMINI_EXCLUDED)
    identity = f"{name} {display}"
    return ListedModel(
        id=name,
        supports_function_calling=generates and not excluded,
        prefer="flash" in identity.casefold() and not excluded,
        deprioritize=deprioritize(identity),
    )


def _openai_model(item: dict) -> ListedModel:
    model_id = str(item["id"])
    declared = _capability(item, ("function_calling", "tools", "tool_use"))
    if declared is None:
        declared = not bool(segments(model_id) & _OPENAI_EXCLUDED)
    return ListedModel(id=model_id, supports_function_calling=declared)


def _anthropic_model(item: dict) -> ListedModel:
    declared = _capability(item, ("tool_use", "tools", "function_calling"))
    if declared is None:
        declared = item.get("type", "model") == "model"
    return ListedModel(id=str(item["id"]), supports_function_calling=declared)


def _gemini_contents(messages: list[TurnMessage]) -> list[dict]:
    contents: list[dict] = []
    for message in messages:
        if message.role == "user":
            contents.append({"role": "user", "parts": [{"text": message.content}]})
        elif message.role == "assistant":
            parts: list[dict] = []
            if message.content:
                parts.append({"text": message.content})
            for call in message.tool_calls:
                part = {"functionCall": {"name": call.name, "args": call.arguments}}
                if call.signature:
                    part["thoughtSignature"] = call.signature
                parts.append(part)
            if parts:
                contents.append({"role": "model", "parts": parts})
        elif message.role == "tool":
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": message.tool_name,
                                "response": json.loads(message.content) if message.content else {},
                            }
                        }
                    ],
                }
            )
    return contents


def _gemini_turn(payload: dict) -> LlmTurn:
    candidates = payload.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    texts: list[str] = []
    calls: list[ToolCall] = []
    carried = ""
    for part in parts:
        if not isinstance(part, dict):
            continue
        signature = _part_signature(part)
        if part.get("thought"):
            if signature:
                carried = signature
            continue
        if part.get("text"):
            texts.append(str(part["text"]))
        call = part.get("functionCall")
        if isinstance(call, dict) and call.get("name"):
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            calls.append(
                ToolCall(
                    id=uuid.uuid4().hex,
                    name=str(call["name"]),
                    arguments=args,
                    signature=_part_signature(call) or signature or carried,
                )
            )
            carried = ""
    return LlmTurn("\n".join(texts).strip(), calls)


def _part_signature(part: dict) -> str:
    for key in ("thoughtSignature", "thought_signature"):
        value = part.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _openai_messages(messages: list[TurnMessage]) -> list[dict]:
    converted: list[dict] = []
    for message in messages:
        if message.role == "user":
            converted.append({"role": "user", "content": message.content})
        elif message.role == "assistant":
            row: dict = {"role": "assistant", "content": message.content or None}
            if message.tool_calls:
                row["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in message.tool_calls
                ]
            converted.append(row)
        elif message.role == "tool":
            converted.append({"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content})
    return converted


def _openai_turn(payload: dict) -> LlmTurn:
    choices = payload.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    calls: list[ToolCall] = []
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        name = str(function.get("name") or "")
        if not name:
            continue
        raw = function.get("arguments") if function.get("arguments") is not None else "{}"
        args: dict = {}
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                args = parsed
        calls.append(ToolCall(id=str(call.get("id") or uuid.uuid4().hex), name=name, arguments=args))
    return LlmTurn(str(message.get("content") or ""), calls)


def _anthropic_messages(messages: list[TurnMessage]) -> list[dict]:
    converted: list[dict] = []
    pending: list[dict] = []

    def flush() -> None:
        if pending:
            converted.append({"role": "user", "content": list(pending)})
            pending.clear()

    for message in messages:
        if message.role == "tool":
            pending.append({"type": "tool_result", "tool_use_id": message.tool_call_id, "content": message.content})
            continue
        flush()
        if message.role == "user":
            converted.append({"role": "user", "content": message.content})
        elif message.role == "assistant":
            content: list[dict] = []
            if message.content:
                content.append({"type": "text", "text": message.content})
            for call in message.tool_calls:
                content.append({"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments})
            converted.append({"role": "assistant", "content": content})
    flush()
    return converted


def _anthropic_turn(payload: dict) -> LlmTurn:
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in payload.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text"):
            texts.append(str(block["text"]))
        elif block.get("type") == "tool_use" and block.get("name"):
            args = block.get("input") if isinstance(block.get("input"), dict) else {}
            calls.append(ToolCall(id=str(block.get("id") or uuid.uuid4().hex), name=str(block["name"]), arguments=args))
    return LlmTurn("\n".join(texts).strip(), calls)
