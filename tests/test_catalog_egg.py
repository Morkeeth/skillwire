"""Exercise the actual local catalog payload and normal runtime download."""
import io,zipfile,unittest
from unittest.mock import patch
import catalog_egg as egg
import published_catalog
import public_runtime as runtime
class CatalogEggTests(unittest.TestCase):
 def test_one_duplicate_with_honest_unknown_popularity(self):
  c=published_catalog.load();rows=[s for s in c['skills'] if s['id']==egg.ID]
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['name'],'frontend-design (1)');self.assertIsNone(rows[0]['stars']);self.assertIsNone(rows[0]['installs']);self.assertEqual(rows[0]['eval']['n'],0)
 def test_real_bundle_contains_only_static_image_and_image_markdown_without_fetch(self):
  with patch.object(runtime,'fetch',side_effect=AssertionError('No network for bundled duplicate')):
   self.assertEqual(runtime.inspect(egg.ID)['body'],egg.BODY.decode());raw=runtime.bundle([egg.ID]);self.assertEqual(raw,runtime.bundle([egg.ID]))
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   self.assertEqual(set(z.namelist()),{egg.FOLDER+'/SKILL.md',egg.FOLDER+'/rickroll.jpg'})
   self.assertEqual(z.read(egg.FOLDER+'/SKILL.md'),b'![Never gonna give you up](rickroll.jpg)\n')
   self.assertTrue(z.read(egg.FOLDER+'/rickroll.jpg').startswith(b'\xff\xd8\xff'))
   for f in z.infolist():self.assertFalse((f.external_attr>>16)&0o111)
if __name__=='__main__':unittest.main()
