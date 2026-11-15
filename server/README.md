# Current application runtime (VietLip 1.9.0)

The installed Windows application is `desktop_launcher.py` with the bundled
Python runtime. It shows the PC's LAN IP; Android connects over local Wi-Fi/LAN.
Build/install instructions: `../packaging/windows_server/README.md`. No USB
inference route, LLM or external API key is needed for the default SO17 workflow.
Optional AI text review runs after a session and preserves the raw caption.
See `../docs/READING_METHODS_1_9.md` for its separate PC configuration and endpoints.

Start `run_realtime.ps1` for the tested SO17 native runtime. Model startup and
visual-activity preparation finish before live connections are accepted. See the
root README and `docs/ARCHITECTURE.md` for the current workflow; older CLI/model
adapters described below remain for compatibility and experiments.

Runtime checks: `.venv/Scripts/python.exe -m ruff check app`,
`.venv/Scripts/python.exe -m ruff format --check app`, and
`.venv/Scripts/python.exe -m pytest -q`. Keep formatter changes out of vendor code.

## Historical server notes

The following sections describe older adapters and launchers. Use the root README for the installed application.

# Lip Reader API

> **Cấu hình ứng dụng 1.4.0 (2026-11-06):** chạy `run_realtime.ps1`, native SO_seed17, CUDA float32, WebSocket 2 ở 25 fps. `raw_face` mặc định tự endpoint bằng chuyển động môi. Xem README gốc và `docs/AUTO_LIVE_2026-11-06.md`. Phần tài liệu 1.1 bên dưới có đường dẫn D:, Lip_Final, Ollama và launcher full-stack cũ.

`start` nhận `auto_endpoint: true` để bật gate (mặc định cho raw_face).
`mouth_roi` mặc định giữ chế độ cửa sổ cũ; bật auto rõ ràng khi replay dữ liệu đã căn miệng.
Server trả `ready.auto_endpoint`, `activity` (speech_start/speech_end/endpoint_reason),
`telemetry` (recognition_state, decoder_state, capture_fps), `partial`,
`segment_final` tự động và `session_final` khi client gửi stop.
`activity_detector=estimated_lip_motion_v1` là ước lượng hình học, không phải xác suất
đang nói đã hiệu chuẩn. Camera không dừng sau segment_final. Không dùng audio hoặc
transcript tham chiếu cho detector. `auto_endpoint: false` chỉ dành cho so sánh phát triển.

FastAPI CPU-capable, GPU-preferred cho Auto-AVSR tiếng Việt. API nhận một MP4, căn mặt/crop
miệng bằng đúng implementation MediaPipe của Auto-AVSR, đưa về 25 fps và
transform giống benchmark (`96 -> center crop 88`, grayscale, normalize
`0.421/0.165`).

`WS /v1/realtime` nhận JPEG lấy mẫu từ camera và trả phụ đề thị giác sau mỗi vài
giây. Server prewarm model khi mở phiên, giải mã cửa sổ 6 giây chồng lấn 1 giây,
nối các đoạn vào transcript tích lũy, serialize với job cuối bằng cùng semaphore
và chỉ giữ snapshot mới nhất khi inference chậm hơn camera. Partial không gọi
LLM; `POST /v1/jobs` với MP4 tối đa 45 giây vẫn là kết quả độc lập để rà soát.

## Chạy server chuẩn

```powershell
cd D:\Project\Lip_App\lip_reader\server
.\setup_server.ps1
.\run_full_stack.ps1
```

`run_full_stack.ps1` đọc cấu hình local trong `.env`, kiểm tra Ollama/model rồi
preload Auto-AVSR. Nếu chỉ cần VSR hoặc dùng provider cloud đã quản lý riêng,
chạy `run_server.ps1`. Kiểm tra:

```powershell
Invoke-RestMethod http://127.0.0.1:7100/healthz
```

Dừng đúng cây tiến trình của API mà không tắt Ollama desktop:

```powershell
.\stop_server.ps1
```

`.env` hiện cấu hình Ollama `qwen2.5:7b`; file này bị Git ignore để không commit
secret khi đổi sang cloud. `run_server.ps1` sẽ đọc `.env` và preload model để
request app đầu tiên không chịu cold start. Muốn debug lazy-load thì đặt
`$env:LIP_MODEL_LOAD_ON_STARTUP = "false"` trước khi chạy.

## Chạy CPU (không cần GPU)

```powershell
.\setup_server.ps1 -Runtime cpu
$env:LIP_DEVICE = "cpu"
.\run_server.ps1
```

`LIP_DEVICE=auto` (mặc định) sẽ chọn CUDA nếu runtime CUDA khả dụng, ngược lại
tự fallback CPU float32. Có thể đặt `LIP_CPU_THREADS`; giá trị `0` tự chọn tối
đa 12 logical threads.

