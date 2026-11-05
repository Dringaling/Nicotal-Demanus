from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from app.config import load_settings
from app.llm import LLMClient, LLMError, _merge_specs, split_into_chunks
from app.sample import sample_deck
from app.schema import BulletItem, DeckSpec, SlideSpec

CONFIG = Path(__file__).resolve().parents[1] / "config" / "providers.toml"


def make_settings(
    tmp_path: Path,
    *,
    local_cache: bool = False,
    max_retries: int = 0,
):
    base = load_settings(CONFIG)
    cache = replace(
        base.provider.cache,
        local_cache=local_cache,
        local_cache_dir=str(tmp_path / "cache"),
    )
    provider = replace(
        base.provider,
        api_key_file=str(tmp_path / "key.env"),
        cache=cache,
        max_retries=max_retries,
    )
    (tmp_path / "key.env").write_text(
        "DEEPINFRA_FLEX_C79C=test-key\n", encoding="utf-8"
    )
    return replace(base, provider=provider)


def chat_response(content: str, usage: dict | None = None) -> dict:
    return {
        "id": "chatcmpl-test",
        "model": "deepseek-ai/DeepSeek-V4.1-Flash-1017",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": usage
        or {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "cached_tokens": 80,
            "cache_write_tokens": 20,
            "estimated_cost": 0.0005,
        },
    }


def valid_content() -> str:
    return sample_deck().model_dump_json()


def make_client(settings, handler, tmp_path: Path) -> LLMClient:
    return LLMClient(
        settings,
        transport=httpx.MockTransport(handler),
        root=tmp_path,
    )


