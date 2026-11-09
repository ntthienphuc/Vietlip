# Nhánh âm vị học trên cửa sổ dở câu

Đã huấn luyện tiếp nhánh âm vị trong project ứng dụng. Kết quả hiện tại:
**giảm lỗi rất nhẹ trên cửa sổ kiểm thử, chưa giảm WER của phụ đề hoàn chỉnh
trên ba video phát lại**. Nhánh mới giữ dưới dạng tùy chọn thử nghiệm; SO17
vẫn là cấu hình live mặc định.

## Huấn luyện thực tế

Tailscale tới WORKSTATION-TT (100.97.93.24) và SSH tài khoản PC đã hoạt động.
Chạy trên RTX 3060 12 GB, trong thư mục riêng
`D:/Lip_App_Window_20261107/run_v1/`. Gói kết quả đã tải về app và đối chiếu
SHA256; job kết thúc với exit code 0. Checkpoint SO17 gốc chỉ được đọc.

- Khởi tạo từ nhánh âm vị v1, giữ visual encoder SO17 cố định.
- 8.209 cửa sổ train, 503 dev, 534 test thường, 540 test giữ riêng tiếng.
  Chỉ train tham gia cập nhật trọng số; dev chọn epoch.
- Cửa sổ tiền tố và trượt, tối đa 150 frame / 6 giây, lưới 25 fps.
  Cắt cửa sổ trước khi chạy encoder để không nhìn thấy hình ảnh tương lai.
- Tính CTC loss trên phần chứa trọn từ có mốc thời gian. Không gán cả âm tiết
  cho mảnh khẩu hình bị cắt ở đầu/cuối cửa sổ. Đây là nhãn theo mốc từ,
  chưa phải căn chỉnh âm vị chính xác.
- Hai đầu ra IPA không thanh / có thanh; loss có thanh có trọng số 0,3.
  Huấn luyện 20 epoch, LR 0,0005 với cosine decay.
- Trích 9.786 cửa sổ mất 712,6 giây; train 20 epoch mất 317,7 giây,
  chưa gồm tải đặc trưng vào bộ nhớ và chuyển gói kết quả.
- Chọn **epoch 4** bằng PER dev: **33,59% → 33,14%**.
  Epoch cuối tăng lên 34,60%; không lấy epoch cuối chỉ vì đã train lâu hơn.

Checkpoint: `artifacts/phoneme_window_20261107/remote_result/training/best.pt`.
Mã và cách chạy: [phoneme_probe/README.md](../server/experiments/phoneme_probe/README.md).

## So sánh trên cùng cửa sổ

Chọn trước một cửa sổ mỗi clip kiểm thử bằng hash, ưu tiên cửa sổ có mép phải
dở tiếng. Tổng 383 cửa sổ: 127 dev, 128 test, 128 test giữ riêng tiếng.
Một clip dev không còn cửa sổ phù hợp. Hai nhánh dùng cùng tensor hình ảnh,
đặc trưng SO17 và ba ứng viên văn bản. Cả hai trọng số chọn câu đều là **0,1**,
chọn riêng bằng WER dev trên lưới 0 / 0,1 / 0,3 / 0,6 / 1.

WER/CER dưới đây chỉ tính phần từ nằm trọn trong cửa sổ. Mốc tham chiếu chỉ
dùng chấm điểm, không được đưa cho decoder.

| Nhóm | SO17 | Âm vị v1 | Âm vị cửa sổ |
|---|---:|---:|---:|
| Test thường, WER | 29,38% (444/1.511) | 29,05% (439/1.511) | 29,19% (441/1.511) |
| Test thường, CER | 23,83% | 23,60% | 23,68% |
| Test giữ riêng, WER | 28,05% (437/1.558) | 27,66% (431/1.558) | 27,60% (430/1.558) |
| Test giữ riêng, CER | 20,97% | 20,39% | 20,39% |

Nhánh mới giảm 10 lỗi / 3.069 đơn vị so với SO17 trên hai nhóm test cộng lại,
nhưng nhiều hơn v1 một lỗi. Kết quả này chưa cho thấy lợi ích nhất quán so với
nhánh cũ. 12 tiếng giữ riêng chỉ vắng trong train của **nhánh âm vị mới**;
encoder SO17 có thể đã gặp chúng. Chưa chứng minh đọc được từ chưa xuất hiện
trong toàn bộ quá trình huấn luyện.

