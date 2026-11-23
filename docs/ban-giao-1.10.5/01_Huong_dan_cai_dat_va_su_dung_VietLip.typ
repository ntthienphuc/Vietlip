#import "template/lib.typ": basic-report

#let navy = rgb("#17344a");#let muted=rgb("#405461");#let shade=rgb("#edf1f3");#let rule=rgb("#c0cbd2");

#show: basic-report.with(doc-category:"Hướng dẫn sử dụng",doc-title:"Hướng dẫn cài đặt và sử dụng VietLip",author:"Dự án VietLip",affiliation:"Phiên bản 1.10.5  ·  Android và Windows",language:"vi",heading-color:navy,body-font:"Times New Roman",heading-font:"Calibri",logo:image("images/logo.png",width:50pt))

#set page(margin:(top:25mm,bottom:22mm,left:26mm,right:23mm));#set text(size:12pt);#set par(justify:true,leading:0.68em,spacing:0.94em);

#show heading.where(level:1): set text(size:20pt,weight:"bold");#show heading.where(level:2): set text(size:13.2pt,weight:"bold");

#show link: set text(fill:navy);#let cap(it)=text(font:"Calibri",size:9pt,fill:muted,it);

#let remark(title,it)=block(width:100%,inset:(left:10pt,top:5pt,bottom:5pt,right:4pt),stroke:(left:1.5pt+navy),above:6pt,below:5pt)[#set par(justify:false);#strong(title) #it];

#heading(level:1,numbering:none)[Cài đặt và mở máy chủ Windows]

#block(width:100%,breakable:false)[#grid(columns:(1fr,10pt,1fr,10pt,1fr),align:horizon,[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Windows")]#linebreak()#text(size:9.2pt)[#text("Mở máy chủ và mã QR")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Android")]#linebreak()#text(size:9.2pt)[#text("Quét mã để ghép nối")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Đọc môi")]#linebreak()#text(size:9.2pt)[#text("Xem phụ đề và lưu phiên")]]])]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.33fr,0.67fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Thành phần")]),strong([#text("Điều kiện vận hành")])),[#text("Hệ điều hành và bộ nhớ")],[#text("Windows 10 hoặc 11 x64. Khuyến nghị 16 GB RAM. Dành khoảng 6 GB ở đích cài và thêm 3,5 GB trên ổ chứa thư mục tạm.")],[#text("Xử lý và kết nối")],[#text("CPU có thể chạy nhận dạng. GPU NVIDIA với driver tương thích CUDA 12.6 giúp giảm thời gian xử lý. PC dùng Wi-Fi hoặc Ethernet trên cùng mạng nội bộ với điện thoại.")])]

#block(breakable:false,width:100%)[#grid(columns: (48%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/desktop.png",width:100%,height:218pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("1. Chạy trình cài đặt")]#linebreak()#text("Mở VietLip-Server-Setup-1.10.5.exe trong 01_Bo_cai và làm theo trình cài. Bộ cài đã chứa môi trường chạy và mô hình đọc môi.")]#block(below:8pt)[#strong[#text("2. Mở VietLip Server")]#linebreak()#text("Tìm VietLip Server trong Start Menu. Chờ cửa sổ hiển thị “Sẵn sàng đọc môi” và mã QR.")]#block(below:8pt)[#strong[#text("3. Giữ cửa sổ này mở")]#linebreak()#text("Khi Windows hỏi quyền truy cập mạng, chọn mạng riêng mà bạn tin cậy. Giữ PC thức trong khi quay.")]])#v(5pt)#cap[#text("Hình 1. Cửa sổ máy chủ. Hãy quét mã đang hiển thị trên máy tính của bạn.")]]

#par[Để VietLip Server mở trong suốt phiên đọc môi. Nếu cửa sổ còn báo đang nạp mô hình, chờ đến khi mã QR xuất hiện.]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Ghép điện thoại bằng mã QR")]

#par[Kết nối điện thoại và PC vào cùng mạng nội bộ. PC có thể dùng Wi-Fi hoặc cáp Ethernet.]

#block(above: 7pt, below: 7pt)[#strong[#text("1. Cài ứng dụng")]#linebreak()#text("Bản 1.10.5 yêu cầu Android 7.0 (API 24) trở lên. Chuyển VietLip-1.10.5.apk vào điện thoại rồi mở bằng ứng dụng Tệp. Khi Android hỏi quyền cài từ nguồn này, cấp quyền cho ứng dụng đang mở APK. Với bản VietLip cùng chữ ký đã cài, chọn Cập nhật để giữ lịch sử.")]

