from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.config import ConfigError, load_secret, load_settings, paths

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "providers.toml"


def test_load_settings_reads_provider() -> None:
    settings = load_settings(CONFIG)
    assert settings.provider_name == "deepinfra"
    assert settings.provider.model == "deepseek-ai/DeepSeek-V4.1-Flash-1017"
    assert settings.provider.service_tier == "flex"
    assert settings.provider.base_url == "https://api.deepinfra.com/v1/openai"


def test_load_settings_reads_generation_and_cache() -> None:
    settings = load_settings(CONFIG)
    assert settings.provider.generation.max_tokens == 8000
    assert settings.provider.generation.response_format == "json_schema"
    assert settings.provider.cache.prompt_cache_key == "demanus-deck-v1"
    assert settings.provider.cache.local_cache is True


def test_load_settings_reads_server() -> None:
    settings = load_settings(CONFIG)
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8000


def test_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Không tìm thấy file cấu hình"):
        load_settings(tmp_path / "missing.toml")


def test_secret_from_env_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(CONFIG)
    secret_file = tmp_path / "key.env"
    secret_file.write_text("DEEPINFRA_FLEX_C79C=from-file\n", encoding="utf-8")
    provider = replace(settings.provider, api_key_file=str(secret_file))

    monkeypatch.setenv(provider.api_key_env, "from-env")
    assert load_secret(provider, root=tmp_path) == "from-env"


def test_secret_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(CONFIG)
    monkeypatch.delenv(settings.provider.api_key_env, raising=False)
    secret_file = tmp_path / "key.env"
    secret_file.write_text(
        '# comment\nDEEPINFRA_FLEX_C79C="abc123" # note\n', encoding="utf-8"
    )
    provider = replace(settings.provider, api_key_file=str(secret_file))

    assert load_secret(provider, root=tmp_path) == "abc123"


def test_missing_secret_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(CONFIG)
    monkeypatch.delenv(settings.provider.api_key_env, raising=False)
    provider = replace(settings.provider, api_key_file=str(tmp_path / "nope.env"))

    with pytest.raises(ConfigError, match="Thiếu API key"):
        load_secret(provider, root=tmp_path)


def test_paths_live_under_root(tmp_path: Path) -> None:
    resolved = paths(tmp_path)
    assert resolved.input == tmp_path / "input"
    assert resolved.output == tmp_path / "output"
    assert resolved.templates == tmp_path / "templates"
    assert resolved.secret == tmp_path / "secret"
    assert resolved.cache == tmp_path / "input" / ".cache"
