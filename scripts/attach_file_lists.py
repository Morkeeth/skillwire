"""Attach pinned public folder file metadata, enabling small downloads from large repos."""
import hashlib,json,stat,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def main():
    path=ROOT/'evidence/hosted-catalog.json';c=json.loads(path.read_text());repo_files={}
    for source in c['sources']:
        cache=ROOT/'data/hosted-sources'/source['repo'].replace('/','--');tree=cache/'tree.json';archive=cache/'source.zip'
        files=[]
        if tree.exists():
            data=json.loads(tree.read_text())
            if data.get('truncated'):raise ValueError('Incomplete tree')
            files=[{'path':i['path'],'bytes':i.get('size',0),'git_blob_sha':i['sha'],'symlink':i.get('mode')=='120000'} for i in data['tree'] if i['type']=='blob']
        elif archive.exists():
            with zipfile.ZipFile(archive) as z:
                for i in z.infolist():
                    if i.is_dir():continue
                    rel=i.filename.split('/',1)[1]
                    files.append({'path':rel,'bytes':i.file_size,'git_blob_sha':None,'symlink':stat.S_ISLNK(i.external_attr>>16)})
        repo_files[source['repo']]=files
    for s in c['skills']:
        folder=PurePosixPath(s['path']).parent;prefix='' if str(folder)=='.' else str(folder)+'/'
        s['folder_files']=[dict(i,path=i['path'][len(prefix):]) for i in repo_files[s['repo']] if i['path'].startswith(prefix)]
        s['download_limit_note']='Folder will be rejected if it exceeds 120 files, a file exceeds 2 MiB, contains symlinks or exceeds stack response limits.'
    path.write_text(json.dumps(c,indent=2));print('File lists attached to',len(c['skills']),'entries')
if __name__=='__main__':main()
