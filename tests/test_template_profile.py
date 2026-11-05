from __future__ import annotations

from app.template_profile import (
    format_template_profile,
    load_template_profile,
    template_profile_hash,
)


def test_profile_loads_geometry_and_colors() -> None:
    profile = load_template_profile("dividing-fractions")
    assert profile is not None
    assert profile.width_in == 10.0
    assert profile.height_in == 5.625
    assert profile.colors["accent1"] == "#4285F4"
    assert profile.major_font == "Arial"


def test_profile_contains_mapped_layouts() -> None:
    profile = load_template_profile("dividing-fractions")
    assert profile is not None
    names = {layout.name for layout in profile.layouts}
    assert "TITLE" in names
    assert "TITLE_AND_BODY" in names
    assert "TITLE_AND_TWO_COLUMNS" in names
    assert any(layout.media for layout in profile.layouts)


def test_format_template_profile() -> None:
    profile = load_template_profile("dividing-fractions")
    assert profile is not None
    text = format_template_profile(profile)
    assert "TEMPLATE CONTEXT" in text
    assert "TITLE_AND_BODY" in text
    assert "accent1=#4285F4" in text
    assert "Layout media:" in text


def test_fingerprint_is_stable() -> None:
    first = template_profile_hash("dividing-fractions")
    second = template_profile_hash("dividing-fractions")
    assert first == second
    assert first


def test_unknown_template_returns_none() -> None:
    assert load_template_profile("khong-ton-tai") is None
