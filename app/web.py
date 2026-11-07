# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import storage, theme_store
from . import tags as tag_utils
from .boho_render import render_deck_boho
from .config import ConfigError, REPO_ROOT, Settings, lan_url, load_settings
from .copy_slide_render import render_deck_copy_slides
from .llm import LLMClient, LLMError
from .preview import render_preview
from .render import render_deck
from .template_render import render_deck_with_template
from .templates_catalog import (
    apply_template_palette,
    get_template,
    grouped_templates,
    refresh_templates,
    template_file,
)
from .theme_render import render_deck_theme

logger = logging.getLogger(__name__)

WEB_DIR = REPO_ROOT / "web"
MAX_TITLE = 200
PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def _url_without(path: str, params: dict[str, str]) -> str:
    """Ghép URL, giữ lại các tham số được truyền vào."""
    if not params:
        return path
    return f"{path}?{urlencode(params)}"


def _split_tags(
    values: list[str] | None, single: str | None = None
) -> list[str]:
    """Gom tag từ query string: hỗ trợ `?tags=a&tags=b` và `?tags=a,b`."""
    raw: list[str] = []
    if single:
        raw.append(single)
    for value in values or []:
        raw.extend(str(value).split(","))
    return tag_utils.limit_filter_tags(raw)


def write_deck(spec, meta, out_path: Path) -> None:
    if meta.renderer == "flat":
        render_deck(spec, out_path)
    elif meta.renderer == "boho":
        render_deck_boho(spec, meta, out_path)
    elif meta.renderer == "copy":
        render_deck_copy_slides(spec, meta, out_path)
    elif meta.renderer == "theme":
        render_deck_theme(spec, meta, out_path)
    else:
        template_path = template_file(meta)
        if template_path is None:
            render_deck(spec, out_path)
        else:
            render_deck_with_template(spec, template_path, out_path)


