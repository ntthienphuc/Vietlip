# VietLip 1.10.1

Ứng dụng Android đọc môi tiếng Việt qua camera, kết nối không dây tới server
Windows trong cùng mạng nội bộ. Server hiển thị IP; người dùng nhập IP trong
**Cài đặt → Lưu và kiểm tra**. Phụ đề live chỉ dùng hình ảnh. Video lưu có âm
thanh để đối chiếu khi thử nghiệm.

**Bộ cài hiện tại:** `output/VietLip-Final` — gồm đúng hai file:
`VietLip-1.10.1.apk` và `VietLip-Server-Setup-1.10.1.exe`. EXE chứa đầy đủ
runtime và mô hình; mở trực tiếp để cài, không cần ZIP hoặc BIN đi kèm.
Cần khoảng 6 GB cho bản Windows đã cài và thêm khoảng 3,5 GB trống ở ổ chứa
thư mục tạm khi mở EXE; dữ liệu giải nén tạm được dọn khi đóng bộ cài.

Mặc định **Trực tiếp — SO17** để ưu tiên live. Trong Cài đặt có thêm các phương pháp
Khôi phục câu qua Groq hoặc OpenRouter ngay trong phiên, theo từng câu. Bản AI nằm riêng; phụ đề
gốc vẫn được lưu và hiển thị. Phương pháp AI cần cấu hình endpoint trên PC.
Xem [cách dùng và cấu hình](docs/LIVE_AI_1_10.md).

## Dùng bộ cài

1. Chạy `VietLip-Server-Setup-1.10.1.exe`. Bộ cài có sẵn Python, thư viện
   CPU/CUDA và checkpoint SO17.
2. Mở **VietLip Server** từ Start Menu và chờ **Sẵn sàng đọc môi**.
3. Cài `VietLip-1.10.1.apk` đi kèm riêng lên Android. Cập nhật trực tiếp để giữ
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
1,5 giây**. Nhận dạng live dùng SO17; AI tùy chọn khôi phục từng câu đã chốt và hiển thị cùng bản gốc ngay trong phiên.
Các tài liệu thử nghiệm cũ được giữ để đối chiếu.

Ứng dụng vẫn là bản thử nghiệm, **chưa đạt độ chính xác cao với câu nói tự do**.
Bốn lượt camera Wi-Fi ngày 16/11, cùng người nói và cùng 10 câu mỗi lượt, có
WER gộp 47,5% ở bản gốc, 48,0% với Groq và 43,5% với OpenRouter. Đây là mẫu
nhỏ, chưa đại diện cho người nói/câu tự do; LLM vẫn có thể sửa sai ý.
Xem [phạm vi và kết quả kiểm chứng 1.10](docs/RELEASE_1_10_2026-11-16.md).
Vòng tám phiên đoạn văn tiếp theo có WER ước lượng theo chép âm thanh cục bộ
57,88% ở bản gốc và 61,41% với Groq. Người dùng có vấp/đổi từ nên nhãn ASR này
chưa phải tham chiếu kiểm nghe hoàn chỉnh. [Báo cáo và quyết định giữ cấu hình](docs/PARAGRAPH_BENCHMARK_2026-11-16.md).
Đóng gói và đổi UI không phải cải thiện độ chính xác. GPU được ưu tiên; CPU chạy được nhưng
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

- [Bộ cài cuối, cài sạch, kiểm điện thoại và biên nhận dọn máy](docs/FINAL_DELIVERY_2026-11-16.md).
- [Kiểm tra code, gói hai file và quy tắc lưu trữ](docs/MAINTENANCE.md).
- [UI/UX 1.8.0 và kiểm chứng trên điện thoại](UI_UX_POLISH_REPORT.md).
- [AI theo từng câu và kiểm chứng 1.10.1](docs/RELEASE_1_10_2026-11-16.md).
- [Tám phiên đoạn văn: so cửa sổ, ngắt đoạn và LLM](docs/PARAGRAPH_BENCHMARK_2026-11-16.md).
- [Thử sửa transcript bằng LLM lớn: kết quả và giới hạn](docs/LLM_REWRITE_2026-11-15.md).
- [Kiểm dữ liệu local, ba mô hình thị giác và phép thử LLM mở rộng](docs/LLM_EXPANSION_2026-11-15.md).
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

Các bộ cài cũ và cache build được dọn sau khi kiểm chứng bản cuối. Video,
bằng chứng, model và thử nghiệm được giữ để đối chiếu; chúng không nằm trong
bộ cài người dùng. Script bộ cài 1.1 cũ ở `packaging/legacy_windows_server_1_1`.

## UI/UX 1.7.0

Xem [audit](UI_UX_AUDIT.md) và [báo cáo thay đổi, kiểm thử](UI_UX_POLISH_REPORT.md).
Ở bản 1.7 đã gỡ lựa chọn chế độ/ngữ cảnh/LLM; giữ một luồng nhận dạng hình ảnh. Lịch sử cũ
vẫn đọc được và hiển thị phụ đề thị giác gốc. Các endpoint upload/jobs/WebSocket
giữ đường dẫn; API 1.3.0 chỉ nhận `mode=visual_only`.
