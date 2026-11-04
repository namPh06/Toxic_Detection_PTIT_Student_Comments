/* Presentation of a trace returned by the same prediction request. */
'use strict';
(() => {
 const el=id=>document.getElementById(id); let trace=null, step=0, timer=null, revision=0, recording=false;
 const stop=()=>{clearInterval(timer);timer=null;el('pipeline-play').textContent='Tự chạy';};
 function draw(){
  if(!trace)return;
  el('pipeline-title').textContent=`${step+1}/${trace.stages.length} · ${trace.stages[step].title}`;
  el('pipeline-content').textContent=trace.stages[step].content;
  el('pipeline-prev').disabled=step===0;el('pipeline-next').disabled=step===trace.stages.length-1;
  [...el('pipeline-steps').children].forEach((b,i)=>b.setAttribute('aria-pressed',String(i===step)));
 }
 function clear(){stop();el('pipeline-mp4').pause();el('pipeline-mp4').removeAttribute('src');el('pipeline-mp4').hidden=true;el('pipeline-download').hidden=true;trace=null;revision++;el('pipeline-view').hidden=true;}
 window.pipelineShow=t=>{
  clear(); if(!t)return;trace=t;step=0;el('pipeline-view').hidden=false;
  el('pipeline-meta').textContent=`${t.model} · Run: ${t.run} · Chuẩn hóa: ${t.preprocess_version||'không ghi phiên bản'}`;
  el('pipeline-warning').textContent=t.warning||'';el('pipeline-video-status').textContent='';
  el('pipeline-steps').replaceChildren(...t.stages.map((s,i)=>{const b=document.createElement('button');b.type='button';b.className='button';b.textContent=`${i+1}. ${s.title}`;b.onclick=()=>{stop();step=i;draw();};return b;}));draw();
 };
 el('pipeline-prev').onclick=()=>{stop();step=Math.max(0,step-1);draw();};
 el('pipeline-next').onclick=()=>{stop();step=Math.min(trace.stages.length-1,step+1);draw();};
 el('pipeline-play').onclick=()=>{if(timer){stop();return;}if(step===trace.stages.length-1)step=0;draw();el('pipeline-play').textContent='Tạm dừng';timer=setInterval(()=>{if(step>=trace.stages.length-1){stop();return;}step++;draw();},2500);};
 el('predict-text').addEventListener('input',clear);el('predict-model').addEventListener('change',clear);
 // A retrained run repopulates this selector; invalidate its previous trace.
 new MutationObserver(clear).observe(el('predict-model'),{childList:true});
 window.pipelineRevision=()=>revision;
 window.pipelineReset=clear;
 el('pipeline-video').onclick=async()=>{
  if(!trace||recording)return;
  const snapshot=structuredClone(trace), rev=revision;
  recording=true;el('pipeline-video').disabled=true;stop();
  const request=async(url,body)=>{
   const r=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
   if(r.status===404)throw Error('Máy chủ đang chạy chưa hỗ trợ tạo video. Hãy tắt và mở lại hệ thống, sau đó nhấn Ctrl+F5.');
   const text=await r.text();let data;
   try{data=JSON.parse(text);}catch{throw Error(`Máy chủ trả phản hồi không hợp lệ (HTTP ${r.status}). Hãy khởi động lại hệ thống và thử lại.`);}
   if(!r.ok||data.error)throw Error(data.error||`Không tạo được video (HTTP ${r.status})`);return data;
  };
  try{
   el('pipeline-video-status').textContent='Đang chuẩn bị hoạt hình MP4…';
   let job=await request('/api/pipeline-video',{text:snapshot.stages[0].content,model:snapshot.model,run:snapshot.run});
   while(job.state==='running'){
    if(revision!==rev)return;
    el('pipeline-video-status').textContent=`Đang dựng hoạt hình: ${job.progress}%. Bạn vẫn có thể sử dụng giao diện.`;
    await new Promise(r=>setTimeout(r,1500));
    job=await request('/api/pipeline-video?id='+job.id);
   }
   if(revision!==rev)return;
   if(job.state==='error')throw Error(job.error);
   const url='/api/pipeline-video.mp4?id='+job.id;
   el('pipeline-mp4').src=url;el('pipeline-mp4').hidden=false;
   el('pipeline-download').href=url+'&download=1';el('pipeline-download').hidden=false;
   el('pipeline-video-status').textContent='Video đã sẵn sàng. Nhấn phát để xem hoạt hình.';
  }catch(e){if(revision===rev)el('pipeline-video-status').textContent='Không tạo được video: '+e.message;}
  finally{recording=false;el('pipeline-video').disabled=false;}
 };
})();
