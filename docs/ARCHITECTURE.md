# Kiến trúc Lip Reader

## Quyết định production

```text
Flutter camera / gallery
        |
        +-- sampled JPEG / WebSocket --> latest-only visual draft
        |                               -> local-agreement stable prefix
        |                               -> no LLM, review required
        |
        | MP4 + input_kind + processing mode + optional context/consent
        v
FastAPI upload boundary -> HTTP 202 job + bounded queue
        |
        | validate size/header/duration; temp file with guaranteed cleanup
        v
Frozen Auto-AVSR preprocessing
MediaPipe full/short-range -> FaceMesh rescue -> orientation check/rotation
-> temporal smoothing -> affine alignment
-> 96x96 grayscale mouth ROI -> 25 fps -> center crop 88 -> normalize
        |
        v
Vietnamese Auto-AVSR epoch 13
Conformer + hybrid attention/CTC beam 10, N-best 10, CTC weight 0.1
        |
        v
immutable raw transcript + alternatives + N-best medoid diagnostic
        |
        +------------------ visual_only ------------------> Human review
        |
        +-- context_select --> LLM may select one exact N-best candidate
        |
        +-- llm_assist ------> separate free-form suggestion (never replaces raw)
                                |
                                +--> Ollama native / cloud OpenAI-compatible
                                     (text evidence only; video never sent)
                                     -> token/similarity grounding validator
```

Auto-AVSR là transcript owner duy nhất. `visual_only` là mặc định. Hai chế độ
LLM cần ngữ cảnh và xác nhận rà soát; kết quả hỗ trợ luôn ở field/UI riêng để
provenance của kết quả thị giác không bị mất.

**Phạm vi phát hành 1.1.0 đã khóa:** EV-B-C-DAG và AV-HuBERT không phải thành
phần của request path. Đây là quyết định production, không phải một tính năng
đang chờ bật. Controller EV-DAG chuẩn tối ưu quyết định theo cửa sổ 256 mẫu,
trong khi sản phẩm xử lý từng video; với một hoặc hai request, budget 49% còn có
thể tạo ra 0 lượt verifier. Router cũng được hiệu chỉnh theo checkpoint cũ và
AV-HuBERT verifier không nằm trong gói CPU. Ghép các thành phần này vào bản
1.1.0 sẽ tăng kích thước, độ trễ và RAM mà không có bằng chứng tăng chất lượng
theo request. Mã nghiên cứu được giữ cho batch quality-control; chỉ mở lại track
này sau một benchmark riêng có N-best từ checkpoint step 55986, calibration,
coverage và latency gate.

Mã router, policy và CLI tái lập pre-verifier routing hiện được đóng gói trong
`research/ev_bcdag`. Đây là add-on batch/QC có provenance thật, không phải một
nút giả trong app. CLI chấp nhận tối đa 256 Auto-AVSR rows, công bố risk/expected
utility và đề xuất clip cần verifier. Nó không chạy AV-HuBERT, không tạo final
decision và luôn báo calibration có trước checkpoint epoch 13.

N-best consensus trên request path dùng score-weighted medoid theo khoảng cách
chỉnh sửa từ. Cơ chế này chỉ sinh `consensus_transcript` và diagnostic
`is_calibrated_probability=false`; `transcript` top-1 bất biến. Khi medoid khác
top-1, app hiển thị như một gợi ý đối chiếu riêng.

Crop không chỉ dựa vào tỷ lệ detect. Server kiểm tra hình học mắt–mũi–miệng,
thử các hướng 90/270/180 khi cần và xếp hạng bằng số landmark thẳng, độ phủ
full-range rồi tổng độ phủ. Điều này tránh trường hợp detector báo 100% trên
video nằm ngang nhưng ROI môi vẫn sai.

## Phụ đề trực tiếp và ranh giới streaming

