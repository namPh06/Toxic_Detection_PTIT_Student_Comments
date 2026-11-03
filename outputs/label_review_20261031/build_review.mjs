import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out='outputs/label_review_20261031';
const data=JSON.parse(await fs.readFile(out+'/review_manifest.json','utf8'));
const wb=Workbook.create();
const text=v=>String(v??'').startsWith('=')?"'"+v:String(v??'');
const wrappedLines=(v,width)=>String(v).split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/width)),0);
for(const [name,rows] of [['Bo_sung_60',data.priority],['Kiem_chung_200',data.others]]){
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 const n=rows.length+1;
 sh.getRange('A1:G1').values=[['Bình luận','Nhãn (t/n)','Ngữ cảnh có sẵn','Ghi chú khi chưa rõ','Mã bình luận','Mã kiểm tra nội dung','Bài viết gốc']];
 sh.getRange('A2:G'+n).setNumberFormat('@');
 sh.getRange('A2:G'+n).values=rows.map(r=>[text(r.comment),'',text(r.context),'',r.id,r.text_hash,text(r.post_url)]);
 sh.getRange('A1:G'+n).format.font={name:'Arial',size:11,color:'#243247'};
 sh.getRange('A2:G'+n).format.wrapText=true;
 sh.getRange('A2:G'+n).format.verticalAlignment='top';
 const table=sh.tables.add('A1:G'+n,true,name==='Bo_sung_60'?'BoSungTable':'KiemChungTable');table.showFilterButton=true;
 sh.getRange('A1:G1').format={fill:'#203864',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:34,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
 sh.getRange('A:A').format.columnWidth=82;
 sh.getRange('B:B').format.columnWidth=13;
 sh.getRange('C:C').format.columnWidth=68;
 sh.getRange('D:D').format.columnWidth=32;
 sh.getRange('E:E').format.columnWidth=27;
 sh.getRange('F:F').format.columnWidth=23;
 sh.getRange('G:G').format.columnWidth=35;
 sh.getRange('B2:B'+n).format.fill='#FFF2CC';sh.getRange('D2:D'+n).format.fill='#FFF8E7';
 sh.getRange('B2:B'+n).format.horizontalAlignment='center';
 sh.getRange('E2:G'+n).format.font.color='#66758A';
 sh.getRange('B2:B'+n).dataValidation={rule:{type:'list',values:['t','n']}};
 sh.getRange('B2:B'+n).conditionalFormats.add('cellIs',{operator:'equal',formula:'"t"',format:{fill:'#FCE4D6'}});
 sh.getRange('B2:B'+n).conditionalFormats.add('cellIs',{operator:'equal',formula:'"n"',format:{fill:'#E2F0D9'}});
 for(let i=0;i<rows.length;i++){
  const lines=Math.max(wrappedLines(rows[i].comment,75),wrappedLines(rows[i].context,61));
  sh.getRange('A'+(i+2)+':G'+(i+2)).format.rowHeight=Math.min(409,Math.max(58,lines*17+14));
 }
 sh.freezePanes.freezeRows(1);sh.tabColor=name==='Bo_sung_60'?'#203864':'#52739D';
}
const guide=wb.worksheets.add('Huong_dan');guide.showGridLines=false;
guide.getRange('A1:B20').format.font={name:'Arial',size:11,color:'#243247'};
guide.getRange('A:A').format.columnWidth=25;guide.getRange('B:B').format.columnWidth=112;
guide.getRange('A2').values=[['Gán nhãn đợt 2']];guide.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#203864'};
const notes=[
 ['Làm trước','Mở Bo_sung_60, đọc cột A và ngữ cảnh cột C, rồi nhập nhãn vào cột B.'],
 ['Cách nhập','t = toxic; n = non-toxic. Chưa rõ thì để B trống và ghi lý do ở D. Không tự coi ô trống là n.'],
 ['Làm tiếp','Điền Kiem_chung_200 theo cùng cách. Nhóm này được giữ riêng để kiểm chứng, không dùng huấn luyện.'],
 ['Ngữ cảnh','Chỉ có bình luận cha được liên kết trong dữ liệu. Nội dung bài viết chưa được thu thập. Có thể mở bài viết gốc ở cột G nếu truy cập được.'],
 ['Giữ nguyên','Không sửa A, C, E, F, G hoặc chuyển câu giữa các sheet. Cột D dành cho giải thích, nhất là câu mỉa mai hoặc thiếu ngữ cảnh.'],
 ['Đọc câu dài','Nếu hàng chưa hiển thị hết nội dung, chọn ô rồi đọc đầy đủ trên thanh công thức hoặc mở rộng chiều cao hàng.'],
 ['Toxic','Công kích, hạ nhục, quấy rối, kỳ thị, đe dọa; hoặc chính người viết chê trường theo tiêu chí đề tài.'],
 ['Non-toxic','Hỏi đáp, thông tin, trao đổi; phản đối lời xúc phạm hoặc yêu cầu dừng khi không kèm công kích khác.'],
 ['Góp ý về trường','Phân biệt góp ý nêu bất tiện và lý do cụ thể với chê bai. Có lý do không tự động khiến mọi lời chê thành non-toxic.'],
 ['Từ tục và đùa','Từ tục, emoji hoặc từ “đừng” riêng lẻ không quyết định nhãn. Không tự suy ra quan hệ thân thiết hay mục đích mỉa mai.'],
 ['Khi khó quyết định','Đọc toàn câu và ngữ cảnh. Thiếu thông tin thì để trống, ghi rõ chỗ còn thiếu ở D; không ép thành t hoặc n.'],
 ['Sau khi điền','Lưu và đóng file, rồi báo đã gán nhãn. Có thể làm xong Bo_sung_60 trước và báo để tiếp tục cải tiến.'],
 ['Nguồn','Bình luận và quan hệ trả lời từ dữ liệu crawl của đề tài. Tiêu chí ptit-v3.1-school-feedback-20261030.'],
 ['Phạm vi kiểm chứng','200 câu được lấy ngẫu nhiên từ 1.026 câu thuộc 217 bài chưa có nhãn người dùng. Không đại diện cho toàn bộ 5.111 câu.']
];
guide.getRange('A4:B'+(notes.length+3)).values=notes;
guide.getRange('A4:A'+(notes.length+3)).format.font.bold=true;
guide.getRange('A4:B'+(notes.length+3)).format.wrapText=true;
guide.getRange('A4:B'+(notes.length+3)).format.verticalAlignment='center';
for(let i=0;i<notes.length;i++)guide.getRange('A'+(i+4)+':B'+(i+4)).format.rowHeight=Math.max(38,wrappedLines(notes[i][1],103)*17+14);
guide.tabColor='#8593A5';
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Bo_sung_60!A1:D3',include:'values,formulas',tableMaxRows:3,tableMaxCols:4,maxChars:2600})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},summary:'formula error scan',maxChars:1000})).ndjson);
for(const [name,range] of [['Bo_sung_60','A1:D5'],['Kiem_chung_200','A1:D5'],['Huong_dan','A1:B17']]){
 const image=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(out+'/'+name+'_preview.png',new Uint8Array(await image.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(out+'/Gan_nhan_bo_sung_va_kiem_chung.xlsx');
console.log('Exported 60 development + 200 validation rows, all labels blank.');
