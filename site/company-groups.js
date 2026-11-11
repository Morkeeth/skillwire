/* Display-only grouping from pinned catalog names and repository paths.
   A repository owner alone is never enough: general skills stay individual.
   These are product families, not a claim that every member is vendor-authored. */
(function(root){
  'use strict';
  const families=[
    {id:'vercel',label:'Vercel',owner:'vercel-labs',tokens:['vercel']},
    {id:'heygen',label:'HeyGen',owner:'heygen-com',tokens:['heygen','hyperframes'],repos:['heygen-com/hyperframes']},
    {id:'microsoft',label:'Microsoft',owner:'microsoft',tokens:['microsoft','azure','aks','appinsights'],repos:['microsoft/azure-skills']},
    {id:'google',label:'Google',owner:'google',tokens:['google'],repos:['google/agents-cli']},
    {id:'openai',label:'OpenAI',owner:'openai',tokens:['openai']},
    {id:'anthropic',label:'Anthropic',owner:'anthropics',tokens:['anthropic']},
    {id:'neon',label:'Neon',owner:'neondatabase',tokens:['neon']},
    {id:'prisma',label:'Prisma',owner:'prisma',tokens:['prisma']},
    {id:'supabase',label:'Supabase',owner:'supabase',tokens:['supabase']},
    {id:'remotion',label:'Remotion',owner:'remotion-dev',tokens:['remotion']},
    {id:'lark',label:'Lark',owner:'larksuite',tokens:['lark','larksuite'],repos:['larksuite/cli']}
  ];
  // Named general skill that belongs to no company, even if its repository owner does.
  const general=new Set(['find-skills']);
  function companyFor(skill,catalog){
    if(general.has(String(skill.name||'').toLowerCase()))return null;
    const owners=new Set((catalog.sources||[]).map(s=>String(s.repo||'').split('/')[0].toLowerCase()));
    const name=String(skill.name||'').toLowerCase().split(/[^a-z0-9]+/);
    for(const family of families){
      if(!owners.has(family.owner))continue;
      const token=family.tokens.find(t=>name.includes(t));
      const repo=(family.repos||[]).includes(skill.repo);
      if(token||repo)return {id:family.id,label:family.label,
        basis:repo?'Product repository '+skill.repo:'Product name in skill name: '+token,
        source:skill.source};
    }
    return null;
  }
  function createClassifier(catalog){
    return new Map(catalog.skills.map(s=>[s.id,companyFor(s,catalog)]));
  }
  function groupRows(rows,classifier){
    const slots=[],groups=new Map();
    for(const skill of rows){
      const company=classifier.get(skill.id);
      if(!company){slots.push({kind:'skill',skill});continue;}
      let group=groups.get(company.id);
      if(!group){group={kind:'company',id:company.id,label:company.label,members:[]};groups.set(company.id,group);slots.push(group);}
      group.members.push(skill);
    }
    return slots;
  }
  function companySpots(catalog,classifier){
    const counts=new Map();
    for(const skill of catalog.skills){
      const company=classifier.get(skill.id);
      if(!company)continue;
      const spot=counts.get(company.id)||{id:company.id,label:company.label,count:0};
      spot.count++;counts.set(company.id,spot);
    }
    return families.filter(f=>counts.has(f.id)).map(f=>counts.get(f.id));
  }
  function ownEntries(catalog,classifier){
    return catalog.skills.filter(s=>general.has(String(s.name||'').toLowerCase())&&!classifier.get(s.id));
  }
  const api={families,companyFor,createClassifier,groupRows,companySpots,ownEntries};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.SkillWireCompanies=api;
})(typeof globalThis==='object'?globalThis:this);
