# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging
from pathlib import Path

from . import aspose, libreoffice

logger = logging.getLogger(__name__)

__all__ = ["find_soffice", "preview_backend", "render_preview"]


def find_soffice() -> str | None:
    return libreoffice.find_soffice()


def preview_backend() -> str:
    if libreoffice.find_soffice():
        return "libreoffice"
    if aspose.is_available():
        return "aspose"
    return "none"


def render_preview(
    pptx_path: Path,
    spec=None,
    out_dir: Path | None = None,
    max_slides: int | None = None,
) -> list[Path]:
    if out_dir is None:
        raise ValueError("Thiếu thư mục preview")

    pptx_path = Path(pptx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("slide-*.png"):
        stale.unlink()

    soffice = libreoffice.find_soffice()
    if soffice:
        try:
            return libreoffice.render(
                soffice, pptx_path, out_dir, max_slides=max_slides
            )
        except Exception:
            logger.exception("LibreOffice preview thất bại, thử Aspose")

    if aspose.is_available():
        try:
            return aspose.render(
                pptx_path, out_dir, max_slides=max_slides
            )
        except Exception:
            logger.exception("Aspose preview thất bại")

    logger.warning(
        "Không có backend preview (LibreOffice/Aspose); bỏ qua preview"
    )
    return []
