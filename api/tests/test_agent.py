import json
import logging
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import AgentToolCall, Device, Event
from app.services.agent.dates import GUATEMALA, resolve_window
from app.services.agent.llm import (
    MODEL_UNAVAILABLE_MESSAGE,
    NOT_CONFIGURED_MESSAGE,
    RATE_LIMIT_MESSAGE,
    ListedModel,
    LlmTurn,
    RateLimited,
    ToolCall,
    TurnMessage,
    choose_model,
    clear_model_cache,
    plain_text,
    request_json,
)
from app.services.agent.providers import AnthropicProvider, GeminiProvider, OpenAiProvider, build_provider
from app.services.agent.tools import TOOL_SCHEMAS
from tests.conftest import auth_header
from tests.test_dashboard import local_noon, post_event
from tests.test_device import attach_device, open_site, zone_body

TOOL_NAMES = {
    "search_events",
    "count_events",
    "summarize_events",
    "get_event",
    "change_event_status",
    "get_usage",
    "get_equipment_status",
    "briefing",
}


class ScriptedProvider:
    def __init__(self, turns: list, models: list[ListedModel] | None = None) -> None:
        self.turns = list(turns)
        self.models = (
            [ListedModel(id="unit-flash", supports_function_calling=True, prefer=True)] if models is None else models
        )
        self.list_calls = 0
        self.completions: list[dict] = []

    def list_models(self) -> list[ListedModel]:
        self.list_calls += 1
        return list(self.models)

    def complete(self, *, model: str, system: str, messages: list[TurnMessage], tools: list[dict]) -> LlmTurn:
        self.completions.append(
            {
                "model": model,
                "system": system,
                "messages": [
                    {
                        "role": message.role,
                        "content": message.content,
                        "tool_calls": [
                            {"name": call.name, "arguments": call.arguments} for call in message.tool_calls
                        ],
                    }
                    for message in messages
                ],
                "tools": [tool["name"] for tool in tools],
            }
        )
        if not self.turns:
            return LlmTurn(content="Listo.", tool_calls=[])
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


@pytest.fixture(autouse=True)
def llm_settings(monkeypatch):
    clear_model_cache()
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "")
    yield
    clear_model_cache()


def install(monkeypatch, provider: ScriptedProvider) -> None:
    monkeypatch.setattr("app.services.agent.runner.get_provider", lambda: provider)


def event_facts(event_id: str) -> tuple[str, datetime | None, str | None]:
    db = SessionLocal()
    try:
        event = db.get(Event, uuid.UUID(event_id))
        assert event is not None
        return event.status, event.reviewed_at, event.snapshot_key
    finally:
        db.close()


def tool_rows(organization_id: str) -> list[tuple[str, str]]:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(AgentToolCall)
            .where(AgentToolCall.organization_id == uuid.UUID(organization_id))
            .order_by(AgentToolCall.created_at)
        ).all()
        return [(row.tool_name, row.outcome) for row in rows]
    finally:
        db.close()


