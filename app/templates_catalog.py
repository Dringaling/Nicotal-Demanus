# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import copy
import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import REPO_ROOT, ConfigError
from .schema import DeckSpec, Palette
from .template_profile import TemplateProfile, format_profile_layouts

THEMES_DIR = REPO_ROOT / "templates" / "themes"
_CACHE: dict[str, TemplateMeta] | None = None
_ALIASES: dict[str, str] = {}
_VARIANT_METADATA_KEYS = {"name", "description", "style", "tags"}


@dataclass(frozen=True)
class TemplateMeta:
    id: str
    name: str
    file: str
    font: str
    bg_color: tuple[int, int, int]
    card_color: tuple[int, int, int]
    accent_color: tuple[int, int, int]
    text_color: tuple[int, int, int]
    muted_color: tuple[int, int, int]
    description: str
    style: str = ""
    tags: tuple[str, ...] = ()
    accent_secondary: tuple[int, int, int] | None = None
    assets_dir: str = ""
    theme_file: str = ""
    renderer: str = "theme"
    layout_map: dict[str, str] = field(default_factory=dict)
    parent_id: str = ""
    variant_id: str = ""
    variant_name: str = ""
    kind: str = "theme"

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def display_name(self) -> str:
        if self.kind == "theme" and not self.variant_id:
            return f"{self.name} - Mặc định"
        return self.name


def _rgb(value: object, field_name: str) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise ConfigError(f"'{field_name}' phải là mảng 3 số RGB")
    return (int(value[0]), int(value[1]), int(value[2]))


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _infer_kind(renderer: str) -> str:
    return "pptx" if renderer in {"pptx", "boho", "copy"} else "theme"


def _read_theme(path: Path, data: dict) -> TemplateMeta:
    theme = data.get("theme")
    if not isinstance(theme, dict):
        raise ConfigError(f"Thiếu bảng [theme] trong {path}")

    palette = data.get("palette")
    if not isinstance(palette, dict):
        raise ConfigError(f"Thiếu bảng [palette] trong {path}")

    layout_raw = data.get("layout_map") or {}
    if not isinstance(layout_raw, dict):
        raise ConfigError(f"[layout_map] phải là bảng TOML trong {path}")

    renderer = str(theme.get("renderer", "theme"))
    return TemplateMeta(
        id=str(theme.get("id", path.stem)),
        name=str(theme.get("name", path.stem)),
        file=str(theme.get("pptx", "")),
        font=str(theme.get("font", "Lexend")),
        bg_color=_rgb(palette.get("bg"), "palette.bg"),
        card_color=_rgb(palette.get("card"), "palette.card"),
        accent_color=_rgb(palette.get("accent"), "palette.accent"),
        text_color=_rgb(palette.get("text"), "palette.text"),
        muted_color=_rgb(palette.get("muted"), "palette.muted"),
        description=str(theme.get("description", "")),
        style=str(theme.get("style", "")),
        tags=tuple(str(tag) for tag in theme.get("tags", [])),
        accent_secondary=(
            _rgb(palette["accent_secondary"], "palette.accent_secondary")
            if "accent_secondary" in palette
            else None
        ),
        assets_dir=str(theme.get("assets_dir", "")),
        theme_file=str(path),
        renderer=renderer,
        layout_map={
            str(key): str(value) for key, value in layout_raw.items()
        },
        kind=str(theme.get("kind", _infer_kind(renderer))),
    )


def _read_variant(
    path: Path,
    data: dict,
    base: TemplateMeta,
    variant_id: str,
    variant: dict,
) -> TemplateMeta:
    palette = data.get("palette")
    if not isinstance(palette, dict):
        raise ConfigError(f"Thiếu bảng [palette] trong {path}")
    merged = _deep_merge(palette, variant.get("palette") or {})

    variant_name = str(variant.get("name", variant_id))

    def pick(key: str, default):
        return variant[key] if key in variant else default

    return TemplateMeta(
        id=f"{base.id}__{variant_id}",
        name=f"{base.name} - {variant_name}",
        file=base.file,
        font=base.font,
        bg_color=_rgb(merged.get("bg"), "palette.bg"),
        card_color=_rgb(merged.get("card"), "palette.card"),
        accent_color=_rgb(merged.get("accent"), "palette.accent"),
        text_color=_rgb(merged.get("text"), "palette.text"),
        muted_color=_rgb(merged.get("muted"), "palette.muted"),
        description=str(pick("description", base.description)),
        style=str(pick("style", base.style)),
        tags=tuple(str(tag) for tag in pick("tags", base.tags)),
        accent_secondary=(
            _rgb(merged["accent_secondary"], "palette.accent_secondary")
            if "accent_secondary" in merged
            else base.accent_secondary
        ),
        assets_dir=base.assets_dir,
        theme_file=str(path),
        renderer=base.renderer,
        layout_map=base.layout_map,
        parent_id=base.id,
        variant_id=variant_id,
        variant_name=variant_name,
        kind=base.kind,
    )


