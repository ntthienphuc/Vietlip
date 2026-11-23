# LipLens — đọc môi tiếng Việt · 1.5.0

Kho mã nguồn lúc phát hành 1.5 là kho riêng. Địa chỉ hiện tại là [ntthienphuc/Vietlip](https://github.com/ntthienphuc/Vietlip).

Ứng dụng Android dùng camera và máy chủ suy luận trên PC. Phụ đề live **chỉ dùng
hình ảnh**; video lưu trên điện thoại có âm thanh để đối chiếu khi kiểm thử.
Tự phát hiện chuyển động môi và khoảng ngừng, tiếp tục nhận câu mới mà không cần
bấm “Xong câu”. Đã thử trên Samsung SM-G965F / Android 10. Bản iPhone chưa được
build hoặc kiểm chứng.

**Hiện vẫn là ứng dụng thử nghiệm: chưa đọc câu nói tự do với độ chính xác cao.**
Đợt so sánh mới giữ SO17 làm mặc định; bốn câu điện thoại được xác nhận vẫn có
57,50% WER khi phát lại với mốc cửa sổ cố định. Tốc độ cập nhật không bảo đảm câu
đúng. Xem [kết quả chọn checkpoint](docs/CHECKPOINT_SELECTION_2026-11-09.md).

## Giao diện và luồng sử dụng

- Preview dọc lớn, hiển thị trọn hình đúng tỷ lệ; có viền trống khi tỷ lệ camera
  khác màn hình. Hướng và lật ảnh theo CameraX, cả trước và trong khi quay.
- Live ưu tiên camera và phụ đề, ẩn thanh điều hướng. Chữ lớn; phần gạch dưới còn
  được cập nhật, phần đã chốt được giữ theo cơ chế đồng thuận giữa các cửa sổ.
- Nút mở rộng xem/sao chép toàn bộ phụ đề. Thông số camera nằm trong “Thông tin
  phiên”; tuỳ chọn quay và hướng dẫn nằm trong nút ba chấm.
- Cỡ chữ lớn và màn hình nhỏ có thể cuộn; lịch sử tự cập nhật khi phiên mới được
  lưu. Bản ghi từ công cụ phát lại được ghi rõ “Kiểm thử phát lại”.
- App báo trạng thái kết nối, thiếu mặt, hình tối và mất luồng; không im lặng chờ
  vô hạn. Camera vẫn có thể ghi lại nhai/cười thành hoạt động môi.

## Chạy trên máy đã chuẩn bị

```powershell
cd E:\Project\Lip_App\lip_reader
.\server\run_realtime.ps1
```

Chờ `/healthz` báo `model_state: ready`. Cấu hình hiện tại: SO17, CUDA nếu có,
float32, live beam 3 / CTC 0.1, cửa sổ 6 giây, bước 1,5 giây, camera nhắm 25 fps.
Không cần LLM hoặc API key. Phoneme/LLM và checkpoint trộn tắt mặc định.

Qua USB, cắm điện thoại đã cho phép gỡ lỗi rồi chạy:

```powershell
.\tools\connect_android_usb.ps1
```

Trong Cài đặt, dùng `http://127.0.0.1:7100`, bấm **Lưu và kiểm tra**. Giữ cáp
trong phiên. Đây là đường kết nối đã kiểm chứng. Wi-Fi dùng địa chỉ IPv4 của PC
và cần máy chủ được phép nhận kết nối trên mạng đó; việc cùng Wi-Fi chưa đủ.
Android emulator dùng `http://10.0.2.2:7100`.

Trở về Đọc môi, **Bắt đầu live**, nhìn gần chính diện và nói tự nhiên từng câu.
**Kết thúc phiên** lưu video và phụ đề. Live tối đa 5 phút; gửi một video để xử lý
đầy đủ tối đa 45 giây. Video MP4 nằm trong dữ liệu app, có thể mất nếu gỡ ứng dụng.

## Cài đặt từ một checkout mới

Đã dùng Python 3.11, Flutter 3.44 / Dart 3.12, Android SDK và JDK 21 ở máy này.
Model, video, khóa ký và kết quả chạy lớn không nằm trong Git. **Clone mã nguồn
chưa đủ để suy luận:** cần checkpoint SO17 được cấp riêng, có hash trong
`server/models/MODEL_MANIFEST.json`.

```powershell
.\server\setup_server.ps1 -Runtime gpu  # hoặc cpu
.\tools\import_model.ps1 -SourcePath 'C:\path\to\SO_seed17.pt'
.\build_android.ps1 -Mode profile -OutputDir output
```

Bản profile AOT dùng để kiểm thử local. Để cập nhật bản đang cài có chữ ký nội bộ,
dùng `tools/sign_device_apk.ps1` với khóa ký local hiện có; không gỡ app để đổi
chữ ký vì sẽ mất dữ liệu. iOS yêu cầu môi trường và kiểm thử riêng.

## Kiểm chứng và giới hạn

- [Bàn giao 1.5.0: UI, máy thật và thời gian dựng phụ đề](docs/RELEASE_1_5_0_2026-11-09.md).
- [Kiến trúc, cách bảo trì và các lệnh kiểm tra](docs/ARCHITECTURE.md).
- [Chọn cấu hình sau thử bảy checkpoint và các bản trộn](docs/CHECKPOINT_SELECTION_2026-11-09.md).
- [Âm vị trực tiếp và video bốn câu](docs/DIRECT_PHONEME_2026-11-09.md).
- [Nhánh âm vị theo cửa sổ dở câu](docs/PHONEME_WINDOWS_2026-11-07.md).
- [Các phương pháp đã xem xét](docs/APP_METHOD_REVIEW_2026-11-09.md).
- [Kết nối / phục hồi](docs/CONNECTION_RECOVERY_2026-11-06.md),
  [chốt phụ đề](docs/CAPTION_STABILITY_2026-11-06.md),
  [ghi âm tham chiếu và từ vựng](docs/AUDIO_OPEN_VOCABULARY_2026-11-06.md).

Mục tiêu là phụ đề khoảng 2–3 giây sau câu. Thời gian xử lý server, thời điểm
Flutter dựng chữ và thời điểm thực sự nói xong là ba mốc khác nhau; các báo cáo
nêu rõ mốc đo, không coi chúng tương đương. Camera có thể có khoảng hụt hình lúc
bắt đầu phiên; hệ thống ghi lại khoảng hụt và phần chưa nhận dạng được.

Nguồn và điều kiện sử dụng giữ tại `server/vendor/licenses`,
`packages/camera_android_camerax/LICENSE` và `server/assets/README.md`.
Đây chưa phải một bản phát hành thương mại. Tài liệu cũ được giữ trong `docs`;
chúng mô tả từng bản thử nghiệm và không thay thế cấu hình hiện tại.
