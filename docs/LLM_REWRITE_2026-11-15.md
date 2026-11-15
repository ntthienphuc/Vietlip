# Thử LLM lớn với video VietLip có sẵn — 15/11/2026

Đã gọi API thật, khôi phục transcript trước LLM và phát lại bốn video qua SO17.
Có cải thiện trên một số câu; chưa đủ ổn định để bật LLM vào phụ đề live mặc định.
Ứng dụng 1.8.0 vẫn đọc môi bằng SO17, chỉ dùng hình ảnh.

## Nguồn và cách so sánh

- Scene 1: bảy câu; scene 2: bốn câu nói nối; scene 4: bốn câu ngắn/dài.
  Cả 15 câu đã được người nói xác nhận trước phép thử này. Scene 3 không nói.
- Transcript, trace và reference được lấy lại có kiểm SHA-256 với manifest backup.
  Riêng reference scene 1 được tái tạo từ lệnh gốc lưu trong lịch sử làm việc;
  byte JSON, kể cả CRLF, khớp hash gốc
  `057ca1e10053ed570eb0fb24bb16cb42b6d022462e54ff7bbe770f9cbd035e06`.
- Ba video còn trên Downloads của điện thoại được lấy lại và khớp hash backup;
  scene 4 được khôi phục trực tiếp từ backup. Chỉ lấy các file cần dùng.
- Mỗi lượt sửa nhận **văn bản cuối của một đoạn tự chốt**. Không gửi video,
  audio, tên scene, câu chuẩn, danh sách đáp án hoặc lịch sử hội thoại.
  Câu chuẩn nằm ở file riêng và chỉ được dùng khi chấm.
- Hai prompt cố định: sửa thận trọng và khôi phục trực tiếp. Temperature 0.
  Không chỉnh prompt sau khi xem câu chuẩn. Hai model cố định:
  `nvidia/nemotron-3-ultra-550b-a55b:free` và
  `baidu/ernie-5.5-flash-preview:free`, qua Kilo Gateway.
- WER dùng đơn vị cách nhau bởi khoảng trắng tiếng Việt; NFC, chữ thường,
  bỏ dấu câu. CER bỏ khoảng trắng, giữ dấu tiếng Việt. WER thấp hơn là tốt hơn.
  Không gán mỗi đoạn tự chốt vào một câu khi endpoint đã gộp hai câu.

Đây là dữ liệu phát triển của cùng một người nói, đã được dùng trong các vòng
trước; không phải tập kiểm định độc lập hay bằng chứng khái quát cho người mới.

## So sánh hoàn chỉnh trên scene 2 và 4

Hai scene có tám câu, 58 đơn vị từ và 192 ký tự tham chiếu. Các lượt Nemotron
trong hai bảng dưới đều trả kết quả hợp lệ; không dùng raw fallback để tạo mức
cải thiện trong bảng. Scene im lặng và đầu vào rỗng được chấm riêng.

| Transcript đưa vào | Cách xử lý | Lỗi từ / 58 | WER | CER |
| --- | --- | ---: | ---: | ---: |
| Gốc từ phiên điện thoại cũ | Giữ nguyên | 30 | 51,72% | 38,02% |
| Cùng transcript gốc | Nemotron thận trọng | 30 | 51,72% | 38,54% |
| Cùng transcript gốc | Nemotron trực tiếp | 28 | 48,28% | 41,15% |
| Đầu ra SO17 phát lại mới | Giữ nguyên | 24 | 41,38% | 33,33% |
| Cùng đầu ra phát lại | Nemotron thận trọng | 20 | **34,48%** | **28,65%** |
| Cùng đầu ra phát lại | Nemotron trực tiếp | 21 | 36,21% | 30,21% |

Trong replay mới, lợi ích chính đến từ scene 2: cách sửa thận trọng giảm từ
13 xuống 9 lỗi từ trên 40 đơn vị; scene 4 vẫn 11/18. Một lỗi “quắc cà phê”
được sửa thành “quán cà phê”. Các câu sai nhưng vẫn đúng ngữ pháp như
“chị chào” hoặc “cảm ơn mà” không được khôi phục thành câu người dùng đã nói.
Có lượt WER giảm trong khi CER tăng; không thể kết luận chỉ bằng độ trôi chảy.

Thời gian HTTP đến đủ câu trả về, chưa gồm chờ endpoint hay thời gian model đọc môi:

| Đầu vào / prompt Nemotron | Trung vị | P95 trong mẫu |
| --- | ---: | ---: |
| Phiên cũ / thận trọng | 0,928 s | 2,197 s |
| Phiên cũ / trực tiếp | 1,003 s | 1,906 s |
| Replay mới / thận trọng | 0,871 s | 1,213 s |
| Replay mới / trực tiếp | 1,177 s | 2,260 s |

Trong bốn đoạn scene 4 có ánh xạ câu rõ ràng ở mỗi bộ này, LLM không khôi phục
thêm câu nào đúng hoàn toàn. Câu vốn đúng ở replay mới được giữ đúng. Scene 2
cũ có ba đoạn cho bốn câu, nên báo cáo điểm toàn phiên thay vì đếm câu bằng
cách ghép vị trí sai.

## Scene dài, lỗi API và phần chưa hoàn thành

