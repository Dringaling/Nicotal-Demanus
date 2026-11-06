# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import copy
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tomli_w

from app.sample import sample_deck
from app.templates_catalog import (
    THEMES_DIR,
    get_template,
    load_theme_data,
    refresh_templates,
)
from app.theme_render import render_deck_theme

# Mỗi dòng: slug gốc, title_layout, content_layout.
# 15 content_layout khác nhau -> không trùng cách bố trí layout.
DESIGNS = [
    ("swiss-editorial", "left_rule", "left", "two_column_text"),
    ("zen-japanese", "full_bleed", "center", "single_column"),
    ("neon-cyberpunk", "split_panel", "band", "grid_2x2"),
    ("warm-boho", "center_card", "badge", "rounded_cards"),
    ("medical-clean", "top_band", "rail", "compact_cards"),
    ("luxury-gold", "center_card", "center", "magazine"),
    ("brutalist", "left_rule", "band", "stacked_bands"),
    ("glass-soft", "top_band", "grid", "glass_grid"),
    ("retro-70s", "split_panel", "badge", "numbered_bands"),
    ("nature-organic", "full_bleed", "center", "centered_list"),
    ("blueprint-tech", "top_band", "grid", "split_list"),
    ("pastel-playful", "center_card", "badge", "metric_tiles"),
    ("dark-academia", "left_rule", "left", "heading_rail"),
    ("high-contrast", "full_bleed", "band", "timeline"),
    ("hud-future", "split_panel", "rail", "two_column_lists"),
]


def _alt_variant(base: dict) -> dict:
    colors = copy.deepcopy(base["colors"])
    background = colors["background"]
    text = colors["text"]

    background["hex"], text["primary_hex"] = (
        text["primary_hex"],
        background["hex"],
    )
    background["rgb"], text["primary_rgb"] = (
        text["primary_rgb"],
        background["rgb"],
    )
    colors["card"]["bg_rgb"] = background["rgb"]
    colors["card"]["bg_hex"] = background["hex"]
    colors["text"]["secondary_rgb"] = base["colors"]["text"]["secondary_rgb"]
    colors["text"]["secondary_hex"] = base["colors"]["text"]["secondary_hex"]

    palette = {
        "bg": background["rgb"],
        "card": colors["card"]["bg_rgb"],
        "accent": base["palette"]["accent"],
        "text": text["primary_rgb"],
        "muted": base["palette"]["muted"],
    }
    return {
        "name": "Alt",
        "description": "Đảo sáng/tối, giữ nguyên layout và accent.",
        "style": f"{base['theme']['style']}-alt",
        "tags": ["generated", "variant"],
        "palette": palette,
        "colors": colors,
    }


def main() -> int:
    ok = 0
    for slug, title_layout, header_layout, content_layout in DESIGNS:
        source = THEMES_DIR / f"gen-{slug}.toml"
        if not source.is_file():
            print(f"[{slug}] missing {source}")
            continue
        data = tomllib.loads(source.read_text(encoding="utf-8"))
        data.pop("variants", None)

        theme = data["theme"]
        theme["id"] = f"gen2-{slug}"
        theme["name"] = f"{theme.get('name', slug)} Layout"
        theme["style"] = f"{slug}-layout"
        theme["title_layout"] = title_layout
        theme["header_layout"] = header_layout
        theme["content_layout"] = content_layout
        data["variants"] = {"alt": _alt_variant(data)}

        path = THEMES_DIR / f"gen2-{slug}.toml"
        path.write_text(tomli_w.dumps(data), encoding="utf-8")
        print(
            f"[{slug}] wrote {path} "
            f"({title_layout} + {header_layout} + {content_layout})"
        )
        ok += 1

    refresh_templates()
    for slug, _, _, _ in DESIGNS:
        theme_id = f"gen2-{slug}"
        meta = get_template(theme_id)
        if meta is None:
            print(f"[{theme_id}] FAILED to load")
            continue
        load_theme_data(meta)
        render_deck_theme(
            sample_deck(), meta, Path("/tmp") / f"{theme_id}.pptx"
        )
    print(f"done: {ok}/{len(DESIGNS)}")
    return 0 if ok == len(DESIGNS) else 1


if __name__ == "__main__":
    sys.exit(main())
