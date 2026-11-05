from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from .schema import DeckSpec, SlideSpec, TableBlock
from .templates_catalog import TemplateMeta, resolve_path

logger = logging.getLogger(__name__)

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def _rgb(values) -> RGBColor:
    return RGBColor(int(values[0]), int(values[1]), int(values[2]))


def _text(
    slide,
    x,
    y,
    w,
    h,
    text: str,
    *,
    size: int,
    color: RGBColor,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    font: str = "Lexend",
):
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = Inches(0.04)
    frame.margin_right = Inches(0.04)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def _multi_text(
    slide,
    x,
    y,
    w,
    h,
    lines: list[str],
    *,
    size: int,
    color: RGBColor,
    font: str = "Lexend",
):
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.04)
    frame.margin_right = Inches(0.04)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    for index, line in enumerate(lines or [""]):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.space_after = Pt(4)
        for run in paragraph.runs:
            run.font.name = font
            run.font.size = Pt(size)
            run.font.color.rgb = color
    return box


def _background(slide, color: RGBColor) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _card(
    slide,
    left,
    top,
    width,
    height,
    fill: RGBColor,
    border: RGBColor,
    accent: RGBColor,
) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = border
    shape.line.width = Pt(1)
    shape.shadow.inherit = False
    shape.adjustments[0] = 0.05

    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, Inches(0.08)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = accent
    bar.line.fill.background()


def _footer(slide, spec: DeckSpec, index: int, total: int, muted: RGBColor) -> None:
    if spec.author:
        _text(
            slide,
            Inches(1.0),
            Inches(7.05),
            Inches(6.0),
            Inches(0.3),
            spec.author,
            size=9,
            color=muted,
        )
    _text(
        slide,
        Inches(11.3),
        Inches(7.05),
        Inches(1.2),
        Inches(0.3),
        f"{index} / {total}",
        size=9,
        color=muted,
        align=PP_ALIGN.RIGHT,
    )


def _fit_hero(text: str, base: int) -> int:
    length = len(text)
    if length <= 45:
        return base
    if length <= 65:
        return 36
    if length <= 85:
        return 30
    return 26


def _fit_card_title(text: str, base: int) -> int:
    length = len(text)
    if length <= 26:
        return base
    if length <= 40:
        return base - 2
    return max(base - 4, 13)


def _hero(
    slide,
    theme,
    spec: DeckSpec,
    index: int,
    total: int,
    tag: str,
    title: str,
    subtitle: str,
) -> None:
    bg = _rgb(theme["colors"]["background"]["rgb"])
    card = _rgb(theme["colors"]["card"]["bg_rgb"])
    border = _rgb(theme["colors"]["card"]["border_rgb"])
    accent = _rgb(theme["colors"]["accent"]["primary_rgb"])
    text_primary = _rgb(theme["colors"]["text"]["primary_rgb"])
    text_secondary = _rgb(theme["colors"]["text"]["secondary_rgb"])
    tag_size = int(theme["typography"]["tag"]["size_pt"])
    hero_size = int(theme["typography"]["title_hero"]["size_pt"])

    _background(slide, bg)
    card_cfg = theme["layouts"]["hero_title"]["card"]
    _card(
        slide,
        Inches(card_cfg["left_inch"]),
        Inches(card_cfg["top_inch"]),
        Inches(card_cfg["width_inch"]),
        Inches(card_cfg["height_inch"]),
        card,
        border,
        accent,
    )

    tag_cfg = theme["layouts"]["hero_title"]["elements"]["tag"]
    _text(
        slide,
        Inches(tag_cfg["left_inch"]),
        Inches(tag_cfg["top_inch"]),
        Inches(tag_cfg["width_inch"]),
        Inches(tag_cfg["height_inch"]),
        tag,
        size=tag_size,
        color=accent,
        bold=True,
    )

    title_cfg = theme["layouts"]["hero_title"]["elements"]["title"]
    _text(
        slide,
        Inches(title_cfg["left_inch"]),
        Inches(title_cfg["top_inch"]),
        Inches(title_cfg["width_inch"]),
        Inches(title_cfg["height_inch"]),
        title,
        size=_fit_hero(title, hero_size),
        color=text_primary,
        bold=True,
    )

    subtitle_cfg = theme["layouts"]["hero_title"]["elements"]["subtitle"]
    _text(
        slide,
        Inches(subtitle_cfg["left_inch"]),
        Inches(subtitle_cfg["top_inch"]),
        Inches(subtitle_cfg["width_inch"]),
        Inches(subtitle_cfg["height_inch"]),
        subtitle,
        size=int(theme["typography"]["card_body"]["size_pt"]),
        color=text_secondary,
    )

    _footer(slide, spec, index, total, text_secondary)


