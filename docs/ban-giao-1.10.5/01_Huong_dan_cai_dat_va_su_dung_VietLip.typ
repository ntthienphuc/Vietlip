#import "template/lib.typ": basic-report

#let navy = rgb("#17344a");#let muted=rgb("#405461");#let shade=rgb("#edf1f3");#let rule=rgb("#c0cbd2");

#show: basic-report.with(doc-category:"Hướng dẫn sử dụng",doc-title:"Hướng dẫn cài đặt và sử dụng VietLip",author:"Dự án VietLip",affiliation:"Phiên bản 1.10.5  ·  Android và Windows",language:"vi",heading-color:navy,body-font:"Times New Roman",heading-font:"Calibri",logo:image("images/logo.png",width:50pt))

#set page(margin:(top:25mm,bottom:22mm,left:26mm,right:23mm));#set text(size:12pt);#set par(justify:true,leading:0.68em,spacing:0.94em);

#show heading.where(level:1): set text(size:20pt,weight:"bold");#show heading.where(level:2): set text(size:13.2pt,weight:"bold");

#show link: set text(fill:navy);#let cap(it)=text(font:"Calibri",size:9pt,fill:muted,it);

#let remark(title,it)=block(width:100%,inset:(left:10pt,top:5pt,bottom:5pt,right:4pt),stroke:(left:1.5pt+navy),above:6pt,below:5pt)[#set par(justify:false);#strong(title) #it];

#heading(level: 1, numbering: none)[#text("Cài đặt và sử dụng VietLip")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Dành cho người cài đặt máy chủ Windows và người dùng điện thoại Android. Sau khi hoàn thành hướng dẫn, người dùng có thể ghép nối hai thiết bị, đọc một đoạn tiếng Việt trước camera và lưu phiên để xem lại.")]

#block(width:100%,breakable:false)[#grid(columns:(1fr,10pt,1fr,10pt,1fr),align:horizon,[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Windows")]#linebreak()#text(size:9.2pt)[#text("Mở máy chủ và mã QR")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Android")]#linebreak()#text(size:9.2pt)[#text("Quét mã để ghép nối")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Đọc môi")]#linebreak()#text(size:9.2pt)[#text("Xem phụ đề và lưu phiên")]]])]

#heading(level: 2, numbering: none, outlined: false)[#text("Kiểm tra trước khi bắt đầu")]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.38fr,0.62fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Thiết bị")]),strong([#text("Dấu hiệu có thể tiếp tục")])),[#text("Máy tính")],[#text("Cửa sổ VietLip Server hiển thị trạng thái sẵn sàng, địa chỉ của máy chủ và mã QR.")],[#text("Điện thoại")],[#text("VietLip mở được camera và thấy rõ khuôn mặt trong vùng xem trước.")],[#text("Mạng")],[#text("Sau khi quét QR hoặc nhập địa chỉ, điện thoại xác nhận đã kết nối với máy chủ.")])]

#heading(level: 2, numbering: none, outlined: false)[#text("Các tệp đi kèm")]

#par([#text("Trong ")#strong[#text("01_Bo_cai")]#text(", tệp EXE dùng cho PC và tệp APK dùng cho điện thoại. ")#strong[#text("03_Video_demo")]#text(" có một phiên đọc thật với tiếng của người nói và một video hướng dẫn từ lúc mở máy chủ đến khi lưu bản ghi. Có thể xem cả hai trước khi cài.")])

#remark([#text("Cách đọc phụ đề.")],[#text("VietLip ước lượng lời tiếng Việt qua hình ảnh. Với thông tin quan trọng như tên riêng, số tiền, liều lượng hoặc lịch hẹn, hãy đề nghị người nói xác nhận nội dung.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Chuẩn bị và mở máy chủ")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Máy chủ Windows thực hiện nhận dạng. Hãy cài thành phần này trên máy tính sẽ được sử dụng cùng điện thoại và giữ máy hoạt động trong suốt phiên.")]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.33fr,0.67fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Thành phần")]),strong([#text("Điều kiện vận hành")])),[#text("Hệ điều hành và bộ nhớ")],[#text("Windows 10 hoặc 11 x64. Khuyến nghị 16 GB RAM. Dành khoảng 6 GB ở đích cài và thêm 3,5 GB trên ổ chứa thư mục tạm.")],[#text("Xử lý và kết nối")],[#text("CPU có thể chạy nhận dạng. GPU NVIDIA với driver tương thích CUDA 12.6 giúp giảm thời gian xử lý. PC dùng Wi-Fi hoặc Ethernet trên cùng mạng nội bộ với điện thoại.")])]

