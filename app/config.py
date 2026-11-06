# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "providers.toml"
PROVIDER_TYPES = {"deepinfra", "openai", "lmstudio"}


class ConfigError(RuntimeError):
    """Cấu hình hoặc secret thiếu/sai."""


@dataclass(frozen=True)
class GenerationSettings:
    temperature: float = 0.4
    top_p: float = 0.95
    max_tokens: int = 8000
    response_format: str = "json_schema"
    chunk_chars: int = 8000


@dataclass(frozen=True)
class CacheSettings:
    prompt_version: str = "demanus-deck-v4"
    prompt_cache_key: str = "demanus-deck-v4"
    cache_ttl: str = "1h"
    local_cache: bool = True
    local_cache_dir: str = "input/.cache"


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    type: str
    base_url: str
    model: str
    service_tier: str = "flex"
    api_key_env: str = ""
    api_key_file: str = ""
    fallback_models: tuple[str, ...] = ()
    fail_fast: bool = False
    timeout_seconds: float = 180.0
    max_retries: int = 3
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    params: dict = field(default_factory=dict)

    @property
    def secret_file(self) -> str:
        return self.api_key_file

    @property
    def requires_key(self) -> bool:
        return bool(self.api_key_env or self.api_key_file)


@dataclass(frozen=True)
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8765
    lan_ip: str = ""


@dataclass(frozen=True)
class Settings:
    provider_name: str
    model_name: str
    provider: ProviderSettings
    server: ServerSettings
    providers: dict[str, ProviderSettings] = field(default_factory=dict)


@dataclass(frozen=True)
class Paths:
    root: Path
    input: Path
    output: Path
    templates: Path
    secret: Path
    cache: Path


def paths(root: Path | None = None) -> Paths:
    base = Path(root) if root is not None else REPO_ROOT
    return Paths(
        root=base,
        input=base / "input",
        output=base / "output",
        templates=base / "templates",
        secret=base / "secret",
        cache=base / "input" / ".cache",
    )


def _require(mapping: dict, key: str, where: str) -> object:
    if key not in mapping:
        raise ConfigError(f"Thiếu khoá '{key}' trong {where}")
    return mapping[key]