def refresh_templates() -> list[TemplateMeta]:
    global _CACHE, _ALIASES
    if not THEMES_DIR.is_dir():
        _CACHE = {}
        _ALIASES = {}
        return []

    templates: dict[str, TemplateMeta] = {}
    aliases: dict[str, str] = {}
    for path in sorted(THEMES_DIR.glob("*.toml")):
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        base = _read_theme(path, data)
        templates[base.id] = base

        variants = data.get("variants") or {}
        if not isinstance(variants, dict):
            raise ConfigError(f"[variants] phải là bảng TOML trong {path}")
        for variant_id, variant in variants.items():
            if not isinstance(variant, dict):
                raise ConfigError(
                    f"[variants.{variant_id}] phải là bảng TOML trong {path}"
                )
            meta = _read_variant(
                path, data, base, str(variant_id), variant
            )
            templates[meta.id] = meta
            aliases[str(variant_id)] = meta.id

    _CACHE = templates
    _ALIASES = aliases
    return list(templates.values())


def list_templates() -> list[TemplateMeta]:
    global _CACHE
    if _CACHE is None:
        refresh_templates()
    return list(_CACHE.values()) if _CACHE else []


def grouped_templates() -> dict[str, list[TemplateMeta]]:
    groups: dict[str, list[TemplateMeta]] = {"pptx": [], "themes": []}
    for meta in list_templates():
        key = "pptx" if meta.kind == "pptx" else "themes"
        groups[key].append(meta)
    return groups


def get_template(template_id: str) -> TemplateMeta | None:
    global _CACHE
    if _CACHE is None:
        refresh_templates()
    if not _CACHE:
        return None
    meta = _CACHE.get(template_id)
    if meta is not None:
        return meta
    alias = (
        template_id.replace("-", "_")
        if "-" in template_id
        else template_id.replace("_", "-")
    )
    target = _ALIASES.get(template_id) or _ALIASES.get(alias)
    if target is not None:
        return _CACHE.get(target)
    return _CACHE.get(alias)


def load_theme_data(meta: TemplateMeta) -> dict:
    path = resolve_path(meta.theme_file) if meta.theme_file else None
    if path is None or not path.is_file():
        raise ConfigError(f"Thiếu theme file cho {meta.id}")

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    variants = data.pop("variants", {}) or {}
    if meta.variant_id:
        override = variants.get(meta.variant_id)
        if not isinstance(override, dict):
            raise ConfigError(
                f"Thiếu variant '{meta.variant_id}' trong {path}"
            )
        override = {
            key: value
            for key, value in override.items()
            if key not in _VARIANT_METADATA_KEYS
        }
        data = _deep_merge(data, override)
    return data


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def template_file(meta: TemplateMeta) -> Path | None:
    if not meta.file:
        return None
    path = resolve_path(meta.file)
    return path if path.is_file() else None


def template_assets_dir(meta: TemplateMeta) -> Path | None:
    if not meta.assets_dir:
        return None
    path = resolve_path(meta.assets_dir)
    return path if path.is_dir() else None


def hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def format_design_tokens(meta: TemplateMeta) -> str:
    lines = [
        f"Name: {meta.name}",
        f"Description: {meta.description}",
        f"Style: {meta.style or '?'}",
        f"Tags: {', '.join(meta.tags) if meta.tags else '?'}",
        "Design tokens:",
        f"- background: {hex_color(meta.bg_color)}",
        f"- card: {hex_color(meta.card_color)}",
        f"- accent: {hex_color(meta.accent_color)}",
        f"- text: {hex_color(meta.text_color)}",
        f"- muted: {hex_color(meta.muted_color)}",
    ]
    if meta.accent_secondary:
        lines.append(f"- accent secondary: {hex_color(meta.accent_secondary)}")
    lines.append(f"- font: {meta.font} (forced; ignore template fonts)")
    return "\n".join(lines)


def format_template_context(
    meta: TemplateMeta,
    profile: TemplateProfile | None,
) -> str:
    lines = ["TEMPLATE CONTEXT", format_design_tokens(meta)]
    if profile is not None:
        lines.append(
            f"Slide size: {profile.width_in:.2f} x {profile.height_in:.2f} in"
        )
        lines.append(format_profile_layouts(profile, meta.layout_map or None))
    return "\n".join(lines)


def apply_template_palette(spec: DeckSpec, meta: TemplateMeta) -> DeckSpec:
    palette = Palette(
        primary=hex_color(meta.accent_color),
        accent=hex_color(meta.accent_color),
        text=hex_color(meta.text_color),
        muted=hex_color(meta.muted_color),
        background=hex_color(meta.bg_color),
    )
    return spec.model_copy(update={"palette": palette, "font": meta.font})
