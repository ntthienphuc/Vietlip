#import "template/lib.typ": basic-report

#let navy = rgb("#17344a");#let muted=rgb("#405461");#let shade=rgb("#edf1f3");#let rule=rgb("#c0cbd2");

#show: basic-report.with(doc-category:"Báo cáo phương pháp",doc-title:"Nhận dạng lời nói tiếng Việt từ khẩu hình trong luồng video",author:"Dự án VietLip",affiliation:"Phiên bản 1.10.5  ·  Android và Windows",language:"vi",heading-color:navy,body-font:"Times New Roman",heading-font:"Calibri",logo:image("images/logo.png",width:50pt))

#set page(margin:(top:25mm,bottom:22mm,left:26mm,right:23mm));#set text(size:12pt);#set par(justify:true,leading:0.68em,spacing:0.94em);

#show heading.where(level:1): set text(size:20pt,weight:"bold");#show heading.where(level:2): set text(size:13.2pt,weight:"bold");

#show link: set text(fill:navy);#let cap(it)=text(font:"Calibri",size:9pt,fill:muted,it);

#let remark(title,it)=block(width:100%,inset:(left:10pt,top:5pt,bottom:5pt,right:4pt),stroke:(left:1.5pt+navy),above:6pt,below:5pt)[#set par(justify:false);#strong(title) #it];

#heading(level:1,numbering:none)[#text("1. Bài toán và kiến trúc hệ thống")]

#heading(level:2,numbering:none,outlined:false)[Tóm tắt]

#par[VietLip tạo phụ đề tiếng Việt từ chuỗi ảnh khuôn mặt. Máy chủ căn chỉnh vùng miệng, mã hóa chuyển động bằng mạng tích chập và Conformer, rồi giải mã văn bản bằng điểm kết hợp CTC và attention. Máy chủ xử lý các cửa sổ hình chồng lấn. Khi hai cửa sổ liên tiếp thống nhất về chữ và mốc thời gian, một phần phụ đề có thể hiện ngay trong lúc người dùng đang nói.]

#par[Khoảng nghỉ giữa các chuyển động môi giúp xác định điểm chốt đoạn. Nếu người dùng bật *Kèm gợi ý câu*, Gemini nhận phần chữ đã chốt và trả về một cách diễn đạt cho cùng đoạn. Ứng dụng giữ riêng hai kết quả.]

#par([#strong[#text("Từ khóa")]#text("   Nhận dạng lời nói thị giác, tiếng Việt, Conformer, CTC, cửa sổ trượt, phụ đề trực tiếp.")])

#block(width:100%,breakable:false)[#grid(columns:(1fr,10pt,1fr,10pt,1fr),align:horizon,[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Android")]#linebreak()#text(size:9.2pt)[#text("Khung hình JPEG có thời điểm thu")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Windows")]#linebreak()#text(size:9.2pt)[#text("Theo dõi mặt và suy luận SO17")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Android")]#linebreak()#text(size:9.2pt)[#text("Hiển thị chữ theo đúng đoạn")]]])]

#heading(level: 2, numbering: none, outlined: false)[#text("1.1. Đơn vị xử lý")]

#par([#text("Một phiên kéo dài từ lúc bắt đầu đến lúc người dùng kết thúc. Bên trong phiên, máy chủ tách các đoạn hoạt động môi. Mỗi đoạn có thể bao gồm một phần câu hoặc nhiều câu, tùy nhịp nói và khoảng nghỉ. “Câu” trên giao diện là đơn vị trình bày được gắn với đoạn do hệ thống chốt. Biên này được xác lập từ tín hiệu thị giác và có thể lệch với dấu câu trong một bản chép tay.")])

#heading(level: 2, numbering: none, outlined: false)[#text("1.2. Phân bố tính toán")]

