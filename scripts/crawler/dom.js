return (()=>{
const H=window.PTITHelpers,action=arguments[0],expected=arguments[1];
const visible=e=>e.isConnected&&e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')&&getComputedStyle(e).visibility!=='hidden';
const blocked=/\/(checkpoint|login|recover|two_step_verification)/i.test(location.pathname)||!!document.querySelector('input[type=password],iframe[src*="captcha"]')||[...document.querySelectorAll('[role=alert]')].some(e=>visible(e)&&/temporarily blocked|too many requests|tạm thời bị chặn|xác minh danh tính/i.test(e.innerText));
if(blocked)return {blocked:true};
const scrollable=e=>visible(e)&&e.clientHeight>60&&e.scrollHeight>e.clientHeight+1&&/(auto|scroll)/.test(getComputedStyle(e).overflowY)&&!e.matches('textarea,input,[contenteditable="true"]');
const scrollDown=targets=>{
 for(const target of new Set(targets.filter(Boolean))){
  const old=target.scrollTop;
  target.scrollTo({top:old+Math.max(180,target.clientHeight*.65),behavior:'instant'});
  if(target.scrollTop>old+1)return {moved:true};
 }
 return {moved:false};
};
if(action==='feed'){
 const posts=[],seen=new Set();
 const group=location.pathname.match(/^\/groups\/([^/]+)/)?.[1];
 const aliases=group?H.groupAliases(group,[...document.querySelectorAll('script[type="application/json"]')].map(s=>s.textContent)):new Set();
 const area=document.body;
 const anchors=[...area.querySelectorAll('a[href]')];let candidates=0,rejected=0;
 for(const a of anchors){if(!visible(a)||a.closest('[role=navigation],[role=complementary]'))continue;
 const p=H.postInfo(a.href);if(!p)continue;candidates++;
 const targetGroup=new URL(p.url).pathname.match(/^\/groups\/([^/]+)/)?.[1];
 if(group&&!aliases.has(targetGroup)){rejected++;continue;}
 if(seen.has(p.id))continue;seen.add(p.id);posts.push(p);}
 return {posts,diagnostics:{anchors:anchors.length,articles:area.querySelectorAll('[role=article]').length,candidates,rejected}};
}
if(action==='feed_hover'){
 const area=document.body;
 return [...area.querySelectorAll('a[href]')].filter(a=>{
  const rect=a.getBoundingClientRect();
  return visible(a)&&rect.bottom>0&&rect.top<innerHeight&&!H.postInfo(a.href)&&!a.closest('[role=navigation],[role=complementary]')&&(a.querySelector('abbr,time')||a.closest('[role=article]')||/^(?:\d+\s*(?:phút|giờ|ngày|tuần|tháng|năm|m|h|d|w)|vừa xong|just now|yesterday|hôm qua)/i.test(H.clean(a.innerText)));
 }).slice(0,30);
}
if(action==='feed_scroll'||action==='feed_retry'){
 const area=document.body;
 const targets=[area,...area.querySelectorAll('*')].filter(e=>scrollable(e)&&!e.closest('[role=navigation],[role=complementary],[role=dialog],[role=article]')&&(e===area||e.matches('[role=feed],[role=main]')||e.querySelector('[role=article]')));
 targets.sort((a,b)=>b.querySelectorAll('[role=article]').length-a.querySelectorAll('[role=article]').length);
 for(let p=area.parentElement;p;p=p.parentElement)if(scrollable(p))targets.push(p);
 const ordered=[...new Set([...targets,document.scrollingElement].filter(Boolean))];
 if(action==='feed_retry'){
  for(const target of ordered){if(target.scrollTop>0){const old=target.scrollTop;target.scrollTo({top:Math.max(0,old-Math.max(300,target.clientHeight*.8)),behavior:'instant'});if(target.scrollTop<old)return {moved:true,retry:true};}}
  return {moved:false,retry:true};
 }
 const result=scrollDown(ordered);
 return {...result,targets:ordered.length,positions:ordered.slice(0,5).map(e=>({role:e.getAttribute('role'),top:e.scrollTop,height:e.clientHeight,total:e.scrollHeight}))};
}
const current=H.postInfo(location.href);if(current&&current.id!==expected)return {wrong_source:true};
const identity=root=>{const ids=new Set([...root.querySelectorAll('a[href]')].map(a=>H.postInfo(a.href)?.id).filter(Boolean));return ids;};
const dialogs=[...document.querySelectorAll('[role=dialog]')].filter(visible);
let root=dialogs.find(e=>{const ids=identity(e);return ids.size===1&&ids.has(expected);});
if(!root)root=[...document.querySelectorAll('[role=article]')].find(e=>visible(e)&&!e.parentElement?.closest('[role=article]')&&identity(e).size===1&&identity(e).has(expected));
if(!root&&dialogs.length===1&&current?.id===expected&&!identity(dialogs[0]).size)root=dialogs[0];
if(!root)return {missing_scope:true};
if(action==='sort'){
 const label=e=>H.clean(e.innerText||e.getAttribute('aria-label')||'');
 const all=/^(?:Tất cả (?:các )?bình luận|All comments)$/i;
 const isAll=e=>all.test(label(e))||[...e.querySelectorAll('span,[dir=auto]')].some(s=>visible(s)&&all.test(label(s)));
 const filtered=/^(?:Phù hợp nhất|Liên quan nhất|Mới nhất|Most relevant|Newest|Top comments)$/i;
 const controls=[...root.querySelectorAll('button,[role=button]')].filter(e=>visible(e)&&!e.closest('[role=menu],[role=listbox]')&&!e.parentElement?.closest('[role=article],[aria-label^="Bình luận của"],[aria-label^="Comment by"],[aria-label^="Comment from"]'));
 const trigger=controls.find(e=>filtered.test(label(e)));
 // A visible menu option is not proof that the active filter has changed.
 if(!trigger&&controls.some(e=>isAll(e)))return {sort_status:'confirmed'};
 if(!trigger)return {sort_status:'unavailable'};
 const states=window.__ptitSortStates||(window.__ptitSortStates=new WeakMap());
 const state=states.get(root)||{attempts:0,opened:false};states.set(root,state);
 if(state.attempts++>=30)return {sort_status:'failed'};
 // Facebook renders the sort menu in a portal outside the post dialog.
 // Only inspect that portal after opening this post's own sort control.
 if(state.opened){
  // Some Facebook layouts use standalone role=button portal entries, without
  // a menu/listbox ancestor. Match their title, including a separate description.
  const option=[...document.querySelectorAll('[role=menuitem],[role=menuitemradio],[role=option],[role=button],button')].find(e=>visible(e)&&e!==trigger&&!e.contains(trigger)&&!e.closest('[role=article]')&&(isAll(e)||all.test(H.clean((e.innerText||e.getAttribute('aria-label')||'').split('\n')[0]))));
  if(option)return {sort_status:'selecting',sort_element:option};
  if(trigger.getAttribute('aria-expanded')==='true')return {sort_status:'waiting'};
 }
 state.opened=true;return {sort_status:'opening',sort_element:trigger};
}
const selector='[role=article],[aria-label^="Bình luận của"],[aria-label^="Comment by"],[aria-label^="Comment from"]';
const own=(node,e)=>node.closest(selector)===e;
const comments=[...root.querySelectorAll(selector)].filter(e=>{
 if(!visible(e)||e.querySelector('[data-ad-preview=message],[data-ad-comet-preview=message]'))return false;
 const labeled=/^(Bình luận của|Comment by|Comment from)/i.test(e.getAttribute('aria-label')||'');
 const hasID=[...e.querySelectorAll('a[href]')].some(a=>own(a,e)&&H.commentInfo(a.href).id);
 const nestedLeaf=!e.querySelector('[role=article]')&&!!e.parentElement?.closest('[role=article]');
 return labeled||hasID||nestedLeaf;
});
if(action==='read'){
 const rows=[];for(const e of comments){const links=[...e.querySelectorAll('a[href]')].filter(a=>own(a,e));if(links.some(a=>{const p=H.postInfo(a.href);return p&&p.id!==expected;}))continue;
 const text=[...e.querySelectorAll('[dir=auto]')].filter(p=>own(p,e)&&visible(p)&&!p.closest('a,button,[role=button]')&&!p.querySelector('[dir=auto]')).map(p=>{const copy=p.cloneNode(true);for(const img of copy.querySelectorAll('img[alt]'))img.replaceWith(document.createTextNode(img.alt));return H.clean(copy.textContent)}).filter(t=>t&&!H.expandKind(t,true)).filter((t,i,a)=>a.indexOf(t)===i).join('\n');if(!text)continue;
 const info=links.map(a=>H.commentInfo(a.href)).find(x=>x.id)||{id:'',parent:''};const author=H.clean(links[0]?.innerText||'');
 const complete=![...e.querySelectorAll('button,[role=button]')].some(b=>own(b,e)&&visible(b)&&H.expandKind(b.innerText,true)==='text');
 rows.push({comment_id:info.id||H.fallbackCommentId(e,expected,author,text,complete),parent_comment_id:info.parent,text_raw:text,text_complete:complete,identifier_quality:info.id?'facebook_comment_id':'fallback_dom_text'});}
 return {rows};
}
if(action==='advance'){
 const tried=window.__ptitTried||(window.__ptitTried=new WeakMap());
 const signature=H.hash(comments.map(c=>H.clean(c.innerText)).join('\n'));
 const attempts=b=>tried.get(b)?.signature===signature?tried.get(b).count:0;
 const button=[...root.querySelectorAll('button,[role=button]')].find(b=>visible(b)&&!b.matches('[disabled],[aria-disabled=true]')&&attempts(b)<2&&H.expandKind(b.innerText,comments.some(c=>c.contains(b))));
 if(button){tried.set(button,{signature,count:attempts(button)+1});button.scrollIntoView({block:'nearest',behavior:'instant'});button.click();return {clicked:true};}
 const targets=[root,...root.querySelectorAll('*')].filter(scrollable);
 targets.sort((a,b)=>b.querySelectorAll(selector).length-a.querySelectorAll(selector).length);
 const dialog=root.closest('[role=dialog]');
 // A post can be nested inside a dialog; never scroll the feed behind it.
 for(let p=root;p;p=p.parentElement){if(scrollable(p))targets.push(p);if(p===dialog)break;}
 if(!dialog)targets.push(document.scrollingElement);
 return scrollDown(targets);
}
return {};
})();
