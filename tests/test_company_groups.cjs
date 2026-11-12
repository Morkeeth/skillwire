/* Run against the real offline catalog and unchanged source identities. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const {companyFor,createClassifier,groupRows}=require('../site/company-groups.js');
const catalog=JSON.parse(execFileSync('python3',['-c','import json,published_catalog;print(json.dumps(published_catalog.load()))'],{cwd:root,maxBuffer:100*1024*1024}));
const before=JSON.stringify(catalog),classifier=createClassifier(catalog),slots=groupRows(catalog.skills,classifier);
const flatten=slots=>slots.flatMap(s=>s.kind==='company'?s.members:[s.skill]);
assert.equal(flatten(slots).length,catalog.skills.length);
assert.deepEqual(new Set(flatten(slots).map(s=>s.id)),new Set(catalog.skills.map(s=>s.id)));
for(const skill of flatten(slots))assert.equal(skill,catalog.skills.find(s=>s.id===skill.id),'Never clone or replace skill evidence');
assert.equal(JSON.stringify(catalog),before,'Catalog/source/evaluation bytes must not change');
const find=catalog.skills.find(s=>s.name==='find-skills'&&s.repo==='vercel-labs/skills');
assert.ok(find);assert.equal(classifier.get(find.id),null);assert.ok(slots.some(x=>x.skill===find));
for(const name of ['vercel-react-best-practices','vercel-composition-patterns','supabase-postgres-best-practices','pdf','xlsx']){
 const matches=catalog.skills.filter(s=>s.name===name);assert.ok(matches.length,name);
 for(const skill of matches)assert.equal(classifier.get(skill.id),null,name+' is general-purpose');
}
const vercel=slots.filter(x=>x.id==='vercel'),heygen=slots.filter(x=>x.id==='heygen');
assert.equal(vercel.length,1);assert.equal(heygen.length,1);
assert.ok(vercel[0].members.some(s=>s.name==='deploy-to-vercel'));
const hyperframes=catalog.skills.filter(s=>s.repo==='heygen-com/hyperframes');
assert.equal(hyperframes.length,20);for(const skill of hyperframes)assert.ok(heygen[0].members.includes(skill));
// Group *after* search/filter/sort: never smuggle unmatched entries into a result.
const filtered=catalog.skills.filter(s=>s.name.includes('vercel')&&s.category==='Development').reverse();
const grouped=groupRows(filtered,classifier);
assert.deepEqual(new Set(flatten(grouped).map(s=>s.id)),new Set(filtered.map(s=>s.id)));
for(const group of grouped.filter(s=>s.kind==='company'))assert.deepEqual(group.members,filtered.filter(s=>classifier.get(s.id)?.id===group.id));
// Unknown owner/name remains separate; substring lookalikes do not acquire a company.
const unknown={id:'unknown',name:'vercellular',repo:'someone/general',source:'unchanged'};
assert.equal(companyFor(unknown,catalog),null);
assert.equal(companyFor({...unknown,name:'vercel-deploy'},{skills:[],sources:[]}),null);
const sample=[vercel[0].members[0],find,vercel[0].members[1],unknown];
assert.deepEqual(groupRows(sample,classifier).map(s=>s.kind),['company','skill','skill']);
// Paginating slots rather than member rows prevents a company appearing twice.
const paged=[...slots.slice(0,150),...slots.slice(150,300)];
assert.equal(new Set(paged.filter(s=>s.kind==='company').map(s=>s.id)).size,paged.filter(s=>s.kind==='company').length);
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
assert.ok(html.indexOf('company-groups.js')<html.indexOf('src="app.js"'));
console.log(JSON.stringify({status:'PASS',skills:catalog.skills.length,spots:slots.length,groups:slots.filter(s=>s.kind==='company').map(s=>({company:s.label,members:s.members.length})),findSkills:{id:find.id,separate:true},catalogUnchanged:true},null,2));