#block(breakable:false,width:100%)[#grid(columns: (48%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/desktop.png",width:100%,height:218pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("1. Chạy trình cài đặt")]#linebreak()#text("Mở VietLip-Server-Setup-1.10.5.exe trong 01_Bo_cai và làm theo trình cài. Bộ cài đã chứa môi trường chạy và mô hình đọc môi.")]#block(below:8pt)[#strong[#text("2. Mở VietLip Server")]#linebreak()#text("Tìm VietLip Server trong Start Menu. Chờ cửa sổ hiển thị “Sẵn sàng đọc môi” và mã QR.")]#block(below:8pt)[#strong[#text("3. Giữ cửa sổ này mở")]#linebreak()#text("Khi Windows hỏi quyền truy cập mạng, chọn mạng riêng mà bạn tin cậy. Giữ PC thức trong khi quay.")]])#v(5pt)#cap[#text("Hình 1. Cửa sổ máy chủ. Hãy quét mã đang hiển thị trên máy tính của bạn.")]]

#remark([#text("Trước khi chuyển sang điện thoại.")],[#text("Nếu trạng thái vẫn đang nạp mô hình, chờ máy chủ sẵn sàng. Nếu Windows báo thiếu dung lượng, kiểm tra cả ổ cài đặt và ổ dùng cho tệp tạm.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Ghép điện thoại bằng mã QR")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Mã QR mang địa chỉ của máy chủ trong mạng hiện tại. Hai thiết bị cần liên lạc được với nhau qua mạng nội bộ. Có thể thiết lập hoàn toàn không dây.")]

#block(above: 7pt, below: 7pt)[#strong[#text("1. Cài ứng dụng")]#linebreak()#text("Bản 1.10.5 yêu cầu Android 7.0 (API 24) trở lên. Chuyển VietLip-1.10.5.apk vào điện thoại rồi mở bằng ứng dụng Tệp. Khi Android hỏi quyền cài từ nguồn này, cấp quyền cho ứng dụng đang mở APK. Với bản VietLip cùng chữ ký đã cài, chọn Cập nhật để giữ lịch sử.")]

#block(breakable:false,width:100%)[#grid(columns: (33%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/connected.png",width:100%,height:285pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("2. Quét trên điện thoại")]#linebreak()#text("Mở VietLip → Cài đặt → Quét QR máy chủ. Cho phép sử dụng camera và hướng máy vào mã trên PC đến khi bộ quét nhận được địa chỉ.")]#block(below:8pt)[#strong[#text("3. Xác nhận ghép nối")]#linebreak()#text("Chờ dòng “Sẵn sàng đọc môi” rồi chạm Về màn hình đọc môi. Điện thoại sẽ dùng lại địa chỉ đã lưu cho lần sau.")]#block(below:8pt)[#strong[#text("Nếu nhập địa chỉ thủ công")]#linebreak()#text("Chép đủ http://, địa chỉ IP và cổng ở cạnh QR. Chạm Lưu và kiểm tra. Cổng mặc định của bộ cài là 7100. Ưu tiên giá trị PC đang hiển thị.")]])#v(5pt)#cap[#text("Hình 2. Màn hình Cài đặt sau khi điện thoại đã lưu địa chỉ và kiểm tra kết nối.")]]

#remark([#text("Đổi mạng hoặc đổi PC.")],[#text("Mở máy chủ trên mạng mới, chọn Làm mới IP rồi quét lại QR. Địa chỉ trong các hình minh họa chỉ tương ứng với mạng tại thời điểm chụp.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Thực hiện một phiên đầu tiên")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Đặt điện thoại dọc ở nơi đủ ánh sáng. Có thể cầm máy hoặc đặt trên giá. Mục tiêu là thấy rõ cả mặt và chuyển động môi liên tục trong vùng xem trước.")]

