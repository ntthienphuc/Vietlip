# VietLip 1.9 — kiểm tra phương pháp trên điện thoại qua Wi-Fi

Ngày 15/11/2026, sau khi người dùng mở VietLip Server, đã kiểm tra hai phương
pháp gateway bằng app Android 1.9.0+18 trên SM-G965F. Server 1.9.0/API 1.4.0
báo ready, SO17 float32 trên CUDA, tại địa chỉ LAN 192.168.1.9:7100.

## Phạm vi và kết quả

Chọn lại cùng video scene 4 từ Downloads trên điện thoại, gửi qua app và chờ
nhận dạng toàn clip. Sau mỗi lượt, app tạo bản AI riêng và mở trang kết quả.
Không có ADB reverse; địa chỉ app vẫn là IP LAN. ADB chỉ điều khiển kiểm thử.

| Phương pháp | Khung hình thị giác | Thời gian nhận dạng hiển thị | Thời gian AI hiển thị | Kết quả lưu |
|---|---:|---:|---:|---|
| Gateway sửa thận trọng | 727 | 7,80 s | 8,3 s | Giữ nguyên raw; bản AI lưu riêng |
| Gateway khôi phục câu | 727 | 8,02 s | 8,9 s | Raw giữ nguyên; bản viết lại lưu riêng |

Hai lượt có cùng raw. Bản khôi phục trôi chảy hơn nhưng thêm ý không tương ứng
với kịch bản đã xác nhận; chưa có lý do bật làm mặc định live.
Đây là kiểm tra luồng full-clip và AI sau phiên, không phải phép đo độ trễ
từ thời điểm người nói ngừng nói hoặc một benchmark độ chính xác mới.

Đã kiểm tra trên giao diện thật:

- Bảng phương pháp lấy trạng thái cấu hình qua Wi-Fi: ba lựa chọn hoạt động
  (Trực tiếp và hai kiểu gateway); hai kiểu local khóa vì chưa cấu hình endpoint.
- Có hai khung Phụ đề gốc/Đề xuất AI và hai nút sao chép riêng.
- Hai kết quả vẫn có đủ hai bản khi mở lại từ Lịch sử; danh sách có 27 phiên,
  bao gồm các phiên cũ. Không xóa lịch sử.
- Sau thử, chọn lại Trực tiếp — SO17, xác nhận trên Cài đặt, bỏ lựa chọn
  video kiểm thử khỏi màn hình nhập và trở về màn hình sẵn sàng đọc môi.
- Server vẫn ready/CUDA, không còn job đang xử lý.

Kiểm tra bổ sung bằng force-stop rồi mở lại tiến trình Android bị phê duyệt
tự động chặn, không cung cấp lý do cụ thể. Do đó chưa xác nhận lại sau khi
khởi động lại tiến trình. Việc mở lại trang Lịch sử đã được kiểm tra trực tiếp;
khả năng lưu/đọc JSON và các phản hồi AI muộn có test tự động riêng.

## Bằng chứng riêng tư

`artifacts/method_settings_20261115/DEVICE_WIFI_FLOW.json` ghi hash video,
mã phiên, raw/bản sửa, số đo hiển thị và tệp bằng chứng UI. Hai screenshot là
`result-conservative-wifi.png` và `result-direct-wifi.png`.
Transcript, video, key và XML giao diện không đưa vào Git.

Biên nhận `ACCEPTANCE.json` đã cập nhật hai luồng Wi-Fi thành verified;
biên nhận trước khi người dùng mở server được giữ riêng để đối chiếu.
Không thay mã runtime hoặc bộ cài trong lượt kiểm tra này.