def ask(client, headers, text: str, site_id: str | None = None) -> dict:
    payload: dict = {"content": text}
    if site_id is not None:
        payload["site_id"] = site_id
    response = client.post("/agent/messages", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_guatemala_windows() -> None:
    moment = datetime(2026, 10, 1, 18, 42, tzinfo=GUATEMALA)
    assert resolve_window("yesterday", None, None, moment) == (
        datetime(2026, 9, 30, 0, 0, tzinfo=GUATEMALA),
        datetime(2026, 10, 1, 0, 0, tzinfo=GUATEMALA),
    )
    week = resolve_window("this_week", None, None, moment)
    assert week == (
        datetime(2026, 9, 28, 0, 0, tzinfo=GUATEMALA),
        datetime(2026, 10, 2, 0, 0, tzinfo=GUATEMALA),
    )
    assert resolve_window("last_night", None, None, moment) == (
        datetime(2026, 9, 30, 20, 0, tzinfo=GUATEMALA),
        datetime(2026, 10, 1, 6, 0, tzinfo=GUATEMALA),
    )
    month = resolve_window("this_month", None, None, moment)
    assert month[0].date().isoformat() == "2026-10-01"
    assert month[1].date().isoformat() == "2026-11-01"
    today = resolve_window("today", None, None, moment)
    assert today[0].date().isoformat() == "2026-10-01"
    assert today[1].date().isoformat() == "2026-10-02"


def test_choose_model_prefers_plain_flash_and_rejects_a_missing_name() -> None:
    models = [
        ListedModel("unit-pro", True, False, False),
        ListedModel("models/unit-flash-preview", True, True, True),
        ListedModel("models/unit-flash", True, True, False),
        ListedModel("unit-embed", False, False, False),
    ]
    assert choose_model(models, "", prefer_flash=True) == "models/unit-flash"
    lite = [
        ListedModel("models/unit-3.8-flash", True, True, False),
        ListedModel("models/unit-2.5-flash-lite", True, True, False),
        ListedModel("models/unit-flash-lite-preview", True, True, True),
    ]
    assert choose_model(lite, "", prefer_flash=True) == "models/unit-2.5-flash-lite"
    ranked = [
        ListedModel("models/unit-omni-9.9-flash", True, True, True),
        ListedModel("models/unit-2.0-flash", True, True, False),
        ListedModel("models/unit-3.4-flash", True, True, False),
    ]
    assert choose_model(ranked, "", prefer_flash=True) == "models/unit-3.4-flash"
    assert choose_model(models, "unit-pro", prefer_flash=True) == "unit-pro"
    with pytest.raises(Exception):
        choose_model(models, "missing-model", prefer_flash=True)
    with pytest.raises(Exception):
        choose_model(models, "unit-embed", prefer_flash=True)
    assert choose_model(models, "", prefer_flash=False) == "unit-pro"


def test_provider_follows_the_env_name() -> None:
    assert isinstance(build_provider("openai", "k"), OpenAiProvider)
    assert isinstance(build_provider("anthropic", "k"), AnthropicProvider)
    assert isinstance(build_provider("gemini", "k"), GeminiProvider)


def test_gemini_list_selects_a_flash_model_from_the_payload() -> None:
    def request(method, url, *, headers, params=None, body=None):
        assert method == "GET"
        assert headers["x-goog-api-key"] == "secret"
        return {
            "models": [
                {"name": "models/unit-pro", "displayName": "Pro", "supportedGenerationMethods": ["generateContent"]},
                {
                    "name": "models/unit-flash-preview",
                    "displayName": "Flash preview",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {"name": "models/unit-omni-9.9-flash", "displayName": "Omni flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/unit-2.0-flash", "displayName": "Flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/unit-flash", "displayName": "Flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/unit-embed", "displayName": "Embed", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/unit-image", "displayName": "Image", "supportedGenerationMethods": ["generateContent"]},
            ]
        }

    models = GeminiProvider("secret", request=request).list_models()
    assert choose_model(models, "", prefer_flash=True) == "models/unit-2.0-flash"


def test_openai_list_skips_non_chat_modalities_and_keeps_the_newest() -> None:
    def request(method, url, *, headers, params=None, body=None):
        return {
            "data": [
                {"id": "unit-whisper", "created": 300, "owned_by": "openai"},
                {"id": "unit-old", "created": 10, "owned_by": "openai"},
                {"id": "unit-new", "created": 200, "owned_by": "openai"},
            ]
        }

    models = OpenAiProvider("k", request=request).list_models()
    assert choose_model(models, "", prefer_flash=False) == "unit-new"


def test_anthropic_list_uses_tool_capability_and_api_order() -> None:
    def request(method, url, *, headers, params=None, body=None):
        assert headers["x-api-key"] == "k"
        return {
            "data": [
                {"id": "unit-first", "type": "model", "capabilities": {"tool_use": {"supported": True}}},
                {"id": "unit-blocked", "type": "model", "capabilities": {"tool_use": {"supported": False}}},
            ]
        }

    models = AnthropicProvider("k", request=request).list_models()
    assert choose_model(models, "", prefer_flash=False) == "unit-first"


def test_adapters_read_a_function_call_without_the_network() -> None:
    def gemini_request(method, url, *, headers, params=None, body=None):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "interno", "thought": True, "thoughtSignature": "sig-thought"},
                            {
                                "functionCall": {"name": "count_events", "args": {"period": "yesterday"}},
                                "thoughtSignature": "sig-call",
                            },
                        ]
                    }
                }
            ]
        }

    gemini = GeminiProvider("k", request=gemini_request).complete(
        model="models/unit-flash",
        system="sistema",
        messages=[TurnMessage(role="user", content="ayer")],
        tools=TOOL_SCHEMAS,
    )
    assert gemini.tool_calls[0].name == "count_events"
    assert gemini.tool_calls[0].arguments == {"period": "yesterday"}
    assert gemini.tool_calls[0].signature == "sig-call"
    assert gemini.content == ""

    replayed: dict = {}

    def replay_request(method, url, *, headers, params=None, body=None):
        replayed["body"] = body
        return {"candidates": [{"content": {"parts": [{"text": "Hubo 2."}]}}]}

    GeminiProvider("k", request=replay_request).complete(
        model="models/unit-flash",
        system="sistema",
        messages=[
            TurnMessage(role="user", content="ayer"),
            TurnMessage(role="assistant", content="", tool_calls=gemini.tool_calls),
            TurnMessage(role="tool", content='{"total": 2}', tool_name="count_events", tool_call_id="1"),
        ],
        tools=TOOL_SCHEMAS,
    )
    echoed = replayed["body"]["contents"][1]["parts"][0]
    assert echoed["functionCall"]["name"] == "count_events"
    assert echoed["thoughtSignature"] == "sig-call"

    def openai_request(method, url, *, headers, params=None, body=None):
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "get_usage", "arguments": "{\"period\": \"this_month\"}"},
                            }
                        ],
                    }
                }
            ]
        }

    openai = OpenAiProvider("k", request=openai_request).complete(
        model="unit-new", system="sistema", messages=[TurnMessage(role="user", content="mes")], tools=TOOL_SCHEMAS
    )
    assert openai.tool_calls[0].name == "get_usage"
    assert openai.tool_calls[0].arguments == {"period": "this_month"}

    def anthropic_request(method, url, *, headers, params=None, body=None):
        return {
            "content": [
                {"type": "tool_use", "id": "tool-1", "name": "get_equipment_status", "input": {}},
            ]
        }

    anthropic = AnthropicProvider("k", request=anthropic_request).complete(
        model="unit-first", system="sistema", messages=[TurnMessage(role="user", content="estado")], tools=TOOL_SCHEMAS
    )
    assert anthropic.tool_calls[0].name == "get_equipment_status"


