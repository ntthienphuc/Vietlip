LIP READER SERVER 1.1.0 - HUONG DAN SU DUNG
============================================

KHOI DONG
---------
1. Mo "Lip Reader Server" va doi den khi hien "San sang nhan video".
2. Dien thoai va may tinh can o cung mang Wi-Fi.
3. Tren app Android, vao Cai dat va nhap dia chi LAN ma cua so server hien ra.
4. Bam "Luu va kiem tra".
5. Quay hoac chon video 2-12 giay, thay ro mat va mieng.

PHU DE TRUC TIEP
----------------
- Bat "Phu de truc tiep" tren app de xem chu cap nhat khi dang noi.
- Server dung cua so 6 giay chong lan 1 giay va noi tung doan thanh transcript lien tuc.
- CPU van hoat dong; lan dau co the cham do nap model, cac lan sau nhanh hon.
- Phien toi da 5 phut va khong dung LLM. Full-clip toi da 45 giay la luong doc lap.

CHE DO XU LY
------------
- Thuan chuyen dong moi: luon san sang, khong can LLM.
- Ngu canh gioi han: LLM chi chon mot cau co san trong N-best.
- Tro ly dien giai: tao ban dien giai rieng va giu nguyen ket qua thi giac.
- Hai che do LLM can thanh phan Ollama + Qwen duoc chon luc cai dat.
- LLM chi nhan N-best va ngu canh chu; video khong duoc gui cho LLM.

PHAN CUNG
---------
- Khong co GPU van chay duoc bang CPU float32; toc do se cham hon.
- Lan khoi dong dau tien co the mat vai phut de nap checkpoint.
- Qwen2.5:7b tai them khoang 4.7 GB va can RAM phu hop.

VAN HANH AN TOAN
----------------
- Luon kiem tra ket qua truoc khi su dung.
- Ket noi HTTP chi danh cho mang LAN tin cay; trien khai cong khai can HTTPS.
- Video tam duoc xoa sau khi xu ly; video khong duoc gui sang LLM.
- Ung dung gui job bat dong bo, tu dong cho trong hang doi va co the huy job.
- Bo cai va APK dung chu ky phan phoi noi bo. Phat hanh rong can chu ky thuong mai.
- Tai san mean-face can duoc cap quyen hoac thay the truoc muc dich thuong mai.

NHAT KY
-------
%LOCALAPPDATA%\Lip Reader Server\server.log
%LOCALAPPDATA%\Lip Reader Server\llm-install.log
