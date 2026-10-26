'use strict';
// Browser-only consistency review. This does not authenticate a CLI run or prove internal model use.
const trialStatus=document.querySelector('#trial-status');
const trialReport=document.querySelector('#trial-report');
const gateStatus=document.querySelector('#trial-gate-status');
const investigator=document.querySelector('#trial-investigator');
const selectionStatus=document.querySelector('#trial-selection');
const gateInputs=['#trial-blind','#trial-verdict','#trial-key'].map(id=>document.querySelector(id));
let reveal=null,gateVersion=0;

function node(tag,value='',className=''){
 const element=document.createElement(tag);
 element.textContent=String(value);
 if(className)element.className=className;
 return element;
}
function item(label,value,state=''){
 const row=node('div','','trial-item '+state);
 row.append(node('b',label),node('span',value));
 return row;
}
function bytesHex(buffer){return [...new Uint8Array(buffer)].map(x=>x.toString(16).padStart(2,'0')).join('');}
async function digest(file){return bytesHex(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()));}
async function textDigest(value){return bytesHex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)));}
function canonical(value){if(Array.isArray(value))return value.map(canonical);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])]));return value;}
async function jsonFile(file){if(file.size>8*1024*1024)throw Error(file.name+' exceeds the 8 MiB local viewer limit.');try{return JSON.parse(await file.text());}catch(error){throw Error('Invalid JSON: '+file.name);}}
function equal(a,b){return JSON.stringify(a)===JSON.stringify(b);}
function gradeText(grade){if(!grade)return 'No grade';if(grade.status!=='graded')return 'Grader or infrastructure error';return grade.passed===true?'Checks passed':grade.passed===false?'Checks failed':'Grade unknown';}
function currentSelection(){return typeof window.limeTrialSelection==='function'?window.limeTrialSelection():[];}
function showSelection(){
 const selected=currentSelection();
 selectionStatus.classList.toggle('ready',selected.length===1);
 if(selected.length===1){const skill=selected[0];selectionStatus.textContent='Selected for this task: '+skill.name+' · '+skill.repo+' @ '+skill.revision+' · SKILL.md '+skill.sha256+'. Download this one-skill ZIP, then use that same ZIP with --stack in the local kit.';}
 else selectionStatus.textContent=selected.length?'Your stack has '+selected.length+' skills. Keep exactly one selected for a one-skill paired decision.':'Choose exactly one skill in Search for this task. A local private skill can instead be selected by folder in the kit.';
}
window.addEventListener('lime-selection-change',showSelection);
showSelection();

async function updateGate(){
 const version=++gateVersion;
 reveal=null;investigator.hidden=true;document.querySelector('.trial-history').hidden=true;trialReport.hidden=true;trialReport.replaceChildren();
 trialStatus.textContent='No run loaded.';
 if(gateInputs.some(input=>!input.files?.[0])){gateStatus.textContent='Choose the blind bundle, saved verdict and withheld key to open labelled evidence.';return;}
 try{
  const [bundleFile,verdictFile,keyFile]=gateInputs.map(input=>input.files[0]);
  const [bundle,verdict,key]=await Promise.all([jsonFile(bundleFile),jsonFile(verdictFile),jsonFile(keyFile)]);
  if(bundle.schema!=='lime-human-pair-v1'||verdict.schema!==bundle.schema||key.schema!==bundle.schema||!bundle.pair_id||bundle.pair_id!==verdict.pair_id||bundle.pair_id!==key.pair_id)throw Error('Blind bundle, verdict and key do not name the same pair.');
  if((await textDigest(JSON.stringify(canonical(bundle))))!==key.bundle_sha256)throw Error('Blind bundle content does not match the withheld key.');
  if(!['A','B','tie','cannot_judge'].includes(verdict.choice)||verdict.reviewed_both!==true||String(verdict.reason||'').trim().length<15||!Number.isFinite(Date.parse(verdict.reviewed_at_utc)))throw Error('The saved blind verdict is incomplete.');
  if(!key.source?.protocol_sha256||!key.source?.skill_sources_sha256||!key.source?.record_sha256||!key.mapping)throw Error('The reveal key lacks run links.');
  if(version!==gateVersion)return;
  reveal={bundle,verdict,key};investigator.hidden=false;document.querySelector('.trial-history').hidden=false;
  const testVerdict=/synthetic|automated interface probe/i.test(String(verdict.limit||'')+' '+verdict.reason);
  gateStatus.textContent=(testVerdict?'TEST VERDICT — no human choice. ':'')+'Blind '+verdict.choice+' choice loaded for pair '+bundle.pair_id.slice(0,12)+'… . Now inspect the matching run. This local verdict is unauthenticated.';
 }catch(error){if(version===gateVersion)gateStatus.textContent=error.message;}
}
gateInputs.forEach(input=>input.addEventListener('change',updateGate));

