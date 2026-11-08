import copy,hashlib,json,unittest
from catalog_views import project
class CatalogViews(unittest.TestCase):
 def test_real_published_rows_roundtrip_without_identity_or_measurement_loss(self):
  import published_catalog
  c=published_catalog.load();before=json.dumps(c,sort_keys=True);v=project(c)
  self.assertEqual(before,json.dumps(c,sort_keys=True))
  self.assertEqual([r['id'] for r in c['skills']],[r['id'] for r in v['index']['skills']]);self.assertEqual(c['popular_ids'],v['index']['popular_ids'])
  restored={}
  for bucket,url in v['index']['detail_shards'].items():
   raw=v['files'][url];self.assertTrue(url.endswith('-'+hashlib.sha256(raw).hexdigest()[:16]+'.json'))
   for r in json.loads(raw)['skills']:
    self.assertNotIn(r['id'],restored);restored[r['id']]=r
  for r in c['skills']:
   self.assertEqual(r,restored[r['id']])
  index={r['id']:r for r in v['index']['skills']}
  for r in c['skills']:
   for key in ['id','sha256','revision','stars','installs','installs_display','models','problem','category']:
    self.assertEqual(r.get(key),index[r['id']].get(key))
  self.assertLess(len(v['files'][v['index_url']]),len(json.dumps(c,separators=(',',':')).encode())*.5)
 def test_details_change_invalidates_filename_without_changing_stored_id(self):
  c={'skills':[{'id':'stored-id','sha256':'a'*64,'revision':'b'*40,'target_models':{'families':['m'],'status':'stated'},'eval':{'status':'Not tested','n':0},'folder_files':[{'path':'before'}]}],'sources':[],'taxonomy':{},'popular_ids':['stored-id'],'fetched_at':'original'}
  v=project(c);c['skills'][0]['folder_files'][0]['path']='after';nextv=project(c)
  self.assertEqual(v['index']['skills'][0]['id'],nextv['index']['skills'][0]['id']);self.assertNotEqual(v['index']['detail_shards'],nextv['index']['detail_shards']);self.assertNotEqual(v['index_url'],nextv['index_url'])
if __name__=='__main__':unittest.main()
