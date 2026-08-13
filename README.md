# Đọc môi Việt

Ứng dụng Flutter + FastAPI nhận dạng tiếng Việt từ video chuyển động môi.
Bản 1.1.0 dùng Auto-AVSR làm model owner, chạy được trên CPU, có phụ đề trực
tiếp qua WebSocket và cung cấp ba mức hỗ trợ ngữ cảnh. Kết quả luôn cần được
kiểm tra trước khi dùng làm phụ đề cuối.

## Thành phần

- `lib/`: app Android/iOS/Web/Windows; luồng chính là quay/chọn MP4, upload,
  xem transcript + alternatives, chọn mức hỗ trợ LLM, retake và local history.
- `server/`: FastAPI, bounded job queue, model adapter, exact Auto-AVSR
  preprocessing, upload validation và contract test. Detector dùng
  full/short-range, FaceMesh cứu hộ,
  kiểm tra hướng rồi mới chạy mean-face alignment và crop môi chính chủ.
- `docs/`: khảo sát hai workspace, kiến trúc và research roadmap.
- `research/ev_bcdag/`: frozen batch/QC router, policy và advisor tái lập; không
  nằm trên đường suy luận tương tác.
- `packaging/deployment/`: CPU container, Compose và reverse-proxy HTTPS mẫu.

## Chạy app

```powershell
cd D:\Project\Lip_App\lip_reader
flutter pub get
flutter run
```

Build/test Android bằng script sau để Gradle và Pub cache luôn nằm trên ổ D:

```powershell
$env:LIP_READER_RELEASE_PASSWORD = '<mật khẩu khóa ký nội bộ>'
.\build_android.ps1
```

Mật khẩu khóa ký chỉ được truyền qua biến môi trường trong phiên terminal và
không được lưu trong mã nguồn. Khi phát hành qua Play Store, thay khóa nội bộ
bằng khóa phát hành do chủ sở hữu sản phẩm quản lý.

Mở tab Cài đặt và nhập địa chỉ LAN mà Lip Reader Server hiển thị, ví dụ
`http://192.168.1.20:7100`. APK 1.1.0 cho phép HTTP tới companion server trong
mạng LAN tin cậy và được ký bằng khóa phân phối nội bộ. Phát hành qua Internet
cần chuyển API sang HTTPS và dùng khóa store được lưu trữ an toàn.

Ba chế độ xử lý:

- `Thuần chuyển động môi` (mặc định): không dùng LLM.
- `Chọn theo ngữ cảnh`: LLM chỉ được chọn nguyên văn một câu trong N-best.
- `Gợi ý câu tự nhiên`: LLM tạo một gợi ý riêng; app vẫn giữ bản visual gốc.

Hai chế độ sau bắt buộc có ngữ cảnh và xác nhận người dùng sẽ rà soát kết quả.
Decoder production dùng đúng protocol ViCocktail: beam 10, N-best 10, CTC 0.1.
LLM Assist còn phải qua validator grounding phía server; prompt đúng chưa đủ.

Khi bật **Phụ đề trực tiếp**, app đồng thời lưu MP4 và gửi JPEG 360 px ở 8 fps
qua `/v1/realtime`. Server giải mã cửa sổ 6 giây chồng lấn 1 giây, chốt từng đoạn
vào transcript tích lũy và dùng backpressure latest-only khi CPU không theo kịp.
Phiên kéo dài tối đa 5 phút. Đây là near-real-time caption cho checkpoint offline,
không phải mô hình streaming causal. LLM không chạy trên partial; với video tối
đa 45 giây, người dùng vẫn có thể chạy full-clip để nhận kết quả cuối độc lập.

## Chạy server

```powershell
cd D:\Project\Lip_App\lip_reader\server
.\setup_server.ps1
.\run_full_stack.ps1
# Khi dùng xong:
.\stop_server.ps1
```

Mở `http://127.0.0.1:7100/docs`. `setup_server.ps1` mặc định cài PyTorch CPU,
nên server không GPU vẫn suy luận thật. Nếu có NVIDIA CUDA, cài wheel PyTorch
CUDA chính thức rồi dùng `requirements-gpu.txt`; server tự ưu tiên GPU và
fallback về CPU. Full-stack local hiện dùng Ollama `qwen2.5:7b`; video không
được gửi sang LLM. Xem [server/README.md](server/README.md).

## Kiểm thử

```powershell
flutter analyze
flutter test

cd server
.\.venv\Scripts\python.exe -m pytest -q
```

## Đọc trước khi phát triển model

- [Kiến trúc và ranh giới sản phẩm](docs/ARCHITECTURE.md)
- [Kết quả khảo sát hai workspace](docs/EXPLORATION_REPORT.md)
- [Research và roadmap](docs/RESEARCH_AND_ROADMAP.md)
- [Báo cáo kiểm thử thiết bị thật](docs/DEVICE_TEST_REPORT.md)

Checkpoint active là `epoch=13-step=55986-002.ckpt`, SHA-256
`6A41D0A3ACF15075A0E2F75EAD2215B5B8FCC38697885DE8EE851EB3FF576C00`.
Source server tham chiếu `Lip_Final/06_CHECKPOINT`; installer đóng gói bản đã
kiểm hash.

EV-B-C-DAG/AV-HuBERT được chủ động loại khỏi phạm vi phát hành 1.1.0. Controller
batch 256 mẫu không phù hợp request từng video và calibration cũ không hợp lệ
với checkpoint hiện tại; Auto-AVSR + N-best + cổng LLM có kiểm soát là cấu hình
production đã khóa của phiên bản này.

App 1.1.0 gửi video qua `/v1/jobs`: upload trả HTTP 202, app poll trạng thái và
nhận kết quả sau. Endpoint đồng bộ cũ vẫn được giữ để tương thích. Mỗi response
còn có N-best consensus diagnostic/medoid để đối chiếu nhưng không sửa top-1.
