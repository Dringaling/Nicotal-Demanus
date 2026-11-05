from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import REPO_ROOT, ConfigError
from .schema import DeckSpec, Palette
from .template_profile import TemplateProfile, format_profile_layouts

CONFIG_PATH = REPO_ROOT / "config" / "templates.toml"


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
    accent_secondary: tuple[int, int, int] | None = None
    assets_dir: str = ""
    theme_file: str = ""
    renderer: str = "template"
    layout_map: dict[str, str] = field(default_factory=dict)

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _rgb(value: object, field: str) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise ConfigError(f"'{field}' phải là mảng 3 số RGB")
    return (int(value[0]), int(value[1]), int(value[2]))


def load_templates(path: Path | None = None) -> dict[str, TemplateMeta]:
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    if not cfg_path.is_file():
        raise ConfigError(f"Không tìm thấy file metadata template: {cfg_path}")

    with cfg_path.open("rb") as handle:
        raw = tomllib.load(handle)

    templates_raw = raw.get("templates")
    if not isinstance(templates_raw, dict):
        raise ConfigError(f"Thiếu bảng [templates] trong {cfg_path}")

    result: dict[str, TemplateMeta] = {}
    for template_id, data in templates_raw.items():
        if not isinstance(data, dict):
            raise ConfigError(f"[templates.{template_id}] phải là bảng TOML")
        layout_raw = data.get("layout_map") or {}
        if not isinstance(layout_raw, dict):
            raise ConfigError(
                f"[templates.{template_id}.layout_map] phải là bảng TOML"
            )
        result[template_id] = TemplateMeta(
            id=template_id,
            name=str(data.get("name", template_id)),
            file=str(data.get("file", "")),
            font=str(data.get("font", "Lexend")),
            bg_color=_rgb(data.get("bg_color"), "bg_color"),
            card_color=_rgb(data.get("card_color"), "card_color"),
            accent_color=_rgb(data.get("accent_color"), "accent_color"),
            text_color=_rgb(data.get("text_color"), "text_color"),
            muted_color=_rgb(data.get("muted_color"), "muted_color"),
            description=str(data.get("description", "")),
            accent_secondary=(
                _rgb(data["accent_secondary"], "accent_secondary")
                if "accent_secondary" in data
                else None
            ),
            assets_dir=str(data.get("assets_dir", "")),
            theme_file=str(data.get("theme_file", "")),
            renderer=str(data.get("renderer", "template")),
            layout_map={
                str(key): str(value) for key, value in layout_raw.items()
            },
        )
    return result


def list_templates() -> list[TemplateMeta]:
    return list(load_templates().values())


def get_template(template_id: str) -> TemplateMeta | None:
    return load_templates().get(template_id)


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