def _as_str(value: object, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Giá trị '{key}' phải là chuỗi không rỗng")
    return value.strip()


def _infer_type(base_url: str) -> str:
    host = urlparse(base_url).hostname or ""
    if "deepinfra.com" in host:
        return "deepinfra"
    if "/api/v1" in base_url:
        return "lmstudio"
    return "openai"


def _parse_generation(raw: object) -> GenerationSettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("Bảng [generation] phải là bảng TOML")
    return GenerationSettings(
        temperature=float(raw.get("temperature", 0.4)),
        top_p=float(raw.get("top_p", 0.95)),
        max_tokens=int(raw.get("max_tokens", 8000)),
        response_format=str(raw.get("response_format", "json_schema")),
        chunk_chars=int(raw.get("chunk_chars", 8000)),
    )


def _parse_cache(raw: object) -> CacheSettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("Bảng [cache] phải là bảng TOML")
    return CacheSettings(
        prompt_version=str(raw.get("prompt_version", "demanus-deck-v4")),
        prompt_cache_key=str(raw.get("prompt_cache_key", "demanus-deck-v4")),
        cache_ttl=str(raw.get("cache_ttl", "1h")),
        local_cache=bool(raw.get("local_cache", True)),
        local_cache_dir=str(raw.get("local_cache_dir", "input/.cache")),
    )


PROVIDER_RESERVED = {
    "type",
    "base_url",
    "api_key_env",
    "secret_file",
    "api_key_file",
    "timeout_seconds",
    "max_retries",
    "params",
    "generation",
    "cache",
    "default_model",
}


def _merge_generation(
    base: GenerationSettings, raw: object
) -> GenerationSettings:
    if raw is None:
        return base
    if not isinstance(raw, dict):
        raise ConfigError("Bảng [generation] phải là bảng TOML")
    return GenerationSettings(
        temperature=float(raw.get("temperature", base.temperature)),
        top_p=float(raw.get("top_p", base.top_p)),
        max_tokens=int(raw.get("max_tokens", base.max_tokens)),
        response_format=str(
            raw.get("response_format", base.response_format)
        ),
        chunk_chars=int(raw.get("chunk_chars", base.chunk_chars)),
    )


def _merge_cache(base: CacheSettings, raw: object) -> CacheSettings:
    if raw is None:
        return base
    if not isinstance(raw, dict):
        raise ConfigError("Bảng [cache] phải là bảng TOML")
    return CacheSettings(
        prompt_version=str(raw.get("prompt_version", base.prompt_version)),
        prompt_cache_key=str(
            raw.get("prompt_cache_key", base.prompt_cache_key)
        ),
        cache_ttl=str(raw.get("cache_ttl", base.cache_ttl)),
        local_cache=bool(raw.get("local_cache", base.local_cache)),
        local_cache_dir=str(
            raw.get("local_cache_dir", base.local_cache_dir)
        ),
    )


def _provider_common(
    provider_name: str, data: dict, where: str
) -> dict:
    base_url = _as_str(_require(data, "base_url", where), "base_url").rstrip("/")
    provider_type = str(data.get("type", _infer_type(base_url))).strip().lower()
    if provider_type not in PROVIDER_TYPES:
        raise ConfigError(
            f"Provider '{provider_name}' có type '{provider_type}' không hợp lệ; "
            f"chọn một trong {sorted(PROVIDER_TYPES)}"
        )
    params = data.get("params", {})
    if not isinstance(params, dict):
        raise ConfigError(
            f"'params' của provider '{provider_name}' phải là bảng TOML"
        )
    return {
        "type": provider_type,
        "base_url": base_url,
        "timeout_seconds": float(data.get("timeout_seconds", 180)),
        "max_retries": int(data.get("max_retries", 3)),
        "params": params,
        "generation": _parse_generation(data.get("generation", {})),
        "cache": _parse_cache(data.get("cache", {})),
    }


def _resolve_model(
    provider_name: str,
    model_id: str,
    common: dict,
    data: dict,
) -> ProviderSettings:
    where = f"[providers.{provider_name}.{model_id}]"
    model = _as_str(_require(data, "model", where), "model")

    if "api_key_env" not in data:
        raise ConfigError(
            f"{where} phải khai báo 'api_key_env' riêng cho model "
            "(dùng chuỗi rỗng nếu local không cần key)"
        )
    api_key_env = str(data.get("api_key_env", ""))
    api_key_file = str(
        data.get("secret_file", data.get("api_key_file", ""))
    )

    params = dict(common["params"])
    model_params = data.get("params", {})
    if not isinstance(model_params, dict):
        raise ConfigError(f"'params' của {where} phải là bảng TOML")
    params.update(model_params)

    fallback = params.get("fallback_models", [])
    if not isinstance(fallback, list):
        raise ConfigError(
            f"'fallback_models' của {where} phải là mảng chuỗi"
        )

    return ProviderSettings(
        name=f"{provider_name}/{model_id}",
        type=common["type"],
        base_url=common["base_url"],
        model=model,
        service_tier=str(params.get("service_tier", "flex")),
        api_key_env=api_key_env,
        api_key_file=api_key_file,
        fallback_models=tuple(str(item) for item in fallback),
        fail_fast=bool(params.get("fail_fast", False)),
        timeout_seconds=common["timeout_seconds"],
        max_retries=common["max_retries"],
        generation=_merge_generation(
            common["generation"], data.get("generation")
        ),
        cache=_merge_cache(common["cache"], data.get("cache")),
        params=params,
    )


def _load_models(
    raw: dict, cfg_path: Path
) -> tuple[dict[str, ProviderSettings], str, str, ProviderSettings]:
    providers_raw = raw.get("providers")
    if not isinstance(providers_raw, dict) or not providers_raw:
        raise ConfigError(
            f"Thiếu bảng [providers] trong {cfg_path}"
        )

    models: dict[str, ProviderSettings] = {}
    for provider_name, pdata in providers_raw.items():
        if not isinstance(pdata, dict):
            raise ConfigError(f"[providers.{provider_name}] phải là bảng TOML")
        common = _provider_common(
            str(provider_name), pdata, f"[providers.{provider_name}]"
        )
        model_tables = {
            key: value
            for key, value in pdata.items()
            if key not in PROVIDER_RESERVED and isinstance(value, dict)
        }
        if not model_tables:
            model_tables = {str(provider_name): pdata}

        for model_id, mdata in model_tables.items():
            if not isinstance(mdata, dict):
                raise ConfigError(
                    f"[providers.{provider_name}.{model_id}] phải là bảng TOML"
                )
            resolved = _resolve_model(
                str(provider_name), str(model_id), common, mdata
            )
            models[resolved.name] = resolved

    seen_env: dict[str, str] = {}
    for key, provider in models.items():
        env = provider.api_key_env.strip()
        if not env:
            continue
        if env in seen_env:
            raise ConfigError(
                f"api_key_env '{env}' bị trùng giữa "
                f"'{seen_env[env]}' và '{key}'; mỗi model phải có tên riêng"
            )
        seen_env[env] = key

    default_provider = raw.get("default_provider")
    if not default_provider:
        default = raw.get("default")
        if isinstance(default, dict):
            default_provider = default.get("provider")
    if not default_provider:
        raise ConfigError(f"Thiếu 'default_provider' trong {cfg_path}")
    default_provider = str(default_provider)

    default_model = raw.get("default_model")
    if default_model:
        default_model = str(default_model)
        key = f"{default_provider}/{default_model}"
        if key not in models:
            raise ConfigError(
                f"default_model '{default_model}' không có trong "
                f"provider '{default_provider}'"
            )
    else:
        candidates = [
            item
            for item in models
            if item.startswith(f"{default_provider}/")
        ]
        if not candidates:
            raise ConfigError(
                f"Provider '{default_provider}' chưa khai báo model nào"
            )
        key = candidates[0]
        default_model = key.split("/", 1)[1]

    return models, default_provider, default_model, models[key]


def load_settings(path: Path | None = None) -> Settings:
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    if not cfg_path.is_file():
        raise ConfigError(f"Không tìm thấy file cấu hình: {cfg_path}")

    with cfg_path.open("rb") as fh:
        raw = tomllib.load(fh)

    models, provider_name, model_name, provider = _load_models(raw, cfg_path)

    override_provider = os.environ.get("DEMANUS_PROVIDER", "").strip()
    override_model = os.environ.get("DEMANUS_MODEL", "").strip()
    if override_provider:
        provider_name = override_provider
        if not override_model:
            candidates = [
                item
                for item in models
                if item.startswith(f"{provider_name}/")
            ]
            if not candidates:
                raise ConfigError(
                    f"DEMANUS_PROVIDER='{provider_name}' không có model nào"
                )
            model_name = candidates[0].split("/", 1)[1]
    if override_model:
        model_name = override_model

    key = f"{provider_name}/{model_name}"
    if key not in models:
        raise ConfigError(
            f"Không tìm thấy model '{model_name}' trong provider "
            f"'{provider_name}'"
        )
    provider = models[key]

    server_raw = raw.get("server", {})
    if not isinstance(server_raw, dict):
        raise ConfigError("Bảng [server] phải là bảng TOML")
    server = ServerSettings(
        host=str(server_raw.get("host", "0.0.0.0")),
        port=int(server_raw.get("port", 8765)),
        lan_ip=str(server_raw.get("lan_ip", "")),
    )

    return Settings(
        provider_name=provider_name,
        model_name=model_name,
        provider=provider,
        server=server,
        providers=models,
    )


def detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def lan_url(settings: Settings) -> str:
    host = settings.server.lan_ip.strip() or detect_lan_ip()
    return f"http://{host}:{settings.server.port}"


def _read_env_file(key_path: Path, wanted: str | None) -> str | None:
    for raw_line in key_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if wanted and key.strip() != wanted:
            continue
        value = value.strip()
        if value and value[0] in "\"'":
            quote = value[0]
            end = value.find(quote, 1)
            if end != -1:
                value = value[1:end]
        else:
            for marker in (" #", "\t#"):
                cut = value.find(marker)
                if cut != -1:
                    value = value[:cut]
        return value.strip() or None
    return None


def load_secret(provider: ProviderSettings, root: Path | None = None) -> str:
    if not provider.requires_key:
        return ""

    env_value = (
        os.environ.get(provider.api_key_env) if provider.api_key_env else None
    )
    if env_value and env_value.strip():
        return env_value.strip()

    if not provider.api_key_file:
        return ""

    base = Path(root) if root is not None else REPO_ROOT
    key_path = Path(provider.api_key_file)
    if not key_path.is_absolute():
        key_path = base / key_path

    if not key_path.is_file():
        raise ConfigError(
            f"Thiếu API key: đặt biến môi trường {provider.api_key_env} "
            f"hoặc tạo file {key_path}"
        )

    value = _read_env_file(key_path, provider.api_key_env or None)
    if not value:
        raise ConfigError(
            f"File {key_path} không chứa biến {provider.api_key_env}"
        )
    return value


def secret_status(
    provider: ProviderSettings, root: Path | None = None
) -> str:
    if not provider.requires_key:
        return "not-required"
    try:
        load_secret(provider, root)
    except ConfigError:
        return "missing"
    return "set"
