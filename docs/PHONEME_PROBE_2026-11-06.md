# Thử nhánh âm vị tiếng Việt trên ứng dụng

Đã triển khai, huấn luyện và đo nhánh âm vị mới trong project app. Kết quả từng
đoạn cải thiện nhẹ, nhưng phép thử live liên tục xấu hơn. **Không bật nhánh này
trong cấu hình live mặc định.** Server đã trở về SO_seed17 / beam 3 / CTC 0.1,
LLM tắt. APK 1.4.4 không thay đổi.

## Phần đã làm

- Giữ nguyên visual encoder và nhánh văn bản của SO_seed17. Huấn luyện thêm
  221.010 tham số trên đặc trưng hình ảnh: nhánh CTC âm vị và nhánh CTC có
  thanh điệu (trọng số loss 0,3). Không sửa checkpoint nghiên cứu gốc.
- 36 đơn vị IPA, ký hiệu ngăn âm tiết và blank; nhánh thứ hai thêm sáu thanh.
  Các đơn vị như /tʰ/, /uə/ giữ nguyên. /ɓ/, /m/, /p/ không bị gộp cưỡng ép.
- Phép chuyển chữ sang âm dùng vPhon của James Kirby, broad Northern forms,
  pin commit và SHA256 mã nguồn. Đây là nhãn chuẩn hóa, không phải phiên âm
  được người nghe gán cho từng người nói. Chưa mô hình hóa đầy đủ phương ngữ.
- Video → encoder → nhánh âm vị chỉ nhận hình ảnh. Văn bản tham chiếu dùng
  để huấn luyện/đánh giá. Lúc chọn câu, chỉ phiên âm các ứng viên do mô hình
  tự sinh; không đưa đáp án vào suy luận.
- Có đường thử opt-in trên server, dùng lại cùng encoder, căn thời gian theo
  token của câu đã chọn. Nếu một ứng viên không có phiên âm hỗ trợ, giữ top-1
  gốc. Không dùng LLM viết lại câu.

Mã: `server/experiments/phoneme_probe/`,
`server/app/services/phoneme_rescorer.py`; hook tùy chọn trong
`native_engine.py`. Chi tiết chạy lại trong
[README của thí nghiệm](../server/experiments/phoneme_probe/README.md).

## Dữ liệu và tách tập

Tìm thấy 48.000 video local; 32.768 clip đáp ứng giới hạn độ dài, có nhãn
âm vị hỗ trợ và đủ frame cho CTC. Dữ liệu thử cố định trước khi suy luận:

| Nhóm | Clip | Tiếng theo khoảng trắng | Nguồn |
|---|---:|---:|---:|
| Học nhánh mới | 2.048 | 40.960 | 235 |
| Chọn epoch/trọng số | 128 | 2.560 | 49 |
| Kiểm tra thường | 128 | 2.560 | 52 |
| Kiểm tra tiếng giữ riêng | 128 | 2.560 | 45 |

Không có SHA256 video trùng giữa 2.432 clip. Source ID của tập học không
trùng dev/test; dev không trùng test. Hai nhóm test có thể cùng source.
Source khác nhau **không chứng minh người nói khác nhau**.

12 tiếng bị loại khỏi tập học/dev của nhánh mới: khách, nghi, chứng, vàng,
chung, hoa, nắm, hùng, quy, khí, chân, biển. Encoder SO17 có thể đã gặp
chúng trong huấn luyện cũ. Vì vậy đây chỉ là giữ riêng đối với **nhánh mới**,
không phải kết quả từ chưa từng có trong toàn bộ quá trình pretraining.

Phép thử còn phát hiện 11/12 tiếng có chuỗi âm vị bỏ thanh trùng với tiếng
khác trong tập học; ba tiếng trùng cả biểu diễn có thanh. “Khách” là trường
hợp có chuỗi âm vị mới trong nhóm này, nhưng nhánh chỉ dự đoán đúng nguyên
chuỗi có ranh giới 0/6 lần. Tổng 56/148 lần xuất hiện giữ riêng có chuỗi
âm vị và ranh giới khớp qua căn chỉnh. **Đây không phải độ chính xác từ có dấu.**

9.522 clip local bị loại vì có ít nhất một tiếng không được bộ phiên âm hỗ
trợ (số, tên riêng, từ ngoại ngữ, v.v.). Không âm thầm phiên chữ thành âm.
Số loại theo từng lý do có trong DATASET.json.

## Huấn luyện và kết quả từng đoạn

Trích đặc trưng 2.439 đoạn, gồm 7 đoạn điện thoại để đánh giá, mất 316 giây.
Huấn luyện 25 epoch mất 38,7 giây sau khi đã cache đặc trưng; chọn epoch 11
theo PER trên dev. PER dev: 99,84% lúc khởi tạo → 31,28%.

Trọng số chọn lại câu bằng CTC âm vị lấy từ dev, trong lưới
0 / 0,1 / 0,3 / 0,6 / 1,0. Chọn 1,0; giữ nguyên lựa chọn khi sang test.
Giải mã gốc và mới đều dùng ba ứng viên SO17, beam 3, CTC 0,1.

