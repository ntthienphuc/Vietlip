# Chọn cấu hình ứng dụng sau các thử nghiệm checkpoint

**Giữ SO17, float32, live beam 3 / CTC 0.1, cửa sổ 6 giây và bước 1,5 giây.**
Nhánh âm vị, LLM và checkpoint trộn không bật trong cấu hình mặc định.

## Phép so sánh đã hoàn tất

Thử bảy checkpoint gốc, trung bình nhóm SO, nhóm WW, cả sáu bản fine-tune,
và trộn SO17 với trung bình cả sáu ở tỷ lệ 25%, 50%, 75%. Tất cả dùng cùng
pixel tensor và mốc cửa sổ; kiểm SHA256. Chọn ứng viên trên 127 cửa sổ dev
(1.607 đơn vị từ), rồi kiểm tra hai tập 128 cửa sổ và các phụ đề ghép hoàn chỉnh.
Không dùng câu mẫu làm gợi ý nhận dạng. Checkpoint gốc được giữ nguyên.

| Bộ so sánh | SO17 | Trung bình sáu bản | SO17 + trung bình 50% |
| --- | ---: | ---: | ---: |
| Dev WER | 32,48% | 31,55% | 31,11% |
| Test WER / CER | 29,38% / 23,83% | 27,73% / 22,48% | 28,66% / 23,41% |
| Lexical test WER / CER | 28,05% / 20,97% | 26,12% / 19,31% | 26,44% / 19,85% |
| Điện thoại lượt 2, lỗi / 44 đơn vị | 25 | 26 | 26 |
| Điện thoại lượt 3, lỗi / 76 đơn vị | 48 | 48 | 48 |
| Điện thoại lượt 4, lỗi / 40 đơn vị | 23 | 24 | 23 |
| Video ghép dài, lỗi / 599 đơn vị | 400 | 388 | 384 |

Ứng viên trộn giúp tập corpus và video ghép nhưng làm xấu đi ít nhất một clip
điện thoại. Không thay mô hình mặc định dựa trên tổng điểm bị video dài chi phối.
Không tiếp tục chỉnh tỷ lệ theo các câu điện thoại đã biết. Đây là điểm dừng
thực dụng của đợt chọn cấu hình, không phải bằng chứng mô hình tối ưu toàn cục.

## Giới hạn quan trọng

WER dùng đơn vị tách bằng khoảng trắng tiếng Việt; các đơn vị này thường là âm
tiết. Các tập corpus có lịch sử dùng để phát triển mô hình; không chứng minh
chưa từng xuất hiện trong pretraining. Các clip điện thoại đã được dùng phân tích
trong nhiều lượt; không gọi đây là bộ kiểm thử độc lập của sản phẩm.

Không cửa sổ nào trả rỗng trong phép so sánh này, nhưng điều đó không có nghĩa
mọi câu đều đúng. Lượt điện thoại mới vẫn có **23/40 lỗi (57,50% WER)** và
**57/132 lỗi ký tự (43,18% CER)** với SO17. Ứng dụng chưa đạt đọc câu tự do chính
xác cao; cải thiện giao diện và tốc độ truyền hình không khắc phục giới hạn này.

## Bằng chứng và tái lập

- Bảng số và hash báo cáo gốc: [evidence/checkpoint_selection_20261109.json](evidence/checkpoint_selection_20261109.json).
- Dữ liệu đầy đủ giữ tại `artifacts/checkpoint_soup_20261109` và
  `artifacts/checkpoint_interpolation_20261109` trên máy, không đưa video lên Git.
- Script: `server/experiments/checkpoint_soup.py`. `--resume` chỉ nhận cùng
  protocol, model identity, thứ tự sample và hash pixel; một lần gián đoạn sau
  khi ghi EVAL đã được tiếp tục để hoàn tất bảng tổng hợp.
- [Các phương pháp đã xem xét](APP_METHOD_REVIEW_2026-11-09.md),
  [giải mã âm vị trực tiếp](DIRECT_PHONEME_2026-11-09.md).

Không thuê Vast cho phép so sánh suy luận này. Việc huấn luyện tiếp chỉ có ý
nghĩa khi có thêm dữ liệu camera được gán nhãn, tập phát triển và tập nghiệm thu
giữ riêng; học thuộc bốn hoặc bảy câu đã biết không đáp ứng mục tiêu ứng dụng.
