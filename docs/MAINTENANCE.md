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

Thư mục dùng hằng ngày: `C:\Users\thien\Downloads\VietLip`.

- `VietLip-1.6.3.apk`: cài/cập nhật Android.
- `VietLip-Windows-1.6.3.zip`: giải nén toàn bộ, mở `BAT_DAU.txt`, chạy EXE
  trong `02-Server-Windows`; giữ hai BIN cạnh EXE trong lúc cài.

ZIP dùng đúng binary của bản 1.6.3 đã kiểm chứng trên điện thoại và Windows.
Nó có hướng dẫn Wi-Fi và checksum từng file; không có video thử nghiệm hoặc khóa ký.
Việc dọn định dạng source không thay đổi phiên bản hay kết quả nhận dạng của binary.

Tạo lại gói phân phối từ bộ cài đã có manifest:

```powershell
python tools/package_delivery.py --kit C:\VietLip-release `
  --output C:\VietLip-two-files --receipt C:\VietLip-delivery-receipt.json
```

Lệnh từ chối thư mục đầu ra đã tồn tại, kiểm mọi hash nguồn, rồi đọc lại và kiểm
hash mọi nội dung ZIP. Gói nguồn và bộ cài được giữ nguyên trong lúc đóng gói.

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
