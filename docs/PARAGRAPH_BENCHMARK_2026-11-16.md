# VietLip — tám phiên đọc đoạn văn, 16/11/2026

Giữ cấu hình phát hành **1.10.1** sau vòng này. Các biến thể chưa cho thấy
cải thiện đủ ổn định để thay mặc định. Đã thu và xuất đủ tám video có tiếng,
kiểm SHA-256 giữa điện thoại và PC; tổng thời lượng 206,53 giây. Đây là bốn
đoạn khác nội dung, mỗi đoạn đọc hai lần bởi cùng một người, không phải tám
nội dung hoặc tám người nói độc lập.

## Tham chiếu và phép đo phiên thật

Người dùng xác nhận có vấp, lặp hoặc đổi vài từ. Vì vậy kịch bản không phải
tham chiếu nguyên văn của mọi video. Faster-Whisper medium chạy cục bộ trên
CPU/int8, không có prompt kịch bản, tạo candidate âm thanh. Giữ nguyên các
candidate và những chỗ bất đồng; chưa coi chúng là bản chép đã được kiểm nghe
từng từ. WER/CER dưới đây là **ước lượng theo ASR**, không phải độ chính xác
triển khai đã xác minh bằng nhãn con người.

| Đầu ra thực tế trong tám phiên | Lỗi token / tham chiếu ASR | WER ước lượng | CER ước lượng |
| --- | ---: | ---: | ---: |
| Đọc môi gốc | 213/368 | 57,88% | 44,36% |
| Groq GPT-OSS 120B đã trả trong live | 226/368 | 61,41% | 49,63% |

Theo kịch bản ban đầu, kết quả tương ứng là 217/370 (58,65%) và 229/370
(61,89%). Chỉ dùng bảng phụ này kiểm độ nhạy; không gán lỗi do người dùng
đọc khác kịch bản thành lỗi mô hình đã được xác minh.

Cả tám phiên kết thúc đầy đủ, không có cửa sổ thị giác unavailable trong trace
gốc, trung vị capture 25,04 fps. Có mười đoạn chốt và mười phản hồi Groq thành
công; model chốt theo khoảng ngừng, không theo dấu câu của kịch bản. Trung vị
riêng AI là 1.140,5 ms, tối đa 1.484 ms. Từ mốc cuối cửa sổ hình có padding tới
Flutter render receipt: trung vị 2.445,5 ms, tối đa 2.720 ms. Đây không phải
thời gian từ âm cuối đến chữ hiện trên màn hình; offset audio/camera chưa được
hiệu chuẩn để báo chỉ số đó.

Audio chỉ dùng audit và chấm; LLM chỉ nhận đầu ra mô hình. Không gửi câu chuẩn
hoặc âm thanh cho VSR/LLM. Chưa xác minh các câu có nằm ngoài train set hay không.

## Đối chiếu các hướng cải thiện

A/B dùng chọn phương án phát triển; C/D ban đầu giữ để kiểm cấu hình đã chọn.
Sau khi đã mở điểm C/D cho cửa sổ tám giây, các kiểm tra tiếp theo trên C/D
được ghi là **validation tái sử dụng**, không gọi là test độc lập mới.

Các phép so hình dùng cùng MP4, resample 25 Hz và JPEG quality80 cố định.
Pixel/cửa sổ hoặc tick quyết định được giữ theo từng protocol. Không so trực
tiếp replay với phiên camera để nhận chênh lệch là cải thiện: MP4 không tái dựng
đúng byte JPEG và clock gốc của camera. Baseline ở mỗi bảng là baseline của
chính protocol replay đó. Dự đoán được lưu trước khi scorer mở tham chiếu.

| Hướng thử | Bằng chứng chính | Quyết định |
| --- | --- | --- |
| Bề ngang 480 thay 360 | Chỉ giảm một lỗi token tổng trên A/B theo script, A2 tăng ba lỗi; endpoint chậm hơn | Giữ 360 |
| Cửa sổ 8 giây | A/B giảm 110 xuống 100 lỗi; C/D có D2 tăng năm lỗi, tổng chỉ giảm hai | Không đổi mặc định |
| Cửa sổ 10 giây | A/B top1 vẫn 110 lỗi; xử lý chậm hơn | Loại |
| Chọn medoid giữa ba rank stream | Chỉ giảm hai lỗi trên A/B, dưới ngưỡng ba lỗi đã đặt | Loại |
| LLM nhận ba rank stream | 104 lỗi A/B so với 100 ở source context8 tương ứng; năm lượt API thành công | Loại |
| Qwen3.8-27B qua Groq | Hai lượt trả được, rồi chạm quota; các lượt sau giữ raw; chưa có lợi ích đáng kể ở phần hoàn tất | Giữ pilot dang dở, chưa chọn |
| Giải mã lại toàn bộ turn dài | 148/180 lỗi theo script; xuất hiện chuỗi số lặp, endpoint mất khoảng 3–8,5 giây | Loại |
| Chốt sau 0,6 giây thay 1 giây | Giúp A/B nhưng C/D tái sử dụng tăng một lỗi; video cũ và im lặng không tăng lỗi | Giữ ứng viên thử nghiệm, chưa làm mặc định |

