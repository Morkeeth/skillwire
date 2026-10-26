"""Attach model mentions from exact skill lines; sanitize public text and bound popular selection."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EMAIL=re.compile(r'[A-Z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}',re.I)
PATTERNS=[('Opus',r'\b(?:Claude[ -])?Opus(?:[ -]+\d+(?:\.\d+)*)?\b'),('Sonnet',r'\b(?:Claude[ -])?Sonnet(?:[ -]+\d+(?:\.\d+)*)?\b'),('Haiku',r'\b(?:Claude[ -])?Haiku(?:[ -]+\d+(?:\.\d+)*)?\b'),('GPT',r'\bGPT(?:[ -]+\d[\w.\-]*)?\b'),('Gemini',r'\bGemini(?![ -]+CLI)(?:[ -]+\d[\w.\-]*)?\b'),('Qwen',r'\bQwen(?:[ -]?\d[\w.\-]*)?\b'),('Llama',r'\bLlama(?:[ -]+\d[\w.\-]*)?\b'),('DeepSeek',r'\bDeepSeek(?:[ -][RV]\d[\w.\-]*)?\b'),('Claude',r'\bClaude(?![ -]+(?:Code|Desktop|skills?\b|Opus|Sonnet|Haiku))\b'),('Any model',r'\b(?:any|all)[ -]+(?:LLMs?|models?|language models?)\b')]
def sanitize(value):
    if isinstance(value,str):return EMAIL.sub('[email removed]',value)
    if isinstance(value,list):return [sanitize(v) for v in value]
    if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items()}
    return value

def enrich(c):
    for s in c['skills']:
        body=(ROOT/'data/hosted-sources'/s['repo'].replace('/','--')/(s['sha256']+'.md')).read_text()
        evidence=[];families=[]
        for family,pattern in PATTERNS:
            for line_no,line in enumerate(body.splitlines(),1):
                match=re.search(pattern,line,re.I)
                if match:
                    families.append(family);evidence.append({'family':family,'named':match.group(0),'quote':line.strip(),'line':line_no,'source':s['source']+'#L'+str(line_no)});break
        s['target_models']=dict(status='stated' if evidence else 'not stated',families=families,evidence=evidence,meaning='Model named in skill text; tuning and suitability are not verified.')
        names=', '.join(s['models'])
        s['support_summary']=('The '+('skill' if s['model_basis']=='stated in skill' else 'repository')+' names '+names+'. Compatibility has not been tested.' if s['model_basis'].startswith('stated') else 'No harness is named in the inspected text. Format compatibility is inferred and has not been tested.')
        s['support_source']=s['source'] if s['model_basis']=='stated in skill' else 'https://github.com/'+s['repo']+'/tree/'+s['revision']
        s.pop('model_evidence',None)
    # Real repository stars, diversity cap, deterministic source-based tie break.
    preferred=['brainstorming','systematic-debugging','test-driven-development','frontend-design','pdf','xlsx','web-design-guidelines','vercel-react-best-practices','skill-creator','playwright','security-review','tdd-workflow']
    popularity=sorted(c['skills'],key=lambda s:(-s['stars'],preferred.index(s['name']) if s['name'] in preferred else len(preferred),s['name']))
    counts={};popular=[]
    for s in popularity:
        if counts.get(s['repo'],0)>=3:continue
        counts[s['repo']]=counts.get(s['repo'],0)+1;popular.append(s['id'])
        if len(popular)==50:break
    c['popular_ids']=popular;c['popular_method']='Up to 50 entries by fetched repository stars, at most three per repository. Named task skills break within-repository ties. Installs unknown. Available source diversity may yield fewer than 50.'
    return sanitize(c)
if __name__=='__main__':
    path=ROOT/'evidence/hosted-catalog.json';c=enrich(json.loads(path.read_text()));path.write_text(json.dumps(c,indent=2));print(len(c['popular_ids']),'popular entries;',sum(s['target_models']['status']=='stated' for s in c['skills']),'skills name models')
