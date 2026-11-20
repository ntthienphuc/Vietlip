# VietLip 1.10.4 · Kết nối bằng QR

## Dùng trên PC và Android

Mở VietLip Server và đợi trạng thái **Sẵn sàng đọc môi**. Mở **Cài đặt → Quét QR máy chủ** trên Android rồi hướng camera sau vào mã lớn. Ứng dụng tự kiểm tra server và lưu địa chỉ khi nhận được phản hồi VietLip hợp lệ. Hai thiết bị cần kết nối được qua Wi-Fi/LAN. Nếu PC có nhiều IP, chọn đúng địa chỉ trong danh sách cạnh QR. Khi đổi mạng, bấm **Làm mới IP** và quét lại.

Ô địa chỉ và nút **Lưu và kiểm tra** dùng được khi cần nhập tay. Khi quét sai QR hoặc không tới được máy chủ, địa chỉ đã lưu trước đó vẫn dùng được. Mã chỉ chứa địa chỉ HTTP của server trên mạng nội bộ. Camera giải mã tại chỗ bằng ML Kit tích hợp trong APK.

## Kiểm tra bộ cài

- 53 test Flutter qua và analyze sạch. Hai bài riêng kiểm định dạng QR Windows, giữ đúng cổng và từ chối dữ liệu ngoài định dạng hoặc ngoài mạng nội bộ.
- 12 test server, phiên bản và đóng gói qua. Bộ cài Windows tự xác minh được payload. 163 file core VietLip khớp manifest ngày 17/11.
- Ảnh chụp của cửa sổ Windows thật giải mã được địa chỉ 192.168.1.8:7100. Cửa sổ hiển thị vùng QR 268 × 268 theo kích thước Tk.
- Galaxy S9+ cài đè bản 1.10.4+26 bằng chữ ký cũ. SHA-256 file trên điện thoại khớp APK bàn giao. Mở quét thì camera trước nhả và camera sau vào. Quay lại màn đọc môi thì camera trước mở lại.
- Kết quả đo ảnh/độ trễ của model đọc môi nằm trong báo cáo 1.10.3.

Bộ cài và hash được ghi ở [DELIVERY.json](../artifacts/qr_pairing/DELIVERY.json).


Đã cài EXE 1.10.4 lên PC và mở lại qua Start Menu. Cả 11.927 file khớp manifest sau cài. Server báo SO17 sẵn sàng trên CUDA. S9+ kết nối tới bản cài qua Wi-Fi và hiện Sẵn sàng đọc môi khi dùng địa chỉ đã lưu. Đã quét trực tiếp mã trên màn hình PC hai lần bằng camera sau S9+. Cả hai lần tự về Cài đặt, lưu đúng http://192.168.1.8:7100 và báo Sẵn sàng đọc môi. Tiến trình giữ cùng PID và không có log crash của tiến trình trong lượt thử. Lần thứ hai camera sau mở lúc 08:04:56 và nhả lúc 08:04:58 theo đồng hồ điện thoại. Bằng chứng gồm windows-ui.json, installed-health.json, installed-verify.json, phone-camera-switch.txt và ảnh giao diện.


## Android build 27

Nếu camera đã hướng vào QR, Android build 26 có thể nhận mã ngay và tự quay về Cài đặt trước khi người dùng kịp thấy hình. Build 27 giữ màn quét trong lúc xác minh server và hiện xác nhận trước khi tự quay về. Lỗi kết nối hiển thị ngay trong màn quét với nút Quét lại. Hai bài Flutter bao phủ mã nằm sẵn trong khung và lỗi server, nâng tổng số test qua lên 55.

Đã cài đè và quét thật trên S9+. Ảnh mẫu sau cú bấm ghi lại trạng thái hướng camera ở 0,36 giây, Đã nhận mã QR ở 0,66 giây, Đã kết nối ở 1,70 giây và trở về Cài đặt ở 2,78 giây. Địa chỉ đã lưu là 192.168.1.8:7100. Không có crash trong tiến trình kiểm thử. EXE Windows 1.10.4 dùng cùng payload đã xác minh.