#par([#text("Android giữ luồng xem trước và gửi gói ảnh qua WebSocket nội bộ. Số thứ tự và thời điểm thu cho phép máy chủ xác định thứ tự khung hình và khoảng gián đoạn. Máy chủ Windows nạp checkpoint một lần, xử lý từng cửa sổ rồi gửi sự kiện phụ đề về điện thoại. Việc chuyển suy luận sang PC cho phép dùng cùng trọng số trên CPU hoặc GPU và giảm khối lượng tính toán trên thiết bị cầm tay.")])

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.33fr,0.67fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Biến đầu ra")]),strong([#text("Nguồn thông tin và ý nghĩa")])),[#text("Y gốc")],[#text("SO17 suy luận từ chuỗi ảnh vùng môi. Biểu diễn từ các cửa sổ liên tiếp được ghép vào dòng thời gian của phiên.")],[#text("Y gợi ý")],[#text("Gemini nhận phần chữ Y gốc của một đoạn đã chốt. Gợi ý gắn với chính đoạn đó và được trình bày riêng.")],[#text("Âm thanh bản ghi")],[#text("Nếu người dùng cho phép micrô, âm thanh được lưu trong MP4 trên điện thoại để nghe lại. Nhánh suy luận trực tiếp nhận các khung ảnh.")])]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("2. ")#text("Tạo chuỗi ảnh vùng miệng")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Tín hiệu đầu vào có cả chuyển động phát âm lẫn chuyển động do tư thế đầu, khoảng cách camera và rung tay. Tiền xử lý đưa vùng môi về một hệ tọa độ ổn định trước khi tính đặc trưng.")]

#block(width:100%,breakable:false)[#grid(columns:(1fr,10pt,1fr,10pt,1fr,10pt,1fr),align:horizon,[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Mặt trong video")]#linebreak()#text(size:9.2pt)[#text("Định vị các mốc mặt")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Căn chỉnh")]#linebreak()#text(size:9.2pt)[#text("Biến đổi về hình tham chiếu")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Vùng môi")]#linebreak()#text(size:9.2pt)[#text("Ảnh xám 96 × 96")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Đầu vào mạng")]#linebreak()#text(size:9.2pt)[#text("Cắt giữa còn 88 × 88")]]])]

#heading(level: 2, numbering: none, outlined: false)[#text("2.1. Căn chỉnh theo mốc khuôn mặt")]

#par([#text("Máy chủ dùng các bộ phát hiện dựa trên MediaPipe để định vị khuôn mặt và thu mốc hình học. Khi chất lượng theo dõi thấp, đường xử lý có thể thử bổ sung mốc hoặc hướng ảnh khác. Các mốc hợp lệ dùng để nội suy vị trí thiếu trong đoạn và làm trơn quỹ đạo cục bộ. Biến đổi hình học theo khuôn mặt tham chiếu đưa vùng miệng về vị trí tương đối nhất quán qua các khung.")])

#heading(level: 2, numbering: none, outlined: false)[#text("2.2. Biểu diễn cường độ")]

#par([#text("Từ mỗi khung đã căn chỉnh, hệ thống trích vùng miệng xám 96 × 96 điểm ảnh và lấy phần trung tâm 88 × 88. Với cường độ ban đầu u trong [0, 255], giá trị đưa vào mạng là z = (u / 255 − 0,421) / 0,165. Một cửa sổ T khung tạo tensor T × 1 × 88 × 88 trước khi bổ sung chiều lô. Hai hằng số chuẩn hóa thuộc cấu hình suy luận của checkpoint.")])

#heading(level: 2, numbering: none, outlined: false)[#text("2.3. Ảnh hưởng của lấy mẫu")]

#par([#text("Ứng dụng hướng đến 25 hình/giây và luồng gửi được thu nhỏ có giữ tỷ lệ. Tần số mục tiêu xác định lưới lấy mẫu cho bộ nhận dạng. Khi camera hoặc mạng làm mất các pha chuyển động ngắn, việc lấy lại mẫu chỉ sắp xếp các quan sát sẵn có. Các chi tiết như thời điểm môi vừa khép rồi mở vẫn có thể thiếu.")])

#par[Video toàn mặt cần qua bước định vị và căn chỉnh. Với dữ liệu đã cắt sẵn vùng miệng, máy chủ dùng đường tiền xử lý dành cho ảnh vùng miệng.]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("3. ")#text("SO17 và biểu diễn theo thời gian")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Bản ứng dụng dùng checkpoint SO_seed17.pt của đường thị giác Auto-AVSR, với phép suy luận FP32. Kiến trúc kết hợp đặc trưng không–thời gian ở vùng miệng với ngữ cảnh theo chuỗi [1, 2].")]

