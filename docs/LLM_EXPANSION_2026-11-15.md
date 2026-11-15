# Kiểm dữ liệu local và mở rộng phép thử LLM — 15/11/2026

Kết quả trên 32 clip từ 32 nguồn chưa ủng hộ đưa LLM vào luồng live.
Qwen 4B không giảm tổng lỗi. Gateway với prompt thận trọng giảm 3 lỗi trên
639 đơn vị tham chiếu, nhưng thêm trung vị 7,04 giây. Prompt khôi phục mạnh
thay nhiều chữ hơn và làm tổng WER tăng.

Đây là phép thử trên transcript đã lưu. Lượt này không chạy lại video bằng
checkpoint mới, không huấn luyện và không thay mô hình mặc định của app.

## Dữ liệu thực sự tìm được

Đã rà các vùng liên quan trong Downloads/Documents trên C:, Project/Archives/Media
trên E:, loại các thư mục môi trường và build khỏi chỉ mục media/nhãn/model.
Chỉ mục có 34.957 đường dẫn; không phải tất cả đều là dữ liệu đọc môi.

- Bốn video điện thoại đã dùng trước đây và các bản transcript/nhãn khôi phục
  vẫn ở vùng bằng chứng riêng của project.
- Archive local `E:\Archives\From Downloads\VSL and Lip Reading\vsr_benchmark_results.zip`
  có nhãn và dự đoán của ba mô hình trên 7.315 clip, 104 nhóm nguồn.
  SHA-256 trùng chỉ mục backup `Lip_QuanLy/SOURCE_ARCHIVES_INDEX.json`:
  `e5dc17c93819342e7b255b242c79a8e1b6411c671b6fffe7e0c0b6129e4d2d83`.
- 891 clip thuộc benchmark source-dev, 6.424 clip thuộc ViCocktail valid.
  ID clip, ID nguồn và nhãn khớp giữa M1/M2/M3. Nhóm nguồn không có nghĩa
  là đã kiểm chứng danh tính người nói độc lập.
- Các AVI demo trong LipTrace là dữ liệu mô phỏng kỹ thuật; video VSL là
  dữ liệu cử chỉ. Không đưa hai nhóm này vào WER đọc lời nói tiếng Việt.
- Phần lớn corpus video và checkpoint khác đã chuyển sang backup trong đợt
  dọn máy. Lượt khôi phục bốn mẫu metadata qua Drive bị quota 403, không có
  file tải thành công; không coi đó là bằng chứng đã khôi phục corpus.

Nhãn trong archive là nhãn phát triển lịch sử, chưa được nghe/xác nhận lại
và có chỗ lỗi chính tả. Không gọi đây là một bộ test độc lập mới hoặc
độ chính xác hiện tại của SO17 trên camera.

## Kiểm các mô hình thị giác

Tính lại từ toàn bộ dự đoán đã lưu, dùng cùng quy tắc NFC, chữ thường,
bỏ dấu câu; WER theo đơn vị cách trắng, CER bỏ khoảng trắng.

| Mô hình đã lưu | Benchmark source-dev: WER / CER | ViCocktail valid: WER / CER |
|---|---:|---:|
| M1 — Auto-AVSR ViCocktail V0, epoch 13 | 55,12% / 45,53% | 41,87% / 34,11% |
| M2 — Auto-AVSR benchmark_v1, epoch 13 | 25,60% / 20,62% | 94,23% / 81,33% |
| M3 — AV-HuBERT ViCocktail best | 57,26% / 47,18% | 44,31% / 36,63% |

Đây là 21.945 hàng dự đoán của 7.315 clip, không phải 21.945 video độc lập.
M2 tốt hơn trong miền benchmark nhưng kém rất mạnh trên ViCocktail. Bằng chứng
này cho thấy cần chọn mô hình theo miền dữ liệu; chưa đủ để thay SO17 trên điện thoại.

Chẩn đoán N-best cũng được tính lại: chọn đáp án bằng câu chuẩn giảm WER của
M1 xuống 51,16% / 37,83% ở hai miền. Đây là trần chẩn đoán có dùng nhãn,
không phải độ chính xác của một bộ giải mã thực tế hay LLM.

Manifest khóa lịch sử ghi M1/M2 native beam 10 và M3 beam 10.
Các checkpoint này khác SO17 đang phục vụ app. Bản SO17 cài trên máy vẫn có
SHA-256 `cddfb8c79f1db9d66695c0b1b7e2d98837187c600668a8aee3ccdd5b58981ecc`.

## Thiết kế phép thử LLM

