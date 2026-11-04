from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .schema import DeckSpec, SlideSpec

DPI = 150
PX = DPI  # pixel trên mỗi inch
WIDTH = int(round(13.333 * PX))
HEIGHT = int(round(7.5 * PX))
SCALE = DPI / 72.0

_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}

_REGULAR_CANDIDATES = (
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
_BOLD_CANDIDATES = (
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found

    candidates = (
        "/usr/bin/soffice",
        "/usr/lib/libreoffice/program/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


def preview_backend() -> str:
    return "libreoffice" if find_soffice() else "pillow"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidates = _BOLD_CANDIDATES if bold else _REGULAR_CANDIDATES
    for candidate in candidates:
        if Path(candidate).is_file():
            font = ImageFont.truetype(candidate, size)
            _FONT_CACHE[key] = font
            return font

    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _mix(first: str, second: str, ratio: float) -> tuple[int, int, int]:
    a = _rgb(first)
    b = _rgb(second)
    return tuple(int(x + (y - x) * ratio) for x, y in zip(a, b))


def _shade(value: str, factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in _rgb(value))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font,
    fill: tuple[int, int, int],
    *,
    align: str = "left",
    valign: str = "top",
    line_spacing: float = 1.2,
) -> None:
    x, y, w, h = box
    lines = _wrap(draw, text, font, w)
    ascent, descent = font.getmetrics()
    line_height = int((ascent + descent) * line_spacing)
    total = line_height * len(lines)

    if valign == "middle":
        start_y = y + (h - total) // 2
    elif valign == "bottom":
        start_y = y + h - total
    else:
        start_y = y

    for index, line in enumerate(lines):
        line_width = draw.textlength(line, font=font)
        if align == "center":
            left = x + (w - line_width) / 2
        elif align == "right":
            left = x + w - line_width
        else:
            left = x
        draw.text((left, start_y + index * line_height), line, font=font, fill=fill)


def _draw_header(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    palette = spec.palette
    x, y = int(0.6 * PX), int(0.45 * PX)
    w, h = int(12.13 * PX), int(0.95 * PX)
    draw.rounded_rectangle(
        [x + 10, y + 10, x + w + 10, y + h + 10],
        radius=12,
        fill=_shade(palette.primary, 0.72),
    )
    draw.rounded_rectangle(
        [x, y, x + w, y + h], radius=12, fill=_rgb(palette.primary)
    )
    draw.rectangle(
        [x, y, x + int(0.16 * PX), y + h], fill=_rgb(palette.accent)
    )

    size = 30 if len(slide.title) <= 34 else 26 if len(slide.title) <= 52 else 22
    font = _font(int(size * SCALE), bold=True)
    _draw_text(
        draw,
        (x + int(0.34 * PX), y, w - int(0.5 * PX), h),
        slide.title,
        font,
        (255, 255, 255),
        valign="middle",
    )


def _draw_footer(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, index: int, total: int
) -> None:
    palette = spec.palette
    font = _font(int(9 * SCALE))
    if spec.author:
        draw.text(
            (int(0.8 * PX), int(7.04 * PX)),
            spec.author,
            font=font,
            fill=_rgb(palette.muted),
        )
    label = f"{index} / {total}"
    label_width = draw.textlength(label, font=font)
    draw.text(
        (WIDTH - int(0.8 * PX) - label_width, int(7.04 * PX)),
        label,
        font=font,
        fill=_rgb(palette.muted),
    )


def _draw_bullets(
    draw: ImageDraw.ImageDraw,
    spec: DeckSpec,
    items,
    x: int,
    y: int,
    w: int,
    h: int,
) -> None:
    cursor = y
    for item in items:
        size = 20 if item.level == 0 else 16
        font = _font(int(size * SCALE), bold=(item.level == 0))
        color = _rgb(spec.palette.primary if item.level == 0 else spec.palette.text)
        prefix = "•  " if item.level == 0 else "–  "
        indent = int(0.3 * PX * item.level)
        text = prefix + item.text
        lines = _wrap(draw, text, font, w - indent)
        ascent, descent = font.getmetrics()
        line_height = int((ascent + descent) * 1.2)
        for line in lines:
            draw.text((x + indent, cursor), line, font=font, fill=color)
            cursor += line_height
        cursor += int(0.06 * PX)
        if cursor > y + h:
            break


def _body_top(slide: SlideSpec) -> int:
    return int((2.0 if slide.subtitle else 1.7) * PX)


def _draw_two_column(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    palette = spec.palette
    top = _body_top(slide)
    width = int(5.72 * PX)
    gap = int(0.3 * PX)
    left = int(0.8 * PX)

    for column, x in zip(slide.columns, (left, left + width + gap)):
        draw.rounded_rectangle(
            [x, top, x + width, top + int(4.7 * PX)],
            radius=14,
            fill=_mix(palette.background, palette.accent, 0.06),
            outline=_shade(palette.muted, 1.25),
            width=2,
        )
        if column.heading:
            _draw_text(
                draw,
                (x + int(0.2 * PX), top + int(0.15 * PX), width - int(0.4 * PX), int(0.5 * PX)),
                column.heading,
                _font(int(17 * SCALE), bold=True),
                _rgb(palette.accent),
            )
        _draw_bullets(
            draw,
            spec,
            column.bullets,
            x + int(0.2 * PX),
            top + int(0.75 * PX),
            width - int(0.4 * PX),
            int(3.75 * PX),
        )


def _draw_table(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    block = slide.table
    if block is None:
        return

    palette = spec.palette
    left = int(0.8 * PX)
    top = _body_top(slide) + int(0.1 * PX)
    width = int(11.7 * PX)
    cols = len(block.headers)
    rows = len(block.rows) + 1
    col_width = width / cols
    row_height = int(0.5 * PX)

    for row in range(rows):
        for col in range(cols):
            x = left + col * col_width
            y = top + row * row_height
            if row == 0:
                fill = _rgb(palette.primary)
                color = (255, 255, 255)
                font = _font(int(14 * SCALE), bold=True)
            else:
                fill = (
                    _rgb(palette.background)
                    if row % 2 == 1
                    else _mix(palette.background, palette.primary, 0.06)
                )
                color = _rgb(palette.text)
                font = _font(int(13 * SCALE))

            draw.rectangle(
                [x, y, x + col_width, y + row_height],
                fill=fill,
                outline=_shade(palette.muted, 1.4),
            )
            value = (
                block.headers[col]
                if row == 0
                else block.rows[row - 1][col]
            )
            _draw_text(
                draw,
                (int(x + 8), y + 4, int(col_width - 16), row_height - 8),
                value,
                font,
                color,
                valign="middle",
            )


def _draw_title_slide(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    palette = spec.palette
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=_rgb(palette.primary))
    draw.rectangle(
        [int(0.9 * PX), int(2.35 * PX), int(2.5 * PX), int(2.47 * PX)],
        fill=_rgb(palette.accent),
    )
    _draw_text(
        draw,
        (int(0.9 * PX), int(2.7 * PX), int(11.5 * PX), int(1.6 * PX)),
        slide.title,
        _font(int(40 * SCALE), bold=True),
        (255, 255, 255),
    )
    if slide.subtitle:
        _draw_text(
            draw,
            (int(0.9 * PX), int(4.45 * PX), int(11.5 * PX), int(0.9 * PX)),
            slide.subtitle,
            _font(int(20 * SCALE)),
            _shade(palette.background, 0.88),
        )
    if spec.author:
        draw.text(
            (int(0.9 * PX), int(6.35 * PX)),
            spec.author,
            font=_font(int(14 * SCALE)),
            fill=_shade(palette.background, 0.7),
        )


def _draw_section(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    palette = spec.palette
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=_rgb(palette.background))
    draw.rectangle(
        [0, 0, int(0.35 * PX), HEIGHT], fill=_rgb(palette.accent)
    )
    draw.text(
        (int(1.0 * PX), int(2.1 * PX)),
        "§",
        font=_font(int(72 * SCALE), bold=True),
        fill=_rgb(palette.accent),
    )
    _draw_text(
        draw,
        (int(1.0 * PX), int(3.4 * PX), int(11.0 * PX), int(1.0 * PX)),
        slide.title,
        _font(int(36 * SCALE), bold=True),
        _rgb(palette.primary),
    )
    if slide.subtitle:
        _draw_text(
            draw,
            (int(1.0 * PX), int(4.55 * PX), int(11.0 * PX), int(0.8 * PX)),
            slide.subtitle,
            _font(int(18 * SCALE)),
            _rgb(palette.text),
        )


def _draw_quote(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    palette = spec.palette
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=_rgb(palette.background))
    draw.text(
        (int(0.8 * PX), int(0.5 * PX)),
        "“",
        font=_font(int(120 * SCALE), bold=True),
        fill=_rgb(palette.accent),
    )
    _draw_text(
        draw,
        (int(1.2 * PX), int(2.1 * PX), int(11.0 * PX), int(2.6 * PX)),
        slide.title,
        _font(int(26 * SCALE)),
        _rgb(palette.primary),
    )
    if slide.subtitle:
        draw.text(
            (int(1.2 * PX), int(4.95 * PX)),
            slide.subtitle,
            font=_font(int(16 * SCALE)),
            fill=_rgb(palette.muted),
        )


def _draw_closing(
    draw: ImageDraw.ImageDraw, spec: DeckSpec, slide: SlideSpec
) -> None:
    palette = spec.palette
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=_rgb(palette.primary))
    _draw_text(
        draw,
        (int(0.9 * PX), int(2.6 * PX), int(11.5 * PX), int(1.2 * PX)),
        slide.title,
        _font(int(44 * SCALE), bold=True),
        (255, 255, 255),
        align="center",
    )
    if slide.subtitle:
        _draw_text(
            draw,
            (int(0.9 * PX), int(3.9 * PX), int(11.5 * PX), int(0.8 * PX)),
            slide.subtitle,
            _font(int(20 * SCALE)),
            _shade(palette.background, 0.85),
            align="center",
        )
    if spec.author:
        _draw_text(
            draw,
            (int(0.9 * PX), int(5.2 * PX), int(11.5 * PX), int(0.5 * PX)),
            spec.author,
            _font(int(14 * SCALE)),
            _shade(palette.background, 0.7),
            align="center",
        )


def _render_pillow(spec: DeckSpec, out_dir: Path) -> list[Path]:
    paths: list[Path] = []
    total = len(spec.slides)

    for index, slide in enumerate(spec.slides, start=1):
        image = Image.new("RGB", (WIDTH, HEIGHT), _rgb(spec.palette.background))
        draw = ImageDraw.Draw(image)

        if slide.layout == "title":
            _draw_title_slide(draw, spec, slide)
        elif slide.layout == "section":
            _draw_section(draw, spec, slide)
        elif slide.layout == "quote":
            _draw_quote(draw, spec, slide)
        elif slide.layout == "closing":
            _draw_closing(draw, spec, slide)
        else:
            _draw_header(draw, spec, slide)
            if slide.subtitle:
                _draw_text(
                    draw,
                    (
                        int(0.8 * PX),
                        int(1.48 * PX),
                        int(11.7 * PX),
                        int(0.35 * PX),
                    ),
                    slide.subtitle,
                    _font(int(13 * SCALE)),
                    _rgb(spec.palette.muted),
                )
            if slide.layout == "bullets":
                _draw_bullets(
                    draw,
                    spec,
                    slide.bullets,
                    int(0.8 * PX),
                    _body_top(slide),
                    int(11.7 * PX),
                    int(5.1 * PX),
                )
            elif slide.layout == "two_column":
                _draw_two_column(draw, spec, slide)
            elif slide.layout == "table":
                _draw_table(draw, spec, slide)
            _draw_footer(draw, spec, index, total)

        path = out_dir / f"slide-{index:02d}.png"
        image.save(path, format="PNG")
        paths.append(path)

    return paths


def _render_libreoffice(
    soffice: str, pptx_path: Path, out_dir: Path
) -> list[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        command = [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            temp_dir,
            str(pptx_path),
        ]
        subprocess.run(command, capture_output=True, timeout=120, check=False)
        pdf_path = Path(temp_dir) / f"{pptx_path.stem}.pdf"
        if not pdf_path.is_file():
            raise RuntimeError("LibreOffice không tạo được PDF")

        import pymupdf

        document = pymupdf.open(pdf_path)
        paths: list[Path] = []
        try:
            for index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(DPI / 72.0, DPI / 72.0)
                )
                path = out_dir / f"slide-{index:02d}.png"
                pixmap.save(path)
                paths.append(path)
        finally:
            document.close()
        return paths


def render_preview(
    pptx_path: Path, spec: DeckSpec, out_dir: Path
) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("slide-*.png"):
        stale.unlink()

    soffice = find_soffice()
    if soffice:
        try:
            return _render_libreoffice(soffice, Path(pptx_path), out_dir)
        except Exception:
            pass

    return _render_pillow(spec, out_dir)
