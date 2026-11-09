# Lip Reader 1.3.0 — tối ưu ứng dụng và phép đo trên PC

Mọi code/runtime/artifact mới nằm trong `E:\Project\Lip_App\lip_reader`.
Không huấn luyện lại hoặc sửa trọng số/nghiên cứu gốc, không publish/push.
Máy đo: GTX 1650 Ti 4 GB, RAM 16 GB, Windows; Android API35 x86_64 emulator.
Camera giả lập không có người nói. Accuracy đo bằng video cũ phát qua API thật.

## Camera

Đường cũ chuyển các plane YUV qua nhiều RPC CameraX → Dart → Kotlin. Đổi sang
NV21 đơn thuần không giải quyết được. Bản mới dùng bản sao plugin CameraX
0.7.4+2 trong `packages/camera_android_camerax`, nén JPEG trên một worker native
trước khi gửi sang Dart. Một lần encode và tối đa hai event chưa ACK; frame mới
bị bỏ khi đầy, không tích hàng đợi. Timestamp lấy từ ImageProxy. Preview và MP4
vẫn dùng plugin CameraX; toàn bộ ImageProxy được close trong finally.

Phép đo cuối 30 giây: **723 frame / 29,922 giây thời gian camera = 24,13 fps**,
nén trung bình **11,57 ms/frame**, nguồn **720×480**, JPEG quality 80.
So với phép đo cũ khoảng 13 fps, bottleneck chuyển plane đã giảm rõ.
Đây là FPS emulator/transport, không phải FPS hay chất lượng camera điện thoại thật.
Raw receipt: `artifacts/optimization_v2/camera_1793936568238179000.json`.

UI chỉ nhắc “Bắt đầu nói” khi nhận được frame đầu, giúp tránh nói trong lúc
CameraX còn mở luồng. Recording, lifecycle, timestamp/ACK và lưu history được giữ.

## Decoder

Đo tách frontend/encoder/search cho thấy search chiếm phần lớn thời gian.
KV cache riêng cho từng beam tránh tính lại attention của toàn bộ tiền tố.
CTC prefix trên GPU vốn chạy hàng nghìn phép toán rất nhỏ; dùng recurrence NumPy
của ESPnet trên CPU, giữ neural encoder/decoder trên CUDA. Không đổi checkpoint,
beam, trọng số CTC, từ vựng hay thêm câu mẫu. Bộ nhớ đệm source reset mỗi search.
Các trạng thái CTC sớm không hợp lệ được đặt log-zero trước khi tái sử dụng.

**34/34 clip có top-1 và cả N-best 3 giống nhau** trong phép so sánh trên cùng
encoder features. Search trung bình **1,564 → 0,356 giây**, khoảng **4,4 lần**.
Đây là thời gian search, không phải tổng end-to-end hay bảo đảm mọi đầu vào giống bit.
Unit tests kiểm cả đổi thứ tự/nhân bản beam, câu mới, từ lặp và EOS ngoài prebeam.
Receipt: `CPU_CTC_PARITY.json`; KV-only: `INCREMENTAL_PARITY.json`.

Rollback chẩn đoán: đặt `LIP_INCREMENTAL_DECODER=0` và
`LIP_CTC_PREFIX_DEVICE=cuda` trước khi chạy server.

## Toàn bộ checkpoint SO/WW

Chọn trước 32 clip từ bản sao validation archive bằng thứ tự SHA256, tối đa 2 clip
mỗi nhóm tên file; 28 nhóm, không khẳng định đó là 28 người. 16 clip chẵn dùng chọn
cấu hình, 16 clip lẻ giữ riêng để kiểm tra ứng viên sau đó. Không khẳng định dữ liệu
này độc lập với quá trình huấn luyện checkpoint. Reference không đi vào inference.
WER là edit distance sau NFC, chữ thường, bỏ dấu câu, tách theo khoảng trắng tiếng Việt.

| Checkpoint | 16 clip phát triển mới (314 đơn vị) | 6 ROI cũ (120) | 2 clip mặt cũ (33) |
|---|---:|---:|---:|
| SO seed17 | 63,38% | 40,83% | 39,39% |
| SO seed29 | 62,74% | 40,00% | 39,39% |
| SO seed43 | 64,01% | 44,17% | 39,39% |
| WW seed17 | 62,10% | 32,50% | 54,55% |
| WW seed29 | 61,15% | 35,00% | 51,52% |
| WW seed43 | 61,78% | 31,67% | 54,55% |

