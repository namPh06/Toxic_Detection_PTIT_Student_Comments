// All API mutations are intercepted; these checks never label real comments.
async function checkLabelingBrowser(page, baseURL) {
  const passed = [], writes = [];
  const check = (ok, name) => { if (!ok) throw Error(name); passed.push(name); };
  const suggestion = {suggested_label:'toxic',model_score:.91,model:'local-fixture',revision:'test',text_hash:'hash-1'};
  const rows = [
    {id:'1:1',post_id:'1',comment_id:'1',text_raw:'Bình luận cần người đọc đánh giá',text_clean:'bình luận',text_hash:'hash-1',quality:'ready',label:'',annotation_note:'',text_complete:true,suggestion},
    {id:'1:2',post_id:'1',comment_id:'2',text_raw:'Bình luận dài',text_clean:'dài',text_hash:'hash-2',quality:'ready',label:'',annotation_note:'',text_complete:true,suggestion:{...suggestion,suggested_label:'',truncated:true,abstain_reason:'truncated',model_score:.6}},
    {id:'1:3',post_id:'1',comment_id:'3',text_raw:'Nội dung đã đổi',text_clean:'nội dung',text_hash:'new-hash',quality:'ready',label:'',annotation_note:'',annotation_stale:true,previous_label:'non-toxic',suggestion:null},
    {id:'1:4',post_id:'1',comment_id:'4',text_raw:'Chưa mở hết…',text_clean:'chưa mở',text_hash:'hash-4',quality:'incomplete',label:'',annotation_note:'',text_complete:false,suggestion:null}
  ];
  const status = {summary:{total:4,usable:3,labeled:0,posts:1,labels:{unlabeled:3},quality:{ready:3,incomplete:1},avg_tokens:2},
    job:{running:false,message:'Chờ nhãn'},result:null,stale:false,annotation_job:{running:false,message:'Chờ tạo gợi ý'},
    dataset_health:{reviewed:0,suggested:1,abstained:1,stale_annotations:1,incomplete:1,unknown_completeness:1,training_ready:false,training_message:'Cần thêm mẫu được duyệt'}};
  await page.route(baseURL+'/api/**', async route => {
    const request=route.request(),path=new URL(request.url()).pathname;
    if(request.method()==='POST')writes.push({path,body:request.postDataJSON()});
    if(path==='/api/status')return route.fulfill({json:status});
    if(path==='/api/rows')return route.fulfill({json:{rows,total:rows.length}});
    if(path==='/api/suggest'){status.annotation_job={running:true,message:'Đang xử lý'};return route.fulfill({json:{started:true,total:3}});}
    if(path==='/api/annotate'){rows[0].label=request.postDataJSON().label;rows[0].suggestion=null;status.dataset_health.reviewed=1;status.summary.labeled=1;return route.fulfill({json:{saved:true}});}
    throw Error('Unexpected API in fixture: '+path);
  });
  await page.route(baseURL+'/status', route=>route.fulfill({json:{phase:'idle',ready:false,running:false,posts:0,comments:0,target:20,results:[],message:'Fixture'}}));
  try {
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:800});
      await page.goto(baseURL+'/#data');
      await page.waitForSelector('.label-form');
      check(await page.locator('#train').isDisabled(),`Training blocked without reviewed data at ${width}px`);
      check(await page.locator('#dataset-csv').isDisabled(),`Reviewed export disabled with zero labels at ${width}px`);
      check(await page.locator('.use-suggestion').count()===1,`No accept button for uncertain/truncated rows at ${width}px`);
      check(await page.locator('.label-form').nth(2).innerText().then(t=>t.includes('Nội dung đã đổi')),`Stale annotation is explained at ${width}px`);
      check(await page.locator('.label-suggestion').first().innerText().then(t=>t.includes('0.910')&&t.includes('Không phải độ chính xác')),`Score is not presented as accuracy at ${width}px`);
      check(await page.evaluate(()=>document.scrollingElement.scrollWidth<=innerWidth),`No page overflow at ${width}px`);
    }
    await page.locator('.use-suggestion').click();
    check(writes.length===0&&await page.locator('.label-form').first().locator('select').inputValue()==='toxic','Using suggestion only fills the form');
    await page.locator('.label-form').first().locator('input[name="note"]').fill('Đang đọc và sửa ghi chú');
    await page.evaluate(status=>renderStatus(status),status);
    check(await page.locator('.label-form').first().locator('input[name="note"]').inputValue()==='Đang đọc và sửa ghi chú','Polling preserves unsaved review edits');
    await page.locator('.label-form').first().locator('button[type="submit"]').click();
    await page.waitForFunction(()=>!document.querySelector('#dataset-csv').disabled);
    const annotation=writes.find(w=>w.path==='/api/annotate')?.body;
    check(annotation?.label==='toxic'&&annotation?.text_hash==='hash-1'&&annotation?.note==='Đang đọc và sửa ghi chú','Explicit review posts the displayed text hash and chosen label');
    await page.locator('details').filter({has:page.locator('#auto-suggest')}).locator('summary').click();
    await page.locator('#auto-suggest').click();
    await page.waitForFunction(()=>document.querySelector('#auto-suggest').disabled);
    check(writes.filter(w=>w.path==='/api/suggest').length===1,'Suggestion button starts one job');
    check(await page.locator('#train').isDisabled(),'Training disabled while suggestions run');
    await page.locator('#review-refresh').click();
    check(await page.locator('.label-form').count()===4,'Manual list refresh remains available');
    return passed;
  } finally {
    await page.unroute(baseURL+'/api/**');await page.unroute(baseURL+'/status');
  }
}
async function checkBulkLabelingBrowser(page, baseURL) {
  const passed=[],writes=[];
  const check=(ok,name)=>{if(!ok)throw Error(name);passed.push(name);};
  let completed=false;
  const row={id:'1:1',post_id:'1',comment_id:'1',text_raw:'Bình luận fixture',text_clean:'bình luận fixture',text_hash:'hash',quality:'ready',label:'',annotation_note:'',text_complete:true};
  const status={summary:{total:140,usable:138,labeled:0,posts:12,labels:{unlabeled:138},quality:{ready:138,duplicate:2},avg_tokens:3},job:{running:false,message:'Chờ huấn luyện'},result:null,annotation_job:{running:false,message:'Sẵn sàng'},dataset_health:{automatic:0,reviewed:0,training_ready:false}};
  await page.route(baseURL+'/api/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(request.method()==='POST')writes.push({path,body:request.postDataJSON()});
    if(path==='/api/status')return route.fulfill({json:status});
    if(path==='/api/rows')return route.fulfill({json:{rows:[completed?{...row,label:'toxic',label_source:'automatic',model_score:.6,label_threshold:.5,label_model:'fixture',label_revision:'fixture',needs_review:true,review_reason:'uncertain'}:row],total:138}});
    if(path==='/api/auto-label'){status.annotation_job={running:true,automatic:true,message:'Đang xử lý 138 mẫu'};return route.fulfill({json:{started:true,total:138}});}
    if(path==='/api/dataset-auto.csv')return route.fulfill({contentType:'text/csv',body:'label,label_source\ntoxic,automatic\n'});
    throw Error('Unexpected API in bulk fixture: '+path);
  });
  await page.route(baseURL+'/status',route=>route.fulfill({json:{phase:'idle',ready:false,running:false,posts:0,comments:0,target:20,results:[],message:'Fixture'}}));
  try{
    await page.goto(baseURL+'/#data');await page.waitForSelector('.label-form');
    check(await page.locator('#label-filter').inputValue()==='all','Default filter shows completed automatic labels');
    await page.locator('#search').fill('lọc riêng');
    await page.locator('#auto-label-all').click();
    await page.waitForFunction(()=>document.querySelector('#auto-label-all').disabled);
    check(writes.length===1&&writes[0].path==='/api/auto-label'&&JSON.stringify(writes[0].body)==='{}','One request labels the whole workspace without sending page or search filters');
    check(await page.locator('#auto-suggest').isDisabled()&&await page.locator('#train').isDisabled(),'Other model jobs blocked while bulk labels run');
    await page.locator('.label-form input[name="note"]').fill('Ghi chú chưa lưu');
    completed=true;status.annotation_job={running:false,automatic:true,message:'Đã gán 138 nhãn'};
    status.summary.labeled=138;status.summary.labels={toxic:20,'non-toxic':118};
    status.dataset_health={automatic:138,reviewed:0,needs_review:5,training_ready:true};
    await page.evaluate(status=>renderStatus(status),status);
    check(await page.locator('.label-form input[name="note"]').inputValue()==='Ghi chú chưa lưu','Bulk completion preserves unsaved notes');
    check(!await page.locator('#auto-dataset-csv').isDisabled()&&await page.locator('#dataset-csv').isDisabled(),'Automatic export available without per-row approval; reviewed export stays separate');
    check(!await page.locator('#train').isDisabled(),'Machine-labeled dataset can be trained directly');
    check(await page.locator('#automatic-training-warning').evaluate(el=>!el.hidden),'Automatic label limitation is displayed');
    await page.locator('#review-refresh').click();
    await page.waitForFunction(()=>document.querySelector('.label-suggestion')?.textContent.includes('Nhãn tự động'));
    await page.locator('.label-suggestion .row-detail > summary').click();
    check(await page.locator('.label-suggestion').innerText().then(t=>t.includes('Cần kiểm tra')&&t.includes('0.600')),'Uncertain automatic label keeps score and review flag');
    const download=page.waitForEvent('download');await page.locator('#auto-dataset-csv').click();
    check((await download).suggestedFilename()==='ptit-dataset-auto.csv','CSV download uses automatic dataset endpoint');
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:800});
      check(await page.evaluate(()=>document.scrollingElement.scrollWidth<=innerWidth),`Bulk controls fit at ${width}px`);
    }
    return passed;
  }finally{await page.unroute(baseURL+'/api/**');await page.unroute(baseURL+'/status');}
}
if(typeof module!=='undefined')module.exports={checkLabelingBrowser,checkBulkLabelingBrowser};
