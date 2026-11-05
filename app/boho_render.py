from __future__ import annotations

import logging
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

from .render import (
    CONTENT_LEFT,
    CONTENT_WIDTH,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    _body_top,
    _bullets,
    _table,
    _text,
    _two_column,
)
from .schema import DeckSpec, Palette
from .templates_catalog import TemplateMeta, hex_color, template_assets_dir

logger = logging.getLogger(__name__)

_ASSETS = {
    "bg": "bg_paper.jpg",
    "brush": "brush_header.png",
    "accent": "brush_accent.png",
}


def _asset_paths(meta: TemplateMeta) -> dict[str, Path] | None:
    directory = template_assets_dir(meta)
    if directory is None:
        return None
    paths = {key: directory / name for key, name in _ASSETS.items()}
    if not all(path.is_file() for path in paths.values()):
        return None
    return paths


def _styled_spec(spec: DeckSpec, meta: TemplateMeta) -> DeckSpec:
    palette = Palette(
        primary=hex_color(meta.accent_color),
        accent=hex_color(meta.accent_color),
        text=hex_color(meta.text_color),
        muted=hex_color(meta.muted_color),
        background=hex_color(meta.bg_color),
    )
    return spec.model_copy(update={"palette": palette, "font": meta.font})


def _background(
    slide,
    assets: dict[str, Path],
    *,
    brush: bool = True,
    accent: bool = True,
    brush_width: float = 5.4,
    brush_y: float = -0.15,
) -> None:
    slide.shapes.add_picture(
        str(assets["bg"]), 0, 0, width=SLIDE_WIDTH, height=SLIDE_HEIGHT
    )
    if brush:
        slide.shapes.add_picture(
            str(assets["brush"]),
            Inches(0.35),
            Inches(brush_y),
            width=Inches(brush_width),
        )
    if accent:
        slide.shapes.add_picture(
            str(assets["accent"]),
            Inches(11.1),
            Inches(6.35),
            width=Inches(1.8),
        )


def _footer(slide, spec: DeckSpec, index: int, total: int) -> None:
    if spec.author:
        _text(
            slide,
            CONTENT_LEFT,
            Inches(7.04),
            Inches(7.0),
            Inches(0.3),
            spec.author,
            size=9,
            color=spec.palette.muted,
            font=spec.font,
        )
    _text(
        slide,
        Inches(11.2),
        Inches(7.04),
        Inches(1.5),
        Inches(0.3),
        f"{index} / {total}",
        size=9,
        color=spec.palette.muted,
        font=spec.font,
        align=PP_ALIGN.RIGHT,
    )


def _content_header(
    slide,
    spec: DeckSpec,
    slide_spec,
    assets: dict[str, Path],
    index: int,
    total: int,
) -> None:
    _background(slide, assets)
    _text(
        slide,
        Inches(0.9),
        Inches(0.45),
        Inches(11.4),
        Inches(0.9),
        slide_spec.title,
        size=30,
        color=spec.palette.text,
        font=spec.font,
        bold=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(0.9),
            Inches(1.38),
            Inches(11.4),
            Inches(0.4),
            slide_spec.subtitle,
            size=13,
            color=spec.palette.muted,
            font=spec.font,
        )
    _footer(slide, spec, index, total)


def _title_slide(slide, spec: DeckSpec, slide_spec, assets) -> None:
    _background(
        slide, assets, brush_width=7.0, brush_y=1.0, accent=False
    )
    slide.shapes.add_picture(
        str(assets["accent"]),
        Inches(10.7),
        Inches(5.9),
        width=Inches(2.1),
    )
    _text(
        slide,
        Inches(0.9),
        Inches(2.35),
        Inches(10.5),
        Inches(1.7),
        slide_spec.title,
        size=40,
        color=spec.palette.text,
        font=spec.font,
        bold=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(0.9),
            Inches(4.2),
            Inches(10.5),
            Inches(0.9),
            slide_spec.subtitle,
            size=20,
            color=spec.palette.muted,
            font=spec.font,
        )
    if spec.author:
        _text(
            slide,
            Inches(0.9),
            Inches(6.2),
            Inches(6.0),
            Inches(0.4),
            spec.author,
            size=14,
            color=spec.palette.muted,
            font=spec.font,
        )


