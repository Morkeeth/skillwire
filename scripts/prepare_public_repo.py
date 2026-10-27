"""Create a clean, history-free public-source pack. Never creates or pushes a remote."""
import datetime,gzip,hashlib,json,shutil,zipfile
from pathlib import Path
from export_release import FILES
ROOT=Path(__file__).resolve().parents[1]
EXTRA=['scripts/prepare_public_repo.py','scripts/export_release.py','METHOD.md','CATALOG.md','.github/workflows/public-pr-checks.yml','scripts/verify_native_pilot.py','scripts/summarize_native_eval.py','scripts/native_tdd_cases.py','scripts/native_discovery_cases.py','scripts/run_native_family.py','EVAL.md','tests/test_local_task_eval.py','tests/test_public_product.py','tests/test_human_review.py','tests/test_native_tdd_cases_v2.py','scripts/recheck_public_outcomes.py','scripts/frozen_outcomes.py','scripts/frozen_outcomes_v2.py','scripts/harder_outcomes.py','evidence/subscription-inline-frozen.json','evidence/subscription-harder-frozen.json','evidence/harder-preflight.json']
EXTRA += ['tests/test_downloaded_eval_kit.py']
def main():
 out=ROOT/'data/public-repo'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out.mkdir(parents=True,exist_ok=False);manifest=[]
 for name in sorted(set(FILES+EXTRA)):
  p=ROOT/name
  if p.is_symlink():raise ValueError('No source symlinks')
  raw=p.read_bytes();check=gzip.decompress(raw) if name.endswith('.gz') else raw
  if b'/'+b'Users/' in check:raise ValueError('Machine home path in export: '+name)
  target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);manifest.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
 (out/'.gitignore').write_text('data/\nruns/\ndist/\n.vercel/\n.env*\n**/__pycache__/\n*.pyc\n')
 (out/'PUBLIC-SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=out.with_suffix('.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(out.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(out))
 result={'directory':str(out.relative_to(ROOT)),'archive':str(archive.relative_to(ROOT)),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(manifest),'git_history':False,'private_sources_or_runtime_auth':False,'remote_created':False,'pushed':False,'note':'Root owns outward repository, release alias and article actions. This pack alone does not clear the actual evaluation coverage/own-setup live-run defect.'}
 (ROOT/'evidence/public-repo-pack.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
