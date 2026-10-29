import datetime,json,os,types,unittest
from unittest.mock import patch
import x_poll
from voting import VoteError
from test_voting import DailyVotes
class XPoll(DailyVotes):
 def test_off_means_no_store_or_provider_access(self):
  with patch.dict(os.environ,{'SKILLWIRE_X_POLL_ENABLED':'0'},clear=True):
   self.assertEqual(x_poll.sync('anything',service=None)['fetched'],False)
   self.assertEqual(x_poll.public_status(None,'none')['enabled'],False)
 def test_daily_fetch_and_failure_preserve_old_dated_result(self):
  env={'PATH':os.environ.get('PATH',''),'SKILLWIRE_X_POLL_ENABLED':'1','CRON_SECRET':'test-cron','X_API_BEARER_TOKEN':'test-only-token','SKILLWIRE_X_POLL_POST_ID':'123'};calls=[]
  def fetch(url,token):
   calls.append(url);return {'data':{'id':'123','attachments':{'poll_ids':['456']}},'includes':{'polls':[{'id':'456','options':[{'label':'One','votes':4},{'label':'Two','votes':2}],'voting_status':'open','end_datetime':'2026-11-01T00:00:00Z'}]}}
  with patch.dict(os.environ,env,clear=True):
   x_poll.sync('Bearer test-cron',lambda:self.clock,self.v,fetch);old=x_poll.public_status(self.store,self.v.ns)
   x_poll.sync('Bearer test-cron',lambda:self.clock,self.v,fetch);self.assertEqual(len(calls),1)
   self.clock+=datetime.timedelta(days=1)
   with self.assertRaises(VoteError):x_poll.sync('Bearer test-cron',lambda:self.clock,self.v,lambda *_:(_ for _ in ()).throw(RuntimeError('offline')))
   self.assertEqual(x_poll.public_status(self.store,self.v.ns),old)
   self.assertFalse(x_poll.sync('Bearer test-cron',lambda:self.clock,self.v,fetch)['fetched']);self.assertEqual(len(calls),1)
 def test_bad_job_auth_or_missing_x_access_never_fetches(self):
  with patch.dict(os.environ,{'SKILLWIRE_X_POLL_ENABLED':'1','CRON_SECRET':'test-cron'},clear=True):
   with self.assertRaises(VoteError):x_poll.sync('bad')
   with self.assertRaises(VoteError):x_poll.sync('Bearer test-cron')