Tất cả dùng beam 3, CTC=.1, cùng tensor đã chuẩn bị. Thử beam 1/3/5, CTC .1/.3/.5
với WW29: trên nhóm phát triển mới + hai clip mặt, CTC=.5 giảm 209 xuống 202 lỗi.
Tuy nhiên kiểm tra 16 clip giữ riêng: WW29/.5 **174/320 = 54,38%**, SO17/.1
**169/320 = 52,81%**. Do đó giữ SO17 mặc định; không chọn WW29 chỉ theo điểm phát triển.
Các file `MATRIX_beam3.json`, `*_frozen_ctc*.json`, `WW_seed29_decoder_options.json`
giữ từng reference, hypothesis và lỗi để đối chiếu.

## LLM

Đã tải và chạy cục bộ Qwen3-1.7B Q4_K_M bằng llama.cpp CPU. Không cần API key,
không gửi video/transcript ra dịch vụ ngoài. Model SHA256:
`b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897`.
Nguồn: [Unsloth GGUF](https://huggingface.co/unsloth/Qwen3-1.7B-GGUF),
[Qwen3 model](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF),
[llama.cpp](https://github.com/ggml-org/llama.cpp).

Chỉ cho LLM chọn một id trong N-best, không cho viết thêm transcript; output sai,
timeout hoặc đang bận trả nguyên câu thị giác. Trên 32 clip WW29/.5, model chọn id 0
cả 32 lần: **365 lỗi trước và sau**, thêm khoảng 2 giây/lượt. Vì vậy **LLM tắt mặc
định trong live**. Đây là kết quả của model/prompt cụ thể, không kết luận mọi LLM
đều không giúp. Oracle N-best là 354 lỗi: trần lợi ích của chỉ chọn 3 câu cũng nhỏ.
Receipt: `llm_selector_unbounded.json`; adapter và benchmark ở `server/app/services/candidate_selector.py`
và `server/scripts/benchmark_llm_selector.py`. Các tùy chọn hỗ trợ LLM sau upload
vẫn có trong app; cần chủ động chạy/configure dịch vụ. Launcher thử local:
`server/run_local_llm.ps1`. Không tự bật sau khi khởi động app.

## Research dùng để quyết định

[Streaming AVSR, Interspeech 2023](https://www.isca-archive.org/interspeech_2023/ma23_interspeech.html)
dùng chunk-wise attention, causal convolution và triggered attention. Checkpoint
hiện tại là encoder offline; KV cache ở decoder không biến nó thành causal.
Giữ cửa sổ hữu hạn và đo độ trễ thực tế là lựa chọn ứng dụng với checkpoint đang có.
Kết quả có audio của paper không được dùng làm điểm tham chiếu cho app visual-only.

[VALLR, ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/html/Thomas_VALLR_Visual_ASR_Language_Model_for_Lip_Reading_ICCV_2025_paper.html)
dùng visual-to-phoneme và LLM đã fine-tune cho phoneme-to-text. Đây là pipeline
được huấn luyện riêng; không thể suy ra cùng mức cải thiện khi gắn prompt sửa câu
vào checkpoint tiếng Việt hiện tại.

[CameraX ImageAnalysis](https://developer.android.com/media/camera/camerax/analyze)
mô tả KEEP_ONLY_LATEST và yêu cầu close ImageProxy. Bản native bridge giữ các nguyên
tắc này; không dùng queue dài để làm số FPS nhìn có vẻ cao trong khi hình đã cũ.

## Video ghép dài và cách hiểu latency

32 clip, **634 đơn vị sau chuẩn hóa** (635 CSV rows), video liên tục **193,8 giây**;
bản chèn 1 giây giữ nguyên frame cuối giữa clip dài **225,8 giây**.
Khoảng nghỉ này là tổng hợp, không phải kiểm chứng phát hiện im lặng tự nhiên.
Nhiều nhóm/người thay đổi ở mối ghép; phép thử stress này không đại diện cuộc hội
thoại tự nhiên một người. Video, CSV, metadata và mọi event nằm dưới
`artifacts/optimization_v2`.

Latency “sau cuối đoạn” là lần cập nhật đầu tiên có cửa sổ bao phủ hết đoạn video,
không phải thời gian xuất hiện một câu đúng. WER được báo riêng để không che lỗi
bằng chỉ số tốc độ. Tất cả replay phát theo thời gian thật 25 fps qua WS protocol 2.

Kết quả thử cửa sổ 8 giây: liên tục **436/634 = 68,77% WER**, có nghỉ **441/634 =
69,56%**; nhận đủ 4.845 và 5.645 frame, không drop transport. Decode trung vị
0,566/0,557 giây; cập nhật sau cuối đoạn trung vị 1,021/1,063 giây, p95
1,446/1,477 giây. Dù nhanh, cửa sổ 8 giây kém WER hơn baseline 6 giây
**396/634 = 62,46%**, nên không chọn 8 giây làm mặc định.

Baseline 6 giây trước tối ưu: decode trung vị 1,689 giây, p95 2,321 giây;
cập nhật sau cuối đoạn trung vị 2,591 giây, p95 3,737 giây; stop-to-final 3,189 giây.
Một phần đầu baseline có tác vụ build trên PC; không coi đây là benchmark hệ thống
được cô lập hoàn toàn. Phép đo decoder paired trên cùng input là bằng chứng trực tiếp
cho speedup của thuật toán.

## Cấu hình cuối và kiểm chứng

SO17, beam 3, CTC .1, cửa sổ **6 giây**, cập nhật **1,5 giây**, right context **1 giây**.
Video 193,8 giây: **399/634 = 62,93% WER**, 4.845 frame/0 drop, decode trung vị
**0,476 giây**, p95 **0,566 giây**. Cập nhật sau cuối đoạn: trung vị **1,164 giây**,
p95 **1,772 giây**, 32/32 đoạn trong 3 giây. Stop-to-final **0,640 giây**.
WER chưa cải thiện so với baseline 62,46%; chênh 3 lỗi có thể đến từ lịch snapshot
khác. Không dùng speedup để khẳng định accuracy tăng.

Hai clip quay cả mặt: **10/33 = 30,30% WER**, 367 frame/14,68 giây, không drop.
Decode gồm preprocess trung vị 1,127 giây, p95 3,015 giây (có cold face detection);
cập nhật sau cuối hai clip 1,47 và 1,80 giây, stop-to-final **1,471 giây**.
Lần trước cùng nhóm clip đã dao động 36,4–48,5% theo lịch snapshot/tải máy, nên
không dùng 30,3% của hai clip để suy ra độ chính xác chung.

Tổng hợp máy đọc được: `STREAM_METRICS_FINAL.json`. Scripts giữ mọi event,
window transcript và word timestamps. Thử đổi commit-delay/time ownership trên
saved outputs không cho cải thiện đủ rõ; không thay chính sách ghép chỉ để ăn theo
vài từ trong benchmark. Cấu hình 8 giây và toàn bộ kết quả kém được giữ lại.

43 server tests pass; 10 Flutter tests pass; Flutter analyze không có issue.
APK profile AOT versionName 1.3.0, versionCode 4 đã cài trên emulator.
Đã kiểm tra native camera, bắt đầu/dừng, về Home khi đang quay và trở lại:
luồng được đóng, camera khởi tạo lại, không giữ ImageProxy cũ.
Các test này không thay thế phép thử người nói/camera/Wi-Fi/thermal trên điện thoại thật.

Luồng Photo Picker → upload → job → kết quả/N-best cũng chạy trên APK 1.3.0:
job hoàn tất 3,679 giây, trong đó decode 0,995 giây; diagnostics xác nhận
incremental decoder và CPU CTC prefix. Câu hiển thị vẫn có lỗi (“một lần và lớp”
thay cho đoạn nói về “môn ngữ văn lớp 10”). Receipt `APP_UPLOAD_JOB.json` và
screenshot `app-result-1.3.0.png` giữ nguyên kết quả thực tế.

APK bàn giao: `output/LipReader-1.3.0-local.apk`, profile AOT, ký debug cho kiểm thử local.
SHA256: `1f11c1be876f7e4d237131ab3652e0565b31306dedd8b9f2038966f3c6a242a0`.
Các checkpoint còn lại cũng đã có hardlink dưới `server/models`; manifest ghi
nguồn/hash. Không sửa bytes của file hardlink. LLM server đã dừng sau benchmark;
VSR server còn chạy local cổng 7100, CUDA ready. Không có deploy/publish/push.

## Đo camera khi nối VSR server cuối

APK 1.3.0 cuối chạy thêm khoảng 30 giây với VSR server thật: 727 frame,
29,944 giây capture, server ghi 24,28 fps, 0 khoảng mất hình trên 0,5 giây;
encode native trung bình 12,23 ms. Log: `device-real-server.log` và `server-final.log`.
Đây vẫn là camera cảnh tổng hợp không có mặt người, nên server từ chối tạo chữ;
phép đo chứng minh vận chuyển camera/receiver, không đo recognition từ người thật.