| Nhóm | WER gốc | WER chọn bằng âm vị | CER gốc → mới | PER nhánh âm vị |
|---|---:|---:|---:|---:|
| Dev (đã dùng chọn) | 31,80% | 30,78% | 25,97% → 24,96% | 31,28% |
| Test thường | 28,55% (731/2.560) | 27,81% (712/2.560) | 23,68% → 22,76% | 25,51% |
| Test giữ riêng | 28,91% (740/2.560) | 27,77% (711/2.560) | 22,27% → 21,01% | 23,62% |
| 7 câu điện thoại, cắt đoạn | 63,16% (48/76) | 61,84% (47/76) | 43,54% → 42,44% | 39,13% trên 3 câu hỗ trợ |

WER dùng đơn vị khoảng trắng; CER bỏ khoảng trắng; PER bỏ ranh giới âm tiết.
Không clip nào trả chuỗi rỗng trong các nhóm này; **không rỗng không có nghĩa
là nhận đúng hoặc đủ tin cậy**. Bốn câu điện thoại chứa camera/Lip Lens/
bluetooth/laser không có phiên âm tham chiếu đầy đủ; vẫn tính WER cả bảy câu.
7 đoạn được cắt với hỗ trợ âm thanh để chẩn đoán, không phải live.

Bootstrap theo source trên test thường cho khoảng 95% của thay đổi WER
[-1,43; 0,00] điểm phần trăm; test giữ riêng [-2,03; -0,30].
Các khoảng này chỉ mô tả tập đã chọn, không đại diện chất lượng triển khai.

Kiểm tra trật tự đặc trưng trên test thường:

| Đầu vào của nhánh | PER |
|---|---:|
| Đặc trưng theo đúng thời gian | 25,51% |
| Xáo thứ tự đặc trưng | 89,83% |
| Lặp đặc trưng trung bình | 100,00% |

Điều này cho thấy nhánh phụ thuộc chuỗi đặc trưng theo thời gian. Đây là
đặc trưng sau encoder đã có ngữ cảnh cả đoạn, chưa phải bằng chứng học
khẩu hình thuần túy độc lập với biểu diễn ngôn ngữ của encoder.

## Kiểm tra live và quyết định

Phát lại clip điện thoại 50,72 giây qua WebSocket thật, 25 fps, JPEG như
client, auto endpoint, cửa sổ 6 giây / cập nhật 1,5 giây:

| Phép thử trong lượt này | Gốc | Nhánh âm vị |
|---|---:|---:|
| WER caption cuối | 63,16% (48/76) | 67,11% (51/76) |
| Frame gửi / frame rơi do transport | 1.268 / 0 | 1.268 / 0 |
| Số câu tự chốt | 7 | 7 |
| Thời gian xử lý cửa sổ trung vị | 919 ms | 936 ms |
| Stop → final | 0,982 giây | 1,005 giây |

Đây là hai lượt phát theo đồng hồ, không phải hai lượt camera vật lý.
Lịch cửa sổ và endpoint có thể khác nhau theo thời gian chạy. Kết quả
baseline lượt này khác phép replay 43/76 trong round03; giữ nguyên cả hai
bằng chứng, không chọn con số thuận lợi hơn. Không kết luận mức suy giảm
này là hằng số của mô hình. Tuy nhiên nó không đạt tiêu chí cải thiện live.

Riêng head trên tensor 150 frame: trung vị 0,396 ms, p95 0,454 ms
(300 lần, 20 warm-up). Đây không gồm encoder, CTC rescoring, beam,
camera/network/UI; không dùng số này làm độ trễ toàn ứng dụng.
Checkpoint mới 888.853 byte. Cả hai phép live vẫn chốt chữ khoảng vài giây
sau khoảng ngừng, nhưng tỷ lệ sai còn cao.

**Quyết định:** giữ baseline đang phục vụ điện thoại; trial tắt mặc định.
Nhánh có khả năng học âm vị và giúp chọn câu trên clip đủ ngữ cảnh, nhưng
chưa giải quyết lời nói tự do, từ ngoại ngữ hay caption ổn định qua cửa sổ.
Hướng thử tiếp theo là huấn luyện/hiệu chỉnh trên các cửa sổ dở câu và
chỉ học phần âm vị có bằng chứng hình ảnh, rồi kiểm tra transcript live.
Chưa có bằng chứng rằng thêm LLM vào đầu ra này sẽ giải quyết các lỗi trên.

## Artefact và kiểm chứng

Tất cả ở `artifacts/phoneme_probe_20261106/`:

- `data_v1/DATASET.json`: tách tập, nguồn, hash, nhãn và lý do loại.
- `features_v1/{IDENTITY,COMPLETE}.json`: danh tính encoder/cache.
- `train_v1/{best.pt,last.pt,TRAINING.json}`: trọng số mới và lịch học.
- `evaluation_v1/{ROWS,EVALUATION}.json`: từng dự đoán, điểm CTC, WER/CER/PER.
- `AUDIT.json`, `RECEIPT.json`: giữ riêng âm vị, đối chứng và timing.
- `LIVE_TRIAL_REPLAY.json`, `LIVE_BASELINE_REPLAY.json`: sự kiện live đầy đủ.
- `DELIVERY.json`: hash source cuối, test và health sau khi khôi phục server.

vPhon: [kho chính thức](https://github.com/kirbyj/vPhon), GPL-3.0-or-later,
mã và license giữ trong dependencies thí nghiệm, không đóng vào APK.
Tham khảo hướng phoneme-first:
[VALLR](https://arxiv.org/abs/2503.21408); không chuyển các số liệu tiếng Anh
của paper thành tuyên bố hiệu quả tiếng Việt.