def test_gemini_uses_the_preceding_thought_signature_when_the_call_has_none() -> None:
    def request(method, url, *, headers, params=None, body=None):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thought": True, "thoughtSignature": "sig-thought"},
                            {"functionCall": {"name": "count_events", "args": {"period": "today"}}},
                        ]
                    }
                }
            ]
        }

    turn = GeminiProvider("k", request=request).complete(
        model="models/unit-flash",
        system="sistema",
        messages=[TurnMessage(role="user", content="hoy")],
        tools=TOOL_SCHEMAS,
    )
    assert turn.tool_calls[0].signature == "sig-thought"


def test_http_429_retries_then_raises(monkeypatch) -> None:
    calls = {"n": 0}
    slept: list[float] = []

    class Response:
        status_code = 429
        headers: dict[str, str] = {}

        def json(self):
            return {}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, *args, **kwargs):
            calls["n"] += 1
            return Response()

    monkeypatch.setattr("app.services.agent.llm.httpx.Client", Client)
    monkeypatch.setattr("app.services.agent.llm._sleep", lambda seconds: slept.append(seconds))
    with pytest.raises(RateLimited):
        request_json("GET", "https://example.test/models", headers={})
    assert calls["n"] == 4
    assert slept == [2.0, 4.0, 8.0]


def test_http_429_retries_once_and_honors_retry_after(monkeypatch) -> None:
    calls = {"n": 0}
    slept: list[float] = []

    class Limited:
        status_code = 429
        headers = {"retry-after": "45"}

        def json(self):
            return {}

    class Ok:
        status_code = 200
        headers: dict[str, str] = {}

        def json(self):
            return {"ok": True}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, *args, **kwargs):
            calls["n"] += 1
            return Limited() if calls["n"] == 1 else Ok()

    monkeypatch.setattr("app.services.agent.llm.httpx.Client", Client)
    monkeypatch.setattr("app.services.agent.llm._sleep", lambda seconds: slept.append(seconds))
    assert request_json("GET", "https://example.test/models", headers={}) == {"ok": True}
    assert calls["n"] == 2
    assert slept == [20.0]


def test_plain_text_drops_emphasis_markers() -> None:
    assert plain_text("Hubo **6** intrusiones y *12.00* minutos.") == "Hubo 6 intrusiones y 12.00 minutos."


