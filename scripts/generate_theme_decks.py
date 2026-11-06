# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from app.llm import LLMClient
from app.templates_catalog import get_template, refresh_templates
from app.theme_render import render_deck_theme

NAME = "Chuyển đổi số trong giáo dục"
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


def _ten_slides(spec):
    slides = list(spec.slides)
    if len(slides) <= 10:
        return spec, len(slides)
    if slides[-1].layout == "closing":
        slides = slides[:9] + [slides[-1]]
    else:
        slides = slides[:10]
    return spec.model_copy(update={"slides": slides}), 10


async def main() -> int:
    refresh_templates()
    themes = sorted(
        path.stem
        for path in Path("templates/themes").glob("gen-*.toml")
    )
    if not themes:
        print("Không có theme gen-*.toml")
        return 1

    settings = load_settings()
    key = "lmstudio-native/gemma-4-e4b-it"
    base = settings.providers[key]
    provider = replace(
        base,
        cache=replace(base.cache, local_cache=False),
        max_retries=1,
    )
    settings = replace(
        settings,
        provider_name="lmstudio-native",
        model_name="gemma-4-e4b-it",
        provider=provider,
    )
    client = LLMClient(settings)

    output = Path("output")
    output.mkdir(parents=True, exist_ok=True)

    ok = 0
    for theme_id in themes:
        meta = get_template(theme_id)
        if meta is None:
            print(f"[{theme_id}] SKIP: không nạp được theme")
            continue
        print(f"[{theme_id}] generating...")
        started = time.time()
        try:
            spec, usage = await client.generate_spec(
                NAME,
                DETAILS,
                template=theme_id,
                description=DESCRIPTION,
            )
            spec, count = _ten_slides(spec)
            out = output / f"theme-{theme_id}.pptx"
            render_deck_theme(spec, meta, out)
            elapsed = time.time() - started
            print(
                f"[{theme_id}] OK {count} slide, {elapsed:.1f}s, "
                f"completion={usage.completion_tokens} -> {out}"
            )
            ok += 1
        except Exception as exc:
            print(f"[{theme_id}] FAILED: {type(exc).__name__}: {exc}")
    print(f"done: {ok}/{len(themes)}")
    return 0 if ok == len(themes) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
