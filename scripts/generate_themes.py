# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import asyncio
import json
import re
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tomli_w

from app.config import load_settings
from app.llm import LLMClient
from app.sample import sample_deck
from app.templates_catalog import (
    THEMES_DIR,
    _deep_merge,
    get_template,
    load_theme_data,
    refresh_templates,
)
from app.theme_render import render_deck_theme

REFERENCE_PATH = THEMES_DIR / "neo_tech_minimal.toml"
REFERENCE_TEXT = REFERENCE_PATH.read_text(encoding="utf-8")
REFERENCE_DATA = tomllib.loads(REFERENCE_TEXT)
REFERENCE_DATA.pop("variants", None)

STYLES = [
    (
        "swiss-editorial",
        "Swiss Editorial",
        "Lưới Thụy Sĩ, nhiều khoảng trắng, đường kẻ mảnh, chữ lớn, tương phản cao.",
    ),
    (
        "zen-japanese",
        "Japanese Zen",
        "Tối giản thiền Nhật, bất đối xứng, nhiều không gian âm, điểm nhấn trục dọc.",
    ),
    (
        "neon-cyberpunk",
        "Neon Cyberpunk",
        "Nền tối, tương phản mạnh, điểm nhấn neon, thẻ góc cạnh, cảm giác tương lai.",
    ),
    (
        "warm-boho",
        "Warm Boho",
        "Thẻ bo tròn hữu cơ, tông đất ấm, khoảng thở rộng, mềm mại.",
    ),
    (
        "medical-clean",
        "Medical Clean",
        "Xanh y khoa, bố cục chính xác, thẻ gọn, cảm giác tin cậy.",
    ),
    (
        "luxury-gold",
        "Luxury Gold",
        "Nền mận đậm, điểm nhấn vàng, thẻ lớn, khoảng cách sang trọng.",
    ),
    (
        "brutalist",
        "Brutalist",
        "Khối đậm, viền dày, chữ quá khổ, hình học thô, tương phản mạnh.",
    ),
    (
        "glass-soft",
        "Glass Soft",
        "Thẻ trong mờ, gradient nhẹ, nhiều khoảng trắng, cảm giác kính.",
    ),
    (
        "retro-70s",
        "Retro 70s",
        "Cam nâu ấm, hình khối bo tròn, badge đậm, phong cách thập niên 70.",
    ),
    (
        "nature-organic",
        "Nature Organic",
        "Xanh olive, thẻ mềm, nhịp điệu tự nhiên, tĩnh và thư thái.",
    ),
    (
        "blueprint-tech",
        "Blueprint Tech",
        "Lưới kỹ thuật, nhãn chính xác, đường mảnh, cảm giác bản vẽ.",
    ),
    (
        "pastel-playful",
        "Pastel Playful",
        "Pastel sáng, thẻ tròn, số liệu lớn, thân thiện và vui.",
    ),
    (
        "dark-academia",
        "Dark Academia",
        "Nâu kem cổ điển, bố cục dày, chữ trang trọng, cảm giác học thuật.",
    ),
    (
        "high-contrast",
        "High Contrast",
        "Đen trắng vàng, chữ rất lớn, viền mạnh, ưu tiên khả năng đọc.",
    ),
    (
        "hud-future",
        "HUD Future",
        "Teal tối, thẻ góc cạnh, đường HUD, số liệu nổi bật.",
    ),
]


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _norm(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, (list, tuple)):
        return tuple(_norm(item) for item in value)
    return value


def summarize(data: dict) -> dict:
    theme = data.get("theme", {})
    palette = data.get("palette", {})
    hero = (
        data.get("layouts", {})
        .get("hero_title", {})
        .get("card", {})
    )
    typography = data.get("typography", {})
    return {
        "id": theme.get("id"),
        "name": theme.get("name"),
        "style": theme.get("style"),
        "palette": [
            palette.get(key, []) for key in ("bg", "card", "accent", "text", "muted")
        ],
        "hero": [
            hero.get(key)
            for key in (
                "left_inch",
                "top_inch",
                "width_inch",
                "height_inch",
                "corner_radius",
            )
        ],
        "typography": [
            typography.get(key, {}).get("size_pt")
            for key in (
                "title_hero",
                "title_section",
                "card_title",
                "card_body",
                "big_metric",
            )
        ],
    }


def fingerprint(summary: dict) -> tuple:
    return _norm(
        (summary["palette"], summary["hero"], summary["typography"])
    )


