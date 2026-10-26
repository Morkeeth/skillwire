"""Join public source metadata and exact-hash-bound public evaluation evidence."""
import copy,json,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load():
    c=json.loads((ROOT/'evidence/hosted-catalog.json').read_text())
    licence_path=ROOT/'evidence/public-source-licences.json'
    if licence_path.exists():
        licences=json.loads(licence_path.read_text())['sources'];known={(v['repo'],v['revision']) for v in licences if v.get('text') is not None}
        for skill in c['skills']:skill['root_licence_text_available']=(skill['repo'],skill['revision']) in known
        c['root_licence_text_status']={'available':len(known),'unknown':len(licences)-len(known),'notice':'Missing root licence text is unknown, not permission. Review repository and skill-specific terms before use.'}
    path=ROOT/'evidence/public-evaluation-results.json'
    if path.exists():
        results=json.loads(path.read_text());byid={r['skill_id']:r for r in results['evaluations']}
        for s in c['skills']:
            r=byid.get(s['id'])
            if r and r['skill_sha256']==s['sha256']:s['eval']=copy.deepcopy(r)
        c['evaluation_source']='evaluations.json';c['evaluation_limits']=results['limits']
    native=ROOT/'evidence/public-native-evaluation.json'
    if native.exists():
        studies=json.loads(native.read_text())['studies']
        for study in studies:
            assert study['public_fixture'] is True and study['mode']=='native_installed'
            selected=next((s for s in c['skills'] if s['id']==study['skill']['id']),None)
            assert selected and selected['sha256']==study['skill']['sha256'],'Native result source hash mismatch'
            if study['effect']['valid_pairs']>0:selected['native_eval']=copy.deepcopy(study)
    return c


def load_runtime():
    """Minimal fixed source metadata for public endpoints; no evaluation/UI payload."""
    return json.loads(gzip.decompress((ROOT/'evidence/runtime-catalog.json.gz').read_bytes()))
