# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from .schema import DeckSpec, SlideSpec

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def _rgb(values: Any) -> RGBColor:
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
    bullet: bool = False,
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
        paragraph.text = ("•  " if bullet else "") + line
        paragraph.space_after = Pt(5)
        for run in paragraph.runs:
            run.font.name = font
            run.font.size = Pt(size)
            run.font.color.rgb = color
    return box


def _bg(slide, color: RGBColor) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _rect(slide, x, y, w, h, color: RGBColor, shape=MSO_SHAPE.RECTANGLE):
    box = slide.shapes.add_shape(shape, x, y, w, h)
    box.fill.solid()
    box.fill.fore_color.rgb = color
    box.line.fill.background()
    box.shadow.inherit = False
    return box


def _card(
    slide,
    x,
    y,
    w,
    h,
    fill: RGBColor,
    border: RGBColor,
    accent: RGBColor,
    *,
    radius: float = 0.06,
    bar: bool = True,
):
    box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h
    )
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    box.line.color.rgb = border
    box.line.width = Pt(1)
    box.shadow.inherit = False
    box.adjustments[0] = radius
    if bar:
        bar_shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, x, y, w, Inches(0.08)
        )
        bar_shape.fill.solid()
        bar_shape.fill.fore_color.rgb = accent
        bar_shape.line.fill.background()
        bar_shape.shadow.inherit = False
    return box


def _footer(slide, spec: DeckSpec, index: int, total: int, muted: RGBColor):
    if spec.author:
        _text(
            slide,
            Inches(0.8),
            Inches(7.08),
            Inches(6.0),
            Inches(0.25),
            spec.author,
            size=9,
            color=muted,
        )
    _text(
        slide,
        Inches(11.5),
        Inches(7.08),
        Inches(1.2),
        Inches(0.25),
        f"{index} / {total}",
        size=9,
        color=muted,
        align=PP_ALIGN.RIGHT,
    )


def _theme_colors(theme: dict) -> dict[str, RGBColor]:
    colors = theme["colors"]
    return {
        "bg": _rgb(colors["background"]["rgb"]),
        "card": _rgb(colors["card"]["bg_rgb"]),
        "border": _rgb(colors["card"]["border_rgb"]),
        "accent": _rgb(colors["accent"]["primary_rgb"]),
        "accent2": _rgb(colors["accent"]["secondary_rgb"]),
        "success": _rgb(colors["accent"]["success_rgb"]),
        "text": _rgb(colors["text"]["primary_rgb"]),
        "muted": _rgb(colors["text"]["secondary_rgb"]),
    }


def _title_layout(theme: dict) -> str:
    return str(theme.get("theme", {}).get("title_layout", "center_card"))


def _content_layout(theme: dict) -> str:
    return str(theme.get("theme", {}).get("content_layout", "three_cards"))


def _header_layout(theme: dict) -> str:
    return str(theme.get("theme", {}).get("header_layout", "left"))


def _font_size(theme: dict, key: str, default: int) -> int:
    try:
        return int(theme["typography"][key]["size_pt"])
    except Exception:
        return default


def _bullet_texts(slide_spec: SlideSpec) -> list[str]:
    if slide_spec.layout == "two_column" and slide_spec.columns:
        result = []
        for column in slide_spec.columns:
            if column.heading:
                result.append(column.heading)
            result.extend(bullet.text for bullet in column.bullets)
        return result
    return [bullet.text for bullet in slide_spec.bullets]


