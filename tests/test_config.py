# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.config import (
    ConfigError,
    detect_lan_ip,
    lan_url,
    load_secret,
    load_settings,
    paths,
    secret_status,
)

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
    assert settings.provider.generation.chunk_chars == 8000
    assert settings.provider.cache.prompt_cache_key == "demanus-deck-v4"
    assert settings.provider.cache.local_cache is True


def test_load_settings_reads_server() -> None:
    settings = load_settings(CONFIG)
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8765
    assert settings.server.lan_ip == "192.168.1.12"


def test_lan_url_uses_configured_ip() -> None:
    settings = load_settings(CONFIG)
    assert lan_url(settings) == "http://192.168.1.12:8765"


def test_detect_lan_ip_returns_string() -> None:
    detected = detect_lan_ip()
    assert isinstance(detected, str)
    assert detected


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
    provider = replace(settings.provider, api_key_file=str(secret_file))
    secret_file.write_text(
        f'# comment\n{provider.api_key_env}="abc123" # note\n',
        encoding="utf-8",
    )

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


def test_loads_multiple_providers() -> None:
    settings = load_settings(CONFIG)
    assert set(settings.providers) >= {
        "deepinfra/deepseek-flash-flex",
        "deepinfra/deepseek-flash-standard",
        "lmstudio-openai/gemma-4-e4b-it",
        "lmstudio-native/gemma-4-e4b-it",
    }
    assert settings.providers["lmstudio-openai/gemma-4-e4b-it"].type == "openai"
    assert settings.providers["lmstudio-native/gemma-4-e4b-it"].type == "lmstudio"
    assert settings.providers["lmstudio-native/gemma-4-e4b-it"].requires_key is False


def test_default_provider_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMANUS_PROVIDER", "lmstudio-native")
    settings = load_settings(CONFIG)
    assert settings.provider_name == "lmstudio-native"
    assert settings.provider.type == "lmstudio"


def test_unknown_default_provider_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMANUS_PROVIDER", "khong-ton-tai")
    with pytest.raises(ConfigError, match="DEMANUS_PROVIDER"):
        load_settings(CONFIG)


def test_local_provider_needs_no_key() -> None:
    settings = load_settings(CONFIG)
    provider = settings.providers["lmstudio-native/gemma-4-e4b-it"]
    assert load_secret(provider) == ""
    assert secret_status(provider) == "not-required"


def test_each_model_has_its_own_api_key_env() -> None:
    settings = load_settings(CONFIG)
    flex = settings.providers["deepinfra/deepseek-flash-flex"]
    standard = settings.providers["deepinfra/deepseek-flash-standard"]

    assert flex.api_key_env == "DEMANUS_DEEPINFRA_FLEX_8F3A"
    assert standard.api_key_env == "DEMANUS_DEEPINFRA_STANDARD_9C1B"
    assert flex.api_key_env != standard.api_key_env
    assert flex.service_tier == "flex"
    assert standard.service_tier == "default"


def test_model_must_declare_api_key_env(tmp_path: Path) -> None:
    config = tmp_path / "providers.toml"
    config.write_text(
        'default_provider = "deepinfra"\n'
        'default_model = "m1"\n'
        "\n"
        "[providers.deepinfra]\n"
        'type = "deepinfra"\n'
        'base_url = "https://api.deepinfra.com/v1/openai"\n'
        "\n"
        "[providers.deepinfra.m1]\n"
        'model = "some-model"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="api_key_env"):
        load_settings(config)


def test_duplicate_api_key_env_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "providers.toml"
    config.write_text(
        'default_provider = "deepinfra"\n'
        'default_model = "m1"\n'
        "\n"
        "[providers.deepinfra]\n"
        'type = "deepinfra"\n'
        'base_url = "https://api.deepinfra.com/v1/openai"\n'
        "\n"
        "[providers.deepinfra.m1]\n"
        'model = "some-model"\n'
        'api_key_env = "SAME_KEY"\n'
        "\n"
        "[providers.deepinfra.m2]\n"
        'model = "other-model"\n'
        'api_key_env = "SAME_KEY"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="bị trùng"):
        load_settings(config)
