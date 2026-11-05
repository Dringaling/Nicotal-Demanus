from __future__ import annotations

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

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _rgb(value: object, field_name: str) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise ConfigError(f"'{field_name}' phải là mảng 3 số RGB")
    return (int(value[0]), int(value[1]), int(value[2]))


def _read_theme(path: Path) -> TemplateMeta:
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    theme = data.get("theme")
    if not isinstance(theme, dict):
        raise ConfigError(f"Thiếu bảng [theme] trong {path}")

    palette = data.get("palette")
    if not isinstance(palette, dict):
        raise ConfigError(f"Thiếu bảng [palette] trong {path}")

    layout_raw = data.get("layout_map") or {}
    if not isinstance(layout_raw, dict):
        raise ConfigError(f"[layout_map] phải là bảng TOML trong {path}")

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
        renderer=str(theme.get("renderer", "theme")),
        layout_map={
            str(key): str(value) for key, value in layout_raw.items()
        },
    )


def refresh_templates() -> list[TemplateMeta]:
    global _CACHE
    if not THEMES_DIR.is_dir():
        _CACHE = {}
        return []

    templates: dict[str, TemplateMeta] = {}
    for path in sorted(THEMES_DIR.glob("*.toml")):
        meta = _read_theme(path)
        templates[meta.id] = meta
    _CACHE = templates
    return list(templates.values())


def list_templates() -> list[TemplateMeta]:
    global _CACHE
    if _CACHE is None:
        refresh_templates()
    return list(_CACHE.values()) if _CACHE else []


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
    return _CACHE.get(alias)


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