def create_app(
    settings: Settings | None = None,
    llm_factory: Callable[[Settings], LLMClient] | None = None,
    root: Path | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    factory = llm_factory or (lambda current: LLMClient(current))
    base = Path(root) if root is not None else REPO_ROOT
    output_dir = base / "output"
    server_url = lan_url(settings)

    try:
        storage.migrate_legacy_inputs(root=base)
    except Exception:
        logger.exception("Migrate input cũ thất bại")

    template_groups = grouped_templates()

    app = FastAPI(title="Demanus", version="0.1.0")
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
    fonts_dir = REPO_ROOT / "src" / "fonts"
    if fonts_dir.is_dir():
        app.mount(
            "/fonts",
            StaticFiles(directory=str(fonts_dir)),
            name="fonts",
        )
    icons_dir = REPO_ROOT / "src" / "icons"
    if icons_dir.is_dir():
        app.mount(
            "/icons",
            StaticFiles(directory=str(icons_dir)),
            name="icons",
        )

    def render_index(
        request: Request,
        error: str | None = None,
        status_code: int = 200,
        form: dict | None = None,
        tags_filter: list[str] | None = None,
        tag_query: str | None = None,
        query: str | None = None,
        reuse: dict | None = None,
        message: str | None = None,
    ):
        selected_tags = list(tags_filter or [])
        records = storage.list_inputs(
            tags=selected_tags, search=query, root=base
        )
        query_norm = storage.normalize_search(query or "")
        inputs = []
        for record in records:
            outputs = storage.outputs_for(record, root=base)
            matched = [
                output
                for output in outputs
                if query_norm
                and query_norm in storage.normalize_search(output.slug)
            ]
            inputs.append(
                {
                    "record": record,
                    "description": storage.read_text(
                        record.description_hash, base
                    )[:160],
                    "outputs": list(reversed(outputs)),
                    "newest": outputs[-1] if outputs else None,
                    "has_output": bool(outputs),
                    "matched_outputs": matched,
                    "matched_slugs": {output.slug for output in matched},
                    "expanded": bool(matched),
                }
            )

        linked = {
            slug
            for record in storage.list_inputs(root=base)
            for slug in record.output_slugs
        }
        orphans = [
            output
            for output in storage.list_outputs(root=base)
            if output.slug not in linked
        ]
        if query_norm:
            orphans = [
                output
                for output in orphans
                if query_norm in storage.normalize_search(output.slug)
            ]

        preserve: dict[str, str] = {}
        if query:
            preserve["q"] = query
        if tag_query:
            preserve["tq"] = tag_query
        search_hidden: dict[str, str] = {}
        if selected_tags:
            search_hidden["tags"] = ",".join(selected_tags)
        if tag_query:
            search_hidden["tq"] = tag_query
        search_clear_url = _url_without("/", search_hidden)
        tag_links = {
            name: _url_without("/", {"tags": name, **preserve})
            for name in storage.list_tags(root=base)
        }
        tags_layout = tag_utils.build_tag_layout(
            dom_id="tags",
            title="Tags",
            counts=storage.tag_counts(root=base),
            selected=selected_tags,
            query=tag_query or "",
            search_param="tq",
            filter_param="tags",
            hidden_fields={"q": query} if query else {},
            delete_base="/tags",
            clear_url=_url_without("/", preserve),
        )
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "inputs": inputs,
                "orphans": orphans,
                "input_tags_layout": tags_layout,
                "search_hidden": search_hidden,
                "search_clear_url": search_clear_url,
                "query": query or "",
                "tag_links": tag_links,
                "tags": storage.list_tags(root=base),
                "template_groups": template_groups,
                "server_url": server_url,
                "error": error,
                "form": form or {},
                "reuse": reuse,
                "message": message,
            },
            status_code=status_code,
        )

    def resolve_pptx(slug: str) -> Path:
        try:
            path = storage.safe_path(output_dir, f"{slug}.pptx")
        except storage.StorageError as exc:
            raise HTTPException(status_code=404, detail="Không tìm thấy deck") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy deck")
        return path

    async def render_record(record: storage.InputRecord, template: str) -> str:
        meta = get_template(template)
        if meta is None:
            raise storage.StorageError("Template không hợp lệ.")

        storage.update_status(record.id, "generating", root=base)
        try:
            client = factory(settings)
            prompt_template = "flat" if meta.renderer == "copy" else template
            spec, _usage = await client.generate_spec(
                record.title,
                storage.read_text(record.details_hash, base),
                template=prompt_template,
                description=storage.read_text(record.description_hash, base),
            )
            out_path = storage.allocate_output(record.title, record.id, root=base)
            write_deck(spec, meta, out_path)

            slug = out_path.stem
            sidecar = out_path.parent / slug
            sidecar.mkdir(parents=True, exist_ok=True)
            (sidecar / "spec.json").write_text(
                spec.model_dump_json(indent=2), encoding="utf-8"
            )
            render_preview(
                out_path,
                apply_template_palette(spec, meta),
                sidecar / "preview",
            )
            storage.append_output(record.id, slug, root=base)
            storage.update_status(record.id, "done", root=base)
        except Exception:
            storage.update_status(record.id, "failed", root=base)
            raise
        return slug

    @app.get("/", response_class=HTMLResponse)
    async def index(
        request: Request,
        tag: str | None = Query(None),
        tags: list[str] | None = Query(None),
        tq: str | None = Query(None),
        q: str | None = Query(None),
        use: str | None = Query(None),
        msg: str | None = Query(None),
    ):
        selected_tags = _split_tags(tags, tag)
        reuse = None
        if use:
            try:
                record = storage.get_input(use, root=base)
            except (storage.StorageError, FileNotFoundError):
                return render_index(
                    request,
                    "Không tìm thấy input.",
                    404,
                    tags_filter=selected_tags,
                    tag_query=tq,
                    query=q,
                    message=msg,
                )
            selected = (
                get_template(record.template) if record.template else None
            )
            reuse = {
                "id": record.id,
                "title": record.title,
                "description": storage.read_text(record.description_hash, base),
                "details": storage.read_text(record.details_hash, base),
                "tags": record.tags,
                "template": selected.id if selected else record.template,
            }
        return render_index(
            request,
            tags_filter=selected_tags,
            tag_query=tq,
            query=q,
            reuse=reuse,
            message=msg,
        )

    @app.get("/review", response_class=HTMLResponse)
    async def review(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={
                "decks": storage.list_outputs(root=base),
                "server_url": server_url,
            },
        )

    def render_themes(
        request: Request,
        theme: str | None = None,
        error: str | None = None,
        status_code: int = 200,
        content_override: str | None = None,
        alias_override: str | None = None,
    ):
        refresh_templates()
        entries = theme_store.list_theme_entries()
        system_themes = [item for item in entries if not item.is_alias]
        user_themes = [item for item in entries if item.is_alias]
        selected = next((item for item in entries if item.id == theme), None)
        if selected is None and system_themes:
            selected = system_themes[0]
        content = (
            content_override
            if content_override is not None
            else (
                theme_store.read_theme_text(selected.id)
                if selected
                else ""
            )
        )
        return templates.TemplateResponse(
            request=request,
            name="themes.html",
            context={
                "system_themes": system_themes,
                "user_themes": user_themes,
                "selected": selected,
                "content": content,
                "alias": (
                    alias_override
                    if alias_override is not None
                    else (selected.alias if selected else "")
                ),
                "error": error,
                "server_url": server_url,
            },
            status_code=status_code,
        )

    @app.get("/themes", response_class=HTMLResponse)
    async def themes_page(
        request: Request,
        theme: str | None = Query(None),
        error: str | None = Query(None),
    ):
        return render_themes(request, theme=theme, error=error)

    @app.post("/themes/save")
    async def themes_save(
        request: Request,
        theme: str = Form(""),
        alias: str = Form(""),
        content: str = Form(""),
        action: str = Form("save"),
    ):
        try:
            if action == "alias":
                new_id = theme_store.create_alias(theme, alias, content)
            else:
                new_id = theme_store.save_theme(theme, content)
            refresh_templates()
        except ConfigError as exc:
            return render_themes(
                request,
                theme=theme,
                error=(
                    f"Không lưu được theme: {exc}. "
                    "File hợp lệ cần [theme], [palette], [colors.*], "
                    "[typography], [layouts.three_cards.header]."
                ),
                status_code=400,
                content_override=content,
                alias_override=alias,
            )
        return RedirectResponse(
            f"/themes?theme={quote(new_id)}", status_code=303
        )

    @app.post("/themes/{theme_id}/reset")
    async def themes_reset(
        request: Request,
        theme_id: str,
        confirm: str = Form(""),
    ):
        if confirm != "yes":
            raise HTTPException(
                status_code=400, detail="Thiếu xác nhận reset"
            )
        try:
            new_id = theme_store.reset_theme(theme_id)
        except ConfigError as exc:
            return render_themes(
                request,
                theme=theme_id,
                error=f"Không reset được theme: {exc}",
                status_code=400,
            )
        refresh_templates()
        return RedirectResponse(
            f"/themes?theme={quote(new_id)}", status_code=303
        )

    @app.post("/themes/{theme_id}/delete")
    async def themes_delete(
        request: Request,
        theme_id: str,
        confirm: str = Form(""),
    ):
        if confirm != "yes":
            raise HTTPException(
                status_code=400, detail="Thiếu xác nhận xoá"
            )
        try:
            theme_store.delete_theme(theme_id)
        except ConfigError as exc:
            return render_themes(
                request,
                theme=theme_id,
                error=f"Không xoá được theme: {exc}",
                status_code=400,
            )
        refresh_templates()
        return RedirectResponse("/themes", status_code=303)

    @app.get("/health")
    async def health():
        return {"status": "ok", "url": server_url}

    @app.get("/api/templates")
    async def api_templates():
        return {
            "pptx": [
                {
                    "id": meta.id,
                    "name": meta.display_name(),
                    "description": meta.description,
                }
                for meta in template_groups["pptx"]
            ],
            "themes": [
                {
                    "id": meta.id,
                    "name": meta.display_name(),
                    "parent_id": meta.parent_id,
                    "variant_id": meta.variant_id,
                }
                for meta in template_groups["themes"]
            ],
        }

    @app.post("/generate")
    async def generate(
        request: Request,
        title: str = Form(""),
        description: str = Form(""),
        details: str = Form(""),
        tags: str = Form(""),
        template: str = Form("flat"),
    ):
        title = title.strip()
        description = description.strip()
        details = details.strip()
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        form = {
            "title": title,
            "description": description,
            "details": details,
            "tags": ",".join(tag_list),
            "template": template,
        }

        meta = get_template(template)
        if meta is None:
            return render_index(request, "Template không hợp lệ.", 400, form)
        if not title:
            return render_index(request, "Tiêu đề không được để trống.", 400, form)
        if not description:
            return render_index(request, "Mô tả không được để trống.", 400, form)
        if not details:
            return render_index(request, "Chi tiết không được để trống.", 400, form)

        try:
            record = storage.create_input(
                title,
                description,
                details,
                tags=tag_list,
                template=template,
                root=base,
            )
        except storage.DuplicateTitleError as exc:
            return render_index(
                request,
                f"Tiêu đề đã tồn tại (id {exc.existing_id}).",
                400,
                form,
            )
        except storage.StorageError as exc:
            return render_index(request, str(exc), 400, form)

        try:
            slug = await render_record(record, template)
        except Exception as exc:
            logger.exception("Sinh PPTX thất bại cho input %s", record.id)
            message = "Không thể sinh file. Vui lòng thử lại."
            if isinstance(exc, LLMError):
                message = f"Lỗi gọi model: {exc}"
            return render_index(request, message, 500, form)

        return RedirectResponse(f"/deck/{slug}", status_code=303)

    @app.post("/inputs/{input_id}/generate")
    async def regenerate(
        input_id: str,
        template: str = Form("flat"),
        tags: str | None = Form(None),
    ):
        try:
            record = storage.get_input(input_id, root=base)
        except (storage.StorageError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        if get_template(template) is None:
            raise HTTPException(status_code=400, detail="Template không hợp lệ")

        if tags is not None:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            try:
                record = storage.set_input_tags(input_id, tag_list, root=base)
            except storage.StorageError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not storage.read_text(record.description_hash, base).strip():
            raise HTTPException(
                status_code=400, detail="Mô tả không được để trống."
            )
        if not storage.read_text(record.details_hash, base).strip():
            raise HTTPException(
                status_code=400, detail="Chi tiết không được để trống."
            )

        try:
            slug = await render_record(record, template)
        except LLMError as exc:
            raise HTTPException(
                status_code=500, detail=f"Lỗi gọi model: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Sinh lại PPTX thất bại cho input %s", record.id)
            raise HTTPException(
                status_code=500, detail="Không thể sinh file"
            ) from exc
        return RedirectResponse(f"/deck/{slug}", status_code=303)

    @app.post("/inputs/{input_id}/tags")
    async def update_input_tags(input_id: str, tags: str = Form("")):
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        try:
            storage.set_input_tags(input_id, tag_list, root=base)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        except storage.StorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/inputs/{input_id}/outputs/{slug}/delete")
    async def delete_input_output(input_id: str, slug: str):
        try:
            storage.remove_output(input_id, slug, root=base)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        except storage.StorageError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy output"
            ) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/inputs/{input_id}/delete")
    async def delete_input(input_id: str, confirm: str = Form("")):
        if confirm != "yes":
            raise HTTPException(status_code=400, detail="Thiếu xác nhận xoá")
        try:
            record = storage.get_input(input_id, root=base)
        except (storage.StorageError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy input"
            ) from exc
        if record.status == "generating":
            raise HTTPException(
                status_code=409, detail="Input đang được sinh, thử lại sau."
            )
        count = storage.delete_input(input_id, root=base)
        message = f"Đã xoá input và {count} output."
        return RedirectResponse(
            f"/?msg={quote(message)}", status_code=303
        )

    @app.post("/tags/{tag}/delete")
    async def delete_tag(tag: str):
        storage.delete_tag(tag, root=base)
        return RedirectResponse("/", status_code=303)

    @app.get("/api/inputs/check-title")
    async def check_title(title: str = Query("")):
        status = storage.title_status(title, root=base)
        return {
            "valid": status.valid,
            "duplicate": status.duplicate,
            "normalized": status.normalized,
            "message": status.message,
            "existing_id": status.existing_id,
        }

    @app.get("/api/inputs")
    async def api_inputs():
        payload = []
        for record in storage.list_inputs(root=base):
            outputs = storage.outputs_for(record, root=base)
            payload.append(
                {
                    "id": record.id,
                    "title": record.title,
                    "tags": record.tags,
                    "status": record.status,
                    "created_at": record.created_at,
                    "template": record.template,
                    "output_slug": record.output_slug,
                    "output_slugs": record.output_slugs,
                    "outputs": [
                        {
                            "slug": output.slug,
                            "size_bytes": output.size_bytes,
                            "modified_at": output.modified_at,
                            "has_preview": output.has_preview,
                        }
                        for output in outputs
                    ],
                }
            )
        return payload

    @app.get("/api/tags")
    async def api_tags():
        return {
            "tags": storage.list_tags(root=base),
            "counts": storage.tag_counts(root=base),
        }

    @app.get("/deck/{slug}", response_class=HTMLResponse)
    async def deck(request: Request, slug: str):
        path = resolve_pptx(slug)
        preview_dir = path.parent / path.stem / "preview"
        previews = (
            sorted(item.name for item in preview_dir.glob("slide-*.png"))
            if preview_dir.is_dir()
            else []
        )
        return templates.TemplateResponse(
            request=request,
            name="deck.html",
            context={
                "slug": slug,
                "previews": previews,
                "count": len(previews),
                "server_url": server_url,
            },
        )

    @app.get("/api/decks")
    async def api_decks():
        return [
            {
                "slug": record.slug,
                "size_bytes": record.size_bytes,
                "modified_at": record.modified_at,
                "has_preview": record.has_preview,
            }
            for record in storage.list_outputs(root=base)
        ]

    @app.get("/download/{slug}")
    async def download(slug: str):
        path = resolve_pptx(slug)
        return FileResponse(
            path,
            media_type=PPTX_MEDIA_TYPE,
            filename=f"{slug}.pptx",
        )

    @app.post("/api/decks/{slug}/delete")
    async def delete(slug: str):
        try:
            storage.delete_output(slug, root=base)
        except (storage.StorageError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy deck"
            ) from exc
        return RedirectResponse("/review", status_code=303)

    @app.get("/preview/{slug}/{index}")
    async def preview(slug: str, index: int):
        try:
            sidecar = storage.safe_path(output_dir, slug)
        except storage.StorageError as exc:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy preview"
            ) from exc
        if index < 1:
            raise HTTPException(status_code=404, detail="Không tìm thấy preview")

        path = sidecar / "preview" / f"slide-{index:02d}.png"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Không tìm thấy preview")
        return FileResponse(path, media_type="image/png")

    return app


app = create_app()
