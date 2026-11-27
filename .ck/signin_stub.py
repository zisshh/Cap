"""signin_stub.py <port> <log>: builder CK's scratch stand-in for the desktop endpoints a signed-in
Pro account uses for meeting notes (capabilities, plan, transcribe, notes). Scratch only."""
import http.server
import json
import sys
import threading
import time
import urllib.parse

PORT, LOG = int(sys.argv[1]), sys.argv[2]
lock = threading.Lock()


def log(entry):
    entry["t"] = int(time.time() * 1000)
    with lock:
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        log({"method": "GET", "path": url.path, "auth": self.headers.get("Authorization", "")[:20]})
        if url.path == "/api/desktop/meetings/capabilities":
            return self._json(200, {
                "transcription": True,
                "notes": True,
                "limits": {"maxClipSeconds": 30, "maxClipBytes": 4_000_000, "maxTranscriptChars": 400_000},
            })
        if url.path == "/api/desktop/plan":
            return self._json(200, {"upgraded": True})
        return self._json(200, {})

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        log({"method": "POST", "path": url.path, "bytes": len(body),
             "auth": self.headers.get("Authorization", "")[:20]})
        if url.path == "/api/desktop/meetings/transcribe":
            words = [{"text": f"word{k}", "startMs": k * 400, "endMs": k * 400 + 300} for k in range(6)]
            return self._json(200, {"text": " ".join(w["text"] for w in words), "words": words})
        if url.path == "/api/desktop/meetings/notes":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for name, data in [("title", {"title": "Scripted meeting"}),
                               ("delta", {"text": "## Summary\n- Scripted notes.\n"}), ("done", {})]:
                self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.05)
            self.close_connection = True
            return
        return self._json(200, {})


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
