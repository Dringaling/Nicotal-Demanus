# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import storage
from app.config import REPO_ROOT

TITLE = "Chuyển đổi số trong giáo dục"
DESCRIPTION = "Báo cáo 10 slide để kiểm tra giao diện theme."
DETAILS = """Dàn ý 10 slide cho báo cáo "Chuyển đổi số trong giáo dục":
1. Bìa: Chuyển đổi số trong giáo dục
2. Mục tiêu báo cáo
3. Thực trạng chuyển đổi số
4. Thách thức chính
5. Giải pháp: hạ tầng số
6. Giải pháp: dữ liệu và AI
7. Giải pháp: đào tạo giáo viên
8. Kết quả kỳ vọng
9. Lộ trình triển khai
10. Kết luận"""


def main() -> int:
    output = REPO_ROOT / "output"
    decks = sorted(
        output.glob("theme-gen-*.pptx"),
        key=lambda path: path.stat().st_mtime,
    )
    slugs = [path.stem for path in decks]
    if not slugs:
        print("Không có theme-gen-*.pptx")
        return 1

    records = storage.list_inputs(root=REPO_ROOT)
    record = next((item for item in records if item.title == TITLE), None)
    if record is None:
        record = storage.create_input(
            TITLE,
            DESCRIPTION,
            DETAILS,
            tags=["generated", "theme"],
            template="gen-swiss-editorial",
            root=REPO_ROOT,
        )
        print("created input", record.id)
    else:
        print("reusing input", record.id)

    record.output_slugs = slugs
    record.output_slug = slugs[-1]
    record.status = "done"
    storage._save_record(record, REPO_ROOT)
    storage._merge_tags(["generated", "theme"], REPO_ROOT)

    print(f"linked {len(slugs)} outputs to {record.id}")
    for slug in slugs:
        print(" -", slug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
