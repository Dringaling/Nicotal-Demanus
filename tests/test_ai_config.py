# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app import ai_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "providers.toml"


@pytest.fixture()
def paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    base = tmp_path / "config" / "providers.toml"
    base.parent.mkdir(parents=True)
    shutil.copy(CONFIG, base)
    local = base.parent / "providers.local.toml"
    return base, local, tmp_path


def payload(paths) -> dict:
    base, local, root = paths
    return ai_config.payload(base, local, root=root)


def add_provider(paths, name: str = "local-test") -> None:
    base, local, _ = paths
    ai_config.save_provider(
        name=name,
        type="openai",
        base_url="http://127.0.0.1:1234/v1",
        timeout_seconds=60,
        max_retries=1,
        create=True,
        base_path=base,
        local_path=local,
    )


def add_model(paths, provider: str = "local-test", model_id: str = "demo") -> None:
    base, local, root = paths
    ai_config.save_model(
        provider=provider,
        model_id=model_id,
        model="demo-model",
        generation={"temperature": 0.2},
        api_key="sk-test",
        create=True,
        base_path=base,
        local_path=local,
        root=root,
    )


def test_payload_shape(paths) -> None:
    data = payload(paths)

    assert data["default_provider"] == "deepinfra"
    assert data["default_model"] == "deepseek-flash-flex"
    assert data["default_key"] == "deepinfra/deepseek-flash-flex"
    assert data["types"]
    assert data["param_fields"]["deepinfra"]
    assert data["generation_fields"]
    assert data["response_formats"]


def test_payload_never_contains_key(paths) -> None:
    add_provider(paths)
    add_model(paths)
    data = payload(paths)

    text = repr(data)
    assert "sk-test" not in text
    model = [
        item
        for provider in data["providers"]
        for item in provider["models"]
        if item["id"] == "demo"
    ][0]
    assert model["key"] == "set"


def test_source_marks_local_entries(paths) -> None:
    add_provider(paths)
    data = payload(paths)
    provider = [item for item in data["providers"] if item["name"] == "local-test"][0]

    assert provider["source"] == "local"
    shipped = [item for item in data["providers"] if item["name"] == "deepinfra"][0]
    assert shipped["source"] == "shipped"


def test_create_provider_writes_local(paths) -> None:
    base, local, _ = paths
    add_provider(paths)

    assert local.is_file()
    assert "local-test" in local.read_text(encoding="utf-8")
    assert local.stat().st_mode & 0o777 == 0o600


def test_duplicate_provider(paths) -> None:
    add_provider(paths)

    with pytest.raises(ai_config.AiConfigError) as exc:
        add_provider(paths)
    assert exc.value.status == 409


def test_type_cannot_change(paths) -> None:
    add_provider(paths)
    base, local, _ = paths

    with pytest.raises(ai_config.AiConfigError) as exc:
        ai_config.save_provider(
            name="local-test",
            type="lmstudio",
            base_url="http://127.0.0.1:1234",
            create=False,
            base_path=base,
            local_path=local,
        )
    assert "type" in str(exc.value)


def test_base_url_must_be_http(paths) -> None:
    base, local, _ = paths

    with pytest.raises(ai_config.AiConfigError):
        ai_config.save_provider(
            name="bad",
            type="openai",
            base_url="ftp://example.com",
            create=True,
            base_path=base,
            local_path=local,
        )


def test_model_identity_hashed(paths) -> None:
    add_provider(paths)
    add_model(paths)
    base, local, root = paths

    text = local.read_text(encoding="utf-8")
    assert "DEMANUS_LOCAL_TEST_DEMO_" in text
    secret = list((root / "secret").glob("*.env"))
    assert len(secret) == 1
    assert secret[0].stat().st_mode & 0o777 == 0o600
    assert "sk-test" in secret[0].read_text(encoding="utf-8")


def test_duplicate_model(paths) -> None:
    add_provider(paths)
    add_model(paths)

    with pytest.raises(ai_config.AiConfigError) as exc:
        add_model(paths)
    assert exc.value.status == 409


def test_model_key_status(paths) -> None:
    add_provider(paths)
    add_model(paths)
    data = payload(paths)
    model = [
        item
        for provider in data["providers"]
        for item in provider["models"]
        if item["id"] == "demo"
    ][0]

    assert model["key"] == "set"


def test_model_without_key_is_missing(paths) -> None:
    add_provider(paths)
    base, local, root = paths
    ai_config.save_model(
        provider="local-test",
        model_id="no-key",
        model="demo-model",
        create=True,
        base_path=base,
        local_path=local,
        root=root,
    )
    data = payload(paths)
    model = [
        item
        for provider in data["providers"]
        for item in provider["models"]
        if item["id"] == "no-key"
    ][0]

    assert model["key"] == "missing"


