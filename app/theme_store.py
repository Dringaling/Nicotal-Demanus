# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import shutil
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from .config import REPO_ROOT, ConfigError

THEMES_DIR = REPO_ROOT / "templates" / "themes"
ACTIVE_DIR = THEMES_DIR / "active"
_MAX_ALIAS = 60


@dataclass(frozen=True)
class ThemeEntry:
    id: str
    name: str
    file: Path
    is_alias: bool
    alias: str
    base_name: str


def sync_active_themes(
    overwrite: bool = False,
    themes_dir: Path | None = None,
    active_dir: Path | None = None,
) -> int:
    backup = Path(themes_dir) if themes_dir is not None else THEMES_DIR
    active = Path(active_dir) if active_dir is not None else ACTIVE_DIR
    active.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in sorted(backup.glob("*.toml")):
        target = active / source.name
        if overwrite or not target.is_file():
            shutil.copy2(source, target)
            copied += 1
    return copied


def ensure_active_themes(
    themes_dir: Path | None = None,
    active_dir: Path | None = None,
) -> int:
    return sync_active_themes(False, themes_dir, active_dir)


def _check_rgb(value: object, field_name: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(isinstance(item, (int, float)) for item in value)
    ):
        raise ConfigError(f"{field_name} phải là mảng 3 số RGB")


def validate_theme_data(data: dict) -> None:
    theme = data.get("theme")
    if not isinstance(theme, dict):
        raise ConfigError("Theme thiếu bảng [theme]")
    if not str(theme.get("id", "")).strip():
        raise ConfigError("Theme thiếu theme.id")
    if not str(theme.get("name", "")).strip():
        raise ConfigError("Theme thiếu theme.name")

    palette = data.get("palette")
    if not isinstance(palette, dict):
        raise ConfigError("Theme thiếu bảng [palette]")
    for key in ("bg", "card", "accent", "text", "muted"):
        _check_rgb(palette.get(key), f"palette.{key}")

    if str(theme.get("renderer", "theme")) != "theme":
        return

    colors = data.get("colors")
    if not isinstance(colors, dict):
        raise ConfigError("Theme thiếu bảng [colors]")
    required_colors = {
        "background": ("rgb",),
        "card": ("bg_rgb", "border_rgb"),
        "accent": ("primary_rgb", "secondary_rgb", "success_rgb"),
        "text": ("primary_rgb", "secondary_rgb"),
    }
    for table, keys in required_colors.items():
        section = colors.get(table)
        if not isinstance(section, dict):
            raise ConfigError(f"Thiếu colors.{table}")
        for key in keys:
            _check_rgb(section.get(key), f"colors.{table}.{key}")

    typography = data.get("typography")
    if not isinstance(typography, dict):
        raise ConfigError("Theme thiếu bảng [typography]")
    for key in (
        "title_hero",
        "title_section",
        "card_title",
        "card_body",
        "big_metric",
    ):
        item = typography.get(key)
        if not isinstance(item, dict) or not isinstance(
            item.get("size_pt"), (int, float)
        ):
            raise ConfigError(f"Thiếu typography.{key}.size_pt")

    layouts = data.get("layouts")
    if not isinstance(layouts, dict):
        raise ConfigError("Theme thiếu bảng [layouts]")
    three_cards = layouts.get("three_cards")
    header = three_cards.get("header") if isinstance(three_cards, dict) else None
    if not isinstance(header, dict):
        raise ConfigError("Thiếu layouts.three_cards.header")
    for key in ("left_inch", "top_inch", "width_inch", "height_inch"):
        if not isinstance(header.get(key), (int, float)):
            raise ConfigError(
                f"Thiếu layouts.three_cards.header.{key}"
            )

    variants = data.get("variants", {})
    if not isinstance(variants, dict):
        raise ConfigError("[variants] phải là bảng TOML")
    for variant_id, variant in variants.items():
        if not isinstance(variant, dict):
            raise ConfigError(f"[variants.{variant_id}] phải là bảng TOML")
        variant_palette = variant.get("palette")
        if variant_palette is None:
            continue
        if not isinstance(variant_palette, dict):
            raise ConfigError(
                f"variants.{variant_id}.palette phải là bảng TOML"
            )
        for key in ("bg", "card", "accent", "text", "muted"):
            if key in variant_palette:
                _check_rgb(
                    variant_palette[key],
                    f"variants.{variant_id}.palette.{key}",
                )


def _alias_parts(path: Path) -> tuple[str, str]:
    stem = path.stem
    if "." not in stem:
        return "", ""
    base, alias = stem.split(".", 1)
    return base, alias


def validate_alias(alias: str) -> str:
    value = str(alias).strip()
    if not value:
        raise ConfigError("Alias không được để trống")
    if len(value) > _MAX_ALIAS:
        raise ConfigError(f"Alias tối đa {_MAX_ALIAS} ký tự")
    for char in value:
        if char in "-_" or char.isdigit():
            continue
        name = unicodedata.name(char, "")
        if char.isalpha() and name.startswith(("LATIN", "VIETNAMESE")):
            continue
        raise ConfigError(
            "Alias chỉ gồm chữ cái Latin/Việt, số, dấu '-' và '_' "
            "(không khoảng trắng)"
        )
    return value


def _active_files(active_dir: Path | None = None) -> list[Path]:
    active = Path(active_dir) if active_dir is not None else ACTIVE_DIR
    if not active.is_dir():
        return []
    return sorted(active.glob("*.toml"))


