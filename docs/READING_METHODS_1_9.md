# VietLip 1.9 — lựa chọn phương pháp phụ đề

Mặc định **Trực tiếp — SO17**: giữ cấu hình live đã kiểm chứng, không gửi chữ
cho LLM và không chờ bước sửa câu. Kết nối camera/server vẫn qua Wi-Fi nội bộ.

Trong **Cài đặt → Phương pháp phụ đề**, có thêm:

| Phương pháp | Khi nào chạy | Căn cứ lựa chọn |
|---|---|---|
| Trực tiếp | Trong phiên live | Mặc định, ưu tiên phản hồi nhanh và giữ đúng đầu ra thị giác |
| AI sửa thận trọng | Sau phiên | Giảm ít lỗi trên mẫu rộng; khoảng 7 giây thêm trong benchmark |
| AI khôi phục câu | Sau phiên | Điểm tốt nhất trên video điện thoại đã thử; 9–12 giây thêm, có thể đổi ý |
| AI trên PC, thận trọng | Sau phiên, cần endpoint local | Qwen 4B đã thử chưa giảm tổng lỗi |
| AI trên PC, khôi phục | Sau phiên, cần endpoint local | Thử nghiệm; không khuyến nghị mặc định |

Thời gian trên là số đo lượt thử trước, không phải cam kết thời gian trên mọi máy.
Hai kiểu prompt giữ nguyên với benchmark trong
[báo cáo phép thử](LLM_EXPANSION_2026-11-15.md).

## Cách dùng

1. Nhập IP và kiểm tra máy chủ như trước.
2. Chọn phương pháp. Lựa chọn áp dụng cho phiên tiếp theo hoặc lần xử lý video tiếp theo.
3. Live luôn hiện bản phụ đề gốc. Nếu chọn AI, kết thúc phiên sẽ lưu bản gốc
   trước rồi tạo bản sửa riêng; không giữ camera hay chặn phiên mới để chờ AI.
4. Bấm **Xem bản đã lưu**, hoặc vào **Lịch sử → chọn phiên**. Màn hình hiển thị
   **Phụ đề gốc** và **Đề xuất AI**, mỗi bản có nút sao chép riêng. Trang đang mở
   cập nhật khi AI trả kết quả.

Phương pháp không được cấu hình trên PC hiển thị khóa. Có cấu hình không có
nghĩa model đang sẵn sàng: nếu endpoint dừng, sai key, quota hoặc timeout thì
bản gốc vẫn giữ nguyên và màn hình báo AI chưa hoàn tất.

Video và âm thanh không gửi cho LLM. Gateway trên PC có thể chuyển văn bản
lên dịch vụ Internet theo cấu hình của người quản trị PC.

## Cấu hình tùy chọn trên PC

SO17 chạy ngay không cần API key. Server đọc cấu hình AI từ
`%LOCALAPPDATA%\VietLip\rewrite.json`, hoặc đường dẫn trong biến môi trường
`VIETLIP_REWRITE_CONFIG`. File này nằm ngoài bộ cài và Git; cập nhật app/server
không ghi đè cấu hình.

Mẫu `rewrite.example.json` được kèm trong bộ cài Windows. Tạo thư mục VietLip
trong LocalAppData nếu chưa có, sao chép mẫu thành `rewrite.json`, điền endpoint
chat-completions và model do dịch vụ cung cấp, đặt `enabled: true` cho provider
cần dùng. Có thể dùng `api_key_env` để đọc key từ biến môi trường của server,
hoặc trường `api_key` trong file riêng. Không đưa key vào app Android hoặc Git.
Mở lại bảng chọn phương pháp để cập nhật trạng thái cấu hình.

Model local phải được chạy ở endpoint tương ứng trước. Bộ cài không chứa LLM
hoặc tự chiếm thêm GPU để nạp Qwen: máy 4 GB VRAM còn cần chạy SO17. Những
checkpoint M1/M2/M3 trong báo cáo lịch sử không được giả làm lựa chọn có sẵn
khi chưa khôi phục và kiểm chứng được trọng số.

## Giao thức và độ bền dữ liệu

- API 1.4 bổ sung `GET /v1/rewrite-methods` và `POST /v1/rewrites`.
  Giao thức video/jobs/WebSocket vẫn dùng nhận dạng hình ảnh.
- Request chỉ nhận `text` và `method`; client không được truyền endpoint,
  câu chuẩn, lịch sử hội thoại hoặc thông tin xác thực.
- Tối đa 4.000 ký tự mỗi bản sửa. Một request AI mỗi lúc, không tích hàng đợi
  sửa câu làm chậm luồng live. Timeout provider 25 giây; client dừng chờ sau
  khoảng 30–32 giây. Phản hồi bị cắt, rỗng hoặc lỗi giữ bản gốc.
- AI chỉ cập nhật trường `rewrite`; không ghi đè `transcript`, thời gian,
  đường dẫn video hoặc model đọc môi gốc. Các trường trợ lý cũ trong lịch sử
  vẫn được giữ để tương thích, không tự hiển thị thành kết quả mới.
- Ghi lịch sử được tuần tự hóa. Xóa lịch sử trong khi AI chạy sẽ không làm
  phiên đã xóa xuất hiện lại khi có phản hồi muộn. Trạng thái đang chờ cũ quá
  hạn không hiển thị vòng quay vô tận.

## Kiểm chứng

Xem bằng chứng cài đặt và phép thử runtime tại
`artifacts/method_settings_20261115/` và các log `methods-*` trong
`artifacts/llm_expansion_20261115/`. Dữ liệu thử, key và video không nằm trong Git.

Ngày 15/11/2026: 43 test Flutter và 109 test server pass, 9 test nghiên cứu
âm vị tùy chọn bị skip do thiếu dependency ngoài bộ cài. Kiểm đủ 11.924 file
server đã cài không sai hash; runtime CUDA/tokenizer/MediaPipe kiểm tra thành công.
APK Android 1.9.0+18 trên SM-G965F khớp SHA-256 với file bàn giao. Hai phương
pháp gateway đã chạy thành công bằng chính module production được cài trên PC.

Phê duyệt tự động chặn lệnh mở server từ agent, không cung cấp lý do chi tiết.
Sau khi cài, server đang dừng và cần người dùng mở shortcut. Chưa xác nhận lại
luồng AI app → Wi-Fi → server trên thiết bị sau nâng cấp; không coi các test
module/UI là phép đo live hoặc phép đo chính xác mới.