def _messages(
    slug: str,
    name: str,
    brief: str,
    previous: list[dict],
    error: str = "",
) -> list[dict]:
    instruction = (
        "Create ONE new Demanus theme TOML with a clearly different visual style, "
        "not a simple color swap. Keep the same table structure as the reference: "
        "[theme], [palette], [colors.*], [typography], [layouts.*]. "
        "Vary palette/colors, typography scale, card geometry (positions, sizes, "
        "corner radius), header/body placement, and spacing. "
        "The new theme must be clearly different from EVERY previous design below. "
        "Do not reuse the same palette AND the same hero card geometry as any "
        "previous design. If the brief is close to an existing design, mix two "
        "previous designs in a new way (for example palette from one, geometry from "
        "another) rather than copying one. "
        "Return only the TOML document, no markdown, no commentary."
    )
    previous_text = (
        json.dumps(previous, ensure_ascii=False, indent=2) if previous else "[]"
    )
    user = (
        f"STYLE BRIEF: {name} — {brief}\n"
        f"Theme id: gen-{slug}\n"
        f"Theme name: {name}\n\n"
        f"REFERENCE THEME TOML:\n{REFERENCE_TEXT}\n\n"
        f"PREVIOUS DESIGNS (must not be repeated):\n{previous_text}\n\n"
        f"{instruction}"
    )
    if error:
        user += (
            f"\n\nThe previous TOML was rejected: {error}. "
            "Fix it and return only TOML."
        )
    return [
        {
            "role": "system",
            "content": (
                "You are a senior presentation theme designer. "
                "You output only valid TOML."
            ),
        },
        {"role": "user", "content": user},
    ]


async def generate_one(
    client: LLMClient,
    slug: str,
    name: str,
    brief: str,
    previous: list[dict],
    fingerprints: set[tuple],
) -> tuple[Path, dict]:
    error = ""
    for attempt in range(3):
        content, _usage = await client.chat(
            _messages(slug, name, brief, previous, error)
        )
        try:
            data = tomllib.loads(_strip_fence(content))
            if not isinstance(data.get("theme"), dict):
                raise ValueError("Thiếu bảng [theme]")
            merged = _deep_merge(REFERENCE_DATA, data)
            merged["theme"]["id"] = f"gen-{slug}"
            merged["theme"]["name"] = name
            merged["theme"].setdefault("description", brief)
            merged["theme"].setdefault("style", slug)
            merged["theme"].setdefault("tags", ["generated", slug])

            summary = summarize(merged)
            summary["id"] = f"gen-{slug}"
            summary["name"] = name
            summary["style"] = slug
            fp = fingerprint(summary)
            if fp in fingerprints:
                duplicate = next(
                    (
                        item["id"]
                        for item in previous
                        if fingerprint(item) == fp
                    ),
                    "một thiết kế trước",
                )
                raise ValueError(
                    f"Thiết kế trùng palette + geometry + typography với "
                    f"{duplicate}; đổi palette và geometry"
                )

            path = THEMES_DIR / f"gen-{slug}.toml"
            path.write_text(tomli_w.dumps(merged), encoding="utf-8")
            refresh_templates()
            meta = get_template(f"gen-{slug}")
            if meta is None:
                raise ValueError("Không nạp được theme sau khi ghi")
            load_theme_data(meta)
            render_deck_theme(
                sample_deck(), meta, Path("/tmp") / f"gen-{slug}.pptx"
            )
            return path, summary
        except Exception as exc:
            error = str(exc)
            print(f"  attempt {attempt + 1} failed: {error[:200]}")
    raise RuntimeError(f"Không tạo được theme {slug}: {error}")


async def main() -> int:
    settings = load_settings()
    key = "deepinfra/deepseek-flash-flex"
    provider = replace(settings.providers[key], max_retries=2)
    settings = replace(
        settings,
        provider_name="deepinfra",
        model_name="deepseek-flash-flex",
        provider=provider,
    )
    client = LLMClient(settings)

    previous: list[dict] = []
    fingerprints: set[tuple] = set()
    ok = 0
    for slug, name, brief in STYLES:
        print(f"[{slug}] generating...")
        try:
            path, summary = await generate_one(
                client, slug, name, brief, previous, fingerprints
            )
            previous.append(summary)
            fingerprints.add(fingerprint(summary))
            print(f"[{slug}] OK -> {path}")
            ok += 1
        except Exception as exc:
            print(f"[{slug}] FAILED: {exc}")
    print(f"done: {ok}/{len(STYLES)}")
    return 0 if ok == len(STYLES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