def test_missing_configured_model_replies_in_spanish(client, accounts, monkeypatch) -> None:
    headers, _camera_id, _zone_id, _token = open_site(client, accounts())
    provider = ScriptedProvider([], models=[ListedModel("unit-flash", True, True)])
    install(monkeypatch, provider)
    monkeypatch.setattr(settings, "llm_model", "missing-model")
    body = ask(client, headers, "Hola")
    assert body["messages"][-1]["content"] == MODEL_UNAVAILABLE_MESSAGE
    assert provider.completions == []
    assert provider.list_calls == 1


def test_model_choice_is_cached_and_logged(client, accounts, monkeypatch, caplog) -> None:
    headers, _camera_id, _zone_id, _token = open_site(client, accounts())
    provider = ScriptedProvider(
        [LlmTurn(content="Primera.", tool_calls=[]), LlmTurn(content="Segunda.", tool_calls=[])],
        models=[
            ListedModel("unit-pro", True, False),
            ListedModel("unit-flash", True, True),
        ],
    )
    install(monkeypatch, provider)
    with caplog.at_level(logging.INFO, logger="sentinel.agent"):
        first = ask(client, headers, "Hola")
        second = ask(client, headers, "Otra vez")
    assert first["messages"][-1]["content"] == "Primera."
    assert second["messages"][-1]["content"] == "Segunda."
    assert provider.list_calls == 1
    assert {item["model"] for item in provider.completions} == {"unit-flash"}
    assert "llm model selected provider=gemini model=unit-flash" in caplog.text


def test_empty_model_list_uses_the_same_spanish_message(client, accounts, monkeypatch) -> None:
    headers, _camera_id, _zone_id, _token = open_site(client, accounts())
    provider = ScriptedProvider([], models=[])
    install(monkeypatch, provider)
    body = ask(client, headers, "Hola")
    assert body["messages"][-1]["content"] == MODEL_UNAVAILABLE_MESSAGE
    assert provider.completions == []


def test_rate_limit_is_a_friendly_spanish_message(client, accounts, monkeypatch) -> None:
    headers, _camera_id, _zone_id, _token = open_site(client, accounts())
    provider = ScriptedProvider([RateLimited()])
    install(monkeypatch, provider)
    body = ask(client, headers, "Hola")
    assert body["messages"][-1]["content"] == RATE_LIMIT_MESSAGE


def test_unconfigured_assistant_does_not_call_a_provider(client, accounts, monkeypatch) -> None:
    headers, _camera_id, _zone_id, _token = open_site(client, accounts())
    provider = ScriptedProvider([])
    install(monkeypatch, provider)
    monkeypatch.setattr(settings, "llm_api_key", "")
    body = ask(client, headers, "Hola")
    assert body["messages"][-1]["content"] == NOT_CONFIGURED_MESSAGE
    assert provider.list_calls == 0
    assert provider.completions == []


def test_search_stays_in_the_organization_and_hides_snapshots(client, accounts, monkeypatch) -> None:
    headers, camera_id, zone_id, token = open_site(client, accounts())
    other_headers, other_camera, other_zone, other_token = open_site(client, accounts())
    yesterday = post_event(client, token, camera_id, zone_id, local_noon(-1))
    own = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    foreign = post_event(client, other_token, other_camera, other_zone, datetime.now(GUATEMALA))
    assert yesterday.status_code == 200 and yesterday.json()["created"] is True
    assert own.status_code == 200 and own.json()["created"] is True
    assert foreign.status_code == 200 and foreign.json()["created"] is True
    _status, _reviewed, snapshot_key = event_facts(own.json()["id"])
    assert snapshot_key
    foreign_key = event_facts(foreign.json()["id"])[2]
    provider = ScriptedProvider(
        [
            LlmTurn(content="", tool_calls=[ToolCall(id="1", name="count_events", arguments={"period": "today"})]),
            LlmTurn(
                content="",
                tool_calls=[ToolCall(id="2", name="get_event", arguments={"event_id": foreign.json()["id"]})],
            ),
            LlmTurn(
                content="",
                tool_calls=[ToolCall(id="3", name="search_events", arguments={"period": "today"})],
            ),
            LlmTurn(content="Hay un evento.", tool_calls=[]),
        ]
    )
    install(monkeypatch, provider)
    body = ask(client, headers, "¿Qué pasó hoy?")
    assert body["messages"][-1]["content"] == "Hay un evento."
    assert set(provider.completions[0]["tools"]) == TOOL_NAMES
    count_payload = provider.completions[1]["messages"][-1]["content"]
    assert '"total": 1' in count_payload
    detail_payload = provider.completions[2]["messages"][-1]["content"]
    assert "Evento no encontrado" in detail_payload
    blob = json.dumps(provider.completions)
    assert snapshot_key not in blob
    assert foreign_key not in blob
    assert "snapshot" not in blob.casefold()
    assert "/videos/" not in blob
    assert other_token not in blob
    start, _end = resolve_window("yesterday", None, None)
    counted = ScriptedProvider(
        [
            LlmTurn(content="", tool_calls=[ToolCall(id="4", name="count_events", arguments={"period": "yesterday"})]),
            LlmTurn(content="Ayer hubo uno.", tool_calls=[]),
        ]
    )
    install(monkeypatch, counted)
    ask(client, headers, "¿Y ayer?")
    assert start.isoformat() in counted.completions[1]["messages"][-1]["content"]
    assert '"total": 1' in counted.completions[1]["messages"][-1]["content"]


