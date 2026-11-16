# VietLip 1.10 — hai chế độ, AI theo từng câu

VietLip có hai lựa chọn: **Trực tiếp** và **Khôi phục câu**. Mở nút chế độ cạnh
tên ứng dụng ở trang Đọc môi, hoặc **Cài đặt → Cách đọc môi**, chọn rồi Áp dụng.
Chế độ được giữ cố định trong phiên; thay đổi áp dụng cho phiên tiếp theo.

## Trải nghiệm live

- **Trực tiếp:** nhận dạng SO17 và hiển thị lời đọc môi ngay khi có kết quả.
- **Khôi phục câu:** cùng luồng SO17; mỗi câu đã chốt tự gọi AI một lần.
  Bản đọc môi nằm trên, câu AI ở dưới, có thanh tiến trình khi đang xử lý.
  Các cặp cuộn theo câu; kéo lên hoặc mở rộng để xem lại.
- Tiếp tục nói trong khi AI chạy. Phản hồi AI gắn theo mã câu, không thay thế
  kết quả của câu mới hơn. Cửa sổ tạm và gói chốt lặp không tạo lượt gọi mới.
- Tự nhận khoảng ngừng bằng chuyển động môi. Một đoạn được chốt có thể chứa
  hơn một câu ngữ pháp khi người dùng nói liền; app không đoán dấu câu để gọi
  thêm LLM trên cửa sổ đang thay đổi.
- Bản gốc và từng bản AI được lưu riêng trong Lịch sử. Kết thúc phiên không
  gọi lại AI cho toàn bộ bản ghi live. Mở bản đã lưu để xem các cặp.
- Video chọn từ thư viện vẫn dùng xử lý toàn clip; AI xem lại văn bản của
  lượt xử lý đó, trên trang kết quả.

Khôi phục dùng **Groq / GPT-OSS 120B** hoặc **OpenRouter / Nemotron 3 Ultra
550B bản :free**. Chọn dịch vụ trong cùng bảng cài đặt. Model thực tế lấy từ
cấu hình PC; server báo khi chưa cấu hình. Không còn lựa chọn thận trọng,
LLM local hoặc endpoint 6.1-sol trong luồng ứng dụng.

## Cấu hình PC

Mặc định Trực tiếp không cần key. AI đọc file riêng
`%LOCALAPPDATA%\VietLip\rewrite.json`, ngoài thư mục cài và Git. Mẫu
`rewrite.example.json` nằm cạnh bộ cài. Có thể dùng `api_key_env`, hoặc
`api_key_file` trỏ tới JSON riêng và `api_key_name` chọn trường trong file đó.
Không nhúng key trong APK, gói Windows, source hoặc log. Hai tài khoản/API key
của PC hiện tại được lưu riêng; bản cài chuyển sang máy khác cần key riêng.

Chỉ văn bản của câu gốc và prompt cố định gửi lên API. Video, âm thanh, câu
chuẩn và lịch sử hội thoại không gửi cho LLM. Nội dung khôi phục vẫn có thể sai
ý và không được ghi đè lên bản gốc.

OpenRouter chỉ chấp nhận model có hậu tố `:free`, tắt fallback và đặt giá tối
đa input/output bằng 0. Không tự chuyển sang model trả phí. Quota, lỗi key,
timeout và kết quả bị cắt đều hiện trạng thái rõ, giữ bản gốc. Key và dịch vụ
vẫn chịu chính sách/hạn mức của tài khoản nhà cung cấp.

## Giao thức và thứ tự

API 1.5 cung cấp `GET /v1/rewrite-methods` và `POST /v1/rewrites`. Request gồm
`text`, `method` (`visual`/`recovery`), `provider` (`groq`/`openrouter`) và
`sentence_id` tùy chọn. Không nhận endpoint, credential, media hay câu chuẩn.
Discovery chỉ trả tên model và trạng thái, không trả key hoặc đường dẫn riêng.

Client giới hạn hai lượt đang xử lý, sáu lượt đang chờ; timeout có thời hạn.
Server giới hạn hai lượt AI đồng thời, tách khỏi semaphore mô hình thị giác.
Từ bản 1.10.1, hạn chờ 12 giây áp dụng cho toàn lượt HTTP bất đồng bộ, kể cả
khi API gửi keepalive liên tục. Hết hạn hủy kết nối, giải phóng lượt đang chạy,
giữ bản gốc và lưu trạng thái timeout; phản hồi muộn không đổi lại câu đã chốt.
Cùng mã câu/nội dung/provider được gộp trong bộ nhớ server tối đa năm phút;
đổi nội dung với cùng mã bị từ chối. Cache tối đa 128 mục đã hoàn thành.
Lịch sử ghi tuần tự và chỉ cập nhật bản còn tồn tại, không phục hồi phiên đã xóa.

Độ trễ AI được đo riêng. Mục tiêu nói xong 2–3 giây có chữ còn phụ thuộc phát
hiện điểm ngừng, thời gian nhận dạng hình ảnh, mạng và quota. Hai API đã được
gọi thành công; các số đo và phạm vi kiểm chứng nằm trong biên bản phát hành.