#block(breakable:false,width:100%)[#grid(columns: (33%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/guide-live.png",width:100%,height:285pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("1. Đặt khung hình")]#linebreak()#text("Nhìn gần chính diện và giữ miệng trong khung. Có thể bắt đầu ở khoảng 40–50 cm, sau đó điều chỉnh theo kích thước khuôn mặt trên màn hình. Chọn camera phù hợp trước khi bắt đầu.")]#block(below:8pt)[#strong[#text("2. Bắt đầu đọc môi")]#linebreak()#text("Chạm Bắt đầu đọc môi. Nói tự nhiên, giữ đầu tương đối ổn định và nghỉ ngắn ở cuối câu. Theo dõi vùng phụ đề dưới khung camera.")]#block(below:8pt)[#strong[#text("3. Kết thúc phiên")]#linebreak()#text("Sau câu cuối, giữ khung hình một lúc để hệ thống nhận ra khoảng nghỉ và chốt phần cuối. Chạm Kết thúc phiên rồi đợi ứng dụng lưu xong.")]])#v(5pt)#cap[#text("Hình 3. Vị trí khung camera và hai ô văn bản khi người dùng chọn Kèm gợi ý câu.")]]

#heading(level: 2, numbering: none, outlined: false)[#text("Một bài thực hành ngắn")]

#par([#text("Nhìn vào camera, nói “Xin chào mọi người”, nghỉ khoảng ba giây rồi đọc “Cảm ơn mọi người và hẹn gặp lại”. Quan sát thời điểm chữ bắt đầu hiện và vị trí lưu câu cuối. Có thể mở video 01 trong thư mục demo để đối chiếu thao tác.")])

#remark([#text("Khi chưa thấy chữ.")],[#text("Tiếp tục giữ mặt trong khung cho tới cuối một cụm tự nhiên. Một câu rất ngắn có thể chỉ xuất hiện sau khoảng nghỉ.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Phụ đề gốc và gợi ý câu")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Hai lựa chọn phục vụ hai nhu cầu đọc. Chọn Phụ đề trực tiếp khi cần theo dõi kết quả từ khẩu hình. Chọn Kèm gợi ý câu khi muốn đọc thêm một cách diễn đạt cho đoạn vừa kết thúc.")]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.29fr,0.32fr,0.39fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Điều người dùng cần biết")]),strong([#text("Phụ đề trực tiếp")]),strong([#text("Kèm gợi ý câu")])),[#text("Nội dung trên màn hình")],[#text("Văn bản do mô hình thị giác trên PC sinh ra.")],[#text("Phụ đề gốc ở trên. Gợi ý diễn đạt cho cùng câu ở dưới.")],[#text("Thời điểm chữ xuất hiện")],[#text("Khi có đủ căn cứ trong lúc nói hoặc khi đoạn được chốt.")],[#text("Phụ đề gốc hiện trước. Gợi ý có thể về sau khi máy chủ nhận phản hồi từ Google.")],[#text("Kết nối cần có")],[#text("Kết nối mạng nội bộ giữa Android và PC.")],[#text("Mạng nội bộ và Internet trên PC. Máy chủ cần key Gemini hợp lệ.")])]

#heading(level: 2, numbering: none, outlined: false)[#text("Bật gợi ý cho phiên tiếp theo")]

#block(above: 7pt, below: 7pt)[#strong[#text("1. Dùng key có sẵn hoặc đổi trên PC")]#linebreak()#text("Bộ cài nội bộ trong thư mục này cấp sẵn key Gemini cho tài khoản Windows mới. Để dùng key riêng, mở VietLip Server → Cài đặt key Gemini, nhập key mới rồi lưu. Windows mã hóa key theo tài khoản hiện tại. Cài lại hoặc cập nhật sẽ giữ key đã chọn. EXE cấp sẵn key dành cho nhóm nội bộ. Người có bản cài có thể trích key và sử dụng hạn mức dùng chung.")]

