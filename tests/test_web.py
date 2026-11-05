# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from app import storage
from app.config import lan_url, load_settings
from app.llm import LLMError, UsageInfo
from app.sample import sample_deck
from app.templates_catalog import list_templates
from app.web import create_app

CONFIG = Path(__file__).resolve().parents[1] / "config" / "providers.toml"


class FakeClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
        description: str = "",
    ):
        return sample_deck(), UsageInfo()


class FailingClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
        description: str = "",
    ):
        raise LLMError("model không phản hồi")


def make_client(tmp_path: Path, *, failing: bool = False) -> TestClient:
    settings = load_settings(CONFIG)
    factory = (lambda _: FailingClient(settings)) if failing else (
        lambda current: FakeClient(current)
    )
    app = create_app(settings, llm_factory=factory, root=tmp_path)
    return TestClient(app)


def generate(
    client: TestClient,
    *,
    title: str = "Báo cáo",
    description: str = "Mô tả ngắn về mục tiêu",
    details: str = "Nội dung chi tiết từng slide",
    tags: str = "",
    template: str = "flat",
):
    return client.post(
        "/generate",
        data={
            "title": title,
            "description": description,
            "details": details,
            "tags": tags,
            "template": template,
        },
        follow_redirects=False,
    )


def test_index_and_health(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    expected_url = lan_url(load_settings(CONFIG))
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="title"' in response.text
    assert 'name="description"' in response.text
    assert 'name="details"' in response.text
    assert 'name="tags"' in response.text
    assert 'name="template"' in response.text
    assert expected_url in response.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "url": expected_url}


def test_generate_creates_deck(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client)

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/deck/")
    slug = location.rsplit("/", 1)[-1]

    assert (tmp_path / "output" / f"{slug}.pptx").is_file()
    assert (tmp_path / "output" / slug / "spec.json").is_file()
    assert (tmp_path / "output" / slug / "preview").is_dir()

    records = storage.list_inputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].status == "done"
    assert records[0].output_slug == slug

    preview_dir = tmp_path / "output" / slug / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "slide-01.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    deck = client.get(location)
    assert deck.status_code == 200
    assert "carousel" in deck.text
    assert "Tải PPTX" in deck.text


def test_generate_rejects_empty_title(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, title="")
    assert response.status_code == 400
    assert "Tiêu đề" in response.text


def test_generate_rejects_empty_description(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, description="")
    assert response.status_code == 400
    assert "Mô tả" in response.text


def test_generate_rejects_empty_details(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, details="")
    assert response.status_code == 400
    assert "Chi tiết" in response.text


def test_generate_accepts_long_details(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, details="Nội dung chi tiết. " * 1500)
    assert response.status_code == 303