#block(width:100%)[#set text(size: 11pt);#set par(justify:false,leading:0.65em);#table(columns:(0.22fr,0.39fr,0.39fr,), inset:7pt,stroke:(x,y)=>(top: if y==0 {0.7pt+navy} else {0.3pt+rule}), fill:(x,y)=>if y==0 {shade},table.header(strong([#text("Khối")]),strong([#text("Cấu hình trong mô hình ứng dụng")]),strong([#text("Vai trò")])),[#text("Tích chập 3D")],[#text("1 → 64 kênh. Nhân 5 × 7 × 7. Bước 1 × 2 × 2.")],[#text("Kết hợp thông tin của các ảnh lân cận, giảm kích thước không gian và giữ bước thời gian.")],[#text("Thân ResNet")],[#text("Bốn tầng BasicBlock, lần lượt 2, 2, 2, 2 khối. Đầu ra 512 chiều.")],[#text("Mã hóa đặc trưng hình dạng vùng miệng ở từng vị trí thời gian.")],[#text("Conformer")],[#text("Chiếu 512 → 768. 12 khối, 12 đầu attention, tầng truyền thẳng 3.072, nhân tích chập 31.")],[#text("Kết hợp biến đổi cục bộ và quan hệ giữa các vị trí trong cùng cửa sổ.")],[#text("Hai nhánh giải mã")],[#text("Đầu CTC trên đặc trưng 768 chiều. Transformer decoder 6 khối, 12 đầu, tầng truyền thẳng 3.072.")],[#text("Tạo điểm cho chuỗi token theo hai cách bổ sung nhau.")])]

#heading(level: 2, numbering: none, outlined: false)[#text("3.1. Vì sao cần một chuỗi ảnh?")]

#par([#text("Một ảnh chụp miệng đang khép cung cấp ít thông tin về âm ngay trước hoặc sau nó. Tích chập theo thời gian quan sát chuyển đổi giữa các trạng thái. Khối Conformer mở rộng ngữ cảnh đến những vị trí xa hơn trong cửa sổ. Cách xử lý này có thể khai thác nhịp vận động và ảnh hưởng giữa các âm kế tiếp.")])

#heading(level: 2, numbering: none, outlined: false)[#text("3.2. Vai trò của checkpoint")]

#par([#text("SO17 là bộ tham số nhận dạng đã huấn luyện được nạp vào kiến trúc này. Trong phiên sử dụng, hệ thống tính đầu ra với tham số cố định. Thông tin từ các cửa sổ mới thay đổi bằng chứng đầu vào và giả thuyết văn bản, chứ không cập nhật trọng số mô hình.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("4. ")#text("Ghép điểm CTC và attention")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Bộ giải mã xét các chuỗi ứng viên hình thành từ các mảnh văn bản tiếng Việt. Cơ chế này cho phép sinh một câu mới bằng cách tổ hợp các đơn vị đã học [3, 4].")]

#heading(level: 2, numbering: none, outlined: false)[#text("4.1. Bảng đơn vị tiếng Việt")]

#par([#text("Bộ SentencePiece đi kèm có 2.000 đơn vị. Adapter thêm ký hiệu trống của CTC và ký hiệu kết thúc, đồng thời kiểm tra thứ tự token giữa bảng đơn vị và tokenizer. Một tiếng có thể được tạo từ nhiều mảnh. Vì vậy một từ vắng trong các câu huấn luyện vẫn có thể biểu diễn được. Khả năng biểu diễn một cách viết và khả năng chọn đúng cách viết ấy từ khẩu hình là hai điều kiện khác nhau.")])

#heading(level: 2, numbering: none, outlined: false)[#text("4.2. Điểm của một giả thuyết")]

