# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import secrets
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import config
from .config import ConfigError

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")

TYPE_PARAM_FIELDS: dict[str, tuple[str, ...]] = {
    "deepinfra": ("service_tier", "fail_fast", "fallback_models"),
    "lmstudio": ("store",),
    "openai": (),
}

GENERATION_FIELDS = (
    "temperature",
    "top_p",
    "max_tokens",
    "chunk_chars",
    "response_format",
)

RESPONSE_FORMATS = ("json_schema", "json_object", "text")

_INT_GENERATION = {"max_tokens", "chunk_chars"}
_FLOAT_GENERATION = {"temperature", "top_p"}

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


class AiConfigError(RuntimeError):
    """Thao tác cấu hình AI không hợp lệ."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def is_local_host(host: str | None) -> bool:
    return (host or "").strip() in _LOCAL_HOSTS


def _paths(
    base_path: Path | None, local_path: Path | None
) -> tuple[Path, Path]:
    base = Path(base_path) if base_path is not None else config.CONFIG_PATH
    local = (
        Path(local_path) if local_path is not None else config.LOCAL_CONFIG_PATH
    )
    return base, local


def _raw(base_path: Path | None, local_path: Path | None) -> dict:
    base, local = _paths(base_path, local_path)
    return config.merged_raw(base, local)


def _local(base_path: Path | None, local_path: Path | None) -> dict:
    _, local = _paths(base_path, local_path)
    return config.read_local_config(local)


def _settings(base_path: Path | None, local_path: Path | None):
    base, local = _paths(base_path, local_path)
    return config.load_settings(base, local)


def _model_tables(provider_table: dict) -> dict[str, dict]:
    return {
        str(key): value
        for key, value in provider_table.items()
        if key not in config.PROVIDER_RESERVED and isinstance(value, dict)
    }


def _base_raw(base_path: Path | None) -> dict:
    base, _ = _paths(base_path, None)
    with base.open("rb") as handle:
        return tomllib.load(handle)


def _validate_candidate(
    candidate: dict, base_path: Path | None
) -> None:
    """Parse thử cấu hình sau khi merge; sai thì không ghi gì."""
    base, _ = _paths(base_path, None)
    merged = config.deep_merge(_base_raw(base_path), candidate)
    try:
        config._load_models(merged, base)
    except ConfigError as exc:
        raise AiConfigError(str(exc), 400) from exc


def payload(
    base_path: Path | None = None,
    local_path: Path | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    raw = _raw(base_path, local_path)
    local = _local(base_path, local_path)
    settings = _settings(base_path, local_path)
    local_providers = local.get("providers") or {}

    providers: list[dict] = []
    for name, table in (raw.get("providers") or {}).items():
        if not isinstance(table, dict):
            continue
        provider_type = str(
            table.get("type")
            or config.infer_provider_type(str(table.get("base_url") or ""))
        )
        models: list[dict] = []
        local_models = (local_providers.get(name) or {})
        for model_id, model_table in _model_tables(table).items():
            key = f"{name}/{model_id}"
            resolved = settings.providers.get(key)
            status = (
                config.secret_status(resolved, root) if resolved else "missing"
            )
            merged_params = dict(resolved.params) if resolved else {}
            allowed = TYPE_PARAM_FIELDS.get(provider_type, ())
            params = {
                field: merged_params[field]
                for field in allowed
                if field in merged_params
            }
            generation = (
                {
                    "temperature": resolved.generation.temperature,
                    "top_p": resolved.generation.top_p,
                    "max_tokens": resolved.generation.max_tokens,
                    "chunk_chars": resolved.generation.chunk_chars,
                    "response_format": resolved.generation.response_format,
                }
                if resolved
                else {}
            )
            models.append(
                {
                    "id": model_id,
                    "model": str(model_table.get("model", "")),
                    "key": status,
                    "source": "local" if model_id in local_models else "shipped",
                    "is_default": (
                        name == settings.provider_name
                        and model_id == settings.model_name
                    ),
                    "params": params,
                    "generation": generation,
                }
            )
        providers.append(
            {
                "name": str(name),
                "type": provider_type,
                "base_url": str(table.get("base_url", "")),
                "timeout_seconds": float(table.get("timeout_seconds", 180)),
                "max_retries": int(table.get("max_retries", 3)),
                "source": "local" if name in local_providers else "shipped",
                "models": models,
            }
        )

    return {
        "default_provider": settings.provider_name,
        "default_model": settings.model_name,
        "default_key": f"{settings.provider_name}/{settings.model_name}",
        "default_key_status": config.secret_status(settings.provider, root),
        "types": sorted(config.PROVIDER_TYPES),
        "param_fields": {
            key: list(value) for key, value in TYPE_PARAM_FIELDS.items()
        },
        "generation_fields": list(GENERATION_FIELDS),
        "response_formats": list(RESPONSE_FORMATS),
        "providers": providers,
    }


def _clean_name(value: object, label: str) -> str:
    name = str(value or "").strip().lower()
    if not NAME_PATTERN.match(name):
        raise AiConfigError(
            f"{label} không hợp lệ: chỉ a-z, 0-9, dấu gạch, tối đa 32 ký tự"
        )
    return name


def _clean_base_url(value: object) -> str:
    url = str(value or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AiConfigError("base_url phải là http(s)://host[/path]")
    return url


def _provider_entry(raw: dict, name: str) -> dict | None:
    table = (raw.get("providers") or {}).get(name)
    return table if isinstance(table, dict) else None


def save_provider(
    *,
    name: object,
    type: object,
    base_url: object,
    timeout_seconds: object = 180,
    max_retries: object = 3,
    create: bool = False,
    base_path: Path | None = None,
    local_path: Path | None = None,
) -> str:
    provider_name = _clean_name(name, "Tên provider")
    provider_type = str(type or "").strip().lower()
    if provider_type not in config.PROVIDER_TYPES:
        raise AiConfigError(
            f"type '{provider_type}' không hợp lệ; chọn một trong "
            f"{sorted(config.PROVIDER_TYPES)}"
        )
    url = _clean_base_url(base_url)
    try:
        timeout = float(timeout_seconds)
        retries = int(max_retries)
    except (TypeError, ValueError) as exc:
        raise AiConfigError("timeout và số lần thử phải là số") from exc
    if timeout <= 0:
        raise AiConfigError("timeout phải lớn hơn 0")
    if retries < 0:
        raise AiConfigError("số lần thử không được âm")

    raw = _raw(base_path, local_path)
    local = _local(base_path, local_path)
    existing = _provider_entry(raw, provider_name)
    if create and existing is not None:
        raise AiConfigError(f"đã có provider '{provider_name}'", 409)
    if not create and existing is None:
        raise AiConfigError(f"không có provider '{provider_name}'", 404)
    if existing is not None:
        current_type = str(existing.get("type") or "")
        if current_type and current_type != provider_type:
            raise AiConfigError(
                f"provider '{provider_name}' không đổi được type "
                f"({current_type} → {provider_type}); tạo provider mới thay thế"
            )

    providers = local.setdefault("providers", {})
    table = providers.get(provider_name)
    if not isinstance(table, dict):
        table = {}
        providers[provider_name] = table
    table.update(
        {
            "type": provider_type,
            "base_url": url,
            "timeout_seconds": timeout,
            "max_retries": retries,
        }
    )

    _validate_candidate(local, base_path)
    _, local_file = _paths(base_path, local_path)
    config.write_local_config(local, local_file)
    return "created" if create else "updated"


def delete_provider(
    *,
    name: object,
    base_path: Path | None = None,
    local_path: Path | None = None,
    root: Path | None = None,
) -> None:
    provider_name = str(name or "").strip()
    local = _local(base_path, local_path)
    providers = local.get("providers") or {}
    if provider_name not in providers:
        raise AiConfigError(
            f"'{provider_name}' không phải provider tạo trong app", 400
        )
    settings = _settings(base_path, local_path)
    if settings.provider_name == provider_name:
        raise AiConfigError("đang là provider mặc định; chọn provider khác trước")
    removed = providers.pop(provider_name)
    if not providers:
        local.pop("providers", None)

    _validate_candidate(local, base_path)
    _, local_file = _paths(base_path, local_path)
    config.write_local_config(local, local_file)
    _drop_orphan_secrets(removed, base_path, local_path, root)


def _drop_orphan_secrets(
    removed: dict,
    base_path: Path | None,
    local_path: Path | None,
    root: Path | None = None,
) -> None:
    """Xoá file secret không còn model nào dùng."""
    if not isinstance(removed, dict):
        return
    candidates = {
        str(table.get("secret_file") or "")
        for table in _model_tables(removed).values()
        if isinstance(table, dict)
    }
    candidates.discard("")
    if not candidates:
        return
    settings = _settings(base_path, local_path)
    used = {provider.api_key_file for provider in settings.providers.values()}
    base = Path(root) if root is not None else config.REPO_ROOT
    for secret_file in candidates - used:
        path = Path(secret_file)
        if not path.is_absolute():
            path = base / path
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue


def new_identity(
    provider: str,
    model_id: str,
    base_path: Path | None = None,
    local_path: Path | None = None,
) -> tuple[str, str]:
    """`<TÊN>_<4 hex>` và `secret/<tên>_<4 hex>.env`, không trùng model khác."""
    base = re.sub(r"[^a-z0-9]+", "_", f"{provider}_{model_id}".lower()).strip("_")
    if not base or not base[0].isalpha():
        base = f"p_{base}" if base else "provider"
    base = base[:48]
    used = {
        item.api_key_env
        for item in _settings(base_path, local_path).providers.values()
        if item.api_key_env
    }
    for _ in range(50):
        digest = secrets.token_hex(2)
        env = f"DEMANUS_{base.upper()}_{digest.upper()}"
        if env not in used:
            return env, f"secret/demanus_{base}_{digest}.env"
    raise AiConfigError("không sinh được định danh key mới", 500)


def _clean_params(provider_type: str, params: object) -> dict:
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise AiConfigError("params phải là bảng khoá/giá trị")
    allowed = TYPE_PARAM_FIELDS.get(provider_type, ())
    unknown = sorted(set(params) - set(allowed))
    if unknown:
        raise AiConfigError(
            f"params không hợp lệ cho type '{provider_type}': "
            f"{', '.join(unknown)}; chỉ nhận {', '.join(allowed) or '(không có)'}"
        )
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        if key == "fail_fast" or key == "store":
            cleaned[key] = bool(value)
        elif key == "fallback_models":
            if isinstance(value, str):
                items = [item.strip() for item in value.split(",")]
            elif isinstance(value, list):
                items = [str(item).strip() for item in value]
            else:
                raise AiConfigError("fallback_models phải là mảng hoặc chuỗi")
            cleaned[key] = [item for item in items if item]
        else:
            cleaned[key] = str(value)
    return cleaned


def _clean_generation(generation: object) -> dict:
    if generation is None:
        return {}
    if not isinstance(generation, dict):
        raise AiConfigError("generation phải là bảng khoá/giá trị")
    unknown = sorted(set(generation) - set(GENERATION_FIELDS))
    if unknown:
        raise AiConfigError(
            f"generation không hợp lệ: {', '.join(unknown)}; chỉ nhận "
            f"{', '.join(GENERATION_FIELDS)}"
        )
    cleaned: dict[str, Any] = {}
    for key, value in generation.items():
        if value is None or value == "":
            continue
        try:
            if key in _INT_GENERATION:
                cleaned[key] = int(value)
            elif key in _FLOAT_GENERATION:
                cleaned[key] = float(value)
            else:
                cleaned[key] = str(value)
        except (TypeError, ValueError) as exc:
            raise AiConfigError(f"generation.{key} phải là số") from exc
        if key in _INT_GENERATION and cleaned[key] <= 0:
            raise AiConfigError(f"generation.{key} phải lớn hơn 0")
        if key in _FLOAT_GENERATION and not 0 <= cleaned[key] <= 2:
            raise AiConfigError(f"generation.{key} phải trong khoảng 0..2")
    if "response_format" in cleaned and cleaned["response_format"] not in (
        RESPONSE_FORMATS
    ):
        raise AiConfigError(
            "response_format phải là một trong "
            f"{', '.join(RESPONSE_FORMATS)}"
        )
    return cleaned


def save_model(
    *,
    provider: object,
    model_id: object,
    model: object,
    params: object = None,
    generation: object = None,
    api_key: str | None = None,
    create: bool = False,
    base_path: Path | None = None,
    local_path: Path | None = None,
    root: Path | None = None,
) -> str:
    provider_name = str(provider or "").strip()
    raw = _raw(base_path, local_path)
    provider_table = _provider_entry(raw, provider_name)
    if provider_table is None:
        raise AiConfigError(f"không có provider '{provider_name}'", 404)
    provider_type = str(
        provider_table.get("type")
        or config.infer_provider_type(
            str(provider_table.get("base_url") or "")
        )
    )

    name = _clean_name(model_id, "ID model")
    model_name = str(model or "").strip()
    if not model_name:
        raise AiConfigError("model không được để trống")

    models = _model_tables(provider_table)
    existing = models.get(name)
    if create and existing is not None:
        raise AiConfigError(f"đã có model '{name}'", 409)
    if not create and existing is None:
        raise AiConfigError(f"không có model '{name}'", 404)

    cleaned_params = _clean_params(provider_type, params)
    cleaned_generation = _clean_generation(generation)

    if existing is not None:
        env = str(existing.get("api_key_env") or "")
        secret_file = str(existing.get("secret_file") or "")
    else:
        env, secret_file = new_identity(
            provider_name, name, base_path, local_path
        )

    table: dict[str, Any] = {
        "model": model_name,
        "api_key_env": env,
        "secret_file": secret_file,
    }
    if cleaned_params:
        table["params"] = cleaned_params
    if cleaned_generation:
        table["generation"] = cleaned_generation

    local = _local(base_path, local_path)
    providers = local.setdefault("providers", {})
    provider_local = providers.get(provider_name)
    if not isinstance(provider_local, dict):
        provider_local = {}
        providers[provider_name] = provider_local
    provider_local[name] = table

    _validate_candidate(local, base_path)
    _, local_file = _paths(base_path, local_path)
    config.write_local_config(local, local_file)
    if api_key:
        config.write_secret_file(secret_file, env, api_key, root)
    return "created" if create else "updated"


def delete_model(
    *,
    provider: object,
    model_id: object,
    base_path: Path | None = None,
    local_path: Path | None = None,
    root: Path | None = None,
) -> None:
    provider_name = str(provider or "").strip()
    name = str(model_id or "").strip()
    local = _local(base_path, local_path)
    providers = local.get("providers") or {}
    provider_local = providers.get(provider_name)
    if not isinstance(provider_local, dict) or name not in provider_local:
        raise AiConfigError(
            f"'{provider_name}/{name}' không phải model tạo trong app"
        )
    settings = _settings(base_path, local_path)
    if settings.provider_name == provider_name and settings.model_name == name:
        raise AiConfigError("đang là model mặc định; chọn model khác trước")
    removed = provider_local.pop(name)
    if not provider_local:
        providers.pop(provider_name, None)
    if not providers:
        local.pop("providers", None)

    _validate_candidate(local, base_path)
    _, local_file = _paths(base_path, local_path)
    config.write_local_config(local, local_file)
    _drop_orphan_secrets({name: removed}, base_path, local_path, root)


def set_default(
    *,
    provider: object,
    model: object,
    base_path: Path | None = None,
    local_path: Path | None = None,
) -> None:
    provider_name = str(provider or "").strip()
    model_name = str(model or "").strip()
    raw = _raw(base_path, local_path)
    provider_table = _provider_entry(raw, provider_name)
    if provider_table is None:
        raise AiConfigError(f"không có provider '{provider_name}'", 404)
    if model_name not in _model_tables(provider_table):
        raise AiConfigError(
            f"không có model '{model_name}' trong provider '{provider_name}'",
            404,
        )
    local = _local(base_path, local_path)
    local["default_provider"] = provider_name
    local["default_model"] = model_name
    _validate_candidate(local, base_path)
    _, local_file = _paths(base_path, local_path)
    config.write_local_config(local, local_file)