def test_generate_duplicate_title(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert generate(client).status_code == 303
    response = generate(client, details="Nội dung khác")
    assert response.status_code == 400
    assert "Tiêu đề đã tồn tại" in response.text


def test_generate_failure_marks_failed(tmp_path: Path) -> None:
    client = make_client(tmp_path, failing=True)
    response = generate(client)

    assert response.status_code == 500
    assert "Lỗi gọi model" in response.text
    assert "test-key" not in response.text

    records = storage.list_inputs(root=tmp_path)
    assert len(records) == 1
    assert records[0].status == "failed"


def test_api_decks_and_download(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    api = client.get("/api/decks")
    assert api.status_code == 200
    payload = api.json()
    assert len(payload) == 1
    assert payload[0]["slug"] == slug
    assert isinstance(payload[0]["has_preview"], bool)

    download = client.get(f"/download/{slug}")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert download.content[:2] == b"PK"


def test_api_inputs_and_tags(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo",
        "Mô tả",
        "Chi tiết",
        tags=["dental", "research"],
        root=tmp_path,
    )

    inputs = client.get("/api/inputs")
    assert inputs.status_code == 200
    assert inputs.json()[0]["title"] == "Báo cáo"

    tags = client.get("/api/tags")
    assert tags.status_code == 200
    assert "dental" in tags.json()["tags"]
    assert tags.json()["counts"]["dental"] == 1


def test_preview_endpoint(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    preview_dir = tmp_path / "output" / slug / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "slide-01.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    preview = client.get(f"/preview/{slug}/1")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"

    assert client.get(f"/preview/{slug}/999").status_code == 404
    assert client.get("/preview/khong-ton-tai/1").status_code == 404


def test_delete_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    response = client.post(f"/api/decks/{slug}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert not (tmp_path / "output" / f"{slug}.pptx").exists()
    assert not (tmp_path / "output" / slug).exists()


def test_delete_missing_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/decks/khong-ton-tai/delete", follow_redirects=False)
    assert response.status_code == 404


def test_deck_not_found(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/deck/khong-ton-tai").status_code == 404
    assert client.get("/download/khong-ton-tai").status_code == 404


def test_static_asset(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_review_page_lists_decks(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    preview_dir = tmp_path / "output" / slug / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "slide-01.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.get("/review")
    assert response.status_code == 200
    assert slug in response.text
    assert f"/preview/{slug}/1" in response.text
    assert "Xem slide" in response.text


def test_review_page_empty(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/review")
    assert response.status_code == 200
    assert "Chưa có deck nào" in response.text


def test_index_shows_input_thumbnail(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    location = generate(client).headers["location"]
    slug = location.rsplit("/", 1)[-1]

    preview_dir = tmp_path / "output" / slug / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "slide-01.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.get("/")
    assert response.status_code == 200
    assert f"/preview/{slug}/1" in response.text
    assert "thumb-sm" in response.text


def test_tag_filter_and_delete(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo nha khoa",
        "Mô tả",
        "Chi tiết",
        tags=["dental"],
        root=tmp_path,
    )

    filtered = client.get("/?tag=dental")
    assert filtered.status_code == 200
    assert "Báo cáo nha khoa" in filtered.text

    deleted = client.post("/tags/dental/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert storage.list_tags(root=tmp_path) == []
    records = storage.list_inputs(root=tmp_path)
    assert records[0].tags == []


def test_delete_input_keeps_tag(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "Báo cáo",
        "Mô tả",
        "Chi tiết",
        tags=["dental"],
        root=tmp_path,
    )

    response = client.post(
        f"/inputs/{record.id}/delete",
        data={"confirm": "yes"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert storage.list_inputs(root=tmp_path) == []
    assert "dental" in storage.list_tags(root=tmp_path)


def test_index_has_template_select(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="template"' in response.text
    assert "flat" in response.text
    assert "dividing-fractions" in response.text
    assert "boho-minimalist" in response.text
    assert "boho-copy" in response.text
    assert "neo_tech_minimal" in response.text


def test_generate_with_dividing_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="dividing-fractions")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(10)
    assert prs.slide_height == Inches(5.625)


def test_generate_with_boho_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="boho-minimalist")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(13.333)
    first = prs.slides[0]
    pictures = [
        shape
        for shape in first.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert pictures


def test_generate_with_copy_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="boho-copy")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(20)
    assert prs.slide_height == Inches(11.25)
    first = prs.slides[0]
    pictures = [
        shape
        for shape in first.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert pictures


def test_generate_with_theme_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="neo_tech_minimal")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]
    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)
    assert len(prs.slides[0].shapes) >= 2


def test_generate_with_unknown_template(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="khong-ton-tai")
    assert response.status_code == 400
    assert "Template không hợp lệ" in response.text


def test_index_three_columns(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    html = client.get("/").text
    assert ">Tags<" in html
    assert "input-scroll" in html
    assert html.index(">Tags<") < html.index(">Input") < html.index(
        "Tạo bài trình bày"
    )


def test_add_tag_to_existing_input(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "A", "Mô tả", "Chi tiết", tags=["dental"], root=tmp_path
    )
    response = client.post(
        f"/inputs/{record.id}/tags",
        data={"tags": "dental, research"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert storage.get_input(record.id, root=tmp_path).tags == [
        "dental",
        "research",
    ]
    assert "research" in storage.list_tags(root=tmp_path)


def test_remove_tag_from_input_keeps_catalog(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "A", "Mô tả", "Chi tiết", tags=["dental"], root=tmp_path
    )
    response = client.post(
        f"/inputs/{record.id}/tags",
        data={"tags": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert storage.get_input(record.id, root=tmp_path).tags == []
    assert "dental" in storage.list_tags(root=tmp_path)


def test_delete_tag_purges_records(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "A", "Mô tả", "Chi tiết", tags=["dental"], root=tmp_path
    )
    response = client.post("/tags/dental/delete", follow_redirects=False)
    assert response.status_code == 303
    assert storage.list_tags(root=tmp_path) == []
    assert storage.get_input(record.id, root=tmp_path).tags == []


def test_regenerate_appends_outputs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    for _ in range(2):
        response = client.post(
            f"/inputs/{record.id}/generate",
            data={"template": "flat"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    loaded = storage.get_input(record.id, root=tmp_path)
    assert len(loaded.output_slugs) == 2
    assert loaded.output_slugs[0] != loaded.output_slugs[1]
    assert loaded.output_slug == loaded.output_slugs[-1]
    assert loaded.status == "done"


def test_index_lists_outputs_newest_first(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "Báo cáo nha khoa", "Mô tả", "Chi tiết", root=tmp_path
    )
    for _ in range(2):
        client.post(
            f"/inputs/{record.id}/generate",
            data={"template": "flat"},
            follow_redirects=False,
        )

    loaded = storage.get_input(record.id, root=tmp_path)
    oldest, newest = loaded.output_slugs

    for slug in (oldest, newest):
        preview_dir = tmp_path / "output" / slug / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        (preview_dir / "slide-01.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    html = client.get("/").text
    output_list = html.split('class="output-list"', 1)[1]
    slugs = re.findall(r"<strong>([^<]+)</strong>", output_list)
    assert slugs == [newest, oldest]

    summary = html.split('class="input-summary"', 1)[1].split(
        'class="input-details"', 1
    )[0]
    assert "thumb-sm" not in summary
    assert "<img" not in summary
    assert "expand-toggle" in summary
    assert "Xem output" in summary


def test_delete_single_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat"},
        follow_redirects=False,
    )
    loaded = storage.get_input(record.id, root=tmp_path)
    slug = loaded.output_slugs[0]

    response = client.post(
        f"/inputs/{record.id}/outputs/{slug}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    loaded = storage.get_input(record.id, root=tmp_path)
    assert loaded.output_slugs == []
    assert loaded.output_slug == ""
    assert not (tmp_path / "output" / f"{slug}.pptx").exists()
    assert not (tmp_path / "output" / slug).exists()


def test_delete_input_cascades_outputs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat"},
        follow_redirects=False,
    )
    loaded = storage.get_input(record.id, root=tmp_path)
    slug = loaded.output_slugs[0]

    response = client.post(
        f"/inputs/{record.id}/delete",
        data={"confirm": "yes"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert storage.list_inputs(root=tmp_path) == []
    assert not (tmp_path / "output" / f"{slug}.pptx").exists()


def test_delete_input_requires_confirm(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/delete", follow_redirects=False
    )
    assert response.status_code == 400
    assert storage.get_input(record.id, root=tmp_path) is not None


@pytest.mark.parametrize(
    "query", ["bao cao", "BAO CAO", "  báo...cáo!! ", "BÁO CÁO"]
)
def test_search_accent_and_case_insensitive(
    tmp_path: Path, query: str
) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo nha khoa", "Mô tả", "Chi tiết", root=tmp_path
    )
    response = client.get("/", params={"q": query})
    assert response.status_code == 200
    assert "Báo cáo nha khoa" in response.text


def test_search_respects_tag_filter(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo nha khoa", "Mô tả", "Chi tiết", tags=["dental"], root=tmp_path
    )
    storage.create_input(
        "Báo cáo tim mạch", "Mô tả", "Chi tiết", tags=["cardio"], root=tmp_path
    )

    html = client.get("/", params={"tag": "dental", "q": "bao cao"}).text
    assert "Báo cáo nha khoa" in html
    assert "Báo cáo tim mạch" not in html


def test_clear_search_keeps_tag(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input(
        "Báo cáo nha khoa", "Mô tả", "Chi tiết", tags=["dental"], root=tmp_path
    )
    html = client.get("/", params={"tag": "dental", "q": "bao"}).text
    assert 'href="/?tag=dental"' in html


def test_api_inputs_include_outputs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat"},
        follow_redirects=False,
    )

    loaded = storage.get_input(record.id, root=tmp_path)
    payload = client.get("/api/inputs").json()[0]
    assert payload["output_slugs"] == loaded.output_slugs
    assert [item["slug"] for item in payload["outputs"]] == loaded.output_slugs
    assert isinstance(payload["outputs"][0]["has_preview"], bool)


def test_regenerate_failure_marks_failed(tmp_path: Path) -> None:
    client = make_client(tmp_path, failing=True)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat"},
        follow_redirects=False,
    )
    assert response.status_code == 500

    loaded = storage.get_input(record.id, root=tmp_path)
    assert loaded.status == "failed"
    assert loaded.output_slugs == []


def test_check_title_api_shape(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get(
        "/api/inputs/check-title", params={"title": "Báo cáo nha khoa"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "valid",
        "duplicate",
        "normalized",
        "message",
        "existing_id",
    }
    assert payload["valid"] is True
    assert payload["duplicate"] is False
    assert payload["normalized"] == "Báo cáo nha khoa"


def test_check_title_api_invalid(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    for title in ("", "a/b:c?d*e", "a" * 201):
        payload = client.get(
            "/api/inputs/check-title", params={"title": title}
        ).json()
        assert payload["valid"] is False, title
        assert payload["message"]


def test_check_title_api_duplicate(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "Báo cáo", "Mô tả", "Chi tiết", root=tmp_path
    )
    payload = client.get(
        "/api/inputs/check-title", params={"title": "báo cáo"}
    ).json()
    assert payload["duplicate"] is True
    assert payload["existing_id"] == record.id


def test_index_title_check_ui(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    html = client.get("/").text
    assert 'data-check-url="/api/inputs/check-title"' in html
    assert "data-title-error" in html
    assert "data-title-ok" in html
    assert "field-error" in html
    assert "field-ok" in html


def _template_select(html: str, *, last: bool = False) -> str:
    marker = '<select name="template">'
    start = html.rindex(marker) if last else html.index(marker)
    end = html.index("</select>", start)
    return html[start:end]


def _group(html: str, label: str) -> str:
    marker = f'<optgroup label="{label}">'
    start = html.index(marker) + len(marker)
    return html[start : html.index("</optgroup>", start)]


def test_template_dropdown_has_two_groups(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    html = client.get("/").text
    assert '<optgroup label="PPTX Templates">' in html
    assert '<optgroup label="Themes">' in html


def test_pptx_group_entries(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    pptx = _group(client.get("/").text, "PPTX Templates")
    for template_id in (
        "dividing-fractions",
        "operations-integers",
        "blue-medical",
        "cream-green",
        "boho-copy",
        "boho-minimalist",
    ):
        assert f'value="{template_id}"' in pptx


def test_themes_group_entries(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    themes = _group(client.get("/").text, "Themes")
    for template_id in (
        "flat",
        "neo_tech_minimal",
        "neo_tech_minimal__gruvbox",
        "neo_tech_minimal__soft_light",
        "neo_tech_minimal__cappuccino",
        "neo_tech_minimal__latte",
        "neo_tech_minimal__cream_pink",
    ):
        assert f'value="{template_id}"' in themes


def test_default_and_variant_labels(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    html = client.get("/").text
    assert "Neo Tech Minimalist - Mặc định" in html
    assert "Neo Tech Minimalist - Gruvbox" in html
    assert "Flat Demanus - Mặc định" in html


def test_flat_is_selected_by_default(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    select = _template_select(client.get("/").text, last=True)
    option = re.search(r'<option value="flat"[^>]*>', select)
    assert option is not None
    assert "selected" in option.group(0)


def test_default_before_variants(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    themes = _group(client.get("/").text, "Themes")
    assert themes.index('value="neo_tech_minimal"') < themes.index(
        'value="neo_tech_minimal__gruvbox"'
    )


def test_api_templates(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = client.get("/api/templates").json()

    assert set(payload) == {"pptx", "themes"}
    pptx_ids = {item["id"] for item in payload["pptx"]}
    theme_ids = {item["id"] for item in payload["themes"]}
    assert "blue-medical" in pptx_ids
    assert "neo_tech_minimal" not in pptx_ids
    assert "neo_tech_minimal__gruvbox" in theme_ids
    assert "flat" in theme_ids

    variant = next(
        item
        for item in payload["themes"]
        if item["id"] == "neo_tech_minimal__gruvbox"
    )
    assert variant["parent_id"] == "neo_tech_minimal"
    assert variant["variant_id"] == "gruvbox"
    assert variant["name"] == "Neo Tech Minimalist - Gruvbox"


def test_generate_with_variant_uses_variant_colors(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = generate(client, template="neo_tech_minimal__gruvbox")
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]

    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert str(prs.slides[0].shapes[0].fill.fore_color.rgb) == "282828"


def test_empty_group_is_hidden(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.web.grouped_templates",
        lambda: {"pptx": [], "themes": list_templates()},
    )
    client = make_client(tmp_path)
    html = client.get("/").text
    assert "PPTX Templates" not in html
    assert '<optgroup label="Themes">' in html


def test_pptx_templates_not_mixed_into_themes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    themes = _group(client.get("/").text, "Themes")
    for template_id in ("blue-medical", "cream-green", "boho-copy"):
        assert f'value="{template_id}"' not in themes


class RecordingClient:
    calls: list[tuple[str, str, str]] = []

    def __init__(self, settings) -> None:
        self.settings = settings

    async def generate_spec(
        self,
        name: str,
        desc: str,
        template: str = "flat",
        description: str = "",
    ):
        RecordingClient.calls.append((name, desc, description))
        return sample_deck(), UsageInfo()


def make_recording_client(tmp_path: Path) -> TestClient:
    settings = load_settings(CONFIG)
    RecordingClient.calls = []
    app = create_app(
        settings,
        llm_factory=lambda _: RecordingClient(settings),
        root=tmp_path,
    )
    return TestClient(app)


def test_reuse_mode_renders_readonly_form(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "Báo cáo gốc",
        "Mô tả gốc",
        "Chi tiết gốc",
        tags=["dental"],
        root=tmp_path,
    )

    response = client.get("/", params={"use": record.id})

    assert response.status_code == 200
    html = response.text
    assert "Đang dùng input" in html
    assert f'action="/inputs/{record.id}/generate"' in html
    assert "readonly" in html
    assert 'name="title"' not in html
    assert "Báo cáo gốc" in html
    assert "Mô tả gốc" in html
    assert "Chi tiết gốc" in html
    assert "dental" in html
    assert "Tạo mới" in html


def test_reuse_missing_input(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/", params={"use": "deadbeef"})
    assert response.status_code == 404
    assert "Không tìm thấy input" in response.text


def test_reuse_generate_appends_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "Báo cáo gốc", "Mô tả gốc", "Chi tiết gốc", root=tmp_path
    )

    response = client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    loaded = storage.get_input(record.id, root=tmp_path)
    assert len(loaded.output_slugs) == 1
    assert loaded.status == "done"


def test_reuse_ignores_client_payload(tmp_path: Path) -> None:
    client = make_recording_client(tmp_path)
    record = storage.create_input(
        "Gốc", "Mô tả gốc", "Chi tiết gốc", root=tmp_path
    )

    response = client.post(
        f"/inputs/{record.id}/generate",
        data={
            "template": "flat",
            "title": "Bị sửa",
            "description": "Bị sửa",
            "details": "Bị sửa",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert RecordingClient.calls[-1] == ("Gốc", "Chi tiết gốc", "Mô tả gốc")
    assert storage.get_input(record.id, root=tmp_path).title == "Gốc"


def test_reuse_submit_tags_fallback(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "A", "Mô tả", "Chi tiết", tags=["old"], root=tmp_path
    )

    client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat", "tags": "new, other"},
        follow_redirects=False,
    )

    assert storage.get_input(record.id, root=tmp_path).tags == ["new", "other"]
    assert "new" in storage.list_tags(root=tmp_path)


def test_reuse_tag_save_endpoint(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input(
        "A", "Mô tả", "Chi tiết", tags=["old"], root=tmp_path
    )

    html = client.get("/", params={"use": record.id}).text
    assert "data-reuse-tags" in html
    assert f'data-input-id="{record.id}"' in html

    response = client.post(
        f"/inputs/{record.id}/tags",
        data={"tags": "old, new"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert storage.get_input(record.id, root=tmp_path).tags == ["old", "new"]


def test_reuse_empty_details_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "", "", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "flat"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert storage.get_input(record.id, root=tmp_path).output_slugs == []


def test_reuse_with_variant_colors(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/generate",
        data={"template": "neo_tech_minimal__gruvbox"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    slug = response.headers["location"].rsplit("/", 1)[-1]

    prs = Presentation(tmp_path / "output" / f"{slug}.pptx")
    assert str(prs.slides[0].shapes[0].fill.fore_color.rgb) == "282828"


def test_card_has_use_input_link(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    html = client.get("/").text
    assert f'href="/?use={record.id}"' in html
    assert "Dùng input này" in html


def test_delete_overlay_markup(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    html = client.get("/").text

    assert "data-overlay" in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert "Không thể hoàn tác" in html
    assert "data-delete-trigger" in html
    assert "Xoá vĩnh viễn" in html
    assert "Huỷ" in html


def test_no_native_window_confirm(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert "window.confirm" not in script

    client = make_client(tmp_path)
    storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    html = client.get("/").text
    trigger = html.split("data-delete-trigger", 1)[1].split(">", 1)[0]
    assert "confirm(" not in trigger


def test_delete_flash_message(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/delete",
        data={"confirm": "yes"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Đã xoá input và 0 output." in response.text


def test_delete_missing_outputs_still_deletes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    storage.append_output(record.id, "gone", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/delete",
        data={"confirm": "yes"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert storage.list_inputs(root=tmp_path) == []


def test_delete_generating_input_conflict(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)
    storage.update_status(record.id, "generating", root=tmp_path)

    response = client.post(
        f"/inputs/{record.id}/delete",
        data={"confirm": "yes"},
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert storage.get_input(record.id, root=tmp_path) is not None


def test_exit_reuse_mode(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    reuse_html = client.get("/", params={"use": record.id}).text
    assert "Đang dùng input" in reuse_html

    fresh = client.get("/").text
    assert "Đang dùng input" not in fresh
    assert 'name="title"' in fresh


def test_header_brand_and_nav(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    html = client.get("/").text

    assert "Nicotal - Demanus" in html
    assert "<title>Nicotal - Demanus</title>" in html
    assert 'class="topbar-row"' in html
    assert html.count('class="nav-button ') == 2
    assert 'class="nav-button nav-create" href="/">Tạo' in html
    assert 'class="nav-button nav-review" href="/review">Review' in html


def test_header_css_gradient_and_3d() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "web" / "static" / "style.css").read_text(encoding="utf-8")

    assert "background-clip: text" in css
    assert "--brand-gradient: linear-gradient(" in css
    assert "--button-gradient: linear-gradient(" in css
    assert "background: var(--brand-gradient)" in css
    assert "border-bottom: 4px solid var(--rose-border)" in css
    assert "box-shadow: var(--nav-shadow)" in css


def test_input_column_wider_than_form() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "web" / "static" / "style.css").read_text(encoding="utf-8")

    assert (
        "grid-template-columns: 260px minmax(0, 1.6fr) minmax(360px, 1fr)"
        in css
    )


def test_input_summary_has_no_thumbnail(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    html = client.get("/").text
    summary = html.split('class="input-summary"', 1)[1].split(
        'class="input-details"', 1
    )[0]

    assert "<img" not in summary
    assert "thumb-sm" not in summary
    assert "A" in summary


def test_input_card_has_prominent_expand_button(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    html = client.get("/").text

    assert 'class="expand-toggle"' in html
    assert "data-expand" in html
    assert "data-expand-label" in html
    assert "Xem output" in html


def test_input_card_has_no_regen_controls(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    html = client.get("/").text

    assert 'class="regen-form"' not in html
    assert 'aria-label="Template cho lần tạo lại"' not in html
    assert "Tạo lại" not in html


def test_single_generate_control(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    html = client.get("/").text

    assert html.count('<select name="template">') == 1
    assert html.count("Sinh file PPTX") == 1


def test_reuse_mode_has_single_generate_control(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    record = storage.create_input("A", "Mô tả", "Chi tiết", root=tmp_path)

    html = client.get("/", params={"use": record.id}).text

    assert html.count('<select name="template">') == 1
    assert html.count("Sinh file PPTX") == 1


def test_expand_js_updates_label() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")

    assert "data-expand-label" in script
    assert "Thu gọn" in script
    assert "Xem output" in script


def test_header_row_centers_create_button() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "web" / "static" / "style.css").read_text(encoding="utf-8")

    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)" in css
    assert ".nav-create {\n  justify-self: center;" in css


def test_input_details_hidden_rule() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "web" / "static" / "style.css").read_text(encoding="utf-8")

    assert ".input-details[hidden]" in css


def test_template_partials_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    templates = root / "web" / "templates"

    assert (templates / "macros.html").is_file()
    assert (templates / "partials" / "README.md").is_file()
    for name in ("header", "delete_overlay"):
        assert (templates / "partials" / f"{name}.html").is_file()
    assert not (templates / "partials" / "input_card.html").exists()


def test_index_uses_macros() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "web" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert '{% from "macros.html" import' in text
    assert "tags_sidebar(tags, counts, active_tag, query)" in text
    assert "search_bar(active_tag, query)" in text
    assert "input_list(inputs)" in text
    assert "create_form(form, error, template_groups)" in text
    assert "reuse_form(reuse, error, template_groups)" in text
    assert '{% include "partials/delete_overlay.html" %}' in text


def test_css_design_tokens() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "web" / "static" / "style.css").read_text(encoding="utf-8")

    for token in (
        "--brand-gradient",
        "--button-gradient",
        "--brand-size",
        "--nav-padding",
        "--nav-shadow",
        "--card-radius",
        "--gap",
    ):
        assert f"{token}:" in css


def test_macros_have_explicit_parameters() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "web" / "templates" / "macros.html").read_text(
        encoding="utf-8"
    )

    for signature in (
        "{% macro template_select(groups, selected)",
        "{% macro title_field(value)",
        "{% macro textarea_field(name, label",
        "{% macro tag_input(value)",
        "{% macro tag_editor(record)",
        "{% macro reuse_tag_editor(input_id, tags)",
        "{% macro output_item(record, output)",
        "{% macro input_card(item)",
        "{% macro input_list(inputs)",
        "{% macro tags_sidebar(tags, counts, active_tag, query)",
        "{% macro search_bar(active_tag, query)",
        "{% macro create_form(form, error, groups)",
        "{% macro reuse_form(reuse, error, groups)",
    ):
        assert signature in text


def test_static_blocks_stay_includes() -> None:
    root = Path(__file__).resolve().parents[1]
    base = (root / "web" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )
    index = (root / "web" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert '{% include "partials/header.html" %}' in base
    assert '{% include "partials/delete_overlay.html" %}' in index
