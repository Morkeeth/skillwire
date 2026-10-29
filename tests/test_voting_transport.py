import io,json,unittest
from unittest.mock import patch
from voting import SupabaseStore,VoteError
class SupabaseTransport(unittest.TestCase):
 def test_named_rpc_wire_payload_and_void_response(self):
  store=SupabaseStore('https://example.supabase.co','test-only-service-key')
  def response(req,timeout):
   self.assertEqual(req.full_url,'https://example.supabase.co/rest/v1/rpc/skillwire_cast_vote')
   self.assertEqual(req.get_header('Apikey'),'test-only-service-key');self.assertEqual(json.loads(req.data)['p_skill'],'a'*16);return io.BytesIO(b'1')
  with patch('urllib.request.urlopen',side_effect=response):self.assertEqual(store.cast('test','2026-10-29','b'*64,'c'*64,'a'*16),1)
  with patch('urllib.request.urlopen',return_value=io.BytesIO(b'')):self.assertIsNone(store.x_set('test',{'enabled':True}))
 def test_failure_hides_credentials_and_never_confirms_vote(self):
  store=SupabaseStore('https://example.supabase.co','test-only-service-key')
  with patch('urllib.request.urlopen',side_effect=RuntimeError('test-only-service-key')):
   with self.assertRaises(VoteError) as e:store.cast('test','2026-10-29','b'*64,'c'*64,'a'*16)
   self.assertEqual(e.exception.status,503);self.assertNotIn('test-only-service-key',str(e.exception))
