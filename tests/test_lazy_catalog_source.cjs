'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const source=fs.readFileSync('site/app.js','utf8');
const functions=source.slice(source.indexOf('const detailRequests='),source.indexOf('function downloadMotion'));
let body,requests=0;
const skills=[{id:'a',sha256:'same-a',revision:'same-rev',detail_bucket:'00'},{id:'b',sha256:'same-b',revision:'same-rev',detail_bucket:'00'}];
function encoded(rows){return JSON.stringify({skills:rows});}
function url(raw){return 'catalog-cache/detail-'+crypto.createHash('sha256').update(raw).digest('hex').slice(0,16)+'.json';}
body=encoded(skills.map(s=>({...s,folder_files:[{path:'original'}]})));
const catalog={skills,detail_shards:{'00':url(body)}};
const context={catalog,byId:new Map(skills.map(s=>[s.id,s])),crypto:crypto.webcrypto,TextEncoder,Uint8Array,Map,Set,Error,JSON,fetch:async(path,options)=>{requests++;assert.strictEqual(path,catalog.detail_shards['00']);assert.strictEqual(options.cache,'force-cache');await Promise.resolve();return {ok:true,text:async()=>body};}};
vm.createContext(context);vm.runInContext(functions,context);
(async()=>{
 await vm.runInContext("Promise.all([loadSkillDetails('a'),loadSkillDetails('b')])",context);
 assert.strictEqual(requests,1);assert.strictEqual(context.byId.get('a').details_loaded,true);assert.strictEqual(context.byId.get('b').folder_files[0].path,'original');
 await vm.runInContext("loadSkillDetails('a')",context);assert.strictEqual(requests,1);
 // Same cached URL, altered HTTP body: actual SHA implementation must reject without poisoning a row.
 context.byId.get('a').details_loaded=false;vm.runInContext('detailRequests.clear()',context);body+=' ';
 await assert.rejects(vm.runInContext("loadSkillDetails('a')",context),/bytes changed/);
 assert.strictEqual(context.byId.get('a').details_loaded,false);
 // Correct bytes/hash but wrong pinned source identity must also fail.
 body=encoded([{id:'a',sha256:'wrong',revision:'same-rev'}]);catalog.detail_shards['00']=url(body);
 await assert.rejects(vm.runInContext("loadSkillDetails('a')",context),/identity changed/);
 assert.strictEqual(context.byId.get('a').sha256,'same-a');
 assert(!source.includes('Refresh counts'));assert(source.includes("document.documentElement.dataset.catalogIndex||'catalog.json'"));
 console.log(JSON.stringify({passed:5,scope:'Actual lazy loader: coalescing, cached reuse, real SHA byte drift rejection, source identity drift rejection, small-index boot path. No browser/network/model.'}));
})().catch(error=>{console.error(error);process.exitCode=1;});
