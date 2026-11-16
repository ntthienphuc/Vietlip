# VietLip 1.10.1 — bộ cài cuối và biên nhận dọn máy

Thư mục phân phối: `E:\Project\Lip_App\lip_reader\output\VietLip-Final`.
Shortcut `E:\Project\Lip_App\Bo cai VietLip.lnk` trỏ tới thư mục này.
Chỉ có hai file phân phối; các biên nhận ở `artifacts/final_release_20261116`.

| File | Số byte | SHA-256 |
| --- | ---: | --- |
| `VietLip-1.10.1.apk` | 60.980.425 | `0e97e449d926c53df8c7a5c8311d31092910c0ca87f5a88cdd590fb85c7b10e2` |
| `VietLip-Server-Setup-1.10.1.exe` | 3.387.350.582 | `e4f3c0046a122092d86db2cbe16f796e03dc55af4eea867f8c85780694ff8ac5` |

APK là bản có ký 1.10.1+20 đã dùng trong các phiên thử trên điện thoại. Hash đọc
trực tiếp từ APK đang cài khớp file cuối; `apksigner verify` xác nhận chữ ký v2.
Đợt chốt này thay cách phân phối Windows và cập nhật hướng dẫn, giữ nguyên mã
nhận dạng của Android/server đã kiểm chứng trước đó.

EXE tự chứa bộ cài, Python 3.11.9, Torch 2.8.0+cu126, các thư viện và checkpoint
SO17; không cần tải model, cài Python hoặc giữ BIN cạnh EXE. Bootstrapper dùng
.NET Framework trên Windows 10/11 x64, kiểm SHA-256 toàn bộ archive và từng file
theo allowlist trước khi chạy Inno. Thư mục giải nén tạm riêng được dọn khi đóng.
Cần khoảng 6 GB cho bản đã cài và 3,5 GB trống ở ổ tạm, ngoài file EXE đã tải.
Nhật ký ở `%LOCALAPPDATA%\VietLip\logs`.

Mặc định trên điện thoại là **Trực tiếp**, nhận dạng bằng hình ảnh SO17. Khôi phục
câu qua Groq/OpenRouter vẫn là lựa chọn trong Cài đặt. Cấu hình/API key của PC
được giữ riêng ngoài thư mục cài và không được đưa vào bộ cài. Trên PC mới,
Trực tiếp dùng Wi-Fi/LAN nội bộ; AI tùy chọn cần cấu hình key và Internet riêng.

## Kiểm chứng thực tế

- Sáu kiểm thử tích hợp bootstrapper qua: xác minh payload, chặn dữ liệu bị sửa,
  chặn footer bị thiếu, chuyển nguyên tham số và mã thoát của installer, dọn
  thư mục tạm, bảo vệ file cuối đã có và từ chối payload thiếu BIN nội bộ.
- Chạy `--verify` trên chính EXE 3,39 GB: thành công, cả ba thành phần nội bộ
  khớp SHA-256.
- Đóng launcher bình thường, giữ tạm bản cài trước, rồi chạy EXE cuối để cài vào
  thư mục sạch tại `%LOCALAPPDATA%\Programs\VietLip Server`. Setup trả mã 0.
  Windows ghi phiên bản 1.10.1; Start Menu trỏ đúng launcher của bản mới.
- Toàn bộ **11.925 file**, 5.482.995.135 byte trong manifest, khớp hash ở bản
  đã cài. Đã kiểm lại toàn bộ sau khi xóa staging/bản cũ.
- Cửa sổ `VietLip Server · 1.10.1` chạy; health báo SO17 ready, CUDA, float32,
  realtime available. Địa chỉ LAN khi kiểm tra: `http://192.168.1.9:7100`.
- Điện thoại SM-G965F/Android 10 kiểm kết nối thành công qua Wi-Fi; ADB reverse
  rỗng. Một lượt bắt đầu/kết thúc live đạt camera **25 fps**, không lỗi luồng.
  USB dùng điều khiển QA. Lượt này chỉ kiểm vận chuyển/khởi tạo/kết thúc; không
  có câu chuẩn để chấm WER hoặc đo độ trễ sau lời nói.
- Lịch sử mở được và hiển thị 50 phiên. Sau dọn, màn hình chính vẫn báo máy chủ
  sẵn sàng và chế độ Trực tiếp.
- 38 file được bảo vệ, gồm 33 video/âm thanh thử nghiệm, khóa ký, cấu hình/key
  và model đang cài: hash trước/sau không đổi. Không có file source Git bị xóa.

Các kiểm tra cài đặt này diễn ra trên chính PC và điện thoại hiện có, không phải
chứng nhận cho mọi PC/điện thoại. Cấu hình nhận dạng được giữ theo quyết định
trong [báo cáo tám phiên đoạn văn](PARAGRAPH_BENCHMARK_2026-11-16.md); đóng gói
không làm thay đổi WER hoặc bảo đảm độ trễ 2–3 giây cho mọi câu.

## Dọn các bản trước

Đã xóa 34 mục: bản phân phối 1.6.3 trong Downloads, các thư mục output 1.7.0,
1.8.0, 1.9.0, 1.10.0 và bản đóng ZIP 1.10.1; các APK đọc lại/trùng, installer
trung gian, staging, kit cũ, cache build Flutter/Gradle và bản cài tạm đối chiếu.
Không còn APK nào trong repo ngoài file cuối; không còn mục nào chờ xóa trong
danh sách đợt này. Manifest/hướng dẫn nhỏ của các bộ cũ được lưu riêng trong
`archived_release_receipts`; video, kết quả benchmark, source và khóa ký được giữ.

| Ổ | Trống ở mốc đầu đóng gói | Trống sau dọn | Tăng ròng |
| --- | ---: | ---: | ---: |
| C | 24,60 GB | 28,29 GB | 3,69 GB |
| E | 48,78 GB | 93,30 GB | 44,52 GB |
| Tổng | | | **48,21 GB**, khoảng **44,90 GiB** |

GB trong bảng là 10^9 byte. Đây là chênh lệch dung lượng trống đo được, đã tính
cả file cuối mới tạo; không cộng kích thước logic của hard link và không coi
bản cài tạm đối chiếu là dung lượng người dùng được giải phóng ròng.

Các biên nhận chính:

- `INSTALLER_PACKAGE.json`, `PAYLOAD_MANIFEST.json`: hash và danh sách payload.
- `bootstrap-tests.log`, `apk-signature.log`: kiểm thử đóng gói/chữ ký.
- `INSTALL_RUN.json`, `setup-installed.log`: chính EXE cuối đã cài thành công.
- `INSTALL_ACCEPTANCE.json`, `POST_CLEANUP_ACCEPTANCE.json`: kiểm hash trước/sau dọn.
- `PHONE_WIFI_CHECK.json`, `phone-live-smoke/RESULTS.json`: Wi-Fi và 25 fps.
- `CLEANUP_PLAN.json`, `CLEANUP_RESULT.json`, `SPACE_SUMMARY.json`: phạm vi dọn và dung lượng đo.

Mã nguồn đóng gói ở `packaging/windows_server`, có recipe trong
[hướng dẫn bảo trì](MAINTENANCE.md). Các payload lớn được Git bỏ qua; mã nguồn,
hướng dẫn và kiểm thử đóng gói được lưu bằng commit cục bộ.
