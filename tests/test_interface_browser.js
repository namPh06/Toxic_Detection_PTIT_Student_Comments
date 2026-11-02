// UI-only fixtures. No request may change the real workspace.
async function checkInterfaceBrowser(page, baseURL) {
  const passed = [];
  const check = (ok, name) => { if (!ok) throw Error(name); passed.push(name); };
  const status = {
    summary:{total:12,usable:10,labeled:10,posts:5,labels:{toxic:2,'non-toxic':8},quality:{ready:10,duplicate:2},avg_tokens:7},
    job:{running:false,message:'Sẵn sàng'},result:null,stale:false,
    annotation_job:{running:true,message:'Đang tải model.onnx: 24%…'},
    dataset_health:{automatic:10,reviewed:0,needs_review:2,training_ready:true,unknown_completeness:12}
  };
  const crawl = {phase:'error',ready:false,running:false,posts:1,comments:12,target:20,source:'',results:[],
    message:'DevTools disconnected <img id="unsafe-content" src="x"> Stacktrace: fixture'};
  let crawlerConnected=true;
  const row = {id:'5:10',post_id:'5',comment_id:'10',text_raw:'Bình luận mẫu',text_clean:'bình luận mẫu',
    text_hash:'hash',quality:'ready',label:'toxic',label_source:'automatic',model_score:.6,label_threshold:.5,
    label_model:'fixture-model',label_revision:'revision-123',needs_review:true,annotation_note:''};
  await page.route(baseURL+'/api/**', route => {
    if(route.request().method()!=='GET')throw Error('UI check attempted a real mutation');
    const path=new URL(route.request().url()).pathname;
    if(path==='/api/status')return route.fulfill({json:status});
    if(path==='/api/rows')return route.fulfill({json:{rows:[row],total:1}});
    if(path==='/api/report')return route.fulfill({body:'# Báo cáo\nNội dung mẫu.'});
    throw Error('Unexpected UI fixture endpoint: '+path);
  });
  await page.route(baseURL+'/status', route=>crawlerConnected?route.fulfill({json:crawl}):route.abort('connectionrefused'));
  try {
    await page.goto(baseURL+'/#data');
    await page.waitForSelector('.label-form');
    check(!(await page.locator('#annotation-status').innerText()).includes('.onnx'),'Model filename is absent from the main processing status');
    check((await page.locator('#annotation-debug').textContent()).includes('24%'),'Detailed download progress is retained');
    check(!await page.locator('.clean-text').isVisible(),'Normalized content and IDs are collapsed by default');
    await page.locator('#data-rows .row-detail > summary').first().click();
    check(await page.locator('.clean-text').isVisible(),'Original-source details remain available');
    check(!await page.locator('.label-suggestion small').isVisible(),'Model revision is collapsed by default');
    check((await page.locator('.label-suggestion').innerText()).includes('Cần kiểm tra'),'Uncertain label warning stays visible');
    await page.locator('.label-suggestion summary').click();
    check((await page.locator('.label-suggestion').innerText()).includes('0.600'),'Label score is available on demand');
    await page.locator('.skip-link').focus();
    await page.keyboard.press('Enter');
    check(page.url().endsWith('#data')&&await page.locator('main').evaluate(e=>e===document.activeElement),'Skip link focuses content without changing the current screen');

    status.annotation_job={running:false,error:true,message:'ONNX exception <img id="unsafe-content" src="x">'};
    status.job={running:false,error:true,message:'Training exception <img id="unsafe-content" src="x">'};
    await page.evaluate(status=>renderStatus(status),status);
    check(!(await page.locator('#annotation-status').innerText()).includes('ONNX'),'Labeling error has a readable summary');
    await page.locator('nav [data-tab="models"]').click();
    check(!(await page.locator('#training-status').innerText()).includes('exception')&&!await page.locator('#training-debug').isVisible(),'Training errors are collapsed behind a readable summary');
    await page.locator('#training-detail summary').click();
    check((await page.locator('#training-debug').innerText()).includes('Training exception'),'Original training error remains accessible');
    await page.locator('nav [data-tab="crawl"]').click();
    check(!(await page.locator('#crawl-message').innerText()).includes('DevTools')&&!await page.locator('#crawl-debug').isVisible(),'Chrome error details are hidden by default');
    await page.locator('#crawl-detail summary').click();
    check((await page.locator('#crawl-debug').innerText()).includes('DevTools'),'Original Chrome error remains accessible');
    check(!await page.locator('.history-panel').evaluate(e=>e.open),'Technical post history starts collapsed');
    check(await page.locator('#unsafe-content').count()===0,'Error messages are escaped as text');
    await page.evaluate(()=>toast('Traceback <img id="unsafe-toast" src="x">',true));
    check(await page.locator('#toast details').count()===1&&!await page.locator('#toast pre').isVisible()&&await page.locator('#unsafe-toast').count()===0,'Technical toast errors are collapsed and escaped');
    await page.evaluate(()=>document.querySelector('#toast').hidden=true);

    await page.locator('#source-url').fill('https://www.facebook.com/groups/123');
    await page.locator('#target').fill('2');
    crawl.phase='ready';crawl.ready=true;crawl.message='Sẵn sàng';
    await page.waitForFunction(()=>document.querySelector('#crawl-phase').textContent==='Sẵn sàng');
    crawlerConnected=false;
    await page.waitForFunction(()=>document.querySelector('#crawl-phase').textContent==='Mất kết nối');
    check(await page.locator('#browser-open').isDisabled()&&await page.locator('#start').isDisabled()&&await page.locator('#stop').isDisabled(),'Connection loss disables all crawler actions');
    check((await page.locator('#crawl-message').innerText()).includes('MO_CONG_CU.cmd')&&await page.locator('#crawl-message').evaluate(e=>e.classList.contains('annotation-error')),'Connection loss replaces stale readiness with a recovery instruction');
    check(!await page.locator('#crawl-debug').isVisible()&&await page.locator('#source-url').inputValue()==='https://www.facebook.com/groups/123'&&await page.locator('#target').inputValue()==='2','Connection loss hides stale technical errors and preserves collection settings');
    crawlerConnected=true;
    await page.waitForFunction(()=>document.querySelector('#crawl-phase').textContent==='Sẵn sàng');
    check(!await page.locator('#start').isDisabled()&&await page.locator('#browser-open').isDisabled()&&await page.locator('#stop').isDisabled(),'Crawler controls recover automatically after reconnection');
    check(!(await page.locator('#crawl-message').evaluate(e=>e.classList.contains('annotation-error'))),'Reconnection clears the connection error');

    for(const width of [375,768,1024,1440]) {
      await page.setViewportSize({width,height:900});
      for(const tab of ['overview','crawl','data','models','report']) {
        await page.locator('nav [data-tab="'+tab+'"]').click();
        check(await page.locator('#breadcrumb').innerText()===await page.locator('nav [data-tab="'+tab+'"]').getAttribute('aria-label'),`Navigation keeps its full label: ${tab}, ${width}px`);
        check(await page.evaluate(()=>document.scrollingElement.scrollWidth<=document.scrollingElement.clientWidth),`No page overflow: ${tab}, ${width}px`);
      }
      if(width<1024) {
        await page.evaluate(()=>scrollTo(0,document.body.scrollHeight));
        check(await page.locator('nav').evaluate(e=>e.getBoundingClientRect().top>=0&&e.getBoundingClientRect().bottom<=innerHeight),`Navigation remains reachable while scrolling at ${width}px`);
      }
    }
    return passed;
  } finally {
    await page.unroute(baseURL+'/api/**');await page.unroute(baseURL+'/status');
  }
}
if(typeof module!=='undefined')module.exports={checkInterfaceBrowser};
