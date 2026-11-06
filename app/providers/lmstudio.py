# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import UsageInfo

if TYPE_CHECKING:
    from ..config import ProviderSettings


class LMStudioAdapter:
    type = "lmstudio"

    def endpoint(self, provider: "ProviderSettings") -> str:
        base = provider.base_url.rstrip("/")
        if base.endswith("/api/v1"):
            return f"{base}/chat"
        return f"{base}/api/v1/chat"

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
        system_prompt = ""
        parts: list[str] = []
        for message in messages:
            role = str(message.get("role", "user"))
            if role == "system":
                system_prompt = str(message.get("content", ""))
                continue
            parts.append(f"{role.upper()}:\n{message.get('content', '')}")

        generation = provider.generation
        return {
            "model": provider.model,
            "input": "\n\n".join(parts),
            "system_prompt": system_prompt,
            "temperature": generation.temperature,
            "top_p": generation.top_p,
            "max_output_tokens": generation.max_tokens,
            "store": bool(provider.params.get("store", False)),
        }

    def content(self, data: dict[str, Any]) -> str:
        output = data["output"]
        for item in output:
            if item.get("type") == "message":
                return item["content"]
        return output[0]["content"]

    def usage(self, data: dict[str, Any]) -> UsageInfo:
        stats = data.get("stats") or {}
        return UsageInfo(
            prompt_tokens=int(stats.get("input_tokens", 0) or 0),
            completion_tokens=int(
                stats.get("total_output_tokens", 0) or 0
            ),
        )

    def truncated(self, data: dict[str, Any]) -> bool:
        stats = data.get("stats") or {}
        reason = stats.get("stop_reason") or data.get("stop_reason")
        return str(reason).lower() in {
            "length",
            "max_tokens",
            "max_output_tokens",
        }

    def supports_response_format(self) -> bool:
        return False
