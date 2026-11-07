# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import pytest

from app.llm import _cache_key
from app.template_profile import load_profile_from_path
from app.templates_catalog import (
    _deep_merge,
    format_design_tokens,
    format_template_context,
    get_template,
    list_templates,
    load_theme_data,
    resolve_path,
    template_assets_dir,
    template_file,
)

VARIANT_ALIASES = {
    "gruvbox": "neo_tech_minimal__gruvbox",
    "soft_light": "neo_tech_minimal__soft_light",
    "cappuccino": "neo_tech_minimal__cappuccino",
    "latte": "neo_tech_minimal__latte",
    "cream_pink": "neo_tech_minimal__cream_pink",
}


def test_load_templates() -> None:
    templates = list_templates()
    ids = {template.id for template in templates}
    assert "flat" in ids
    assert "dividing-fractions" in ids
    assert "boho-minimalist" in ids
    assert "boho-copy" in ids
    assert "neo_tech_minimal" in ids
    for target in VARIANT_ALIASES.values():
        assert target in ids


def test_default_meta_has_no_variant() -> None:
    meta = get_template("neo_tech_minimal")
    assert meta is not None
    assert meta.variant_id == ""
    assert meta.parent_id == ""
    assert meta.variant_name == ""
    assert meta.kind == "theme"


def test_variant_meta_palette() -> None:
    meta = get_template("neo_tech_minimal__gruvbox")
    assert meta is not None
    assert meta.parent_id == "neo_tech_minimal"
    assert meta.variant_id == "gruvbox"
    assert meta.variant_name == "Gruvbox"
    assert meta.bg_color == (40, 40, 40)
    assert meta.accent_color == (254, 128, 25)
    assert meta.renderer == "theme"


def test_variant_order_matches_toml() -> None:
    ids = [template.id for template in list_templates()]
    assert ids.index("neo_tech_minimal") < ids.index(
        "neo_tech_minimal__gruvbox"
    )
    variants = [item for item in ids if item.startswith("neo_tech_minimal__")]
    assert variants == list(VARIANT_ALIASES.values())


def test_display_names() -> None:
    expected = {
        "neo_tech_minimal__gruvbox": "Neo Tech Minimalist - Gruvbox",
        "neo_tech_minimal__soft_light": "Neo Tech Minimalist - Soft Light",
        "neo_tech_minimal__cappuccino": "Neo Tech Minimalist - Cappuccino",
        "neo_tech_minimal__latte": "Neo Tech Minimalist - Latte",
        "neo_tech_minimal__cream_pink": "Neo Tech Minimalist - Cream Pink",
    }
    for variant_id, name in expected.items():
        meta = get_template(variant_id)
        assert meta is not None
        assert meta.name == name


def test_old_ids_are_aliases() -> None:
    for alias, target in VARIANT_ALIASES.items():
        meta = get_template(alias)
        assert meta is not None
        assert meta.id == target
        assert meta.variant_id


def test_variant_files_removed() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in VARIANT_ALIASES:
        assert not (root / "templates" / "themes" / f"{name}.toml").exists()


def test_load_theme_data_merges_variant() -> None:
    base_meta = get_template("neo_tech_minimal")
    variant_meta = get_template("neo_tech_minimal__gruvbox")
    assert base_meta is not None and variant_meta is not None

    base = load_theme_data(base_meta)
    variant = load_theme_data(variant_meta)

    assert variant["palette"]["bg"] == [40, 40, 40]
    assert variant["colors"]["background"]["hex"] == "#282828"
    assert variant["layouts"] == base["layouts"]
    assert variant["typography"] == base["typography"]
    assert "variants" not in variant


def test_format_design_tokens_uses_variant_colors() -> None:
    meta = get_template("neo_tech_minimal__gruvbox")
    assert meta is not None
    text = format_design_tokens(meta)
    assert "#FE8019" in text
    assert "#282828" in text


def test_deep_merge_falls_back_to_base() -> None:
    base = {
        "palette": {"bg": [1, 2, 3], "accent": [4, 5, 6]},
        "layouts": {"hero": {"left_inch": 1.0}},
    }
    merged = _deep_merge(base, {"palette": {"bg": [9, 9, 9]}})
    assert merged["palette"] == {"bg": [9, 9, 9], "accent": [4, 5, 6]}
    assert merged["layouts"] == {"hero": {"left_inch": 1.0}}
    assert base["palette"]["bg"] == [1, 2, 3]


def test_kind_split() -> None:
    assert get_template("dividing-fractions").kind == "pptx"
    assert get_template("boho-copy").kind == "pptx"
    assert get_template("boho-minimalist").kind == "pptx"
    assert get_template("flat").kind == "theme"
    assert get_template("neo_tech_minimal").kind == "theme"
    assert get_template("neo_tech_minimal__gruvbox").kind == "theme"


def test_cache_key_differs_for_variant() -> None:
    base = _cache_key("v4", "m", "n", "d", "x", "neo_tech_minimal", 8000, "")
    variant = _cache_key(
        "v4", "m", "n", "d", "x", "neo_tech_minimal__gruvbox", 8000, ""
    )
    assert base != variant


def test_generated_themes_use_theme_renderer() -> None:
    for theme_id in VARIANT_ALIASES:
        meta = get_template(theme_id)
        assert meta is not None
        assert meta.renderer == "theme"
        assert meta.theme_file


def test_theme_metadata() -> None:
    meta = get_template("neo_tech_minimal")
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


@pytest.mark.parametrize("variant_id", list(VARIANT_ALIASES.values()))
def test_every_variant_has_palette_override(variant_id: str) -> None:
    base = get_template("neo_tech_minimal")
    meta = get_template(variant_id)
    assert base is not None and meta is not None
    assert meta.bg_color != base.bg_color
    assert meta.theme_file == base.theme_file


def test_template_tag_counts_include_variants() -> None:
    from app.templates_catalog import grouped_templates, template_tag_counts

    groups = grouped_templates()
    counts = template_tag_counts(groups)
    expected = sum(
        1
        for metas in groups.values()
        for meta in metas
        if "dark" in meta.tags
    )

    assert counts.get("dark", 0) == expected
    assert counts


def test_variant_tags_override_base() -> None:
    meta = get_template("neo_tech_minimal__gruvbox")
    base = get_template("neo_tech_minimal")

    assert meta is not None and base is not None
    assert meta.tags
    assert "gruvbox" in meta.tags
    assert meta.tags != base.tags


def test_filter_template_groups_empty_selection() -> None:
    from app.templates_catalog import filter_template_groups, grouped_templates

    groups = grouped_templates()

    assert filter_template_groups(groups, []) == groups


def test_filter_template_groups_or_semantics() -> None:
    from app.templates_catalog import filter_template_groups, grouped_templates

    groups = grouped_templates()
    filtered = filter_template_groups(groups, ["dark", "light"])

    kept = [meta for metas in filtered.values() for meta in metas]
    assert kept
    for meta in kept:
        assert {"dark", "light"} & set(meta.tags)


def test_filter_template_groups_unknown_tag_is_empty() -> None:
    from app.templates_catalog import filter_template_groups, grouped_templates

    assert filter_template_groups(grouped_templates(), ["khong-ton-tai"]) == {}


def test_filter_template_groups_keeps_selected_template() -> None:
    from app.templates_catalog import filter_template_groups, grouped_templates

    filtered = filter_template_groups(
        grouped_templates(), ["dark"], "flat"
    )

    kept = [meta.id for metas in filtered.values() for meta in metas]
    assert "flat" in kept
