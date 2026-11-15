# VietLip — sơ đồ project

Mã ứng dụng đang bảo trì: `E:\Project\Lip_App\lip_reader`.
Bộ cài mới nhất: `output/VietLip-1.9.0` (APK + ZIP Windows).
Các bộ cài trong Downloads hoặc thư mục phiên bản cũ được giữ để đối chiếu/khôi phục.
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
| `output/archive` | Các APK/bộ cài/báo cáo xuất trước VietLip 1.6.0 |
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
rồi tạo Setup.exe và các file dữ liệu .bin. Cần giữ chúng trong cùng thư mục.
Sau build cần cài thử vào đường dẫn khác và kiểm lại API/live; build thành công
chưa chứng minh luồng cài đặt và nhận dạng hoạt động.
