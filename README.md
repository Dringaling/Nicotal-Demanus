# Demanus

Sinh bài trình bày PowerPoint tiếng Việt từ mô tả, dùng `python-pptx` và
DeepInfra (service tier `flex`).

## Yêu cầu

- `uv` (đã bao gồm Python 3.12).
- Tùy chọn: LibreOffice để preview đúng fidelity (nếu không có, dùng fallback
  Pillow).

## Cài đặt

```bash
cd demanus
make install          # hoặc: uv sync
```

## Cấu hình

- `config/providers.toml`: model, `service_tier`, tham số sinh, server.
- `secret/deepinfra_flex_c79c.env`:

  ```env
  DEEPINFRA_FLEX_C79C=<api-key>
  ```

  Biến môi trường thật (nếu set) được ưu tiên hơn file.

## Chạy

```bash
make server           # http://0.0.0.0:8000
make dev              # auto-reload
make smoke            # sinh output/_smoke.pptx, không cần API key
make test             # pytest
```

Trên Windows, dùng Git Bash/WSL để chạy `make`, hoặc chạy trực tiếp `uv ...`.

## Cấu trúc

- `app/config.py` — nạp cấu hình, secret, đường dẫn.
- `app/schema.py` — Pydantic `DeckSpec`.
- `app/prompts.py` — system prompt ổn định + JSON schema.
- `app/llm.py` — client DeepInfra, retry, cache.
- `app/render.py` — `DeckSpec` → `.pptx`.
- `app/storage.py` — `input/<hash>.toml`, `output/<slug>.pptx`.
- `app/preview.py` — `.pptx` → PNG 150 DPI.
- `app/web.py` — FastAPI + Jinja2.
- `web/` — template HTML, CSS, JS.
- `templates/` — file `.pptx` mẫu gốc (giữ nguyên).