def test_status_change_waits_for_confirmation(client, accounts, monkeypatch) -> None:
    account = accounts()
    headers, camera_id, zone_id, token = open_site(client, account)
    created = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    event_id = created.json()["id"]
    provider = ScriptedProvider(
        [
            LlmTurn(
                content="Ya quedó marcado.",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="change_event_status",
                        arguments={"event_id": event_id, "status": "false_positive"},
                    )
                ],
            )
        ]
    )
    install(monkeypatch, provider)
    body = ask(client, headers, "Márcalo como falso positivo")
    assert body["confirmation"]["prompt"].startswith("¿Confirmas marcar el evento de intrusión")
    assert "falso positivo" in body["confirmation"]["prompt"]
    assert "Ya quedó marcado" not in json.dumps(body)
    assert event_facts(event_id)[0] == "new"
    assert ("change_event_status", "pending_confirmation") in tool_rows(account["organization_id"])
    typed = ask(client, headers, "sí")
    assert typed["confirmation"] is None
    assert typed["messages"][-1]["content"].startswith("Listo.")
    assert provider.list_calls == 1
    assert len(provider.completions) == 1
    status, reviewed, _snapshot = event_facts(event_id)
    assert status == "false_positive"
    assert reviewed is None
    outcomes = tool_rows(account["organization_id"])
    assert ("change_event_status", "executed") in outcomes


def test_cancel_and_unrelated_text_do_not_change_the_event(client, accounts, monkeypatch) -> None:
    account = accounts()
    headers, camera_id, zone_id, token = open_site(client, account)
    created = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    event_id = created.json()["id"]
    provider = ScriptedProvider(
        [
            LlmTurn(
                content="",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="change_event_status",
                        arguments={"event_id": event_id, "status": "resolved"},
                    )
                ],
            ),
            LlmTurn(content="Sigo a la espera.", tool_calls=[]),
        ]
    )
    install(monkeypatch, provider)
    proposed = ask(client, headers, "Resuélvelo")
    assert event_facts(event_id)[0] == "new"
    asked = ask(client, headers, "¿Cuántos eventos hay?")
    assert asked["confirmation"]["id"] == proposed["confirmation"]["id"]
    assert event_facts(event_id)[0] == "new"
    cancelled = client.post("/agent/cancel", json={"id": proposed["confirmation"]["id"]}, headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["confirmation"] is None
    assert cancelled.json()["messages"][-1]["content"] == "De acuerdo. No cambié el evento."
    assert event_facts(event_id)[0] == "new"


def test_operator_can_mark_in_review_and_cannot_change_the_rate(client, accounts, monkeypatch) -> None:
    account = accounts()
    headers, camera_id, zone_id, token = open_site(client, account)
    created = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    event_id = created.json()["id"]
    operator = client.post(
        "/users",
        json={
            "email": f"op-{uuid.uuid4()}@example.com",
            "password": "password1",
            "full_name": "Operador",
            "role": "operator",
        },
        headers=headers,
    )
    assert operator.status_code == 201
    operator_headers = auth_header(client, {"email": operator.json()["email"], "password": "password1"})
    provider = ScriptedProvider(
        [
            LlmTurn(
                content="",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="change_event_status",
                        arguments={"event_id": event_id, "status": "in_review"},
                    )
                ],
            )
        ]
    )
    install(monkeypatch, provider)
    body = ask(client, operator_headers, "Pásalo a revisión")
    assert set(provider.completions[0]["tools"]) == TOOL_NAMES
    confirmed = client.post("/agent/confirm", json={"id": body["confirmation"]["id"]}, headers=operator_headers)
    assert confirmed.status_code == 200
    status, reviewed, _snapshot = event_facts(event_id)
    assert status == "in_review"
    assert reviewed is not None
    assert client.put("/pricing", json={"rate_per_minute": 2}, headers=operator_headers).status_code == 403


