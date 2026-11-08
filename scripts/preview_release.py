"""Read-only loopback preview of an already-built SkillWire release."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Preview(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0].startswith("/api/"):
            self.send_error(503, "Preview only: votes and source downloads use the deployed app")
            return
        super().do_GET()
    def do_POST(self):
        self.send_error(405, "Read-only preview: no votes or uploads are saved")
    do_PUT = do_DELETE = do_PATCH = do_POST
    def log_message(self, *args):
        pass

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    parser.add_argument("--port", type=int, default=18828)
    args = parser.parse_args()
    site = args.site.resolve()
    if not (site / "index.html").is_file():
        parser.error("Built catalog not found. Choose the prepared release folder with --site.")
    with ThreadingHTTPServer(("127.0.0.1", args.port), partial(Preview, directory=str(site))) as server:
        print(f"SkillWire preview: http://127.0.0.1:{server.server_port} | read-only, no votes saved", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
