# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from .base import ProviderAdapter, UsageInfo
from .deepinfra import DeepInfraAdapter
from .lmstudio import LMStudioAdapter
from .openai import OpenAIAdapter

_ADAPTERS: dict[str, ProviderAdapter] = {
    adapter.type: adapter
    for adapter in (DeepInfraAdapter(), OpenAIAdapter(), LMStudioAdapter())
}

__all__ = [
    "ProviderAdapter",
    "UsageInfo",
    "get_adapter",
]


def get_adapter(provider_type: str) -> ProviderAdapter:
    try:
        return _ADAPTERS[provider_type]
    except KeyError as exc:
        raise ValueError(
            f"Không có adapter cho provider type '{provider_type}'"
        ) from exc
