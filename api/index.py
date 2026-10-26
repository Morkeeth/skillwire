"""Vercel Python function for public source inspection and selected downloads."""
import json,sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import public_runtime as runtime
class handler(BaseHTTPRequestHandler):
    def send(self,status,body,content='application/json',extra=None):
        if not isinstance(body,bytes):body=json.dumps(body).encode()
        self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        u=urlsplit(self.path);q=parse_qs(u.query);route=q.get('route',[u.path.rsplit('/',1)[-1]])[0]
        try:
            if route=='inspect':return self.send(200,runtime.inspect(q.get('id',[''])[0]))
            if route=='stack':return self.send(200,runtime.bundle(q.get('ids',[''])[0].split(',')),'application/zip',{'Content-Disposition':'attachment; filename="skillwire-skill-stack.zip"'})
            return self.send(404,{'error':'Public endpoint not found.'})
        except runtime.PublicError as e:return self.send(400,{'error':str(e)})
        except Exception:return self.send(502,{'error':'Pinned public source is unavailable. Try again or open its source link.'})
    def do_POST(self):return self.send(405,{'error':'This service accepts no uploads or private skills.'})
    def log_message(self,*args):pass
