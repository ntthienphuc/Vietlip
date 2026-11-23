# Tự build VietLip 1.10.5

Hai sản phẩm của phiên bản này là APK Android (build 30, package `vn.lipread.lip_reader`) và bộ cài VietLip Server cho Windows x64. Chạy các lệnh PowerShell dưới đây từ thư mục chứa `pubspec.yaml`. Chọn đường dẫn làm việc ngắn, ví dụ `C:\src\vietlip`.

## 1. Lấy mã và checkpoint

- Nếu nhận ZIP source nội bộ, giải nén toàn bộ. Checkpoint đã nằm ở `server\models\SO_seed17.pt`.
- Với GitHub, chạy `git clone https://github.com/ntthienphuc/liplens-app.git vietlip` rồi `cd vietlip`. Chạy `.\tools\get_so17.ps1` để tải và kiểm tra checkpoint. Có thể [tải SO17 trực tiếp](https://github.com/ntthienphuc/liplens-app/releases/download/vietlip-1.10.5-so17/SO_seed17.pt) rồi lưu vào `server\models\SO_seed17.pt`. Chỉ build Android thì có thể bỏ qua checkpoint.
- Nếu PC đã cài VietLip Server 1.10.5 bằng EXE bàn giao, builder cũng có thể lấy runtime và checkpoint từ bản cài đó theo bước 3.

Đối chiếu checkpoint trước khi dùng. Script đóng gói cũng kiểm tra lại giá trị này.

```powershell
(Get-FileHash .\server\models\SO_seed17.pt -Algorithm SHA256).Hash
# CDDFB8C79F1DB9D66695C0B1B7E2D98837187C600668A8AEE3CCDD5B58981ECC
```

## 2. Build và kiểm tra APK Android

Cấu hình dùng để kiểm tra là Flutter 3.44.0 (Dart 3.12.0) và Android SDK có platform 36. Cài Android SDK, Build Tools và JDK tương thích với Gradle 9.1 (ví dụ JDK 17 hoặc 21). Kiểm tra đường dẫn SDK/JDK bằng `flutter doctor -v`. Lần build đầu cần Internet để tải dependency Flutter, Gradle và Android.

```powershell
flutter pub get --enforce-lockfile
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --debug --no-pub
```

APK để kiểm tra nằm ở `build\app\outputs\flutter-apk\app-debug.apk`. Để tạo bản release, người quản lý khóa ký cấu hình bốn biến môi trường trong phiên build hoặc kho bí mật của CI rồi chạy `flutter build apk --release --no-pub`.

| Biến | Giá trị |
| --- | --- |
| `LIP_READER_KEYSTORE_PATH` | Đường dẫn tuyệt đối tới keystore |
| `LIP_READER_KEYSTORE_PASSWORD` | Mật khẩu keystore |
| `LIP_READER_KEY_ALIAS` | Alias của khóa |
| `LIP_READER_KEY_PASSWORD` | Mật khẩu khóa |

Kết quả là `build\app\outputs\flutter-apk\app-release.apk`. Android yêu cầu chữ ký trùng với bản đang cài để cập nhật tại chỗ. Với khóa debug hoặc khóa riêng của đội triển khai, dùng máy thử hay giả lập riêng để giữ lịch sử trên điện thoại đang vận hành.

## 3. Build bộ cài Windows x64

Cài Inno Setup 6 (mặc định tại `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`). Builder sử dụng trình biên dịch C# của .NET Framework trên Windows. Chuẩn bị vài chục GB trống cho môi trường Python, stage, file nén tạm và EXE cuối.

**Máy phát triển mới.** Cài Python 3.11 x64 từ bộ cài Windows có Tcl/Tk và Python Launcher. Sau khi đặt checkpoint theo bước 1, tạo môi trường riêng. Chọn một trong hai cấu hình.

```powershell
.\server\setup_server.ps1 -Runtime gpu    # PyTorch 2.8.0 CUDA 12.6, cùng dòng bản bàn giao
# Hoặc cho bộ cài chỉ chạy CPU:
# .\server\setup_server.ps1 -Runtime cpu
```

**Máy đã cài VietLip Server 1.10.5.** Có thể bỏ qua bước tạo môi trường riêng. Khi checkout chưa có `server\.venv`, builder lấy Python và dependency từ runtime đã cài cho tài khoản Windows hiện tại. Mã ứng dụng và server vẫn lấy từ checkout.

Build bằng cùng một lệnh ở cả hai trường hợp. Mỗi lần chọn stage mới và thư mục đầu ra riêng. Có thể truyền `-InnoCompiler` nếu đã cài Inno ở vị trí khác.

```powershell
$work = Join-Path $env:TEMP ("vietlip-build-" + [guid]::NewGuid().ToString("N"))
.\packaging\windows_server\build_installer.ps1 -StageDirectory "$work\stage" -OutputDirectory "$work\out"
$exe = Join-Path $work 'out\VietLip-Server-Setup-1.10.5.exe'
$result = Start-Process -FilePath $exe -ArgumentList '--verify' -Wait -PassThru
if ($result.ExitCode -ne 0) { throw "Kiểm toàn vẹn EXE thất bại ($($result.ExitCode))" }
```

Bộ cài mặc định không chứa credential. Sau khi cài trên máy đích, vào **VietLip Server → Cài đặt key Gemini** nếu cần thử gợi ý câu. Chế độ phụ đề trực tiếp dùng mô hình SO17 trên PC qua mạng LAN.

## 4. Kiểm tra trước khi bàn giao

Với môi trường Python đã tạo ở bước 3, chạy bộ test từ thư mục server.

```powershell
Push-Location server
try {
    .\.venv\Scripts\python.exe -m pytest -q tests ..\packaging\windows_server\tests
} finally {
    Pop-Location
}
```

Để thử luồng thực tế, mở VietLip Server, chờ báo **Sẵn sàng đọc môi**, cho Android và PC dùng cùng Wi-Fi, rồi quét QR trong phần Cài đặt của app. Bắt đầu một phiên và kiểm tra phụ đề gốc. Để kiểm tra đường gọi Gemini, nhập key trên PC, bật **Kèm gợi ý câu** trên điện thoại và đối chiếu hai dòng sau khi chốt câu.
