# Kiểm thử thiết bị thật

Ngày kiểm thử: 2026-07-24.

Thiết bị: Samsung SM-G965F, Android 10 (API 29), ARM64. Bản
`app-debug.apk` được cài qua ADB và chạy bằng camera trước.

## Đã đạt

- app khởi động, xin quyền camera và không có fatal exception trong logcat;
- camera trước preview, đổi trạng thái quay/dừng và tạo MP4 thật;
- sau khi dừng, màn hình tự cuộn tới ba chế độ xử lý;
- validation chế độ LLM bắt buộc context và consent;
- kết nối `/healthz` từ điện thoại tới FastAPI qua ADB reverse;
- health UI hiển thị đúng model `ready`, thiết bị `cpu (float32)` và cảnh báo
  cold start;
- chọn `BAITH53_3.mp4` trong Android file picker, upload qua app tới model thật
  và nhận result screen sau 5.029 giây;
- bản chính trên UI là `em khen thân mến trong bài học ngày hôm nay cô san sẽ
  hướng dẫn chúng ta tìm hiểu văn`; hai N-best khác được tách riêng;
- lịch sử lưu đúng transcript, thời gian và `119 khung hình`;
- Ollama `qwen2.5:7b` chạy thật ở cả `context_select` và `llm_assist`; result
  screen hiển thị provider, model, thời gian và lý do cạnh bản hỗ trợ;
- khi cố ý ngắt endpoint LLM, server vẫn trả visual transcript và trạng thái
  `error`, không làm hỏng kết quả chính;
- APK ARM64 build thành công; Flutter analyze/test và API contract test đạt.

## Benchmark CPU của sample

Video 320×320, 29 fps, 138 frame/4,76 giây. Sau khi resample còn 119 frame.
CSV có 20 từ.

- CLI cold start: 13,534 giây; load 6,013 s, preprocessing 2,158 s, decode
  3,080 s.
- HTTP cold: 13,984 giây.
- HTTP warm: 5,122 giây.
- App → HTTP warm: 5,029 giây.
- CPU float32, 11 logical threads; transcript 20/20, WER 0,0% trên sample này.
- Face detection ratio 100%, blur score 65,74, không có quality warning.

## Vòng polish cuối

Server được khởi động bằng đúng `server/run_server.ps1`, preload model thành
công và `/healthz` báo `ready`, `cpu (float32)`. Hai request HTTP liên tiếp mất
6,134 và 5,000 giây; cả hai đều khớp 20/20 từ trong CSV (WER 0,0%). Flow Android
được chạy lại từ kết nối server → chọn file → gửi visual-only → xem kết quả →
xem lịch sử; result screen báo 4,66 giây và không có crash, ANR hay exception
Flutter trong logcat.

Kiểm tra chốt: 10 API test đạt, 5 Flutter test đạt, `flutter analyze` sạch và
debug APK build thành công. Debug/profile cho phép HTTP để test LAN/ADB; manifest
release giữ `usesCleartextTraffic=false`.

## Full flow LLM local

Cấu hình: Ollama 0.32.1, `qwen2.5:7b` Q4_K_M, context 2.048 token,
`keep_alive=0`; máy có GTX 1650 Ti 4 GB và chạy model hybrid CPU/GPU. `/healthz`
xác minh model Ollama thật trước khi báo `llm_available=true`.

- API `visual_only`: 7,119 giây, WER 0,0%.
- API `context_select`: 23,048 giây tổng; LLM 18,760 giây, chọn index 0 nguyên
  văn từ N-best.
- API `llm_assist`: 31,468 giây tổng; LLM 25,758 giây, thêm viết hoa/dấu câu
  nhưng không thay `transcript` visual.
- API fallback với endpoint LLM không tồn tại: HTTP 200 sau 7,550 giây,
  `assisted_transcript=null`, visual WER 0,0%.
- Thiếu consent hoặc thiếu context đều bị chặn HTTP 422 trước inference.
- Trên Samsung: visual-only báo 4,79 giây; context-select hiển thị LLM 19,90
  giây; llm-assist hiển thị LLM 24,79 giây và trả câu “Em khen thân mến trong
  bài học ngày hôm nay, cô San sẽ hướng dẫn chúng ta tìm hiểu văn.”
- Settings báo `ready · cpu (float32) · LLM: qwen2.5:7b`; cả ba lượt được lưu
  vào local history.

Đây là một sample có vẻ cùng phân phối train/benchmark, không đại diện cho
generalization camera thật. Báo cáo experiment hiện có vẫn ghi test WER khoảng
40,07%; vì vậy app tiếp tục trả `review_required`.

## Chưa thể xác nhận

Chưa benchmark Auto-AVSR CUDA vì venv hiện dùng PyTorch CPU. Chưa có p50/p95 LLM
trên nhiều clip/ngữ cảnh, và chưa integration-test provider cloud; production
vẫn cần dữ liệu ngoài phân phối train để đo hallucination và mức LLM sửa sai/
sửa đúng.

## Test tiếp theo

1. Chạy clip 2, 5, 12 và 30 giây; ghi p50/p95, peak RAM/VRAM và crop failure.
2. Test nhiều ánh sáng/góc/máy/người, không chỉ một clip và một thiết bị.
3. Benchmark CUDA so với CPU trên cùng parity suite.
4. Chạy A/B Qwen local với một provider cloud opt-in trên tập consented; đo WER
   của visual riêng và semantic/hallucination rate của assisted output riêng.
