"""Small browse/search view plus immutable, lazy public evidence shards.
The complete published catalog and runtime source data remain unchanged.
"""
import copy,hashlib,json
from collections import defaultdict
BROWSE_KEYS=('id','name','repo','path','source','revision','sha256','license','problem','category','models','stars','installs','installs_display','installs_fetched_at','local_bundle','root_licence_text_available')
def encode(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
def project(catalog):
    groups=defaultdict(list);rows=[];files={}
    def asset(kind,value):
        raw=encode(value);digest=hashlib.sha256(raw).hexdigest();name='catalog-cache/'+kind+'-'+digest[:16]+'.json';files[name]=raw;return name
    for skill in catalog['skills']:
        bucket=hashlib.sha256(skill['id'].encode()).hexdigest()[:2]
        groups[bucket].append(skill)
        row={k:copy.deepcopy(skill[k]) for k in BROWSE_KEYS if k in skill}
        row['detail_bucket']=bucket
        row['target_models']={k:copy.deepcopy(skill['target_models'].get(k,[] if k=='families' else 'unknown')) for k in ('families','status')}
        row['eval']={k:copy.deepcopy(skill['eval'][k]) for k in ('status','n')}
        if skill.get('native_eval'):row['native_eval']={'effect':{'valid_pairs':skill['native_eval']['effect']['valid_pairs']}}
        rows.append(row)
    sources={k:copy.deepcopy(v) for k,v in catalog.items() if k!='skills'}
    index={k:copy.deepcopy(catalog[k]) for k in ('fetched_at','taxonomy','popular_ids')}
    index.update(schema='skillwire-browse-v1',skills=rows,sources=[],source_details_url=asset('sources',sources),detail_shards={bucket:asset('detail',{'skills':skills}) for bucket,skills in sorted(groups.items())},source_count=len(catalog['sources']))
    index_url=asset('index',index)
    return {'index':index,'index_url':index_url,'files':files}