def _find_file(
    theme_id: str,
    active_dir: Path | None = None,
) -> tuple[Path, dict]:
    for path in _active_files(active_dir):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(data.get("theme", {}).get("id", "")) == theme_id:
            return path, data
    raise ConfigError(f"Không tìm thấy theme: {theme_id}")


def read_theme_text(theme_id: str, active_dir: Path | None = None) -> str:
    path, _ = _find_file(theme_id, active_dir)
    return path.read_text(encoding="utf-8")


def save_theme(
    theme_id: str,
    content: str,
    active_dir: Path | None = None,
) -> str:
    path, _ = _find_file(theme_id, active_dir)
    try:
        data = tomllib.loads(content)
    except Exception as exc:
        raise ConfigError(f"TOML không hợp lệ: {exc}") from exc
    validate_theme_data(data)
    theme = data["theme"]

    base, alias = _alias_parts(path)
    if base:
        theme["id"] = f"{base}.{alias}"
        theme["alias_of"] = base
        theme.setdefault("name", f"{base} - {alias}")
    else:
        theme["id"] = path.stem
        theme.pop("alias_of", None)

    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return str(theme["id"])


def _original_names(themes_dir: Path) -> set[str]:
    names: set[str] = set()
    for path in themes_dir.glob("*.toml"):
        names.add(path.stem.casefold())
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        theme = data.get("theme", {})
        for key in ("id", "name"):
            value = str(theme.get(key, "")).strip()
            if value:
                names.add(value.casefold())
        variants = data.get("variants", {})
        if isinstance(variants, dict):
            for variant in variants.values():
                if isinstance(variant, dict):
                    value = str(variant.get("name", "")).strip()
                    if value:
                        names.add(value.casefold())
    return names


def create_alias(
    theme_id: str,
    alias: str,
    content: str | None = None,
    active_dir: Path | None = None,
    themes_dir: Path | None = None,
) -> str:
    alias = validate_alias(alias)
    backup_dir = Path(themes_dir) if themes_dir is not None else THEMES_DIR
    if alias.casefold() in _original_names(backup_dir):
        raise ConfigError(
            f"Alias '{alias}' trùng tên với theme gốc trong themes/"
        )
    source_path, source_data = _find_file(theme_id, active_dir)
    base, _ = _alias_parts(source_path)
    if base:
        raise ConfigError("Chỉ tạo alias từ theme hệ thống")
    target = source_path.parent / f"{source_path.stem}.{alias}.toml"
    if target.exists():
        raise ConfigError(f"Alias '{alias}' đã tồn tại")

    if content is None:
        content = source_path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(content)
    except Exception as exc:
        raise ConfigError(f"TOML không hợp lệ: {exc}") from exc
    validate_theme_data(data)
    theme = data["theme"]

    base_name = source_path.stem
    original_name = str(source_data.get("theme", {}).get("name", base_name))
    theme["id"] = f"{base_name}.{alias}"
    theme["name"] = f"{original_name} - {alias}"
    theme["alias_of"] = base_name
    target.write_text(tomli_w.dumps(data), encoding="utf-8")
    return str(theme["id"])


def reset_theme(
    theme_id: str,
    active_dir: Path | None = None,
    themes_dir: Path | None = None,
) -> str:
    path, _ = _find_file(theme_id, active_dir)
    active = path.parent
    backup_dir = Path(themes_dir) if themes_dir is not None else THEMES_DIR
    base, alias = _alias_parts(path)

    if base:
        # Alias khôi phục từ bản active hiện tại của theme gốc.
        source = active / f"{base}.toml"
        if not source.is_file():
            fallback = backup_dir / f"{base}.toml"
            if not fallback.is_file():
                raise ConfigError(f"Không tìm thấy theme gốc: {fallback}")
            shutil.copy2(fallback, source)
    else:
        # Bản active của theme gốc khôi phục từ file backup trong themes/.
        source = backup_dir / f"{path.stem}.toml"
        if not source.is_file():
            raise ConfigError(f"Không tìm thấy theme gốc: {source}")

    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"Theme gốc không hợp lệ: {exc}") from exc
    validate_theme_data(data)
    theme = data["theme"]

    if base:
        original_name = str(theme.get("name", base))
        theme["id"] = f"{base}.{alias}"
        theme["name"] = f"{original_name} - {alias}"
        theme["alias_of"] = base
    else:
        theme["id"] = path.stem
        theme.pop("alias_of", None)

    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return str(theme["id"])


def delete_theme(theme_id: str, active_dir: Path | None = None) -> None:
    path, _ = _find_file(theme_id, active_dir)
    base, _ = _alias_parts(path)
    if not base:
        raise ConfigError("Chỉ xoá được alias theme")
    path.unlink()


def list_theme_entries() -> list[ThemeEntry]:
    from .templates_catalog import list_templates

    entries: list[ThemeEntry] = []
    for meta in list_templates():
        if meta.variant_id:
            continue
        if meta.kind != "theme":
            continue
        path = Path(meta.theme_file)
        base, alias = _alias_parts(path)
        entries.append(
            ThemeEntry(
                id=meta.id,
                name=meta.name,
                file=path,
                is_alias=bool(base),
                alias=alias,
                base_name=base or path.stem,
            )
        )
    entries.sort(key=lambda item: (item.is_alias, item.name.casefold()))
    return entries