def test_usage_and_equipment_omit_paths_and_tokens(client, accounts, monkeypatch) -> None:
    account = accounts()
    headers, camera_id, _zone_id, token = open_site(client, account)
    today = datetime.now(GUATEMALA).date().isoformat()
    usage = client.post(
        "/device/usage",
        json={"client_report_id": str(uuid.uuid4()), "camera_id": camera_id, "usage_date": today, "analyzed_minutes": 1.5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert usage.status_code == 200
    priced = client.put("/pricing", json={"rate_per_minute": 2}, headers=headers)
    assert priced.status_code == 200
    db = SessionLocal()
    try:
        device = db.scalar(select(Device).where(Device.organization_id == uuid.UUID(account["organization_id"])))
        assert device is not None
        device.last_seen_at = datetime.now(timezone.utc)
        token_hash = device.token_hash
        db.commit()
    finally:
        db.close()
    provider = ScriptedProvider(
        [
            LlmTurn(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="get_usage", arguments={"period": "this_month"}),
                    ToolCall(id="2", name="get_equipment_status", arguments={}),
                ],
            ),
            LlmTurn(content="Listo.", tool_calls=[]),
        ]
    )
    install(monkeypatch, provider)
    ask(client, headers, "Minutos y equipos")
    blob = json.dumps(provider.completions, ensure_ascii=False)
    assert "1.50" in blob
    assert "3.00" in blob
    assert "en línea" in blob
    assert "/videos/" not in blob
    assert token not in blob
    assert token_hash not in blob
    assert ("get_usage", "executed") in tool_rows(account["organization_id"])
    assert ("get_equipment_status", "executed") in tool_rows(account["organization_id"])


def test_suggested_questions_skip_the_model(client, accounts, monkeypatch) -> None:
    headers, camera_id, zone_id, token = open_site(client, accounts())
    created = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    assert created.status_code == 200 and created.json()["created"] is True
    provider = ScriptedProvider([])
    install(monkeypatch, provider)
    monkeypatch.setattr(settings, "llm_api_key", "")
    week = ask(client, headers, "¿Cuántas intrusiones hubo esta semana?")
    yesterday = ask(client, headers, "Resume los eventos críticos de ayer")
    usage = ask(client, headers, "¿Cuántos minutos se analizaron este mes y cuál es el costo estimado?")
    assert provider.list_calls == 0
    assert provider.completions == []
    assert week["messages"][-1]["content"].startswith("Esta semana hubo ")
    assert "intrusión" in week["messages"][-1]["content"]
    assert yesterday["messages"][-1]["content"] == "Ayer no hubo eventos críticos."
    assert "minutos" in usage["messages"][-1]["content"]
    assert "*" not in week["messages"][-1]["content"]


def test_a_free_form_question_still_calls_the_model_and_stores_plain_text(client, accounts, monkeypatch) -> None:
    headers, _camera_id, _zone_id, _token = open_site(client, accounts())
    provider = ScriptedProvider([LlmTurn(content="Hubo **6** intrusiones.", tool_calls=[])])
    install(monkeypatch, provider)
    body = ask(client, headers, "Dime las intrusiones de esta semana")
    assert provider.completions
    assert "Senti" in provider.completions[0]["system"]
    assert "briefing" in provider.completions[0]["tools"]
    assert body["messages"][-1]["content"] == "Hubo 6 intrusiones."


