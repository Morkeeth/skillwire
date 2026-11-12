/* Anonymous community preferences, separate from usage, editorial rank and evaluations. */
'use strict';
(()=>{
 let state=null,busy=false,lastError='',available=false,revision=0,refreshPromise=null,lastRefreshAt=0;
 const status=document.querySelector('#vote-status'),ranking=document.querySelector('#vote-ranking');
 const landingStatus=document.querySelector('#landing-vote-status'),landingRanking=document.querySelector('#landing-vote-ranking');
 function setStatus(text){status.textContent=text;if(landingStatus)landingStatus.textContent=text;}
 let pendingKey=null;
 function clearPendingKey(){pendingKey=null;try{sessionStorage.removeItem('skillwire-pending-direction')}catch{}}
 function firstRequestKey(){if(pendingKey)return pendingKey;try{pendingKey=sessionStorage.getItem('skillwire-pending-direction')}catch{}if(!/^[a-f0-9]{48}$/.test(pendingKey||'')){pendingKey=Array.from(crypto.getRandomValues(new Uint8Array(24)),x=>x.toString(16).padStart(2,'0')).join('');try{sessionStorage.setItem('skillwire-pending-direction',pendingKey)}catch{}}return pendingKey;}
 function node(tag,text,cls=''){const e=document.createElement(tag);e.textContent=text;e.className=cls;return e;}
 function group(id,name){const g=node('div','','direction-vote');g.dataset.directionId=id;g.dataset.directionName=name;for(const value of [1,-1]){const b=node('button',value===1?'▲':'▼','classic-button');b.type='button';b.dataset.value=String(value);b.onclick=e=>{e.stopPropagation();cast(id,state?.mine[id]===value?0:value);};if(value===-1)g.append(node('output','—','direction-score'));g.append(b);}g.append(node('small','','direction-totals'));update(g);return g;}
 function update(g){const id=g.dataset.directionId,c=state?.counts[id]||{up:0,down:0,score:0},choice=state?.mine[id]||0;g.querySelector('output').textContent=state?(c.score>0?'+':'')+c.score:'—';g.querySelector('output').setAttribute('aria-label','Net community votes for '+g.dataset.directionName);g.querySelector('small').textContent=state?c.up+' up · '+c.down+' down':'';g.querySelectorAll('button').forEach(b=>{const v=Number(b.dataset.value),selected=choice===v;b.setAttribute('aria-pressed',String(selected));b.setAttribute('aria-label',(v===1?'Upvote ':'Downvote ')+g.dataset.directionName+(selected?', selected; tap to undo':''));b.title=(v===1?'Useful':'Not for me')+(selected?' · tap again to undo':'');b.disabled=busy||!available;});g.classList.toggle('has-choice',!!choice);}
 function decorate(){document.querySelectorAll('#results tr[data-id]').forEach(row=>{if(!byId.get(row.dataset.id)?.local_bundle&&!row.querySelector('[data-direction-id]')){const cell=row.querySelector('.vote-cell'),name=row.querySelector('.skill-download')?.textContent;if(cell&&name)cell.append(group(row.dataset.id,name));}});document.querySelectorAll('[data-direction-id]').forEach(update);}
 function rankedSkills(query=''){
  const popular=new Set(catalog.popular_ids);
  const skills=catalog.skills.filter(s=>!s.local_bundle&&(query||popular.has(s.id)||state?.counts[s.id])&&[s.name,s.repo,s.problem].join(' ').toLowerCase().includes(query));
  return skills.sort((a,b)=>(state?.counts[b.id]?.score||0)-(state?.counts[a.id]?.score||0)||(state?.counts[b.id]?.up||0)-(state?.counts[a.id]?.up||0)||((catalog.popular_ids.indexOf(a.id)+1||1e6)-(catalog.popular_ids.indexOf(b.id)+1||1e6))||a.name.localeCompare(b.name));
 }
 function skillRow(s){
  const row=node('article','','community-file'),info=node('div','','community-info');
  const name=node('button',s.name,'community-name');name.type='button';name.onclick=()=>inspect(s.id);info.append(name);
  const a=node('a',s.repo,'community-source');a.href=s.source;a.rel='noopener noreferrer';info.append(a,node('p',s.problem,'community-description'));
  row.append(info,group(s.id,s.name));return row;
 }
 // A/B/C poll over the same direction votes: an up vote is a poll choice, so counts are never separate or seeded.
 let poll=[];
 function loadPoll(){poll=['67b1408b4733c4e8','b51c2b13d57294e2','815857216131ba87'].filter(id=>byId.get(id)&&!byId.get(id).local_bundle);render();}
 async function pollVote(id){if(!state||busy||!available)return;if(state.mine[id]===1){await cast(id,0);return;}for(const other of poll)if(other!==id&&state.mine[other]===1)await cast(other,0);await cast(id,1);}
 function renderPoll(){
  const box=document.querySelector('#landing-poll'),list=document.querySelector('#landing-poll-options');if(!box||!list)return;
  box.hidden=poll.length<3;if(box.hidden)return;
  if(list.dataset.pollIds!==poll.join(',')){
   list.replaceChildren(...poll.map((id,i)=>{const s=byId.get(id),row=node('article','','community-file poll-option'),info=node('div','','community-info'),letter='ABC'[i];row.dataset.pollId=id;
    const name=node('button',letter+' · '+s.name,'community-name');name.type='button';name.onclick=()=>inspect(id);info.append(name,node('p',s.repo,'community-description'));
    const b=node('button','Vote '+letter,'classic-button poll-vote');b.type='button';b.onclick=()=>pollVote(id);row.append(info,node('output','—','poll-count'),b);return row;}));list.dataset.pollIds=poll.join(',');
  }
  [...list.children].forEach((row,i)=>{const id=poll[i],up=state?.counts[id]?.up||0,mine=state?.mine[id]===1,b=row.querySelector('.poll-vote');b.textContent=mine?'Your pick ✓':'Vote '+'ABC'[i];b.setAttribute('aria-pressed',String(mine));b.disabled=!available||busy;row.querySelector('output').textContent=state?up+(up===1?' vote':' votes'):'—';});
 }
 function render(rebuild=false){
  renderPoll();
  if(!catalog?.skills)return;
  if((rebuild||!ranking.children.length)&&!document.querySelector('#content-votes').hidden){
   const query=document.querySelector('#community-query').value.toLowerCase().trim(),skills=rankedSkills(query);
   ranking.replaceChildren();document.querySelector('#community-count').textContent=skills.length+' skills';
   for(const s of skills.slice(0,100))ranking.append(skillRow(s));
   if(!skills.length)ranking.append(node('p','No matches. Try another skill or repository.','community-empty'));
   if(skills.length>100)ranking.append(node('p','Showing the first 100 matches. Narrow your search to see more.','community-empty'));
  }
  if(landingRanking)landingRanking.hidden=!state||state.total===0;
  if(landingRanking&&!landingRanking.children.length&&byId.size){for(const s of rankedSkills().slice(0,4))landingRanking.append(skillRow(s));}
  setStatus(lastError||(state?state.total+' preferences · updated '+new Date(state.updated_at).toLocaleTimeString()+'. Tap your vote again to undo.':'Loading community preferences…'));decorate();
 }
 function refresh(){
  if(busy)return Promise.resolve();if(refreshPromise)return refreshPromise;
  const started=revision;
  refreshPromise=(async()=>{try{const r=await fetch('/api/directions',{credentials:'same-origin',cache:'no-store'});const d=await r.json();if(started!==revision)return;if(!r.ok)throw Error(d.error||'Voting unavailable');state=d;available=!!d.csrf;lastError=d.read_only_reason||'';lastRefreshAt=Date.now();render();}catch(e){if(started!==revision)return;available=false;lastError='Community votes could not refresh: '+e.message+'. Counts will retry automatically.';setStatus(lastError);decorate();}finally{refreshPromise=null;}})();return refreshPromise;
 }
 async function cast(id,value){if(!available||!state||busy)return;busy=true;revision++;decorate();setStatus('Saving your preference…');const focus=document.activeElement?.dataset.value;try{const r=await fetch('/api/direction',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:id,value,csrf:state.csrf,request_key:state.has_identity?undefined:firstRequestKey(),website:document.querySelector('#vote-website').value})});if(r.status>=400&&r.status<500)clearPendingKey();const d=await r.json();if(!r.ok)throw Error(d.error||'Your preference was not confirmed.');state=d;if(d.has_identity)clearPendingKey();lastError=value===0?'Your vote was removed.':'Your vote is saved. Tap again to undo.';}catch(e){lastError=e.message+' Counts may be stale. They will retry automatically.';available=false;}finally{busy=false;render();const g=[...document.querySelectorAll('[data-direction-id]')].find(g=>g.dataset.directionId===id&&g.getClientRects().length);g?.querySelector('button[data-value="'+focus+'"]')?.focus({preventScroll:true});}}
 document.querySelector('#landing-vote-all').onclick=()=>showTab('votes');
 document.querySelector('#landing-vote-details').onclick=()=>{showTab('votes');const details=document.querySelector('#content-votes details');details.open=true;details.scrollIntoView({block:'start'});};
 document.querySelector('#vote-browse').onclick=()=>{showTab('search');document.querySelector('#query').focus();};document.querySelector('#community-query').oninput=()=>render(true);document.querySelector('#community-search').onsubmit=e=>{e.preventDefault();render(true);};
 new MutationObserver(()=>render()).observe(document.querySelector('#results'),{childList:true});decorate();refresh();
 new MutationObserver(()=>{if(!poll.length&&byId.size)loadPoll();}).observe(document.querySelector('#skill-count'),{childList:true,characterData:true,subtree:true});if(byId.size)loadPoll();
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastRefreshAt>=5000)refresh();});
 new MutationObserver(()=>{if(!document.querySelector('#content-votes').hidden){render(true);if(Date.now()-lastRefreshAt>=5000)refresh();}}).observe(document.querySelector('#content-votes'),{attributes:true,attributeFilter:['hidden']});
 setInterval(()=>{if(!document.hidden&&(!document.querySelector('#content-votes').hidden||!document.querySelector('#content-search').hidden)&&!busy)refresh();},30000);
})();
