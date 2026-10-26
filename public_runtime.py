"""Public-only inspect and stack service. No private files, uploads, auth or model calls."""
from __future__ import annotations
import hashlib,io,json,re,stat,urllib.request,zipfile
from functools import lru_cache
from pathlib import Path,PurePosixPath
import public_skill_finder as finder
ROOT=Path(__file__).resolve().parent
MAX_ARCHIVE=96*1024*1024
MAX_TOTAL=12*1024*1024
MAX_ZIP=4*1024*1024
MAX_FILES=120
MAX_WARNINGS=500
class PublicError(ValueError):pass

def digest(data):return hashlib.sha256(data).hexdigest()
@lru_cache(maxsize=1)
def catalog():
    import published_catalog
    return published_catalog.load_runtime()
def skill(skill_id):
    if not re.fullmatch(r'[a-f0-9]{16}',skill_id):raise PublicError('Choose a catalog skill.')
    s=next((s for s in catalog()['skills'] if s['id']==skill_id),None)
    if not s:raise PublicError('Skill not in this source snapshot.')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',s['repo']) or not re.fullmatch(r'[a-f0-9]{40}',s['revision']):raise PublicError('Invalid pinned source.')
    return s

def fetch(url,limit):
    req=urllib.request.Request(url,headers={'User-Agent':'skillwire-public-inspect/1.0'})
    # Fixed GitHub URLs only, reject redirects to other hosts.
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not newurl.startswith(('https://raw.githubusercontent.com/','https://codeload.github.com/')):raise PublicError('Unexpected source redirect.')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    with urllib.request.build_opener(SafeRedirect).open(req,timeout=35) as response:raw=response.read(limit+1)
    if len(raw)>limit:raise PublicError('Pinned source exceeds the download limit. Open the source repository instead.')
    return raw

def local_cache(s):return ROOT/'data/hosted-sources'/s['repo'].replace('/','--')
@lru_cache(maxsize=24)
def body_bytes(skill_id):
    s=skill(skill_id);p=local_cache(s)/(s['sha256']+'.md')
    raw=p.read_bytes() if p.is_file() else fetch('https://raw.githubusercontent.com/'+s['repo']+'/'+s['revision']+'/'+s['path'],finder.MAX_FILE)
    if digest(raw)!=s['sha256']:raise PublicError('Source hash changed. Download stopped.')
    return raw

def warnings_for(files):
    warnings=[]
    code_suffix={'.sh','.bash','.zsh','.py','.js','.ts','.mjs','.cjs','.tsx','.jsx','.rb','.go','.rs','.java','.php','.ps1'}
    for name,raw in files.items():
        suffix=PurePosixPath(name).suffix.lower()
        if suffix not in finder.TEXT_SUFFIXES or b'\x00' in raw:continue
        text=raw.decode('utf-8',errors='replace')
        for n,line in enumerate(text.splitlines(),1):
            for rule,severity,pattern in finder.RISK_PATTERNS:
                if pattern.search(line):
                    action=suffix in code_suffix and not line.lstrip().startswith(('#','//','/*','*'))
                    warnings.append({'file':name,'line':n,'rule':rule,'severity':('high' if severity in {'high','critical'} else 'medium') if action else 'low','context':'action' if action else 'mention','text':redact(line.strip()[:500])})
                    if len(warnings)>=MAX_WARNINGS:return warnings
    return warnings
EMAIL=re.compile(r'[A-Z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}',re.I)
def redact(text):return EMAIL.sub('[email removed]',text)
def inspect(skill_id):
    s=skill(skill_id);raw=body_bytes(skill_id);body=raw.decode('utf-8',errors='replace')
    return {'id':s['id'],'source':s['source'],'revision':s['revision'],'sha256':digest(raw),'body':redact(body),'body_display':'Email addresses removed for display. Download preserves original public source bytes.','warnings':warnings_for({'SKILL.md':raw}),'scan_scope':'SKILL.md only. The stack download scans every included text file. At most 500 matches are shown. Pattern matches are not a malicious verdict.','files_downloaded':False,'executed':False}

def folder_files(s,archive_loader=None):
    source=next((r for r in catalog()['sources'] if r['repo']==s['repo']),None)
    path=local_cache(s)/'source.zip'
    if not archive_loader and not path.is_file() and s.get('folder_files'):
        return raw_folder_files(s)
    if archive_loader:raw=archive_loader(s)
    elif path.is_file():raw=path.read_bytes()
    else:raw=fetch('https://codeload.github.com/'+s['repo']+'/zip/'+s['revision'],MAX_ARCHIVE)
    if len(raw)>MAX_ARCHIVE:raise PublicError('Source archive too large.')
    if source and source.get('archive_sha256') and digest(raw)!=source['archive_sha256']:raise PublicError('Repository archive hash mismatch.')
    files={};total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        roots={n.split('/')[0] for n in z.namelist()}
        if len(roots)!=1:raise PublicError('Unexpected archive layout.')
        root=next(iter(roots));folder=PurePosixPath(s['path']).parent
        prefix=root+'/'+('' if str(folder)=='.' else str(folder)+'/')
        for info in z.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():continue
            rel=info.filename[len(prefix):];p=PurePosixPath(rel)
            if not rel or p.is_absolute() or '..' in p.parts or '\\' in rel:raise PublicError('Unsafe source path.')
            if stat.S_ISLNK(info.external_attr>>16):raise PublicError('Symlink in skill source. Open its repository instead.')
            if info.file_size>finder.MAX_FILE or len(files)>=MAX_FILES:raise PublicError('Skill folder exceeds file limits. Download from the pinned repository instead.')
            total+=info.file_size
            if total>MAX_TOTAL:raise PublicError('Skill folder exceeds total size limit.')
            if rel in files:raise PublicError('Duplicate source file path.')
            files[rel]=z.read(info)
    if 'SKILL.md' not in files or digest(files['SKILL.md'])!=s['sha256']:raise PublicError('Pinned SKILL.md is missing or changed.')
    return files

