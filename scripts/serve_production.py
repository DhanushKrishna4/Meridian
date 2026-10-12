"""Serve the built static application under /Meridian/ like repository Pages."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
import argparse

ROOT=Path(__file__).resolve().parents[1]/'web/dist'
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path in ('/','/Meridian'):
            self.send_response(302);self.send_header('Location','/Meridian/');self.end_headers();return
        if not path.startswith('/Meridian/'):
            self.send_error(404);return
        self.path=self.path[len('/Meridian'):]
        super().do_GET()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=4173)
    args=parser.parse_args()
    if not (ROOT/'index.html').exists():raise SystemExit('Build first: cd web && npm run build')
    print(f'Static Meridian: http://127.0.0.1:{args.port}/Meridian/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