def test_site_scope_filters_tools_and_rejects_another_organization(client, accounts, monkeypatch) -> None:
    account = accounts()
    headers, camera_id, zone_id, token = open_site(client, account)
    sites = client.get("/sites", headers=headers).json()
    home_id = next(site["id"] for site in sites if site["name"] == "Planta")
    other = client.post("/sites", json={"name": "Bodega"}, headers=headers)
    assert other.status_code == 201
    other_id = other.json()["id"]
    camera = client.post(
        "/cameras",
        json={
            "site_id": other_id,
            "name": "Andén",
            "source_type": "file",
            "file_path": "/videos/demo1.mp4",
            "fps": 2,
        },
        headers=headers,
    )
    assert camera.status_code == 201
    other_camera = camera.json()["id"]
    zone = client.post(f"/cameras/{other_camera}/zones", json=zone_body(), headers=headers)
    assert zone.status_code == 201
    other_token = attach_device(account["organization_id"], other_id)
    moment = datetime.now(GUATEMALA)
    assert post_event(client, token, camera_id, zone_id, moment).json()["created"] is True
    foreign = post_event(client, other_token, other_camera, zone.json()["id"], moment)
    assert foreign.status_code == 200 and foreign.json()["created"] is True
    today = moment.date().isoformat()
    assert (
        client.post(
            "/device/usage",
            json={"client_report_id": str(uuid.uuid4()), "camera_id": camera_id, "usage_date": today, "analyzed_minutes": 1.5},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/device/usage",
            json={
                "client_report_id": str(uuid.uuid4()),
                "camera_id": other_camera,
                "usage_date": today,
                "analyzed_minutes": 4,
            },
            headers={"Authorization": f"Bearer {other_token}"},
        ).status_code
        == 200
    )
    stranger = accounts()
    stranger_headers, _camera, _zone, _token = open_site(client, stranger)
    stranger_site = client.get("/sites", headers=stranger_headers).json()[0]["id"]
    denied = client.post(
        "/agent/messages",
        json={"content": "¿Cuántas intrusiones hubo esta semana?", "site_id": stranger_site},
        headers=headers,
    )
    assert denied.status_code == 422
    provider = ScriptedProvider([])
    install(monkeypatch, provider)
    monkeypatch.setattr(settings, "llm_api_key", "")
    scoped = ask(client, headers, "¿Cuántas intrusiones hubo esta semana?", home_id)
    assert scoped["messages"][-1]["content"] == "Esta semana hubo 1 intrusión en Planta."
    assert provider.completions == []
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    scoped_model = ScriptedProvider(
        [
            LlmTurn(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="count_events", arguments={"period": "today"}),
                    ToolCall(id="2", name="get_event", arguments={"event_id": foreign.json()["id"]}),
                    ToolCall(id="3", name="get_equipment_status", arguments={}),
                    ToolCall(id="4", name="get_usage", arguments={"period": "this_month"}),
                ],
            ),
            LlmTurn(content="Solo la planta.", tool_calls=[]),
        ]
    )
    install(monkeypatch, scoped_model)
    body = ask(client, headers, "Resume este sitio", home_id)
    assert body["messages"][-1]["content"] == "Solo la planta."
    system = scoped_model.completions[0]["system"]
    assert "Senti" in system
    assert "únicamente el sitio Planta" in system
    payloads = [message["content"] for completion in scoped_model.completions for message in completion["messages"]]
    joined = "\n".join(payloads)
    assert '"total": 1' in joined
    assert "Evento no encontrado" in joined
    assert "Acceso" in joined
    assert "Andén" not in joined
    assert "1.50" in joined
    assert "4.00" not in joined
    assert "5.50" not in joined
    wide = ScriptedProvider(
        [
            LlmTurn(content="", tool_calls=[ToolCall(id="5", name="count_events", arguments={"period": "today"})]),
            LlmTurn(content="En todos.", tool_calls=[]),
        ]
    )
    install(monkeypatch, wide)
    ask(client, headers, "¿Qué hay en todos los sitios?")
    assert "todos los sitios" in wide.completions[0]["system"]
    assert '"total": 2' in wide.completions[1]["messages"][-1]["content"]


def test_reset_clears_the_thread_and_leaves_the_event(client, accounts, monkeypatch) -> None:
    account = accounts()
    headers, camera_id, zone_id, token = open_site(client, account)
    created = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    event_id = created.json()["id"]
    provider = ScriptedProvider(
        [
            LlmTurn(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="change_event_status", arguments={"event_id": event_id, "status": "resolved"})
                ],
            )
        ]
    )
    install(monkeypatch, provider)
    proposed = ask(client, headers, "Resuélvelo")
    assert proposed["confirmation"] is not None
    reset = client.post("/agent/reset", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["messages"] == []
    assert reset.json()["confirmation"] is None
    assert event_facts(event_id)[0] == "new"