Chọn trước 16 nhóm nguồn từ mỗi miền bằng thứ tự SHA-256 có salt cố định,
mỗi nguồn một clip; tổng 32 clip/32 nguồn. Không chọn theo mức lỗi, câu chuẩn
hay kết quả LLM. Lấy cùng 32 clip cho các phép so sánh M1 và M2.

Mỗi request chỉ có prompt cố định và JSON chứa văn bản raw. Không gửi câu chuẩn,
N-best, tên scene, lịch sử hội thoại, video hoặc âm thanh. Không sửa prompt sau
khi xem điểm. Hai prompt là “sửa thận trọng” và “khôi phục trực tiếp”, giữ nguyên
từ lượt thử trước. Nhiệt độ 0. Đây vẫn là mẫu phát triển nhỏ, không phải xác nhận
khả năng khái quát hoặc phép chọn model cuối cùng.

### Những LLM thực sự đã chạy

1. **Qwen3-4B-Instruct-2507, Q4_K_M**: lấy bản GGUF BF16 đã có trên máy,
   lượng tử hóa sang bản mới trong artifacts; không ghi đè file gốc. Kiểm metadata,
   EOS và chat template với tokenizer config chính thức của Qwen.
   [Model card chính thức](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
   Dùng llama.cpp b12034 Vulkan, offload 24 lớp trên GTX 1650 Ti 4 GB,
   context 1.024, một slot, giới hạn sinh 192 token. 96/96 request hợp lệ.
   Định danh từ GGUF và template; hash file gốc đã được ghim, chưa đối chiếu
   trọng số với một bản phát hành chính thức độc lập.
2. **Gateway alias `gpt-6.1-sol`**: gateway đã được cấu hình sẵn trên máy,
   có hạn mức khả dụng, không cần tạo tài khoản/key mới. Tên này được
   `/v1/models` và response trả về; chưa xác minh độc lập model upstream
   hoặc kích thước tham số. Không trình bày như một endpoint công khai miễn phí.
   Giới hạn sinh 256 token, reasoning effort low.

Kilo Nemotron và Ling trả 429 `PROMOTION_MODEL_LIMIT_REACHED` trong lần thử mới.
Tài liệu vẫn cho phép anonymous access với model free, nhưng giới hạn khuyến mại
thực tế đã chặn yêu cầu trên máy này. Không đổi danh tính/IP để vượt hạn mức.
[Tài liệu Kilo](https://kilo.ai/docs/gateway/authentication).

Đã tìm thấy GGUF Qwen3.5-9B Q5_K_M và Qwen 0.6B trong project khác,
nhưng chỉ kiểm metadata, chưa benchmark hai model này. Không tính chúng là
phép thử thành công. Không sửa runtime hoặc model của các project đó.

### Kết quả cùng 32 clip

| LLM / raw / prompt | WER gốc → sửa | CER gốc → sửa | Clip ít lỗi / nhiều lỗi hơn | Thêm trung vị / P95 |
|---|---:|---:|---:|---:|
| Qwen 4B / M1 / thận trọng | 45,85% → 45,85% | 39,11% → 39,26% | 0 / 0 | 2,40 / 4,94 s |
| Qwen 4B / M1 / trực tiếp | 45,85% → 46,32% | 39,11% → 39,89% | 4 / 7 | 2,61 / 5,38 s |
| Qwen 4B / M2 / thận trọng | 59,94% → 60,41% | 50,02% → 50,46% | 0 / 2 | 2,81 / 3,35 s |
| Gateway / M1 / thận trọng | 45,85% → 45,38% | 39,11% → 38,92% | 2 / 0 | 7,04 / 14,00 s |
| Gateway / M1 / trực tiếp | 45,85% → 47,89% | 39,11% → 41,21% | 9 / 13 | 12,31 / 19,33 s |

Mỗi hàng có 32 clip, 639 đơn vị tham chiếu. Các hàng M1 chia sẻ nguyên raw
và nhãn. Không gộp M1/M2 thành một độ chính xác duy nhất.
Prompt gateway thận trọng giảm từ 293 xuống 290 lỗi; prompt trực tiếp tăng
lên 306 lỗi. Số clip đúng hoàn toàn của M1 là 1/32; sau gateway trực tiếp
thành 2/32, các cách sửa M1 còn lại giữ 1/32. Chỉ có một clip raw đúng nên
chưa thể kết luận LLM ít phá câu đúng nói chung.

Thời gian là HTTP vòng khứ hồi từng lượt hoàn tất, gồm chờ/generation;
không phải time-to-first-token. Chưa cộng nhận diện thị giác, cắt câu, Wi-Fi
và vẽ phụ đề, nên không đạt mục tiêu nói xong 2–3 giây chỉ từ các con số này.
SO17 được tạm dừng trong lúc đo Qwen để đủ tài nguyên, rồi khởi động lại;
chưa đo hai mô hình cùng tranh GPU khi live. Đây không phải cam kết độ trễ sản phẩm.

## Điện thoại đã xác nhận

Giữ nguyên transcript SO17 gốc của scene 1, 2, 4: 15 câu, 134 đơn vị tham chiếu,
đã được người nói xác nhận. Chấm theo toàn phiên, không ép ba lượt server đã
gộp ở scene 2 vào bốn câu tham chiếu. Scene 3 không nói và đầu vào rỗng được
chấm riêng, không pha vào mẫu số WER của lời nói.

| Prompt gateway | WER gốc → sửa | CER gốc → sửa | Trung vị lượt có text / P95 mọi lượt |
|---|---:|---:|---:|
| Thận trọng | 52,99% → 48,51% | 39,32% → 36,36% | 7,03 / 12,55 s |
| Trực tiếp | 52,99% → 26,87% | 39,32% → 23,64% | 9,23 / 17,48 s |

Số lỗi từ giảm 71 → 65 và 71 → 36. Trong 11 lượt đã căn chỉnh được một-một
với câu chuẩn, prompt trực tiếp giúp 6 lượt, làm xấu 0 lượt; số lượt hoàn toàn
đúng tăng từ 0 lên 3. Đây không phải 3/15 câu, vì các câu bị server gộp ở
scene 2 không tham gia phép đếm một-một.

LLM vẫn giữ 12 đơn vị chữ sinh sai trong video im lặng. Nó không giải quyết
được việc phát hiện có nói hay không. Cả hai yêu cầu đầu vào rỗng trả HTTP 200
nhưng content=null; theo giao thức đã khóa, đánh dấu không hợp lệ và giữ raw
rỗng. Không đổi tiêu chuẩn hợp lệ sau khi nhìn kết quả.

Tổng lượt này có 194 request hoàn tất, 192 phản hồi text hợp lệ:
96 local Qwen, 64 gateway corpus, 32/34 gateway điện thoại. Không có lỗi
HTTP trong ba nhóm này; hai phản hồi null kể trên được tính là fallback.
Các probe Kilo bị quota và probe kết nối riêng không nằm trong mẫu số này.

Sửa trực tiếp có lợi cho một số câu sinh hoạt quen thuộc của người dùng,
nhưng không ổn định trên corpus rộng hơn. Không suy rộng rằng model đã khôi
phục thông tin thị giác bị mất hoặc đọc được từ mới bất kỳ. Kết quả hiện tại
hợp với phép thử sửa sau phiên; chưa hợp với phụ đề live 2–3 giây.

## Bằng chứng và bảo trì

Bằng chứng riêng ở `artifacts/llm_expansion_20261115/`, không nằm trong Git:
`DATA_VERIFIED.json`, `FULL_BASELINE.json`, `SELECTION.json`,
`WEIGHT_HASHES.json`, request/response gốc theo run, `SUMMARY.json`,
`Doi_chieu_LLM.html` và CSV. Báo cáo HTML chạy offline, có bộ lọc và đánh dấu
từng từ bị bỏ/thêm. Transcript và nhãn riêng không đưa vào mã nguồn hoặc bộ cài.

`research/llm_rewrite_eval.py` nhận endpoint tùy chọn, key qua tên biến môi trường
và reasoning effort; không ghi Authorization vào báo cáo. Khi quota 429, ngừng
gửi thêm, giữ raw và tách request chưa gửi khỏi request lỗi.
Hai test kiểm Unicode/đối chứng im lặng và HTTP giả lập kiểm cô lập câu chuẩn,
auth không bị ghi log, quota/fallback. Runtime app/server không import tool này.

Kiểm chứng cuối: hai test pass, Ruff check/format pass, diff không lỗi whitespace.
Kiểm request thực tế xác nhận cùng raw M1 giữa Qwen/gateway và giữa hai prompt;
request chỉ chứa prompt cố định và raw. Báo cáo HTML hiển thị 170 thẻ
(160 thẻ đối chiếu corpus, 10 thẻ phiên điện thoại); bộ lọc điện thoại/trực tiếp/ít lỗi
trả đúng hai phiên, tìm chuỗi không có trả 0 và reset trả 170.
Server SO17 đã khởi động lại, healthz báo ready/CUDA/realtime_available;
không để server LLM thử nghiệm ở cổng 7115 hoạt động.

Giữ luồng mặc định SO17 thuần hình ảnh. Các kết quả hiện có chưa biện minh cho
việc tăng độ trễ live bằng LLM. Nếu thử tiếp, dùng bảng này làm mốc và yêu cầu
giảm lỗi trên cùng input trước khi thay đổi ứng dụng.
