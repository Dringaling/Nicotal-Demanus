# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.preview import preview_backend, render_preview

MAX_SLIDES = 10


def main() -> int:
    backend = preview_backend()
    print("preview backend:", backend)
    if backend == "none":
        print("Không có backend preview (LibreOffice/Aspose).")
        return 1

    output = Path("output")
    removed = 0
    for preview in output.glob("*/preview"):
        if preview.is_dir():
            shutil.rmtree(preview)
            removed += 1
    print(f"removed stale preview dirs: {removed}")

    decks = sorted(output.glob("*.pptx"))
    print(f"decks: {len(decks)}")

    total = 0
    for pptx in decks:
        slug = pptx.stem
        sidecar = output / slug
        preview = sidecar / "preview"
        paths = render_preview(
            pptx, None, preview, max_slides=MAX_SLIDES
        )
        print(f"{slug}: {len(paths)} preview")
        total += len(paths)
    print(f"done: {total} preview images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
