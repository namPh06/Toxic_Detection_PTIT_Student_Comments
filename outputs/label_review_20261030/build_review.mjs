import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out='outputs/label_review_20261030';
const data=JSON.parse(await fs.readFile(out+'/review_manifest.json','utf8'));
const wb=Workbook.create();
for(const [name,rows] of [['Can_duyet',data.priority],['Chua_xac_nhan',data.others]]){
 const sh=wb.worksheets.add(name); sh.showGridLines=false;
 const n=rows.length+1;
 sh.getRange('A1:F1').values=[['Bình luận','Nhãn (t/n)','Ngữ cảnh để đối chiếu','Lý do đưa vào danh sách','Mã bình luận','Mã kiểm tra nội dung']];
 sh.getRange('A2:F'+n).setNumberFormat('@');
 sh.getRange('A2:F'+n).values=rows.map(r=>[r.comment.startsWith('=')?"'"+r.comment:r.comment,'',r.context,r.reason,r.id,r.text_hash]);
 sh.getRange('A1:F'+n).format.font={name:'Arial',size:11,color:'#172B4D'};
 sh.getRange('A1:F1').format={fill:'#203864',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:34,wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
 sh.getRange('A2:F'+n).format.wrapText=true;
 sh.getRange('A2:F'+n).format.verticalAlignment='top';
 sh.getRange('A:A').format.columnWidth=100;
 sh.getRange('B:B').format.columnWidth=16;
 sh.getRange('C:C').format.columnWidth=85;
 sh.getRange('D:D').format.columnWidth=36;
 sh.getRange('E:F').format.columnWidth=26;
 sh.getRange('B2:B'+n).format.fill='#FFF2CC';
 sh.getRange('B2:B'+n).format.horizontalAlignment='center';
 sh.getRange('B2:B'+n).dataValidation={rule:{type:'list',values:['t','n']}};
 sh.getRange('B2:B'+n).conditionalFormats.add('cellIs',{operator:'equal',formula:'"t"',format:{fill:'#FCE4D6'}});
 sh.getRange('B2:B'+n).conditionalFormats.add('cellIs',{operator:'equal',formula:'"n"',format:{fill:'#E2F0D9'}});
 for(let i=0;i<rows.length;i++){
  const lines=Math.max(Math.ceil(rows[i].comment.length/90),rows[i].comment.split('\n').length,Math.ceil(rows[i].context.length/75)+rows[i].context.split('\n').length,Math.ceil(rows[i].reason.length/32));
  sh.getRange('A'+(i+2)+':F'+(i+2)).format.rowHeight=Math.min(409,Math.max(48,lines*17+12));
 }
 const table=sh.tables.add('A1:F'+n,true,name==='Can_duyet'?'CanDuyetTable':'ChuaXacNhanTable');table.showFilterButton=true;
 sh.freezePanes.freezeRows(1);sh.tabColor=name==='Can_duyet'?'#203864':'#6B7C93';
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Can_duyet!A1:B4',include:'values,formulas',tableMaxRows:4,tableMaxCols:2})).ndjson);
for(const name of ['Can_duyet','Chua_xac_nhan']){
 const image=await wb.render({sheetName:name,range:'A1:D5',scale:1,format:'png'});
 await fs.writeFile(out+'/'+name+'_preview.png',new Uint8Array(await image.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(out+'/Binh_luan_can_gan_nhan.xlsx');
console.log('Exported workbook');
