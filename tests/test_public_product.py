"""Exercise real pinned sources and security boundaries of hosted inspect/download."""
import hashlib,io,json,stat,unittest,zipfile
from unittest.mock import patch
import public_runtime as r
class HostedProductTests(unittest.TestCase):
    def setUp(self):self.skill=next(s for s in r.catalog()['skills'] if s['repo']=='obra/superpowers' and s['name']=='systematic-debugging')
    def test_actual_pinned_folder_hashes_and_warning_manifest(self):
        data=r.bundle([self.skill['id']])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            manifest=json.loads(z.read('SKILL-SOURCES.json'));row=manifest['skills'][0]
            self.assertEqual(row['sha256'],self.skill['sha256']);self.assertGreater(len(row['files']),1)
            for f in row['files']:self.assertEqual(hashlib.sha256(z.read(row['folder']+'/'+f['path'])).hexdigest(),f['sha256'])
            self.assertTrue(row['warnings']);self.assertFalse(any(('/'+'Users/') in n or n.startswith('data/') for n in z.namelist()))
    def test_same_pinned_selection_has_identical_archive_bytes(self):
        first=r.bundle([self.skill['id']]);second=r.bundle([self.skill['id']])
        self.assertEqual(first,second)
        with zipfile.ZipFile(io.BytesIO(first)) as z:
            manifest=json.loads(z.read('SKILL-SOURCES.json'))
            self.assertNotIn('created_at',manifest)
            self.assertTrue(all(info.date_time==(1980,1,1,0,0,0) for info in z.infolist()))
    def test_pinned_repository_licence_preserved_with_collision(self):
        licence=next(v for v in r.repository_licences() if v['repo']==self.skill['repo'])
        original=r.folder_files(self.skill);original['REPOSITORY-LICENCE.txt']=b'original source file'
        with patch.object(r,'folder_files',return_value=original):data=r.bundle([self.skill['id']])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(len(z.namelist()),len(set(z.namelist())))
            row=json.loads(z.read('SKILL-SOURCES.json'))['skills'][0];info=row['repository_licence_file']
            self.assertEqual(z.read(row['folder']+'/REPOSITORY-LICENCE.txt'),b'original source file')
            self.assertEqual(hashlib.sha256(z.read(row['folder']+'/'+info['path'])).hexdigest(),licence['sha256'])
        with patch.object(r,'repository_licences',return_value=[{**licence,'text':'corrupted text'}]):
            with self.assertRaisesRegex(r.PublicError,'licence hash mismatch'):r.bundle([self.skill['id']])
    def test_only_catalog_ids_and_no_duplicate_selection(self):
        for ids in [[],['../secrets'],['0'*16],[self.skill['id']]*2,[self.skill['id']]*11]:
            with self.assertRaises(r.PublicError):r.bundle(ids)
    def test_inspection_is_exact_hash_and_public_text(self):
        result=r.inspect(self.skill['id']);self.assertEqual(result['sha256'],self.skill['sha256']);self.assertFalse(result['executed']);self.assertFalse(r.EMAIL.search(result['body']))
    def test_changed_body_is_rejected(self):
        r.body_bytes.cache_clear()
        with patch.object(r.Path,'is_file',return_value=False),patch.object(r,'fetch',return_value=b'changed source'):
            with self.assertRaisesRegex(r.PublicError,'hash changed'):r.body_bytes(self.skill['id'])
        r.body_bytes.cache_clear()
    def malicious_archive(self,path,mode=0):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            i=zipfile.ZipInfo('repo/'+str(r.PurePosixPath(self.skill['path']).parent)+'/'+path);i.external_attr=mode<<16;z.writestr(i,b'unsafe')
        return b.getvalue()
    def test_real_archive_parser_rejects_traversal_and_symlinks(self):
        for data in [self.malicious_archive('../escape'),self.malicious_archive('link',stat.S_IFLNK|0o777)]:
            with patch.object(r,'catalog',return_value={'sources':[]}):
                with self.assertRaises(r.PublicError):r.folder_files(self.skill,lambda _:data)
    def test_warning_response_is_bounded_on_adversarial_source(self):
        warnings=r.warnings_for({'SKILL.md':b'curl https://example.com\n'*600})
        self.assertTrue(warnings)
        self.assertLess(len(warnings),600)
        self.assertLessEqual(len(warnings),r.MAX_WARNINGS)
    def test_source_hash_guard_fires(self):
        with self.assertRaisesRegex(r.PublicError,'archive hash mismatch'):r.folder_files(self.skill,lambda _:b'bad archive')
if __name__=='__main__':unittest.main()
