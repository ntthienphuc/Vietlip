# Kiểm tra hướng ảnh và đáp án dự phòng

Giữ cấu hình SO17 của VietLip 1.6.3. Đảo ngang ảnh môi và chấm kết hợp hai
hướng ảnh đều làm xấu đi ít nhất một scene phát triển. Các phép thử này không
thay mã nhận dạng đang chạy, APK hoặc bộ cài Windows.

## So sánh trên đúng cửa sổ đã lưu

50 cửa sổ của bốn scene được kiểm hash pixel, dùng cùng SO17/float32/beam 3,
CTC 0.1 và cùng cách ghép phụ đề. Baseline chạy lại khớp văn bản đã lưu ở
50/50 cửa sổ. Phép đảo ngang chỉ thay trục ngang của tensor ảnh môi; không
đổi mốc thời gian, câu tham chiếu hoặc dùng âm thanh. Đây là replay MP4, không
phải bản phục dựng JPEG camera của phiên live gốc.

| Scene | Đơn vị tham chiếu | SO17 hiện tại | Đảo ngang | Chấm trung bình hai hướng | Thêm đáp án từ ảnh đảo, chấm bằng ảnh gốc |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1, bảy câu | 76 | 43 lỗi | 34 lỗi | 40 lỗi | 43 lỗi |
| 2, nói nối câu | 40 | 15 lỗi | 16 lỗi | 16 lỗi | 12 lỗi |
| 3, im lặng | 0 | 7 chữ sinh thêm | 4 chữ sinh thêm | 4 chữ sinh thêm | 4 chữ sinh thêm |
| 4, bốn câu mới | 18 | 11 lỗi | 11 lỗi | 11 lỗi | 11 lỗi |

WER dùng đơn vị tiếng Việt tách bằng khoảng trắng, thường là âm tiết; CER bỏ
khoảng trắng. Scene im lặng không có WER/CER xác định. Các hướng ảnh không
giải quyết việc sinh chữ khi không nói. Tất cả phép ghép giữ nguyên tiền tố đã
hiển thị; điều này không chứng minh những từ đó đúng.

Chấm hai hướng dùng trung bình cố định của điểm attention/CTC, không thử nhiều
trọng số để khớp đáp án. Biến thể chỉ chấm bằng ảnh gốc là phân tích bổ sung:
nó giúp scene 2 nhưng chưa giúp scene 4, nên cần kiểm tra hồi quy trên video cũ
trước khi cân nhắc sử dụng. Không chọn cấu hình riêng theo từng câu hoặc scene.

## Kiểm tra thêm 159 cửa sổ và quyết định

Giữ cố định biến thể mở rộng đáp án rồi chạy trên ba video điện thoại cũ và
video ghép dài. 159/159 kết quả baseline khớp bản đã lưu; tensor và thời gian
cửa sổ giữ nguyên. Câu tham chiếu chỉ dùng sau khi đã lưu tất cả dự đoán.

| Video | Đơn vị tham chiếu | SO17 hiện tại | Mở rộng đáp án |
| --- | ---: | ---: | ---: |
| Điện thoại lượt 2 | 44 | 25 lỗi | 25 lỗi |
| Điện thoại lượt 3 | 76 | 48 lỗi | 49 lỗi |
| Điện thoại lượt 4 | 40 | 23 lỗi | 23 lỗi |
| Video ghép dài | 599 | 400 lỗi | 402 lỗi |

Biến thể bị loại vì làm xấu một video điện thoại và video dài. Trung vị thời
gian tính nối tiếp tăng từ 227–378 ms lên 526–864 ms tùy video, chưa gồm mạng
và hiển thị. Tổng lỗi trên bảy video có nói của cả hai lượt so sánh là
565/893 ở cả baseline và biến thể; điểm tổng này không thay thế kiểm tra từng
video và không bao gồm scene im lặng.

Đợt thử này kết thúc ở 209 cửa sổ của tám video, với ba phương án: đổi hướng
ảnh, chấm hai hướng, và mở rộng đáp án. Không phương án nào đủ điều kiện thay
cấu hình chính. Kết hợp với các phép thử checkpoint, âm vị và LLM trước đây,
chốt **SO17/float32/beam 3/CTC 0.1**, giữ bộ cài **VietLip 1.6.3** đã kiểm
trên máy và điện thoại. Không rebuild chỉ để đưa một thử nghiệm không đạt vào
sản phẩm; các file mới chỉ là công cụ đánh giá và tài liệu.

