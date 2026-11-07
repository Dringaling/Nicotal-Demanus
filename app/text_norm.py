# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt: đ/Đ -> d/D, NFKD rồi bỏ combining."""
    value = str(text).replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def normalize_search(text: str) -> str:
    """Chuẩn hoá để so khớp: không dấu, không hoa thường, bỏ ký tự đặc biệt."""
    value = strip_accents(text).casefold()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def slugify_tag(text: str) -> str:
    """Chuẩn hoá tag: chữ không dấu, số và dấu gạch ngang."""
    value = strip_accents(text).casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")
