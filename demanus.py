from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

def build_presentation():
    prs = Presentation()

    # Thiết lập kích thước slide 16:9 widescreen tiêu chuẩn (13.33 x 7.5 inches)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Bảng màu trang nhã (Dark Navy & Slate)
    NAVY = RGBColor(24, 43, 73)
    DARK_GRAY = RGBColor(50, 50, 50)
    LIGHT_GRAY = RGBColor(240, 242, 245)

    # ==========================================
    # SLIDE 1: Title Slide (Layout 0)
    # ==========================================
    title_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_layout)

    title = slide1.shapes.title
    subtitle = slide1.placeholders[1]

    title.text = "Báo Cáo Tổng Quan Lâm Sàng"
    title.text_frame.paragraphs[0].font.name = "Arial"
    title.text_frame.paragraphs[0].font.size = Pt(40)
    title.text_frame.paragraphs[0].font.bold = True
    title.text_frame.paragraphs[0].font.color.rgb = NAVY

    subtitle.text = "Chẩn đoán phân biệt & Hướng tiếp cận điều trị\nBác sĩ thực hiện: BS. Duyen"
    subtitle.text_frame.paragraphs[0].font.size = Pt(20)
    subtitle.text_frame.paragraphs[0].font.color.rgb = DARK_GRAY

    # ==========================================
    # SLIDE 2: Nội dung phân cấp Bullet Points (Layout 1)
    # ==========================================
    bullet_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_layout)

    # Tiêu đề slide
    s2_title = slide2.shapes.title
    s2_title.text = "Triệu Chứng & Tiêu Chuẩn Chẩn Đoán"
    s2_title.text_frame.paragraphs[0].font.color.rgb = NAVY
    s2_title.text_frame.paragraphs[0].font.bold = True

    # Nội dung phân cấp
    body_shape = slide2.placeholders[1]
    tf = body_shape.text_frame
    tf.word_wrap = True

    # Bullet cấp 1
    p1 = tf.paragraphs[0]
    p1.text = "Triệu chứng cơ năng chính"
    p1.level = 0
    p1.font.size = Pt(20)
    p1.font.bold = True

    # Bullet cấp 2
    p2 = tf.add_paragraph()
    p2.text = "Khởi phát đột ngột kèm sốt nhẹ hoặc không sốt."
    p2.level = 1
    p2.font.size = Pt(16)

    p3 = tf.add_paragraph()
    p3.text = "Ngứa nhiều, phân bố rải rác vùng cẳng tay và thân mình."
    p3.level = 1
    p3.font.size = Pt(16)

    # Bullet cấp 1 tiếp theo
    p4 = tf.add_paragraph()
    p4.text = "Chẩn đoán phân biệt cần loại trừ"
    p4.level = 0
    p4.font.size = Pt(20)
    p4.font.bold = True

    p5 = tf.add_paragraph()
    p5.text = "Sẩn ngứa do côn trùng cắn (Arthropod bites) vs Thủy đậu giai đoạn sớm."
    p5.level = 1
    p5.font.size = Pt(16)

    # ==========================================
    # SLIDE 3: Bảng dữ liệu / So sánh (Layout trống 6)
    # ==========================================
    blank_layout = prs.slide_layouts[6]
    slide3 = prs.slides.add_slide(blank_layout)

    # Thêm tiêu đề thủ công bằng Textbox
    title_box = slide3.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(0.8))
    t_frame = title_box.text_frame
    tp = t_frame.paragraphs[0]
    tp.text = "Bảng So Sánh Đặc Điểm Lâm Sàng"
    tp.font.size = Pt(28)
    tp.font.bold = True
    tp.font.color.rgb = NAVY

    # Tạo bảng: 3 hàng, 3 cột
    rows, cols = 3, 3
    left, top, width, height = Inches(0.8), Inches(1.8), Inches(11.7), Inches(3.5)
    table_shape = slide3.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    # Đặt độ rộng các cột
    table.columns[0].width = Inches(3.2)
    table.columns[1].width = Inches(4.25)
    table.columns[2].width = Inches(4.25)

    # Dữ liệu bảng
    headers = ["Đặc điểm", "Sẩn ngứa do côn trùng", "Thủy đậu (Giai đoạn sớm)"]
    row_1 = ["Hình thái tổn thương", "Sẩn phù, chấm xuất huyết ở trung tâm", "Dát sẩn tiến triển nhanh thành mụn nước"]
    row_2 = ["Phân bố", "Vùng da hở, cẳng tay, cẳng chân, thân mình", "Thân mình lan ra mặt và chi, nhiều lứa tuổi"]

    data = [headers, row_1, row_2]

    for r_idx, row_data in enumerate(data):
        for c_idx, cell_value in enumerate(row_data):
            cell = table.cell(r_idx, c_idx)
            cell.text = cell_value
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            p.font.size = Pt(15)
            
            # Tô đậm hàng tiêu đề
            if r_idx == 0:
                p.font.bold = True
                p.font.color.rgb = NAVY
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT_GRAY

    # Lưu bài thuyết trình
    prs.save("Bao_Cao_Lam_Sang.pptx")
    print("Đã tạo file Bao_Cao_Lam_Sang.pptx thành công.")

if __name__ == "__main__":
    build_presentation()