import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out='outputs/remaining_semantic_review_20261031';
const ai=JSON.parse(await fs.readFile(out+'/assistant_labels.json','utf8')).rows;
const queue=JSON.parse(await fs.readFile(out+'/review_queue.json','utf8')).rows;
const wb=Workbook.create();const text=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const tag=v=>v==='toxic'?'t':v==='non-toxic'?'n':'';
for(const [name,rows]of [['Can_bo_sung_435',queue],['AI_4275',ai]]){
 const sh=wb.worksheets.add(name);sh.showGridLines=false;const end=rows.length+1;
 sh.getRange('A1:J1').values=[['Bình luận','Bạn chốt t/n','Ngữ cảnh có sẵn','Giải thích của bạn','Mã bình luận','Hash nội dung','AI đề xuất t/n','Lý do của AI','Mã bài viết','Mã bình luận gốc']];
 sh.getRange('A2:J'+end).setNumberFormat('@');
 sh.getRange('A2:J'+end).values=rows.map(r=>[text(r.comment),'',text(r.context),'',r.id,r.text_hash,tag(r.label),text(r.reason),String(r.post_id),String(r.comment_id)]);
 sh.getRange('A1:J'+end).format.font={name:'Arial',size:11,color:'#243247'};sh.getRange('A1:J'+end).format.wrapText=true;sh.getRange('A1:J'+end).format.verticalAlignment='top';
 sh.tables.add('A1:J'+end,true,name+'Table').showFilterButton=true;
 sh.getRange('A1:J1').format={fill:'#203864',font:{name:'Arial',size:11,color:'#FFFFFF',bold:true},wrapText:true,rowHeight:36};
 for(const [col,width]of Object.entries({A:76,B:14,C:66,D:44,E:28,F:28,G:17,H:66,I:25,J:30}))sh.getRange(col+':'+col).format.columnWidth=width;
 sh.getRange('B2:B'+end).dataValidation={rule:{type:'list',values:['t','n']}};sh.getRange('B2:B'+end).format.fill='#FFF2CC';sh.getRange('D2:D'+end).format.fill='#FFF8E7';
 for(let i=0;i<rows.length;i++){const lines=Math.max(...[[rows[i].comment,68],[rows[i].context,58],[rows[i].reason,58]].map(([t,w])=>String(t).split('\n').reduce((a,l)=>a+Math.max(1,Math.ceil(l.length/w)),0)));sh.getRange('A'+(i+2)+':J'+(i+2)).format.rowHeight=Math.min(409,Math.max(68,lines*17+14));}
 sh.freezePanes.freezeRows(1);
}
const guide=wb.worksheets.add('Huong_dan');guide.showGridLines=false;guide.getRange('A:A').format.columnWidth=28;guide.getRange('B:B').format.columnWidth=106;
const notes=[['Rà soát 31/10/2026','Đã đọc hết 4.275 câu còn lại; toàn bộ 5.111 câu sạch đã được đọc qua các lượt.'],['Kết quả AI','104 toxic, 3.755 non-toxic, 416 chưa đủ ngữ cảnh. Đây là đề xuất AI, chưa phải nhãn chuẩn người dùng.'],['Can_bo_sung_435','416 câu mới cần ngữ cảnh + 19 câu chờ từ lượt trước. Chỉ điền khi đủ căn cứ; có thể giữ trống.'],['Cách điền','Cột A là bình luận. Cột B: t=toxic, n=non-toxic. Cột C là ngữ cảnh có sẵn. Cột D để giải thích hoặc bổ sung quan hệ bạn bè.'],['AI_4275','Toàn bộ quyết định và lý do lượt này. Nếu sửa câu đã có tại Can_bo_sung_435, chỉ điền ở sheet hàng chờ để tránh mâu thuẫn.'],['Ngữ cảnh','Chỉ dùng bình luận cha nối đúng ID cùng bài. Chưa có nội dung bài gốc. Không suy quan hệ bạn bè từ emoji hay lời đùa thôi.'],['Nguồn','data/progress.json; QUY_TAC_GAN_NHAN.md v3.2; các JSON cùng thư mục giữ ID, hash và nguồn quyết định.'],['Giữ nhãn người dùng','Không ghi đè workspace, không đưa đề xuất AI vào bộ nhãn chuẩn. 535 nhãn người dùng đủ điều kiện vẫn giữ nguyên.'],['Độ chính xác','111 trường hợp bất đồng với dự đoán máy cũ không phải 111 lỗi đã xác nhận. Không đo độ chính xác bằng đề xuất AI này.'],['Tiếp theo','Bổ sung ngữ cảnh cho hàng chờ khi bạn biết. Chưa huấn luyện hoặc thay mô hình; không phát sinh phí dịch vụ.']];
guide.getRange('A1:B'+notes.length).values=notes;guide.getRange('A1:B'+notes.length).format={font:{name:'Arial',size:11,color:'#243247'},wrapText:true,verticalAlignment:'center'};guide.getRange('A1:B1').format.fill='#203864';guide.getRange('A1:B1').format.font.color='#FFFFFF';guide.getRange('A:A').format.font.bold=true;
for(let i=0;i<notes.length;i++)guide.getRange('A'+(i+1)+':B'+(i+1)).format.rowHeight=Math.max(45,Math.ceil(notes[i][1].length/96)*18+16);
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'Can_bo_sung_435!A1:D3',include:'values,formulas',tableMaxRows:3,tableMaxCols:4,maxChars:1300})).ndjson);console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:10},maxChars:500})).ndjson);
for(const [name,range]of [['Can_bo_sung_435','A1:D5'],['AI_4275','A1:D5'],['Huong_dan','A1:B10']]){const img=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(out+'/'+name+'_preview.png',new Uint8Array(await img.arrayBuffer()));}
await(await SpreadsheetFile.exportXlsx(wb)).save(out+'/Ra_soat_4275_cau.xlsx');console.log('Exported');
