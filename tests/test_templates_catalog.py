from __future__ import annotations

from app.template_profile import load_profile_from_path
from app.templates_catalog import (
    format_template_context,
    get_template,
    list_templates,
    resolve_path,
    template_assets_dir,
    template_file,
)


def test_load_templates() -> None:
    templates = list_templates()
    ids = {template.id for template in templates}
    assert "flat" in ids
    assert "dividing-fractions" in ids
    assert "boho-minimalist" in ids
    assert "boho-copy" in ids
    assert "neo-tech-minimal" in ids


def test_theme_metadata() -> None:
    meta = get_template("neo-tech-minimal")
    assert meta is not None
    assert meta.renderer == "theme"
    assert meta.theme_file
    assert resolve_path(meta.theme_file).is_file()


def test_copy_renderer_metadata() -> None:
    meta = get_template("boho-copy")
    assert meta is not None
    assert meta.renderer == "copy"
    assert meta.file
    assert meta.font == "Lexend"


def test_boho_metadata_and_assets() -> None:
    meta = get_template("boho-minimalist")
    assert meta is not None
    assert meta.font == "Lexend"
    assert meta.accent_color == (217, 119, 87)
    assert meta.accent_secondary == (122, 140, 112)
    assert template_assets_dir(meta) is not None


def test_flat_has_no_template_file() -> None:
    meta = get_template("flat")
    assert meta is not None
    assert template_file(meta) is None


def test_format_context_includes_design_tokens() -> None:
    meta = get_template("boho-minimalist")
    assert meta is not None
    profile = load_profile_from_path(
        str(template_file(meta)), tuple(meta.layout_map.items())
    )
    text = format_template_context(meta, profile)
    assert "TEMPLATE CONTEXT" in text
    assert "accent: #D97757" in text
    assert "font: Lexend" in text
    assert "bullets -> OBJECT" in text
