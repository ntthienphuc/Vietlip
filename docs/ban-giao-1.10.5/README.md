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
(giấy phép MIT), gói Hydra 0.6.2, Times New Roman và Calibri. Tạo thư mục
làm việc cục bộ, chép hai nguồn và `template` vào đó. Chép thư mục
`artifacts/final_review_20261120/images` của máy bàn giao vào cạnh hai nguồn.
Thư mục này gồm `logo.png`, `desktop.png`, `connected.png`, `guide-live.png`
và `history-export.png`. Ảnh phiên có người dùng được quản lý cục bộ.

Trong thư mục làm việc, chạy cho mỗi tài liệu:

```powershell
typst compile --creation-timestamp 1795136400 01_Huong_dan_cai_dat_va_su_dung_VietLip.typ
typst compile --creation-timestamp 1795136400 02_Bao_cao_phuong_phap_nhan_dang_VietLip.typ
```

Lần biên dịch đầu cần tải các gói Typst hoặc dùng cache đã có. Khi tạo
ấn bản mới, cập nhật ngày trên bìa và kiểm tra lại mục lục, ảnh và dấu tiếng
Việt. Dấu vân tay trong SHA256SUMS dùng để đối chiếu sáu tệp đã bàn giao.
