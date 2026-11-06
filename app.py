"""Namaste: a very small web app to try Shipyard with. No dependencies.

  /                 a greeting
  /hello?lang=ta&name=Anya   in Hindi (hi), Tamil (ta), Bengali (bn), Marathi (mr) or English (en)
  /health           ok
  /boom             logs an ERROR and answers 500, so there is something to alert on

Logs go to stdout and, when OTLP_LOGS_URL is set (for example http://host.k3d.internal:4318/v1/logs), to SigNoz or any OpenTelemetry collector.
"""
import json
import logging
import os
import queue
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SERVICE = os.environ.get("SERVICE_NAME", "namaste")
POD = os.environ.get("POD_NAME", socket.gethostname())
NAMESPACE = os.environ.get("POD_NAMESPACE", "")
GREETINGS = {"en": "Hello", "hi": "Namaste", "ta": "Vanakkam", "bn": "Nomoshkar", "mr": "Namaskar"}
SEVERITY = {logging.DEBUG: 5, logging.INFO: 9, logging.WARNING: 13, logging.ERROR: 17, logging.CRITICAL: 21}

log = logging.getLogger("namaste")


def greeting(lang: str) -> str:
    return GREETINGS.get(lang, GREETINGS["hi"])


def clean_name(name: str) -> str:
    kept = "".join(c for c in name if c.isalnum() or c in " -_.")[:40].strip()
    return kept or "friend"


def render(lang: str = "hi", name: str = "friend") -> str:
    return f"{greeting(lang)}, {clean_name(name)}! (served by {POD})\n"


def health() -> str:
    return "ok\n"


def otlp_payload(records: list) -> dict:
    """OpenTelemetry's JSON format for logs (OTLP/HTTP)."""
    attrs = [("service.name", SERVICE), ("k8s.pod.name", POD)] + ([("k8s.namespace.name", NAMESPACE)] if NAMESPACE else [])
    return {"resourceLogs": [{
        "resource": {"attributes": [{"key": k, "value": {"stringValue": v}} for k, v in attrs]},
        "scopeLogs": [{"scope": {"name": "namaste"}, "logRecords": [
            {"timeUnixNano": str(int(r.created * 1e9)), "severityNumber": SEVERITY.get(r.levelno, 9), "severityText": r.levelname,
             "body": {"stringValue": r.getMessage()}} for r in records]}]}]}


class OtlpHandler(logging.Handler):
    """Sends log lines to an OTLP/HTTP endpoint in the background. A slow or missing collector never slows or breaks the app."""

    def __init__(self, url: str, every: float = 2.0):
        super().__init__()
        self.url, self.every = url, every
        self.q: "queue.Queue[logging.LogRecord]" = queue.Queue(maxsize=1000)
        threading.Thread(target=self._loop, daemon=True).start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put_nowait(record)
        except queue.Full:
            pass

    def _loop(self) -> None:
        while True:
            time.sleep(self.every)
            batch = []
            while len(batch) < 200:
                try:
                    batch.append(self.q.get_nowait())
                except queue.Empty:
                    break
            if batch:
                self.send(batch)

    def send(self, batch: list) -> None:
        try:
            req = urllib.request.Request(self.url, data=json.dumps(otlp_payload(batch)).encode(), headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:                       # the collector is down: the lines are still on stdout
            pass


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, body: str) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        q = parse_qs(url.query)
        path = url.path.rstrip("/") or "/"                      # /hello/ is the same page as /hello, not a redirect back and forth
        if path == "/health":
            return self._reply(200, health())
        if path == "/boom":
            log.error("payment gateway timeout after 30s (order %s)", q.get("order", ["unknown"])[0][:20])
            return self._reply(500, "something went wrong\n")
        if path in ("/", "/hello"):
            lang, name = q.get("lang", ["hi"])[0], q.get("name", ["friend"])[0]
            log.info("greeted %r in %s", clean_name(name), lang if lang in GREETINGS else "hi")
            return self._reply(200, render(lang, name))
        log.warning("not found: %s", url.path[:60])
        return self._reply(404, "not found\n")

    def log_message(self, *args) -> None:
        pass


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if os.environ.get("OTLP_LOGS_URL"):
        logging.getLogger().addHandler(OtlpHandler(os.environ["OTLP_LOGS_URL"]))


if __name__ == "__main__":
    setup_logging()
    log.info("namaste is up on pod %s", POD)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
