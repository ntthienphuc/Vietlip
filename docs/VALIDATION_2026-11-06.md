# Kiểm chứng ứng dụng Lip Reader — 2026-11-06

> Đây là biên bản lượt khôi phục 1.2.0. Đợt tối ưu tiếp theo 1.3.0, sáu checkpoint,
> camera native và replay dài được ghi riêng ở [OPTIMIZATION_2026-11-06.md](OPTIMIZATION_2026-11-06.md).

## Phạm vi và trạng thái

Đã khôi phục app vào `E:\Project\Lip_App\lip_reader`, sửa luồng camera/WS/server, tích hợp checkpoint thật và build APK. Không chạy lại nghiên cứu, không sửa bài báo, không thuê GPU/cloud, không push/deploy/publish. Luồng ứng dụng hoạt động local; **chưa đạt mục tiêu nhận dạng chính xác cao**. Không có điện thoại vật lý/người nói live trong đợt kiểm tra này.

App đã bị lưu trữ và xóa source local trước đó. Khôi phục 483 file từ gói backup, đối chiếu SHA256 từng member theo manifest trước khi sửa. Bản gốc là commit `1c38d94`, app 1.1.0; bản sửa là 1.2.0+3. Receipt khôi phục nằm trong workspace của lượt làm việc. Git chưa commit các thay đổi mới.

## Model và lý do chọn

Đọc bộ checkpoint native đầy đủ trong Paired_Neural_Kit_v1 của Lip lớn. Thử thực tế ba model: VLR pretrained, WW seed17, SO seed17; chưa benchmark các seed29/43. Copy runtime/tokenizer vào app và tạo hardlink hai checkpoint nghiên cứu. Không ghi đè trọng số. `server/models/MODEL_MANIFEST.json` ghi nguồn và SHA256. Native E2E nạp strict đủ 767 state entries, bỏ phụ thuộc initializer Lightning lúc inference.

Tất cả số dưới được tính lại cùng chuẩn NFC/chữ thường/bỏ dấu câu, khoảng trắng làm đơn vị WER; dấu tiếng Việt được giữ. Đây là 6 clip vùng môi phát triển và 2 clip điện thoại cũ, đã dùng chọn cấu hình. Không phải tập test độc lập; không suy ra tổng quát hóa.

| Model, float32 beam 3 | 6 ROI, 120 từ | 2 video điện thoại, 33 từ |
|---|---:|---:|
| VLR pretrained | 46/120 = 38,3% WER | 32/33 = 97,0% |
| WW seed17 | 39/120 = 32,5% | 18/33 = 54,5% |
| SO seed17 | 49/120 = 40,8% | 13/33 = 39,4% |

Chọn SO seed17 cho luồng app vì kết quả tốt hơn trên hai video điện thoại nhỏ này; WW tốt hơn trên ROI. Đây là lựa chọn thực dụng có bằng chứng hẹp, không kết luận SO là model tốt nhất nói chung. `WW17_beam3.json` cũ lưu WER trước chuẩn hóa; dùng `METRICS_SUMMARY.json` để so sánh thống nhất.

Thử mixed precision cho đầu ra lỗi/nonfinite, đã loại. Mặc định float32; peak VRAM riêng model đo khoảng 1,2 GB. Không dùng audio và không dùng LLM sửa dự đoán. GPU là GTX 1650 Ti 4 GB; CPU i7-10750H, RAM 16 GB. CPU fallback không được chứng nhận đủ real time.

## Replay thời gian thực

`server/scripts/replay_stream.py` ghép clip theo tên, gửi JPEG theo đồng hồ thực, packet có timestamp và sequence, nhận ACK/partial/final qua API thật. Các ROI có sẵn không chạy face detector; replay điện thoại dùng toàn mặt, resize ngang 360 px và JPEG80. Không đưa transcript/reference vào inference.

| Replay 25 fps sau sửa quyền chốt từ | Thời lượng | Khung gửi/mất do backpressure | WER | Phụ đề đầu | Decode trung vị | Chốt sau kết thúc |
|---|---:|---:|---:|---:|---:|---:|
| 6 ROI nối liên tiếp | 37,00 s | 925 / 0 | 53/120 = 44,2% | 3,81 s | 2,25 s | 4,02 s |
| 2 clip điện thoại | 14,68 s | 367 / 0 | 16/33 = 48,5% | 3,57 s | 3,28 s | 4,85 s |

ROI trước sửa ghép cửa sổ: 80/120 = 66,7% WER. Cửa sổ 6 giây, phần đuôi 1 giây còn được sửa, tối thiểu 2 giây trước decode. Bỏ quy tắc chờ toàn bộ tiền tố giống nhau vì decoder offline sửa từ cũ làm mất cả đoạn mới. Dùng CTC alignment của chính dự đoán để chốt theo thời gian; xử lý jitter tại từ biên và giữ lặp từ thật. Không phải mạng streaming causal. Tốc độ và kết quả ghép có thể thay đổi theo tải máy/thời điểm snapshot.

Các file `SO17_stream_*_v2.json` chứa mọi event và transcript cửa sổ, không chỉ số tổng hợp. `METRICS_SUMMARY.json` được tổng hợp từ các dự đoán đã lưu, không chạy lại model để chọn số đẹp.

## Thay đổi ứng dụng

