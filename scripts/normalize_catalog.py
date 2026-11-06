"""Normalize multiline source descriptions and collapse byte-identical skill copies per repository."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def description(body):
    lines=body.splitlines(); start=next((i for i,l in enumerate(lines) if l.startswith('description:')),None)
    if start is None:return None
    value=lines[start].partition(':')[2].strip()
    if value in ('|','>','|-','>-',''):
        following=[]
        for line in lines[start+1:]:
            if line and not line[0].isspace():break
            following.append(line.strip())
        value=' '.join(following).strip()
    return re.sub(r'\s+',' ',re.sub('<[^>]+>','',value)).strip().strip('\"\'') or None

def normalize(c):
    dedup={}
    for s in sorted(c['skills'],key=lambda x:len(x['path'])):
        body=(ROOT/'data/hosted-sources'/s['repo'].replace('/','--')/(s['sha256']+'.md')).read_text()
        desc=description(body)
        if desc:s['problem']=desc[:500];s['problem_basis']='source description, whitespace normalized and excerpted'
        else:s['problem']='Use '+s['name'].replace('-',' ')+' instructions for the task described in the source.';s['problem_basis']='inferred from skill name; source lacks a usable description'
        s['category']=next(k for k,v in c['taxonomy'].items() if re.search(v,s['name']+' '+s['problem'],re.I))
        key=(s['repo'],s['sha256'])
        if key in dedup:
            dedup[key].setdefault('duplicate_paths',[]).append(s['path'])
        else:dedup[key]=s
    c['raw_skill_files']=len(c['skills']);c['skills']=sorted(dedup.values(),key=lambda s:(-s['stars'],s['name']));c['deduplication']='Byte-identical SKILL.md copies within each repository collapse to one entry. Same skill across repositories may remain.'
    return c
if __name__=='__main__':
    path=ROOT/'evidence/hosted-catalog.json';c=normalize(json.loads(path.read_text()));path.write_text(json.dumps(c,indent=2));print(len(c['skills']),'unique repository/body entries from',c['raw_skill_files'],'files')
