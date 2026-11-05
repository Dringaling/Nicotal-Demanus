from __future__ import annotations

import os
import socket
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "providers.toml"


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
    base_url: str
    model: str
    service_tier: str
    api_key_env: str
    api_key_file: str
    fallback_models: tuple[str, ...] = ()
    fail_fast: bool = False
    timeout_seconds: float = 180.0
    max_retries: int = 3
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)


@dataclass(frozen=True)
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8765
    lan_ip: str = ""


@dataclass(frozen=True)
class Settings:
    provider_name: str
    provider: ProviderSettings
    server: ServerSettings


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


def load_settings(path: Path | None = None) -> Settings:
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    if not cfg_path.is_file():
        raise ConfigError(f"Không tìm thấy file cấu hình: {cfg_path}")

    with cfg_path.open("rb") as fh:
        raw = tomllib.load(fh)

    default = raw.get("default")
    if not isinstance(default, dict):
        raise ConfigError(f"Thiếu bảng [default] trong {cfg_path}")
    provider_name = _as_str(_require(default, "provider", "[default]"), "provider")

    pdata = raw.get(provider_name)
    if not isinstance(pdata, dict):
        raise ConfigError(f"Thiếu bảng [{provider_name}] trong {cfg_path}")

    generation_raw = pdata.get("generation", {})
    cache_raw = pdata.get("cache", {})
    if not isinstance(generation_raw, dict) or not isinstance(cache_raw, dict):
        raise ConfigError("Bảng [generation]/[cache] phải là bảng TOML")

    generation = GenerationSettings(
        temperature=float(generation_raw.get("temperature", 0.4)),
        top_p=float(generation_raw.get("top_p", 0.95)),
        max_tokens=int(generation_raw.get("max_tokens", 8000)),
        response_format=str(generation_raw.get("response_format", "json_schema")),
        chunk_chars=int(generation_raw.get("chunk_chars", 8000)),
    )
    cache = CacheSettings(
        prompt_version=str(cache_raw.get("prompt_version", "demanus-deck-v4")),
        prompt_cache_key=str(cache_raw.get("prompt_cache_key", "demanus-deck-v4")),
        cache_ttl=str(cache_raw.get("cache_ttl", "1h")),
        local_cache=bool(cache_raw.get("local_cache", True)),
        local_cache_dir=str(cache_raw.get("local_cache_dir", "input/.cache")),
    )

    fallback = pdata.get("fallback_models", [])
    if not isinstance(fallback, list):
        raise ConfigError("'fallback_models' phải là mảng chuỗi")

    provider = ProviderSettings(
        base_url=_as_str(_require(pdata, "base_url", provider_name), "base_url").rstrip("/"),
        model=_as_str(_require(pdata, "model", provider_name), "model"),
        service_tier=str(pdata.get("service_tier", "flex")),
        api_key_env=_as_str(_require(pdata, "api_key_env", provider_name), "api_key_env"),
        api_key_file=_as_str(_require(pdata, "api_key_file", provider_name), "api_key_file"),
        fallback_models=tuple(str(m) for m in fallback),
        fail_fast=bool(pdata.get("fail_fast", False)),
        timeout_seconds=float(pdata.get("timeout_seconds", 180)),
        max_retries=int(pdata.get("max_retries", 3)),
        generation=generation,
        cache=cache,
    )

    server_raw = raw.get("server", {})
    if not isinstance(server_raw, dict):
        raise ConfigError("Bảng [server] phải là bảng TOML")
    server = ServerSettings(
        host=str(server_raw.get("host", "0.0.0.0")),
        port=int(server_raw.get("port", 8765)),
        lan_ip=str(server_raw.get("lan_ip", "")),
    )

    return Settings(provider_name=provider_name, provider=provider, server=server)


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


def _read_env_file(key_path: Path, wanted: str) -> str | None:
    for raw_line in key_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != wanted:
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
    env_value = os.environ.get(provider.api_key_env)
    if env_value and env_value.strip():
        return env_value.strip()

    base = Path(root) if root is not None else REPO_ROOT
    key_path = Path(provider.api_key_file)
    if not key_path.is_absolute():
        key_path = base / key_path

    if not key_path.is_file():
        raise ConfigError(
            f"Thiếu API key: đặt biến môi trường {provider.api_key_env} "
            f"hoặc tạo file {key_path}"
        )

    value = _read_env_file(key_path, provider.api_key_env)
    if not value:
        raise ConfigError(
            f"File {key_path} không chứa biến {provider.api_key_env}"
        )
    return value
