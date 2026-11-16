# VietLip — bảo trì và lưu trữ

## Kiểm tra source

`tools/check.ps1` chạy Ruff, kiểm tra định dạng Python/Dart, Flutter analyze,
Flutter tests và server tests. Python mặc định là `server/.venv/Scripts/python.exe`;
có thể chỉ định `-Python` để dùng môi trường đã cài thư viện phát triển.

Code camera, giao tiếp WebSocket, phụ đề và lịch sử được đặt trong các module
`lib/src/data` và `lib/src/features`. Server runtime ở `server/app`. Mã upstream
trong `server/vendor` và `packages/camera_android_camerax` được giữ riêng, có license.
Các script nghiên cứu ở `server/experiments` không tham gia đường nhận dạng mặc định.

Lần dọn ngày 10/11/2026 chuẩn hóa định dạng 14 module Python, bỏ hai import không
dùng trong tests, và kiểm tra AST của code runtime trước/sau: không đổi logic.
Kết quả: 118 server tests và 29 Flutter tests qua; Flutter analyze và Ruff sạch.
Một cảnh báo deprecation từ thư viện Starlette vẫn còn. Dart đã đúng định dạng.

## Bộ cài gồm hai file

Bộ cuối hiện tại: `output/VietLip-Final`, phiên bản 1.10.1.

- `VietLip-1.10.1.apk`: cài cập nhật Android, giữ lịch sử.
- `VietLip-Server-Setup-1.10.1.exe`: chạy trực tiếp trên Windows x64; đã chứa
  Python, thư viện CPU/CUDA và checkpoint SO17, không cần ZIP hoặc BIN bên cạnh.

Thư mục phân phối chỉ có hai file; biên nhận, source và bằng chứng kiểm thử nằm
trong project. Mặc định Trực tiếp; AI khôi phục từng câu qua Groq/OpenRouter vẫn
là lựa chọn trong Cài đặt. Xem `LIVE_AI_1_10.md`.

Tạo lại EXE từ stage đã có manifest:

```powershell
.\packaging\windows_server\build_installer.ps1 -SkipStage `
  -StageDirectory C:\VietLip-stage -OutputDirectory C:\VietLip-final
```

Builder kiểm toàn bộ hash payload và runtime trước khi nén một EXE. Đặt APK có
ký từ `build_android.ps1` cạnh EXE. `tools/package_delivery.py` chỉ còn phục vụ
các bộ kit ZIP lịch sử, không thuộc cách phân phối cuối hiện tại.
EXE tự giải nén cần khoảng 3,5 GB trống ở ổ tạm, ngoài khoảng 6 GB cho bản đã cài.
Tham số `--verify` kiểm tra toàn bộ dữ liệu nhúng mà không cài đặt. Phần bootstrap
có sáu kiểm thử tích hợp Windows trong `packaging/windows_server/tests`.

Trước khi dọn staging/bộ cài cũ, phải cài thử chính EXE, kiểm lại manifest trong
thư mục cài, server health và kết nối Wi-Fi từ điện thoại. Ghi hash hai file cuối,
biên nhận cài đặt và dung lượng trống C/E trước/sau trong artifact của đợt phát hành.

## Tái tạo và lưu trữ

`build`, `.dart_tool`, `.gradle`, `__pycache__` và cache lint/test là dữ liệu sinh ra.
Giữ source, `pubspec.lock`, requirements đã khóa phiên bản, assets, patch CameraX
và khóa ký khi cất project. Khóa ký, video và model chỉ nằm trong backup riêng tư.

Môi trường phát triển có thể tạo lại bằng Python 3.11, các file requirements của
server, Flutter SDK và `flutter pub get`. Runtime Windows sử dụng được ngay từ
bộ cài đi kèm, không cần môi trường phát triển. Thư mục staging được tái tạo bằng
`packaging/windows_server/build_installer.ps1` theo `PROJECT_MAP.md`.

Các checkpoint tự train, video gốc và kết quả đánh giá có nguồn gốc riêng: chỉ
xóa local khi backup có manifest/hash và bằng chứng đọc lại. Git không chứa các
payload đó. Chỉ mục backup ngày 10/11/2026 ghi rõ bản nào đã xác minh, bản nào
đang chờ; sự tồn tại của thư mục Drive không có nghĩa là backup đã hoàn tất.
