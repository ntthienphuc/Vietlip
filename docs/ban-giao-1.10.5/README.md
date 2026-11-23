# VietLip 1.10.5 · Bộ bàn giao nội bộ

Bản Android là build 30, package `vn.lipread.lip_reader`. Thư mục phân phối
`VietLip_1.10.5_Tron_bo` gồm ba thư mục con. Danh sách sáu tệp và mã kiểm
SHA-256 tương ứng nằm trong [SHA256SUMS](SHA256SUMS).

| Thư mục | Nội dung |
| --- | --- |
| `01_Bo_cai` | APK Android đã ký và bộ cài Windows x64 có sẵn mô hình SO17 |
| `02_Tai_lieu` | Hướng dẫn cài đặt và sử dụng, báo cáo phương pháp nhận dạng |
| `03_Video_demo` | Phiên đọc môi trực tiếp và video hướng dẫn thao tác |

Trên máy bàn giao, mở `Downloads\VietLip_1.10.5_Tron_bo`. Bộ cài Windows
nội bộ chứa thông tin cấp quyền Gemini. Các bộ cài và video cá nhân được
lưu ngoài Git.

## Biên tập lại hai báo cáo

Hai tệp nguồn Typst cùng dùng mẫu Basic Report 0.5.0 trong `template`
(giấy phép MIT), gói Hydra 0.6.2, Times New Roman và Calibri. Các thư mục
`template`, `images` và `figures` cạnh hai nguồn chứa đầy đủ mẫu và hình.
Hình 3 dùng `figures/live-captions.png`, chỉ chứa phần giao diện phụ đề.

Tại thư mục chứa hai tệp Typst, chạy:

```powershell
typst compile --creation-timestamp 1795136400 01_Huong_dan_cai_dat_va_su_dung_VietLip.typ
typst compile --creation-timestamp 1795136400 02_Bao_cao_phuong_phap_nhan_dang_VietLip.typ
```

Lần biên dịch đầu cần tải các gói Typst hoặc dùng cache đã có. Khi tạo
ấn bản mới, cập nhật ngày trên bìa và kiểm tra lại mục lục, ảnh và dấu tiếng
Việt. Dấu vân tay trong SHA256SUMS dùng để đối chiếu sáu tệp đã bàn giao.
