from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from .schema import BulletItem, DeckSpec, SlideSpec, TableBlock

LAYOUT_MAP = {
    "title": "TITLE",
    "section": "SECTION_HEADER",
    "bullets": "TITLE_AND_BODY",
    "two_column": "TITLE_AND_TWO_COLUMNS",
    "table": "TITLE_ONLY",
    "quote": "MAIN_POINT",
    "closing": "TITLE",
}

_TITLE_SIZE = 26
_BODY_SIZE = 16
_COLUMN_SIZE = 13


def _remove_all_slides(prs: Presentation) -> None:
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst):
        rel_id = sld_id.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if rel_id:
            prs.part.drop_rel(rel_id)
        sld_id_lst.remove(sld_id)


def _layout_by_name(prs: Presentation, name: str):
    for layout in prs.slide_layouts:
        if layout.name == name:
            return layout
    return None


def _set_title(slide, text: str, size: int = _TITLE_SIZE) -> None:
    shape = slide.shapes.title
    if shape is None:
        return
    shape.text = text
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(size)


def _set_placeholder_text(slide, idx: int, text: str, size: int | None = None):
    for shape in slide.placeholders:
        if shape.placeholder_format.idx != idx:
            continue
        shape.text = text
        if size:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(size)
        return shape
    return None


def _body_placeholder(slide, idx: int):
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == idx:
            return shape
    return None


def _fill_bullets(
    shape,
    items: list[BulletItem],
    base_size: int = _BODY_SIZE,
) -> None:
    frame = shape.text_frame
    frame.word_wrap = True
    frame.clear()
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = item.text
        paragraph.level = item.level
        for run in paragraph.runs:
            run.font.size = Pt(base_size if item.level == 0 else base_size - 2)


def _fill_column(shape, heading, bullets, base_size: int = _COLUMN_SIZE) -> None:
    frame = shape.text_frame
    frame.word_wrap = True
    frame.clear()
    first = True
    if heading:
        paragraph = frame.paragraphs[0]
        paragraph.text = heading
        for run in paragraph.runs:
            run.font.bold = True
            run.font.size = Pt(base_size + 1)
        first = False
    for item in bullets:
        paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        paragraph.text = item.text
        paragraph.level = item.level
        for run in paragraph.runs:
            run.font.size = Pt(base_size if item.level == 0 else base_size - 2)


def _add_table(slide, prs: Presentation, block: TableBlock) -> None:
    left = Inches(0.6)
    top = Inches(1.55)
    width = prs.slide_width - Inches(1.2)
    rows = len(block.rows) + 1
    cols = len(block.headers)
    height = min(Inches(3.6), Inches(0.4 * rows + 0.2))
    shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = shape.table

    col_width = int(width / cols)
    for index in range(cols):
        table.columns[index].width = col_width

    header_fill = RGBColor(0x21, 0x21, 0x21)
    body_fill = RGBColor(0xF5, 0xF5, 0xF5)
    white = RGBColor(0xFF, 0xFF, 0xFF)
    text_color = RGBColor(0x21, 0x21, 0x21)

    for row_index in range(rows):
        table.rows[row_index].height = Inches(0.4)
        for col_index in range(cols):
            cell = table.cell(row_index, col_index)
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            value = (
                block.headers[col_index]
                if row_index == 0
                else block.rows[row_index - 1][col_index]
            )
            cell.text = ""
            paragraph = cell.text_frame.paragraphs[0]
            run = paragraph.add_run()
            run.text = value
            run.font.size = Pt(11 if row_index == 0 else 10)
            run.font.bold = row_index == 0
            run.font.color.rgb = white if row_index == 0 else text_color
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if row_index == 0 else body_fill


def _add_subtitle_box(slide, prs: Presentation, text: str) -> None:
    left = Inches(0.8)
    top = prs.slide_height - Inches(1.35)
    box = slide.shapes.add_textbox(
        left, top, prs.slide_width - Inches(1.6), Inches(0.7)
    )
    paragraph = box.text_frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(14)


def _render_title(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title, 32)
    if slide_spec.subtitle:
        _set_placeholder_text(slide, 1, slide_spec.subtitle, 16)


def _render_section(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title, 30)
    if slide_spec.subtitle:
        _add_subtitle_box(slide, prs, slide_spec.subtitle)


def _render_bullets(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title)
    body = _body_placeholder(slide, 1)
    if body is not None:
        _fill_bullets(body, slide_spec.bullets)


def _render_two_column(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title)
    bodies = sorted(
        (
            shape
            for shape in slide.placeholders
            if shape.placeholder_format.idx in (1, 2)
        ),
        key=lambda shape: shape.placeholder_format.idx,
    )
    for column, body in zip(slide_spec.columns, bodies):
        _fill_column(body, column.heading, column.bullets)


def _render_table(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title)
    if slide_spec.table is not None:
        _add_table(slide, prs, slide_spec.table)


def _render_quote(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title, 28)
    if slide_spec.subtitle:
        _add_subtitle_box(slide, prs, slide_spec.subtitle)


def _render_closing(prs, slide, spec: DeckSpec, slide_spec: SlideSpec) -> None:
    _set_title(slide, slide_spec.title, 32)
    if slide_spec.subtitle:
        _set_placeholder_text(slide, 1, slide_spec.subtitle, 16)


_RENDERERS = {
    "title": _render_title,
    "section": _render_section,
    "bullets": _render_bullets,
    "two_column": _render_two_column,
    "table": _render_table,
    "quote": _render_quote,
    "closing": _render_closing,
}


def render_deck_with_template(
    spec: DeckSpec,
    template_path: Path,
    out_path: Path,
) -> Path:
    prs = Presentation(str(template_path))
    _remove_all_slides(prs)

    fallback = _layout_by_name(prs, "TITLE_AND_BODY") or prs.slide_layouts[-1]
    for slide_spec in spec.slides:
        layout_name = LAYOUT_MAP.get(slide_spec.layout, "TITLE_AND_BODY")
        layout = _layout_by_name(prs, layout_name) or fallback
        slide = prs.slides.add_slide(layout)
        renderer = _RENDERERS.get(slide_spec.layout, _render_bullets)
        renderer(prs, slide, spec, slide_spec)
        if slide_spec.note:
            slide.notes_slide.notes_text_frame.text = slide_spec.note

    prs.core_properties.title = spec.title
    if spec.author:
        prs.core_properties.author = spec.author

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
