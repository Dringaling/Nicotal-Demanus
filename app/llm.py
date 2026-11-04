from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import REPO_ROOT, Settings, load_secret
from .prompts import build_system_prompt
from .schema import DeckSpec

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Gọi hoặc parse phản hồi LLM thất bại."""


class _HTTPError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    estimated_cost: float = 0.0
    from_cache: bool = False


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
    desc: str,
    template: str,
) -> str:
    payload = "\x00".join([prompt_version, model, name, desc, template])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

    def _payload(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        generation = self.provider.generation
        payload: dict[str, Any] = {
            "model": self.provider.model,
            "messages": messages,
            "service_tier": self.provider.service_tier,
            "temperature": generation.temperature,
            "top_p": generation.top_p,
            "max_tokens": generation.max_tokens,
            "stream": False,
            "prompt_cache_key": self.provider.cache.prompt_cache_key,
            "prompt_cache_options": {"ttl": self.provider.cache.cache_ttl},
            "response_format": response_format,
        }
        if self.provider.fallback_models:
            payload["models"] = list(self.provider.fallback_models)
        if self.provider.fail_fast:
            payload["fail_fast"] = True
        return payload

    def _messages(
        self,
        name: str,
        desc: str,
        template: str,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": build_system_prompt()},
            {
                "role": "user",
                "content": (
                    f"Tên báo cáo: {name}\n"
                    f"Mô tả: {desc}\n"
                    f"Template: {template}\n\n"
                    "Trả về JSON deck-spec."
                ),
            },
        ]

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.provider.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout, transport=self._transport
        ) as client:
            response = await client.post(
                f"{self.provider.base_url}/chat/completions",
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
                        f"DeepInfra trả về HTTP {exc.status_code}: {exc.detail}"
                    ) from exc
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc

            if attempt < self.provider.max_retries:
                await asyncio.sleep(min(2 ** (attempt + 1), 30))

        raise LLMError(
            f"Gọi DeepInfra thất bại sau {self.provider.max_retries + 1} lần: "
            f"{last_error}"
        ) from last_error

    def _content(self, data: dict[str, Any]) -> str:
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                "Phản hồi DeepInfra thiếu choices[0].message.content"
            ) from exc

    def _usage(self, data: dict[str, Any]) -> UsageInfo:
        usage = data.get("usage") or {}
        return UsageInfo(
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            cached_tokens=int(usage.get("cached_tokens", 0) or 0),
            cache_write_tokens=int(usage.get("cache_write_tokens", 0) or 0),
            estimated_cost=float(usage.get("estimated_cost", 0.0) or 0.0),
        )

    async def _parse(
        self,
        content: str,
        messages: list[dict[str, str]],
    ) -> DeckSpec:
        try:
            return DeckSpec.model_validate_json(_strip_fence(content))
        except Exception as first_error:
            repair_messages = messages + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        f"JSON trên không hợp lệ: {first_error}. "
                        "Chỉ trả về JSON thuần đúng schema, không markdown."
                    ),
                },
            ]
            data = await self._post_with_retry(
                self._payload(repair_messages, self._response_format("json_object"))
            )
            repaired = self._content(data)
            try:
                return DeckSpec.model_validate_json(_strip_fence(repaired))
            except Exception as second_error:
                raise LLMError(
                    f"Không parse được JSON deck-spec: {second_error}"
                ) from second_error

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
    ) -> tuple[DeckSpec, UsageInfo]:
        key = _cache_key(
            self.provider.cache.prompt_version,
            self.provider.model,
            name,
            desc,
            template,
        )
        cached = self._read_cache(key)
        if cached is not None:
            return cached, UsageInfo(from_cache=True)

        messages = self._messages(name, desc, template)
        mode = self.provider.generation.response_format
        try:
            data = await self._post_with_retry(
                self._payload(messages, self._response_format(mode))
            )
        except LLMError as exc:
            if mode == "json_schema" and "response_format" in str(exc).lower():
                data = await self._post_with_retry(
                    self._payload(messages, self._response_format("json_object"))
                )
            else:
                raise

        content = self._content(data)
        spec = await self._parse(content, messages)
        usage = self._usage(data)
        self._write_cache(key, spec)

        logger.info(
            "DeepInfra ok model=%s tier=%s prompt_tokens=%s cached_tokens=%s cost=%s",
            data.get("model", self.provider.model),
            self.provider.service_tier,
            usage.prompt_tokens,
            usage.cached_tokens,
            usage.estimated_cost,
        )
        return spec, usage