- Camera portrait, không thu âm; khởi tạo có timeout và chống khởi tạo trùng do hộp thoại cấp quyền. Bố cục cho thấy nút quay trên màn hình emulator 720x1280.
- Lấy mẫu theo pha để camera 30 fps không bị throttle thành 15 fps; một encode đang chạy, tối đa 4 frame chờ ACK. Android nén trên worker native, có log số callback/số frame/thời gian encode.
- Packet LIP2: sequence uint32 big endian và timestamp float64 millisecond từ callback camera, rồi JPEG. Server bounded buffer 8 giây/24 MB, latest-window, resample theo timestamp. Khoảng mất hình trên 0,5 giây không được lấp thành chuyển động giả.
- Dùng chung semaphore cho live và job video. Chờ worker kết thúc trước nhả tài nguyên khi disconnect. Stop luôn trả final kể cả cửa sổ trước lỗi; không tái dùng transcript cũ với timestamp mới.
- MP4 được copy khỏi cache sang documents/captures. Phụ đề live có nội dung được lưu history, đánh dấu nếu bị gián đoạn. Về nền sẽ dừng/lưu quay rồi giải phóng camera, trở lại sẽ khởi tạo lại.
- Giữ luồng chọn MP4 → POST job → trạng thái → kết quả/N-best → lịch sử. Video full-clip tối đa 45 giây; live 5 phút. App lưu bản chốt, không tự sửa bằng LLM.

## Kiểm tra phần mềm và thiết bị

37 server tests pass (có một cảnh báo deprecation từ Starlette/AnyIO); 10 Flutter tests pass; Flutter analyze không có issue. Tests bao gồm timestamp/order/gap/bounded buffer, CTC lặp, ghép biên, ACK/backpressure/final, stop sau decode lỗi. `pip check` không có dependency conflict; PowerShell launcher/setup/build parse không lỗi.

Android API35 x86_64 emulator, APK được cài thật bằng adb. Đã kiểm tra camera preview, bắt đầu/dừng, ghi MP4, quay về nền và trở lại; chọn video điện thoại từ Photo Picker, upload thật, nhận kết quả và lịch sử. Camera giả lập chỉ là cảnh kiểm tra, không có mặt người. Server từ chối tạo phụ đề khi không theo dõi được mặt.

Kết quả full-clip trong app cho video 2: “hôm nay chúng ta sẽ học về một lần và lớp”. Reference lịch sử: “hôm nay chúng ta sẽ học về môn ngữ văn lớp 10”. Ví dụ này cho thấy lỗi thực tế vẫn rõ, không thể gắn nhãn độ chính xác cao.

Các phép đo camera emulator được lưu riêng trong log và `DEVICE_CHECK.json`; không thay bằng số 25 fps của replay. Chưa kiểm thử camera/thermal/Wi-Fi trên điện thoại thật, chưa đo phiên nói live 5 phút, chưa đo accuracy trên người/nội dung độc lập.

## Cách tiếp tục

Chạy `server/run_realtime.ps1`, cài APK, cấu hình URL PC. Emulator dùng `http://10.0.2.2:7100`; IPv4 LAN tại lúc kiểm tra là `192.168.1.14` (có thể đổi). Ưu tiên đo FPS, độ trễ và WER trên điện thoại thật, câu mới và người nói mới trước khi nói app đã sẵn sàng sử dụng chính xác cao. Nếu yêu cầu vẫn là nhận dạng tự do với WER thấp, còn cần model/dữ liệu phù hợp miền quay điện thoại; không có chỉnh UI hoặc ghép cửa sổ nào bảo đảm giải quyết được phần đó.


## Replay cuối sau kiểm tra lỗi và tối ưu preprocessing

Lần replay hai clip điện thoại sau cùng (`SO17_stream_phone25_final.json`) nhận đủ 367 frame/14,68 giây, WER 12/33 = **36,4%**, phụ đề đầu 4,29 giây, decode trung vị 3,06 giây, chốt cuối 4,47 giây. So với lần trước 48,5%, model/trọng số vẫn là SO seed17; khác thời điểm lấy snapshot khi tải máy thay đổi cũng làm khác kết quả ghép. Giữ cả hai lần đo và không coi 36,4% là bảo đảm chất lượng ổn định. Replay ROI 44,2% ở bảng trên là lần đã lưu trước đó.

Android cuối dùng profile AOT; nén JPEG một lần ở kích thước camera, gửi góc sensor trong handshake. Server xoay đúng chiều rồi resize 360px trước face tracking. Test màu/hình học xác nhận quay 90 độ và resize không đổi hướng tọa độ. Preprocessing live không thử lại bốn hướng của MP4 vì camera đã khai báo orientation; offline MP4 vẫn có fallback xoay. Điều này giảm chi phí trường hợp không có mặt.

## Số đo camera APK cuối

APK profile 1.2.0+3 SHA256 `10dcbb6134d60d5bff3fa2dbb857cc80efa15e2035f8baeec48f422a10dce4a7`. Phiên camera giả lập cuối: **513 khung/39,454 giây = 13,00 fps**, 802 callback camera, encode trung bình 46,67ms, 2 khoảng timestamp cách nhau trên 0,5 giây. Nhanh hơn bản debug đầu khoảng 2,17fps nhưng **chưa đạt 25fps qua camera**. Không thay số này bằng 25fps của replay. Thử profile trước tối ưu một JPEG nhận 10,19fps trong 63,8 giây và không có gap lớn; các phép đo khác tải máy/thời lượng nên không phải benchmark kiểm soát độc lập.

Settings của APK cuối xác nhận server ready, CUDA float32, phụ đề trực tiếp sẵn sàng. Lịch sử vẫn mở được kết quả nhận dạng thật sau cập nhật APK. Gói bàn giao có APK, launcher, hướng dẫn, báo cáo, metrics JSON và ảnh màn hình. Server local được để chạy cho việc thử app; emulator headless vẫn sẵn sàng. Không phát hành ra Internet.
