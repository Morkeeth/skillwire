"""Capture ranked marketplace anchors without matching across neighboring rows."""
import datetime,hashlib,json,re,sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from pull_catalog import get
class Rows(HTMLParser):
    def __init__(self):super().__init__();self.active=None;self.depth=0;self.capture=None;self.rows=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a':
            match=re.fullmatch(r'/([^/]+)/([^/]+)/([^/]+)',attrs.get('href',''))
            if match:self.active={'owner':match[1],'repo':match[2],'slug':match[3],'spans':[],'name':'','source':''};self.depth=1
            return
        if self.active:
            if tag=='span':self.capture=('span','')
            elif tag in ['h3','p']:self.capture=(tag,'')
    def handle_data(self,text):
        if self.active and self.capture:self.capture=(self.capture[0],self.capture[1]+text)
    def handle_endtag(self,tag):
        if not self.active:return
        if self.capture and tag==self.capture[0]:
            kind,text=self.capture;self.capture=None;text=text.strip()
            if kind=='span':self.active['spans'].append(text)
            elif kind=='h3':self.active['name']=text
            elif kind=='p':self.active['source']=text
        if tag=='a':
            a=self.active;self.active=None;rank=next((int(s) for s in a['spans'] if s.isdigit()),None);values=[s for s in a['spans'] if re.fullmatch(r'[0-9.,]+[KMB]?',s,re.I)]
            if rank and a['name'] and len(values)>=2:
                repo=a['owner']+'/'+a['repo'];self.rows.append({'rank':rank,'name':a['name'],'slug':a['slug'],'repo':repo,'installs_display':values[-1],'marketplace_url':'https://skills.sh/'+repo+'/'+quote(a['slug'])})
def main():
    raw=get('https://skills.sh/');p=Rows();p.feed(raw.decode());byrank={}
    for r in p.rows:byrank.setdefault(r['rank'],r)
    rows=[byrank[n] for n in sorted(byrank)]
    if not rows or len({r['rank'] for r in rows})!=len(rows):raise ValueError('No stable ranked rows')
    gaps=sorted(set(range(1,max(byrank)+1))-set(byrank))
    previous=ROOT/'evidence/marketplace-live.json'
    if previous.exists() and not (ROOT/'evidence/marketplace-live-parser-v1.json').exists():previous.rename(ROOT/'evidence/marketplace-live-parser-v1.json')
    (ROOT/'data/marketplace-live.html').write_bytes(raw);previous.write_text(json.dumps({'url':'https://skills.sh/','fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'raw_sha256':hashlib.sha256(raw).hexdigest(),'parser':'Scoped anchor parser over every publicly listed ranked skill anchor; provider rank gaps retained','provider_rank_gaps':gaps,'rows':rows},indent=2));print(len(rows),'public ranked entries; repo count',len({r['repo'] for r in rows}))
if __name__=='__main__':main()
