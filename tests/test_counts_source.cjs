/* Exercise actual client functions without a browser or a public API write. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('site/votes.js','utf8'),app=fs.readFileSync('site/app.js','utf8'),html=fs.readFileSync('site/index.html','utf8');
function code(start,end){return source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));}
(async()=>{
 let resolve,calls=0,renders=0;const c={Promise,Date,fetch:()=>{calls++;return new Promise(r=>resolve=r)},render:()=>renders++,setStatus:()=>{},decorate:()=>{}};
 vm.createContext(c);vm.runInContext("let state=null,busy=false,lastError='',available=false,revision=0,refreshPromise=null,lastRefreshAt=0;"+code(' function refresh(){',' async function cast('),c);
 const first=vm.runInContext('refresh()',c),second=vm.runInContext('refresh()',c);assert.equal(first,second);assert.equal(calls,1);
 resolve({ok:true,json:async()=>({csrf:'fixture',counts:{skill:{up:3,down:1,score:2}},mine:{},total:4,updated_at:'2026-11-06T12:00:00Z'})});await first;assert.equal(renders,1);assert.equal(vm.runInContext('state.counts.skill.up',c),3);
 vm.runInContext('busy=true',c);await vm.runInContext('refresh()',c);assert.equal(calls,1);vm.runInContext('busy=false',c);
 const stale=vm.runInContext('refresh()',c);vm.runInContext('revision++',c);resolve({ok:true,json:async()=>({csrf:'stale',counts:{skill:{up:999}},mine:{}})});await stale;assert.equal(vm.runInContext('state.counts.skill.up',c),3);assert.equal(renders,1);
 const ids=['67b1408b4733c4e8','b51c2b13d57294e2','815857216131ba87'];
 assert.deepEqual(ids,JSON.parse(fs.readFileSync('site/research-picks.json')).picks.slice(0,3).map(p=>p.catalog_id));
 let replacements=0;const rows=ids.map(()=>{const b={setAttribute(){},textContent:'',disabled:false},o={textContent:''};return {b,o,querySelector:q=>q==='output'?o:b}}),list={dataset:{pollIds:ids.join(',')},children:rows,replaceChildren(){replacements++;throw Error('Same-ID poll nodes must stay still')}};
 const pc={document:{querySelector:q=>q==='#landing-poll'?{}:list},byId:new Map(ids.map(id=>[id,{name:id,repo:'fixture'}])),node:()=>{throw Error('No poll node rebuild on counts update')}};
 vm.createContext(pc);vm.runInContext('let poll='+JSON.stringify(ids)+',state={counts:{},mine:{}},available=true,busy=false;'+code(' function renderPoll(){',' function render(rebuild'),pc);const button=rows[0].b;
 vm.runInContext('state.counts[poll[0]]={up:7};state.mine[poll[0]]=1;renderPoll()',pc);assert.equal(rows[0].o.textContent,'7 votes');assert.equal(rows[0].b,button);assert.equal(rows[0].b.textContent,'Your pick ✓');assert.equal(replacements,0);
 assert(!html.includes('Refresh counts'));assert(!html.includes('<th>Rating</th>'));assert(!html.includes('Curated top 6'));
 assert(source.includes("document.addEventListener('visibilitychange'"));assert(!source.includes("fetch('catalog.json'"));assert(source.includes('if(refreshPromise)return refreshPromise'));
 assert(app.includes("view='all'"));assert(app.includes("$('#popular-view').onclick=()=>{view='popular'"));assert(app.includes('renderedFilterKey===filterCache?.key'));
 const inputs={'#query':{value:''},'#harness-filter':{value:''},'#model-filter':{value:''}};
 const skills=[{id:'p',name:'Popular',problem:'debug',repo:'a/repo',models:['Codex'],target_models:{families:[]},category:'Code',stars:1},{id:'other',name:'Other',problem:'video',repo:'b/repo',models:['Claude'],target_models:{families:[]},category:'Media',stars:2}];
 const fc={$:q=>inputs[q],catalog:{skills,popular_ids:['p']},popularRanks:new Map([['p',0]]),searchText:new Map(skills.map(x=>[x.id,[x.name,x.problem,x.repo,...x.models].join(' ').toLowerCase()])),measured:()=>false};vm.createContext(fc);
 const scope=app.slice(app.indexOf('function activeScope()'),app.indexOf('function renderFilters()'));
 vm.runInContext("let category='all',evidence='all',view='all',popularSearchPinned=false,order='popular',direction=1,filterCache=null;"+scope,fc);
 const all=vm.runInContext('filtered()',fc);assert.equal(all.length,2);assert.equal(all[0].id,'p');assert.equal(vm.runInContext('filtered()',fc),all);
 inputs['#query'].value='video';const match=vm.runInContext('filtered()',fc);assert.equal(match.length,1);assert.equal(match[0].id,'other');assert.notEqual(match,all);
 console.log(JSON.stringify({passed:10,scope:'Actual refresh and poll functions; coalescing, busy guard, stale-response rejection, fixed original poll IDs, stable nodes, controls removed, visibility trigger, full-catalog default, actual filter caching and outside-Popular search. No browser/network/model or measured performance claim.'}));
})().catch(e=>{console.error(e);process.exitCode=1});
