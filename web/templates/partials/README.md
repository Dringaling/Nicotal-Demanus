# Quy ước template & design tokens

## Quy tắc chọn include hay macro

- **Include** (`{% include "partials/<name>.html" %}`): khối tĩnh, dùng một
  lần trên trang, không phụ thuộc dữ liệu động.
  - `header.html` — brand + nút Tạo/Review, dùng ở `base.html`.
  - `delete_overlay.html` — modal xoá input, dùng ở `index.html`.
- **Macro** (`{% from "macros.html" import ... %}`): khối lặp lại hoặc có
  dữ liệu động. Luôn truyền tham số rõ ràng, không dựa vào context ngầm.

## Include

| File | Dùng ở | Dữ liệu |
|---|---|---|
| `header.html` | `base.html` | `server_url` (không bắt buộc) |
| `delete_overlay.html` | `index.html` | không |

## Macro trong `macros.html`

| Macro | Tham số | Dùng ở |
|---|---|---|
| `template_select` | `groups, selected` | `create_form`, `reuse_form` |
| `title_field` | `value` | `create_form` |
| `textarea_field` | `name, label, value, rows, required, placeholder` | `create_form` |
| `tag_input` | `value` | `create_form` |
| `readonly_text` | `label, value` | `reuse_form` |
| `readonly_textarea` | `label, value, rows` | `reuse_form` |
| `tag_editor` | `record` | `input_card` |
| `reuse_tag_editor` | `input_id, tags` | `reuse_form` |
| `output_item` | `record, output` | `input_card` |
| `input_card` | `item` | `input_list` |
| `input_list` | `inputs` | `index.html` |
| `tags_sidebar` | `tags, counts, active_tag, query` | `index.html` |
| `search_bar` | `active_tag, query` | `index.html` |
| `create_form` | `form, error, groups` | `index.html` |
| `reuse_form` | `reuse, error, groups` | `index.html` |

Khi thêm khối mới:

1. Nếu khối lặp lại hoặc nhận dữ liệu → thêm macro vào `macros.html` với
   tham số tường minh.
2. Nếu khối tĩnh dùng một lần → thêm file vào `partials/` và `include`.
3. Cập nhật bảng trên.

## Bảng màu (đóng băng 16 màu)

Chỉ dùng các màu dưới đây. Không thêm màu ngoài danh sách. Gradient phải lấy
đúng **hai** màu trong bảng.

| Token | Hex |
|---|---|
| `--color-wine-900` | `#1c0810` |
| `--color-wine-800` | `#551008` |
| `--color-wine-700` | `#7d1818` |
| `--color-red-600` | `#b61030` |
| `--color-red-500` | `#e24050` |
| `--color-red-400` | `#ee7175` |
| `--color-red-300` | `#f69d9d` |
| `--color-cream-100` | `#fffff2` |
| `--color-cream-200` | `#ead6aa` |
| `--color-tan-300` | `#daa56d` |
| `--color-tan-400` | `#ca713c` |
| `--color-tan-500` | `#ae4c30` |
| `--color-brown-600` | `#713410` |
| `--color-olive-500` | `#657150` |
| `--color-teal-500` | `#71958d` |
| `--color-teal-300` | `#a5baae` |

## Semantic aliases

| Token | Trỏ tới | Dùng cho |
|---|---|---|
| `--navy` | `--color-wine-900` | Heading, nền tối |
| `--blue` | `--color-red-600` | Nút hành động chính |
| `--bg` | `--color-cream-200` | Nền trang |
| `--card` | `--color-cream-100` | Nền card |
| `--text` | `--color-wine-900` | Chữ chính |
| `--muted` | `--color-olive-500` | Chữ phụ |
| `--danger` | `--color-wine-700` | Hành động nguy hiểm |

## Spacing (thang 8px)

| Token | Giá trị |
|---|---|
| `--gap-sm` | `8px` |
| `--gap-md` | `16px` |
| `--gap-lg` | `24px` |

Không hardcode `gap`/`padding`/`margin` ngoài thang này (ngoại lệ nhỏ 2–4px cho
icon/badge).

## Brand & button

| Token | Giá trị / mục đích |
|---|---|
| `--brand-gradient` | Gradient chữ brand, 2 màu palette |
| `--button-gradient` | Gradient nền nút, 2 màu palette |
| `--button-border` | Viền dưới nút 3D |
| `--button-shadow` | Bóng khối nút 3D |
| `--button-ink` | Màu chữ trên nút |
| `--brand-border` | Viền dưới brand |
| `--brand-size` / `--brand-size-sm` | Cỡ chữ brand desktop/mobile |
| `--nav-size` / `--nav-size-sm` | Cỡ chữ nút |
| `--nav-padding` / `--nav-padding-sm` | Padding nút |
| `--nav-min` / `--nav-min-sm` | Chiều rộng tối thiểu nút |
| `--nav-radius` | Bo góc nút |
| `--nav-shadow` / `--nav-shadow-hover` / `--nav-shadow-active` | Bóng nút 3D |
| `--card-radius` | Bo góc card |
| `--card-shadow` | Bóng card |

## Typography

- Font chính cho web: **Be Vietnam Pro** (đủ weight), phục vụ từ
  `src/fonts/Be_Vietnam_Pro/` qua mount `/fonts`.
- Fallback CJK: **Noto Sans CJK SC** rồi **Noto Sans CJK JP**, phục vụ từ
  `src/fonts/NotoSansCJK{sc,jp}-Regular/`.
- Stack trong `body`: `"Be Vietnam Pro", "Noto Sans CJK SC",
  "Noto Sans CJK JP", system-ui, ...`.
- Không thêm font web khác, không copy font vào `web/static`.
- PPTX vẫn dùng **Lexend**; quy ước này chỉ cho giao diện web.

## Quy tắc an toàn khi sửa UI

- Giữ nguyên class/`data-*` mà `web/static/app.js` đang bắt
  (`data-expand`, `data-delete-trigger`, `data-tag-editor`, `data-reuse-tags`,
  `data-check-url`, `data-overlay`...).
- Không đổi cấu trúc `<select name="template">` hoặc số nút submit; test và
  luồng tạo deck phụ thuộc vào đó.
- Thêm màu mới hoặc token mới phải cập nhật bảng trong file này và
  `AGENTS.md`; không thêm biến CSS nếu có thể dùng token sẵn có.
- Sau mỗi thay đổi UI: chạy `uv run pytest tests/test_web.py -q`.
