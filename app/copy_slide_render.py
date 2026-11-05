from __future__ import annotations

import copy
import logging
from io import BytesIO
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches, Pt

from .schema import DeckSpec, SlideSpec, TableBlock
from .templates_catalog import TemplateMeta, hex_color, template_file

logger = logging.getLogger(__name__)

SAMPLE_SLIDES = {
    "title": 5,
    "content": 4,
    "two_column": 8,
    "quote": 9,
}

LAYOUT_SAMPLE = {
    "title": "title",
    "section": "content",
    "bullets": "content",
    "two_column": "two_column",
    "table": "content",
    "quote": "quote",
    "closing": "content",
}

SLOTS = {
    "title": {
        "title": "Google Shape;160;p17",
        "subtitle": "Google Shape;161;p17",
    },
    "content": {
        "title": "Google Shape;141;p16",
        "body": "Google Shape;142;p16",
        "number": "Google Shape;143;p16",
    },
    "two_column": {
        "title": "Google Shape;211;p20",
        "col1_heading": "Google Shape;206;p20",
        "col1_body": "Google Shape;205;p20",
        "col2_heading": "Google Shape;208;p20",
        "col2_body": "Google Shape;207;p20",
        "col3_heading": "Google Shape;210;p20",
        "col3_body": "Google Shape;209;p20",
    },
    "quote": {
        "quote": "Google Shape;227;p21",
        "attribution": "Google Shape;228;p21",
    },
}


