# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from .config import REPO_ROOT, Settings, load_secret
from .prompts import build_system_prompt
from .providers import UsageInfo, get_adapter
from .schema import DeckSpec, SlideSpec
from .spec_repair import sanitize_deck
from .template_profile import load_profile_from_path
from .templates_catalog import format_template_context, get_template, template_file

logger = logging.getLogger(__name__)

MAX_SLIDES = 60


class LLMError(RuntimeError):
    """Gọi hoặc parse phản hồi LLM thất bại."""


class _HTTPError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _cache_key(
    prompt_version: str,
    model: str,
    name: str,
    description: str,
    desc: str,
    template: str,
    chunk_chars: int,
    context_hash: str,
) -> str:
    payload = "\x00".join(
        [
            prompt_version,
            model,
            name,
            description,
            desc,
            template,
            str(chunk_chars),
            context_hash,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_into_chunks(text: str, limit: int) -> list[str]:
    """Cắt văn bản theo đoạn, không vượt quá `limit` ký tự mỗi chunk."""
    text = text.strip()
    if not text:
        return [""]
    if limit <= 0 or len(text) <= limit:
        return [text]

    units = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current: list[str] = []
    size = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        if len(unit) > limit:
            if current:
                chunks.append("\n\n".join(current))
                current, size = [], 0
            for start in range(0, len(unit), limit):
                chunks.append(unit[start : start + limit])
            continue

        if current and size + len(unit) + 2 > limit:
            chunks.append("\n\n".join(current))
            current, size = [], 0

        current.append(unit)
        size += len(unit) + 2

    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text]


def _sum_usage(usages: list[UsageInfo]) -> UsageInfo:
    return UsageInfo(
        prompt_tokens=sum(item.prompt_tokens for item in usages),
        completion_tokens=sum(item.completion_tokens for item in usages),
        cached_tokens=sum(item.cached_tokens for item in usages),
        cache_write_tokens=sum(item.cache_write_tokens for item in usages),
        estimated_cost=sum(item.estimated_cost for item in usages),
        from_cache=False,
    )


def _merge_specs(specs: list[DeckSpec]) -> DeckSpec:
    if not specs:
        raise LLMError("Không có chunk nào để merge")

    base = specs[0]
    merged: list[SlideSpec] = []
    seen_titles: set[str] = set()

    for spec_index, spec in enumerate(specs):
        is_last = spec_index == len(specs) - 1
        for slide in spec.slides:
            if slide.layout == "title" and merged:
                continue
            if slide.layout == "closing" and not is_last:
                continue

            normalized = slide.title.strip().casefold()
            if normalized and normalized in seen_titles:
                continue
            if normalized:
                seen_titles.add(normalized)
            merged.append(slide)

    if not merged or merged[0].layout != "title":
        merged.insert(
            0,
            SlideSpec(
                layout="title",
                title=base.title,
                subtitle=base.subtitle,
            ),
        )

    closing = SlideSpec(
        layout="closing",
        title="Cảm ơn",
        subtitle=base.author,
    )
    has_closing = merged[-1].layout == "closing"

    if len(merged) > MAX_SLIDES:
        limit = MAX_SLIDES if has_closing else MAX_SLIDES - 1
        merged = merged[:limit]
        if has_closing:
            merged[-1] = closing
        else:
            merged.append(closing)
    elif not has_closing:
        merged.append(closing)

    return base.model_copy(update={"slides": merged})


class LLMClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        root: Path | None = None,
    ) -> None:
        self.settings = settings
        self.provider = settings.provider
        self.adapter = get_adapter(self.provider.type)
        self._transport = transport
        self.root = Path(root) if root is not None else REPO_ROOT
        self._api_key_value: str | None = None

    def _api_key(self) -> str:
        if self._api_key_value is None:
            self._api_key_value = load_secret(self.provider, self.root)
        return self._api_key_value

    def _cache_path(self, key: str) -> Path:
        cache_dir = Path(self.provider.cache.local_cache_dir)
        if not cache_dir.is_absolute():
            cache_dir = self.root / cache_dir
        return cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> DeckSpec | None:
        if not self.provider.cache.local_cache:
            return None
        path = self._cache_path(key)
        if not path.is_file():
            return None
        try:
            return DeckSpec.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, key: str, spec: DeckSpec) -> None:
        if not self.provider.cache.local_cache:
            return
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    def _response_format(self, mode: str) -> dict[str, Any]:
        if mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "deck_spec",
                    "schema": DeckSpec.model_json_schema(),
                },
            }
        return {"type": "json_object"}

    @staticmethod
    def _system_prompt(messages: list[dict[str, Any]]) -> str:
        for message in messages:
            if message.get("role") == "system":
                return str(message.get("content", ""))
        return ""

    @staticmethod
    def _native_input(messages: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for message in messages:
            role = str(message.get("role", "user"))
            if role == "system":
                continue
            parts.append(f"{role.upper()}:\n{message.get('content', '')}")
        return "\n\n".join(parts)

    def _payload(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        return self.adapter.payload(
            self.provider, messages, response_format
        )

    def _endpoint(self) -> str:
        return self.adapter.endpoint(self.provider)

    def _messages(
        self,
        name: str,
        chunk: str,
        template: str,
        index: int,
        total: int,
        template_profile: str | None = None,
        description: str = "",
    ) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": build_system_prompt(template_profile),
                "cache_control": {"type": "ephemeral"},
            },
            {
                "role": "user",
                "content": (
                    f"DECK NAME: {name}\n"
                    f"DECK DESCRIPTION: {description}\n"
                    f"TEMPLATE: {template}\n"
                    f"CHUNK {index} OF {total}\n"
                    f"--- CHUNK START ({index}/{total}) ---\n"
                    f"{chunk}\n"
                    f"--- CHUNK END ({index}/{total}) ---\n"
                    "Return only the JSON deck-spec for this chunk."
                ),
            },
        ]

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = self.adapter.headers(self.provider, self._api_key())
        timeout = httpx.Timeout(self.provider.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout, transport=self._transport
        ) as client:
            response = await client.post(
                self._endpoint(),
                json=payload,
                headers=headers,
            )
        if response.status_code == 200:
            return response.json()
        raise _HTTPError(response.status_code, response.text[:400])

    async def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.provider.max_retries + 1):
            try:
                return await self._post(payload)
            except _HTTPError as exc:
                last_error = exc
                if exc.status_code not in (429, 500, 502, 503, 504):
                    raise LLMError(
                        f"{self.provider.name} trả về HTTP "
                        f"{exc.status_code}: {exc.detail}"
                    ) from exc
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc

            if attempt < self.provider.max_retries:
                await asyncio.sleep(min(2 ** (attempt + 1), 30))

        raise LLMError(
            f"Gọi {self.provider.name} thất bại sau "
            f"{self.provider.max_retries + 1} lần: {last_error}"
        ) from last_error

    def _content(self, data: dict[str, Any]) -> str:
        try:
            return self.adapter.content(data)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Phản hồi {self.provider.name} thiếu nội dung"
            ) from exc

    def _usage(self, data: dict[str, Any]) -> UsageInfo:
        return self.adapter.usage(data)

    @staticmethod
    def _validate_content(content: str) -> DeckSpec:
        data = json.loads(_strip_fence(content))
        return DeckSpec.model_validate(sanitize_deck(data))

    async def _parse(
        self,
        content: str,
        messages: list[dict[str, Any]],
    ) -> DeckSpec:
        try:
            return self._validate_content(content)
        except Exception as first_error:
            error_text = str(first_error)
            cut_off = any(
                marker in error_text
                for marker in (
                    "EOF while parsing",
                    "Unterminated string",
                    "Expecting ',' delimiter",
                    "Expecting property name",
                )
            )
            instruction = (
                "The JSON above was cut off. Return a SHORTER valid JSON "
                "deck-spec with at most 4 slides. No markdown, no commentary."
                if cut_off
                else (
                    f"The JSON above is invalid: {first_error}. "
                    "Return only a valid JSON deck-spec matching the schema, "
                    "without markdown."
                )
            )
            repair_messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": instruction},
            ]
            try:
                data = await self._post_with_retry(
                    self._payload(
                        repair_messages, self._response_format("json_object")
                    )
                )
            except LLMError as exc:
                if (
                    not self.adapter.supports_response_format()
                    or "response_format" in str(exc).lower()
                ):
                    data = await self._post_with_retry(
                        self._payload(repair_messages, {})
                    )
                else:
                    raise
            if self.adapter.truncated(data):
                raise LLMError(
                    "Phản hồi bị cắt vì hết token; tăng max_tokens "
                    "hoặc giảm chunk_chars"
                )
            repaired = self._content(data)
            try:
                return self._validate_content(repaired)
            except Exception as second_error:
                raise LLMError(
                    f"Không parse được JSON deck-spec: {second_error}"
                ) from second_error

    async def _request_spec(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[DeckSpec, UsageInfo]:
        mode = self.provider.generation.response_format

        if not self.adapter.supports_response_format():
            data = await self._post_with_retry(self._payload(messages, {}))
        else:
            try:
                data = await self._post_with_retry(
                    self._payload(messages, self._response_format(mode))
                )
            except LLMError as exc:
                if "response_format" not in str(exc).lower():
                    raise
                try:
                    data = await self._post_with_retry(
                        self._payload(
                            messages, self._response_format("json_object")
                        )
                    )
                except LLMError as second:
                    if "response_format" not in str(second).lower():
                        raise
                    data = await self._post_with_retry(
                        self._payload(messages, {})
                    )

        if self.adapter.truncated(data):
            raise LLMError(
                "Phản hồi bị cắt vì hết token; tăng max_tokens "
                "hoặc giảm chunk_chars"
            )

        content = self._content(data)
        spec = await self._parse(content, messages)
        return spec, self._usage(data)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> tuple[str, UsageInfo]:
        data = await self._post_with_retry(
            self._payload(messages, response_format or {})
        )
        if self.adapter.truncated(data):
            raise LLMError(
                "Phản hồi bị cắt vì hết token; tăng max_tokens "
                "hoặc giảm chunk_chars"
            )
        return self._content(data), self._usage(data)

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
        description: str = "",
    ) -> tuple[DeckSpec, UsageInfo]:
        chunk_chars = self.provider.generation.chunk_chars
        meta = get_template(template) if template != "flat" else None
        profile = None
        if meta is not None:
            path = template_file(meta)
            if path is not None:
                profile = load_profile_from_path(
                    str(path), tuple(meta.layout_map.items())
                )
        context = format_template_context(meta, profile) if meta else None
        context_hash = (
            hashlib.sha256(context.encode("utf-8")).hexdigest()[:16]
            if context
            else ""
        )
        key = _cache_key(
            self.provider.cache.prompt_version,
            self.provider.model,
            name,
            description,
            desc,
            template,
            chunk_chars,
            context_hash,
        )
        cached = self._read_cache(key)
        if cached is not None:
            return cached, UsageInfo(from_cache=True)

        chunks = split_into_chunks(desc, chunk_chars)
        total = len(chunks)
        specs: list[DeckSpec] = []
        usages: list[UsageInfo] = []

        for index, chunk in enumerate(chunks, start=1):
            messages = self._messages(
                name, chunk, template, index, total, context, description
            )
            try:
                spec, usage = await self._request_spec(messages)
            except LLMError as exc:
                raise LLMError(f"chunk {index}/{total}: {exc}") from exc
            specs.append(spec)
            usages.append(usage)

        merged = _merge_specs(specs)
        usage = _sum_usage(usages)
        self._write_cache(key, merged)

        logger.info(
            "%s ok type=%s model=%s chunks=%s slides=%s "
            "prompt_tokens=%s cached_tokens=%s cost=%s",
            self.provider.name,
            self.provider.type,
            self.provider.model,
            total,
            len(merged.slides),
            usage.prompt_tokens,
            usage.cached_tokens,
            usage.estimated_cost,
        )
        return merged, usage