## Phụ đề hoàn chỉnh trên video

Hai video điện thoại khoảng 51 và 36 giây, cùng video ROI ghép dài 239 giây.
Tổng 146 cửa sổ, 719 đơn vị tham chiếu. Giữ nguyên từng mốc bắt đầu/kết thúc
cửa sổ và dùng `AgreementTimeline` của app để nối phụ đề.

| Video | SO17: lỗi / đơn vị | v1, trọng số 0,1 | Nhánh mới, trọng số 0,1 |
|---|---:|---:|---:|
| Điện thoại round03 | 48/76 | 50/76 | 48/76 |
| Điện thoại round02 | 25/44 | 25/44 | 25/44 |
| ROI ghép gần 4 phút | 400/599 | 402/599 | 400/599 |

Tổng WER của nhánh mới bằng SO17: 473/719 = 65,79%. CER giảm từ
1.275/2.387 = 53,41% xuống 1.270/2.387 = 53,20%. Nhánh mới sửa một số cách
đoán và làm sai một số cách đoán khác; tổng số lỗi từ không giảm.
Không có cửa sổ trả đầu ra rỗng trong phép thử này. Điều đó không có nghĩa
là tất cả cửa sổ nhận dạng đúng hoặc đủ tin cậy.

Với trọng số 1, nhánh mới cho 48/76, 25/44 và 398/599. Đây là kiểm tra thêm,
không phải trọng số được chọn bởi dev; không chọn nó dựa trên các video test.

Các kết quả này thuộc lịch cửa sổ cố định. Lượt chạy endpoint tự động mới
có thể tạo lịch khác, nên không trộn số liệu của hai cách chạy để kết luận
nhánh nào tốt hơn.

## Đường live và độ trễ

`fixed_ws_replay` truyền JPEG 25 fps qua WebSocket loopback, giải mã lại bằng
pipeline của app và kiểm tra hash tensor chuẩn bị cùng chuỗi top-3 với cache.
Mỗi nhánh dùng chung một lượt encoder; đo riêng chi phí chọn bằng âm vị.
Thời điểm bắt đầu giải mã lấy từ bản ghi cũ, bao gồm phần chờ chốt câu.
Kết quả đầy đủ và thời gian từng cửa sổ nằm trong
`artifacts/phoneme_window_20261107/ws_paired/RESULTS.json`.

Cả 8.145 frame đều được nhận và ACK. Tất cả 146 tensor cửa sổ và top-3
được kiểm tra; phụ đề cuối của 3 nhánh × 3 video khớp đúng bộ chấm offline.

| Video | Trung vị từ cuối cửa sổ đến kết quả | P95 | Chi phí thêm của nhánh mới, trung vị |
|---|---:|---:|---:|
| Điện thoại round03 | 1,05 giây | 1,93 giây | 1,62 ms |
| Điện thoại round02 | 0,92 giây | 1,77 giây | 1,64 ms |
| ROI ghép | 0,49 giây | 1,47 giây | 1,57 ms |

Độ trễ này gồm phần chờ chốt đã cố định và phép so sánh cả hai đầu ra,
không phải ba lượt encoder riêng biệt. Hàng đợi không tăng dần trong clip dài.

Đây là endpoint kiểm thử trong cùng tiến trình. Nó không đo lại camera vật lý,
render Flutter, Wi-Fi hoặc suy luận qua Tailscale. Tailscale đã được dùng
thực tế cho huấn luyện và chuyển kết quả.

Ngoài phép so sánh cố định, API `/v1/realtime` thật đã được kiểm tra với
SO17 và tự endpoint trên clip round03:

- 1.268 frame gửi, 0 frame bị bỏ khi truyền; capture fps trung vị 25.
- 27 cửa sổ; thời gian decode trung vị 872 ms.
- Độ trễ ở các lần chốt câu so với mốc cuối cửa sổ trung vị 1,72 giây.
- Sau khi video kết thúc, chốt phiên mất 0,95 giây.
- 45 lỗi / 76 đơn vị; lịch cửa sổ khác phép so sánh cố định ở trên.