def _rgb(value: str) -> RGBColor:
    raw = value.lstrip("#")
    return RGBColor(int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _walk(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(shape.shapes)


def _find(slide, name: str):
    for shape in _walk(slide.shapes):
        if shape.name == name:
            return shape
    return None


def _remove(shape) -> None:
    if shape is not None:
        shape.element.getparent().remove(shape.element)


def _copy_shapes(source, target) -> None:
    for shape in source.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            picture = target.shapes.add_picture(
                BytesIO(shape.image.blob),
                shape.left,
                shape.top,
                shape.width,
                shape.height,
            )
            try:
                picture.rotation = shape.rotation
            except Exception:
                pass
        else:
            target.shapes._spTree.append(copy.deepcopy(shape.element))


def _replace_text(
    shape,
    text: str,
    *,
    font: str = "Lexend",
    size=None,
    color: RGBColor | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> None:
    if shape is None:
        return
    frame = shape.text_frame
    alignment = frame.paragraphs[0].alignment if frame.paragraphs else None
    frame.clear()
    lines = text.split("\n") if text else [""]
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        if alignment is not None:
            paragraph.alignment = alignment
        for run in paragraph.runs:
            run.font.name = font
            if size is not None:
                run.font.size = size
            if color is not None:
                run.font.color.rgb = color
            if bold is not None:
                run.font.bold = bold
            if italic is not None:
                run.font.italic = italic


def _bullet_text(bullets) -> str:
    lines = []
    for item in bullets:
        prefix = "• " if item.level == 0 else "– "
        lines.append(prefix + item.text)
    return "\n".join(lines)


def _add_table(
    slide,
    block: TableBlock,
    text_color: RGBColor,
    accent_color: RGBColor,
    background: RGBColor,
) -> None:
    rows = len(block.rows) + 1
    cols = len(block.headers)
    width = Inches(17.6)
    height = min(Inches(6.4), Inches(0.8 * rows + 0.2))
    shape = slide.shapes.add_table(
        rows, cols, Inches(1.2), Inches(3.4), width, height
    )
    table = shape.table
    col_width = int(width / cols)
    for index in range(cols):
        table.columns[index].width = col_width

    for row in range(rows):
        table.rows[row].height = Inches(0.8)
        for col in range(cols):
            cell = table.cell(row, col)
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.06)
            cell.margin_bottom = Inches(0.06)
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
            run.font.size = Pt(18 if row == 0 else 16)
            run.font.bold = row == 0
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if row == 0 else text_color
            cell.fill.solid()
            cell.fill.fore_color.rgb = accent_color if row == 0 else background


def _fill_title(
    slide,
    spec: DeckSpec,
    slide_spec: SlideSpec,
    meta: TemplateMeta,
) -> None:
    text_color = _rgb(hex_color(meta.text_color))
    muted = _rgb(hex_color(meta.muted_color))
    _replace_text(
        _find(slide, SLOTS["title"]["title"]),
        slide_spec.title,
        color=text_color,
        bold=True,
    )
    _replace_text(
        _find(slide, SLOTS["title"]["subtitle"]),
        slide_spec.subtitle or spec.subtitle or "",
        color=muted,
        size=Pt(20),
    )


def _fill_content(
    slide,
    spec: DeckSpec,
    slide_spec: SlideSpec,
    index: int,
    meta: TemplateMeta,
) -> None:
    text_color = _rgb(hex_color(meta.text_color))
    muted = _rgb(hex_color(meta.muted_color))
    accent = _rgb(hex_color(meta.accent_color))

    _replace_text(
        _find(slide, SLOTS["content"]["title"]),
        slide_spec.title,
        color=text_color,
        bold=True,
    )
    number = _find(slide, SLOTS["content"]["number"])
    if number is not None:
        _replace_text(number, f"{index:02d}.", color=accent, bold=True)

    body = _find(slide, SLOTS["content"]["body"])
    if slide_spec.layout == "table" and slide_spec.table is not None:
        _remove(body)
        _add_table(
            slide,
            slide_spec.table,
            text_color=text_color,
            accent_color=accent,
            background=_rgb(hex_color(meta.bg_color)),
        )
        return

    if slide_spec.layout == "bullets":
        text = _bullet_text(slide_spec.bullets)
    elif slide_spec.layout == "section":
        text = slide_spec.subtitle or ""
    elif slide_spec.layout == "closing":
        text = slide_spec.subtitle or spec.author or ""
    else:
        text = slide_spec.subtitle or ""

    _remove(body)
    box = slide.shapes.add_textbox(
        Inches(1.0), Inches(3.3), Inches(17.5), Inches(6.6)
    )
    _replace_text(box, text, color=text_color, size=Pt(18))


def _fill_two_column(
    slide,
    spec: DeckSpec,
    slide_spec: SlideSpec,
    meta: TemplateMeta,
) -> None:
    text_color = _rgb(hex_color(meta.text_color))
    accent = _rgb(hex_color(meta.accent_color))
    slots = SLOTS["two_column"]

    _replace_text(
        _find(slide, slots["title"]),
        slide_spec.title,
        color=text_color,
        bold=True,
    )

    pairs = (
        ("col1_heading", "col1_body"),
        ("col2_heading", "col2_body"),
    )
    for column, (heading_key, body_key) in zip(slide_spec.columns, pairs):
        _replace_text(
            _find(slide, slots[heading_key]),
            column.heading or "",
            color=accent,
            bold=True,
            size=Pt(18),
        )
        body = _find(slide, slots[body_key])
        if body is not None:
            body.height = Inches(4.2)
        _replace_text(
            body,
            _bullet_text(column.bullets),
            color=text_color,
            size=Pt(15),
        )

    _remove(_find(slide, slots["col3_heading"]))
    _remove(_find(slide, slots["col3_body"]))


def _fill_quote(
    slide,
    spec: DeckSpec,
    slide_spec: SlideSpec,
    meta: TemplateMeta,
) -> None:
    text_color = _rgb(hex_color(meta.text_color))
    muted = _rgb(hex_color(meta.muted_color))
    slots = SLOTS["quote"]
    _replace_text(
        _find(slide, slots["quote"]),
        slide_spec.title,
        color=text_color,
        italic=True,
    )
    _replace_text(
        _find(slide, slots["attribution"]),
        slide_spec.subtitle or "",
        color=muted,
        size=Pt(16),
    )


def render_deck_copy_slides(
    spec: DeckSpec,
    meta: TemplateMeta,
    out_path: Path,
) -> Path:
    template_path = template_file(meta)
    if template_path is None:
        from .boho_render import render_deck_boho

        logger.warning("Thiếu file template cho %s, dùng boho renderer", meta.id)
        return render_deck_boho(spec, meta, out_path)

    template_prs = Presentation(str(template_path))
    prs = Presentation()
    prs.slide_width = template_prs.slide_width
    prs.slide_height = template_prs.slide_height
    prs.core_properties.title = spec.title
    if spec.author:
        prs.core_properties.author = spec.author

    blank = prs.slide_layouts[6]

    for index, slide_spec in enumerate(spec.slides, start=1):
        sample_type = LAYOUT_SAMPLE.get(slide_spec.layout, "content")
        sample_index = SAMPLE_SLIDES[sample_type]
        source = template_prs.slides[sample_index - 1]
        target = prs.slides.add_slide(blank)
        _copy_shapes(source, target)

        if sample_type == "title":
            _fill_title(target, spec, slide_spec, meta)
        elif sample_type == "two_column":
            _fill_two_column(target, spec, slide_spec, meta)
        elif sample_type == "quote":
            _fill_quote(target, spec, slide_spec, meta)
        else:
            _fill_content(target, spec, slide_spec, index, meta)

        if slide_spec.note:
            target.notes_slide.notes_text_frame.text = slide_spec.note

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
