# VietLip: scene Wi-Fi đầu tiên và bản Android 1.6.1

Scene 1 có bảy câu được người nói xác nhận nguyên văn. Kết nối WebSocket trực
tiếp từ điện thoại trong LAN đã thành công. Server nhận 1.627 khung trong phiên
66,39 giây; FPS tại các sự kiện phụ đề là 24,96–25,04. Không có khoảng hở capture
lớn hơn 0,5 giây. Có bảy đoạn chốt tự động và 25/25 biên nhận Flutter frame.

WER là 41/76 = 53,95%; CER bỏ khoảng trắng là 40,32%. Không có caption đã hiện
bị sửa lùi trong phiên này. Độ trễ cuối cửa sổ hình đến biên nhận ứng dụng là
2,059–2,909 giây (trung vị 2,634); đây chưa phải độ trễ từ lúc ngừng phát âm thật.
Thay right-context ở logic caption thành 0,5 / 1,0 / 1,5 / 2,0 giây không giảm
WER cuối trên cùng 25 giả thuyết. Giữ cấu hình SO17 hiện tại khi thu các baseline.

## Android 1.6.1+13

Thêm **Lịch sử → chọn phiên → Lưu video ra máy**. Dùng trình chọn nơi lưu của
Android, chép nguyên byte MP4 có audio để người dùng xuất bản ghi và đối chiếu.
Đường dẫn nguồn phải thuộc thư mục captures của VietLip. Xử lý I/O trên luồng
riêng; hủy chọn file trả quyền thao tác; lỗi mất file có thông báo. Không thêm
quyền bộ nhớ diện rộng hoặc thư viện phụ thuộc mới.

`server/scripts/lan_recording_exchange.py` là tiện ích QA tạm trong LAN: phục vụ
APK được chỉ định và nhận video do người dùng chọn. Không chạy mô hình, không
thay đổi live API. Giới hạn 200 MB/file, kiểm header, tính SHA-256, mỗi video có
thư mục riêng và receipt; metadata ghi rõ chưa kiểm tra decode media. Không có
endpoint duyệt tùy ý tệp trên PC. Chạy khi cần trao đổi bản ghi thử nghiệm.

Kiểm chứng: Flutter analyze sạch, 28 tests pass, APK release build thành công;
application ID giữ nguyên, chữ ký khớp 1.6.0, versionCode tăng 12 → 13. Kiểm tra
truyền file LAN và tải APK khớp SHA-256. Thao tác chọn nơi lưu và đọc lại video
trên điện thoại thật đang chờ người dùng cập nhật để thử; chưa đánh dấu đã đạt.

Bằng chứng cục bộ: `artifacts/wifi_live_20261109_round01`. Video/bản chép cá nhân
và log đầy đủ không đưa vào Git. Goal tối ưu ứng dụng vẫn active; cần hình gốc
để so lại mô hình/crop trên cùng đầu vào, không suy ra cải thiện từ WER khác clip.
