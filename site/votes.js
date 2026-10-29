/* Community preference is separate from editorial picks, usage and evaluations. */
'use strict';
(()=>{
 let state=null,busy=false,lastError='',available=false;
 const status=document.querySelector('#vote-status'),ranking=document.querySelector('#vote-ranking');
 function node(tag,text,cls=''){const e=document.createElement(tag);e.textContent=text;e.className=cls;return e;}
 function button(id,name){const b=node('button','Vote · '+(state?.counts[id]||0),'classic-button community-vote');b.type='button';b.dataset.voteId=id;b.dataset.voteName=name;b.setAttribute('aria-label','Vote for '+name);b.onclick=e=>{e.stopPropagation();cast(id);};update(b);return b;}
 function update(b){const count=state?.counts[b.dataset.voteId]||0,chosen=state?.selected_today===b.dataset.voteId;b.textContent=(chosen?'Your vote':'Vote')+' · '+count;b.disabled=busy||!available||!state||!!state.selected_today;}
 function decorate(){document.querySelectorAll('#results tr[data-id]').forEach(row=>{if(!byId.get(row.dataset.id)?.local_bundle&&!row.querySelector('[data-vote-id]')){const cell=row.querySelector('.file-name'),name=row.querySelector('.skill-download')?.textContent;if(cell&&name)cell.append(button(row.dataset.id,name));}});document.querySelectorAll('[data-vote-id]').forEach(update);}
 function render(){if(!state)return;const selected=state.selected_today;status.textContent=lastError||((selected?'Today’s vote counted. ':'Choose a skill below or in Search. ')+state.total+' community vote'+(state.total===1?'':'s')+' · updated '+new Date(state.updated_at).toLocaleTimeString()+' · resets at 00:00 UTC.');ranking.replaceChildren();
  if(!state.ranking.length)ranking.append(node('p','No community votes yet. Find a skill and cast the first vote.'));
  state.ranking.forEach((skill,i)=>{const card=node('article','','research-pick');card.append(node('small','#'+(i+1)+' · '+skill.votes+' community votes'),node('h2',skill.name),node('p',skill.repo),button(skill.id,skill.name));const inspectButton=node('button','Inspect skill','classic-button');inspectButton.type='button';inspectButton.onclick=()=>{showTab('search');inspect(skill.id);};card.append(inspectButton);ranking.append(card);});
  const x=document.querySelector('#x-poll-results');x.replaceChildren();const poll=state.x_poll;x.append(node('h2','X poll'));
  if(!poll?.options)x.append(node('p',poll?.message||'X poll not connected.'));
  else{const a=node('a','Vote or view the original X poll ↗');a.href=poll.post_url;a.rel='noopener noreferrer';x.append(a,node('p','Fetched '+new Date(poll.fetched_at).toLocaleString()+' · '+poll.voting_status+' · separate from on-site votes.'));poll.options.forEach(o=>x.append(node('p',o.label+' · '+o.votes+' votes')));}
  decorate();
 }
 async function refresh(){try{const r=await fetch('/api/votes',{credentials:'same-origin',cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'Voting unavailable');state=d;available=true;lastError='';render();}catch(e){available=false;lastError='Community votes could not refresh. '+(state?'The last shown counts may be stale. ':'Please try again shortly.');status.textContent=lastError;document.querySelectorAll('[data-vote-id]').forEach(b=>b.disabled=true);}}
 async function cast(id){if(!available||!state||busy||state.selected_today)return;busy=true;decorate();status.textContent='Counting your vote…';let message='';try{const r=await fetch('/api/vote',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:id,csrf:state.csrf,website:document.querySelector('#vote-website').value})});const d=await r.json();if(!r.ok)throw Error(d.error||'Vote could not be confirmed.');message='Your vote counted. Thank you.';}catch(e){message=e.message;}finally{busy=false;await refresh();if(available)lastError=state.selected_today===id?'Your vote counted. Thank you.':message;render();}}
 document.querySelector('#vote-browse').onclick=()=>{showTab('search');document.querySelector('#query').focus();};document.querySelector('#vote-refresh').onclick=refresh;
 new MutationObserver(decorate).observe(document.querySelector('#results'),{childList:true});decorate();refresh();
 setInterval(()=>{if(!document.hidden&&!document.querySelector('#content-votes').hidden)refresh();},30000);
})();
