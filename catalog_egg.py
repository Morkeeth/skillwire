"""One locally bundled catalog duplicate. No remote source or code execution."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parent
ID='f0e17d35a19c2005'
FOLDER='frontend-design-1'
BODY=b'![Never gonna give you up](rickroll.jpg)\n'
def files():
    return {'SKILL.md':BODY,'rickroll.jpg':(ROOT/'assets'/FOLDER/'rickroll.jpg').read_bytes()}
def entry():
    image=files()['rickroll.jpg']
    return {'id':ID,'name':'frontend-design (1)','problem':'A familiar starting point for distinctive frontend layouts and visual direction.',
      'problem_basis':'Local catalog description; not independently evaluated','category':'Design','category_basis':'Local catalog category',
      'models':['Any'],'model_basis':'No model-specific instructions','repo':'skillwire/local','path':FOLDER+'/SKILL.md',
      'revision':hashlib.sha256(BODY+image).hexdigest()[:40],'sha256':hashlib.sha256(BODY).hexdigest(),
      'source':'/assets/'+FOLDER+'/SKILL.md','stars':None,'installs':None,'installs_display':None,
      'popularity_basis':'Local duplicate; no measured stars or install count.','license':'Unknown','root_licence_text_available':False,
      'eval':{'status':'Not tested','n':0,'model':None,'date':None},
      'target_models':{'status':'unknown','families':[],'evidence':[],'meaning':'No model suitability has been tested.'},
      'support_summary':'Locally bundled by SkillWire. No model compatibility or effectiveness result.',
      'support_source':'/assets/'+FOLDER+'/SKILL.md','folder_files':[{'path':n,'bytes':len(b),'git_blob_sha':None,'symlink':False} for n,b in files().items()],
      'fetched_at':'Bundled locally','local_bundle':True,'revision_basis':'Local payload content digest; not an upstream Git commit.'}
def add(catalog):
    if any(s['id']==ID for s in catalog['skills']):return catalog
    catalog['skills'].append(entry())
    popular=catalog.get('popular_ids')
    if popular is not None:
        original=next((s['id'] for s in catalog['skills'] if s['name']=='frontend-design'),None)
        popular.insert(popular.index(original)+1 if original in popular else len(popular),ID)
    return catalog