#block(breakable:false,width:100%)[#grid(columns: (33%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/connected.png",width:100%,height:285pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("2. Quét trên điện thoại")]#linebreak()#text("Mở VietLip → Cài đặt → Quét QR máy chủ. Cho phép sử dụng camera và hướng máy vào mã trên PC đến khi bộ quét nhận được địa chỉ.")]#block(below:8pt)[#strong[#text("3. Xác nhận ghép nối")]#linebreak()#text("Chờ dòng “Sẵn sàng đọc môi” rồi chạm Về màn hình đọc môi. Điện thoại sẽ dùng lại địa chỉ đã lưu cho lần sau.")]#block(below:8pt)[#strong[#text("Nếu nhập địa chỉ thủ công")]#linebreak()#text("Chép đủ http://, địa chỉ IP và cổng ở cạnh QR. Chạm Lưu và kiểm tra. Cổng mặc định của bộ cài là 7100. Ưu tiên giá trị PC đang hiển thị.")]])#v(5pt)#cap[#text("Hình 2. Màn hình Cài đặt sau khi điện thoại đã lưu địa chỉ và kiểm tra kết nối.")]]

#par[Khi đổi Wi-Fi, mở VietLip Server, chọn *Làm mới IP* rồi dùng điện thoại quét mã mới.]

#pagebreak(weak:true)

#heading(level:1,numbering:none)[Đọc môi trực tiếp]

#par[Giữ điện thoại dọc, đặt nguồn sáng trước mặt và chọn camera. Điều chỉnh khoảng cách để thấy rõ miệng trong khung.]

#block(above:5pt,below:6pt)[#strong("1. Bắt đầu phiên") #linebreak()Nhìn gần chính diện vào camera, cách máy khoảng 40–50 cm. Chạm *Bắt đầu đọc môi* rồi nói tự nhiên.]
#block(above:5pt,below:9pt)[#strong("2. Theo dõi phụ đề") #linebreak()Văn bản hiện dưới khung camera. Với câu dài, phụ đề có thể xuất hiện từng cụm. Với câu ngắn, chữ có thể hiện sau khi bạn ngừng nói.]
#align(center)[#image("figures/live-captions.png",width:68%)]
#align(center)[#cap[Hình 3. Phụ đề gốc ở trên, gợi ý cho cùng câu ở dưới.]]
#block(above:10pt)[#strong("3. Kết thúc phiên") #linebreak()Sau câu cuối, giữ mặt trong khung thêm một nhịp để phụ đề hiện đủ. Chạm *Kết thúc phiên* và chờ ứng dụng lưu.]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Phụ đề gốc và gợi ý câu")]

#par[Chọn *Phụ đề trực tiếp* để xem chữ nhận dạng từ khẩu hình. Chọn *Kèm gợi ý câu* nếu muốn xem thêm cách diễn đạt mà Gemini đề xuất sau mỗi đoạn.]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.29fr,0.32fr,0.39fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Điều người dùng cần biết")]),strong([#text("Phụ đề trực tiếp")]),strong([#text("Kèm gợi ý câu")])),[#text("Nội dung trên màn hình")],[#text("Văn bản do mô hình thị giác trên PC sinh ra.")],[#text("Phụ đề gốc ở trên. Gợi ý diễn đạt cho cùng câu ở dưới.")],[#text("Thời điểm chữ xuất hiện")],[#text("Khi có đủ căn cứ trong lúc nói hoặc khi đoạn được chốt.")],[#text("Phụ đề gốc hiện trước. Gợi ý có thể về sau khi máy chủ nhận phản hồi từ Google.")],[#text("Kết nối cần có")],[#text("Kết nối mạng nội bộ giữa Android và PC.")],[#text("Mạng nội bộ và Internet trên PC. Máy chủ cần key Gemini hợp lệ.")])]

#heading(level: 2, numbering: none, outlined: false)[#text("Bật gợi ý cho phiên tiếp theo")]

#block(above:7pt,below:7pt)[#strong("1. Chọn khóa Gemini trên PC")#linebreak()Bộ cài nội bộ đã có sẵn khóa. Nếu dùng khóa riêng, mở *VietLip Server → Cài đặt key Gemini*, nhập khóa mới rồi lưu.]

#block(above: 7pt, below: 7pt)[#strong[#text("2. Chọn chế độ trên điện thoại")]#linebreak()#text("Vào Cài đặt → Cách đọc môi → Kèm gợi ý câu rồi chạm Áp dụng. Trở về màn Đọc môi và bắt đầu phiên mới.")]

#par[Ở chế độ gợi ý, PC gửi phần chữ đã chốt cho mô hình ngôn ngữ lớn Gemini. Gợi ý có thể đổi từ hoặc dấu câu. Bạn có thể xem lại cả hai dòng trong Lịch sử.]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Xem lại phiên và lưu MP4")]

#par[Mỗi lần chạm *Kết thúc phiên*, ứng dụng lưu phiên vào *Lịch sử*. Mở phiên để xem phụ đề theo thứ tự đã nói.]

