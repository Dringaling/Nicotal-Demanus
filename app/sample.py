from __future__ import annotations

from .schema import BulletItem, Column, DeckSpec, SlideSpec, TableBlock


def sample_deck() -> DeckSpec:
    return DeckSpec(
        title="Báo Cáo Tổng Quan Lâm Sàng",
        subtitle="Chẩn đoán phân biệt & Hướng tiếp cận điều trị",
        author="BS. Duyen",
        font="Lexend",
        slides=[
            SlideSpec(
                layout="title",
                title="Báo Cáo Tổng Quan Lâm Sàng",
                subtitle="Chẩn đoán phân biệt & Hướng tiếp cận điều trị",
                note="Slide bìa của báo cáo.",
            ),
            SlideSpec(
                layout="section",
                title="Phần 1: Triệu chứng và chẩn đoán",
                subtitle="Tổng hợp bệnh sử, khám thực thể và tiêu chuẩn chẩn đoán.",
            ),
            SlideSpec(
                layout="bullets",
                title="Triệu chứng cơ năng chính",
                subtitle="Khởi phát và diễn tiến trong 3 ngày gần đây",
                bullets=[
                    BulletItem(text="Khởi phát đột ngột, kèm sốt nhẹ hoặc không sốt."),
                    BulletItem(text="Ngứa nhiều, tăng về đêm."),
                    BulletItem(text="Phân bố rải rác vùng cẳng tay và thân mình.", level=1),
                    BulletItem(text="Không đau, không chảy dịch.", level=1),
                    BulletItem(text="Chẩn đoán phân biệt cần loại trừ"),
                    BulletItem(text="Sẩn ngứa do côn trùng cắn."),
                    BulletItem(text="Thủy đậu giai đoạn sớm.", level=1),
                ],
                note="Hỏi kỹ thời điểm khởi phát và yếu tố tiếp xúc.",
            ),
            SlideSpec(
                layout="two_column",
                title="Chẩn đoán phân biệt",
                subtitle="So sánh hai giả thuyết chính",
                columns=[
                    Column(
                        heading="Sẩn ngứa do côn trùng",
                        bullets=[
                            BulletItem(text="Sẩn phù, chấm xuất huyết trung tâm."),
                            BulletItem(text="Vùng da hở, cẳng tay, cẳng chân."),
                            BulletItem(text="Tiền sử tiếp xúc côn trùng."),
                        ],
                    ),
                    Column(
                        heading="Thủy đậu giai đoạn sớm",
                        bullets=[
                            BulletItem(text="Dát sẩn tiến triển nhanh thành mụn nước."),
                            BulletItem(text="Thân mình lan ra mặt và chi."),
                            BulletItem(text="Nhiều lứa tuổi trong cùng gia đình."),
                        ],
                    ),
                ],
            ),
            SlideSpec(
                layout="table",
                title="Bảng so sánh đặc điểm lâm sàng",
                table=TableBlock(
                    headers=["Đặc điểm", "Sẩn ngứa do côn trùng", "Thủy đậu sớm"],
                    rows=[
                        [
                            "Hình thái",
                            "Sẩn phù, chấm xuất huyết",
                            "Dát sẩn thành mụn nước",
                        ],
                        [
                            "Phân bố",
                            "Vùng da hở, cẳng tay",
                            "Thân mình lan ra mặt, chi",
                        ],
                        [
                            "Diễn tiến",
                            "Từng đợt, ngứa nhiều",
                            "Nhanh, nhiều lứa tổn thương",
                        ],
                    ],
                ),
            ),
            SlideSpec(
                layout="quote",
                title="Chẩn đoán đúng bắt đầu từ việc lắng nghe bệnh sử.",
                subtitle="Ghi chú lâm sàng",
            ),
            SlideSpec(
                layout="closing",
                title="Cảm ơn",
                subtitle="Liên hệ: BS. Duyen",
            ),
        ],
    )
