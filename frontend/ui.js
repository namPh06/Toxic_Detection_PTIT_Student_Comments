'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Number(value || 0).toLocaleString('vi-VN');
const qualityNames = {ready:'Mẫu sạch',duplicate:'Bản trùng',conflict:'Nhãn mâu thuẫn',incomplete:'Chưa mở hết nội dung',empty_or_ui:'Rỗng / giao diện',excluded:'Đã loại'};
let currentTab = 'overview', page = 1, datasetRequest = 0, lastStatus = null, toastTimer, reviewSaving = false, cleaning = false;
const reviewDrafts = new Map();
let featureConfigInitialized=false, featurePreviewRequest=0, featurePreviewVersion='', featurePreviewIndex=0, colabBusy=false;
let gpuBusy=false, gpuFeedback=null, gpuFailed=false, gpuTargetInitialized=false;
function featureSettings(){
  return {methods:['BoW','TF-IDF'].filter((name,i)=>$(i?'feature-tfidf':'feature-bow').checked),ngram:$('feature-ngram').value,max_features:Number($('feature-max').value),char_features:false};
}
function featureConfigDirty(state){
  if(!state?.result)return false;
  const current=featureSettings(),saved={char_features:false,...state.result.settings};
  return Object.keys(current).some(key=>JSON.stringify(current[key])!==JSON.stringify(saved[key]));
}
function featuresReady(status){return !!status?.features?.ready&&!featureConfigDirty(status.features);}
function selectedAlgorithms(){return [['training-nb','NB'],['training-svm','SVM'],['training-visobert','ViSoBERT']].filter(([id])=>$(id).checked).map(([,name])=>name);}
function trainingDisabled(status){return !selectedAlgorithms().length||!status||status.job.running||status.annotation_job?.running||status.features?.job.running||status.dataset_health?.training_ready===false||!featuresReady(status);}
function automaticCandidates(status){return status?.dataset_health?.automatic_candidates??Math.max(0,(status?.summary?.usable||0)-(status?.summary?.labeled||0));}
function annotationErrorMessage(message=''){
  if(message.includes('provisional_labels'))return 'Máy chủ đang dùng code cũ. Khởi động lại ứng dụng rồi thử lại.';
  if(message.includes('thiếu RAM/VRAM'))return 'Không đủ bộ nhớ để chạy mô hình. Đóng bớt ứng dụng rồi thử lại.';
  if(message.includes('Chưa cài mô hình'))return 'Chưa cài mô hình gán nhãn trong Ollama. Cài mô hình rồi thử lại.';
  if(message.includes('Ollama'))return 'Ollama chưa sẵn sàng. Mở Ollama và kiểm tra mô hình đã cài.';
  return 'Xử lý nhãn gặp lỗi. Vui lòng thử lại.';
}
function updateDataActions(status){
  const busy=!!(cleaning||status?.annotation_job?.running||status?.job.running||status?.features?.job.running);
  $('clean-save').disabled=busy;$('clean-save').textContent=cleaning?'Đang làm sạch…':'Làm sạch dữ liệu';
  $('clean-save').setAttribute('aria-busy',String(cleaning));
  $('auto-suggest').disabled=busy;$('auto-label-all').disabled=busy||automaticCandidates(status)===0;
  $('auto-label-all').textContent=status?.annotation_job?.running&&status.annotation_job.automatic?'Đang gán nhãn…':'Gán nhãn tự động';
  $('auto-suggest').textContent=status?.annotation_job?.running?'Đang tạo gợi ý…':'Tạo gợi ý tự động';
}
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
    if(button.id==='train')button.disabled=trainingDisabled(lastStatus);
    if(button.id==='feature-extract'&&lastStatus)renderFeatureStatus(lastStatus);
    if(['clean-save','auto-suggest','auto-label-all'].includes(button.id))updateDataActions(lastStatus);
    if(button.id.startsWith('dataset-'))button.disabled=!lastStatus?.dataset_health?.usable_labels;
  }
}
function navigate() {
  const name=location.hash.slice(1)||'overview';
  currentTab=['overview','crawl','data','features','models'].includes(name)?name:'overview';
  document.querySelectorAll('.view').forEach(view=>view.hidden=view.id!==currentTab);
  document.querySelectorAll('[data-tab]').forEach(link=>{const active=link.dataset.tab===currentTab;link.classList.toggle('active',active);if(active){link.setAttribute('aria-current','page');$('breadcrumb').textContent=link.getAttribute('aria-label');}else link.removeAttribute('aria-current');});
  if(currentTab==='data') loadRows();
  if(currentTab==='features'&&lastStatus)renderFeatureStatus(lastStatus);
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
  renderFeatureStatus(status);
  const methods=status.features?.result?.settings.methods||['BoW','TF-IDF'];
  const algorithms=selectedAlgorithms(),nb=Number(algorithms.includes('NB')),svm=Number(algorithms.includes('SVM'));
  const configCount=methods.length*(nb+svm)+Number(algorithms.includes('ViSoBERT'));
  ['training-nb','training-svm'].forEach(id=>$(id).disabled=status.job.running);
  $('training-visobert').disabled=status.job.running;
  const compute=status.compute||{device:'cpu',name:'CPU'};
  if(!gpuTargetInitialized){
    if(status.colab?.connected||status.colab?.retryable)$('training-target').value='colab';
    gpuTargetInitialized=true;
  }
  const remoteSelected=$('training-target').value==='colab',remote=status.colab||{};
  $('training-target').disabled=status.job.running;
  $('training-device').textContent=`ViSoBERT: ${remoteSelected?(remote.connected?'Colab · '+remote.gpu:'Colab chưa kết nối'):(compute.device==='cuda'?'GPU · '+compute.name:'CPU (CUDA chưa khả dụng)')}. Naive Bayes / SVM: CPU.`;
  $('total').textContent=number(s.total);$('usable').textContent=number(s.usable);$('labeled').textContent=number(s.labeled);
  $('post-count').textContent=`Từ ${number(s.posts)} bài viết`;
  $('label-percent').textContent=`${s.usable?(100*s.labeled/s.usable).toFixed(1):0}% mẫu sạch đã có nhãn`;
  $('model-count').innerHTML=`${result?result.models.length:0}<small> / ${result?result.models.length:configCount}</small>`;
  $('step-crawl').textContent=s.total?'Đã có dữ liệu':'Chờ thu thập';
  $('step-label').textContent=`${number(s.labeled)} / ${number(s.usable)} mẫu`;
  $('step-model').textContent=status.job.running?'Đang huấn luyện':result?'Đã huấn luyện':featuresReady(status)?'Sẵn sàng huấn luyện':'Chờ trích xuất đặc trưng';
  const non=s.labels['non-toxic']||0,toxic=s.labels.toxic||0,unlabeled=s.labels.unlabeled||0,total=Math.max(1,s.usable);
  $('donut-total').textContent=number(s.usable);
  $('donut').style.background=`conic-gradient(#536b82 0 ${non/total*100}%,#ae263b ${non/total*100}% ${(non+toxic)/total*100}%,#e1e4e9 ${(non+toxic)/total*100}% 100%)`;
  $('donut').setAttribute('aria-label',`Non-toxic ${non}, toxic ${toxic}, chưa gán ${unlabeled}`);
  $('label-legend').innerHTML=[['Non-toxic',non,'#536b82'],['Toxic',toxic,'#ae263b'],['Chưa gán nhãn',unlabeled,'#e1e4e9']].map(([name,n,color])=>`<div class="legend-row"><span class="swatch" style="background:${color}"></span>${name}<b>${number(n)}</b></div>`).join('');
  $('quality-bars').innerHTML=bars(Object.entries(qualityNames).map(([key,name])=>[name,s.quality[key]||0,key==='ready'?'#536b82':'#7b8593']),s.total);
  $('quality-note').textContent=`${number(s.total-s.usable)} mẫu ngoài dataset sạch · Bản gốc được giữ nguyên`;
  $('next-action').textContent=s.labeled===0?'Gán nhãn tự động hoặc lưu nhãn thủ công để tiếp tục trích xuất đặc trưng.':`Đã có ${number(s.labeled)} mẫu có nhãn; còn ${number(unlabeled)} mẫu sạch chưa gán. Nhãn đã lưu dùng được ngay cho thực nghiệm.`;
  const health=status.dataset_health,annotationJob=status.annotation_job;
  if(health?.usable_labels)$('next-action').textContent=`Có ${number(health.usable_labels)} mẫu sạch có nhãn, không cần duyệt. ${featuresReady(status)?'Đặc trưng đã sẵn sàng; tiếp tục huấn luyện.':'Tiếp tục trích xuất đặc trưng trên nhóm phát triển.'}`;
  $('training-status').textContent=status.job.error?'Huấn luyện gặp lỗi. Xem chi tiết bên dưới và thử lại.':!algorithms.length?'Chọn ít nhất một mô hình để huấn luyện.':!status.job.running&&!featuresReady(status)?'Cần trích xuất đặc trưng phù hợp với dữ liệu và cấu hình hiện tại trước khi huấn luyện.':status.job.message;
  $('training-detail').hidden=!status.job.error;$('training-debug').textContent=status.job.error?status.job.message:'';
  $('train').disabled=trainingDisabled(status);
  if(remoteSelected&&algorithms.includes('ViSoBERT')&&(!remote.connected||remote.retryable||gpuBusy))$('train').disabled=true;
  const gpuBlocked=gpuBusy||status.job.running;
  ['colab-url','colab-username','colab-password','colab-connection-file','colab-connect'].forEach(id=>$(id).disabled=gpuBlocked);
  $('colab-disconnect').disabled=gpuBlocked||(!remote.connected&&!remote.retryable);
  $('colab-retry').hidden=!remote.retryable;
  $('colab-retry').disabled=gpuBlocked||!featuresReady(status);
  $('colab-connection-status').textContent=gpuFeedback??remote.message??'Chưa kết nối GPU Colab.';
  $('colab-connection-status').classList.toggle('annotation-error',gpuFailed&&!gpuBusy);
  const colabBlocked=colabBusy||status.job.running||status.annotation_job?.running||status.features?.job.running;
  $('colab-export').disabled=colabBlocked||!featuresReady(status);
  $('colab-import').disabled=colabBlocked||!featuresReady(status);
  if(!colabBusy&&featuresReady(status)&&$('colab-status').textContent==='Cần trích xuất đặc trưng trước khi xuất gói.')$('colab-status').textContent='Đặc trưng đã sẵn sàng. Có thể xuất gói để chạy ViSoBERT trên Colab.';
  $('train').textContent=status.job.running?'Đang huấn luyện…':`Huấn luyện ${configCount} cấu hình`;
  $('training-config-count').textContent=`${configCount} cấu hình`;
  $('training-feature-names').textContent=$('training-config-features').textContent=[...(nb||svm?methods:[]),...(algorithms.includes('ViSoBERT')?['ViSoBERT tokenizer']:[])].join(' · ');
  document.querySelectorAll('.model-cards article').forEach((card,i)=>{card.hidden=i<4?(!methods.includes(i<2?'BoW':'TF-IDF')||!algorithms.includes(i%2?'SVM':'NB')):!algorithms.includes('ViSoBERT');});
  $('stale-warning').hidden=!status.stale;
  $('automatic-training-warning').hidden=!(health?.automatic||result?.summary?.label_sources?.automatic);
  $('model-empty').hidden=!!result;$('model-results').hidden=!result;$('predict-button').disabled=!result||status.job.running;
  updateDataActions(status);
  $('annotation-status').hidden=!(annotationJob?.running||annotationJob?.error);
  $('annotation-status').textContent=annotationJob?.error?annotationErrorMessage(annotationJob.message):annotationJob?.running?(annotationJob.automatic?'Đang gán nhãn…':'Đang tạo gợi ý…'):'';
  $('annotation-status').classList.toggle('annotation-error',!!annotationJob?.error);
  $('dataset-health').innerHTML=health?[[s.labeled,'mẫu đã có nhãn'],[health.usable_labels,'mẫu có nhãn dùng được'],[health.unlabeled,'mẫu sạch chưa có nhãn']].map(([n,label],i)=>`<div><strong class="${i===2?'review-count':''}">${number(n)}</strong><span>${label}</span></div>`).join(''):'Chưa kiểm tra được dataset.';
  const flagged=health?.needs_review||0;
  $('review-notice').hidden=!flagged;
  const reviewMessage=`${number(flagged)} bình luận cần xác nhận nhãn.`;
  if($('review-status').textContent!==reviewMessage)$('review-status').textContent=reviewMessage;
  $('dataset-csv').disabled=$('dataset-json').disabled=!health?.usable_labels;
  if(completed&&currentTab==='data'){
    if(reviewDrafts.size)toast('Đã xử lý toàn bộ. Bấm “Cập nhật danh sách” sau khi lưu phần bạn đang sửa.');
    else loadRows();
  }
  if(result) renderResults(result);
}
function renderResults(result) {
  const names=result.models.map(m=>m.name);
  if($('matrix-model').dataset.run!==result.created_at){$('matrix-model').innerHTML=names.map(n=>`<option>${esc(n)}</option>`).join('');$('matrix-model').value=result.selected_model;$('matrix-model').dataset.run=result.created_at;}
  if($('predict-model').dataset.run!==result.created_at){$('predict-model').innerHTML='<option value="">Mô hình chọn theo validation</option>'+names.map(n=>`<option>${esc(n)}</option>`).join('');$('predict-model').dataset.run=result.created_at;}
  $('split-info').textContent=`Train ${result.split.train.count} · Validation ${result.split.validation.count} · Test ${result.split.test.count} mẫu. Chọn: ${result.selected_model}.`;
  $('metrics-rows').innerHTML=result.models.map(m=>`<tr><td class="${m.name===result.selected_model?'selected-model':''}">${esc(m.name)}${m.name===result.selected_model?' ★':''}<br><small>${esc(m.device||m.parameters?.device||'cpu')}${typeof m.threshold==='number'?` · Ngưỡng ${m.threshold.toFixed(4)}`:''}</small></td><td>${m.validation.f1_macro.toFixed(3)}</td>${['accuracy','precision','recall','f1','f1_macro'].map(k=>`<td>${m.test[k].toFixed(3)}</td>`).join('')}<td>${m.seconds.toFixed(1)}s</td></tr>`).join('');
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
   else {$('training-status').textContent='Mất kết nối máy chủ. Kiểm tra cửa sổ MO_CONG_CU.cmd.';$('feature-status').textContent='Mất kết nối máy chủ. Chạy lại MO_CONG_CU.cmd để tiếp tục.';['train','feature-extract','auto-suggest','auto-label-all','dataset-csv','dataset-json'].forEach(id=>$(id).disabled=true);}
  if(results[1].status==='fulfilled') renderCrawler(results[1].value);
  else {
    $('crawl-phase').textContent='Mất kết nối';
    $('crawl-message').textContent='Mất kết nối máy chủ. Chạy lại MO_CONG_CU.cmd và giữ cửa sổ đó mở. Trang sẽ tự kết nối lại.';
    $('crawl-message').classList.add('annotation-error');$('crawl-detail').hidden=true;
    ['browser-open','start','stop'].forEach(id=>$(id).disabled=true);
  }
  setTimeout(refresh,3000);
}
function renderFeatureStatus(status){
  const state=status.features, result=state?.result,s=status.experiment_summary||status.summary;
  if(!featureConfigInitialized){
    if(result){const config=result.settings;$('feature-bow').checked=config.methods.includes('BoW');$('feature-tfidf').checked=config.methods.includes('TF-IDF');$('feature-ngram').value=config.ngram;$('feature-max').value=config.max_features;}
    featureConfigInitialized=true;
  }
  $('feature-eligible').textContent=number(s.labeled);$('feature-non-toxic').textContent=number(s.labels['non-toxic']);$('feature-toxic').textContent=number(s.labels.toxic);$('feature-unused').textContent=number(status.summary.total-s.labeled);
  const busy=!!(state?.job.running||status.job.running||status.annotation_job?.running),dirty=featureConfigDirty(state),stale=!!(state?.stale||dirty);
  for(const id of ['feature-bow','feature-tfidf','feature-ngram','feature-max'])$(id).disabled=busy;
  $('feature-extract').disabled=busy||status.dataset_health?.training_ready===false;
  $('feature-extract').textContent=state?.job.running?'Đang trích xuất…':result?'Trích xuất lại đặc trưng':'Trích xuất đặc trưng';
  $('feature-form').setAttribute('aria-busy',String(!!state?.job.running));
  $('feature-progress').hidden=!state?.job.running;
  $('feature-status').textContent=state?.job.running?state.job.message:state?.job.error?state.job.message:stale?'Cần trích xuất lại đặc trưng':result?'Đã có bộ đặc trưng phù hợp với dữ liệu hiện tại':'Chưa trích xuất đặc trưng';
  $('feature-status').classList.toggle('annotation-error',!!state?.job.error);
  $('feature-status-note').textContent=status.dataset_health?.training_ready===false?status.dataset_health.training_message:state?.job.running?'Đang tạo BoW và TF-IDF từ tập train. Giữ cửa sổ công cụ mở.':'Tách từ bằng Underthesea. Từ vựng và IDF chỉ học trên train. ViSoBERT dùng tokenizer riêng khi huấn luyện.';
  $('feature-stale').hidden=!stale;$('feature-results').hidden=!result;$('feature-preview').hidden=!result||stale;
  $('step-features').textContent=state?.job.running?'Đang trích xuất':stale?'Cần trích xuất lại':result?'Đã trích xuất':'Chưa trích xuất';
  if(!result)return;
  const version=result.created_at;
  if($('feature-results').dataset.version!==version){
    $('feature-results').dataset.version=version;
    $('feature-created').textContent='Tách từ: '+result.tokenizer+' · Đã lưu: '+new Date(version).toLocaleString('vi-VN');
    $('feature-dimensions').innerHTML=Object.entries(result.methods).map(([name,data])=>`<article class="panel"><div class="panel-heading"><h3>${esc(name)}</h3><span class="pill">${esc(({unigram:'Unigram',bigram:'Bigram',both:'Unigram + bigram'})[result.settings.ngram])}</span></div><div class="panel-body"><strong class="feature-dimension">${number(data.dimensions)}</strong><span> đặc trưng thực tế</span><p class="muted">Giới hạn ${number(result.settings.max_features)} · ${number(data.matrices.train[0])} dòng train × ${number(data.dimensions)} cột.</p></div></article>`).join('');
    $('feature-splits').innerHTML=Object.entries(result.split).map(([part,data])=>`<tr><td>${esc(part==='train'?'Train':part==='validation'?'Validation':'Test')}</td><td>${number(data.count)}</td><td>${number(data.labels['non-toxic'])}</td><td>${number(data.labels.toxic)}</td><td>${number(data.groups)}</td></tr>`).join('');
  }
  if(currentTab==='features'&&!stale&&featurePreviewVersion!==version){featurePreviewVersion=version;loadFeaturePreview(0);}
}
async function loadFeaturePreview(index){
  const request=++featurePreviewRequest;
  $('feature-preview').setAttribute('aria-busy','true');
  try{
    const query=new URLSearchParams({index,split:$('feature-split').value}),data=await api('/api/features?'+query);
    if(request!==featurePreviewRequest||!lastStatus?.features?.ready||featureConfigDirty(lastStatus.features))return;
    featurePreviewIndex=data.index;$('feature-index').value=data.index+1;$('feature-index').max=data.total;
    $('feature-prev').disabled=data.index===0;$('feature-next').disabled=data.index+1>=data.total;
    $('feature-sample-meta').textContent=`Bình luận ${number(data.index+1)} / ${number(data.total)} · ${data.split} · Nhãn: ${data.label}`;
    $('feature-sample-text').textContent=data.text_clean;
    $('feature-sample-tokens').textContent=data.tokens.join(' · ');
    $('feature-terms').innerHTML=data.terms.length?data.terms.map(term=>`<tr><td>${esc(term.term)}</td><td>${term.bow===null?'—':number(term.bow)}</td><td>${term.tfidf===null?'—':term.tfidf.toFixed(6)}</td></tr>`).join(''):'<tr><td colspan="3" class="no-rows">Bình luận này không có đặc trưng nằm trong từ vựng đã học.</td></tr>';
    $('feature-term-note').textContent=`${number(data.term_count)} đặc trưng khác 0${data.term_count>200?' · Hiển thị 200 đặc trưng đầu tiên theo thứ tự chữ cái':''}. Dấu “—” nghĩa là phương pháp chưa được chọn hoặc đặc trưng không thuộc từ vựng của phương pháp đó.`;
  }catch(error){if(request===featurePreviewRequest){featurePreviewVersion='';$('feature-terms').innerHTML='<tr><td colspan="3" class="no-rows">Không tải được đặc trưng. Hãy thử chọn lại bình luận.</td></tr>';toast(error.message,true);}}
  finally{if(request===featurePreviewRequest)$('feature-preview').setAttribute('aria-busy','false');}
}
$('feature-form').onsubmit=event=>{event.preventDefault();action($('feature-extract'),async()=>{await api('/api/features',featureSettings());renderStatus(await api('/api/status'));toast('Đã bắt đầu trích xuất đặc trưng.');});};
async function colabAction(message, fn){
  if(colabBusy)return;
  colabBusy=true;$('colab-status').textContent=message;$('colab-status').classList.remove('annotation-error');
  if(lastStatus)renderStatus(lastStatus);
  try{await fn();}
  catch(error){$('colab-status').textContent=error.message;$('colab-status').classList.add('annotation-error');}
  finally{colabBusy=false;try{renderStatus(await api('/api/status'));}catch{} }
}
async function colabResponse(response){
  if(!response.ok){let message='Không xử lý được gói Colab.';try{message=(await response.json()).error||message;}catch{}throw new Error(message);}
  return response;
}
$('colab-export').onclick=()=>colabAction('Đang đóng gói dữ liệu cho Colab…',async()=>{
  const response=await colabResponse(await fetch('/api/colab/export',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}));
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download='ptit-colab-input.zip';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
  $('colab-status').textContent='Đã xuất gói. Tải notebook, mở trên Colab và tải ZIP lên khi notebook yêu cầu.';
});
$('colab-import').onclick=()=>$('colab-result-file').click();
$('colab-result-file').onchange=()=>{
  const input=$('colab-result-file'),file=input.files[0];if(!file)return;
  colabAction('Đang tải và kiểm tra mô hình Colab. Giữ trang mở cho đến khi hoàn tất…',async()=>{
    if(file.size>1500000000)throw new Error('ZIP kết quả vượt giới hạn 1,5 GB.');
    await colabResponse(await fetch('/api/colab/import',{method:'POST',headers:{'Content-Type':'application/zip'},body:file}));
    $('colab-status').textContent='Đã nhập ViSoBERT từ Colab. Xem bảng so sánh hoặc dùng mục Thử phân loại bình luận bên dưới.';
  }).finally(()=>{input.value='';});
};
async function gpuAction(message, fn){
  if(gpuBusy)return;
  gpuBusy=true;gpuFailed=false;gpuFeedback=message;if(lastStatus)renderStatus(lastStatus);
  try{await fn();gpuFeedback=null;renderStatus(await api('/api/status'));}
  catch(error){gpuFeedback=error.message;gpuFailed=true;}
  finally{gpuBusy=false;if(lastStatus)renderStatus(lastStatus);}
}
$('colab-connection-file').onchange=async()=>{
  const input=$('colab-connection-file'),file=input.files[0];if(!file)return;
  try{
    if(file.size>20000)throw new Error('File kết nối JSON vượt 20 KB.');
    const connection=JSON.parse(await file.text());
    if(!connection||['url','username','password'].some(k=>typeof connection[k]!=='string'||!connection[k]))throw new Error('File kết nối thiếu link, tài khoản hoặc mật khẩu.');
    $('colab-url').value=connection.url;$('colab-username').value=connection.username;$('colab-password').value=connection.password;
    gpuFeedback='Đã mở file kết nối. Bấm Kết nối GPU để kiểm tra.';gpuFailed=false;
  }catch(error){gpuFeedback='Không đọc được file kết nối: '+error.message;gpuFailed=true;}
  finally{input.value='';if(lastStatus)renderStatus(lastStatus);}
};
$('colab-connect-form').onsubmit=event=>{
  event.preventDefault();gpuAction('Đang kiểm tra kết nối GPU Colab…',async()=>{
    await api('/api/colab/connect',{url:$('colab-url').value,username:$('colab-username').value,password:$('colab-password').value});
    $('colab-password').value='';$('training-target').value='colab';$('training-visobert').checked=true;
  });
};
$('colab-disconnect').onclick=()=>gpuAction('Đang ngắt kết nối…',async()=>{await api('/api/colab/disconnect',{});$('training-target').value='local';$('colab-password').value='';});
$('colab-retry').onclick=()=>gpuAction('Đang nối lại lượt Colab…',async()=>{await api('/api/colab/retry',{});});
$('training-target').onchange=()=>{if(lastStatus)renderStatus(lastStatus);};
for(const id of ['feature-bow','feature-tfidf','feature-ngram','feature-max'])$(id).addEventListener('change',()=>{if(lastStatus){featurePreviewVersion='';renderStatus(lastStatus);}});
$('feature-split').onchange=()=>loadFeaturePreview(0);
$('feature-index').onchange=()=>{const value=Number($('feature-index').value);if(Number.isInteger(value)&&value>=1)loadFeaturePreview(value-1);};
$('feature-prev').onclick=()=>loadFeaturePreview(Math.max(0,featurePreviewIndex-1));
$('feature-next').onclick=()=>loadFeaturePreview(featurePreviewIndex+1);
const reasons={no_progress:'Không có tiến triển sau 5 lượt',time_limit:'Đạt giới hạn 3 phút',unrecognized_scope:'Không nhận diện vùng bình luận',unrecognized_scroll:'Không nhận diện vùng cuộn',user_stop:'Dừng theo yêu cầu',dataset_limit:'Đạt giới hạn dữ liệu',crawl_error:'Lỗi khi thu thập bài'};
function renderCrawler(s){
  $('crawl-message').textContent=s.phase==='error'?(s.ready?'Thu thập gặp lỗi. Dữ liệu đã đọc vẫn được giữ trong phiên. Bạn có thể tải bản sao và thử lại.':'Chưa kết nối được với Chrome. Bấm “Mở Chrome thu thập” để thử lại.'):s.message;
  $('crawl-message').classList.toggle('annotation-error',s.phase==='error');
  $('crawl-detail').hidden=s.phase!=='error';$('crawl-debug').textContent=s.phase==='error'?s.message:'';
  $('crawl-posts').textContent=number(s.posts);$('crawl-comments').textContent=number(s.comments);
  $('crawl-phase').textContent=({idle:'Chưa mở Chrome',opening:'Đang mở Chrome',ready:'Sẵn sàng',discovering:'Đang tìm bài',collecting:'Đang thu thập',error:'Cần kiểm tra'})[s.phase]||s.phase;
  $('crawl-progress').max=s.target;$('crawl-progress').value=Math.min(s.posts,s.target);
  $('crawl-source').textContent=s.source?`Nguồn: ${s.source}`:'Chưa chọn nguồn thu thập';
  $('browser-open').disabled=s.ready||s.phase==='opening';$('start').disabled=!s.ready||s.running;$('stop').disabled=!s.running;$('target').disabled=s.running;$('source-url').disabled=s.running;$('collection-filter').disabled=s.running;
  const fc=s.filter_counts||{};$('crawl-filter-status').textContent=s.collection_filter&&s.collection_filter!=='all'?`Lọc ${s.collection_filter}: đã xét ${fc.evaluated||0} · giữ ${fc.accepted||0} · loại ${fc.rejected||0} · chưa rõ ${fc.uncertain||0}`:'Đang giữ tất cả bình luận mới.';
  const body=$('crawl-results'),scroll=body.closest('.table-scroll');
  const html=s.results.length?s.results.map(r=>`<tr><td>${esc(r.post_id)}</td><td>${number(r.count)}</td><td>${esc(reasons[r.reason]||r.reason)}${r.error?`<details class="row-detail"><summary>Chi tiết lỗi</summary><p class="row-meta">${esc(r.error)}</p></details>`:''}</td><td>Chưa xác nhận</td></tr>`).join(''):'<tr><td colspan="4" class="no-rows">Chưa có nhật ký. Kết quả từng bài sẽ xuất hiện sau khi thu thập.</td></tr>';
  if(body.innerHTML!==html){
    const {scrollTop,scrollLeft}=scroll;
    body.innerHTML=html;scroll.scrollTop=scrollTop;scroll.scrollLeft=scrollLeft;
  }
}
function suggestionHTML(row){
  if(row.label_source==='automatic')return row.needs_review?`<div class="label-suggestion needs-review"><span class="review-badge"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 21V3m0 1c5-4 9 4 14 0v11c-5 4-9-4-14 0"/></svg>Cần kiểm tra</span><b>Nhãn AI đề xuất: <span class="label-chip" data-label="${esc(row.label)}">${esc(row.label)}</span></b>${row.annotation_note?`<p class="review-reason"><b>Lý do cần kiểm tra:</b> ${esc(row.annotation_note)}</p>`:''}</div>`:'';
  const suggestion=row.suggestion;if(!suggestion)return '';
  const label=['toxic','non-toxic'].includes(suggestion.suggested_label)?suggestion.suggested_label:'';
  return `<div class="label-suggestion"><b>${label?`Gợi ý: <span class="label-chip" data-label="${esc(label)}">${esc(label)}</span>`:'Chưa đề xuất nhãn'}</b>${suggestion.truncated?'<p class="annotation-error">Chưa đọc hết nội dung.</p>':''}${label?`<button class="button small use-suggestion" type="button" data-label="${esc(label)}">Dùng gợi ý</button>`:''}</div>`;
}
async function loadRows(){
  const request=++datasetRequest;
  const label=$('label-filter').value;
  const query=new URLSearchParams({page,q:$('search').value,label:label==='needs_review'?'all':label,quality:$('quality-filter').value,review:label==='needs_review'?'needs_review':'all'});
  try{
    const data=await api('/api/rows?'+query);if(request!==datasetRequest)return;
    if(!data.rows.length&&page>1){page=Math.max(1,Math.ceil(data.total/25));return loadRows();}
    $('page-info').textContent=`${number(data.total)} bình luận · Trang ${page} / ${Math.max(1,Math.ceil(data.total/25))}`;
    $('prev-page').disabled=page<=1;$('next-page').disabled=page*25>=data.total;
    $('data-rows').innerHTML=data.rows.length?data.rows.map(r=>`<tr><td><div class="raw-text">${esc(r.text_raw)}</div><details class="row-detail"><summary>Bản làm sạch & nguồn</summary><div class="clean-text">${esc(r.text_clean)||'Không còn token'}</div><div class="row-meta">Bài viết: ${esc(r.post_id)}<br>Bình luận: ${esc(r.comment_id)}</div></details></td><td><span class="quality-tag ${['conflict','incomplete','empty_or_ui'].includes(r.quality)?'bad':''}">${esc(qualityNames[r.quality]||r.quality)}</span>${r.text_complete==null?'<p class="row-meta">Chưa xác nhận đã mở hết nội dung.</p>':''}${r.label?`<p class="row-meta">${esc(({manual:'Người đọc xác nhận',imported:'Nhãn nhập từ tệp',automatic:'Mô hình gán tự động',legacy:'Nhãn đã lưu'})[r.label_source]||'Nhãn đã lưu')}</p>`:''}</td><td><form class="label-form" data-id="${esc(r.id)}" data-text-hash="${esc(r.text_hash)}">${r.annotation_stale?`<p class="annotation-error">Nội dung đã đổi. Nhãn cũ: ${esc(r.previous_label||'chưa có')}. Đọc lại trước khi xác nhận.</p>`:''}${suggestionHTML(r)}<select name="label" data-label="${esc(r.label)}" aria-label="Nhãn bình luận ${esc(r.comment_id)}"><option value="" ${!r.label?'selected':''}>Chưa gán nhãn</option><option value="non-toxic" ${r.label==='non-toxic'?'selected':''}>Non-toxic</option><option value="toxic" ${r.label==='toxic'?'selected':''}>Toxic</option></select><input name="note" type="text" placeholder="Ghi chú ngữ cảnh…" aria-label="Ghi chú bình luận ${esc(r.comment_id)}" maxlength="2000" value="${esc(r.annotation_note)}"><label class="check"><input name="excluded" type="checkbox" ${r.excluded?'checked':''}>Loại mẫu khỏi huấn luyện</label><button class="button small" type="submit">Lưu nhãn</button></form></td></tr>`).join(''):'<tr><td colspan="3" class="no-rows">Không có bình luận phù hợp bộ lọc. Thử đổi nhãn hoặc chất lượng.</td></tr>';
    for(const form of document.querySelectorAll('.label-form')){
      if(form.querySelector('.needs-review'))form.querySelector('button[type="submit"]').textContent='Xác nhận nhãn';
      const draft=reviewDrafts.get(form.dataset.id);if(!draft)continue;
      form.elements.label.value=draft.label;form.elements.note.value=draft.note;form.elements.excluded.checked=draft.excluded;
      form.elements.label.dataset.label=draft.label;
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
  form.elements.label.dataset.label=form.elements.label.value;
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
  toast('Đã điền gợi ý, chưa lưu nhãn.');
});
$('auto-suggest').onclick=()=>action($('auto-suggest'),async()=>{const result=await api('/api/suggest',{});renderStatus(await api('/api/status'));toast(`Đang tạo gợi ý cho ${number(result.total)} mẫu.`);});
$('auto-label-all').onclick=()=>action($('auto-label-all'),async()=>{
  const result=await api('/api/auto-label',{});renderStatus(await api('/api/status'));
  if(!lastStatus.annotation_job.running&&!reviewDrafts.size)await loadRows();
  toast(`Đang gán nhãn cho ${number(result.total)} mẫu.`);
});
$('review-refresh').onclick=()=>action($('review-refresh'),loadRows);
for(const prefix of ['dataset'])for(const format of ['csv','json'])$(prefix+'-'+format).onclick=()=>action($(prefix+'-'+format),async()=>{
  const automatic=prefix==='auto-dataset';
  const response=await fetch('/api/'+(automatic?'dataset-auto':'dataset')+'.'+format);
  if(!response.ok){let body;try{body=await response.json();}catch{}throw Error(body?.error||'Không xuất được dataset.');}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download=(automatic?'ptit-dataset-auto.':'ptit-labeled-dataset.')+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
let searchTimer;
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=1;loadRows();},250);});
['label-filter','quality-filter'].forEach(id=>$(id).addEventListener('change',()=>{page=1;loadRows();}));
$('show-review').onclick=()=>{
  $('label-filter').value='needs_review';$('quality-filter').value='ready';$('search').value='';
  page=1;loadRows();$('label-filter').focus();
};
$('prev-page').onclick=()=>{page--;loadRows();};$('next-page').onclick=()=>{page++;loadRows();};
$('clean-save').onclick=()=>action($('clean-save'),async()=>{
  cleaning=true;updateDataActions(lastStatus);$('clean-status').hidden=false;$('clean-status').textContent='Đang làm sạch dữ liệu…';
  try{
    const r=await api('/api/clean',{});renderStatus(await api('/api/status'));
    if(!reviewDrafts.size)await loadRows();
    $('clean-status').textContent=`Đã làm sạch ${number(r.saved)} dòng.`;
    toast('Đã làm sạch dữ liệu.');
  }catch(error){$('clean-status').textContent='Làm sạch thất bại. Vui lòng thử lại.';throw error;}
  finally{cleaning=false;updateDataActions(lastStatus);}
});
$('browser-open').onclick=()=>action($('browser-open'),async()=>{await api('/api/browser',{});toast('Đang mở Chrome. Bạn tự đăng nhập Facebook trong cửa sổ đó.');});
$('crawl-form').onsubmit=event=>{event.preventDefault();action($('start'),async()=>{await api('/start',{target:Number($('target').value),source:$('source-url').value.trim(),collection_filter:$('collection-filter').value});toast('Đã bắt đầu thu thập.');});};
$('stop').onclick=()=>action($('stop'),async()=>{await api('/stop',{});toast('Đã gửi yêu cầu dừng; chờ thao tác hiện tại kết thúc.');});
for(const id of ['training-nb','training-svm','training-visobert'])$(id).onchange=()=>{if(lastStatus)renderStatus(lastStatus);};
$('train').onclick=()=>action($('train'),async()=>{
  const algorithms=selectedAlgorithms(),remote=$('training-target').value==='colab'&&algorithms.includes('ViSoBERT');
  await api(remote?'/api/colab/train':'/api/train',{mode:'optimized',algorithms});
  renderStatus(await api('/api/status'));toast(remote?'Đã bắt đầu. Giữ Colab và chương trình web mở để tự nhận kết quả.':'Đã bắt đầu huấn luyện các mô hình đã chọn. Giữ cửa sổ máy chủ mở.');
});
$('predict-form').onsubmit=event=>{event.preventDefault();action($('predict-button'),async()=>{window.pipelineReset?.();const traceRevision=window.pipelineRevision?.();const r=await api('/api/predict',{text:$('predict-text').value,model:$('predict-model').value,explain:true});if(traceRevision!==window.pipelineRevision?.())return;window.pipelineShow?.(r.trace);$('prediction').textContent=`${r.label.toUpperCase()} · ${r.model} — Bản chuẩn hóa: ${r.text_clean}${r.stale?' · Mô hình dùng snapshot dữ liệu cũ.':''}`;});};
$('import-file').onchange=async()=>{
  const file=$('import-file').files[0];if(!file)return;
  try{if(file.size>10_000_000)throw Error('Tệp tối đa 10 MB.');const r=await api('/api/import',{filename:file.name,content:await file.text()});toast(`Đã nhập ${r.added} mẫu mới và cập nhật ${r.labels_updated} nhãn.`);page=1;await loadRows();renderStatus(await api('/api/status'));}catch(error){toast(error.message,true);}finally{$('import-file').value='';}
};
const importLabel=document.querySelector('label[for="import-file"]');
importLabel.tabIndex=0;importLabel.setAttribute('role','button');
importLabel.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('import-file').click();}});
navigate();refresh();
