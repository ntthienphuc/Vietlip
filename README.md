# VietLip 1.10.5

VietLip hiển thị phụ đề tiếng Việt từ khẩu hình. Điện thoại Android gửi hình camera qua Wi-Fi/LAN đến VietLip Server trên Windows. Máy chủ chạy SO17 cục bộ. Nếu người dùng bật **Kèm gợi ý câu**, PC gửi văn bản đã chốt đến Google Gemini 3.1 Flash-Lite. Ứng dụng hiển thị phụ đề gốc và gợi ý ở hai dòng riêng.

## Cài đặt và sử dụng

[Danh mục bộ bàn giao 1.10.5](docs/ban-giao-1.10.5/README.md) gồm mã SHA-256
của APK, bộ cài Windows, hai tài liệu PDF và hai video demo.

1. Trên Windows 10/11 x64, chạy **VietLip-Server-Setup-1.10.5.exe**. Dành khoảng 6 GB cho ứng dụng và thêm 3,5 GB trên ổ chứa thư mục tạm. Bộ cài mang theo Python, runtime và mô hình. Server tự dùng GPU NVIDIA khi CUDA khả dụng hoặc dùng CPU.
2. Mở **VietLip Server** từ Start Menu và chờ **Sẵn sàng đọc môi**.
3. Cài **VietLip-1.10.5.apk** (build 30). Trong **Cài đặt → Quét QR máy chủ**, hướng camera vào mã trên PC. Nếu cần, nhập địa chỉ cùng cổng đang hiển thị trên PC. Mạng nội bộ phải cho phép điện thoại kết nối tới PC.
4. Trên điện thoại, chạm **Bắt đầu đọc môi**. Giữ mặt rõ, gần chính diện và có đủ ánh sáng. Sau khi nói xong, chờ phụ đề cuối rồi chạm **Kết thúc phiên**. Có thể xuất video ở **Lịch sử → Lưu video ra máy**.

**Gemini.** Bản cài nội bộ có thể cấp sẵn key khi cài mới. Để thay key, mở **VietLip Server → Cài đặt key Gemini** trên Windows, nhập key mới và lưu. Cài lại giữ key hiện tại của tài khoản Windows. Chọn **Kèm gợi ý câu → Áp dụng** trên điện thoại. Chế độ **Phụ đề trực tiếp** dùng được khi PC chỉ có kết nối LAN.

## Mã nguồn

| Thành phần | Đường dẫn |
| --- | --- |
| Giao diện, camera và lịch sử trên điện thoại | [lib](lib), [android](android), [CameraX adapter](packages/camera_android_camerax) |
| Nhận dạng, WebSocket và gợi ý câu | [server/app](server/app) |
| Cửa sổ máy chủ và ghép QR | [desktop_launcher.py](server/desktop_launcher.py) |
| Tạo APK và EXE | [build_android.ps1](build_android.ps1), [đóng gói Windows](packaging/windows_server/README.md) |
| Kiểm thử | [Flutter](test), [server](server/tests), [bộ cài](packaging/windows_server/tests) |

Bộ nhận dạng dùng SO17 FP32, beam 3, trọng số CTC 0,1, cửa sổ tối đa 6 giây. Tốc độ thực tế phụ thuộc camera, mạng và PC. Tiếng trong bản ghi phục vụ nghe lại. Người dùng cần xác nhận các phụ đề quan trọng.

## Phát triển và bàn giao

- Đội triển khai bắt đầu từ [hướng dẫn tự build APK và bộ cài Windows](docs/BUILD_VI.md). Hướng dẫn có cách chuẩn bị checkpoint SO17, kiểm thử và ký APK.
- Flutter dùng `flutter analyze` và `flutter test`. Với bản release, dùng `build_android.ps1 -Mode release` cùng cấu hình ký cục bộ.
- Bản Windows dùng [quy trình đóng gói](packaging/windows_server/README.md). Theo mặc định builder tạo bản không kèm key. Switch `-IncludeSavedGeminiKey` chỉ dành cho bàn giao nội bộ vì người nhận EXE có thể trích key và sử dụng hạn mức chung.
- Model, key, APK/EXE, video riêng và tệp build được quản lý ngoài Git. Giấy phép đi kèm thư viện nằm trong [thư mục vendor](server/vendor). Bộ cài hiện dành cho thử nghiệm nội bộ.
- Xem [kiến trúc](docs/ARCHITECTURE.md), [hành vi gợi ý theo câu](docs/LIVE_AI_1_10.md) và [sơ đồ project](docs/PROJECT_MAP.md).
