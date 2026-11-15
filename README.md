# VietLip 1.7.0

Ứng dụng Android đọc môi tiếng Việt qua camera, kết nối không dây tới server
Windows trong cùng mạng nội bộ. Server hiển thị IP; người dùng nhập IP trong
**Cài đặt → Lưu và kiểm tra**. Phụ đề live chỉ dùng hình ảnh. Video lưu có âm
thanh để đối chiếu khi thử nghiệm.

**Bộ cài 1.7.0:** `E:\Project\Lip_App\lip_reader\output\VietLip-1.7.0` — gồm đúng hai file:
APK Android và ZIP Windows. Giải nén toàn bộ ZIP, rồi mở `BAT_DAU.txt`.

## Dùng bộ cài

1. Chạy `02-Server-Windows/VietLip-Server-Setup-1.7.0.exe`; giữ các file `.bin`
   bên cạnh. Bộ cài có sẵn Python, thư viện CPU/CUDA và checkpoint SO17.
2. Mở **VietLip Server** từ Start Menu và chờ **Sẵn sàng đọc môi**.
3. Cài `VietLip-1.7.0.apk` đi kèm riêng lên Android. Cập nhật trực tiếp để giữ
   lịch sử trên thiết bị.
4. PC và điện thoại kết nối cùng mạng Wi-Fi/LAN có cho phép liên lạc giữa
   thiết bị. Nhập IP server trong app, kiểm tra, rồi **Bắt đầu đọc môi**.

Mạng khách có thể tách thiết bị dù cùng SSID. Nếu kết nối thất bại, kiểm tra IP,
cổng 7100, quyền mạng của server và cấu hình router. Không cần tài khoản cloud
hay LLM/API key. Xem hướng dẫn trong
[`packaging/windows_server/README_INSTALL.txt`](packaging/windows_server/README_INSTALL.txt).

## Giao diện và hành vi

- Tên và biểu tượng VietLip; nền sáng, xanh ngọc, typography Nunito thống nhất.
- Khung “Phụ đề trực tiếp” luôn nằm ngay dưới preview từ màn hình đầu. Trước khi bắt đầu có hướng dẫn ngắn; khi đọc môi, chữ hiện trong khung này.
- Nút bắt đầu/kết thúc cố định, dễ chạm; trạng thái máy chủ được kiểm tra thật và có lối vào Cài đặt.
- Ảnh dùng tỷ lệ gốc và `BoxFit.contain`, không bóp mặt; guide theo vùng hình.
- Phụ đề có vùng riêng, chữ lớn, phần tạm gạch dưới. Mở rộng để xem/sao chép
  toàn phiên. Điều hướng ẩn khi đang live.
- Tự theo dõi chuyển động môi và khoảng ngừng để chốt đoạn. Nhai/cười vẫn có
  thể bị nhầm thành hoạt động nói; phụ đề tự động cần kiểm tra.
- Cài đặt nhận IP có hoặc không có `http://`; mặc định cổng 7100. Nút kiểm
  tra có thời hạn chờ, server chỉ báo sẵn sàng khi mô hình đã chuẩn bị xong.
- Lịch sử cục bộ tự cập nhật; chữ lớn/màn hình nhỏ có thể cuộn.
- Lịch sử → chọn phiên → Lưu video ra máy để xuất MP4 có tiếng. Camera đã dừng
  vẫn giữ vùng phụ đề cho tới khi server gửi và app dựng xong phần cuối.
- Nhãn phiên bản trong Cài đặt đọc trực tiếp từ gói Android đã cài.

## Mô hình và giới hạn

Giữ **SO17 native, float32, beam 3 / CTC 0.1, 25 fps, cửa sổ 6 giây và bước
1,5 giây**. Runtime chỉ dùng SO17; đã gỡ LLM và nhánh chấm lại bằng âm vị. Các tài liệu thử nghiệm cũ được giữ để đối chiếu.

Ứng dụng vẫn là bản thử nghiệm, **chưa đạt độ chính xác cao với câu nói tự do**.
Phiên Wi-Fi bốn câu ngắn mới nhất có WER 66,67% và CER 50,00%; đây là lỗi chữ
trên video thật, dù camera và mạng hoạt động ổn. Đóng gói và đổi UI không phải
cải thiện độ chính xác. GPU được ưu tiên; CPU chạy được nhưng
không bảo đảm realtime. Android đã được build/test; chưa kiểm chứng iPhone.

Bộ lọc CNN giữ được các câu thử và giảm chữ sinh thêm ở một replay im lặng;
chưa bật mặc định vì chưa có bằng chứng cải thiện live trên nhiều bối cảnh.
Xem [kết quả và giới hạn của phiên mới](docs/VISUAL_CONFIRMATION_AND_SCENE04_2026-11-10.md).
Các phép thử checkpoint và nhánh âm vị vẫn ủng hộ giữ SO17. Độ trễ 2–3 giây
là mục tiêu, chưa phải bảo đảm cho mọi câu và cấu hình.

Đã kiểm thêm hướng ảnh và cách chấm đáp án trên 209 cửa sổ của tám video.
Các biến thể gây hồi quy hoặc không giảm tổng lỗi và tăng thời gian xử lý;
[kết quả đối chiếu](docs/ORIENTATION_AUDIT_2026-11-10.md) giữ nguyên cấu hình
và bộ cài hiện tại. Đây là điểm chốt của đợt tối ưu với dữ liệu đang có.

## Bảo trì

- [Kiểm tra code, gói hai file và quy tắc lưu trữ](docs/MAINTENANCE.md).
- [Sơ đồ thư mục và cách tạo bộ cài](docs/PROJECT_MAP.md).
- [Kiến trúc ứng dụng/server](docs/ARCHITECTURE.md).
- [Bằng chứng bộ cài VietLip 1.6.0 trước đây](docs/RELEASE_1_6_0_2026-11-09.md).
- [Kiểm chứng bộ cài VietLip 1.6.3](docs/RELEASE_1_6_3_2026-11-10.md).
- [So sánh cùng cửa sổ và phụ đề trên điện thoại](docs/FROZEN_WIFI_CAPTIONS_2026-11-10.md).
- [Chọn checkpoint](docs/CHECKPOINT_SELECTION_2026-11-09.md).
- [Bản 1.5 và các phép đo phụ đề](docs/RELEASE_1_5_0_2026-11-09.md).

Chạy từ source đã chuẩn bị: `server/run_realtime.ps1`. Build Android có ký:
`build_android.ps1 -Mode release`. Build installer và kiểm tra runtime theo
`packaging/windows_server/README.md`. Không đưa model, khóa ký, video hay thư
mục build vào Git. Mã nguồn của bên thứ ba và license được giữ cùng project.

Các bản xuất cũ chuyển vào `output/archive/pre_vietlip_1_6`; script bộ cài cũ
chuyển vào `packaging/legacy_windows_server_1_1`. Video, bằng chứng, model và
thử nghiệm cũ được giữ để đối chiếu; chúng không nằm trong bộ cài người dùng.

## UI/UX 1.7.0

Xem [audit](UI_UX_AUDIT.md) và [báo cáo thay đổi, kiểm thử](UI_UX_POLISH_REPORT.md).
Gỡ lựa chọn chế độ/ngữ cảnh/LLM; giữ một luồng nhận dạng hình ảnh. Lịch sử cũ
vẫn đọc được và hiển thị phụ đề thị giác gốc. Các endpoint upload/jobs/WebSocket
giữ đường dẫn; API 1.3.0 chỉ nhận `mode=visual_only`.
