# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from .schema import BulletItem, Column, DeckSpec, SlideSpec, TableBlock

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

HEADER_X = Inches(0.6)
HEADER_Y = Inches(0.45)
HEADER_W = Inches(12.13)
HEADER_H = Inches(0.95)
CONTENT_TOP = Inches(1.7)
CONTENT_TOP_WITH_SUBTITLE = Inches(2.0)
CONTENT_BOTTOM = Inches(7.0)
CONTENT_LEFT = Inches(0.8)
CONTENT_WIDTH = Inches(11.7)


def _rgb(value: str) -> RGBColor:
    raw = value.lstrip("#")
    return RGBColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _channels(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _hex(channels: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, c)) for c in channels))


def _shade(value: str, factor: float) -> str:
    return _hex(tuple(int(c * factor) for c in _channels(value)))


def _mix(first: str, second: str, ratio: float) -> str:
    a = _channels(first)
    b = _channels(second)
    return _hex(tuple(int(x + (y - x) * ratio) for x, y in zip(a, b)))


def _rect(slide, x, y, w, h, fill: str, *, rounded: bool = False, line: str | None = None):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    if line:
        shape.line.color.rgb = _rgb(line)
        shape.line.width = Pt(0.75)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    if rounded:
        shape.adjustments[0] = 0.08
    return shape


def _text(
    slide,
    x,
    y,
    w,
    h,
    text: str,
    *,
    size: int,
    color: str,
    font: str,
    bold: bool = False,
    italic: bool = False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = Inches(0.05)
    frame.margin_right = Inches(0.05)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)

    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run_font = run.font
    run_font.name = font
    run_font.size = Pt(size)
    run_font.bold = bold
    run_font.italic = italic
    run_font.color.rgb = _rgb(color)
    return box


def _title_size(text: str) -> int:
    length = len(text)
    if length <= 34:
        return 30
    if length <= 52:
        return 26
    if length <= 72:
        return 22
    return 19


def _body_top(slide_spec: SlideSpec):
    return CONTENT_TOP_WITH_SUBTITLE if slide_spec.subtitle else CONTENT_TOP


def _header(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    _rect(
        slide,
        HEADER_X + Inches(0.07),
        HEADER_Y + Inches(0.07),
        HEADER_W,
        HEADER_H,
        _shade(palette.primary, 0.72),
        rounded=True,
    )
    _rect(slide, HEADER_X, HEADER_Y, HEADER_W, HEADER_H, palette.primary, rounded=True)
    _rect(slide, HEADER_X, HEADER_Y, Inches(0.16), HEADER_H, palette.accent)
    _text(
        slide,
        HEADER_X + Inches(0.34),
        HEADER_Y,
        HEADER_W - Inches(0.5),
        HEADER_H,
        slide_spec.title,
        size=_title_size(slide_spec.title),
        color="#FFFFFF",
        font=spec.font,
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def _footer(slide, spec: DeckSpec, index: int, total: int) -> None:
    palette = spec.palette
    if spec.author:
        _text(
            slide,
            CONTENT_LEFT,
            Inches(7.04),
            Inches(7.0),
            Inches(0.32),
            spec.author,
            size=9,
            color=palette.muted,
            font=spec.font,
        )
    _text(
        slide,
        Inches(11.2),
        Inches(7.04),
        Inches(1.53),
        Inches(0.32),
        f"{index} / {total}",
        size=9,
        color=palette.muted,
        font=spec.font,
        align=PP_ALIGN.RIGHT,
    )


def _bullets(
    slide,
    items: list[BulletItem],
    x,
    y,
    w,
    h,
    spec: DeckSpec,
) -> None:
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.05)
    frame.margin_right = Inches(0.05)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)

    for position, item in enumerate(items):
        paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
        paragraph.level = item.level
        paragraph.space_after = Pt(6)
        prefix = "•  " if item.level == 0 else "–  "
        run = paragraph.add_run()
        run.text = prefix + item.text
        run_font = run.font
        run_font.name = spec.font
        run_font.size = Pt(20 if item.level == 0 else 16)
        run_font.bold = item.level == 0
        run_font.color.rgb = _rgb(
            spec.palette.primary if item.level == 0 else spec.palette.text
        )