Lượt kiểm tra API thật với nhánh mới cũng hoàn tất: 1.268 frame, không bỏ
frame khi truyền, 25 fps, 25 cửa sổ; decode trung vị 866 ms; chốt phiên sau
video 0,96 giây. Log xác nhận đúng SHA256 checkpoint mới trên mọi cửa sổ;
19 cửa sổ áp dụng rescoring, một cửa sổ đổi ứng viên. Kết quả 46/76 lỗi.
Hai lượt endpoint tự động có lịch khác nhau nên đây là kiểm tra tích hợp,
không thay thế phép so sánh cố định. Chi tiết: `PRODUCTION_INTEGRATION.json`.

Độ trễ theo mốc cửa sổ chưa phải phép đo chính xác từ lúc người thật ngừng
nói đến lúc chữ được vẽ trên màn hình điện thoại.

## Quyết định cho ứng dụng

Chưa bật nhánh âm vị cửa sổ mặc định. Chi phí thêm cần được đánh giá cùng
lợi ích phụ đề; hiện lợi ích WER live so với SO17 bằng không.
Đã mở rộng launcher thử để nhận checkpoint và trọng số rõ ràng:

```powershell
.\server\run_phoneme_trial.ps1 `
  -HeadPath E:\Project\Lip_App\lip_reader\artifacts\phoneme_window_20261107\remote_result\training\best.pt `
  -Weight 0.1 -Port 7101
```

Log live của app nay kèm trạng thái áp dụng nhánh âm vị, trọng số, lý do
fallback và SHA256 checkpoint để tránh nhầm cấu hình khi đối chiếu lần chạy.

Nhánh này hiện chọn lại giữa ba câu do SO17 sinh ra. Nó chưa tạo câu trực tiếp
từ chuỗi âm vị. Nếu từ đúng không có trong ba ứng viên, bước chọn lại không
thể tạo ra từ đó. Các trường hợp phiên âm không hỗ trợ vẫn giữ câu gốc.

Để cải thiện ứng dụng tiếp, cần kiểm tra khả năng giải mã từ chuỗi âm vị hoặc
cải thiện biểu diễn hình ảnh trên video camera; tiếp tục tăng epoch cho đầu
ra nhỏ hiện tại đã có dấu hiệu giảm chất lượng dev.

## Kiểm chứng và dữ liệu bàn giao

- 89 kiểm tra server qua, gồm loại trừ loss ở từ bị cắt và căn thời gian theo
  đúng ứng viên được chọn. Một cảnh báo deprecation từ thư viện Starlette.
- Gói kết quả remote SHA256:
  `2110ca9f8dfaa537e39fe98c04deb667cf32dd7cfa6776a86b8c1aa45187e8a6`.
- Đặc trưng từ hai GPU không trùng bit: chênh lệch tuyệt đối lớn nhất 0,001706,
  relative RMS lớn nhất 0,00002544. Kiểm tra ban đầu với ngưỡng tuyệt đối 0,001
  đã không qua; kiểm tra tiếp đủ 383 cửa sổ cho thấy **0 thay đổi ứng viên
  được chọn** ở cả hai nhánh. Phép so sánh chính dùng cùng một cache local
  cho cả hai nhánh, không dùng hai cache khác GPU để so kết quả.
- Dữ liệu và kết quả: `artifacts/phoneme_window_20261107/`:
  `WORKER_RESULT.json`, `remote_result/training/TRAINING.json`,
  `evaluation_v2/RESULTS.json`, `CROSS_GPU.json`, `ws_paired/RESULTS.json`.
  `AUDIT.json` xác nhận provenance và phụ đề của mọi nhánh khớp giữa hai
  đường kiểm tra. Checkpoint mới SHA256:
  `f9435fd632c66d3af74433d1f87134278c39fa0ecf86a7fd95b6c959ab9ee20d`.

Đây là tối ưu và kiểm thử ứng dụng bằng dữ liệu hiện có. Độ chính xác hiện tại
chưa đủ để coi là đọc khẩu hình tự do đáng tin cậy.