def _groups(slide_spec: SlideSpec, count: int) -> list[list[str]]:
    if slide_spec.layout == "two_column" and slide_spec.columns:
        groups = [
            [bullet.text for bullet in column.bullets]
            for column in slide_spec.columns
        ]
        while len(groups) < count:
            groups.append([])
        return groups[:count]

    texts = [bullet.text for bullet in slide_spec.bullets]
    if not texts:
        return [[] for _ in range(count)]
    size = max(1, (len(texts) + count - 1) // count)
    return [texts[index * size : (index + 1) * size] for index in range(count)]


# ---------------------------------------------------------------- title layouts


def _title_center_card(slide, theme, spec, slide_spec, index, total):
    c = _theme_colors(theme)
    _bg(slide, c["bg"])
    _card(
        slide,
        Inches(1.6),
        Inches(1.45),
        Inches(10.13),
        Inches(4.6),
        c["card"],
        c["border"],
        c["accent"],
        radius=0.05,
    )
    _text(
        slide,
        Inches(2.2),
        Inches(2.0),
        Inches(8.9),
        Inches(0.4),
        "BÁO CÁO",
        size=_font_size(theme, "tag", 10),
        color=c["accent"],
        bold=True,
    )
    _text(
        slide,
        Inches(2.2),
        Inches(2.55),
        Inches(8.9),
        Inches(1.8),
        slide_spec.title,
        size=_font_size(theme, "title_hero", 44),
        color=c["text"],
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    subtitle = slide_spec.subtitle or spec.subtitle or spec.author or ""
    if subtitle:
        _text(
            slide,
            Inches(2.2),
            Inches(4.55),
            Inches(8.9),
            Inches(0.9),
            subtitle,
            size=_font_size(theme, "card_body", 13),
            color=c["muted"],
        )
    _footer(slide, spec, index, total, c["muted"])


def _title_left_rule(slide, theme, spec, slide_spec, index, total):
    c = _theme_colors(theme)
    _bg(slide, c["bg"])
    _rect(slide, 0, 0, Inches(0.28), SLIDE_HEIGHT, c["accent"])
    _text(
        slide,
        Inches(0.9),
        Inches(1.35),
        Inches(0.6),
        Inches(0.4),
        "01",
        size=12,
        color=c["accent"],
        bold=True,
    )
    _text(
        slide,
        Inches(1.5),
        Inches(1.2),
        Inches(10.8),
        Inches(1.9),
        slide_spec.title,
        size=_font_size(theme, "title_hero", 52),
        color=c["text"],
        bold=True,
    )
    _rect(
        slide,
        Inches(1.5),
        Inches(3.25),
        Inches(3.2),
        Inches(0.06),
        c["accent"],
    )
    subtitle = slide_spec.subtitle or spec.subtitle or spec.author or ""
    if subtitle:
        _text(
            slide,
            Inches(1.5),
            Inches(3.55),
            Inches(9.5),
            Inches(1.2),
            subtitle,
            size=_font_size(theme, "card_body", 15),
            color=c["muted"],
        )
    _footer(slide, spec, index, total, c["muted"])


def _title_top_band(slide, theme, spec, slide_spec, index, total):
    c = _theme_colors(theme)
    _bg(slide, c["bg"])
    _rect(slide, 0, 0, SLIDE_WIDTH, Inches(2.35), c["text"])
    _text(
        slide,
        Inches(0.9),
        Inches(0.45),
        Inches(11.5),
        Inches(0.4),
        "BÁO CÁO / PRESENTATION",
        size=10,
        color=c["accent2"],
        bold=True,
    )
    _text(
        slide,
        Inches(0.9),
        Inches(0.95),
        Inches(11.5),
        Inches(1.1),
        slide_spec.title,
        size=_font_size(theme, "title_hero", 42),
        color=c["bg"],
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    subtitle = slide_spec.subtitle or spec.subtitle or spec.author or ""
    if subtitle:
        _text(
            slide,
            Inches(0.9),
            Inches(3.0),
            Inches(9.5),
            Inches(1.2),
            subtitle,
            size=_font_size(theme, "card_body", 16),
            color=c["muted"],
        )
    _rect(
        slide,
        Inches(0.9),
        Inches(4.6),
        Inches(2.4),
        Inches(0.07),
        c["accent"],
    )
    _footer(slide, spec, index, total, c["muted"])


def _title_split_panel(slide, theme, spec, slide_spec, index, total):
    c = _theme_colors(theme)
    _bg(slide, c["bg"])
    _rect(slide, 0, 0, Inches(5.1), SLIDE_HEIGHT, c["text"])
    _rect(slide, Inches(5.1), 0, Inches(0.12), SLIDE_HEIGHT, c["accent"])
    _text(
        slide,
        Inches(0.8),
        Inches(1.2),
        Inches(3.6),
        Inches(0.4),
        "DECK",
        size=12,
        color=c["accent2"],
        bold=True,
    )
    _text(
        slide,
        Inches(0.8),
        Inches(1.8),
        Inches(3.8),
        Inches(3.6),
        slide_spec.title,
        size=_font_size(theme, "title_hero", 40),
        color=c["bg"],
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    subtitle = slide_spec.subtitle or spec.subtitle or spec.author or ""
    if subtitle:
        _text(
            slide,
            Inches(5.8),
            Inches(2.2),
            Inches(6.6),
            Inches(1.6),
            subtitle,
            size=_font_size(theme, "title_section", 24),
            color=c["text"],
            bold=True,
        )
    _footer(slide, spec, index, total, c["muted"])


def _title_full_bleed(slide, theme, spec, slide_spec, index, total):
    c = _theme_colors(theme)
    _bg(slide, c["text"])
    _rect(slide, 0, 0, SLIDE_WIDTH, Inches(0.18), c["accent"])
    _text(
        slide,
        Inches(1.1),
        Inches(2.1),
        Inches(11.1),
        Inches(2.0),
        slide_spec.title,
        size=_font_size(theme, "title_hero", 58),
        color=c["bg"],
        bold=True,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    subtitle = slide_spec.subtitle or spec.subtitle or spec.author or ""
    if subtitle:
        _text(
            slide,
            Inches(1.6),
            Inches(4.35),
            Inches(10.1),
            Inches(1.0),
            subtitle,
            size=_font_size(theme, "card_body", 16),
            color=c["muted"],
            align=PP_ALIGN.CENTER,
        )
    _rect(
        slide,
        Inches(5.9),
        Inches(5.55),
        Inches(1.5),
        Inches(0.06),
        c["accent"],
    )
    _footer(slide, spec, index, total, c["muted"])


TITLE_LAYOUTS = {
    "center_card": _title_center_card,
    "left_rule": _title_left_rule,
    "top_band": _title_top_band,
    "split_panel": _title_split_panel,
    "full_bleed": _title_full_bleed,
}


# -------------------------------------------------------------- content layouts


def _content_header(slide, theme, spec, slide_spec, index, total):
    c = _theme_colors(theme)
    _bg(slide, c["bg"])
    style = _header_layout(theme)
    size = _font_size(theme, "title_section", 28)

    if style == "center":
        _text(
            slide,
            Inches(0.9),
            Inches(0.55),
            Inches(11.5),
            Inches(0.8),
            slide_spec.title,
            size=size,
            color=c["text"],
            bold=True,
            align=PP_ALIGN.CENTER,
        )
        _rect(slide, Inches(5.9), Inches(1.35), Inches(1.5), Inches(0.06), c["accent"])
    elif style == "band":
        _rect(slide, 0, 0, SLIDE_WIDTH, Inches(1.35), c["text"])
        _text(
            slide,
            Inches(0.9),
            Inches(0.35),
            Inches(11.5),
            Inches(0.75),
            slide_spec.title,
            size=size,
            color=c["bg"],
            bold=True,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        _rect(slide, 0, Inches(1.35), SLIDE_WIDTH, Inches(0.06), c["accent"])
    elif style == "rail":
        _rect(slide, 0, 0, Inches(0.18), Inches(1.6), c["accent"])
        _text(
            slide,
            Inches(0.55),
            Inches(0.55),
            Inches(11.8),
            Inches(0.8),
            slide_spec.title,
            size=size,
            color=c["text"],
            bold=True,
        )
    elif style == "badge":
        _rect(slide, Inches(0.9), Inches(0.55), Inches(0.12), Inches(0.75), c["accent"])
        _text(
            slide,
            Inches(1.2),
            Inches(0.55),
            Inches(11.0),
            Inches(0.8),
            slide_spec.title,
            size=size,
            color=c["text"],
            bold=True,
        )
    elif style == "grid":
        _rect(slide, Inches(0.85), Inches(0.45), Inches(11.6), Inches(0.95), c["border"], MSO_SHAPE.RECTANGLE)
        _text(
            slide,
            Inches(1.05),
            Inches(0.55),
            Inches(11.2),
            Inches(0.75),
            slide_spec.title,
            size=size,
            color=c["text"],
            bold=True,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        _rect(slide, Inches(0.85), Inches(0.45), Inches(0.18), Inches(0.18), c["accent"])
    else:
        _text(
            slide,
            Inches(0.9),
            Inches(0.55),
            Inches(11.5),
            Inches(0.8),
            slide_spec.title,
            size=size,
            color=c["text"],
            bold=True,
        )
        _rect(slide, Inches(0.9), Inches(1.35), Inches(1.5), Inches(0.06), c["accent"])

    _footer(slide, spec, index, total, c["muted"])
    return c


def _content_three_cards(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 3)
    width = Inches(3.55)
    gap = Inches(0.35)
    left = Inches(0.9)
    for index_card, texts in enumerate(groups):
        x = left + index_card * (width + gap)
        _card(
            slide,
            x,
            Inches(1.85),
            width,
            Inches(4.6),
            c["card"],
            c["border"],
            [c["accent"], c["accent2"], c["success"]][index_card % 3],
        )
        _text(
            slide,
            x + Inches(0.25),
            Inches(2.15),
            width - Inches(0.5),
            Inches(0.35),
            f"0{index_card + 1}",
            size=11,
            color=c["accent"],
            bold=True,
        )
        _multi_text(
            slide,
            x + Inches(0.25),
            Inches(2.6),
            width - Inches(0.5),
            Inches(3.5),
            texts,
            size=_font_size(theme, "card_body", 13),
            color=c["text"],
            bullet=True,
        )


def _content_two_column_text(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 2)
    for column, texts in enumerate(groups):
        x = Inches(0.9) + column * Inches(6.0)
        _rect(
            slide,
            x,
            Inches(1.9),
            Inches(5.45),
            Inches(0.03),
            c["border"],
        )
        _multi_text(
            slide,
            x,
            Inches(2.15),
            Inches(5.45),
            Inches(4.4),
            texts,
            size=_font_size(theme, "card_body", 15),
            color=c["text"],
            bullet=True,
        )


def _content_timeline(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 3)
    y = Inches(2.3)
    _rect(slide, Inches(1.1), y + Inches(0.55), Inches(11.1), Inches(0.05), c["accent"])
    for index_card, texts in enumerate(groups):
        x = Inches(1.0) + index_card * Inches(3.85)
        _rect(
            slide,
            x + Inches(1.55),
            y + Inches(0.3),
            Inches(0.55),
            Inches(0.55),
            c["accent"],
            MSO_SHAPE.OVAL,
        )
        _text(
            slide,
            x + Inches(1.55),
            y + Inches(0.36),
            Inches(0.55),
            Inches(0.4),
            str(index_card + 1),
            size=12,
            color=c["bg"],
            bold=True,
            align=PP_ALIGN.CENTER,
        )
        _text(
            slide,
            x,
            y + Inches(1.05),
            Inches(3.6),
            Inches(0.5),
            texts[0] if texts else "",
            size=_font_size(theme, "card_title", 17),
            color=c["text"],
            bold=True,
            align=PP_ALIGN.CENTER,
        )
        _multi_text(
            slide,
            x,
            y + Inches(1.65),
            Inches(3.6),
            Inches(2.4),
            texts[1:],
            size=_font_size(theme, "card_body", 12),
            color=c["muted"],
            bullet=True,
        )


def _content_heading_rail(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    _rect(slide, 0, Inches(1.6), Inches(0.18), Inches(5.0), c["accent"])
    _text(
        slide,
        Inches(0.6),
        Inches(1.9),
        Inches(3.0),
        Inches(0.4),
        "NỘI DUNG",
        size=11,
        color=c["accent"],
        bold=True,
    )
    _text(
        slide,
        Inches(0.6),
        Inches(2.35),
        Inches(3.2),
        Inches(3.4),
        slide_spec.title,
        size=_font_size(theme, "title_section", 24),
        color=c["text"],
        bold=True,
    )
    texts = _bullet_texts(slide_spec)
    _multi_text(
        slide,
        Inches(4.4),
        Inches(1.9),
        Inches(7.9),
        Inches(4.6),
        texts,
        size=_font_size(theme, "card_body", 14),
        color=c["text"],
        bullet=True,
    )


def _content_magazine(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 2)
    for column, texts in enumerate(groups):
        x = Inches(0.9) + column * Inches(6.0)
        _multi_text(
            slide,
            x,
            Inches(1.85),
            Inches(5.45),
            Inches(4.7),
            texts,
            size=_font_size(theme, "card_body", 13),
            color=c["text"],
            bullet=True,
        )
    _rect(slide, Inches(6.55), Inches(1.9), Inches(0.04), Inches(4.4), c["border"])


def _content_centered_list(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    texts = _bullet_texts(slide_spec)
    _multi_text(
        slide,
        Inches(1.8),
        Inches(1.9),
        Inches(9.7),
        Inches(4.5),
        texts,
        size=_font_size(theme, "card_body", 16),
        color=c["text"],
        bullet=True,
    )


def _content_stacked_bands(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    texts = _bullet_texts(slide_spec)[:5]
    top = Inches(1.85)
    height = Inches(0.85)
    for row, text in enumerate(texts):
        y = top + row * (height + Inches(0.12))
        _rect(
            slide,
            Inches(0.9),
            y,
            Inches(11.5),
            height,
            c["card"] if row % 2 == 0 else c["border"],
        )
        _text(
            slide,
            Inches(1.15),
            y + Inches(0.12),
            Inches(0.5),
            Inches(0.5),
            str(row + 1),
            size=14,
            color=c["accent"],
            bold=True,
        )
        _text(
            slide,
            Inches(1.75),
            y + Inches(0.16),
            Inches(10.3),
            height - Inches(0.3),
            text,
            size=_font_size(theme, "card_body", 14),
            color=c["text"],
            anchor=MSO_ANCHOR.MIDDLE,
        )


def _content_glass_grid(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    texts = _bullet_texts(slide_spec)
    cells = _groups(slide_spec, 4)
    for index_card, cell in enumerate(cells):
        row, col = divmod(index_card, 2)
        x = Inches(0.9) + col * Inches(5.85)
        y = Inches(1.85) + row * Inches(2.35)
        _card(
            slide,
            x,
            y,
            Inches(5.55),
            Inches(2.1),
            c["card"],
            c["border"],
            c["accent"] if index_card % 2 == 0 else c["accent2"],
            radius=0.12,
        )
        _multi_text(
            slide,
            x + Inches(0.25),
            y + Inches(0.25),
            Inches(5.05),
            Inches(1.65),
            cell or texts[:1],
            size=_font_size(theme, "card_body", 13),
            color=c["text"],
            bullet=True,
        )


def _content_numbered_bands(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    texts = _bullet_texts(slide_spec)[:4]
    for row, text in enumerate(texts):
        y = Inches(1.85) + row * Inches(1.2)
        _text(
            slide,
            Inches(0.9),
            y,
            Inches(0.9),
            Inches(0.9),
            f"0{row + 1}",
            size=28,
            color=c["accent"],
            bold=True,
        )
        _rect(slide, Inches(1.9), y + Inches(0.1), Inches(0.04), Inches(0.7), c["border"])
        _text(
            slide,
            Inches(2.15),
            y + Inches(0.08),
            Inches(10.2),
            Inches(0.8),
            text,
            size=_font_size(theme, "card_body", 15),
            color=c["text"],
            anchor=MSO_ANCHOR.MIDDLE,
        )


def _content_single_column(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    texts = _bullet_texts(slide_spec)
    _multi_text(
        slide,
        Inches(0.9),
        Inches(1.9),
        Inches(11.5),
        Inches(4.6),
        texts,
        size=_font_size(theme, "card_body", 15),
        color=c["text"],
        bullet=True,
    )


def _content_compact_cards(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 3)
    for index_card, texts in enumerate(groups):
        x = Inches(0.9) + index_card * Inches(3.95)
        _rect(
            slide,
            x,
            Inches(1.9),
            Inches(0.55),
            Inches(0.55),
            [c["accent"], c["accent2"], c["success"]][index_card % 3],
        )
        _text(
            slide,
            x,
            Inches(2.6),
            Inches(3.6),
            Inches(0.5),
            texts[0] if texts else "",
            size=_font_size(theme, "card_title", 17),
            color=c["text"],
            bold=True,
        )
        _multi_text(
            slide,
            x,
            Inches(3.15),
            Inches(3.6),
            Inches(2.7),
            texts[1:],
            size=_font_size(theme, "card_body", 12),
            color=c["muted"],
            bullet=True,
        )


def _content_two_column_lists(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 2)
    for column, texts in enumerate(groups):
        x = Inches(0.9) + column * Inches(6.0)
        _rect(slide, x, Inches(1.9), Inches(5.45), Inches(0.03), c["border"])
        _multi_text(
            slide,
            x,
            Inches(2.15),
            Inches(5.45),
            Inches(4.4),
            texts,
            size=_font_size(theme, "card_body", 14),
            color=c["text"],
            bullet=True,
        )


def _content_grid_2x2(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    cells = _groups(slide_spec, 4)
    for index_card, cell in enumerate(cells):
        row, col = divmod(index_card, 2)
        x = Inches(0.9) + col * Inches(5.85)
        y = Inches(1.85) + row * Inches(2.35)
        _rect(
            slide,
            x,
            y,
            Inches(5.55),
            Inches(2.1),
            c["card"],
        )
        _rect(slide, x, y, Inches(5.55), Inches(0.06), c["accent"])
        _multi_text(
            slide,
            x + Inches(0.25),
            y + Inches(0.25),
            Inches(5.05),
            Inches(1.65),
            cell,
            size=_font_size(theme, "card_body", 13),
            color=c["text"],
            bullet=True,
        )


def _content_rounded_cards(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 3)
    for index_card, texts in enumerate(groups):
        x = Inches(0.9) + index_card * Inches(3.95)
        _card(
            slide,
            x,
            Inches(1.85),
            Inches(3.6),
            Inches(4.6),
            c["card"],
            c["border"],
            [c["accent"], c["accent2"], c["success"]][index_card % 3],
            radius=0.18,
        )
        _text(
            slide,
            x + Inches(0.25),
            Inches(2.15),
            Inches(3.1),
            Inches(0.8),
            f"0{index_card + 1}",
            size=30,
            color=c["accent"],
            bold=True,
        )
        _multi_text(
            slide,
            x + Inches(0.25),
            Inches(3.05),
            Inches(3.1),
            Inches(3.1),
            texts,
            size=_font_size(theme, "card_body", 13),
            color=c["text"],
            bullet=True,
        )


def _content_metric_tiles(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    groups = _groups(slide_spec, 4)
    for index_card, texts in enumerate(groups):
        x = Inches(0.9) + index_card * Inches(2.95)
        _rect(slide, x, Inches(1.9), Inches(2.7), Inches(2.3), c["card"])
        _text(
            slide,
            x + Inches(0.2),
            Inches(2.05),
            Inches(2.3),
            Inches(0.8),
            f"0{index_card + 1}",
            size=28,
            color=c["accent"],
            bold=True,
        )
        _multi_text(
            slide,
            x + Inches(0.2),
            Inches(2.9),
            Inches(2.3),
            Inches(1.1),
            texts[:2],
            size=11,
            color=c["muted"],
            bullet=True,
        )
    _rect(slide, Inches(0.9), Inches(4.5), Inches(11.5), Inches(0.05), c["accent"])


def _content_split_list(slide, theme, spec, slide_spec, index, total):
    c = _content_header(slide, theme, spec, slide_spec, index, total)
    texts = _bullet_texts(slide_spec)
    _text(
        slide,
        Inches(0.9),
        Inches(1.9),
        Inches(3.4),
        Inches(1.4),
        "01",
        size=72,
        color=c["accent"],
        bold=True,
    )
    _rect(
        slide,
        Inches(0.9),
        Inches(3.35),
        Inches(2.8),
        Inches(0.06),
        c["border"],
    )
    _multi_text(
        slide,
        Inches(4.8),
        Inches(1.9),
        Inches(7.6),
        Inches(4.6),
        texts,
        size=_font_size(theme, "card_body", 15),
        color=c["text"],
        bullet=True,
    )


CONTENT_LAYOUTS = {
    "three_cards": _content_three_cards,
    "two_column_text": _content_two_column_text,
    "timeline": _content_timeline,
    "heading_rail": _content_heading_rail,
    "magazine": _content_magazine,
    "centered_list": _content_centered_list,
    "stacked_bands": _content_stacked_bands,
    "glass_grid": _content_glass_grid,
    "numbered_bands": _content_numbered_bands,
    "single_column": _content_single_column,
    "compact_cards": _content_compact_cards,
    "two_column_lists": _content_two_column_lists,
    "grid_2x2": _content_grid_2x2,
    "rounded_cards": _content_rounded_cards,
    "metric_tiles": _content_metric_tiles,
    "split_list": _content_split_list,
}


def render_title(slide, theme, spec, slide_spec, index, total):
    layout = _title_layout(theme)
    TITLE_LAYOUTS.get(layout, _title_center_card)(
        slide, theme, spec, slide_spec, index, total
    )


def render_content(slide, theme, spec, slide_spec, index, total):
    layout = _content_layout(theme)
    CONTENT_LAYOUTS.get(layout, _content_three_cards)(
        slide, theme, spec, slide_spec, index, total
    )
