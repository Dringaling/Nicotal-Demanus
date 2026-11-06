# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schema import BulletItem, Column, DeckSpec, SlideSpec, TableBlock
from app.templates_catalog import get_template, refresh_templates
from app.theme_render import render_deck_theme

OUTPUT = Path("output")


def test_deck() -> DeckSpec:
    return DeckSpec(
        title="Kiểm tra theme",
        subtitle="Title + context, 2 cột, 3 cột, bảng, list",
        author="Demanus",
        slides=[
            SlideSpec(
                layout="title",
                title="Kiểm tra theme mới",
                subtitle="Title + context cho trang bìa",
            ),
            SlideSpec(
                layout="section",
                title="Phần 1: Tổng quan",
                subtitle="Title + context cho section",
            ),
            SlideSpec(
                layout="bullets",
                title="Danh sách (list)",
                bullets=[
                    BulletItem(text="Mục chính thứ nhất"),
                    BulletItem(text="Mục chính thứ hai"),
                    BulletItem(text="Mục chính thứ ba"),
                    BulletItem(text="Mục phụ", level=1),
                    BulletItem(text="Mục phụ khác", level=1),
                    BulletItem(text="Mục chính thứ tư"),
                ],
            ),
            SlideSpec(
                layout="two_column",
                title="So sánh 2 cột",
                columns=[
                    Column(
                        heading="Trước",
                        bullets=[
                            BulletItem(text="Quy trình thủ công"),
                            BulletItem(text="Thiếu dữ liệu"),
                            BulletItem(text="Phản hồi chậm"),
                        ],
                    ),
                    Column(
                        heading="Sau",
                        bullets=[
                            BulletItem(text="Tự động hóa"),
                            BulletItem(text="Dữ liệu tập trung"),
                            BulletItem(text="Phản hồi nhanh"),
                        ],
                    ),
                ],
            ),
            SlideSpec(
                layout="table",
                title="Bảng so sánh",
                table=TableBlock(
                    headers=["Tiêu chí", "Trước", "Sau"],
                    rows=[
                        ["Thời gian", "2 giờ", "15 phút"],
                        ["Chi phí", "Cao", "Thấp"],
                        ["Độ chính xác", "Trung bình", "Cao"],
                    ],
                ),
            ),
            SlideSpec(
                layout="bullets",
                title="Ba nhóm nội dung",
                bullets=[
                    BulletItem(text="Nhóm 1: Chiến lược"),
                    BulletItem(text="Nhóm 1: Mục tiêu"),
                    BulletItem(text="Nhóm 2: Công nghệ"),
                    BulletItem(text="Nhóm 2: Hạ tầng"),
                    BulletItem(text="Nhóm 3: Con người"),
                    BulletItem(text="Nhóm 3: Đào tạo"),
                ],
            ),
            SlideSpec(
                layout="quote",
                title="Thiết kế tốt là thiết kế không cần giải thích.",
                subtitle="Demanus",
            ),
            SlideSpec(
                layout="section",
                title="Phần 2: Chi tiết",
                subtitle="Title + context cho section thứ hai",
            ),
            SlideSpec(
                layout="bullets",
                title="Danh sách dài",
                bullets=[
                    BulletItem(text=f"Mục nội dung số {index}")
                    for index in range(1, 8)
                ],
            ),
            SlideSpec(
                layout="closing",
                title="Cảm ơn",
                subtitle="Liên hệ: demanus@example.com",
            ),
        ],
    )


def main() -> int:
    refresh_templates()
    themes = sorted(
        path.stem
        for path in Path("templates/themes").glob("gen2-*.toml")
    )
    if not themes:
        print("Không có theme gen2-*.toml")
        return 1

    OUTPUT.mkdir(parents=True, exist_ok=True)
    deck = test_deck()
    ok = 0
    for theme_id in themes:
        meta = get_template(theme_id)
        if meta is None:
            print(f"[{theme_id}] SKIP")
            continue
        out = OUTPUT / f"theme-test-{theme_id}.pptx"
        try:
            render_deck_theme(deck, meta, out)
            print(f"[{theme_id}] OK -> {out}")
            ok += 1
        except Exception as exc:
            print(f"[{theme_id}] FAILED: {type(exc).__name__}: {exc}")
    print(f"done: {ok}/{len(themes)}")
    return 0 if ok == len(themes) else 1


if __name__ == "__main__":
    sys.exit(main())
