"""Exercise the production privacy filter and official loader without sending analytics."""
import pathlib,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AnalyticsTests(unittest.TestCase):
 def test_real_filter_strips_queries_hashes_and_personal_properties(self):
  script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
for(const host of ['skillwire.net','www.skillwire.net','127.0.0.1']){
 const added=[],origin='https://'+host,window={location:{origin,hostname:host}};
 const document={querySelector:()=>null,createElement:()=>({dataset:{}}),head:{append:s=>added.push(s)}};
 vm.runInNewContext(fs.readFileSync('site/analytics.js','utf8'),{window,document,URL,Set});
 const f=window.vaq[0][1];assert.equal(window.vaq[0][0],'beforeSend');
 const r=f({type:'pageview',url:origin+'/?email=person@example.test&token=private#skill-private',email:'person@example.test',data:{token:'private'}});
 assert.equal(JSON.stringify(r),JSON.stringify({type:'pageview',url:origin+'/'}));
 for(const url of [origin+'/users/person@example.test','https://foreign.example/','javascript:alert(1)'])assert.equal(f({type:'pageview',url}),null);
 assert.equal(f({type:'event',url:origin+'/',name:'email',data:{email:'private'}}),null);
 assert.equal(f(null),null);assert.equal(f({type:'pageview',url:origin+'/eval-guide.html?secret=private'}).url,origin+'/eval-guide.html');
 assert.equal(added.length,host==='127.0.0.1'?0:1);if(added.length){assert.equal(added[0].src,'/_vercel/insights/script.js');assert.equal(added[0].defer,true);}
}
console.log('PASS: actual privacy callback and official loader, no network');
'''
  p=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_every_public_page_uses_external_bootstrap_under_existing_csp(self):
  for name in ['index.html','eval-guide.html','human-review.html']:
   text=(ROOT/'site'/name).read_text();self.assertIn('<script defer src="analytics.js"></script>',text);self.assertIn('name="referrer" content="origin"',text)
if __name__=='__main__':unittest.main()
