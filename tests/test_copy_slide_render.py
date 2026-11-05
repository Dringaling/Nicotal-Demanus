# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from app.copy_slide_render import render_deck_copy_slides
from app.sample import sample_deck
from app.templates_catalog import get_template


def _walk(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(shape.shapes)


def test_copy_slide_render_creates_deck(tmp_path: Path) -> None:
    meta = get_template("boho-copy")
    assert meta is not None
    out = render_deck_copy_slides(sample_deck(), meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(20)
    assert prs.slide_height == Inches(11.25)


def test_copy_slide_has_pictures_and_lexend(tmp_path: Path) -> None:
    meta = get_template("boho-copy")
    assert meta is not None
    out = render_deck_copy_slides(sample_deck(), meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    first = prs.slides[0]
    pictures = [
        shape
        for shape in _walk(first.shapes)
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert pictures

    for slide in prs.slides:
        for shape in _walk(slide.shapes):
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text.strip():
                        assert run.font.name == "Lexend"


def test_copy_slide_replaces_title(tmp_path: Path) -> None:
    meta = get_template("boho-copy")
    assert meta is not None
    spec = sample_deck()
    out = render_deck_copy_slides(spec, meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    texts = []
    for slide in prs.slides:
        for shape in _walk(slide.shapes):
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
    assert spec.slides[0].title in "\n".join(texts)
