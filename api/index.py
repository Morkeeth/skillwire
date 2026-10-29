"""Vercel Python function for public source inspection and selected downloads."""
import json,sys,os
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import public_runtime as runtime
import voting
class handler(BaseHTTPRequestHandler):
    def send(self,status,body,content='application/json',extra=None):
        if not isinstance(body,bytes):body=json.dumps(body).encode()
        self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def vote_cookie(self):
        try:
            cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));return cookie['sw_vote'].value if 'sw_vote' in cookie else None
        except Exception:return None
    def vote_ip(self):
        return self.headers.get('x-vercel-forwarded-for','').split(',')[0].strip() if os.environ.get('VERCEL') else self.client_address[0]
    def vote_origin(self):
        allowed={'https://skillwire.net','https://www.skillwire.net'}
        if os.environ.get('VERCEL_URL'):allowed.add('https://'+os.environ['VERCEL_URL'])
        allowed.update(x for x in os.environ.get('SKILLWIRE_VOTE_ORIGINS','').split(',') if x)
        return self.headers.get('Origin') in allowed
    def do_GET(self):
        u=urlsplit(self.path);q=parse_qs(u.query);route=q.get('route',[u.path.rsplit('/',1)[-1]])[0]
        try:
            if route=='votes':
                service=voting.configured();body,cookie=service.status(self.vote_cookie(),self.vote_ip())
                import x_poll
                body['x_poll']=x_poll.public_status(service.store,service.ns)
                return self.send(200,body,extra={'Set-Cookie':'sw_vote='+cookie+'; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Strict'})
            if route=='x-poll-sync':
                import x_poll
                return self.send(200,x_poll.sync(self.headers.get('Authorization','')))
            if route=='inspect':return self.send(200,runtime.inspect(q.get('id',[''])[0]))
            if route=='stack':return self.send(200,runtime.bundle(q.get('ids',[''])[0].split(',')),'application/zip',{'Content-Disposition':'attachment; filename="skillwire-skill-stack.zip"'})
            return self.send(404,{'error':'Public endpoint not found.'})
        except voting.VoteError as e:return self.send(e.status,{'error':str(e)})
        except runtime.PublicError as e:return self.send(400,{'error':str(e)})
        except Exception:return self.send(502,{'error':'Pinned public source is unavailable. Try again or open its source link.'})
    def do_POST(self):
        u=urlsplit(self.path);route=parse_qs(u.query).get('route',[u.path.rsplit('/',1)[-1]])[0]
        if route!='vote':return self.send(405,{'error':'This service accepts no uploads or private skills.'})
        try:
            if not self.vote_origin():raise voting.VoteError(403,'Refresh this page before voting.')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise voting.VoteError(415,'Use a JSON vote request.')
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:raise voting.VoteError(400,'Invalid vote request.')
            if not 0<length<=1024:raise voting.VoteError(413,'Vote request too large or empty.')
            try:body=json.loads(self.rfile.read(length))
            except (ValueError,UnicodeDecodeError):raise voting.VoteError(400,'Invalid vote request.')
            if not isinstance(body,dict) or not isinstance(body.get('skill_id'),str):raise voting.VoteError(400,'Choose a published skill.')
            result=voting.configured().cast(self.vote_cookie(),self.vote_ip(),body.get('skill_id'),body.get('csrf'),True,body.get('website',''))
            return self.send(201,result)
        except voting.VoteError as e:return self.send(e.status,{'error':str(e)})
        except Exception:return self.send(503,{'error':'Community voting is temporarily unavailable.'})
    def log_message(self,*args):pass
