# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.theme_store import sync_active_themes


def main() -> int:
    copied = sync_active_themes(overwrite=True)
    print(f"copied {copied} f0 themes into themes/active/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
