# VietLip — sơ đồ project

Mã ứng dụng đang bảo trì: `E:\Project\Lip_App\lip_reader`.
Bộ cài mới nhất: `output/VietLip-Final` (APK + EXE Windows tự chứa đầy đủ).
Các bản phân phối cũ được dọn sau khi kiểm chứng bản cuối; giữ biên nhận kiểm thử.
Recipe đóng gói và kiểm tra: [MAINTENANCE.md](MAINTENANCE.md).

| Thư mục | Dùng để làm gì |
| --- | --- |
| `lib`, `android`, `ios` | App Flutter và mã nền tảng; Android là nền tảng đã build/test |
| `server/app` | API, tiền xử lý và nhận dạng realtime |
| `server/desktop_launcher.py`, `desktop_runtime.py` | Cửa sổ server Windows và cấu hình bộ cài |
| `packages/camera_android_camerax` | Bản CameraX có sửa hướng hình và tốc độ khung |
| `packaging/windows_server` | Bộ cài Windows hiện tại, runtime đi kèm và kiểm tra hash |
| `test`, `server/tests` | Các kiểm thử ứng dụng và server |
| `tools` | Công cụ build, ký và kiểm tra thiết bị dành cho người phát triển |
| `docs` | Hướng dẫn, báo cáo phiên bản và quyết định chọn mô hình |
| `output/VietLip-Final` | Hai file phân phối cuối: APK Android và EXE Windows |
| `artifacts` | Video và bằng chứng thử nghiệm cục bộ, không đưa vào Git/bộ cài |
| `research`, `server/experiments` | Thử nghiệm trước đây, không thuộc bộ cài cho người dùng |
| `packaging/legacy_windows_server_1_1` | Script bộ cài 1.1 cũ, chỉ giữ để tra cứu |

Thư mục build, cache, khóa ký và model vẫn được Git bỏ qua. Không đổi vị trí
model hoặc kết quả thử nghiệm đã được tham chiếu trong báo cáo. Bộ cài chỉ mang
SO17 đã chọn; không mang các video cá nhân hoặc checkpoint thử nghiệm khác.

## Tạo bộ cài mới

```powershell
.\build_android.ps1 -Mode release -OutputDir 'C:\VietLip-release\01-Android'
.\packaging\windows_server\build_installer.ps1 `
  -StageDirectory 'C:\VietLip-build\stage' `
  -OutputDirectory 'C:\VietLip-release\02-Server-Windows'
```

Stage phải là thư mục mới. Builder kiểm hash, thử import bằng Python đi kèm,
rồi tạo một Setup.exe chứa đầy đủ runtime và model, không cần file .bin ngoài.
Nếu môi trường phát triển đã dọn, builder dùng runtime và checkpoint của
VietLip Server đang cài; checkpoint vẫn phải khớp SHA-256 đã khóa.
Sau build cần cài thử và kiểm lại payload/API/điện thoại; build thành công
chưa chứng minh luồng cài đặt và nhận dạng hoạt động.
