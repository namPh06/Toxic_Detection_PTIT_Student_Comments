import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out='outputs/assistant_review_20261031';
const ai=JSON.parse(await fs.readFile(out+'/assistant_labels.json','utf8')).rows;
const human=JSON.parse(await fs.readFile(out+'/human_label_audit.json','utf8')).rows;
const manifest=JSON.parse(await fs.readFile('outputs/label_review_20261031/review_manifest.json','utf8'));
const wb=Workbook.create();const tag=v=>v==='toxic'?'t':v==='non-toxic'?'n':'';
const safe=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const humanRows=human.map(r=>[r.comment,'',tag(r.label),tag(r.suggested_label),r.reason,r.context,r.id,r.text_hash,r.source_cell,'Nhãn người dùng; '+r.status]);
const aiRows=ai.map(r=>[r.comment,'','',tag(r.label),r.reason,r.context,r.id,r.text_hash,'Kiem_chung_200!B'+(r.sequence+1),'AI đề xuất; '+r.status]);
const sheets=[['Can_xem_lai',[...humanRows.filter((r,i)=>human[i].status==='needs_confirmation'),...aiRows.filter((r,i)=>ai[i].status==='needs_context')]],['AI_200',aiRows],['Ra_soat_536',humanRows]];
for(const [name,rows]of sheets){const sh=wb.worksheets.add(name);sh.showGridLines=false;const end=rows.length+1;
sh.getRange('A1:J1').values=[['Bình luận','Bạn chốt t/n','Nhãn người dùng','AI đề xuất t/n','Lý do rà soát','Ngữ cảnh có sẵn','Mã bình luận','Hash nội dung','Vị trí nguồn','Nguồn và trạng thái']];
sh.getRange('A2:J'+end).setNumberFormat('@');sh.getRange('A2:J'+end).values=rows.map(r=>r.map(safe));
sh.getRange('A1:J'+end).format.font={name:'Arial',size:11,color:'#243247'};sh.getRange('A1:J'+end).format.wrapText=true;sh.getRange('A1:J'+end).format.verticalAlignment='top';
sh.tables.add('A1:J'+end,true,name+'Table').showFilterButton=true;
sh.getRange('A1:J1').format={fill:'#203864',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:40,wrapText:true};
for(const [col,width]of Object.entries({A:76,B:14,C:17,D:17,E:64,F:64,G:28,H:28,I:28,J:44}))sh.getRange(col+':'+col).format.columnWidth=width;
sh.getRange('B2:B'+end).format.fill='#FFF2CC';sh.getRange('B2:B'+end).dataValidation={rule:{type:'list',values:['t','n']}};
for(let i=0;i<rows.length;i++){const lines=Math.max(...[0,4,5].map(j=>String(rows[i][j]).split('\n').reduce((a,l)=>a+Math.max(1,Math.ceil(l.length/(j===0?69:57))),0)));sh.getRange('A'+(i+2)+':J'+(i+2)).format.rowHeight=Math.min(409,Math.max(65,lines*17+14));}
sh.freezePanes.freezeRows(1);}
const guide=wb.worksheets.add('Huong_dan');guide.showGridLines=false;guide.getRange('A:A').format.columnWidth=28;guide.getRange('B:B').format.columnWidth=112;
const notes=[['Kết quả 31/10/2026','Rà 536 nhãn người dùng và tự đọc 200 câu còn trống. Không phát sinh phí API.'],['200 câu AI','2 toxic; 187 non-toxic; 11 chưa rõ. Cột D là đề xuất AI, không phải nhãn chuẩn người dùng.'],['536 nhãn người dùng','70 toxic; 466 non-toxic. Nhập thêm 60 nhãn thật; giữ nguyên 476 nhãn trước.'],['Cần xem lại','83 nhãn người dùng: 29 đề xuất toxic, 54 chưa đủ căn cứ chốt. Cộng 11 câu AI thiếu ngữ cảnh = 94 dòng trong Can_xem_lai.'],['Cách chốt','Điền cột B tại Can_xem_lai: t=toxic, n=non-toxic. Chưa rõ để trống. Chỉ điền ở một sheet này để tránh nhãn trùng mâu thuẫn.'],['Nếu sửa đề xuất AI khác','Ghi rõ ID và nhãn trong phản hồi; AI_200 giữ nguyên làm hồ sơ đề xuất ban đầu.'],['Câu dài','Hàng dài có thể cần mở rộng chiều cao hoặc đọc toàn văn trên thanh công thức. Không rút gọn dữ liệu gốc.'],['Tiêu chí','ptit-v3.1-school-feedback-20261030. Đọc toàn câu, xác định tác giả đang công kích hay phản đối; phân biệt góp ý có lý do với chê trường.'],['Ngoại lệ đã chốt','36 câu đã được người dùng xử lý riêng được giữ quyết định; không yêu cầu xác nhận lại tự động.'],['Ngữ cảnh','Chỉ dùng cha nối bằng ID cùng bài. Nội dung bài gốc chưa có; không suy quan hệ thân thiết từ emoji.'],['Phạm vi','Đọc ngữ nghĩa 736 câu trong đợt này. 5.111 câu sạch vẫn có nhiều câu chỉ mang dự đoán mô hình; chưa rà ngữ nghĩa hết.'],['Kiểm chứng','Không dùng 200 nhãn AI để công bố độ chính xác; giữ riêng 119 bài khỏi huấn luyện/truy hồi. Không chỉnh mô hình theo các nhãn này.'],['Nguồn','data/progress.json; workspace.json; hai manifest review; QUY_TAC_GAN_NHAN.md. JSON audit cùng thư mục lưu ID, hash, nguồn và lý do.'],['Sau khi chốt','Lưu file rồi báo để đối chiếu ID/hash và nhập riêng các quyết định người dùng. File gốc không bị điền nhãn AI.']];
guide.getRange('A1:B'+notes.length).values=notes;guide.getRange('A1:B'+notes.length).format={font:{name:'Arial',size:11,color:'#243247'},wrapText:true,verticalAlignment:'center'};guide.getRange('A1:B1').format.fill='#203864';guide.getRange('A1:B1').format.font.color='#FFFFFF';guide.getRange('A:A').format.font.bold=true;
for(let i=0;i<notes.length;i++)guide.getRange('A'+(i+1)+':B'+(i+1)).format.rowHeight=Math.max(44,Math.ceil(notes[i][1].length/100)*18+14);
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'Can_xem_lai!A1:E3',include:'values,formulas',tableMaxRows:3,tableMaxCols:5,maxChars:1600})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
for(const [name,range]of [['Can_xem_lai','A1:F4'],['AI_200','A1:F4'],['Ra_soat_536','A1:F4'],['Huong_dan','A1:B14']]){const img=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(out+'/'+name+'_preview.png',new Uint8Array(await img.arrayBuffer()));}
await(await SpreadsheetFile.exportXlsx(wb)).save(out+'/Ket_qua_gan_nhan_va_ra_soat.xlsx');console.log('Saved workbook');
