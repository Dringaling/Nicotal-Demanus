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
make server           # http://0.0.0.0:8765
make dev              # auto-reload
make smoke            # sinh output/_smoke.pptx, không cần API key
make test             # pytest
```

Mô tả (`desc`) không giới hạn ký tự. Nội dung dài được chia thành các chunk
(`chunk_chars`, mặc định 8000 ký tự) trước khi gửi model.

Trên Windows, dùng Git Bash/WSL để chạy `make`, hoặc chạy trực tiếp `uv ...`.

## Truy cập LAN

- `[server] host = "0.0.0.0"` và `port = 8765`.
- `lan_ip` trong `[server]` là IP máy này (mặc định `192.168.1.12`); để trống
  để tự dò.
- Máy khác mở `http://<lan_ip>:8765`; cần mở firewall cho cổng 8765.
- Giao diện: `/` tạo deck, `/review` xem thumbnail tất cả deck,
  `/deck/<slug>` lật slide.

## Cấu trúc

- `app/config.py` — nạp cấu hình, secret, đường dẫn.
- `app/schema.py` — Pydantic `DeckSpec`.
- `app/prompts.py` — system prompt ổn định + JSON schema.
- `app/llm.py` — client DeepInfra, retry, cache.
- `app/render.py` — `DeckSpec` → `.pptx`.
- `app/template_render.py` — dựng `.pptx` từ template gốc (prototype).
- `app/storage.py` — `input/<hash>.toml`, `output/<slug>.pptx`.
- `app/preview.py` — `.pptx` → PNG 150 DPI.
- `app/web.py` — FastAPI + Jinja2.
- `web/` — template HTML, CSS, JS.
- `templates/` — file `.pptx` mẫu gốc (giữ nguyên).
