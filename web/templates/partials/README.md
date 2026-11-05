# Quy ước template

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

## CSS design tokens

Khai báo trong `:root` của `web/static/style.css`. Không hardcode lại giá trị
trong rule; dùng `var(--token)`.

| Token | Giá trị / mục đích |
|---|---|
| `--navy` | Màu nền tối chủ đạo |
| `--blue` | Màu nhấn mặc định |
| `--bg` | Nền trang |
| `--card` | Nền card |
| `--text` | Màu chữ chính |
| `--muted` | Màu chữ phụ |
| `--danger` | Màu hành động nguy hiểm |
| `--gold` | Vàng gradient thương hiệu |
| `--rose` | Hồng gradient thương hiệu |
| `--rose-deep` | Hồng đậm cuối gradient |
| `--rose-border` | Viền dưới nút 3D |
| `--rose-shadow` | Bóng khối nút 3D |
| `--rose-ink` | Màu chữ trên nút |
| `--brand-border` | Viền dưới brand |
| `--brand-gradient` | Gradient chữ brand |
| `--button-gradient` | Gradient nền nút |
| `--brand-size` / `--brand-size-sm` | Cỡ chữ brand (desktop/mobile) |
| `--nav-size` / `--nav-size-sm` | Cỡ chữ nút |
| `--nav-padding` / `--nav-padding-sm` | Padding nút |
| `--nav-min` / `--nav-min-sm` | Chiều rộng tối thiểu nút |
| `--nav-radius` | Bo góc nút |
| `--nav-shadow` / `--nav-shadow-hover` / `--nav-shadow-active` | Bóng nút 3D |
| `--card-radius` | Bo góc card |
| `--card-shadow` | Bóng card |
| `--gap` | Khoảng cách grid/card |

Khi thêm token: đặt tên theo mục đích (không theo giá trị), thêm vào `:root`,
dùng ở rule tương ứng, và cập nhật bảng này.
