// Run on an HTTP origin in an isolated Playwright page with helpers.js and dom.js.
async function checkCrawlerBrowser(page, helpers, dom) {
  const passed = [];
  const link = id => `<a href="https://www.facebook.com/groups/ptit/posts/${id}/">Bài ${id}</a>`;
  const comment = id => `<div aria-label="Comment from Student"><a href="https://www.facebook.com/groups/ptit/posts/1/?comment_id=${id}">Student</a><div dir="auto">Nội dung bình luận ${id}</div></div>`;
  const check = (ok, name) => { if (!ok) throw Error(name); passed.push(name); };
  async function setup(html) {
    await page.setContent(`<!doctype html><style>body{margin:0}a{display:inline-block}</style>${html}`);
    await page.addScriptTag({content: helpers});
    await page.evaluate(() => { delete window.__ptitTried; window.scrollTo(0, 0); });
  }
  const run = (action, expected = '1') => page.evaluate(({dom, action, expected}) => new Function(dom).call(window, action, expected), {dom, action, expected});

  await setup(`<main role="main"><div id="feed" role="feed" style="height:220px;overflow:auto;scroll-behavior:smooth"><article role="article" style="height:1400px">${link('1')}</article></div></main>`);
  check((await run('feed')).posts[0].id === '1', 'Feed recognizes post links');
  check((await run('feed_scroll')).moved && await page.$eval('#feed', e => e.scrollTop > 0), 'Nested feed scrolls immediately despite smooth scrolling');
  check(await page.evaluate(() => document.scrollingElement.scrollTop === 0), 'Nested feed does not move the outer page');

  const originalURL=page.url();
  await page.evaluate(()=>history.replaceState(null,'','/groups/450310163844833/'));
  const aliases={data:[{__typename:'Group',id:'450310163844833',url:'https://www.facebook.com/groups/2k5ptit/'},
    {__typename:'Group',id:'999',url:'https://www.facebook.com/groups/another/'}]};
  const aliasLinks='<main role="main"><a href="https://www.facebook.com/groups/2k5ptit/posts/11/">Alias</a><a href="https://www.facebook.com/groups/450310163844833/posts/12/">ID</a><a href="https://www.facebook.com/groups/another/posts/13/">Other group</a></main>';
  await setup(`<script type="application/json">${JSON.stringify(aliases)}</script>${aliasLinks}`);
  const aliasFeed=await run('feed');
  check(aliasFeed.posts.map(p=>p.id).join(',')==='11,12'&&aliasFeed.diagnostics.rejected===1,'Numeric group URL accepts its verified slug and rejects posts from other groups');
  await setup(`<script type="application/json">invalid JSON</script>${aliasLinks}`);
  check((await run('feed')).posts.map(p=>p.id).join(',')==='12','Unverified group aliases remain excluded');
  await page.evaluate(url=>history.replaceState(null,'',url),originalURL);

  await setup(`<main role="main"><article role="article" style="height:1800px">${link('1')}</article></main>`);
  check((await run('feed_scroll')).moved && await page.evaluate(() => scrollY > 0), 'Normal page feed still scrolls');

  await setup('<main role="main"><a id="old" href="#old"><time>1 giờ</time></a><div style="height:1500px"></div><a id="new" href="#new"><time>2 giờ</time></a></main>');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const hovered = await page.evaluate(dom => new Function(dom).call(window, 'feed_hover', '').map(e => e.id), dom);
  check(hovered.join(',') === 'new', 'Timestamp hover does not jump back to offscreen old links');

  await setup(`<div id="dialog" role="dialog" style="height:260px;overflow:auto">${link('2')}<article role="article">${link('1')}<div id="inner" style="height:140px;overflow:auto">${Array.from({length:20}, (_, i) => comment(i)).join('')}</div><div style="height:1200px"></div></article></div>`);
  await page.$eval('#inner', e => { e.scrollTop = e.scrollHeight; });
  check((await run('advance')).moved && await page.$eval('#dialog', e => e.scrollTop > 0), 'Exhausted comment scroller falls back to its enclosing dialog');

  await setup(`<div role="dialog" style="position:fixed;top:0;background:white">${link('2')}<article role="article">${link('1')}${comment('1')}</article></div><div style="height:2400px"></div>`);
  check(!(await run('advance')).moved && await page.evaluate(() => scrollY === 0), 'Short post inside a dialog never scrolls the background feed');

  await setup(`<div role="dialog">${link('1')}<div id="comments"></div><button id="more">Xem tất cả bình luận</button></div>`);
  await page.evaluate(template => {
    window.clicks = 0;
    document.querySelector('#more').onclick = () => {
      document.querySelector('#comments').insertAdjacentHTML('beforeend', template.replaceAll('TEST_ID', String(++window.clicks)));
    };
  }, comment('TEST_ID'));
  for (let i = 0; i < 5; i++) check((await run('advance')).clicked, `Reused load-more button works, batch ${i + 1}`);
  const rows = (await run('read')).rows;
  check(rows.length === 5 && rows[4].comment_id === '5' && rows[4].text_raw === 'Nội dung bình luận 5', 'Comment from labels are read with the correct IDs and text');

  await setup(`<div role="dialog">${link('1')}<div aria-label="Comment from Student"><a href="https://www.facebook.com/student">Student</a><div dir="auto" id="partial">Nội dung...</div><button id="expand">Xem thêm</button></div></div>`);
  const partial = (await run('read')).rows[0];
  await page.evaluate(() => {
    document.querySelector('#partial').textContent = 'Nội dung đầy đủ của bình luận';
    document.querySelector('#expand').remove();
  });
  await page.addScriptTag({content: helpers});
  const expanded = (await run('read')).rows[0];
  check(partial.text_complete === false && expanded.text_complete === true && partial.comment_id === expanded.comment_id, 'Expanding text preserves fallback identity and clears incomplete status');

  await setup(`<div role="dialog">${link('1')}<button id="more">View 10 more comments</button></div>`);
  check((await run('advance')).clicked && (await run('advance')).clicked && !(await run('advance')).clicked, 'Unresponsive load-more button is limited to two attempts');

  const labels = await page.evaluate(() => {
    const H = window.PTITHelpers;
    const accepted = ['Xem tất cả bình luận', 'Xem thêm 5 bình luận', 'Xem 3 câu trả lời', 'Xem các bình luận trước', 'View more comments', 'View 10 more comments', 'See more comments', 'View all replies (10)', '3 replies'];
    const rejected = ['Thích', 'Trả lời', 'Reply', 'Share', 'Gửi', 'Đăng', 'See more', 'Xem tất cả thành viên', 'View all comments and reply'];
    return accepted.every(t => H.expandKind(t) === 'comments') && rejected.every(t => H.expandKind(t) === null) && H.expandKind('Xem thêm', true) === 'text';
  });
  check(labels, 'Only explicit expand-comments/text controls match');
  check((await run('advance', '999')).missing_scope, 'An unrelated post is not operated on');
  await page.evaluate(() => document.body.insertAdjacentHTML('beforeend', '<input type="password">'));
  check((await run('feed_scroll')).blocked && (await run('advance')).blocked, 'Login barriers stop all scrolling');
  return passed;
}
async function checkDashboardScroll(page, baseURL) {
  const passed = [];
  const check = (ok, name) => { if (!ok) throw Error(name); passed.push(name); };
  const status = {phase:'ready', ready:true, running:false, posts:30, comments:30, target:30, source:'', message:'Fixture',
    results:Array.from({length:30}, (_, i) => ({post_id:String(i),count:1,reason:'no_progress'}))};
  await page.route(baseURL + '/status', route => route.fulfill({json:status}));
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height:800});
    await page.goto(baseURL + '/#crawl');
    await page.waitForFunction(() => document.querySelectorAll('#crawl-results tr').length === 30);
    if(!await page.locator('.history-panel').evaluate(e=>e.open))await page.locator('.history-panel > summary').click();
    const stable = await page.evaluate(status => {
      const log = document.querySelector('.crawl-log'), body = document.querySelector('#crawl-results');
      log.scrollTop = 160; log.scrollLeft = 10;
      const top = log.scrollTop, left = log.scrollLeft, row = body.firstElementChild;
      renderCrawler(status);
      const unchanged = row === body.firstElementChild && log.scrollTop === top && log.scrollLeft === left;
      renderCrawler({...status, results:[...status.results, {post_id:'31', count:1, reason:'no_progress'}]});
      return unchanged && log.scrollTop === top && log.scrollLeft === left;
    }, status);
    check(stable, `Log keeps its rows and scroll position across updates at ${width}px`);
    await page.locator('.crawl-log').focus();
    const before = await page.$eval('.crawl-log', e => e.scrollTop);
    await page.keyboard.press('PageDown');
    await page.waitForFunction(before => document.querySelector('.crawl-log').scrollTop > before, before);
    check(true, `Log supports keyboard scrolling at ${width}px`);
    check(await page.$eval('.crawl-log th', e => getComputedStyle(e).position === 'sticky'), `Log header stays visible at ${width}px`);
    for (const tab of ['overview','data','models','report']) {
      await page.goto(baseURL + '/#' + tab);
      if (tab === 'data') await page.waitForSelector('.label-form');
      if (tab === 'report') await page.waitForFunction(() => document.querySelector('.report-preview').textContent.length > 100);
      const layout = await page.evaluate(tab => {
        const d = document.scrollingElement;
        d.scrollTop = 0; d.scrollTop = d.scrollHeight;
        const table = document.querySelector('#' + tab + ' .table-scroll');
        const preview = document.querySelector('#' + tab + ' .report-preview');
        if (table) table.scrollLeft = table.scrollWidth;
        if (preview) preview.scrollTop = preview.scrollHeight;
        return {page:d.scrollHeight <= d.clientHeight || d.scrollTop > 0,
          width:d.scrollWidth <= d.clientWidth,
          table:!table || table.scrollWidth <= table.clientWidth || table.scrollLeft > 0,
          preview:!preview || preview.scrollHeight <= preview.clientHeight || preview.scrollTop > 0};
      }, tab);
      check(Object.values(layout).every(Boolean), `${tab} page and overflowing content are scrollable at ${width}px`);
    }
  }
  await page.unroute(baseURL + '/status');
  return passed;
}
if (typeof module !== 'undefined') module.exports = {checkCrawlerBrowser, checkDashboardScroll};
