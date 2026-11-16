VIETLIP SERVER 1.10.1 — ĐỌC MÔI TIẾNG VIỆT

1. Cài VietLip Server bằng file Setup.exe. Giữ tất cả file .bin cạnh Setup.exe.
   Bộ cài đã có Python 3.11, runtime CPU/CUDA và mô hình SO17. Không tải thêm model.
2. Mở VietLip Server trong Start Menu. Chờ “Sẵn sàng đọc môi”.
3. Kết nối điện thoại Android và PC cùng mạng Wi-Fi / LAN.
4. Cài VietLip-1.10.1.apk trên điện thoại. Mở Cài đặt, nhập IP được server hiển thị
   (có thể chỉ nhập IP; app tự dùng http và cổng 7100), rồi Lưu và kiểm tra.
5. Trở về Đọc môi, bấm Bắt đầu đọc môi. Giữ máy dọc, mặt đủ sáng, nói từng câu.
   Hệ thống tự chốt đoạn khi thấy khoảng ngừng. Kết thúc phiên để lưu bản ghi.

KẾT NỐI KHÔNG DÂY
- Ví dụ địa chỉ: http://192.168.1.20:7100. IP của mỗi PC sẽ khác.
- IP có thể thay đổi khi đổi Wi-Fi hoặc khởi động lại router. Bấm Làm mới IP trên
  server và cập nhật địa chỉ trong app nếu cần.
- Cùng tên Wi-Fi chưa bảo đảm các thiết bị liên lạc được. Mạng khách/công cộng
  có thể chặn kết nối giữa thiết bị; dùng mạng nội bộ cho phép kết nối ngang hàng.
- Nếu Windows hỏi quyền mạng, cho phép VietLip/Python trên mạng nội bộ tin cậy.
  Khi firewall chặn, quản trị viên cần cho phép TCP 7100 từ mạng cục bộ tới
  runtime\pythonw.exe. Không cần tắt firewall hoặc mở cổng Internet.
- Server hiện rõ khi có phiên bản khác đang chạy trên cổng 7100. Đóng server cũ
  rồi mở lại bản mới; app không tự tắt chương trình khác.

PHẦN CỨNG VÀ GIỚI HẠN
- Windows 10/11 x64, RAM khuyến nghị 16 GB, khoảng 6 GB trống để cài.
- Ưu tiên GPU NVIDIA và driver tương thích CUDA 12.6. CPU có thể chạy nhưng
  chậm hơn; không bảo đảm độ trễ 2–3 giây trên mọi cấu hình.
- Nhận dạng chỉ dùng hình ảnh. Video lưu trên điện thoại có tiếng để đối chiếu.
- Đây là bản thử nghiệm, vẫn nhận sai đáng kể khi nói tự do. Cần kiểm tra phụ đề.
- Lịch sử → chọn phiên → Lưu video ra máy để xuất bản MP4 có tiếng. Bản gốc
  vẫn được giữ trong ứng dụng. Khi kết thúc, chờ phụ đề cuối được chốt.
- Bộ lọc CNN nhận biết lời nói đang được kiểm tra riêng và chưa bật mặc định.
  Cười, nhai hoặc chuyển động môi không nói vẫn có thể tạo phụ đề sai.
- Giữ cửa sổ server mở; đóng cửa sổ sẽ dừng server do cửa sổ đó khởi động.
- Nhật ký: %LOCALAPPDATA%\VietLip\logs. Không cần LLM hoặc API key.
- Quyền của mã nguồn/tài sản bên thứ ba được giữ trong server\vendor\licenses,
  server\assets và runtime\Lib\site-packages. Bộ cài dành cho thử nghiệm nội bộ;
  chưa xác nhận quyền thương mại của toàn bộ dữ liệu và mô hình.

KIỂM TRA / GỠ CÀI ĐẶT
- API health: http://IP-CUA-PC:7100/healthz.
- Công cụ kiểm file (PowerShell tại thư mục đã cài):
  .\runtime\python.exe .\verify_bundle.py
- Gỡ VietLip Server từ Windows Settings > Apps. Bản ghi điện thoại và các project
  khác không bị tác động. Nhật ký local được giữ để đối chiếu.

AI KHÔI PHỤC CÂU (TÙY CHỌN)
- Chọn Cài đặt > Cách đọc môi > Khôi phục câu, rồi chọn Groq hoặc OpenRouter.
- Khi chốt câu, app hiện bản đọc môi ở trên và bản khôi phục ở dưới ngay trong live.
- Tạo rewrite.json từ rewrite.example.json tại %LOCALAPPDATA%\VietLip, cấu hình
  key riêng trên PC và enabled=true. Key không nằm trong APK hoặc bộ cài.
- OpenRouter chỉ dùng model :free, không tự chuyển sang model trả phí.
- AI cần Internet, chỉ nhận văn bản. Lỗi API/hết quota giữ nguyên câu gốc.
- Trực tiếp vẫn hoạt động trong mạng nội bộ mà không cần API key.
