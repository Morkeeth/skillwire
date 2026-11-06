"""Deterministic metadata cleanup without inventing model support or efficacy."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RULES={
'Documents':r'\b(?:pdf|docx|xlsx|spreadsheet|powerpoint|slides?|presentations?|document(?:s|ation)? creation)\b',
'Design':r'\b(?:ui|ux|frontend|canvas|brand|visual|web design|design system|accessibility)\b',
'Infrastructure':r'\b(?:deploy(?:ment|ing)?|docker|cloud|devops|kubernetes|terraform|infrastructure)\b',
'Research':r'\b(?:research|scientific|biology|chemistry|papers?|pubmed|genomics)\b',
'Marketing':r'\b(?:marketing|seo|sales|campaign|social media|conversion)\b',
'Data':r'\b(?:data|sql|database|analytics|csv|tabular)\b',
'Testing':r'\b(?:test(?:ing|s)?|debug(?:ging)?|verification|review(?:s|ing)?|security)\b',
'Writing':r'\b(?:writing|copywriting|content|editing|prose|humanizer)\b',
'Workflow':r'\b(?:workflow|planning|brainstorm(?:ing)?|productivity|plan|handoff)\b',
'Development':r'.*'}
def plain(text):
    text=re.sub(r'\\(["\x27])',r'\1',text)
    text=re.sub(r'`([^`]+)`',r'\1',text);text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
    text=re.sub(r'\s+',' ',text).strip().strip('"\x27')
    first=re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)[0]
    if len(first)>220:first=first[:217].rsplit(' ',1)[0].rstrip(' ,;:')+'…'
    return first

def main():
    path=ROOT/'evidence/hosted-catalog.json';c=json.loads(path.read_text())
    # The GitHub redirect is the same project, not another independent popular repository.
    aliases={'affaan-m/everything-claude-code':'affaan-m/ECC'}
    if any(s['repo']=='affaan-m/ECC' for s in c['sources']):
        c['skills']=[s for s in c['skills'] if s['repo'] not in aliases]
        c['sources']=[s for s in c['sources'] if s['repo'] not in aliases]
        c['repository_aliases']=aliases
    c['taxonomy']=RULES
    for s in c['skills']:
        s['problem']=plain(s['problem']);s['problem_basis']='source-description summary/excerpt; not independently verified'
        s['category']=next(k for k,p in RULES.items() if re.search(p,s['name'].replace('-',' ')+' '+s['problem'],re.I))
        s['category_basis']='inferred from name/description keyword rules'
    preferred=['brainstorming','systematic-debugging','test-driven-development','frontend-design','pdf','xlsx','web-design-guidelines','vercel-react-best-practices','skill-creator','playwright','security-review','tdd-workflow','humanizer','caveman','last30days','design-taste','marketing-ideas']
    ranked=sorted(c['skills'],key=lambda s:(0 if s.get('installs') is not None else 1,-(s.get('installs') or 0),-s['stars'],preferred.index(s['name']) if s['name'] in preferred else len(preferred),len(s['path']),s['name']))
    counts={};seen=set();popular=[]
    for s in ranked:
        key=(s['repo'],s['name'].lower())
        if key in seen or counts.get(s['repo'],0)>=3:continue
        # Skip labelled draft/archive and localization copies in the curated entry view.
        if re.search(r'(?:^|/)(?:in-progress|archive|archives|deprecated|zh[^/]*|translations?|[a-z]{2}-[A-Z]{2})(?:/|$)',s['path']):continue
        seen.add(key);counts[s['repo']]=counts.get(s['repo'],0)+1;popular.append(s['id'])
        if len(popular)==50:break
    c['popular_ids']=popular;c['popular_method']='Up to 50 skills by observed skills.sh installs first, then fetched repository stars for entries with unknown installs; max three distinct skill names per canonical repository. Named task-skill tie break; draft/archive/localization paths excluded from Popular. Full catalog remains available.'
    path.write_text(json.dumps(c,indent=2));print(len(c['skills']),'catalog entries;',len(popular),'Popular;',len(c['sources']),'source repos')
if __name__=='__main__':main()
