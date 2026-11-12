"""Loopback preview of static output plus the same public Vercel handler."""
import argparse,sys,os
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from api.index import handler as PublicHandler
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'):return PublicHandler.do_GET(self)
        # Only dist is served. A request can never browse the repository or local data.
        return super().do_GET()
    send=PublicHandler.send
    vote_cookie=PublicHandler.vote_cookie
    vote_ip=PublicHandler.vote_ip
    vote_origin=PublicHandler.vote_origin
    def do_POST(self):return PublicHandler.do_POST(self)
    def log_message(self,*args):pass
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=18828);a=ap.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(Handler,directory=str(ROOT/'dist')))
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data'/('preview-'+str(a.port)+'.pid')).write_text(str(os.getpid()))
    print('SkillWire product http://127.0.0.1:'+str(a.port),flush=True);server.serve_forever()
