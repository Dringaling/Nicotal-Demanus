# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import storage
from app.config import REPO_ROOT

OUTPUT = REPO_ROOT / "output"
TAGS = ["script", "generated"]


def deck_meta(slug: str) -> tuple[str, str]:
    spec_path = OUTPUT / slug / "spec.json"
    if not spec_path.is_file():
        return slug, slug
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception:
        return slug, slug
    title = str(data.get("title") or slug).strip() or slug
    lines = [title]
    for slide in data.get("slides", [])[:20]:
        text = str(slide.get("title") or "").strip()
        if text:
            lines.append(f"- {text}")
    return title[:200], "\n".join(lines)


def main() -> int:
    records = storage.list_inputs(root=REPO_ROOT)
    linked = {
        slug for record in records for slug in record.output_slugs
    }
    orphans = [
        path.stem
        for path in sorted(OUTPUT.glob("*.pptx"))
        if path.stem not in linked
    ]
    print(f"orphans: {len(orphans)}")
    if not orphans:
        return 0

    by_title = {record.title: record for record in records}
    created = 0
    for slug in orphans:
        title, details = deck_meta(slug)
        record = by_title.get(title)
        if record is None:
            try:
                record = storage.create_input(
                    title,
                    "Deck sinh bởi script.",
                    details,
                    tags=TAGS,
                    template="flat",
                    root=REPO_ROOT,
                )
                created += 1
            except storage.DuplicateTitleError as exc:
                record = storage.get_input(exc.existing_id, root=REPO_ROOT)
            by_title[title] = record
        if slug not in record.output_slugs:
            storage.append_output(record.id, slug, root=REPO_ROOT)
        print(f"{slug} -> {record.id} ({title})")

    print(f"created {created} inputs, linked {len(orphans)} decks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