#par([#text("Nhánh CTC gán điểm theo thời gian, cho phép ký hiệu trống và các lặp liên tiếp, rồi gộp các đường căn chỉnh tương thích với cùng chuỗi. Nhánh attention tính token kế tiếp dựa vào token đã sinh và biểu diễn thị giác. Khi mở rộng một tiền tố, máy chủ kết hợp điểm của hai nhánh trong miền log.")])

#remark([#text("Quy tắc xếp hạng của cấu hình triển khai")],[#text("S = 0,90 × S_attention + 0,10 × S_CTC. Beam search giữ tối đa ba giả thuyết ở mỗi bước. Các hệ số này mô tả cách tìm kiếm khi suy luận.")])

#par([#strong[#text("Ví dụ tính điểm.")]#text(" Giả sử hai tiền tố A và B có cặp điểm (attention, CTC) lần lượt là (−1,0; −3,0) và (−1,1; −1,2). Điểm kết hợp của A là −1,20, của B là −1,11. B xếp trên A vì điểm CTC của B bù được phần chênh lệch attention.")])

#heading(level: 2, numbering: none, outlined: false)[#text("4.3. Từ chuỗi token đến mốc chữ")]

#par([#text("Sau khi chọn chuỗi, hệ thống dùng căn chỉnh Viterbi trên điểm CTC để tìm đường thời gian phù hợp với các token đã dự đoán. Các mảnh thuộc cùng đơn vị hiển thị được gom theo biên SentencePiece. Mốc đầu và cuối thu được dùng để so sánh hai dự đoán từ cửa sổ chồng lấn. Sai token vẫn có thể nhận được một mốc căn chỉnh hợp lệ.")])

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("5. ")#text("Nhận biết hoạt động môi và điểm dừng")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Cơ chế phân đoạn quan sát biến dạng môi theo thời gian. Nó vận hành trên ảnh camera ngay cả khi người dùng tắt micrô.")]

#heading(level: 2, numbering: none, outlined: false)[#text("5.1. Đại lượng chuyển động")]

#par([#text("Với đầu vào toàn mặt, bộ theo dõi lấy 20 mốc ở đường viền môi, dùng trục nối hai mắt để định hướng tọa độ và dùng khoảng cách giữa mắt để chuẩn hóa tỷ lệ. Nó còn tính độ mở miệng bằng khoảng cách môi trên–dưới chia cho chiều rộng miệng. Thay đổi tư thế đầu lớn, mặt quá nhỏ hoặc góc xoay bất lợi được đánh dấu để hạn chế diễn giải chuyển động của cả đầu thành chuyển động môi.")])

#remark([#text("Điểm hoạt động hình học")],[#text("m = max(Δh / 0,009, |Δa| / 0,035). Δh là căn trung bình bình phương độ dịch của các tọa độ môi đã chuẩn hóa. Δa là biến thiên độ mở tương đối giữa hai quan sát hợp lệ. m biểu thị mức biến đổi hình học.")])

#heading(level: 2, numbering: none, outlined: false)[#text("5.2. Quy tắc mở và chốt đoạn")]

#par([#text("Khi chưa có đoạn, hệ thống tìm ít nhất ba quan sát chuyển động trong 0,45 giây, trải trên tối thiểu 0,18 giây. Ngưỡng mở là 1,0 và ngưỡng duy trì hạ xuống 0,65 để tránh ngắt đoạn ở những pha chuyển động nhẹ. Bộ đệm giữ tối đa 0,45 giây trước thời điểm bắt đầu phát hiện để đưa phần đầu của âm vào cửa sổ.")])

#par([#text("Đối với camera toàn mặt, khoảng giảm hoạt động kéo dài 0,60 giây có thể kích hoạt chốt đoạn. Phần đuôi sau quan sát chuyển động cuối được giữ tối đa 0,24 giây. Gián đoạn khung hình hoặc mất quan sát mặt có thể kết thúc đoạn theo nguyên nhân khác. Mốc gửi phụ đề còn phụ thuộc thời gian chờ tài nguyên, chạy mô hình và truyền kết quả.")])

#heading(level: 2, numbering: none, outlined: false)[#text("5.3. Hệ quả đối với lời nói tự nhiên")]

