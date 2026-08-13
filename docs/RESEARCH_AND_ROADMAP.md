# Research và roadmap cho VSR tiếng Việt tự nhiên

## Evidence mới đáng theo dõi

1. [Real-time AV-ASR của PyTorch](https://pytorch.org/blog/real-time-speech-rec/)
   dùng Emformer RNN-T và báo cáo mô hình nhỏ có RTF dưới 1 trên CPU. Đây là
   blueprint đúng cho streaming, nhưng là AVSR/English và cần retrain tiếng
   Việt; không thể áp trực tiếp lên checkpoint offline hiện tại.
2. [VALLR (ICCV 2025)](https://openaccess.thecvf.com/content/ICCV2025/html/Thomas_VALLR_Visual_ASR_Language_Model_for_Lip_Reading_ICCV_2025_paper.html)
   tách visual-to-phoneme và phoneme-to-text bằng language model để xử lý
   homophene/context. Hướng này đáng thử với âm vị/âm tiết tiếng Việt, nhưng
   project hiện tại đã có các auxiliary onset/rime và LoRA reranker thất bại,
   nên phải là protocol mới chứ không đưa thẳng vào app.
3. [Landmark-guided cross-speaker VSR (LREC-COLING 2024)](https://aclanthology.org/2024.lrec-main.876/)
   nhắm trực tiếp speaker variation. Đây là hướng khớp nhất với benchmark
   signer-independent hiện tại.
4. [Inter-language transfer cho low-resource VSR](https://aclanthology.org/2024.sigul-1.19/)
   cho thấy pretrain English frontend rồi fine-tune target language có ích khi
   dữ liệu gán nhãn ít. Project đang dùng đúng tinh thần này; bước tiếp theo là
   kiểm tra frontend adaptation có kiểm soát và dữ liệu raw-camera Việt.
5. [AudioVSR (EMNLP 2024)](https://aclanthology.org/2024.emnlp-main.858/)
   và [SynthVSR (CVPR 2023)](https://openaccess.thecvf.com/content/CVPR2023/html/Liu_SynthVSR_Scaling_Up_Visual_Speech_Recognition_With_Synthetic_Supervision_CVPR_2023_paper.html)
   dùng audio/synthetic visual data để tăng dữ liệu. Phù hợp cho rare words,
   thanh điệu và camera conditions, với điều kiện audit lip-sync/identity bias.
6. [VSP-LLM (Findings EMNLP 2024)](https://aclanthology.org/2024.findings-emnlp.666/)
   dùng self-supervised visual features và LLM cho context. Về sản phẩm, chỉ nên
   thử constrained N-best reranking và luôn hiển thị bản visual gốc; free-form
   rewrite dễ tạo câu trôi chảy nhưng sai bằng chứng môi.
7. [SwinLip (2025)](https://arxiv.org/abs/2505.04394) giảm compute của visual
   encoder. Đây là candidate cho on-device/edge sau khi tái lập trên tiếng Việt.
8. [Đánh giá generalization mới (2026)](https://arxiv.org/abs/2606.07259) tiếp
   tục cảnh báo model AVSR sụt mạnh trên unseen data dù phân phối được kiểm
   soát. Điều này củng cố việc giữ `review_required` và xây raw-camera test.
9. [Streaming AVSR với alignment regularization](https://arxiv.org/abs/2211.02133)
   dùng chunk-wise self-attention, causal convolution và triggered attention.
   Đây là bằng chứng rõ rằng VSR/AVSR không bắt buộc “một video, một lần
   inference”; tuy nhiên khả năng streaming nằm trong kiến trúc/training, không
   thể tạo ra bằng cách cắt tùy ý checkpoint full-context hiện tại.
10. [MMS-LLaMA (Findings ACL 2025)](https://aclanthology.org/2025.findings-acl.1065/)
    nén luồng AV thành ít token hơn trước khi đưa vào LLM. Ý tưởng token
    compression đáng thử về lâu dài, nhưng kết quả audio-visual tiếng Anh không
    chứng minh hiệu quả cho visual-only tiếng Việt.
11. [Speaker-adaptive prompt tuning](https://arxiv.org/abs/2302.08102) báo cáo
    cải thiện trên người chưa thấy với dưới 5 phút adaptation data. Đây là
    candidate hợp lý cho chế độ cá nhân hóa opt-in, sau khi có protocol chống
    leakage và cơ chế xóa adapter của người dùng.
12. [Sub-word VSR + visual speech detection (CVPR 2022)](https://openaccess.thecvf.com/content/CVPR2022/html/Prajwal_Sub-Word_Level_Lip_Reading_With_Visual_Attention_CVPR_2022_paper.html)
    gợi ý hai mảnh hữu ích cho tiếng Việt: unit dưới mức từ và detector phát
    hiện đoạn đang nói. Detector có thể giảm khoảng lặng trước/sau, nhưng cần
    giữ pre/post-roll để không cắt mất âm đầu/cuối.
13. [Whisper-Streaming](https://arxiv.org/abs/2307.14743) chứng minh có thể bọc
    một model offline bằng local agreement để tạo partial có tiền tố ổn định và
    độ trễ thích nghi. Đây là cơ sở cho preview 1.1.0; phương pháp không biến
    checkpoint thành causal và output cuối vẫn phải chạy trên video đầy đủ.

## Các dạng deployment khả thi

| Dạng | Model hiện tại | Latency cảm nhận | Việc cần làm |
|---|---:|---:|---|
| Full-clip đồng bộ | Có | Chờ sau khi quay | MVP đang dùng; warm worker, giới hạn 2–12 giây |
| Full-clip bất đồng bộ | Đã triển khai | App nhận job/progress | HTTP 202 + bounded queue + polling + TTL; hợp CPU/clip dài |
| Dynamic batching nhiều người | Có thể benchmark | Tăng nhẹ để đổi throughput | Bucket theo số frame, padding mask, kiểm tra output parity/OOM |
| Caption cửa sổ chồng lấn | Đã triển khai có giới hạn | Partial sau mỗi vài giây | JPEG 8 fps, cửa sổ 6 giây/chồng 1 giây, latest-only, tối đa 5 phút |
| Streaming thật | Không | Partial ổn định hơn | Train causal/chunked encoder + CTC/RNN-T, cache state, endpointing |
| On-device hoàn toàn | Chưa | Thấp, riêng tư | Distill/quantize model nhỏ; benchmark thermal/RAM/WER trên máy thật |
| Hybrid edge/server | Có thể làm sớm | Upload nhẹ và ít lỗi | Trên máy: face/quality/VSD; server: crop chuẩn + full model |

Release hiện dùng hybrid: điện thoại lưu video đầy đủ và có thể gửi JPEG lấy mẫu
qua WebSocket để nhận caption local-agreement; server vẫn trả job cho MP4 ngắn,
giữ một model nóng và xử lý tuần tự. Hàng đợi có giới hạn 8 job, kết quả giữ 30
phút, video tạm bị xóa ngay khi job kết thúc/hủy. Khuyến nghị mở rộng là điện
thoại cảnh báo chất lượng và trim khoảng lặng; GPU worker giữ model nóng, xử lý
full clip. “Một video một
inference” ở đây là contract của model, không có nghĩa phải start process/model
lại cho từng video. Một worker có thể phục vụ nhiều request tuần tự; khi tải
tăng, API chuyển thành job queue và scale worker theo GPU.

### Kết quả deployment CPU đã đo

Trên i7-10750H, sample 4,76 giây chạy PyTorch CPU float32/11 threads mất 13,98
giây cold và 5,12 giây warm; app Samsung → server warm mất 5,03 giây. Vì thế
CPU server là phương án thật, không phải mock. Production nhỏ có thể dùng một
worker preload + queue; không tăng Uvicorn workers tùy ý vì mỗi process nhân
bản checkpoint/RAM.

Track tối ưu tiếp theo nên tách frontend/encoder tensor graph khỏi SentencePiece
và beam decoder Python, sau đó thử ONNX Runtime/OpenVINO trên đúng parity suite.
Dynamic INT8 hợp để thử với phần Transformer/Linear, static calibration hợp hơn
với CNN frontend; không quantize toàn pipeline rồi chỉ nhìn latency. Mỗi biến
thể phải giữ transcript/N-best parity hoặc báo lại WER/CER trên signer-held-out.
`torch.export`/AOTInductor là track Linux server; không phải shortcut cho app
Android hiện tại và custom ESPnet beam search có thể vẫn cần runtime riêng.

## Ba mức LLM trong sản phẩm

1. `visual_only` — mặc định, không gọi LLM.
2. `context_select` — gửi N-best text + chủ đề; LLM chỉ trả index và server chỉ
   chấp nhận một candidate nguyên văn. Đây là mức nên A/B test đầu tiên.
3. `llm_assist` — cho phép viết lại tự do, nhưng trả ở `assisted_transcript`
   riêng, có consent và nhãn “có thể suy đoán”. Server từ chối câu có token mới
   ngoài N-best/ngữ cảnh, thay quá 35% token hoặc similarity dưới 0,45. Không
   dùng làm ground truth.

Video không cần gửi sang LLM. Với provider local tương thích OpenAI, cả N-best
và context có thể nằm trong mạng riêng. Dù dùng local hay cloud, log phải tách
`raw_visual`, `assisted`, mode/model/prompt version; feedback của người dùng
không tự động biến thành nhãn train nếu chưa có opt-in riêng.

## Roadmap thực dụng

### P0 — MVP hiện tại

- one-shot upload, crop đúng training contract, Auto-AVSR owner;
- full/short-range merge, FaceMesh rescue, orientation/rotation validation;
- beam-10/N-best-10 alternatives, raw diagnostics, retake;
- không gọi score là confidence;
- đo latency/VRAM/crop failure trên máy thật.
- thay `20words_mean_face.npy` research asset bằng canonical reference tạo từ
  dữ liệu có quyền sử dụng trước commercial release.

### P1 — raw-camera calibration

- 20–30 người mới, nhiều điện thoại/ánh sáng/góc/quãng cách;
- prompt freeze trước, signer/source grouped split;
- báo WER/CER/exact, crop ratio, retake, p50/p95/p99;
- hiệu chuẩn quality/abstention từ tập này, không tái dùng test để tune.

### P2 — cải thiện “tự nhiên”

- speech start/end detection bằng mouth-motion nhưng giữ pre/post-roll;
- face alignment ổn định và quality hint ngay khi quay;
- user vocabulary/topic chỉ bias trong N-best có sẵn;
- personalization adapter opt-in, tách train/eval theo người;
- active-learning queue chỉ khi người dùng đồng ý và sửa transcript.

### P3 — model experiments

- landmark-guided frontend và speaker-invariance;
- cross-lingual/self-supervised pretraining;
- phoneme/âm tiết intermediate theo VALLR, so với direct text;
- synthetic Vietnamese conditions với leakage/bias audit;
- SwinLip/quantization/distillation cho edge.

Mỗi experiment phải so với Auto-AVSR frozen ở cùng split/decoder, có
signer-held-out evaluation và gate rõ. Gain trên source-dev không đủ để đi vào
production.

EV-B-C-DAG được khóa ngoài phạm vi phát hành 1.0.0 và chỉ là track batch/QC.
Router/policy vượt 6/6 unit test, nhưng cửa sổ chuẩn 256 sample không phù hợp
request đơn, verifier AV-HuBERT chưa được đóng gói và calibration cũ không còn
hợp lệ với checkpoint step 55986. Đây không phải dependency còn thiếu của app;
chỉ mở lại như một phiên bản nghiên cứu riêng sau khi tái tạo N-best, refit và
đạt gate coverage/latency trên batch độc lập.

Phần tái lập đã được triển khai ở `research/ev_bcdag`: frozen router/policy,
exact feature code và CLI batch advisor. Chạy thử trên bốn clip thực tế tạo một
verifier recommendation theo budget floor(0,49×4)=1, nhưng kết quả chỉ là minh
họa routing do cửa sổ chưa đủ 256, verifier chưa chạy và calibration khác
checkpoint. Đây là cách triển khai EV trung thực nhất với bằng chứng hiện có.

### P3b — N-best minimum-risk evidence đã triển khai

- tính score-weighted medoid trên word-edit distance;
- luôn giữ top-1 làm transcript owner;
- công bố medoid, top-1 support và expected edit risk như diagnostic;
- không gọi các đại lượng này là confidence hoặc xác suất đúng;
- bước tiếp theo là benchmark WER/CER của medoid trên raw-camera calibration
  trước khi cân nhắc dùng nó làm lựa chọn mặc định.

### P3c — phụ đề trực tiếp liên tục đã triển khai

- camera vừa ghi MP4 vừa lấy mẫu JPEG 360 px/8 fps trên isolate;
- WebSocket prewarm model, dùng chung semaphore với job và chỉ giữ snapshot mới;
- giải mã từ 2 giây; cửa sổ 6 giây chồng 1 giây được nối vào transcript tích lũy;
- phiên tối đa 5 phút, không gọi LLM; full-clip 45 giây vẫn là luồng độc lập;
- smoke test CPU checkpoint thật: partial cold khoảng 9,9 giây, lượt warm ngắn
  khoảng 1,8 giây; số này là latency vận hành, không phải metric chất lượng.

### P4 — streaming thật

- causal frontend + Emformer/RNN-T hoặc chunked Conformer;
- stateful WebSocket, backpressure và endpoint finalization;
- stability metric (revision/flicker), TTFT, endpoint latency;
- transcript partial phải được phân biệt rõ với final-reviewed output.

### P5 — deployment optimization sau khi metric đạt gate

- profile tách decode video, landmark/crop, encoder và beam decoder;
- warm model, pinned-memory/async transfer; bucket clip theo frame;
- thử FP16/BF16, `torch.compile`/ONNX/TensorRT theo output-parity suite;
- distill/quantize một visual encoder nhỏ cho quality/VSD hoặc full on-device;
- canary theo model version, rollback, queue deadline và overload rejection;
- không tối ưu throughput trước khi có raw-camera WER/crop gate đạt chuẩn.
