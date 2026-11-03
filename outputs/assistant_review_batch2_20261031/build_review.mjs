import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out='outputs/assistant_review_batch2_20261031';
const ai=JSON.parse(await fs.readFile(out+'/assistant_labels.json','utf8')).rows;
const queue=JSON.parse(await fs.readFile(out+'/review_queue.json','utf8')).rows;
const wb=Workbook.create();const text=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const tag=v=>v==='toxic'?'t':v==='non-toxic'?'n':'';
for(const [name,rows]of [['Can_duyet_19',queue],['AI_100',ai]]){
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
const notes=[['Duyệt tiếp 31/10/2026','19 câu: 18 câu mới cần ngữ cảnh và 1 câu chưa chốt ở lượt trước.'],['Làm ở Can_duyet_19','Đọc A và C, điền B: t=toxic, n=non-toxic. Chưa đủ căn cứ thì để trống. Ghi giải thích ở D.'],['Đùa thân mật','Nếu bạn biết rõ là bạn bè trêu nhau và cùng hưởng ứng, ghi điều đó ở D. Không suy từ emoji hoặc xưng hô mày–tao.'],['AI_100','100 đề xuất mới: 2 toxic, 80 non-toxic, 18 chưa rõ. Tất cả do AI đọc trong phiên này, chưa phải nhãn người dùng.'],['Muốn sửa đề xuất AI','Có thể điền B và D tại AI_100 cho câu không thuộc Can_duyet_19. Với 18 câu trùng, chỉ chốt ở Can_duyet_19 để tránh mâu thuẫn.'],['Ngữ cảnh','Chỉ có bình luận cha nối bằng ID cùng bài; bài gốc chưa được thu thập. Có câu cha không đồng nghĩa biết hai người là bạn.'],['Bộ nhãn phát triển','535 nhãn người dùng đủ điều kiện: 85 toxic, 450 non-toxic. 1 nhãn lịch sử đang chờ bị loại khỏi huấn luyện.'],['Kiểm chứng','Giữ riêng các bài kiểm chứng. Không đo độ chính xác bằng nhãn do AI tự tạo. Chưa huấn luyện hay triển khai mô hình mới.'],['Phạm vi','Đã đọc thêm 100 câu theo thứ tự manifest cũ; đây không phải mẫu ngẫu nhiên để đánh giá. Tổng 836 câu đã được đọc trong hai lượt; còn 4.275 câu sạch chưa rà ngữ nghĩa.'],['Nguồn','data/progress.json; manifest đợt 30/10; QUY_TAC_GAN_NHAN.md v3.2. JSON cùng thư mục giữ ID/hash/nguồn.'],['Sau khi điền','Lưu file rồi báo đã chốt. File Excel cũ và các nhãn người dùng không bị thay đổi trong lượt này.']];
guide.getRange('A1:B'+notes.length).values=notes;guide.getRange('A1:B'+notes.length).format={font:{name:'Arial',size:11,color:'#243247'},wrapText:true,verticalAlignment:'center'};guide.getRange('A1:B1').format.fill='#203864';guide.getRange('A1:B1').format.font.color='#FFFFFF';guide.getRange('A:A').format.font.bold=true;
for(let i=0;i<notes.length;i++)guide.getRange('A'+(i+1)+':B'+(i+1)).format.rowHeight=Math.max(45,Math.ceil(notes[i][1].length/96)*18+16);
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'Can_duyet_19!A1:D3',include:'values,formulas',tableMaxRows:3,tableMaxCols:4,maxChars:1300})).ndjson);console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:10},maxChars:500})).ndjson);
for(const [name,range]of [['Can_duyet_19','A1:D5'],['AI_100','A1:D5'],['Huong_dan','A1:B11']]){const img=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(out+'/'+name+'_preview.png',new Uint8Array(await img.arrayBuffer()));}
await(await SpreadsheetFile.exportXlsx(wb)).save(out+'/Duyet_tiep_19_cau.xlsx');console.log('Exported');
