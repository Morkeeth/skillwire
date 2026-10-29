/* Editorial recommendations are separate from catalog sort and paid placement. */
'use strict';
(async()=>{
  const host=document.querySelector('#research-picks');
  try {
    const response=await fetch('research-picks.json');
    if(!response.ok)throw Error('Source review unavailable');
    const data=await response.json();
    for(const pick of [...data.picks].sort((a,b)=>a.rank-b.rank)){
      const card=el('article','research-pick');card.dataset.editorialRank=String(pick.rank);
      card.append(el('small','','#'+pick.rank+' · '+pick.job),el('h2','',pick.name),el('p','pick-reason',pick.reason));
      const context=el('details','pick-evidence');context.append(el('summary','','Evidence and limits'),el('p','',pick.why));
      const evidence=el('p','research-evidence');evidence.append(el('strong','','Evidence: '),document.createTextNode(pick.evidence));context.append(evidence);
      const limits=el('p','research-limit');limits.append(el('strong','','Limits: '),document.createTextNode(pick.limits));context.append(limits);card.append(context);
      const links=el('div','research-links');links.append(link('Read reviewed source ↗',pick.source));
      if(pick.catalog_id){const b=el('button','classic-button','Find pinned catalog version');b.type='button';b.onclick=()=>{if(!byId.has(pick.catalog_id)){b.textContent='Catalog still loading — try again';return;}showTab('search');inspect(pick.catalog_id);};links.append(b);}
      card.append(links,el('small','research-date','Editorial order '+data.ranked_at+' · Source checked '+data.checked_at+' · '+pick.version_note));host.append(card);
    }
    const details=el('details','research-method');details.append(el('summary','','How these picks were chosen'));
    details.append(el('p','',data.ranking_basis),el('p','',data.method),el('p','',data.coverage));
    for(const item of data.longlist){const p=el('p','');p.append(link(item.repo+' ↗',item.source),document.createTextNode(' — '+item.decision));details.append(p);}host.append(details);
  }catch(error){host.replaceChildren(el('p','','Research picks could not load. The full catalog is still available.'));}
})();
