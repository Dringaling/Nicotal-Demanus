from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

DPI = 150


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


def render(soffice: str, pptx_path: Path, out_dir: Path) -> list[Path]:
    pptx_path = Path(pptx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