Checkpoint hiện tại là offline Conformer/attention decoder, nên bản 1.1.0 triển
khai **near-real-time preview** thay vì tuyên bố streaming causal. Camera vẫn lưu
MP4 đầy đủ, đồng thời lấy mẫu 8 fps, xoay đúng hướng và nén JPEG 360 px trên
isolate. WebSocket server gom tối thiểu 2 giây, giải mã cửa sổ 6 giây chồng lấn
1 giây, dùng local agreement cho partial rồi chốt từng đoạn vào transcript tích
lũy. Một worker chỉ giữ snapshot mới nhất; partial cũ không tạo hàng đợi. Phiên
giới hạn 5 phút, không gọi LLM. Video tối đa 45 giây vẫn có thể chạy full-clip
độc lập; phiên dài hơn giữ caption trực tiếp và không upload nguyên MP4.

Streaming thật vẫn là model track riêng: causal visual frontend + Emformer/RNN-T
hoặc chunked Conformer, state cache và train/evaluate lại theo stability, TTFT,
WER/CER. WebSocket hiện tại là lớp triển khai an toàn quanh model offline, không
làm checkpoint offline trở thành causal.

## API V1

- `GET /healthz`: model state, CUDA, device, version; không lộ path checkpoint.
- `WS /v1/realtime`: JPEG frame stream, partial thị giác + stable prefix,
  latest-only backpressure; không LLM và không tạo kết quả cuối.
- `POST /v1/transcriptions`: multipart `video`, `input_kind`, `request_id`,
  `mode`, `context_hint`, `accept_llm_risk`.
- `POST /v1/jobs`: tải video, trả HTTP 202 ngay cùng `job_id`.
- `GET /v1/jobs/{job_id}`: trạng thái queued/processing/completed/failed và kết
  quả cuối; `DELETE` hủy job còn chờ hoặc bỏ kết quả của job đang chạy.
- `/docs`: OpenAPI UI của FastAPI.

Mọi response thành công có `status=review_required`. Raw beam score, N-best
entropy và margin chỉ là diagnostic, không phải xác suất đúng.

## Mobile UX

- Front camera mặc định, video không thu âm.
- Phụ đề trực tiếp là tùy chọn mặc định bật; lỗi caption không làm mất MP4.
- Phiên caption tối đa 5 phút; full-clip tối đa 45 giây, khuyến nghị 2–12 giây.
- Khung mặt và vùng miệng giúp người dùng tự căn.
- Có đường chọn video sẵn, retake, N-best alternatives và local history.
- Sau khi quay/chọn, tự cuộn tới video và ba chế độ xử lý.
- `context_select` bị chặn ở N-best; `llm_assist` có nhãn nguồn và yêu cầu đối chiếu.
- Result LLM hiển thị provider/model/runtime/reason; raw transcript luôn ở card
  riêng và luôn được lưu làm bản chính.
- App upload một lần rồi poll job; không tự thu thập train data.
- Bản 1.1.0 cho phép HTTP/WS tới companion server trong LAN tin cậy; triển khai qua
  Internet phải dùng HTTPS và network security policy chặt hơn.
- APK dùng khóa phân phối nội bộ, không dùng debug signing. Phát hành qua store
  phải dùng khóa release được quản trị và bảo vệ độc lập.

## Scale-up

V1 có bounded in-process queue và serialize inference bằng semaphore một GPU.
Đây là profile đúng cho companion server vì worker cần dùng chung model đã nạp.
Khi scale qua nhiều máy:

1. API gateway giữ upload/contract.
2. Job queue tách preprocessing và GPU worker.
3. Worker warm model một lần; một process/model trên CPU hoặc mỗi GPU.
4. Object storage dùng TTL ngắn hoặc không lưu video.
5. Theo dõi p50/p90/p95/p99, OOM, crop failure, retake và WER trên tập đồng ý
   gán nhãn; không theo dõi “confidence” giả.

Sample CPU 4,76 giây ngày 2026-07-24 đo được 13,98 giây cold và 5,12 giây
warm. Vì vậy standard server preload checkpoint; semaphore giữ một inference
mỗi worker để RAM/latency ổn định. Khi tải vượt một worker, chuyển contract
ngoài thành job async thay vì tăng nhiều Uvicorn worker trong cùng máy (mỗi
worker sẽ nhân bản checkpoint trong RAM).
