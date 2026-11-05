from __future__ import annotations

import json

from .schema import DeckSpec

PROMPT_VERSION = "demanus-deck-v3"


def deck_json_schema() -> dict:
    return DeckSpec.model_json_schema()


def _schema_text() -> str:
    return json.dumps(
        deck_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


_LAYOUT_GUIDE = """\
- title: cover slide. `title` is the deck title; `subtitle` and `author` are optional.
- section: opens a part. `title` is the part name; `subtitle` is a short description.
- bullets: bullet list. Use `bullets`; level 0 is a main point, level 1 is a sub-point.
- two_column: comparison. Exactly two `columns`, each with `heading` and `bullets`.
- table: comparison table. `table.headers` and `table.rows` are required; every row
  must have exactly as many cells as there are headers.
- quote: pull quote. `title` is the quote; `subtitle` is the source.
- closing: final slide. `title` is the thank-you line; `subtitle` is contact info."""

SYSTEM_PROMPT = f"""\
You are an expert designer of medical presentations in Vietnamese. Convert the
user's description into a JSON deck-spec that the python-pptx renderer can build.

CHUNK PROTOCOL
- The user message contains exactly one chunk of a longer document.
- A chunk is delimited by `--- CHUNK START (i/N) ---` and `--- CHUNK END (i/N) ---`.
- Generate slides only for the text between those markers.
- If i == 1, include exactly one slide with layout "title" as the first slide.
- If i == N, include exactly one slide with layout "closing" as the last slide.
- If 1 < i < N, do not emit "title" or "closing" slides.
- Do not repeat content that belongs to other chunks; the chunks are merged later.
- Follow any explicit slide plan inside the chunk (for example "Slide 12: ...").

CONTENT RULES
- All user-visible text must be Vietnamese with diacritics, professional and concise.
- Target 3-6 content slides per chunk unless the chunk contains an explicit slide plan.
- Each slide has one main idea. At most 8 bullets, each at most 20 words.
- Tables: at most 4 columns and 8 rows. Do not overload cells.
- Never invent clinical numbers, dosages, or conclusions absent from the description.
  If data is missing, write "cần bổ sung" instead.
- Do not include bullet characters in text; the renderer adds them.
- Default font is "Lexend"; default palette is navy, blue, white.

OUTPUT RULES
- Return only a single JSON object. No markdown, no code fences, no commentary.
- The JSON must match the schema exactly. Do not add extra fields.
- `layout` must be one of: title, section, bullets, two_column, table, quote, closing.

LAYOUT CATALOG
{_LAYOUT_GUIDE}

JSON SCHEMA
{_schema_text()}
"""


def build_system_prompt(template_profile: str | None = None) -> str:
    if not template_profile:
        return SYSTEM_PROMPT
    instructions = """\
TEMPLATE CONTEXT
The deck will be rendered into the template described below. Use this context:
- Respect the placeholder sizes. Keep titles short and bullets concise.
- Prefer the template's accent colors for emphasis; do not specify colors in the JSON.
- If a slide would benefit from a visual, mention one of the layout media names in
  the `note` field. Do not put image names in slide text.
"""
    return SYSTEM_PROMPT + "\n\n" + instructions + "\n" + template_profile