#block(above: 7pt, below: 7pt)[#strong[#text("2. Chọn chế độ trên điện thoại")]#linebreak()#text("Vào Cài đặt → Cách đọc môi → Kèm gợi ý câu rồi chạm Áp dụng. Trở về màn Đọc môi và bắt đầu phiên mới.")]

#remark([#text("Dữ liệu gửi tới dịch vụ gợi ý.")],[#text("PC gửi phần chữ đã chốt tới mô hình ngôn ngữ lớn của Google. Mô hình có thể sửa dấu câu và diễn đạt lại, đồng thời cũng có thể đổi nghĩa. Hãy đối chiếu hai dòng khi có sự khác biệt.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Xem lại phiên và lưu MP4")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Lịch sử cho phép đối chiếu câu gốc và gợi ý sau khi buổi đọc kết thúc. Chức năng xuất video tạo một tệp có thể mở bằng trình phát trên điện thoại.")]

#block(breakable:false,width:100%)[#grid(columns: (33%,1fr),gutter:12pt,align:top,[#align(center)[#image("images/history-export.png",width:100%,height:285pt,fit:"contain")]], [#set par(justify:false);#block(below:8pt)[#strong[#text("1. Chọn đúng phiên")]#linebreak()#text("Mở tab Lịch sử. Mở phiên vừa quay và xem các câu theo thứ tự. Nếu đã bật gợi ý, đối chiếu từng gợi ý với câu gốc tương ứng.")]#block(below:8pt)[#strong[#text("2. Xuất video")]#linebreak()#text("Tại mục Video của phiên, chạm Lưu video ra máy. Chọn thư mục dễ tìm, chẳng hạn Downloads, rồi xác nhận thao tác lưu của Android.")]#block(below:8pt)[#strong[#text("3. Kiểm tra tệp")]#linebreak()#text("Mở tệp MP4 vừa lưu bằng trình phát. Xem đầu và cuối, kiểm tra hình và âm thanh nếu đã cấp quyền micrô. Giữ bản trong lịch sử cho đến khi xác nhận bản xuất mở được.")]])#v(5pt)#cap[#text("Hình 4. Màn hình chi tiết một phiên và vị trí nút Lưu video ra máy.")]]

#heading(level: 2, numbering: none, outlined: false)[#text("Phân biệt bản quay và bản ghi màn hình")]

#par([#text("MP4 xuất từ Lịch sử lưu hình camera của phiên. Khi đã cấp quyền micrô, âm thanh giúp người dùng nghe lại lời đã nói. Nếu cần minh họa chính giao diện và thời điểm phụ đề xuất hiện, hãy ghi màn hình điện thoại trong khi đọc. Video demo 01 đi kèm minh họa dạng thứ hai.")])

#heading(level: 2, numbering: none, outlined: false)[#text("Đọc một video đã có trên điện thoại")]

#par([#text("Ở màn Đọc môi, chạm Chọn video có sẵn rồi chọn video trong thư viện Android. Khi thấy “Video sẵn sàng”, cuộn xuống dưới thẻ video nếu cần, sau đó chạm Đọc môi từ video này. Giữ kết nối với máy chủ trong lúc chờ kết quả.")])