def _two_column(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    top = _body_top(slide_spec)
    width = Inches(5.72)
    gap = Inches(0.3)
    positions = (CONTENT_LEFT, CONTENT_LEFT + width + gap)

    for column, x in zip(slide_spec.columns, positions):
        _rect(
            slide,
            x,
            top,
            width,
            Inches(4.7),
            _mix(palette.background, palette.accent, 0.06),
            rounded=True,
            line=_shade(palette.muted, 1.25),
        )
        if column.heading:
            _text(
                slide,
                x + Inches(0.2),
                top + Inches(0.15),
                width - Inches(0.4),
                Inches(0.5),
                column.heading,
                size=17,
                color=palette.accent,
                font=spec.font,
                bold=True,
            )
        _bullets(
            slide,
            column.bullets,
            x + Inches(0.2),
            top + Inches(0.75),
            width - Inches(0.4),
            Inches(3.75),
            spec,
        )


def _table(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    block = slide_spec.table
    if block is None:
        return

    top = _body_top(slide_spec) + Inches(0.1)
    rows = len(block.rows) + 1
    cols = len(block.headers)
    height = min(Inches(4.6), Inches(0.5 * rows + 0.2))
    shape = slide.shapes.add_table(rows, cols, CONTENT_LEFT, top, CONTENT_WIDTH, height)
    table = shape.table

    base_width = int(CONTENT_WIDTH / cols)
    for index in range(cols):
        table.columns[index].width = base_width

    for row_index in range(rows):
        table.rows[row_index].height = Inches(0.5)
        for col_index in range(cols):
            cell = table.cell(row_index, col_index)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)

            value = (
                block.headers[col_index]
                if row_index == 0
                else block.rows[row_index - 1][col_index]
            )
            cell.text = ""
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT
            run = paragraph.add_run()
            run.text = value
            run_font = run.font
            run_font.name = spec.font
            run_font.size = Pt(14 if row_index == 0 else 13)
            run_font.bold = row_index == 0
            run_font.color.rgb = _rgb("#FFFFFF" if row_index == 0 else palette.text)

            cell.fill.solid()
            if row_index == 0:
                cell.fill.fore_color.rgb = _rgb(palette.primary)
            elif row_index % 2 == 1:
                cell.fill.fore_color.rgb = _rgb(palette.background)
            else:
                cell.fill.fore_color.rgb = _rgb(
                    _mix(palette.background, palette.primary, 0.06)
                )


def _title_slide(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    _rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, palette.primary)
    _rect(slide, Inches(0.9), Inches(2.35), Inches(1.6), Inches(0.12), palette.accent)
    _text(
        slide,
        Inches(0.9),
        Inches(2.7),
        Inches(11.5),
        Inches(1.6),
        slide_spec.title,
        size=40,
        color="#FFFFFF",
        font=spec.font,
        bold=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(0.9),
            Inches(4.45),
            Inches(11.5),
            Inches(0.9),
            slide_spec.subtitle,
            size=20,
            color=_shade(palette.background, 0.88),
            font=spec.font,
        )
    if spec.author:
        _text(
            slide,
            Inches(0.9),
            Inches(6.35),
            Inches(6.0),
            Inches(0.4),
            spec.author,
            size=14,
            color=_shade(palette.background, 0.7),
            font=spec.font,
        )


def _section(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    _rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, palette.background)
    _rect(slide, 0, 0, Inches(0.35), SLIDE_HEIGHT, palette.accent)
    _text(
        slide,
        Inches(1.0),
        Inches(2.1),
        Inches(2.0),
        Inches(1.3),
        "§",
        size=72,
        color=palette.accent,
        font=spec.font,
        bold=True,
    )
    _text(
        slide,
        Inches(1.0),
        Inches(3.4),
        Inches(11.0),
        Inches(1.0),
        slide_spec.title,
        size=36,
        color=palette.primary,
        font=spec.font,
        bold=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(1.0),
            Inches(4.55),
            Inches(11.0),
            Inches(0.8),
            slide_spec.subtitle,
            size=18,
            color=palette.text,
            font=spec.font,
        )


def _quote(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    _rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, palette.background)
    _text(
        slide,
        Inches(0.8),
        Inches(0.5),
        Inches(2.0),
        Inches(1.5),
        "“",
        size=120,
        color=palette.accent,
        font=spec.font,
        bold=True,
    )
    _text(
        slide,
        Inches(1.2),
        Inches(2.1),
        Inches(11.0),
        Inches(2.6),
        slide_spec.title,
        size=26,
        color=palette.primary,
        font=spec.font,
        italic=True,
    )
    if slide_spec.subtitle:
        _text(
            slide,
            Inches(1.2),
            Inches(4.95),
            Inches(11.0),
            Inches(0.6),
            slide_spec.subtitle,
            size=16,
            color=palette.muted,
            font=spec.font,
        )


def _closing(slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    palette = spec.palette
    _rect(slide, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT, palette.primary)
    _text(
        slide,
        Inches(0.9),
        Inches(2.6),
        Inches(11.5),
        Inches(1.2),
        slide_spec.title,
        size=44,
        color="#FFFFFF",
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
            color=_shade(palette.background, 0.85),
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
            color=_shade(palette.background, 0.7),
            font=spec.font,
            align=PP_ALIGN.CENTER,
        )


def render_deck(spec: DeckSpec, out_path: Path) -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    prs.core_properties.title = spec.title
    if spec.author:
        prs.core_properties.author = spec.author

    blank_layout = prs.slide_layouts[6]
    total = len(spec.slides)

    for index, slide_spec in enumerate(spec.slides, start=1):
        slide = prs.slides.add_slide(blank_layout)

        if slide_spec.layout == "title":
            _title_slide(slide, spec, slide_spec)
        elif slide_spec.layout == "section":
            _section(slide, spec, slide_spec)
        elif slide_spec.layout == "quote":
            _quote(slide, spec, slide_spec)
        elif slide_spec.layout == "closing":
            _closing(slide, spec, slide_spec)
        else:
            _header(slide, spec, slide_spec)
            if slide_spec.subtitle:
                _text(
                    slide,
                    CONTENT_LEFT,
                    Inches(1.48),
                    CONTENT_WIDTH,
                    Inches(0.35),
                    slide_spec.subtitle,
                    size=13,
                    color=spec.palette.muted,
                    font=spec.font,
                )
            if slide_spec.layout == "bullets":
                _bullets(
                    slide,
                    slide_spec.bullets,
                    CONTENT_LEFT,
                    _body_top(slide_spec),
                    CONTENT_WIDTH,
                    Inches(5.1),
                    spec,
                )
            elif slide_spec.layout == "two_column":
                _two_column(slide, spec, slide_spec)
            elif slide_spec.layout == "table":
                _table(slide, spec, slide_spec)
            _footer(slide, spec, index, total)

        if slide_spec.note:
            slide.notes_slide.notes_text_frame.text = slide_spec.note

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