#par([#text("Hai câu nói liền nhau có thể nằm trong một đoạn. Ngược lại, người nói dừng giữa câu để suy nghĩ có thể tạo hai đoạn. Mỉm cười hoặc nhai cũng làm thay đổi hình dạng môi. Quy tắc điểm dừng ước lượng hoạt động thị giác và vì thế không thể xác định trọn vẹn ý định nói.")])

#block(width:100%,breakable:false)[#grid(columns:(1fr,10pt,1fr,10pt,1fr),align:horizon,[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Quan sát")]#linebreak()#text(size:9.2pt)[#text("Tích lũy dấu hiệu chuyển động")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Đang nói")]#linebreak()#text(size:9.2pt)[#text("Cập nhật lần môi chuyển động gần nhất")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Khoảng nghỉ")]#linebreak()#text(size:9.2pt)[#text("Giữ đuôi và chốt đoạn")]]])]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("6. ")#text("Cửa sổ trượt và nguyên tắc ổn định chữ")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Mạng nhận dạng xử lý một đoạn hữu hạn mỗi lần. Cảm giác đọc trực tiếp đến từ việc chạy lại trên hình mới, căn các giả thuyết vào cùng trục thời gian và chỉ công bố những phần có đủ căn cứ.")]

#block(breakable:false,width:100%)[#set text(font:"Calibri",size:9pt);
#grid(columns:(86pt,1fr), row-gutter:4pt,align:horizon,
[Thời gian], [#grid(columns:(1fr,1fr,1fr,1fr,auto),[0 s],[2 s],[4 s],[6 s],[8 s])],
[Lần đầu], [#rect(width:25%,height:7pt,fill:rgb("#5491af"),stroke:none)],
[Đủ hình mới], [#rect(width:43.75%,height:7pt,fill:rgb("#36738e"),stroke:none)],
[Cửa sổ về sau], [#grid(columns:(1fr,3fr),[],[#rect(width:100%,height:7pt,fill:navy,stroke:none)])])
#v(3pt)#cap[Hình 1. Độ phủ của ba cửa sổ minh họa trên cùng trục thời gian. Các lần xử lý trung gian được lược bớt.]]

#heading(level: 2, numbering: none, outlined: false)[#text("6.1. Lập lịch")]

#par([#text("Khi có ít nhất 2,0 giây hình của đoạn đang nói, máy chủ có thể thử lần giải mã sớm đầu tiên. Các lần tiếp theo cách nhau ít nhất 1,5 giây theo mốc hình mới và nhìn lại tối đa 6 giây. Vì vậy lượng hình chồng lấn thay đổi theo lịch xử lý. Khi phát hiện điểm dừng, máy chủ giữ cố định các khung thuộc cửa sổ cuối để giải mã phần còn lại.")])

#heading(level: 2, numbering: none, outlined: false)[#text("6.2. Thỏa thuận giữa các cửa sổ")]

#par([#text("Mốc CTC được đưa về thời gian tuyệt đối của phiên. Một tiền tố được chấp nhận sớm khi hai cửa sổ khác nhau trả cùng chữ theo đúng thứ tự, với chênh lệch trung điểm trong dung sai 0,65 giây. Hệ thống dành lại 1 giây ngữ cảnh ở mép phải trước khi công bố sớm. Nếu bất đồng ở một vị trí, phần đuôi tiếp tục chờ thêm hình.")])

#par([#text("Khi một phần chưa giải quyết sắp rời khỏi phạm vi quan sát, hệ thống giữ các đơn vị cũ đã trượt ra ngoài theo quy tắc bộ đệm hữu hạn. Tại điểm dừng, giả thuyết cuối quyết định phần chưa chốt. Kết quả là đoạn ngắn có thể chỉ hiện chữ sau lúc nói xong, còn đoạn dài có cơ hội hiện từng cụm trước đó.")])

#par[Độ trễ đến chữ đầu tiên phụ thuộc vào lượng hình đã tích lũy và mức thống nhất giữa các cửa sổ. Sau khi người nói dừng, thời gian đến phụ đề cuối còn gồm khoảng chờ chốt đoạn, lượt giải mã cuối và thời gian truyền kết quả về điện thoại.]

#pagebreak(weak:true)

#heading(level: 1, numbering: none)[#text("7. ")#text("Gợi ý theo câu và giới hạn suy luận")]

#block(above: 4pt, below: 9pt)[#set text(size: 11.4pt, fill: muted);#text("Ở chế độ Kèm gợi ý câu, Gemini 3.1 Flash-Lite xử lý một chuỗi văn bản đã chốt. Nhánh thị giác và nhánh gợi ý tạo ra hai đối tượng có thể đối chiếu theo cùng đoạn.")]

#block(width:100%,breakable:false)[#grid(columns:(1fr,10pt,1fr,10pt,1fr),align:horizon,[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("SO17")]#linebreak()#text(size:9.2pt)[#text("Sinh phụ đề gốc của đoạn")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Gemini")]#linebreak()#text(size:9.2pt)[#text("Nhận văn bản đã chốt")]]],[#align(center+horizon)[→]],[#block(width:100%,fill:shade,inset:6pt)[#set par(justify:false);#text(font:"Calibri",size:9.6pt,weight:"bold",fill:navy)[#text("Giao diện")]#linebreak()#text(size:9.2pt)[#text("Trình bày gợi ý bên dưới")]]])]

#heading(level: 2, numbering: none, outlined: false)[#text("7.1. Điều kiện và ràng buộc sinh")]

#par([#text("PC gửi nội dung câu đến API khi người dùng bật gợi ý. Chỉ dẫn yêu cầu ưu tiên sửa lỗi gần âm và dấu câu, giữ tên riêng, con số, phủ định và ý chính. Nhiệt độ lấy mẫu đặt bằng 0, mức suy luận đặt ở MINIMAL và giới hạn độ dài đầu ra được tính từ độ dài câu. Đây là cấu hình điều khiển sinh văn bản. Việc tuân thủ từng ràng buộc vẫn phụ thuộc phản hồi của mô hình.")])

#heading(level: 2, numbering: none, outlined: false)[#text("7.2. Phần tín hiệu Gemini có thể sử dụng")]

#par([#text("Một kết hợp từ quen thuộc có thể giúp khôi phục cách diễn đạt khi bản gốc chỉ sai nhẹ. Tuy nhiên, hai câu có nghĩa khác nhau đều có thể đúng ngữ pháp và phù hợp với cùng một chuỗi đọc môi sai. Gemini chỉ nhận văn bản đã chọn, nên không thể xem lại vùng miệng hoặc so sánh các ứng viên thị giác đã bị beam search loại bỏ.")])

#heading(level: 2, numbering: none, outlined: false)[#text("7.3. Trường hợp tiếng Việt")]

#par[Chẳng hạn, “tối” và “thôi” có phần vần gần nhau. Góc quay có thể làm mờ dấu hiệu bật hơi; cao độ của thanh điệu cũng không thể quan sát trực tiếp từ môi. Khi phần chữ đầu vào còn mơ hồ, ngữ cảnh có thể khiến mô hình ngôn ngữ chọn một cách diễn đạt khác ý người nói.]

#pagebreak(weak:true)

#heading(level:1,numbering:none)[Tài liệu tham khảo]

#block(above:8pt,below:10pt)[#link("https://arxiv.org/abs/2303.14307")[#strong("1. Ma và cộng sự (2023).") Auto-AVSR: Audio-Visual Speech Recognition with Automatic Labels.]]

#block(above:8pt,below:10pt)[#link("https://arxiv.org/abs/2005.08100")[#strong("2. Gulati và cộng sự (2020).") Conformer: Convolution-augmented Transformer for Speech Recognition.]]

#block(above:8pt,below:10pt)[#link("https://arxiv.org/abs/1609.06773")[#strong("3. Kim, Hori và Watanabe (2017).") Joint CTC-Attention based End-to-End Speech Recognition using Multi-task Learning.]]

#block(above:8pt,below:10pt)[#link("https://aclanthology.org/D18-2012/")[#strong("4. Kudo và Richardson (2018).") SentencePiece: A simple and language independent subword tokenizer and detokenizer for Neural Text Processing.]]