Đây là điểm dừng thực dụng theo yêu cầu chọn phương án tốt nhất hiện có khi
các thử tiếp không cải thiện. Không phải chứng minh tối ưu toàn cục, đạt đọc
câu tự do chính xác cao hoặc luôn hiện chữ sau 2–3 giây. Một đợt huấn luyện
tiếp cần thêm video camera có bản chép và tập nghiệm thu tách biệt; học tiếp
các kịch bản đã biết không chứng minh khả năng đọc câu mới.

## Giới hạn của chọn lại ba đáp án

Với bốn cửa sổ chốt câu của scene 4, SO17 có 11/18 lỗi. Ngay cả khi dùng đáp
án thật để chọn phương án tốt nhất trong ba kết quả, vẫn còn 9/18 lỗi. Đây là
phép chẩn đoán có biết đáp án, không phải một thuật toán nhận dạng sử dụng được.
Câu dài cuối vẫn có ít nhất tám lỗi trong cả ba phương án. Chọn lại hoặc viết
lại văn bản không thể được coi là đã khôi phục bằng chứng hình ảnh bị thiếu.

Phiên camera thật vẫn có WER 66,67% / CER 50,00%; không lấy WER replay 61,11%
trừ khỏi WER live để tuyên bố cải thiện. Các video này cùng một người và đã được
dùng phát triển nhiều lần, không phải tập nghiệm thu độc lập của sản phẩm.

## Chi phí và kiểm chứng

Trên GPU hiện có, baseline có trung vị giải mã khoảng 93–314 ms tùy scene.
Tổng chi phí nối tiếp ước tính của hai lần giải mã cộng chấm lại hai hướng
khoảng 291–879 ms; cách đo này còn mã hóa lại ảnh và chưa tối ưu cache. Các số
này loại trừ chờ kết thúc câu, tiền xử lý mặt, mạng và dựng chữ trên điện thoại.
Không dùng chúng để cam kết độ trễ nói xong đến thấy chữ.

Lượt chấm đầu tiên dừng đúng khi một đáp án dở câu không thể chuyển qua
SentencePiece rồi trở lại cùng văn bản. Kết quả dang dở được giữ riêng và
không được dùng tính điểm. Lượt thứ hai ghi rõ hai đề xuất không khôi phục
được token gốc ở một cửa sổ scene 2, loại chúng khỏi việc chấm lại thay vì
âm thầm đổi chữ. 50 cửa sổ hoàn tất; kiểm độc lập công thức điểm, lựa chọn
ứng viên và tiền tố phụ đề đều đạt.

Cuối lượt, nối PC vào cùng Wi-Fi hiện tại của điện thoại và cập nhật IP trong
app bằng màn hình Cài đặt. Nút kiểm tra báo sẵn sàng; GUI Windows hiển thị IP
mới. Phiên camera kiểm kết nối nhận 554 frame trong 22,141 giây, tốc độ gần
nhất 24,54 fps, không khoảng trống capture trên 500 ms và kết thúc bình thường.
Không có ADB reverse. Phiên không thấy mặt, không phát sinh lượt giải mã và
không sinh chữ, nên chỉ xác nhận đường truyền/đóng phiên, không tính vào độ
chính xác hoặc độ trễ câu nói. 31 file Python ứng dụng/server khớp bản đã cài.

## Bằng chứng và tái lập

- `artifacts/orientation_replay_20261110_v1`: 50 cặp giải mã cùng cửa sổ.
- `artifacts/orientation_consensus_20261110_v1`: lần dừng do kiểm token.
- `artifacts/orientation_consensus_20261110_v2`: chấm ứng viên hoàn tất và
  `VERIFICATION.json` kiểm các bất biến.
- `artifacts/orientation_archive_20261110_v1`: kiểm tra hồi quy 159 cửa sổ.
  `FINAL_WIFI_SMOKE_RECEIPT.json` và trace ghi lần kiểm kết nối sau đổi mạng.
- [Bảng số và hash báo cáo gốc](evidence/orientation_audit_20261110.json).
- Script trong `server/experiments/visual_activity_probe`: `orientation_replay.py`,
  `orientation_consensus.py`, `orientation_archive.py`.

Mỗi script tạo thư mục mới, kiểm hash và chỉ dùng bản chép để tính lỗi sau khi
lưu dự đoán. Video, bản chép cá nhân, tensor và model không đưa vào Git/bộ cài.