async def test_payload_uses_flex_and_cache_key(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    body = seen[0]
    assert body["service_tier"] == "flex"
    assert body["prompt_cache_key"] == "demanus-deck-v4"
    assert body["model"] == "deepseek-ai/DeepSeek-V4.1-Flash-1017"
    assert body["response_format"]["type"] == "json_schema"


async def test_system_prompt_is_stable_and_desc_is_last(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec("Báo cáo A", "Mô tả A cho bệnh nhân")
    await client.generate_spec("Báo cáo B", "Mô tả B cho bệnh nhân")

    assert seen[0]["messages"][0]["content"] == seen[1]["messages"][0]["content"]
    assert "Mô tả A cho bệnh nhân" in seen[0]["messages"][-1]["content"]
    assert "Mô tả A cho bệnh nhân" not in seen[0]["messages"][0]["content"]


async def test_authorization_header_and_key_not_in_body(tmp_path: Path) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    assert captured[0].headers["authorization"] == "Bearer test-key"
    assert "test-key" not in captured[0].content.decode()


async def test_parse_plain_json_and_usage(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    spec, usage = await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    assert spec.title == sample_deck().title
    assert usage.prompt_tokens == 100
    assert usage.cached_tokens == 80
    assert usage.estimated_cost == pytest.approx(0.0005)
    assert usage.from_cache is False


async def test_parse_markdown_fence(tmp_path: Path) -> None:
    fenced = f"```json\n{valid_content()}\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=chat_response(fenced))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    spec, _ = await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")
    assert spec.title == sample_deck().title


async def test_repair_invalid_json(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            return httpx.Response(200, json=chat_response("không phải json"))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    spec, _ = await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    assert spec.title == sample_deck().title
    assert len(seen) == 2
    assert seen[1]["response_format"]["type"] == "json_object"


async def test_retry_on_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, text="model busy")
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(
        make_settings(tmp_path, max_retries=1), handler, tmp_path
    )
    spec, _ = await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    assert spec.title == sample_deck().title
    assert calls["count"] == 2


async def test_retry_exhausted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="model busy")

    client = make_client(
        make_settings(tmp_path, max_retries=1), handler, tmp_path
    )
    with pytest.raises(LLMError, match="thất bại"):
        await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")


async def test_local_cache_hit(tmp_path: Path) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(
        make_settings(tmp_path, local_cache=True), handler, tmp_path
    )
    first, first_usage = await client.generate_spec(
        "Báo cáo", "Mô tả chi tiết về bệnh nhân"
    )
    second, second_usage = await client.generate_spec(
        "Báo cáo", "Mô tả chi tiết về bệnh nhân"
    )

    assert calls["count"] == 1
    assert first.title == second.title
    assert first_usage.from_cache is False
    assert second_usage.from_cache is True


def test_split_short_text_is_single_chunk() -> None:
    assert split_into_chunks("abc", 10) == ["abc"]


def test_split_long_text_by_paragraphs() -> None:
    text = "a" * 20 + "\n\n" + "b" * 20 + "\n\n" + "c" * 20
    chunks = split_into_chunks(text, 25)
    assert len(chunks) == 3
    assert "".join(chunks).replace("\n\n", "") == text.replace("\n\n", "")


def test_split_hard_splits_long_paragraph() -> None:
    chunks = split_into_chunks("x" * 25, 10)
    assert len(chunks) == 3
    assert all(len(chunk) <= 10 for chunk in chunks)


def _chunk_deck() -> DeckSpec:
    return DeckSpec(
        title="Báo cáo",
        slides=[
            SlideSpec(layout="title", title="Báo cáo"),
            SlideSpec(
                layout="bullets",
                title="Nội dung",
                bullets=[BulletItem(text="Ý chính")],
            ),
            SlideSpec(layout="closing", title="Cảm ơn"),
        ],
    )


def test_merge_specs_dedupes_title_and_closing() -> None:
    merged = _merge_specs([_chunk_deck(), _chunk_deck()])
    assert [slide.layout for slide in merged.slides] == [
        "title",
        "bullets",
        "closing",
    ]


def test_merge_specs_adds_missing_title_and_closing() -> None:
    deck = DeckSpec(
        title="Báo cáo",
        slides=[
            SlideSpec(
                layout="bullets",
                title="Ý chính",
                bullets=[BulletItem(text="Nội dung")],
            )
        ],
    )
    merged = _merge_specs([deck])
    assert merged.slides[0].layout == "title"
    assert merged.slides[-1].layout == "closing"


def test_merge_specs_caps_at_sixty() -> None:
    slides = [
        SlideSpec(
            layout="bullets",
            title=f"Ý {index}",
            bullets=[BulletItem(text="Nội dung")],
        )
        for index in range(60)
    ]
    deck = DeckSpec(title="Báo cáo", slides=slides)
    merged = _merge_specs([deck])
    assert len(merged.slides) == 60
    assert merged.slides[0].layout == "title"
    assert merged.slides[-1].layout == "closing"


async def test_chunk_markers_and_count(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    settings = make_settings(tmp_path)
    generation = replace(settings.provider.generation, chunk_chars=10)
    settings = replace(
        settings, provider=replace(settings.provider, generation=generation)
    )
    client = make_client(settings, handler, tmp_path)

    await client.generate_spec("Báo cáo", "a" * 25)

    assert len(seen) == 3
    for index, body in enumerate(seen, start=1):
        user = body["messages"][-1]["content"]
        assert f"--- CHUNK START ({index}/3) ---" in user
        assert f"--- CHUNK END ({index}/3) ---" in user


async def test_system_prompt_is_english(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    system = seen[0]["messages"][0]["content"]
    assert "You are" in system
    assert "CHUNK PROTOCOL" in system


async def test_chunk_failure_reports_index(tmp_path: Path) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 2:
            return httpx.Response(500, text="chunk failed")
        return httpx.Response(200, json=chat_response(valid_content()))

    settings = make_settings(tmp_path)
    generation = replace(settings.provider.generation, chunk_chars=10)
    settings = replace(
        settings, provider=replace(settings.provider, generation=generation)
    )
    client = make_client(settings, handler, tmp_path)

    with pytest.raises(LLMError, match="chunk 2/"):
        await client.generate_spec("Báo cáo", "a" * 25)


async def test_template_context_in_system_prompt(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec(
        "Báo cáo",
        "Mô tả chi tiết về bệnh nhân",
        template="dividing-fractions",
    )

    system = seen[0]["messages"][0]["content"]
    user = seen[0]["messages"][-1]["content"]
    assert "TEMPLATE CONTEXT" in system
    assert "TITLE_AND_BODY" in system
    assert "accent: #4285F4" in system
    assert "TEMPLATE: dividing-fractions" in user


async def test_flat_template_has_no_template_context(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec("Báo cáo", "Mô tả chi tiết về bệnh nhân")

    system = seen[0]["messages"][0]["content"]
    assert "TEMPLATE CONTEXT" not in system


async def test_description_in_user_prompt(tmp_path: Path) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(valid_content()))

    client = make_client(make_settings(tmp_path), handler, tmp_path)
    await client.generate_spec(
        "Báo cáo",
        "Chi tiết nội dung từng slide",
        description="Mô tả ngắn về mục tiêu và số slide",
    )

    user = seen[0]["messages"][-1]["content"]
    assert "DECK DESCRIPTION: Mô tả ngắn về mục tiêu và số slide" in user
    assert "Chi tiết nội dung từng slide" in user
