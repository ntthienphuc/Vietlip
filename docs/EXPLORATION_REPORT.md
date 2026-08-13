# Báo cáo khảo sát hai workspace

## `Lip_App/Lip_Final`

Bundle có 7 nhóm chính: báo cáo cuối, code/experiment, reproducibility,
evidence, execution records, checkpoint và integrity. Pha code lớn gồm:

- benchmark signer-independent: 92.396 train / 11.573 valid / 11.304 test;
- input canonical: mouth ROI grayscale 96x96, 25 fps, tối đa 750 frame;
- Auto-AVSR, AV-HuBERT, SwinLip adaptation và nhiều nhánh structured/bridge;
- app-facing E0–E6, C-DAG V1–V4 và EV-B-C-DAG;
- test, scripts, config, raw prediction summaries và provenance.

Kết luận có tác động trực tiếp đến sản phẩm:

- Auto-AVSR test WER 40,0704%, là transcript owner;
- AV-HuBERT 40,4050%, chỉ phù hợp verifier/diagnostic;
- E0–E6 không policy nào qua đủ deployment gate;
- EV-B-C-DAG tốt nhất trong selective routing nhưng one-shot chỉ đạt coverage
  85,2088% so với floor 85,8535%, thiếu 73 clip;
- sản phẩm phù hợp draft/triage/human review, chưa phù hợp final subtitle.

Hai checkpoint có thật trong upload:

| File thực tế | Bytes | SHA-256 | Vai trò |
|---|---:|---|---|
| `epoch=13-loss_val=53.8436-003.ckpt` | 2.921.264.106 | `57a6e8…79816` | benchmark Auto-AVSR |
| `checkpoint_avg_top3-004.pt` | 5.741.209.834 | `d89250…28b95` | benchmark AV-HuBERT |

Hash của cả hai khớp manifest. Tuy nhiên manifest/README mô tả 4 checkpoint
16,135 GiB và path lồng theo dataset, trong khi folder thực tế chỉ có 2 file
phẳng khoảng 8,07 GiB với hậu tố `-003/-004`. Hai checkpoint ViCocktail không
có trong upload hiện tại. Đây là lệch packaging cần sửa trước khi bàn giao.

Một lệch tài liệu khác: README đầu bundle còn nhắc `02_EVIDENCE` và
`04_V1_PROJECT_SNAPSHOT`, trong khi cấu trúc thực là `04_EVIDENCE` và code nằm
trong `02_PROJECT_MAIN`.

## `vsl-translator`

Đây là repo Flutter đa nền tảng + FastAPI:

- app dùng GoRouter, Material 3, camera, settings, dictionary, history/profile;
- realtime dùng WebSocket gửi keypoint, server Redis-buffer và segment cử chỉ;
- one-shot dùng multipart video; Android có offline TFLite/MediaPipe fallback;
- server có ONNX engines, health/status, dictionary static serving và test;
- packaging có Windows installer và output release.

Các pattern được tái sử dụng cho Lip Reader:

- tách Flutter client và Python server;
- cấu hình URL server lưu local;
- health check rõ ràng;
- upload one-shot là luồng chính;
- model lazy-load, inference lock, temp cleanup;
- UI camera có trạng thái loading/error và local fallback path là gallery.

Các pattern không sao chép:

- keypoint WebSocket/Redis segmentation phụ thuộc bản chất sign language;
- offline TFLite vì Auto-AVSR checkpoint khoảng 2,9 GB chưa phù hợp mobile;
- dictionary/gesture classification không liên quan VSR.

Repo VSL đang có nhiều file modified/untracked trên branch `big_update`; quá
trình này chỉ đọc nó làm tham chiếu và không sửa file nào trong repo đó.
