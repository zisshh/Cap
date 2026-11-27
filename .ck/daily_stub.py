"""daily_stub.py <port> <log>: builder CK's scratch stand-in for the desktop meeting endpoints.
The first transcribe request is held until a second one is in flight, then answered with the
daily audio limit (429 daily_audio_limit, an hour to the reset); every later transcribe request
fails with a 500. So one track hits the daily limit while the other track's clip is still being
sent and then fails as an ordinary server error. Scratch only, never shipped."""
import http.server
import json
import sys
import threading
import time
import urllib.parse

PORT, LOG = int(sys.argv[1]), sys.argv[2]
lock = threading.Lock()
state = {"n": 0}
second = threading.Event()


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
        log({"method": "GET", "path": url.path})
        if url.path == "/api/desktop/meetings/capabilities":
            return self._json(200, {
                "transcription": True,
                "notes": True,
                "limits": {"maxClipSeconds": 30, "maxClipBytes": 4_000_000, "maxTranscriptChars": 400_000},
            })
        return self._json(200, {})

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if url.path != "/api/desktop/meetings/transcribe":
            log({"method": "POST", "path": url.path})
            return self._json(200, {})
        with lock:
            n = state["n"]
            state["n"] += 1
        log({"method": "POST", "path": url.path, "n": n, "phase": "received"})
        if n == 0:
            held = second.wait(30)
            log({"n": n, "answer": 429, "held_for_second": held})
            return self._json(429, {"error": "daily_audio_limit", "retryAfterSeconds": 3600})
        if n == 1:
            second.set()
            time.sleep(2)
        log({"n": n, "answer": 500})
        return self._json(500, {"error": "server_error"})


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
