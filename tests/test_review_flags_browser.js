// Every API request is intercepted; these checks never change real comments.
async function checkReviewFlagsBrowser(page, baseURL) {
  const passed=[], writes=[];
  const check=(ok,name)=>{if(!ok)throw Error(name);passed.push(name);};
  const rows=[
    {id:'1:1',post_id:'1',comment_id:'1',text_raw:'Bình luận có thể là đùa hoặc công kích',text_clean:'bình luận',text_hash:'hash-1',quality:'ready',label:'toxic',label_source:'automatic',needs_review:true,annotation_note:'Thiếu ngữ cảnh để phân biệt lời đùa. <img id="unsafe-reason" src="x">',text_complete:true,label_model:'Qwen',review_reason:'uncertain_v4_semantic'},
    {id:'1:2',post_id:'1',comment_id:'2',text_raw:'Cảm ơn thông tin',text_clean:'cảm ơn',text_hash:'hash-2',quality:'ready',label:'non-toxic',label_source:'automatic',needs_review:false,annotation_note:'Thông tin rõ ràng',text_complete:true,label_model:'Qwen'}
  ];
  const status={summary:{total:2,usable:2,labeled:2,posts:1,labels:{toxic:1,'non-toxic':1},quality:{ready:2},avg_tokens:3},job:{running:false,message:''},result:null,stale:false,annotation_job:{running:false,message:''},dataset_health:{automatic:2,reviewed:0,needs_review:1,usable_labels:2,unlabeled:0,training_ready:false}};
  await page.route(baseURL+'/api/**',async route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname;
    if(path==='/api/status')return route.fulfill({json:status});
    if(path==='/api/rows'){
      const filtered=url.searchParams.get('review')==='needs_review'?rows.filter(r=>r.needs_review):rows;
      return route.fulfill({json:{rows:filtered,total:filtered.length}});
    }
    if(path==='/api/annotate'){
      const body=request.postDataJSON(),row=rows.find(r=>r.id===body.id);
      writes.push(body);
      Object.assign(row,{label:body.label,label_source:'manual',needs_review:false,annotation_note:body.note});
      Object.assign(status.dataset_health,{automatic:1,reviewed:1,needs_review:0});
      return route.fulfill({json:{saved:true}});
    }
    throw Error('Unexpected API in review fixture: '+path);
  });
  await page.route(baseURL+'/status',route=>route.fulfill({json:{phase:'idle',ready:false,running:false,posts:0,comments:0,target:20,results:[],message:'Fixture'}}));
  try {
    for(const width of [1440,375]){
      await page.setViewportSize({width,height:900});
      await page.goto(baseURL+'/#data');
      await page.waitForSelector('.review-badge');
      check(await page.locator('.review-badge').count()===1,`Only uncertain AI label has a flag at ${width}px`);
      check(await page.locator('.label-form').first().locator('select').inputValue()==='toxic',`Flagged comment keeps its label at ${width}px`);
      check((await page.locator('.review-reason').innerText()).includes('Thiếu ngữ cảnh'),`Uncertainty reason is visible at ${width}px`);
      check(await page.locator('#unsafe-reason').count()===0,`AI reason is escaped at ${width}px`);
      check((await page.locator('#review-status').innerText()).includes('1 bình luận'),`Pending review count is visible at ${width}px`);
      check(!await page.locator('#dataset-csv').isDisabled(),`Flagged labels remain exportable at ${width}px`);
      check(await page.evaluate(()=>document.scrollingElement.scrollWidth<=innerWidth),`No page overflow at ${width}px`);
    }
    await page.locator('#show-review').click();
    await page.waitForFunction(()=>document.querySelectorAll('.label-form').length===1);
    check(await page.locator('#label-filter').inputValue()==='needs_review','Shortcut selects pending review in the label filter');
    check(await page.locator('#label-filter').evaluate(el=>el===document.activeElement),'Review shortcut moves keyboard focus to the label filter');
    check(await page.locator('#review-filter').count()===0,'Separate review status filter is removed');
    await page.reload();
    await page.waitForSelector('.review-badge');
    check(await page.locator('.review-badge').count()===1,'Flag is restored after page reload');
    await page.locator('#label-filter').selectOption('needs_review');
    await page.waitForFunction(()=>document.querySelectorAll('.label-form').length===1);
    const form=page.locator('.label-form').first();
    await form.locator('select').selectOption('non-toxic');
    check(writes.length===0&&await page.locator('.review-badge').count()===1,'Unsaved edits do not clear the flag');
    await form.locator('button[type="submit"]').click();
    await page.waitForFunction(()=>document.querySelectorAll('.label-form').length===0&&document.querySelector('#review-save-all').disabled);
    check(writes.length===1&&writes[0].label==='non-toxic'&&writes[0].text_hash==='hash-1','Manual confirmation saves chosen label and displayed text hash');
    check(await page.locator('#review-notice').isHidden(),'Review count and banner clear after successful confirmation');
    await page.locator('#label-filter').selectOption('all');
    await page.waitForFunction(()=>document.querySelectorAll('.label-form').length===2);
    check(await page.locator('.review-badge').count()===0&&await page.locator('.label-form').first().locator('select').inputValue()==='non-toxic','Confirmed label remains and the flag is removed');
    return passed;
  } finally {
    await page.unroute(baseURL+'/api/**');await page.unroute(baseURL+'/status');
  }
}