Rank streams là các chuỗi ghép từ rank 1/2/3 theo từng cửa sổ; không gọi chúng
là ba giả thuyết toàn câu có xác suất đã hiệu chuẩn. API khôi phục không nhận
đáp án hoặc chủ đề đoạn văn. Baseline/context8 chạy lại ở lượt đo không có
ASR song song cho cùng văn bản ở cả bốn clip, giúp kiểm tính lặp lại. Khi tách
ASR ra, endpoint model+alignment tối đa đo được là 1.025 ms cho baseline và
1.440 ms cho context8; không dùng runtime này làm độ trễ âm học tới màn hình.

Qwen3.8-27B có trong catalog tài khoản và bảng free tier tại thời điểm kiểm.
Giới hạn phụ thuộc tài khoản/dịch vụ; pilot 429 không được tự chuyển sang route
trả phí. [Bảng giới hạn chính thức Groq](https://console.groq.com/docs/rate-limits).

## Kiểm tra riêng ngắt đoạn nhanh

Các ngưỡng 1,0 / 0,8 / 0,6 giây dùng cùng chuỗi quan sát chuyển động môi, không
dùng audio để cắt câu. Giữ window6, beam3, CTC0.1 và AgreementTimeline. Biến
thể sửa lại phần đầu turn ngắn không có thêm lợi ích nên không đưa thêm cơ chế
đổi chữ vào app.

| Nhóm đối chiếu, tham chiếu ASR | Pause 1,0 giây | Pause 0,6 giây |
| --- | ---: | ---: |
| A/B, 179 token | 108 lỗi | 99 lỗi |
| C/D tái sử dụng, 189 token | 97 lỗi | 98 lỗi |
| Bốn video mười câu cũ, 401 token | 188 lỗi | 188 lỗi |
| Video im lặng | 0 chữ sinh thêm | 0 chữ sinh thêm |

Ngắt nhanh giúp tách ba câu ở một số clip và giảm thời gian chờ ngừng khoảng
0,4 giây theo chính sách. Tuy nhiên, chưa có xác minh live cho cấu hình này,
và điểm trên C/D không cải thiện. Giữ cấu hình đã phát hành để ưu tiên độ ổn
định; các số trên không chứng minh model đọc môi mới chính xác hơn nói chung.

## Bằng chứng và trạng thái bàn giao

Tất cả tài liệu cục bộ nằm trong
`artifacts/paragraph_benchmark_20261116`, không đưa video, khuôn mặt, âm thanh,
transcript chi tiết hoặc khóa API vào Git/bộ cài:

- `SESSION_INDEX.json`, `EXPORT_INDEX.json`: thứ tự tám phiên và hash MP4.
- `samples/A1` … `samples/D2`: MP4 gốc, visual/AI trace, acoustic candidate.
- `REFERENCE_STATUS.json`: xác nhận đọc khác script và quy tắc báo cáo.
- `LIVE_BASELINE_SCORES.json`, `LIVE_AGGREGATE.json`: số đo phiên thật.
- `replay_dev_v1`, `replay_validation_v1`, `timing_isolated_v1`: replay hình,
  dự đoán, hash đầu vào và chấm điểm.
- `nbest_llm_dev`, `qwen_direct_dev`, `fullturn_dev_v1`: các nhánh đã thử,
  giữ cả lỗi API và kết quả không cải thiện.
- `endpoint_replay_dev_v1`, `endpoint_validation`, `endpoint_old`,
  `endpoint_silence`: kiểm tra ngắt đoạn theo cùng quan sát hình.
- `SELECTION_RULE.json`, `FROZEN_CHOICE_BEFORE_VALIDATION.json`,
  `ENDPOINT_CHOICE_BEFORE_CHECKS.json`, `FINAL_DECISION.json`: quyết định và giới hạn.

Không có thay đổi vào mã nhận dạng hoặc mặc định sản phẩm trong vòng này.
Server và điện thoại giữ VietLip 1.10.1. Các thí nghiệm giúp xác định hướng
không nên đưa vào app và giữ dữ liệu cho việc cải thiện mô hình thị giác sau này.
Sau khi kiểm tra server hoạt động trở lại, đã để điện thoại ở **Trực tiếp**.
Hai lựa chọn khôi phục bằng API vẫn nằm trong Cài đặt; lịch sử tám phiên vẫn
giữ nguyên các cặp bản gốc/Groq đã ghi trong lúc thu dữ liệu.
