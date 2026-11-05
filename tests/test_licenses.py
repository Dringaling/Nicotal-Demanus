# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agpl_license_file() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("                    GNU AFFERO GENERAL PUBLIC LICENSE")
    assert "Version 3, 19 November 2007" in text


def test_mpl_license_file() -> None:
    text = (ROOT / "LICENSE.MPL-2.0").read_text(encoding="utf-8")
    assert text.startswith("Mozilla Public License Version 2.0")
    assert "2. License Grants and Conditions" in text


def test_notice_has_exception_and_mpl_policy() -> None:
    text = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "SPECIAL EXCEPTION FOR DOCUMENT PREVIEW MODULE" in text
    assert "aspose.slides for Python" in text
    assert "Mozilla Public License 2.0 modules" in text


def test_licenses_md_policy_table() -> None:
    text = (ROOT / "LICENSES.md").read_text(encoding="utf-8")
    assert "AGPL-3.0-or-later" in text
    assert "MPL-2.0" in text
    assert "app/preview/aspose.py" in text
    assert "| Phạm vi | Giấy phép | Ghi chú |" in text


def test_pip_licenses_in_dev_dependencies() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["dependency-groups"]["dev"]
    assert any(item.startswith("pip-licenses") for item in dev)


def test_make_licenses_target() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "licenses:" in text
    assert "THIRD_PARTY_LICENSES.md" in text
    assert "pip-licenses" in text


def test_third_party_report_exists() -> None:
    text = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    assert "pymupdf" in text.lower()
    assert "python-pptx" in text.lower()


def test_aspose_documented_as_proprietary() -> None:
    text = (ROOT / "LICENSES.md").read_text(encoding="utf-8").lower()
    assert "aspose-slides" in text
    assert "proprietary" in text
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "Aspose Pty Ltd" in notice


def test_pymupdf_documented_as_agpl() -> None:
    text = (ROOT / "LICENSES.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "pymupdf" in lowered
    assert "AGPL-3.0" in text
    assert "Tương thích" in text or "tương thích" in text


def test_unknown_licenses_are_noted() -> None:
    text = (ROOT / "LICENSES.md").read_text(encoding="utf-8")
    assert "UNKNOWN" in text


def test_spdx_headers_on_project_modules() -> None:
    paths = [ROOT / "demanus.py"]
    paths += sorted((ROOT / "app").rglob("*.py"))
    for path in paths:
        first = path.read_text(encoding="utf-8").splitlines()[0]
        assert first == "# SPDX-License-Identifier: AGPL-3.0-or-later", path


def test_mpl_modules_listed_only_when_present() -> None:
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    if "MPL-2.0 modules" in notice:
        assert "Currently there are no MPL-2.0 modules" in notice


def test_readme_license_section() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Giấy phép" in text
    assert "LICENSE.MPL-2.0" in text
    assert "NOTICE" in text
    assert "THIRD_PARTY_LICENSES.md" in text
    assert "LICENSES.md" in text
