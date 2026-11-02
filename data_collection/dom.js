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
 const area=document.querySelector('[role=main]')||document.body;
 const anchors=[...area.querySelectorAll('a[href]')];let candidates=0,rejected=0;
 for(const a of anchors){if(!visible(a)||a.closest('[role=navigation],[role=complementary]'))continue;
 const p=H.postInfo(a.href);if(!p)continue;candidates++;
 const targetGroup=new URL(p.url).pathname.match(/^\/groups\/([^/]+)/)?.[1];
 if(group&&!aliases.has(targetGroup)){rejected++;continue;}
 if(seen.has(p.id))continue;seen.add(p.id);posts.push(p);}
 return {posts,diagnostics:{anchors:anchors.length,articles:area.querySelectorAll('[role=article]').length,candidates,rejected}};
}
if(action==='feed_hover'){
 const area=document.querySelector('[role=main]')||document.body;
 return [...area.querySelectorAll('a[href]')].filter(a=>{
  const rect=a.getBoundingClientRect();
  return visible(a)&&rect.bottom>0&&rect.top<innerHeight&&!H.postInfo(a.href)&&!a.closest('[role=navigation],[role=complementary]')&&(a.querySelector('abbr,time')||/^(?:\d+\s*(?:phút|giờ|ngày|tuần|tháng|năm|m|h|d|w)|vừa xong|just now|yesterday|hôm qua)/i.test(H.clean(a.innerText)));
 }).slice(0,12);
}
if(action==='feed_scroll'){
 const area=document.querySelector('[role=main]')||document.body;
 const targets=[area,...area.querySelectorAll('*')].filter(e=>scrollable(e)&&!e.closest('[role=navigation],[role=complementary],[role=dialog],[role=article]')&&(e===area||e.matches('[role=feed]')||e.querySelector('[role=article]')));
 targets.sort((a,b)=>b.querySelectorAll('[role=article]').length-a.querySelectorAll('[role=article]').length);
 for(let p=area.parentElement;p;p=p.parentElement)if(scrollable(p))targets.push(p);
 return scrollDown([...targets,document.scrollingElement]);
}
const current=H.postInfo(location.href);if(current&&current.id!==expected)return {wrong_source:true};
const identity=root=>{const ids=new Set([...root.querySelectorAll('a[href]')].map(a=>H.postInfo(a.href)?.id).filter(Boolean));return ids;};
const dialogs=[...document.querySelectorAll('[role=dialog]')].filter(visible);
let root=dialogs.find(e=>{const ids=identity(e);return ids.size===1&&ids.has(expected);});
if(!root)root=[...document.querySelectorAll('[role=article]')].find(e=>visible(e)&&!e.parentElement?.closest('[role=article]')&&identity(e).size===1&&identity(e).has(expected));
if(!root&&dialogs.length===1&&current?.id===expected&&!identity(dialogs[0]).size)root=dialogs[0];
if(!root)return {missing_scope:true};
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
 const text=[...e.querySelectorAll('[dir=auto]')].filter(p=>own(p,e)&&visible(p)&&!p.closest('a,button,[role=button]')&&!p.querySelector('[dir=auto]')).map(p=>H.clean(p.innerText)).filter(t=>t&&!H.uiOnly(t)&&!H.expandKind(t,true)).filter((t,i,a)=>a.indexOf(t)===i).join('\n');if(!text)continue;
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