function pickRunFiles(files){
 const required=['plan.json','protocol.json','protocol-freeze.json','SKILL-SOURCES.json','artifact-results.json','records.json'];
 const picked={},optional={};
 for(const file of files){
  if(file.size>8*1024*1024)continue;
  const relative=file.webkitRelativePath||'';
  if(relative.includes('/model-runs/')){
   const arm=relative.includes('/with/')?'with':relative.includes('/without/')?'without':null;
   if(arm&&file.name==='stdout.jsonl')optional[arm+'-trace']=file;
   if(arm&&file.name==='record.json')optional[arm+'-record']=file;
   if(file.name!=='records.json')continue;
  }
  if(['TASK.md','grader.py'].includes(file.name)&&(!relative||relative.split('/').length===2)){optional[file.name]=file;continue;}
  if(!required.includes(file.name))continue;
  if(file.name==='records.json'&&relative&&!relative.includes('/model-runs/'))continue;
  if(picked[file.name])throw Error('Choose one run folder; duplicate '+file.name);
  picked[file.name]=file;
 }
 for(const name of required)if(!picked[name])throw Error('Missing '+name+'. Choose the complete run folder or all six JSON receipts.');
 return {picked,optional};
}
async function toolCalls(file){
 const calls=[];let total=0,invalid=0;
 for(const line of (await file.text()).split('\n')){
  if(!line.trim())continue;
  let event;try{event=JSON.parse(line);}catch(error){invalid++;continue;}
  if(event.type!=='item.completed'||event.item?.type!=='command_execution')continue;
  total++;
  if(calls.length<20)calls.push({command:String(event.item.command||'(command unavailable)').slice(0,500),status:String(event.item.status||'unknown'),exit:event.item.exit_code});
 }
 return {calls,total,invalid};
}

