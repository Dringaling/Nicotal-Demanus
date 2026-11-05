from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from pptx import Presentation

from .config import REPO_ROOT

SEMANTIC_LAYOUTS = {
    "title": "TITLE",
    "section": "SECTION_HEADER",
    "bullets": "TITLE_AND_BODY",
    "two_column": "TITLE_AND_TWO_COLUMNS",
    "table": "TITLE_ONLY",
    "quote": "MAIN_POINT",
    "closing": "TITLE",
}

TEMPLATE_PATHS = {
    "dividing-fractions": (
        REPO_ROOT / "templates" / "Dividing Fractions by Fractions Lesson.pptx"
    ),
}

_COLOR_KEYS = (
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)


@dataclass(frozen=True)
class PlaceholderInfo:
    idx: int
    type: str
    name: str
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class LayoutInfo:
    name: str
    placeholders: tuple[PlaceholderInfo, ...]
    media: tuple[str, ...]


@dataclass(frozen=True)
class TemplateProfile:
    name: str
    width_in: float
    height_in: float
    colors: dict[str, str]
    major_font: str
    minor_font: str
    layouts: tuple[LayoutInfo, ...]

    def to_dict(self) -> dict:
        return asdict(self)

    def fingerprint(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _theme_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if re.match(r"ppt/theme/theme\d+\.xml$", name)
        ]
        if not names:
            return ""
        return archive.read(sorted(names)[0]).decode("utf-8", "ignore")


def _color_value(fragment: str) -> str | None:
    match = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', fragment)
    if match:
        return "#" + match.group(1).upper()
    match = re.search(r'<a:sysClr[^>]*lastClr="([0-9A-Fa-f]{6})"', fragment)
    if match:
        return "#" + match.group(1).upper()
    return None


def _parse_colors(theme: str) -> dict[str, str]:
    colors: dict[str, str] = {}
    for key in _COLOR_KEYS:
        match = re.search(rf"<a:{key}>(.*?)</a:{key}>", theme, re.S)
        if not match:
            continue
        value = _color_value(match.group(1))
        if value:
            colors[key] = value
    return colors


def _parse_font(theme: str, tag: str) -> str:
    match = re.search(rf'<a:{tag}><a:latin typeface="([^"]*)"', theme)
    return match.group(1) if match else ""


def _placeholder_info(placeholder) -> PlaceholderInfo:
    return PlaceholderInfo(
        idx=placeholder.placeholder_format.idx,
        type=str(placeholder.placeholder_format.type),
        name=placeholder.name,
        x=round(placeholder.left / 914400, 2),
        y=round(placeholder.top / 914400, 2),
        w=round(placeholder.width / 914400, 2),
        h=round(placeholder.height / 914400, 2),
    )


def _layout_media(archive: zipfile.ZipFile, layout) -> tuple[str, ...]:
    part_name = str(layout.part.partname).rsplit("/", 1)[-1]
    rels_name = f"ppt/slideLayouts/_rels/{part_name}.rels"
    if rels_name not in archive.namelist():
        return ()
    rels = archive.read(rels_name).decode("utf-8", "ignore")
    return tuple(
        sorted(set(re.findall(r'Target="\.\./media/([^"]+)"', rels)))
    )


@lru_cache(maxsize=8)
def load_profile_from_path(
    path_value: str,
    layout_items: tuple[tuple[str, str], ...] = (),
) -> TemplateProfile:
    mapping = dict(layout_items) or SEMANTIC_LAYOUTS
    path = Path(path_value)
    presentation = Presentation(str(path))
    theme = _theme_xml(path)
    wanted = set(mapping.values())

    layouts: list[LayoutInfo] = []
    with zipfile.ZipFile(path) as archive:
        for layout in presentation.slide_layouts:
            if layout.name not in wanted:
                continue
            placeholders = tuple(
                _placeholder_info(placeholder)
                for placeholder in layout.placeholders
            )
            layouts.append(
                LayoutInfo(
                    name=layout.name,
                    placeholders=placeholders,
                    media=_layout_media(archive, layout),
                )
            )

    return TemplateProfile(
        name=path.stem,
        width_in=round(presentation.slide_width / 914400, 3),
        height_in=round(presentation.slide_height / 914400, 3),
        colors=_parse_colors(theme),
        major_font=_parse_font(theme, "majorFont"),
        minor_font=_parse_font(theme, "minorFont"),
        layouts=tuple(layouts),
    )


@lru_cache(maxsize=8)
def load_template_profile(template_id: str) -> TemplateProfile | None:
    path = TEMPLATE_PATHS.get(template_id)
    if path is None or not path.is_file():
        return None
    return load_profile_from_path(str(path))


def template_profile_hash(template_id: str) -> str:
    profile = load_template_profile(template_id)
    return profile.fingerprint() if profile else ""


def format_profile_layouts(
    profile: TemplateProfile,
    layout_map: dict[str, str] | None = None,
) -> str:
    mapping = layout_map or SEMANTIC_LAYOUTS
    lines = ["Semantic layout mapping:"]

    for semantic, template_name in mapping.items():
        layout = next(
            (item for item in profile.layouts if item.name == template_name),
            None,
        )
        if layout is None:
            continue
        parts = [
            f"idx{ph.idx} {ph.type} at ({ph.x:.2f},{ph.y:.2f}) "
            f"size {ph.w:.2f}x{ph.h:.2f} in"
            for ph in layout.placeholders
            if ph.idx != 12
        ]
        lines.append(f"- {semantic} -> {template_name}: " + "; ".join(parts))

    media = sorted({name for layout in profile.layouts for name in layout.media})
    if media:
        lines.append("Layout media: " + ", ".join(media))

    return "\n".join(lines)


def format_template_profile(profile: TemplateProfile) -> str:
    lines = [
        "TEMPLATE CONTEXT",
        f"Name: {profile.name}",
        f"Slide size: {profile.width_in:.2f} x {profile.height_in:.2f} in",
        "Theme colors: "
        + ", ".join(f"{key}={value}" for key, value in profile.colors.items()),
        f"Fonts: major={profile.major_font or '?'}, minor={profile.minor_font or '?'}",
        format_profile_layouts(profile),
    ]

    return "\n".join(lines)
