'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Number(value || 0).toLocaleString('vi-VN');
const qualityNames = {ready:'Mẫu sạch',duplicate:'Bản trùng',conflict:'Nhãn mâu thuẫn',incomplete:'Chưa mở hết nội dung',empty_or_ui:'Rỗng / giao diện',excluded:'Đã loại'};
let currentTab = 'overview', page = 1, datasetRequest = 0, lastStatus = null, toastTimer, reviewSaving = false;
const reviewDrafts = new Map();
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!response.ok) {
    const text = await response.text();
    let message; try {message = JSON.parse(text).error;} catch {message = text;}
    throw Error(message || `Yêu cầu thất bại (${response.status})`);
  }
  return response.json();
}
function toast(message, error=false) {
  clearTimeout(toastTimer);
  if(error&&/Traceback|Stacktrace|DevTools|Session info|https?:\/\/|\.onnx\b/i.test(message)){
    $('toast').innerHTML=`Không thể hoàn tất thao tác. Xem chi tiết để kiểm tra, rồi thử lại.<details><summary>Chi tiết lỗi</summary><pre>${esc(message)}</pre></details>`;
  }else $('toast').textContent=message;
  $('toast').classList.toggle('error',error); $('toast').hidden=false;
  toastTimer=setTimeout(()=>$('toast').hidden=true,error?10000:4500);
}
async function action(button, fn) {
  button.disabled=true;
  try {await fn();} catch(error) {toast(error.message,true);} finally {
    button.disabled=false;
    if(button.id==='train'&&lastStatus)button.disabled=lastStatus.job.running||lastStatus.annotation_job?.running||lastStatus.dataset_health?.training_ready===false;
    if(['auto-suggest','auto-label-all'].includes(button.id))button.disabled=!!(lastStatus?.annotation_job?.running||lastStatus?.job.running);
    if(button.id.startsWith('dataset-'))button.disabled=!lastStatus?.dataset_health?.reviewed;
    if(button.id.startsWith('auto-dataset-'))button.disabled=!lastStatus?.summary?.labeled;
  }
}
function navigate() {
  const name=location.hash.slice(1)||'overview';
  currentTab=['overview','crawl','data','models','report'].includes(name)?name:'overview';
  document.querySelectorAll('.view').forEach(view=>view.hidden=view.id!==currentTab);
  document.querySelectorAll('[data-tab]').forEach(link=>{const active=link.dataset.tab===currentTab;link.classList.toggle('active',active);if(active){link.setAttribute('aria-current','page');$('breadcrumb').textContent=link.getAttribute('aria-label');}else link.removeAttribute('aria-current');});
  if(currentTab==='data') loadRows();
  if(currentTab==='report') loadReport();
}
window.addEventListener('hashchange',navigate);
document.querySelector('.skip-link').addEventListener('click',event=>{event.preventDefault();$('main-content').focus();});
function bars(items, max) {
  return items.map(([name,value,color])=>`<div><div class="bar-head"><span>${esc(name)}</span><b>${number(value)}</b></div><div class="bar-track"><div class="bar-fill" style="width:${Math.min(100,100*value/Math.max(1,max))}%;background:${color||'#536b82'}"></div></div></div>`).join('');
}
function renderStatus(status) {
  const completed=lastStatus?.annotation_job?.running&&lastStatus.annotation_job.automatic&&!status.annotation_job?.running;
  lastStatus=status;
  updateReviewActions();
  const s=status.summary, result=status.result;
  $('total').textContent=number(s.total);$('usable').textContent=number(s.usable);$('labeled').textContent=number(s.labeled);
  $('post-count').textContent=`Từ ${number(s.posts)} bài viết`;
  $('label-percent').textContent=`${s.usable?(100*s.labeled/s.usable).toFixed(1):0}% mẫu sạch đã có nhãn`;
  $('model-count').innerHTML=`${result?result.models.length:0}<small> / 5</small>`;
  $('step-crawl').textContent=s.total?'Đã có dữ liệu':'Chờ thu thập';
  $('step-label').textContent=`${number(s.labeled)} / ${number(s.usable)} mẫu`;
  $('step-model').textContent=status.job.running?'Đang huấn luyện':result?'Đã huấn luyện':status.dataset_health?.training_ready?'Sẵn sàng huấn luyện':'Chờ dữ liệu có nhãn';
  $('step-report').textContent=result?'Đã có kết quả':'Chưa có thực nghiệm';
  const non=s.labels['non-toxic']||0,toxic=s.labels.toxic||0,unlabeled=s.labels.unlabeled||0,total=Math.max(1,s.usable);
  $('donut-total').textContent=number(s.usable);
  $('donut').style.background=`conic-gradient(#536b82 0 ${non/total*100}%,#ae263b ${non/total*100}% ${(non+toxic)/total*100}%,#e1e4e9 ${(non+toxic)/total*100}% 100%)`;
  $('donut').setAttribute('aria-label',`Non-toxic ${non}, toxic ${toxic}, chưa gán ${unlabeled}`);
  $('label-legend').innerHTML=[['Non-toxic',non,'#536b82'],['Toxic',toxic,'#ae263b'],['Chưa gán nhãn',unlabeled,'#e1e4e9']].map(([name,n,color])=>`<div class="legend-row"><span class="swatch" style="background:${color}"></span>${name}<b>${number(n)}</b></div>`).join('');
  $('quality-bars').innerHTML=bars(Object.entries(qualityNames).map(([key,name])=>[name,s.quality[key]||0,key==='ready'?'#536b82':'#7b8593']),s.total);
  $('quality-note').textContent=`${number(s.total-s.usable)} mẫu ngoài dataset sạch · Bản gốc được giữ nguyên`;
  $('next-action').textContent=s.labeled===0?'Bấm “Làm sạch & gán nhãn toàn bộ” để xử lý tất cả mẫu hợp lệ trong một lần.':`Đã có ${number(s.labeled)} mẫu có nhãn; còn ${number(unlabeled)} mẫu sạch chưa gán. Có thể tải dataset hoặc chạy thực nghiệm.`;
  const health=status.dataset_health,annotationJob=status.annotation_job;
  $('training-status').textContent=status.job.error?'Huấn luyện gặp lỗi. Xem chi tiết bên dưới và thử lại.':!status.job.running&&health?.training_ready===false?health.training_message:status.job.message;
  $('training-detail').hidden=!status.job.error;$('training-debug').textContent=status.job.error?status.job.message:'';
  $('train').disabled=status.job.running||annotationJob?.running||health?.training_ready===false;
  $('train').textContent=status.job.running?'Đang huấn luyện…':'Huấn luyện 5 cấu hình';
  $('stale-warning').hidden=!status.stale;
  $('automatic-training-warning').hidden=!(health?.automatic||result?.summary?.label_sources?.automatic);
  $('model-empty').hidden=!!result;$('model-results').hidden=!result;$('predict-button').disabled=!result||status.job.running;
  $('report-state').textContent=result?(status.stale?'Có kết quả, dữ liệu đã thay đổi':'Đã có kết quả thực nghiệm'):(s.labeled?'Dataset đã có nhãn, chờ huấn luyện':'Đã có phần phương pháp, đang chờ dataset');
  $('report-description').textContent=result?'Báo cáo gồm bảng chỉ số, so sánh đặc trưng/thuật toán và confusion matrix từ lần huấn luyện gần nhất.':'Báo cáo hiện có thống kê bộ dữ liệu và cơ sở lý thuyết. Phần chỉ số sẽ được bổ sung sau khi bạn gán nhãn và chạy huấn luyện.';
  $('auto-suggest').disabled=!!(annotationJob?.running||status.job.running);
  $('auto-label-all').disabled=$('auto-suggest').disabled;
  $('auto-label-all').textContent=annotationJob?.running&&annotationJob.automatic?'Đang xử lý toàn bộ…':'Làm sạch & gán nhãn toàn bộ';
  $('auto-suggest').textContent=annotationJob?.running?'Đang tạo gợi ý…':'Tạo gợi ý tự động';
  $('annotation-status').textContent=annotationJob?.error?'Có lỗi trong bước xử lý. Mở “Chi tiết xử lý dữ liệu” bên dưới để kiểm tra.':annotationJob?.running&&annotationJob.message?.startsWith('Đang tải')?'Đang tải mô hình lần đầu. Vui lòng giữ ứng dụng mở.':!annotationJob?.running&&s.usable>0&&s.labeled===s.usable?`Đã gán nhãn ${number(s.labeled)} mẫu sạch. Bạn có thể tải dataset ngay.`:annotationJob?.message||'Sẵn sàng xử lý dữ liệu.';
  $('annotation-debug').textContent=annotationJob?.message||'';
  $('annotation-status').classList.toggle('annotation-error',!!annotationJob?.error);
  $('dataset-health').innerHTML=health?[[s.labeled,'mẫu đã có nhãn'],[health.automatic,'nhãn tự động'],[health.reviewed,'nhãn đã duyệt'],[health.needs_review,'nhãn máy cần kiểm tra']].map(([n,label],i)=>`<div><strong class="${i===3?'review-count':''}">${number(n)}</strong><span>${label}</span></div>`).join(''):'Chưa kiểm tra được dataset.';
  $('dataset-details').textContent=health?`${number(s.labeled)} / ${number(s.usable)} mẫu sạch đã có nhãn. ${number(s.total-s.usable)} mẫu ngoài dataset sạch. Gợi ý chưa lưu nhãn: ${number(health.suggested)}; chưa rõ: ${number(health.abstained)}. ${number(health.unknown_completeness)} bình luận chưa xác nhận độ đầy đủ. Trung bình ${s.avg_tokens} token/mẫu sạch.`:'';
  $('dataset-csv').disabled=$('dataset-json').disabled=!health?.reviewed;
  $('auto-dataset-csv').disabled=$('auto-dataset-json').disabled=!s.labeled;
  if(completed&&currentTab==='data'){
    if(reviewDrafts.size)toast('Đã xử lý toàn bộ. Bấm “Cập nhật danh sách” sau khi lưu phần bạn đang sửa.');
    else loadRows();
  }
  if(result) renderResults(result);
}
function renderResults(result) {
  const names=result.models.map(m=>m.name);
  if($('matrix-model').dataset.run!==result.created_at){$('matrix-model').innerHTML=names.map(n=>`<option>${esc(n)}</option>`).join('');$('matrix-model').value=result.selected_model;$('matrix-model').dataset.run=result.created_at;}
  $('split-info').textContent=`Train ${result.split.train.count} · Validation ${result.split.validation.count} · Test ${result.split.test.count} mẫu. Chọn: ${result.selected_model}.`;
  $('metrics-rows').innerHTML=result.models.map(m=>`<tr><td class="${m.name===result.selected_model?'selected-model':''}">${esc(m.name)}${m.name===result.selected_model?' ★':''}</td><td>${m.validation.f1_macro.toFixed(3)}</td>${['accuracy','precision','recall','f1','f1_macro'].map(k=>`<td>${m.test[k].toFixed(3)}</td>`).join('')}<td>${m.seconds.toFixed(1)}s</td></tr>`).join('');
  $('score-bars').innerHTML=result.models.map(m=>`<div><div class="bar-head"><span>${esc(m.name)}</span><b>${m.test.f1_macro.toFixed(3)}</b></div><div class="bar-track"><div class="bar-fill" style="width:${100*m.test.f1_macro}%"></div></div></div>`).join('');
  renderMatrix();
}
function renderMatrix(){
  const model=lastStatus?.result?.models.find(m=>m.name===$('matrix-model').value);if(!model)return;
  const matrix=model.test.confusion_matrix;
  $('matrix').innerHTML=`<table class="matrix-table"><thead><tr><th>Nhãn dataset ↓ / Dự đoán →</th><th>Non-toxic</th><th>Toxic</th></tr></thead><tbody><tr><th>Non-toxic</th><td>${matrix[0][0]}</td><td class="off">${matrix[0][1]}</td></tr><tr><th>Toxic</th><td class="off">${matrix[1][0]}</td><td>${matrix[1][1]}</td></tr></tbody></table>`;
}
$('matrix-model').addEventListener('change',renderMatrix);
async function refresh() {
  const results=await Promise.allSettled([api('/api/status'),api('/status')]);
  if(results[0].status==='fulfilled') renderStatus(results[0].value);
   else {$('training-status').textContent='Mất kết nối máy chủ. Kiểm tra cửa sổ MO_CONG_CU.cmd.';['train','auto-suggest','auto-label-all','dataset-csv','dataset-json','auto-dataset-csv','auto-dataset-json'].forEach(id=>$(id).disabled=true);}
  if(results[1].status==='fulfilled') renderCrawler(results[1].value);
  else {
    $('crawl-phase').textContent='Mất kết nối';
    $('crawl-message').textContent='Mất kết nối máy chủ. Chạy lại MO_CONG_CU.cmd và giữ cửa sổ đó mở. Trang sẽ tự kết nối lại.';
    $('crawl-message').classList.add('annotation-error');$('crawl-detail').hidden=true;
    ['browser-open','start','stop'].forEach(id=>$(id).disabled=true);
  }
  setTimeout(refresh,3000);
}
const reasons={no_progress:'Không có tiến triển sau 5 lượt',time_limit:'Đạt giới hạn 3 phút',unrecognized_scope:'Không nhận diện vùng bình luận',unrecognized_scroll:'Không nhận diện vùng cuộn',user_stop:'Dừng theo yêu cầu',dataset_limit:'Đạt giới hạn dữ liệu',crawl_error:'Lỗi khi thu thập bài'};
function renderCrawler(s){
  $('crawl-message').textContent=s.phase==='error'?(s.ready?'Thu thập gặp lỗi. Dữ liệu đã đọc vẫn được giữ trong phiên. Bạn có thể tải bản sao và thử lại.':'Chưa kết nối được với Chrome. Bấm “Mở Chrome thu thập” để thử lại.'):s.message;
  $('crawl-message').classList.toggle('annotation-error',s.phase==='error');
  $('crawl-detail').hidden=s.phase!=='error';$('crawl-debug').textContent=s.phase==='error'?s.message:'';
  $('crawl-posts').textContent=number(s.posts);$('crawl-comments').textContent=number(s.comments);
  $('crawl-phase').textContent=({idle:'Chưa mở Chrome',opening:'Đang mở Chrome',ready:'Sẵn sàng',discovering:'Đang tìm bài',collecting:'Đang thu thập',error:'Cần kiểm tra'})[s.phase]||s.phase;
  $('crawl-progress').max=s.target;$('crawl-progress').value=Math.min(s.posts,s.target);
  $('crawl-source').textContent=s.source?`Nguồn: ${s.source}`:'Chưa chọn nguồn thu thập';
  $('browser-open').disabled=s.ready||s.phase==='opening';$('start').disabled=!s.ready||s.running;$('stop').disabled=!s.running;$('target').disabled=s.running;$('source-url').disabled=s.running;
  const body=$('crawl-results'),scroll=body.closest('.table-scroll');
  const html=s.results.length?s.results.map(r=>`<tr><td>${esc(r.post_id)}</td><td>${number(r.count)}</td><td>${esc(reasons[r.reason]||r.reason)}${r.error?`<details class="row-detail"><summary>Chi tiết lỗi</summary><p class="row-meta">${esc(r.error)}</p></details>`:''}</td><td>Chưa xác nhận</td></tr>`).join(''):'<tr><td colspan="4" class="no-rows">Chưa có nhật ký. Kết quả từng bài sẽ xuất hiện sau khi thu thập.</td></tr>';
  if(body.innerHTML!==html){
    const {scrollTop,scrollLeft}=scroll;
    body.innerHTML=html;scroll.scrollTop=scrollTop;scroll.scrollLeft=scrollLeft;
  }
}
function suggestionHTML(row){
  if(row.label_source==='automatic')return `<div class="label-suggestion"><b>Nhãn tự động đã lưu: ${esc(row.label)}</b><p>Chưa được người đọc xác nhận. Chỉ cần lưu lại nếu bạn chỉnh sửa.</p>${row.needs_review?`<p class="annotation-error">Cần kiểm tra: ${row.review_reason==='truncated'?'văn bản quá dài, mô hình chỉ đọc một phần':'điểm nằm trong vùng chưa rõ'}.</p>`:''}<details class="row-detail"><summary>Thông tin nhãn</summary><p>Điểm toxic: ${typeof row.model_score==='number'?row.model_score.toFixed(3):'—'} · Ngưỡng ${esc(row.label_threshold)}</p><small>${esc(row.label_model)} · ${esc(String(row.label_revision||'').slice(0,12))}</small></details></div>`;
  const suggestion=row.suggestion;if(!suggestion)return '';
  const label=['toxic','non-toxic'].includes(suggestion.suggested_label)?suggestion.suggested_label:'';
  const score=typeof suggestion.model_score==='number'&&Number.isFinite(suggestion.model_score)?suggestion.model_score.toFixed(3):'không có';
  return `<div class="label-suggestion"><b>${label?`Gợi ý: ${esc(label)}`:'Chưa đề xuất nhãn'}</b><p>Điểm toxic: ${score} · Không phải độ chính xác.</p>${suggestion.truncated?'<p class="annotation-error">Mô hình chỉ đọc một phần văn bản dài; cần xem toàn bộ bình luận.</p>':''}${!label?'<p>Cần bạn đọc và đánh giá ngữ cảnh.</p>':''}<details class="row-detail"><summary>Thông tin mô hình</summary><small>${esc(suggestion.model)} · ${esc(String(suggestion.revision||'').slice(0,12))}</small></details>${label?`<button class="button small use-suggestion" type="button" data-label="${esc(label)}">Dùng gợi ý</button>`:''}</div>`;
}
async function loadRows(){
  const request=++datasetRequest;
  const query=new URLSearchParams({page,q:$('search').value,label:$('label-filter').value,quality:$('quality-filter').value});
  try{
    const data=await api('/api/rows?'+query);if(request!==datasetRequest)return;
    if(!data.rows.length&&page>1){page=Math.max(1,Math.ceil(data.total/25));return loadRows();}
    $('page-info').textContent=`${number(data.total)} bình luận · Trang ${page} / ${Math.max(1,Math.ceil(data.total/25))}`;
    $('prev-page').disabled=page<=1;$('next-page').disabled=page*25>=data.total;
    $('data-rows').innerHTML=data.rows.length?data.rows.map(r=>`<tr><td><div class="raw-text">${esc(r.text_raw)}</div><details class="row-detail"><summary>Bản làm sạch & nguồn</summary><div class="clean-text">${esc(r.text_clean)||'Không còn token'}</div><div class="row-meta">Bài viết: ${esc(r.post_id)}<br>Bình luận: ${esc(r.comment_id)}</div></details></td><td><span class="quality-tag ${['conflict','incomplete','empty_or_ui'].includes(r.quality)?'bad':''}">${esc(qualityNames[r.quality]||r.quality)}</span>${r.text_complete==null?'<p class="row-meta">Chưa xác nhận đã mở hết nội dung.</p>':''}${r.label?`<p class="row-meta">${esc(({manual:'Người đọc xác nhận',imported:'Nhãn nhập từ tệp',automatic:'Mô hình gán tự động',legacy:'Nhãn đã lưu'})[r.label_source]||'Nhãn đã lưu')}</p>`:''}</td><td><form class="label-form" data-id="${esc(r.id)}" data-text-hash="${esc(r.text_hash)}">${r.annotation_stale?`<p class="annotation-error">Nội dung đã đổi. Nhãn cũ: ${esc(r.previous_label||'chưa có')}. Đọc lại trước khi xác nhận.</p>`:''}${suggestionHTML(r)}<select name="label" aria-label="Nhãn bình luận ${esc(r.comment_id)}"><option value="" ${!r.label?'selected':''}>Chưa gán nhãn</option><option value="non-toxic" ${r.label==='non-toxic'?'selected':''}>Non-toxic</option><option value="toxic" ${r.label==='toxic'?'selected':''}>Toxic</option></select><input name="note" type="text" placeholder="Ghi chú ngữ cảnh…" aria-label="Ghi chú bình luận ${esc(r.comment_id)}" maxlength="2000" value="${esc(r.annotation_note)}"><label class="check"><input name="excluded" type="checkbox" ${r.excluded?'checked':''}>Loại mẫu khỏi huấn luyện</label><button class="button small" type="submit">Lưu đánh giá</button></form></td></tr>`).join(''):'<tr><td colspan="3" class="no-rows">Không có bình luận phù hợp bộ lọc. Thử đổi nhãn hoặc chất lượng.</td></tr>';
    for(const form of document.querySelectorAll('.label-form')){
      const draft=reviewDrafts.get(form.dataset.id);if(!draft)continue;
      form.elements.label.value=draft.label;form.elements.note.value=draft.note;form.elements.excluded.checked=draft.excluded;
      if(draft.text_hash!==form.dataset.textHash){const warning=document.createElement('p');warning.className='annotation-error';warning.textContent='Nội dung đã đổi từ lúc chỉnh sửa. Đọc lại và cập nhật đánh giá trước khi lưu.';form.prepend(warning);}
    }
    updateReviewActions();
  }catch(error){toast(error.message,true);}
}
function updateReviewActions(){
  const count=reviewDrafts.size;
  $('review-pending').textContent=count?`${number(count)} bình luận có thay đổi chưa lưu, gồm cả ngoài trang hiện tại.`:'Không có thay đổi chưa lưu.';
  $('review-save-all').textContent=reviewSaving?'Đang lưu…':`Lưu tất cả thay đổi${count?` (${number(count)})`:''}`;
  $('review-save-all').disabled=reviewSaving||!count;
  document.querySelectorAll('.label-form button[type="submit"]').forEach(button=>button.disabled=reviewSaving);
}
function rememberReview(form){
  reviewDrafts.set(form.dataset.id,{id:form.dataset.id,text_hash:form.dataset.textHash,label:form.elements.label.value,note:form.elements.note.value,excluded:form.elements.excluded.checked});
  updateReviewActions();
}
async function saveReviews(items,bulk){
  if(reviewSaving||!items.length)return;
  reviewSaving=true;updateReviewActions();
  try{
    await api(bulk?'/api/annotate-bulk':'/api/annotate',bulk?{rows:items}:items[0]);
    for(const item of items)if(reviewDrafts.get(item.id)===item)reviewDrafts.delete(item.id);
    toast(`Đã lưu ${number(items.length)} đánh giá.`);
    await loadRows();renderStatus(await api('/api/status'));
  }catch(error){toast(error.message,true);}
  finally{reviewSaving=false;updateReviewActions();}
}
for(const eventName of ['input','change'])$('data-rows').addEventListener(eventName,event=>{const form=event.target.closest('.label-form');if(form)rememberReview(form);});
$('review-save-all').onclick=()=>saveReviews([...reviewDrafts.values()],true);
$('data-rows').addEventListener('submit',event=>{
  event.preventDefault();const form=event.target;if(!form.matches('.label-form'))return;
  if(reviewSaving)return;rememberReview(form);saveReviews([reviewDrafts.get(form.dataset.id)],false);
});
$('data-rows').addEventListener('click',event=>{
  const button=event.target.closest('.use-suggestion');if(!button)return;
  button.closest('form').elements.label.value=button.dataset.label;
  rememberReview(button.closest('form'));
  toast('Đã điền gợi ý. Đọc bình luận rồi bấm “Lưu tất cả thay đổi” để lưu cùng các dòng đã sửa.');
});
$('auto-suggest').onclick=()=>action($('auto-suggest'),async()=>{const result=await api('/api/suggest',{});renderStatus(await api('/api/status'));toast(`Đang tạo gợi ý cho ${number(result.total)} mẫu. Khi xong, bấm “Cập nhật danh sách” để xem.`);});
$('auto-label-all').onclick=()=>action($('auto-label-all'),async()=>{
  const result=await api('/api/auto-label',{});renderStatus(await api('/api/status'));
  if(!lastStatus.annotation_job.running&&!reviewDrafts.size)await loadRows();
  toast(`Đã nhận xử lý toàn bộ ${number(result.total)} mẫu, không phụ thuộc bộ lọc. Không cần lưu từng dòng.`);
});
$('review-refresh').onclick=()=>action($('review-refresh'),loadRows);
for(const prefix of ['dataset','auto-dataset'])for(const format of ['csv','json'])$(prefix+'-'+format).onclick=()=>action($(prefix+'-'+format),async()=>{
  const automatic=prefix==='auto-dataset';
  const response=await fetch('/api/'+(automatic?'dataset-auto':'dataset')+'.'+format);
  if(!response.ok){let body;try{body=await response.json();}catch{}throw Error(body?.error||'Không xuất được dataset.');}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download=(automatic?'ptit-dataset-auto.':'ptit-reviewed-dataset.')+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
let searchTimer;
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=1;loadRows();},250);});
['label-filter','quality-filter'].forEach(id=>$(id).addEventListener('change',()=>{page=1;loadRows();}));
$('prev-page').onclick=()=>{page--;loadRows();};$('next-page').onclick=()=>{page++;loadRows();};
$('clean-save').onclick=()=>action($('clean-save'),async()=>{const r=await api('/api/clean',{});toast(`Đã lưu bản làm sạch gồm ${number(r.saved)} dòng. Bạn có thể tải CSV hoặc JSON.`);});
$('browser-open').onclick=()=>action($('browser-open'),async()=>{await api('/api/browser',{});toast('Đang mở Chrome. Bạn tự đăng nhập Facebook trong cửa sổ đó.');});
$('crawl-form').onsubmit=event=>{event.preventDefault();action($('start'),async()=>{await api('/start',{target:Number($('target').value),source:$('source-url').value.trim()});toast('Đã bắt đầu thu thập.');});};
$('stop').onclick=()=>action($('stop'),async()=>{await api('/stop',{});toast('Đã gửi yêu cầu dừng; chờ thao tác hiện tại kết thúc.');});
$('train').onclick=()=>action($('train'),async()=>{await api('/api/train',{});renderStatus(await api('/api/status'));toast('Đã bắt đầu huấn luyện. Giữ cửa sổ máy chủ mở.');});
$('predict-form').onsubmit=event=>{event.preventDefault();action($('predict-button'),async()=>{const r=await api('/api/predict',{text:$('predict-text').value,model:$('predict-model').value});$('prediction').textContent=`${r.label.toUpperCase()} · ${r.model} — Bản chuẩn hóa: ${r.text_clean}${r.stale?' · Mô hình dùng snapshot dữ liệu cũ.':''}`;});};
$('import-file').onchange=async()=>{
  const file=$('import-file').files[0];if(!file)return;
  try{if(file.size>10_000_000)throw Error('Tệp tối đa 10 MB.');const r=await api('/api/import',{filename:file.name,content:await file.text()});toast(`Đã nhập ${r.added} mẫu mới và cập nhật ${r.labels_updated} nhãn.`);page=1;await loadRows();renderStatus(await api('/api/status'));}catch(error){toast(error.message,true);}finally{$('import-file').value='';}
};
async function loadReport(){try{const response=await fetch('/api/report');if(!response.ok)throw Error('Không tải được báo cáo.');$('report-preview').textContent=await response.text();}catch(error){toast(error.message,true);}}
$('report-refresh').onclick=loadReport;
const importLabel=document.querySelector('label[for="import-file"]');
importLabel.tabIndex=0;importLabel.setAttribute('role','button');
importLabel.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('import-file').click();}});
navigate();refresh();
