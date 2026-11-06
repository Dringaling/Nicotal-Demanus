# SPDX-License-Identifier: AGPL-3.0-or-later
"""Preview backend dùng Aspose.Slides (thư viện độc quyền).

Việc dùng thư viện này được cho phép bởi "Special Exception for Document
Preview Module" trong file NOTICE ở thư mục gốc dự án. Mọi mã nguồn khác
vẫn thuộc AGPLv3.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_ASPOSE_SLIDES = 10
TARGET_WIDTH = 640


def _import_slides():
    import aspose.slides as slides

    return slides


def is_available() -> bool:
    try:
        _import_slides()
    except Exception:
        return False
    return True


def render(
    pptx_path: Path,
    out_dir: Path,
    slides_module=None,
    max_slides: int | None = None,
) -> list[Path]:
    slides = slides_module or _import_slides()
    pptx_path = Path(pptx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    with slides.Presentation(str(pptx_path)) as presentation:
        width = float(presentation.slide_size.size.width)
        if width <= 0:
            raise RuntimeError("Không đọc được kích thước slide")
        scale = TARGET_WIDTH / width

        limit = (
            MAX_ASPOSE_SLIDES
            if max_slides is None
            else min(max_slides, MAX_ASPOSE_SLIDES)
        )
        for index, slide in enumerate(presentation.slides, start=1):
            if index > limit:
                break
            image = slide.get_image(scale, scale)
            path = out_dir / f"slide-{index:02d}.png"
            image.save(str(path), slides.ImageFormat.PNG)
            paths.append(path)

    return paths