#remark([#text("Quyền riêng tư.")],[#text("Bản ghi có thể chứa khuôn mặt và giọng nói. Nếu chuyển cho người khác, hãy kiểm tra đúng phiên, nội dung và sự đồng ý của những người xuất hiện.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Điện thoại chưa kết nối được")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Kiểm tra lần lượt từ PC đến điện thoại. Quan sát kết quả sau mỗi thao tác để xác định bước gây gián đoạn.")]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.32fr,0.68fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Hiện tượng")]),strong([#text("Cách xử lý")])),[#text("PC chưa hiện sẵn sàng")],[#text("Mở VietLip Server và chờ nạp mô hình. Nếu có thông báo cổng bị dùng, xác định cửa sổ VietLip cũ, kết thúc phiên đang chạy rồi đóng cửa sổ cũ trước khi mở lại.")],[#text("Bộ quét không thấy mã")],[#text("Kiểm tra quyền Camera cho VietLip trong phần Ứng dụng của Android. Đưa nguyên mã QR vào khung, tránh lóa. Có thể nhập địa chỉ và cổng ngay trong Cài đặt.")],[#text("Quét được nhưng lưu địa chỉ thất bại")],[#text("So địa chỉ trên điện thoại với dòng địa chỉ cạnh QR trên PC. Làm mới IP nếu đã đổi mạng. Chọn Lưu và kiểm tra sau khi sửa.")],[#text("Hai máy cùng Wi-Fi vẫn mất kết nối")],[#text("Wi-Fi khách có thể cô lập các thiết bị. Dùng mạng riêng cho phép hai thiết bị liên lạc hoặc nối PC vào điểm phát sóng của điện thoại, sau đó làm mới địa chỉ trên PC.")],[#text("Kết nối mất giữa phiên")],[#text("Kiểm tra PC còn thức, máy chủ còn mở và Wi-Fi trên điện thoại còn hoạt động. Quét lại khi địa chỉ thay đổi rồi mở phiên mới để kiểm tra.")])]

#heading(level: 2, numbering: none, outlined: false)[#text("Khi cần người quản trị mạng")]

#par([#text("Đề nghị kiểm tra quyền nhận kết nối TCP tới cổng đang hiển thị trên PC từ mạng nội bộ. Nếu cần mô tả sự cố, ghi lại trạng thái trên cửa sổ máy chủ, trạng thái sau khi chọn Lưu và kiểm tra, cùng thao tác vừa thực hiện.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("Hình ảnh, phụ đề và âm thanh")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Khi điện thoại đã báo sẵn sàng, xác định vấn đề nằm ở hình camera, phụ đề gốc, gợi ý hay bản xuất video.")]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.32fr,0.68fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Dấu hiệu")]),strong([#text("Điều chỉnh và quan sát")])),[#text("Vùng camera đen hoặc môi quá nhỏ")],[#text("Cấp quyền camera cho VietLip, kiểm tra camera đang chọn, đưa mặt lại gần và hướng ánh sáng từ trước vào mặt. Quan sát vùng xem trước rồi bắt đầu một phiên ngắn.")],[#text("Chữ hiện chậm hoặc ghép hai câu")],[#text("Thử một câu ngắn ở nơi sáng và giữ máy cố định. Nghỉ rõ sau câu. Kiểm tra tải xử lý của PC khi hiện tượng lặp lại với cùng cách quay.")],[#text("Có chữ khi chỉ cử động hoặc cười")],[#text("Giữ nét mặt thư giãn giữa các câu. Chuyển động môi không lời đôi khi kích hoạt nhận dạng. Xem lại nội dung trước khi sử dụng.")],[#text("Có phụ đề gốc, thiếu dòng gợi ý")],[#text("Kiểm tra chế độ vừa áp dụng, Internet của PC và cấu hình Gemini trong cửa sổ máy chủ. Có thể tiếp tục dùng phụ đề trực tiếp trong lúc dịch vụ gián đoạn.")],[#text("Xuất được MP4 nhưng thiếu tiếng")],[#text("Kiểm tra âm lượng trình phát và quyền micrô của VietLip. Sau khi cấp quyền, quay một phiên mới và thử xuất lại.")])]

#heading(level: 2, numbering: none, outlined: false)[#text("Tài liệu tham khảo về cách trình bày")]

#block(above:4pt,below:5pt)[#link("https://diataxis.fr/how-to-guides/")[#strong[#text("Diátaxis · How-to guides")]]#linebreak()#text("Hướng dẫn này tổ chức nội dung theo công việc mà người dùng muốn hoàn thành.")]

#block(above:4pt,below:5pt)[#link("https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions")[#strong[#text("Microsoft Writing Style Guide · Writing step-by-step instructions")]]#linebreak()#text("Tên nút, thứ tự thao tác và dấu hiệu hoàn tất được đặt cùng bước để người đọc dễ làm theo.")]

#v(5pt)
#cap[Mẫu trình bày: #link("https://typst.app/universe/package/basic-report/")[Basic Report 0.5.0], Roland Schätzle. Dự án VietLip Việt hóa và điều chỉnh cho ấn bản này.]