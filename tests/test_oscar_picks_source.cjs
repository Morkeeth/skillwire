'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('site/app.js','utf8');
const actual=source.slice(source.indexOf('async function renderOscarPicks'),source.indexOf('async function boot'));
class Node{constructor(tag,cls,text){Object.assign(this,{tag,cls,text,children:[]});}append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;}}
const nodes={'#oscar-picks-list':new Node('div'),'#oscar-picks-preview':new Node('div')};
const picks=JSON.parse(fs.readFileSync('site/oscar-picks.json','utf8'));
const catalog=JSON.parse(fs.readFileSync('evidence/hosted-catalog.json','utf8'));
const byId=new Map(catalog.skills.map(s=>[s.id,s]));let inspected=null,fail=false;
const context={$:s=>nodes[s],el:(...a)=>new Node(...a),byId,inspect:id=>{inspected=id;},fetch:async path=>{assert.equal(path,'oscar-picks.json');return {ok:!fail,json:async()=>picks};}};
vm.createContext(context);vm.runInContext(actual,context);
(async()=>{
 await context.renderOscarPicks();
 assert.equal(nodes['#oscar-picks-preview'].children.length,3);
 const entries=nodes['#oscar-picks-list'].children.filter(n=>n.cls==='oscar-pick');
 assert.equal(entries.length,20);
 for(let i=0;i<entries.length;i++){
  const pick=picks.picks[i],entry=entries[i],button=entry.children.find(n=>n.tag==='button');
  assert.equal(Boolean(button),Boolean(pick.catalog_id&&byId.has(pick.catalog_id)));
  if(button){assert.equal(byId.get(pick.catalog_id).name,pick.name);button.onclick();assert.equal(inspected,pick.catalog_id);}
  assert(entry.children.some(n=>n.cls==='pick-provenance'&&n.text.includes(pick.basis)));
 }
 assert.equal(picks.picks.filter(p=>p.kind==='working-set').length,18);
 assert.equal(picks.picks.filter(p=>p.kind==='try-next').length,2);
 assert(picks.picks.filter(p=>p.kind==='try-next').every(p=>p.basis.includes('no observed Oscar usage')));
 const plan=picks.picks.find(p=>p.name==='plan');assert.equal(plan.catalog_id,null,'Generic same-name plan is not Oscar’s local skill');
 fail=true;await context.renderOscarPicks();assert(nodes['#oscar-picks-preview'].children[0].text.includes('full catalogue'));
 console.log(JSON.stringify({passed:5,scope:'Actual picks renderer with real published catalogue: all20 rows, verified links and local-only fallback, separate recommendations/provenance, generic-name collision rejected, fetch failure leaves full catalogue available. No browser/network/model.'}));
})().catch(e=>{console.error(e);process.exitCode=1;});
