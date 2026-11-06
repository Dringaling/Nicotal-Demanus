# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..config import ProviderSettings


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    estimated_cost: float = 0.0
    from_cache: bool = False


class ProviderAdapter(Protocol):
    type: str

    def endpoint(self, provider: "ProviderSettings") -> str: ...

    def headers(
        self, provider: "ProviderSettings", api_key: str
    ) -> dict[str, str]: ...

    def payload(
        self,
        provider: "ProviderSettings",
        messages: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> dict[str, Any]: ...

    def content(self, data: dict[str, Any]) -> str: ...

    def usage(self, data: dict[str, Any]) -> UsageInfo: ...

    def truncated(self, data: dict[str, Any]) -> bool: ...

    def supports_response_format(self) -> bool: ...