#block(breakable:false,width:100%)[#grid(columns: (33%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/history-export.png",width:100%,height:285pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("1. Chọn đúng phiên")]#linebreak()#text("Mở tab Lịch sử. Mở phiên vừa quay và xem các câu theo thứ tự. Nếu đã bật gợi ý, đối chiếu từng gợi ý với câu gốc tương ứng.")]#block(below:8pt)[#strong[#text("2. Xuất video")]#linebreak()#text("Tại mục Video của phiên, chạm Lưu video ra máy. Chọn thư mục dễ tìm, chẳng hạn Downloads, rồi xác nhận thao tác lưu của Android.")]#block(below:8pt)[#strong[#text("3. Xem video đã lưu")]#linebreak()#text("Mở tệp MP4 trong thư mục đã chọn để xem lại. Video có tiếng nếu đã cấp quyền micrô khi quay.")]])#v(5pt)#cap[#text("Hình 4. Màn hình chi tiết một phiên và vị trí nút Lưu video ra máy.")]]

#heading(level: 2, numbering: none, outlined: false)[#text("Đọc một video đã có trên điện thoại")]

#par([#text("Ở màn Đọc môi, chạm Chọn video có sẵn rồi chọn video trong thư viện Android. Khi thấy “Video sẵn sàng”, cuộn xuống dưới thẻ video nếu cần, sau đó chạm Đọc môi từ video này. Giữ kết nối với máy chủ trong lúc chờ kết quả.")])

#pagebreak(weak:true)

#heading(level:1,numbering:none)[Xử lý sự cố]

#heading(level:2,numbering:none,outlined:false)[Kết nối điện thoại với máy chủ]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.32fr,0.68fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Hiện tượng")]),strong([#text("Cách xử lý")])),[#text("PC chưa hiện sẵn sàng")],[#text("Mở VietLip Server và chờ nạp mô hình. Nếu có thông báo cổng bị dùng, xác định cửa sổ VietLip cũ, kết thúc phiên đang chạy rồi đóng cửa sổ cũ trước khi mở lại.")],[#text("Bộ quét không thấy mã")],[#text("Kiểm tra quyền Camera cho VietLip trong phần Ứng dụng của Android. Đưa nguyên mã QR vào khung, tránh lóa. Có thể nhập địa chỉ và cổng ngay trong Cài đặt.")],[#text("Quét được nhưng lưu địa chỉ thất bại")],[#text("So địa chỉ trên điện thoại với dòng địa chỉ cạnh QR trên PC. Làm mới IP nếu đã đổi mạng. Chọn Lưu và kiểm tra sau khi sửa.")],[#text("Hai máy cùng Wi-Fi vẫn mất kết nối")],[#text("Wi-Fi khách có thể cô lập các thiết bị. Dùng mạng riêng cho phép hai thiết bị liên lạc hoặc nối PC vào điểm phát sóng của điện thoại, sau đó làm mới địa chỉ trên PC.")],[#text("Kết nối mất giữa phiên")],[#text("Kiểm tra PC còn thức, máy chủ còn mở và Wi-Fi trên điện thoại còn hoạt động. Quét lại khi địa chỉ thay đổi rồi mở phiên mới để kiểm tra.")])]

#heading(level:2,numbering:none,outlined:false)[Hình ảnh, phụ đề và âm thanh]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.32fr,0.68fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Dấu hiệu")]),strong([#text("Cách xử lý")])),[#text("Vùng camera đen hoặc môi quá nhỏ")],[#text("Cấp quyền camera cho VietLip. Nếu thấy “Camera chưa sẵn sàng”, chạm “Mở lại camera”. Khi môi quá nhỏ, đưa máy lại gần và hướng mặt về phía nguồn sáng.")],[#text("Chữ hiện chậm hoặc ghép hai câu")],[#text("Thử một câu ngắn ở nơi sáng và giữ máy cố định. Nghỉ rõ sau câu. Kiểm tra tải xử lý của PC khi hiện tượng lặp lại với cùng cách quay.")],[#text("Có chữ khi chỉ cử động hoặc cười")],[#text("Giữ nét mặt thư giãn giữa các câu. Chuyển động môi không lời đôi khi kích hoạt nhận dạng. ")],[#text("Có phụ đề gốc, thiếu dòng gợi ý")],[#text("Kiểm tra chế độ vừa áp dụng, Internet của PC và cấu hình Gemini trong cửa sổ máy chủ. Có thể tiếp tục dùng phụ đề trực tiếp trong lúc dịch vụ gián đoạn.")],[#text("Xuất được MP4 nhưng thiếu tiếng")],[#text("Kiểm tra âm lượng trình phát và quyền micrô của VietLip. Sau khi cấp quyền, quay một phiên mới và thử xuất lại.")])]