Baseline của cả 15 câu cũ: **71/134 lỗi từ, WER 52,99%, CER 39,32%**.
Đợt Nemotron trực tiếp trả thành công 12/17 trường hợp đầu vào, rồi bị 429
`PROMOTION_MODEL_LIMIT_REACHED`. Năm trường hợp còn lại giữ raw. Với chính
chính sách fallback đó, điểm là 64/134, WER 47,76%, CER 38,41%. Đây là kết quả
**LLM khi có kết quả + raw khi API lỗi**, không phải phép thử LLM hoàn chỉnh
trên 15 câu. Trong bảy đoạn scene 1, chỉ ba đoạn đầu có kết quả API; bốn đoạn
cuối chưa được sửa. Vòng thận trọng đầy đủ bị quota nên không có kết quả mới.

Trong các đoạn có ánh xạ câu ở vòng này, ba đoạn giảm lỗi từ, không có đoạn
tăng lỗi từ; một đoạn từ sai thành đúng hoàn toàn. Các đoạn fallback giữ nguyên.
Không dùng con số đó làm tỷ lệ thành công trên người nói hoặc video mới.

Pilot Ernie trên clip bốn câu có 5/7 lượt hợp lệ cho mỗi prompt. Một câu dài
hết ngân sách 700 token vì model bắt buộc reasoning; lượt đầu vào rỗng trả
content null. Khi giữ raw ở lỗi API, cách sửa trực tiếp làm WER từ 66,67% lên
72,22%, CER từ 50% lên 55%. Tăng ngân sách lên 3072 token để thử lại đã gặp
quota ngay lượt đầu, nên chưa có bằng chứng cho cấu hình Ernie đó. Runner hiện
dừng gửi thêm khi gặp 429 và ghi rõ các trường hợp chưa gửi.

Tài liệu [Kilo authentication](https://kilo.ai/docs/gateway/authentication)
cho phép anonymous free models và công bố giới hạn chung 200 yêu cầu/giờ/IP,
nhưng endpoint thực tế áp dụng thêm giới hạn promotion. Không bảo đảm có thể
dùng anonymous làm dịch vụ live. Danh sách model và điều kiện dùng dữ liệu nằm
ở [tài liệu nhà cung cấp](https://kilo.ai/docs/gateway/models-and-providers).
Lượt API thành công ghi cost 0. Không có key Groq/Gemini/OpenRouter trong những
biến môi trường provider chuyên biệt đã kiểm; không gọi các dịch vụ đó.

## Video được phát lại bằng server hiện tại

Bốn replay, tổng 134,56 giây hình ở 25 Hz: 1623 / 579 / 435 / 727 khung hình.
Mọi khung được server ACK. SO17/CUDA/float32, beam 3, CTC 0,1, cùng cấu hình
desktop hiện tại; không audio vào suy luận.

| Scene | Lỗi từ / tham chiếu | WER | Ghi chú |
| --- | ---: | ---: | --- |
| 1 | 44/76 | 57,89% | Bảy câu |
| 2 | 13/40 | 32,50% | Bốn câu |
| 3 | 0/0 | Không xác định | Replay này không sinh chữ |
| 4 | 11/18 | 61,11% | Bốn câu |

Tổng phần có lời: 68/134 lỗi từ, WER 50,75%, CER 36,14%.
Không so chênh lệch giữa phiên gốc và replay để nhận là cải thiện model:
JPEG, lấy mẫu từ MP4 và lịch chạy đã khác. So sánh raw/LLM luôn dùng cùng văn
bản đầu vào trong từng bộ. LLM không xóa được 12 từ sinh sai trong scene 3 cũ;
replay mới không tái hiện lỗi đó nên không chứng minh được một bản sửa silence.

## Quyết định cho app

Giữ SO17 làm luồng live mặc định. Mức giảm lỗi ở một vài clip đáng thử tiếp,
nhưng thời gian cộng thêm thường khoảng một giây, kết quả không đồng đều và
quota anonymous làm gián đoạn. Chưa chứng minh mục tiêu nói xong 2–3 giây có
phụ đề đã được LLM sửa đúng. Chưa đưa lựa chọn model hoặc cài đặt LLM trở lại app.

Runner độc lập `research/llm_rewrite_eval.py` dùng thư viện chuẩn Python, lưu
nguyên request/response, raw, output, model ID, thời gian và lỗi. Reference ở
file riêng; API lỗi hoặc hết token giữ raw. Thử endpoint cục bộ đã xác minh:
NFC, CER/WER im lặng, không gửi reference, circuit khi quota và đếm lượt gửi đúng.

## Bằng chứng cục bộ và chạy lại

Gốc: `artifacts/llm_rewrite_20261115/` (gitignored, gồm video/transcript cá nhân).
`RECOVERY_VERIFIED.json`, `SCENE01_REFERENCE_RECOVERY.json`,
`SUMMARY_VERIFIED.json`, `RUNNER_VERIFIED.json`, `FRESH_PROVENANCE.json`;
`api_original_scenes_v2/`, `api_fresh_v1/`, `api_archived_15sentences/`,
`api_pilot/`, `api_ernie_extended/` và `fresh_scene*/`.
Các vòng pilot lặp được giữ nguyên, không thay thế bằng kết quả đẹp hơn.

```powershell
python research/llm_rewrite_eval.py --inputs INPUTS.json --references REFERENCES.json --turn-references TURN_REFERENCES.json --output NEW_DIRECTORY --models nvidia/nemotron-3-ultra-550b-a55b:free
```

INPUTS chỉ có `id`, `scene`, `raw`. REFERENCES ánh xạ scene tới câu chuẩn;
TURN_REFERENCES tùy chọn chỉ dùng khi có ánh xạ đoạn/câu hợp lệ. Không ghi
đè thư mục đầu ra đã tồn tại. Raw và reference cá nhân không vào Git/bộ cài.
