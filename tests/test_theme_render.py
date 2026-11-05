from __future__ import annotations

from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches

from app.sample import sample_deck
from app.templates_catalog import get_template
from app.theme_render import render_deck_theme

VARIANTS = [
    "neo_tech_minimal__gruvbox",
    "neo_tech_minimal__soft_light",
    "neo_tech_minimal__cappuccino",
    "neo_tech_minimal__latte",
    "neo_tech_minimal__cream_pink",
]


def _background_rgb(path: Path) -> str:
    prs = Presentation(path)
    shape = prs.slides[0].shapes[0]
    return str(shape.fill.fore_color.rgb)


def test_theme_render_creates_deck(tmp_path: Path) -> None:
    meta = get_template("neo_tech_minimal")
    assert meta is not None
    out = render_deck_theme(sample_deck(), meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)


def test_theme_render_uses_lexend(tmp_path: Path) -> None:
    meta = get_template("neo_tech_minimal")
    assert meta is not None
    out = render_deck_theme(sample_deck(), meta, tmp_path / "deck.pptx")
    prs = Presentation(out)
    first = prs.slides[0]
    assert len(first.shapes) >= 2

    fonts = set()
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text.strip():
                        fonts.add(run.font.name)
    assert fonts == {"Lexend"}


@pytest.mark.parametrize("theme_id", VARIANTS)
def test_variant_theme_renders(tmp_path: Path, theme_id: str) -> None:
    meta = get_template(theme_id)
    assert meta is not None
    out = render_deck_theme(sample_deck(), meta, tmp_path / f"{theme_id}.pptx")
    prs = Presentation(out)
    assert len(prs.slides) == len(sample_deck().slides)
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)


def test_variant_uses_variant_colors(tmp_path: Path) -> None:
    base = get_template("neo_tech_minimal")
    variant = get_template("neo_tech_minimal__gruvbox")
    assert base is not None and variant is not None

    base_out = render_deck_theme(sample_deck(), base, tmp_path / "base.pptx")
    variant_out = render_deck_theme(
        sample_deck(), variant, tmp_path / "variant.pptx"
    )

    assert _background_rgb(base_out) == "0F172A"
    assert _background_rgb(variant_out) == "282828"


def test_variant_keeps_base_layout(tmp_path: Path) -> None:
    base = get_template("neo_tech_minimal")
    variant = get_template("neo_tech_minimal__latte")
    assert base is not None and variant is not None

    base_out = render_deck_theme(sample_deck(), base, tmp_path / "base.pptx")
    variant_out = render_deck_theme(
        sample_deck(), variant, tmp_path / "variant.pptx"
    )

    base_prs = Presentation(base_out)
    variant_prs = Presentation(variant_out)
    assert len(base_prs.slides) == len(variant_prs.slides)
    for base_slide, variant_slide in zip(
        base_prs.slides, variant_prs.slides
    ):
        assert len(base_slide.shapes) == len(variant_slide.shapes)