async function inspectTrial(files){
 if(!reveal)throw Error('Save and load a blind verdict with its matching key first.');
 trialReport.hidden=true;trialReport.replaceChildren();trialStatus.textContent='Reading local receipts…';
 const {picked,optional}=pickRunFiles(files),data={};
 for(const [name,file] of Object.entries(picked))data[name]=await jsonFile(file);
 const plan=data['plan.json'],protocol=data['protocol.json'],seal=data['protocol-freeze.json'],sources=data['SKILL-SOURCES.json'],result=data['artifact-results.json'],records=data['records.json'];
 if(!plan?.skills?.length||!sources?.skills?.length||!result?.arms||!seal?.plan_sha256||!Array.isArray(records))throw Error('These are not a complete SkillWire pair of receipts.');
 const hashes={};for(const name of ['plan.json','protocol.json','SKILL-SOURCES.json'])hashes[name]=await digest(picked[name]);
 const checks=[];const check=(name,ok)=>checks.push({name,state:ok?'match':'mismatch'});const unknown=name=>checks.push({name,state:'unverified'});
 check('Plan bound to seal',hashes['plan.json']===seal.plan_sha256);
 check('Protocol bound to seal',hashes['protocol.json']===seal.protocol_sha256);
 check('Skill manifest bound to seal',hashes['SKILL-SOURCES.json']===seal.sources_sha256);
 check('Results refer to plan',result.plan_sha256===hashes['plan.json']);
 check('Results refer to protocol',result.protocol_sha256===hashes['protocol.json']);
 check('Blind key refers to protocol',reveal.key.source.protocol_sha256===hashes['protocol.json']);
 check('Blind key refers to skill manifest',reveal.key.source.skill_sources_sha256===hashes['SKILL-SOURCES.json']);
 check('Blind task matches run task',(await textDigest(reveal.bundle.task))===plan.task_sha256);
 check('Plan skills match source manifest',plan.skills.length===sources.skills.length&&plan.skills.every(s=>sources.skills.some(m=>m.id===s.id&&m.sha256===s.sha256&&m.revision===s.revision)));
 check('Good and bad controls fired',plan.ready===true&&plan.controls?.reference?.passed===true&&plan.controls?.deliberately_bad?.passed===false);
 for(const [name,key] of [['TASK.md','task_sha256'],['grader.py','grader_sha256']]){
  if(optional[name])check(name+' matches plan',(await digest(optional[name]))===plan[key]);else unknown(name+' not supplied');
 }
 const selected=currentSelection();
 if(selected.length===1)check('Current selected skill matches run',plan.skills.length===1&&plan.skills[0].id===selected[0].id&&plan.skills[0].sha256===selected[0].sha256&&plan.skills[0].revision===selected[0].revision);
 else unknown(selected.length?'Choose one current skill to compare':'No catalog skill selected; local private source cannot be compared here');
 const arms=new Set(records.map(record=>record.arm));
 check('Both CLI records present',records.length===2&&arms.has('without')&&arms.has('with'));
 for(const arm of ['without','with']){
  const record=records.find(r=>r.arm===arm),summary=result.arms[arm];
  check(arm+' status and grade agree',!!record&&!!summary&&summary.status===record.status&&equal(summary.grade,record.grade));
  check(arm+' model matches sealed protocol',!!record&&record.model_requested===protocol.model);
  check(arm+' mode and adapter match seal',!!record&&record.mode===protocol.mode&&record.adapter_sha256===protocol.adapter_sha256);
  check(arm+' read claim agrees with CLI record',!!record&&!!summary&&equal(summary.read,record.read));
  if(protocol.mode==='native_installed')check(arm+' skill installation matches arm',!!record&&record.skill_installed===(arm==='with'));
  else if(record)unknown(arm+' installation meaning depends on '+protocol.mode+' mode');
  if(record?.read?.status==='full_body_tool_output_observed')check(arm+' full-read claim has recorded resources',Array.isArray(record.full_resource_outputs_observed)&&record.full_resource_outputs_observed.length>0&&Array.isArray(record.read.matched_skill_ids)&&record.read.matched_skill_ids.some(id=>sources.skills.some(s=>s.id===id)));
  if(optional[arm+'-record'])check(arm+' individual record matches blind key',(await digest(optional[arm+'-record']))===reveal.key.source.record_sha256?.[arm]);
  else unknown(arm+' individual record not supplied to bind blind key');
  if(optional[arm+'-trace']){
   const traceHash=await digest(optional[arm+'-trace']);
   if(record?.read?.trace_sha256)check(arm+' raw trace matches recorded read hash',traceHash===record.read.trace_sha256);
   else unknown(arm+' raw trace has no recorded hash');
  }else unknown(arm+' raw trace not supplied; read evidence unverified');
 }
 const state=checks.some(c=>c.state==='mismatch')?'mismatch':checks.some(c=>c.state==='unverified')?'unverified':'match';
 const summary=node('section','','trial-summary '+(state==='match'?'':state));
 summary.append(node('h3','Pair evidence'),node('p',state==='mismatch'?'Receipt mismatch. Do not interpret this pair until the source files agree.':state==='unverified'?'Supplied receipt fields agree; missing files leave parts of this pair unverified.':'Supplied receipt links agree. This still does not prove internal skill use.'));
 summary.append(item('Task SHA-256',plan.task_sha256),item('Starting files',plan.initial_fixture?.length??'unknown'),item('CLI',protocol.harness+' · '+protocol.model+' · '+protocol.reasoning),item('Order',Array.isArray(protocol.arm_order)?protocol.arm_order.join(' → '):'unknown'));
 trialReport.append(summary);
 const sourceBox=node('section','','trial-sources');sourceBox.append(node('h3','Pinned skill files'));
 for(const s of sources.skills){const card=node('article','','trial-source');card.append(node('b',s.name),item('Source',s.repo+' @ '+s.revision),item('SKILL.md SHA-256',s.sha256),item('Files',s.files?.length??'unknown'));sourceBox.append(card);}trialReport.append(sourceBox);
 const controls=node('section','','trial-controls');controls.append(node('h3','Pre-run controls'),item('Known good',gradeText(plan.controls?.reference)),item('Deliberately bad',gradeText(plan.controls?.deliberately_bad)),item('Control gate',plan.ready&&plan.controls?.reference?.passed===true&&plan.controls?.deliberately_bad?.passed===false?'Good passed · bad failed':'Not proved'));trialReport.append(controls);
 const checkBox=node('section','','trial-checks');checkBox.append(node('h3','Receipt links'));
 for(const result of checks)checkBox.append(item(result.name,result.state.toUpperCase(),result.state==='match'?'':result.state));trialReport.append(checkBox);
 const armBox=node('section','','trial-arms');armBox.append(node('h3','Saved outcomes after blind choice'));
 for(const arm of ['without','with']){
  const row=result.arms[arm],record=records.find(r=>r.arm===arm),card=node('article','','trial-arm');card.append(node('h4',arm==='with'?'With selected skill':'Without selected skill'));
  if(!row){card.append(node('p','Missing arm; no score.'));armBox.append(card);continue;}
  card.append(item('CLI status',row.status||'unknown'),item('Outcome',gradeText(row.grade)),item('Recorded read',record?.read?.status||'not supplied'),item('Installed',record?String(record.skill_installed):'record not supplied'));
  for(const c of row.grade?.checks||[])card.append(item(c.passed?'PASS':'FAIL',c.name));
  if(record)card.append(item('Tool resource reads',record.full_resource_outputs_observed?.length??0));
  if(optional[arm+'-trace']){
   const trace=await toolCalls(optional[arm+'-trace']);card.append(item('Raw trace','Supplied locally · '+(await digest(optional[arm+'-trace'])).slice(0,16)+'… SHA-256'),item('CLI tool calls',trace.total+' completed command executions'+(trace.invalid?' · '+trace.invalid+' invalid lines':'')));
   const details=node('details','','trial-tool-details');details.append(node('summary','View recorded commands'+(trace.total>trace.calls.length?' (first '+trace.calls.length+')':'')));
   for(const call of trace.calls){const event=node('div','','trial-tool-call');event.append(node('code',call.command),node('span',call.status+' · exit '+(call.exit??'unknown')));details.append(event);}card.append(details);
  }else card.append(item('Raw trace','Not supplied to this viewer'));
  armBox.append(card);
 }
 trialReport.append(armBox,node('p','These local files are unauthenticated. A saved verdict is a task preference, not a controlled estimate. Installation, recorded reading and internal influence are separate observations.','trial-limit'));
 trialReport.hidden=false;
 trialStatus.textContent=state==='mismatch'?'MISMATCH: this pair failed receipt checks.':state==='unverified'?'UNVERIFIED: supplied fields agree but evidence is missing.':'Supplied receipts match. Internal skill use remains unknown.';
}
for(const id of ['#trial-folder','#trial-files'])document.querySelector(id).addEventListener('change',async event=>{try{await inspectTrial([...event.target.files]);}catch(error){trialReport.hidden=true;trialStatus.textContent=error.message;}});
document.querySelector('#trial-find-skill').addEventListener('click',()=>document.querySelector('[data-tab="search"]').click());
