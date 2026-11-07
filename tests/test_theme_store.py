# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import tomli_w

from app import theme_store
from app.config import ConfigError


def _theme_data(name: str = "Demo") -> dict:
    return {
        "theme": {
            "id": "demo",
            "name": name,
            "description": "Demo theme",
            "style": "demo",
            "tags": ["demo"],
            "renderer": "theme",
            "font": "Lexend",
        },
        "palette": {
            "bg": [250, 250, 248],
            "card": [255, 255, 255],
            "accent": [227, 30, 36],
            "text": [17, 17, 17],
            "muted": [110, 110, 110],
        },
        "colors": {
            "background": {"hex": "#FAFAF8", "rgb": [250, 250, 248]},
            "card": {
                "bg_hex": "#FFFFFF",
                "bg_rgb": [255, 255, 255],
                "border_hex": "#E2E8F0",
                "border_rgb": [226, 232, 240],
                "border_width_pt": 1.0,
            },
            "accent": {
                "primary_hex": "#E31E24",
                "primary_rgb": [227, 30, 36],
                "secondary_hex": "#F59E0B",
                "secondary_rgb": [245, 158, 11],
                "success_hex": "#10B981",
                "success_rgb": [16, 185, 129],
            },
            "text": {
                "primary_hex": "#111111",
                "primary_rgb": [17, 17, 17],
                "secondary_hex": "#6E6E6E",
                "secondary_rgb": [110, 110, 110],
                "accent_hex": "#E31E24",
                "accent_rgb": [227, 30, 36],
            },
        },
        "typography": {
            "title_hero": {"size_pt": 44},
            "title_section": {"size_pt": 26},
            "card_title": {"size_pt": 18},
            "card_body": {"size_pt": 13},
            "big_metric": {"size_pt": 48},
        },
        "layouts": {
            "three_cards": {
                "header": {
                    "left_inch": 1.0,
                    "top_inch": 0.8,
                    "width_inch": 11.333,
                    "height_inch": 0.8,
                }
            },
            "hero_title": {},
            "metric_highlights": {},
        },
    }


def _make_theme(tmp_path: Path) -> tuple[Path, Path]:
    themes = tmp_path / "themes"
    themes.mkdir()
    (themes / "demo.toml").write_text(
        tomli_w.dumps(_theme_data()), encoding="utf-8"
    )
    return themes, themes / "active"


