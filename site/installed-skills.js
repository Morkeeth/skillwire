'use strict';
// Explicit import of local CLI metadata. No scan, upload, or telemetry.
const doctorInput=document.querySelector('#doctor-file');
const doctorStatus=document.querySelector('#doctor-status');
const doctorList=document.querySelector('#doctor-list');
let doctorSnapshot=null;
function renderDoctor(){
 doctorList.replaceChildren();
 if(!doctorSnapshot){doctorList.hidden=true;return;}
 doctorList.hidden=false;
 const selected=window.limeTrialSelection?.()||[];
 const clis=doctorSnapshot.clis.map(c=>c.name+(c.subscription_verified?' · subscription verified':' · subscription unverified')).join('; ')||'No supported CLI found';
 const intro=document.createElement('p');intro.textContent='CLI snapshot: '+clis+'. '+doctorSnapshot.installed_skills.length+' SKILL.md files reported.';doctorList.append(intro);
 if(selected.length===1){
  const matches=doctorSnapshot.installed_skills.filter(s=>s.sha256===selected[0].sha256);
  const status=document.createElement('p');status.textContent=matches.length?'Selected SKILL.md hash found locally: '+matches.map(s=>s.name+' ('+s.scope+')').join(', ')+'.':'Selected SKILL.md hash not found in imported snapshot. The downloaded ZIP can still be used by the local trial kit.';doctorList.append(status);
 }
 const list=document.createElement('ul');
 for(const s of doctorSnapshot.installed_skills.slice(0,30)){const row=document.createElement('li');row.textContent=s.name+' · '+s.scope+' · SHA-256 '+s.sha256.slice(0,12)+'…';list.append(row);}
 doctorList.append(list);
 if(doctorSnapshot.installed_skills.length>30){const more=document.createElement('p');more.textContent='Showing 30 of '+doctorSnapshot.installed_skills.length+' reported files.';doctorList.append(more);}
}
doctorInput.addEventListener('change',async()=>{
 doctorSnapshot=null;renderDoctor();const file=doctorInput.files?.[0];if(!file)return;
 try{
  if(file.size>2*1024*1024)throw Error('doctor.json exceeds the 2 MiB local viewer limit.');
  const data=JSON.parse(await file.text());
  if(!Array.isArray(data.clis)||!Array.isArray(data.installed_skills)||data.installed_skills.length>1000||data.model_calls!==0)throw Error('Expected a doctor metadata snapshot with zero model calls.');
  if(!data.installed_skills.every(s=>typeof s.name==='string'&&s.name.length<200&&/^[a-f0-9]{64}$/i.test(s.sha256)&&['user','project'].includes(s.scope)))throw Error('Invalid installed skill metadata.');
  if(!data.clis.every(c=>typeof c.name==='string'&&typeof c.subscription_verified==='boolean'))throw Error('Invalid CLI metadata.');
  doctorSnapshot=data;doctorStatus.textContent='Local doctor snapshot imported; contents are self-reported.';renderDoctor();
 }catch(error){doctorStatus.textContent='Cannot read doctor.json: '+error.message;}
});
window.addEventListener('lime-selection-change',renderDoctor);