Asset căn mặt tải từ upstream hiện chỉ nên dùng cho research prototype vì
LICENSE nguồn có thêm giới hạn thương mại/BBC content. Xem `assets/README.md`;
phải thay bằng canonical reference tạo từ dữ liệu có quyền sử dụng trước phát
hành thương mại.

Kiểm tra end-to-end bằng video + word-timestamp CSV:

```powershell
.\.venv\Scripts\python.exe scripts\test_http_sample.py `
  C:\path\sample.mp4 C:\path\sample.csv --runs 2 --mode visual_only

.\.venv\Scripts\python.exe scripts\test_http_sample.py `
  C:\path\sample.mp4 C:\path\sample.csv --runs 1 `
  --mode llm_assist --context-hint "chủ đề/người nói" --accept-llm-risk
```

## Bật runtime GPU

1. Tạo/cập nhật `.env` từ `.env.example` hoặc đặt biến môi trường trong shell.
2. Cài bản PyTorch CUDA phù hợp driver từ trang chính thức PyTorch.
3. Chạy `.\setup_server.ps1 -Runtime gpu` để cài các dependency còn lại.
4. Chạy server và gửi MP4:

```powershell
$env:LIP_MODEL_LOAD_ON_STARTUP = "true"
.\run_server.ps1
curl.exe -F "video=@sample.mp4;type=video/mp4" `
  -F "input_kind=raw_face" `
  -F "mode=visual_only" http://127.0.0.1:7100/v1/transcriptions
```

GTX 1650 Ti 4 GB nên bắt đầu với đoạn 2–12 giây và `LIP_PRECISION=float16`.
Giới hạn vận hành là 1.125 frame/45 giây. Nên ưu tiên clip 2–12 giây;
VRAM và độ trễ thực tế phải được đo trước khi phát hành.

## Contract an toàn

- `status` luôn là `review_required`;
- raw score/margin không được gọi là xác suất đúng;
- `visual_only` không gửi video/transcript sang LLM;
- `context_select` chỉ được trả một candidate nguyên văn trong N-best;
- `llm_assist` đặt gợi ý ở `assisted_transcript`, không sửa `transcript`;
- hai mode LLM cần `context_hint` và `accept_llm_risk=true`;
- LLM lỗi/không cấu hình không làm mất kết quả visual;
- AV-HuBERT/EV-B-C-DAG không được phép thay câu;
- file upload được lưu tạm và xóa trong `finally`;
- `/v1/jobs` trả 202, dùng bounded queue một model, xóa video sau hoàn tất/hủy
  và hết hạn metadata kết quả; endpoint đồng bộ được giữ tương thích;
- `consensus_transcript` là N-best medoid để rà soát, không thay `transcript` và
  không phải xác suất đúng;
- `/healthz` không trả đường dẫn checkpoint.
- `/v1/realtime` chỉ trả phụ đề cần rà soát, không thay kết quả MP4 và không
  chuyển hình ảnh sang LLM.

## Job API cho CPU và clip dài

```powershell
$accepted = curl.exe -s -F "video=@sample.mp4;type=video/mp4" `
  -F "mode=visual_only" http://127.0.0.1:7100/v1/jobs | ConvertFrom-Json
Invoke-RestMethod "http://127.0.0.1:7100/v1/jobs/$($accepted.job_id)"
```

`LIP_MAX_QUEUED_JOBS` mặc định là 8; khi đầy, server trả 429 thay vì nhận video
không giới hạn. `LIP_JOB_RETENTION_SECONDS` mặc định 1800. Companion server chỉ
chạy một Uvicorn worker để không nhân bản checkpoint; triển khai nhiều máy cần
queue ngoài như Redis/RabbitMQ và worker model riêng.

Chạy test nhẹ, không cần checkpoint:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## LLM local đã cấu hình

Máy test dùng Ollama native để có JSON schema chặt và giải phóng model ngay sau
mỗi request:

```powershell
$env:LIP_LLM_PROVIDER = "ollama"
$env:LIP_LLM_BASE_URL = "http://127.0.0.1:11434"
$env:LIP_LLM_MODEL = "qwen2.5:7b"
$env:LIP_LLM_NUM_CTX = "2048"
$env:LIP_LLM_MAX_OUTPUT_TOKENS = "160"
$env:LIP_LLM_KEEP_ALIVE = "0"
```

`keep_alive=0` đổi latency cold cao hơn để trả khoảng 5 GB RAM/VRAM cho VSR sau
mỗi lượt. Trên máy nhiều RAM có thể đặt `5m` để giảm latency LLM warm.

Để dùng cloud/private OpenAI-compatible, đổi `LIP_LLM_PROVIDER` thành
`openai_compatible`, đặt base URL kết thúc ở `/v1`, model và API key. Chỉ text
N-best + context được gửi sang LLM; video luôn chỉ đi qua VSR. `/healthz` kiểm
tra provider/model thật thay vì chỉ báo “đã cấu hình”.