def raw_folder_files(s):
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import quote
    manifest=s['folder_files']
    if len(manifest)>MAX_FILES or sum(f['bytes'] for f in manifest)>MAX_TOTAL:raise PublicError('Skill folder exceeds download limits. Open its pinned repository instead.')
    for f in manifest:
        rel=f['path'];p=PurePosixPath(rel)
        if not rel or p.is_absolute() or '..' in p.parts or '\\' in rel or f.get('symlink'):raise PublicError('Unsafe path or symlink in public source.')
        if f['bytes']>finder.MAX_FILE:raise PublicError('Source file exceeds download limit.')
    folder=PurePosixPath(s['path']).parent
    def one(f):
        raw=fetch('https://raw.githubusercontent.com/'+s['repo']+'/'+s['revision']+'/'+quote(str(folder/f['path']),safe='/'),finder.MAX_FILE)
        if len(raw)!=f['bytes']:raise PublicError('Pinned file size changed.')
        if f.get('git_blob_sha'):
            blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()
            if blob!=f['git_blob_sha']:raise PublicError('Pinned file blob hash changed.')
        return f['path'],raw
    with ThreadPoolExecutor(max_workers=6) as pool:files=dict(pool.map(one,manifest))
    if 'SKILL.md' not in files or digest(files['SKILL.md'])!=s['sha256']:raise PublicError('Pinned SKILL.md hash changed.')
    return files

@lru_cache(maxsize=1)
def repository_licences():
    path=ROOT/'evidence/public-source-licences.json'
    return json.loads(path.read_text())['sources'] if path.is_file() else []

def bundle(ids,archive_loader=None):
    if not isinstance(ids,list) or not 1<=len(ids)<=10 or len(set(ids))!=len(ids):raise PublicError('Choose one to ten different skills.')
    chosen=[skill(i) for i in ids];out=io.BytesIO();total=0;manifest={'schema':1,'privacy':'Only chosen public source folders. No local/private skills, credentials or user history.','notice':'Untrusted public source, never executed by SkillWire. Check source licences and warning lines before use.','skills':[]}
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        def write_fixed(name,raw):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3
            info.external_attr=0o644<<16
            z.writestr(info,raw)
        for s in chosen:
            files=folder_files(s,archive_loader);warnings=warnings_for(files);prefix=re.sub(r'[^\w.-]+','-',s['name'])[:80]+'-'+s['id']
            row={k:s[k] for k in ['id','name','repo','path','source','revision','sha256','license']};row.update(folder=prefix,warnings=warnings,warning_limit_reached=len(warnings)>=MAX_WARNINGS,warning_limit=MAX_WARNINGS,files=[])
            for name,raw in sorted(files.items()):
                total+=len(raw)
                if total>MAX_TOTAL:raise PublicError('Stack too large. Choose fewer skills.')
                write_fixed(prefix+'/'+name,raw);row['files'].append({'path':name,'sha256':digest(raw),'bytes':len(raw)})
            licence=next((v for v in repository_licences() if v['repo']==s['repo'] and v['revision']==s['revision'] and v.get('text') is not None),None)
            row['repository_licence_file']=None
            row['licence_scope']='Root repository licence only. Review any skill-specific terms too. Missing text is unknown, not permission.'
            if licence:
                raw=licence['text'].encode('utf-8')
                if digest(raw)!=licence['sha256']:raise PublicError('Pinned licence hash mismatch.')
                name='REPOSITORY-LICENCE.txt'
                while name in files:name='_'+name
                total+=len(raw)
                if total>MAX_TOTAL:raise PublicError('Stack too large. Choose fewer skills.')
                write_fixed(prefix+'/'+name,raw)
                row['repository_licence_file']={'path':name,'sha256':digest(raw),'source':licence['source']}
            manifest['skills'].append(row)
        write_fixed('SKILL-SOURCES.json',json.dumps(manifest,indent=2))
        write_fixed('READ-BEFORE-INSTALL.txt','These public skill folders are untrusted source, not a safety endorsement.\nSkillWire did not execute any included code.\nReview SKILL-SOURCES.json and licences, then inspect warnings before installing.\nKeep folders separate. You choose whether and where to install them.\n')
    data=out.getvalue()
    if len(data)>MAX_ZIP:raise PublicError('Compressed stack exceeds hosting response limit. Choose fewer skills.')
    return data