def test_params_validated_by_type(paths) -> None:
    base, local, _ = paths

    with pytest.raises(ai_config.AiConfigError) as exc:
        ai_config.save_model(
            provider="deepinfra",
            model_id="bad-params",
            model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
            params={"store": True},
            create=True,
            base_path=base,
            local_path=local,
        )
    assert "service_tier" in str(exc.value)


def test_generation_rejects_unknown_field(paths) -> None:
    base, local, _ = paths

    with pytest.raises(ai_config.AiConfigError):
        ai_config.save_model(
            provider="deepinfra",
            model_id="bad-gen",
            model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
            generation={"nope": 1},
            create=True,
            base_path=base,
            local_path=local,
        )


def test_generation_rejects_bad_response_format(paths) -> None:
    base, local, _ = paths

    with pytest.raises(ai_config.AiConfigError):
        ai_config.save_model(
            provider="deepinfra",
            model_id="bad-format",
            model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
            generation={"response_format": "xml"},
            create=True,
            base_path=base,
            local_path=local,
        )


def test_set_default(paths) -> None:
    add_provider(paths)
    add_model(paths)
    base, local, _ = paths
    ai_config.set_default(
        provider="local-test", model="demo", base_path=base, local_path=local
    )
    data = payload(paths)

    assert data["default_key"] == "local-test/demo"
    assert data["default_provider"] == "local-test"


def test_set_default_unknown_model(paths) -> None:
    base, local, _ = paths

    with pytest.raises(ai_config.AiConfigError) as exc:
        ai_config.set_default(
            provider="deepinfra", model="nope", base_path=base, local_path=local
        )
    assert exc.value.status == 404


def test_delete_default_provider_blocked(paths) -> None:
    add_provider(paths)
    add_model(paths)
    base, local, root = paths
    ai_config.set_default(
        provider="local-test", model="demo", base_path=base, local_path=local
    )

    with pytest.raises(ai_config.AiConfigError):
        ai_config.delete_provider(
            name="local-test", base_path=base, local_path=local, root=root
        )


def test_delete_default_model_blocked(paths) -> None:
    add_provider(paths)
    add_model(paths)
    base, local, root = paths
    ai_config.set_default(
        provider="local-test", model="demo", base_path=base, local_path=local
    )

    with pytest.raises(ai_config.AiConfigError):
        ai_config.delete_model(
            provider="local-test",
            model_id="demo",
            base_path=base,
            local_path=local,
            root=root,
        )


def test_delete_local_provider(paths) -> None:
    add_provider(paths)
    add_model(paths)
    base, local, root = paths
    ai_config.delete_provider(
        name="local-test", base_path=base, local_path=local, root=root
    )
    data = payload(paths)

    assert "local-test" not in [item["name"] for item in data["providers"]]
    assert not list((root / "secret").glob("*.env"))


def test_delete_local_model(paths) -> None:
    add_provider(paths)
    add_model(paths)
    base, local, root = paths
    ai_config.delete_model(
        provider="local-test",
        model_id="demo",
        base_path=base,
        local_path=local,
        root=root,
    )
    data = payload(paths)
    provider = [item for item in data["providers"] if item["name"] == "local-test"][0]

    assert provider["models"] == []
    assert not list((root / "secret").glob("*.env"))


def test_delete_shipped_provider_blocked(paths) -> None:
    base, local, root = paths

    with pytest.raises(ai_config.AiConfigError):
        ai_config.delete_provider(
            name="deepinfra", base_path=base, local_path=local, root=root
        )


def test_invalid_candidate_does_not_write(paths) -> None:
    base, local, _ = paths
    add_provider(paths)
    before = local.read_text(encoding="utf-8")

    with pytest.raises(ai_config.AiConfigError):
        ai_config.save_model(
            provider="local-test",
            model_id="broken",
            model="",
            create=True,
            base_path=base,
            local_path=local,
        )

    assert local.read_text(encoding="utf-8") == before


def test_provider_without_models_is_ignored(paths) -> None:
    add_provider(paths)
    base, local, _ = paths
    from app.config import load_settings

    settings = load_settings(base, local)

    assert "local-test" not in settings.providers
    assert settings.provider_name == "deepinfra"


def test_is_local_host() -> None:
    assert ai_config.is_local_host("127.0.0.1")
    assert ai_config.is_local_host("::1")
    assert not ai_config.is_local_host("192.168.1.50")