def test_ensure_active_copies_backups(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    copied = theme_store.ensure_active_themes(themes, active)
    assert copied == 1
    assert (active / "demo.toml").is_file()
    assert theme_store.ensure_active_themes(themes, active) == 0


def test_create_alias_inherits_active_edits(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    active_file = active / "demo.toml"
    data = tomllib.loads(active_file.read_text(encoding="utf-8"))
    data["theme"]["name"] = "Demo EDITED"
    active_file.write_text(tomli_w.dumps(data), encoding="utf-8")

    new_id = theme_store.create_alias("demo", "my_alias", None, active)

    assert new_id == "demo.my_alias"
    alias = tomllib.loads(
        (active / "demo.my_alias.toml").read_text(encoding="utf-8")
    )
    assert alias["theme"]["id"] == "demo.my_alias"
    assert alias["theme"]["alias_of"] == "demo"
    assert "EDITED" in alias["theme"]["name"]


def test_alias_validation() -> None:
    for bad in ("", "bad alias", "a.b", "a/b", "a?b", "主题"):
        with pytest.raises(ConfigError):
            theme_store.validate_alias(bad)
    assert theme_store.validate_alias("Báo-cáo_01") == "Báo-cáo_01"


def test_reset_alias_uses_active_system_copy(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)

    system_file = active / "demo.toml"
    data = tomllib.loads(system_file.read_text(encoding="utf-8"))
    data["theme"]["name"] = "Demo ACTIVE"
    system_file.write_text(tomli_w.dumps(data), encoding="utf-8")

    theme_store.create_alias("demo", "alias", None, active)
    alias_file = active / "demo.alias.toml"
    alias = tomllib.loads(alias_file.read_text(encoding="utf-8"))
    alias["theme"]["name"] = "Changed"
    alias_file.write_text(tomli_w.dumps(alias), encoding="utf-8")

    new_id = theme_store.reset_theme("demo.alias", active, themes)

    assert new_id == "demo.alias"
    reset = tomllib.loads(alias_file.read_text(encoding="utf-8"))
    assert reset["theme"]["id"] == "demo.alias"
    assert reset["theme"]["name"] == "Demo ACTIVE - alias"


def test_reset_system_uses_backup(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)

    system_file = active / "demo.toml"
    data = tomllib.loads(system_file.read_text(encoding="utf-8"))
    data["theme"]["name"] = "Demo EDITED"
    system_file.write_text(tomli_w.dumps(data), encoding="utf-8")

    new_id = theme_store.reset_theme("demo", active, themes)

    assert new_id == "demo"
    reset = tomllib.loads(system_file.read_text(encoding="utf-8"))
    assert reset["theme"]["name"] == "Demo"


def test_delete_only_alias(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)

    with pytest.raises(ConfigError, match="alias"):
        theme_store.delete_theme("demo", active)

    theme_store.create_alias("demo", "alias", None, active)
    theme_store.delete_theme("demo.alias", active)
    assert not (active / "demo.alias.toml").exists()


def test_save_theme_forces_file_identity(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    data = _theme_data()
    data["theme"]["id"] = "hacked"
    new_id = theme_store.save_theme(
        "demo", tomli_w.dumps(data), active
    )
    assert new_id == "demo"
    saved = tomllib.loads(
        (active / "demo.toml").read_text(encoding="utf-8")
    )
    assert saved["theme"]["id"] == "demo"


def test_empty_alias_rejected(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    with pytest.raises(ConfigError, match="không được để trống"):
        theme_store.create_alias("demo", "", None, active, themes)


def test_alias_matching_original_theme_rejected(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    for name in ("demo", "Demo"):
        with pytest.raises(ConfigError, match="trùng"):
            theme_store.create_alias("demo", name, None, active, themes)


def test_save_rejects_invalid_theme(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    invalid = '[theme]\nid = "demo"\nname = "Demo"\n'
    with pytest.raises(ConfigError, match="palette"):
        theme_store.save_theme("demo", invalid, active)
    assert "palette" in (active / "demo.toml").read_text(encoding="utf-8")


def test_create_alias_rejects_invalid_content(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    invalid = '[theme]\nid = "demo"\nname = "Demo"\n'
    with pytest.raises(ConfigError, match="palette"):
        theme_store.create_alias("demo", "bad", invalid, active, themes)
    assert not (active / "demo.bad.toml").exists()


def test_catalog_skips_invalid_active_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import templates_catalog

    active = tmp_path / "active"
    active.mkdir()
    (active / "demo.toml").write_text(
        tomli_w.dumps(_theme_data()), encoding="utf-8"
    )
    (active / "broken.toml").write_text(
        '[theme]\nid = "broken"\nname = "Broken"\n', encoding="utf-8"
    )
    monkeypatch.setattr(templates_catalog, "ACTIVE_DIR", active)
    monkeypatch.setattr(
        templates_catalog, "ensure_active_themes", lambda: 0
    )
    try:
        items = templates_catalog.refresh_templates()
        ids = {item.id for item in items}
        assert "demo" in ids
        assert "broken" not in ids
    finally:
        monkeypatch.undo()
        templates_catalog.refresh_templates()


def test_sync_active_overwrites_system_keeps_alias(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)

    system_file = active / "demo.toml"
    data = tomllib.loads(system_file.read_text(encoding="utf-8"))
    data["theme"]["name"] = "Edited"
    system_file.write_text(tomli_w.dumps(data), encoding="utf-8")
    theme_store.create_alias("demo", "alias", None, active)

    copied = theme_store.sync_active_themes(True, themes, active)

    assert copied == 1
    restored = tomllib.loads(system_file.read_text(encoding="utf-8"))
    assert restored["theme"]["name"] == "Demo"
    assert (active / "demo.alias.toml").is_file()


def test_ensure_active_does_not_overwrite(tmp_path: Path) -> None:
    themes, active = _make_theme(tmp_path)
    theme_store.ensure_active_themes(themes, active)
    system_file = active / "demo.toml"
    data = tomllib.loads(system_file.read_text(encoding="utf-8"))
    data["theme"]["name"] = "Edited"
    system_file.write_text(tomli_w.dumps(data), encoding="utf-8")

    theme_store.ensure_active_themes(themes, active)

    kept = tomllib.loads(system_file.read_text(encoding="utf-8"))
    assert kept["theme"]["name"] == "Edited"