def _section(slide, spec: DeckSpec, slide_spec, assets) -> None:
    _background(slide, assets, brush_width=4.6, brush_y=1.55)
    _text(
        slide,
        Inches(0.9),
        Inches(1.9),
        Inches(10.5),
        Inches(1.0),
        slide_spec.title,
        size=34,
        color=spec.palette.text,
        font=spec.font,
        bold=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(0.9),
            Inches(3.0),
            Inches(10.5),
            Inches(0.8),
            slide_spec.subtitle,
            size=18,
            color=spec.palette.muted,
            font=spec.font,
        )


def _quote(slide, spec: DeckSpec, slide_spec, assets) -> None:
    _background(slide, assets, brush_width=7.0, brush_y=1.0, accent=False)
    _text(
        slide,
        Inches(1.1),
        Inches(1.9),
        Inches(10.5),
        Inches(2.6),
        slide_spec.title,
        size=26,
        color=spec.palette.text,
        font=spec.font,
        italic=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(1.1),
            Inches(4.8),
            Inches(10.5),
            Inches(0.6),
            slide_spec.subtitle,
            size=16,
            color=spec.palette.muted,
            font=spec.font,
        )


def _closing(slide, spec: DeckSpec, slide_spec, assets) -> None:
    _background(slide, assets, brush_width=7.0, brush_y=1.2, accent=False)
    _text(
        slide,
        Inches(0.9),
        Inches(2.6),
        Inches(11.5),
        Inches(1.2),
        slide_spec.title,
        size=44,
        color=spec.palette.text,
        font=spec.font,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(0.9),
            Inches(3.9),
            Inches(11.5),
            Inches(0.8),
            slide_spec.subtitle,
            size=20,
            color=spec.palette.muted,
            font=spec.font,
            align=PP_ALIGN.CENTER,
        )
    if spec.author:
        _text(
            slide,
            Inches(0.9),
            Inches(5.2),
            Inches(11.5),
            Inches(0.5),
            spec.author,
            size=14,
            color=spec.palette.muted,
            font=spec.font,
            align=PP_ALIGN.CENTER,
        )


def _content(
    slide,
    spec: DeckSpec,
    slide_spec,
    assets,
    index: int,
    total: int,
) -> None:
    _content_header(slide, spec, slide_spec, assets, index, total)
    top = _body_top(slide_spec) + Inches(0.15)
    if slide_spec.layout == "bullets":
        _bullets(
            slide,
            slide_spec.bullets,
            CONTENT_LEFT,
            top,
            CONTENT_WIDTH,
            Inches(4.7),
            spec,
        )
    elif slide_spec.layout == "two_column":
        _two_column(slide, spec, slide_spec)
    elif slide_spec.layout == "table":
        _table(slide, spec, slide_spec)


def render_deck_boho(
    spec: DeckSpec,
    meta: TemplateMeta,
    out_path: Path,
) -> Path:
    assets = _asset_paths(meta)
    styled = _styled_spec(spec, meta)

    if assets is None:
        from .render import render_deck

        logger.warning("Thiếu asset boho trong %s, dùng flat renderer", meta.assets_dir)
        return render_deck(styled, out_path)

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    prs.core_properties.title = styled.title
    if styled.author:
        prs.core_properties.author = styled.author

    blank = prs.slide_layouts[6]
    total = len(styled.slides)

    for index, slide_spec in enumerate(styled.slides, start=1):
        slide = prs.slides.add_slide(blank)
        if slide_spec.layout == "title":
            _title_slide(slide, styled, slide_spec, assets)
        elif slide_spec.layout == "section":
            _section(slide, styled, slide_spec, assets)
        elif slide_spec.layout == "quote":
            _quote(slide, styled, slide_spec, assets)
        elif slide_spec.layout == "closing":
            _closing(slide, styled, slide_spec, assets)
        else:
            _content(slide, styled, slide_spec, assets, index, total)
        if slide_spec.note:
            slide.notes_slide.notes_text_frame.text = slide_spec.note

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
