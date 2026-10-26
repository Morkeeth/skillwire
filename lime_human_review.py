"""Create and reveal a local blind review of two saved text artifacts. No model or network calls."""
import argparse,datetime,hashlib,json,secrets,sys
from pathlib import Path,PurePosixPath

SCHEMA='lime-human-pair-v1'
MAX_TOTAL=1024*1024

def digest(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def safe_path(raw):
 p=PurePosixPath(raw)
 if not raw or p.is_absolute() or '..' in p.parts or str(p)=='.' or '\\' in raw or any(part.startswith('.') for part in p.parts):raise ValueError('Use ordinary relative text artifact paths only')
 return p

def contents(folder,paths):
 files={};total=0
 for name in paths:
  p=safe_path(name);root=folder.resolve();file=folder.joinpath(*p.parts)
  if file.is_symlink() or not file.resolve().is_relative_to(root) or not file.is_file():raise ValueError('Missing, symlinked or unsafe artifact: '+name)
  raw=file.read_bytes();total+=len(raw)
  if len(raw)>256*1024 or total>MAX_TOTAL:raise ValueError('Text artifact exceeds local review limit')
  files[name]={'content':raw.decode('utf-8'),'sha256':digest(raw)}
 return files

def prepare(a):
 if a.out.exists():raise ValueError('Use a new output directory')
 paths=list(dict.fromkeys(a.files))
 if not 1<=len(paths)<=20 or len(paths)!=len(a.files):raise ValueError('Select one to twenty distinct artifact files')
 source={'kind':'manual-artifacts','model_execution':'not verified'}
 if a.run:
  run=a.run.resolve();task=(run/'TASK.md').read_bytes();folders={};grades={}
  for arm in ['without','with']:
   p=run/'model-runs'/arm/'record.json';record=json.loads(p.read_text())
   if record.get('status')!='completed' or record.get('grade',{}).get('status')!='graded':raise ValueError('Both native arms must complete and be graded before review')
   folders[arm]=Path(record['workspace']);grades[arm]=record['grade']
  source={'kind':'completed-native-run','model_execution':'two completed CLI records; artifact snapshot taken by this tool','record_sha256':{arm:digest((run/'model-runs'/arm/'record.json').read_bytes()) for arm in folders},'protocol_sha256':digest((run/'protocol.json').read_bytes()),'skill_sources_sha256':digest((run/'SKILL-SOURCES.json').read_bytes()),'grades':grades}
 else:
  if not (a.task and a.without and a.with_skill):raise ValueError('Provide --run or --task, --without and --with')
  task=a.task.read_bytes();folders={'without':a.without,'with':a.with_skill}
 if not task or len(task)>128*1024:raise ValueError('Task empty or too large')
 task_text=task.decode('utf-8');arms={arm:contents(folder,paths) for arm,folder in folders.items()}
 context_paths=list(dict.fromkeys(a.context or []))
 if len(context_paths)!=len(a.context or []) or len(context_paths)>20:raise ValueError('Choose at most twenty distinct context files')
 context=[]
 if context_paths:
  context_without=contents(run/'without' if a.run else folders['without'],context_paths)
  context_with=contents(run/'with' if a.run else folders['with'],context_paths)
  for name in context_paths:
   if context_without[name]['sha256']!=context_with[name]['sha256']:raise ValueError('Starting context differs between arms: '+name)
   context.append({'path':name,**context_without[name]})
 # The random mapping exists only in the withheld key. The browser bundle has no arm names or grades.
 order=['without','with'] if secrets.randbits(1)==0 else ['with','without']
 items=[]
 for name in paths:items.append({'path':name,'A':arms[order[0]][name], 'B':arms[order[1]][name]})
 pair_id=digest(encoded({'task_sha256':digest(task),'context':context,'files':items}))
 bundle={'schema':SCHEMA,'pair_id':pair_id,'task':task_text,'context':context,'files':items,'notice':'A and B hide skill condition and automated grades. Text files only. Read both before choosing; no content is sent to SkillWire.'}
 bundle_text=json.dumps(bundle,indent=2,ensure_ascii=False)+'\n'
 if len(bundle_text.encode())>MAX_TOTAL:raise ValueError('Blind review bundle exceeds 1 MiB browser limit')
 key={'schema':SCHEMA,'pair_id':pair_id,'bundle_sha256':digest(encoded(bundle)),'mapping':{'A':order[0],'B':order[1]},'source':source,'prepared_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'limit':'The key withholds arm names and grades from the browser bundle. A manual source does not verify model execution.'}
 a.out.mkdir(parents=True,exist_ok=False)
 (a.out/'blind-review.json').write_text(bundle_text)
 (a.out/'reveal-key.json').write_text(json.dumps(key,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'blind_bundle':str(a.out/'blind-review.json'),'withheld_key':str(a.out/'reveal-key.json'),'files':len(items),'source_kind':source['kind'],'model_calls':0}))

def reveal(a):
 bundle=json.loads(a.bundle.read_text());key=json.loads(a.key.read_text());review=json.loads(a.review.read_text())
 if bundle.get('schema')!=SCHEMA or key.get('schema')!=SCHEMA or bundle.get('pair_id')!=key.get('pair_id') or key.get('bundle_sha256')!=digest(encoded(bundle)):raise ValueError('Blind bundle and withheld key do not match')
 if review.get('schema')!=SCHEMA or review.get('pair_id')!=key['pair_id'] or review.get('choice') not in ['A','B','tie','cannot_judge']:raise ValueError('Review does not match pair or choice')
 note=review.get('reason')
 if not isinstance(note,str) or len(note.strip())<15 or len(note)>4000:raise ValueError('Review reason must be 15 to 4000 characters')
 if review.get('reviewed_both') is not True:raise ValueError('Reviewer must confirm both artifacts were inspected')
 choice=review['choice'];selected=key['mapping'].get(choice) if choice in ['A','B'] else choice
 result={'schema':'lime-human-reveal-v1','pair_id':key['pair_id'],'choice_blind':choice,'choice_condition':selected,'reason':note.strip(),'source_kind':key['source']['kind'],'model_execution':key['source']['model_execution'],'automated_grades_after_review':key['source'].get('grades'),'mapping':key['mapping'],'reviewed_both':True,'limits':'One human preference on this task is not a general skill effect. Manual artifacts do not prove model execution. The review file is local and unauthenticated.'}
 with a.out.open('x') as f:f.write(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'result':str(a.out),'choice_condition':selected,'source_kind':key['source']['kind']}))

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 q=sub.add_parser('prepare');q.add_argument('--run',type=Path);q.add_argument('--task',type=Path);q.add_argument('--without',type=Path);q.add_argument('--with',dest='with_skill',type=Path);q.add_argument('--files',nargs='+',required=True);q.add_argument('--context',nargs='*',default=[]);q.add_argument('--out',type=Path,required=True)
 q=sub.add_parser('reveal');q.add_argument('--bundle',type=Path,required=True);q.add_argument('--key',type=Path,required=True);q.add_argument('--review',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
 a=p.parse_args()
 try:prepare(a) if a.command=='prepare' else reveal(a)
 except (ValueError,OSError,KeyError,UnicodeError,json.JSONDecodeError) as e:p.error(str(e))
if __name__=='__main__':main()
