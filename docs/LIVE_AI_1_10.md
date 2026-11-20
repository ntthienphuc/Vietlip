# Hành vi phụ đề của VietLip 1.10.5

**Phụ đề trực tiếp** là mặc định. SO17 trên PC đọc các cửa sổ video chồng lấn và tự chốt đoạn theo chuyển động môi. Phụ đề có thể hiện trước khi nói xong khi các cửa sổ cùng xác nhận một cụm từ.

**Kèm gợi ý câu** dùng cùng phụ đề gốc. Khi chốt một đoạn, PC có thể gửi văn bản đó tới Gemini 3.1 Flash-Lite. Điện thoại giữ phần gốc ở trên và gắn phản hồi bên dưới đúng câu. Các cập nhật cửa sổ tạm thời không gọi Gemini. Người dùng có thể tiếp tục nói trong lúc chờ. Nếu API lỗi hoặc chạm hạn mức, bản gốc vẫn được giữ.

## Cấu hình

1. Với bộ cài nội bộ đã được cá nhân hóa, tài khoản Windows mới được cấp key trong lúc cài.
2. Để nhập hoặc đổi key, mở **VietLip Server → Cài đặt key Gemini**. Server bảo vệ key bằng Windows DPAPI theo tài khoản đang dùng. Cập nhật hoặc cài lại giữ key người dùng đã lưu.
3. Trên điện thoại mở **Cài đặt → Cách đọc môi → Kèm gợi ý câu → Áp dụng** và bắt đầu phiên mới. PC cần Internet để gọi Google.

Android chỉ liên lạc với VietLip Server. Lịch sử giữ phụ đề gốc và gợi ý riêng để người dùng đối chiếu. Mục tiêu của gợi ý là làm câu dễ đọc hơn. Với các chi tiết như phủ định, số hoặc tên riêng, nên xác nhận với người nói.
