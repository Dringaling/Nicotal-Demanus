# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import UsageInfo

if TYPE_CHECKING:
    from ..config import ProviderSettings


class OpenAIAdapter:
    type = "openai"

    def endpoint(self, provider: "ProviderSettings") -> str:
        return f"{provider.base_url.rstrip('/')}/chat/completions"

    def headers(
        self, provider: "ProviderSettings", api_key: str
    ) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def payload(
        self,
        provider: "ProviderSettings",
        messages: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        generation = provider.generation
        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": messages,
            "temperature": generation.temperature,
            "top_p": generation.top_p,
            "max_tokens": generation.max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format
        return payload

    def content(self, data: dict[str, Any]) -> str:
        return data["choices"][0]["message"]["content"]

    def usage(self, data: dict[str, Any]) -> UsageInfo:
        usage = data.get("usage") or {}
        return UsageInfo(
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            cached_tokens=int(usage.get("cached_tokens", 0) or 0),
            cache_write_tokens=int(usage.get("cache_write_tokens", 0) or 0),
            estimated_cost=float(usage.get("estimated_cost", 0.0) or 0.0),
        )

    def truncated(self, data: dict[str, Any]) -> bool:
        try:
            return data["choices"][0].get("finish_reason") == "length"
        except (KeyError, IndexError, TypeError):
            return False

    def supports_response_format(self) -> bool:
        return True