def _card_groups(slide_spec: SlideSpec) -> list[tuple[str, str, list[str]]]:
    if slide_spec.layout == "bullets":
        items = slide_spec.bullets
        if not items:
            return [("01 / Ý CHÍNH", "", [])]
        size = max(1, (len(items) + 2) // 3)
        groups = []
        for start in range(0, len(items), size):
            chunk = items[start : start + size]
            title = chunk[0].text
            body = [
                ("• " if item.level == 0 else "– ") + item.text
                for item in chunk[1:]
            ]
            groups.append((f"{len(groups) + 1:02d} / Ý CHÍNH", title, body))
        while len(groups) < 3:
            groups.append((f"{len(groups) + 1:02d} / Ý CHÍNH", "", []))
        return groups[:3]

    if slide_spec.layout == "two_column":
        groups = []
        for column in slide_spec.columns:
            body = [
                ("• " if item.level == 0 else "– ") + item.text
                for item in column.bullets
            ]
            groups.append(
                (f"{len(groups) + 1:02d} / NỘI DUNG", column.heading or "", body)
            )
        while len(groups) < 3:
            groups.append(
                (
                    f"{len(groups) + 1:02d} / GHI CHÚ",
                    slide_spec.subtitle or "",
                    [],
                )
            )
        return groups[:3]

    return [("01 / NỘI DUNG", slide_spec.title, [])]


def _three_cards(
    slide,
    theme,
    spec: DeckSpec,
    slide_spec: SlideSpec,
    index: int,
    total: int,
) -> None:
    bg = _rgb(theme["colors"]["background"]["rgb"])
    card = _rgb(theme["colors"]["card"]["bg_rgb"])
    border = _rgb(theme["colors"]["card"]["border_rgb"])
    accents = [
        _rgb(theme["colors"]["accent"]["primary_rgb"]),
        _rgb(theme["colors"]["accent"]["secondary_rgb"]),
        _rgb(theme["colors"]["accent"]["success_rgb"]),
    ]
    text_primary = _rgb(theme["colors"]["text"]["primary_rgb"])
    text_secondary = _rgb(theme["colors"]["text"]["secondary_rgb"])
    section_size = int(theme["typography"]["title_section"]["size_pt"])
    card_title_size = int(theme["typography"]["card_title"]["size_pt"])
    card_body_size = int(theme["typography"]["card_body"]["size_pt"])

    _background(slide, bg)
    header = theme["layouts"]["three_cards"]["header"]
    _text(
        slide,
        Inches(header["left_inch"]),
        Inches(header["top_inch"]),
        Inches(header["width_inch"]),
        Inches(header["height_inch"]),
        slide_spec.title,
        size=section_size,
        color=text_primary,
        bold=True,
    )

    groups = _card_groups(slide_spec)
    for position, (badge, title, body) in enumerate(groups, start=1):
        card_cfg = theme["layouts"]["three_cards"][f"card_{position}"]
        left = Inches(card_cfg["left_inch"])
        top = Inches(card_cfg["top_inch"])
        width = Inches(card_cfg["width_inch"])
        height = Inches(card_cfg["height_inch"])
        _card(slide, left, top, width, height, card, border, accents[position - 1])

        _text(
            slide,
            left + Inches(0.25),
            top + Inches(0.25),
            width - Inches(0.5),
            Inches(0.3),
            badge,
            size=int(theme["typography"]["tag"]["size_pt"]),
            color=accents[position - 1],
            bold=True,
        )
        _text(
            slide,
            left + Inches(0.25),
            top + Inches(0.65),
            width - Inches(0.5),
            Inches(0.9),
            title,
            size=_fit_card_title(title, card_title_size),
            color=text_primary,
            bold=True,
        )
        _multi_text(
            slide,
            left + Inches(0.25),
            top + Inches(1.55),
            width - Inches(0.5),
            height - Inches(1.75),
            body,
            size=card_body_size if len(body) <= 4 else card_body_size - 1,
            color=text_secondary,
        )

    _footer(slide, spec, index, total, text_secondary)


def _table_slide(
    slide,
    theme,
    spec: DeckSpec,
    slide_spec: SlideSpec,
    index: int,
    total: int,
) -> None:
    block: TableBlock | None = slide_spec.table
    if block is None:
        return

    bg = _rgb(theme["colors"]["background"]["rgb"])
    card = _rgb(theme["colors"]["card"]["bg_rgb"])
    border = _rgb(theme["colors"]["card"]["border_rgb"])
    accent = _rgb(theme["colors"]["accent"]["primary_rgb"])
    text_primary = _rgb(theme["colors"]["text"]["primary_rgb"])
    text_secondary = _rgb(theme["colors"]["text"]["secondary_rgb"])
    dark = _rgb(theme["colors"]["background"]["rgb"])

    _background(slide, bg)
    header = theme["layouts"]["three_cards"]["header"]
    _text(
        slide,
        Inches(header["left_inch"]),
        Inches(header["top_inch"]),
        Inches(header["width_inch"]),
        Inches(header["height_inch"]),
        slide_spec.title,
        size=int(theme["typography"]["title_section"]["size_pt"]),
        color=text_primary,
        bold=True,
    )

    rows = len(block.rows) + 1
    cols = len(block.headers)
    width = Inches(11.333)
    shape = slide.shapes.add_table(
        rows, cols, Inches(1.0), Inches(2.0), width, Inches(4.6)
    )
    table = shape.table
    col_width = int(width / cols)
    for col in range(cols):
        table.columns[col].width = col_width

    for row in range(rows):
        table.rows[row].height = Inches(0.6)
        for col in range(cols):
            cell = table.cell(row, col)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            value = (
                block.headers[col]
                if row == 0
                else block.rows[row - 1][col]
            )
            cell.text = ""
            paragraph = cell.text_frame.paragraphs[0]
            run = paragraph.add_run()
            run.text = value
            run.font.name = "Lexend"
            run.font.size = Pt(14 if row == 0 else 12)
            run.font.bold = row == 0
            run.font.color.rgb = dark if row == 0 else text_primary
            cell.fill.solid()
            cell.fill.fore_color.rgb = accent if row == 0 else card

    _footer(slide, spec, index, total, text_secondary)


def render_deck_theme(
    spec: DeckSpec,
    meta: TemplateMeta,
    out_path: Path,
) -> Path:
    theme_path = resolve_path(meta.theme_file) if meta.theme_file else None
    if theme_path is None or not theme_path.is_file():
        from .render import render_deck

        logger.warning("Thiếu theme file cho %s, dùng flat renderer", meta.id)
        return render_deck(spec, out_path)

    with theme_path.open("rb") as handle:
        theme = tomllib.load(handle)

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    prs.core_properties.title = spec.title
    if spec.author:
        prs.core_properties.author = spec.author

    blank = prs.slide_layouts[6]
    total = len(spec.slides)

    for index, slide_spec in enumerate(spec.slides, start=1):
        slide = prs.slides.add_slide(blank)
        if slide_spec.layout == "title":
            _hero(
                slide,
                theme,
                spec,
                index,
                total,
                "BÁO CÁO LÂM SÀNG",
                slide_spec.title,
                slide_spec.subtitle or spec.subtitle or spec.author or "",
            )
        elif slide_spec.layout == "section":
            _hero(
                slide,
                theme,
                spec,
                index,
                total,
                "PHẦN",
                slide_spec.title,
                slide_spec.subtitle or "",
            )
        elif slide_spec.layout == "quote":
            _hero(
                slide,
                theme,
                spec,
                index,
                total,
                "TRÍCH DẪN",
                slide_spec.title,
                slide_spec.subtitle or "",
            )
        elif slide_spec.layout == "closing":
            _hero(
                slide,
                theme,
                spec,
                index,
                total,
                "CẢM ƠN",
                slide_spec.title,
                slide_spec.subtitle or spec.author or "",
            )
        elif slide_spec.layout == "table":
            _table_slide(slide, theme, spec, slide_spec, index, total)
        else:
            _three_cards(slide, theme, spec, slide_spec, index, total)

        if slide_spec.note:
            slide.notes_slide.notes_text_frame.text = slide_spec.note

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
