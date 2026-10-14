"""
LLM Guard sidecar: a tiny HTTP wrapper around llm-guard's PromptInjection scanner.

It runs in its own container so llm-guard's strict dependency pins (transformers, torch,
regex, ...) never have to co-resolve with the backend's Pydantic AI / provider SDK stack.

  GET  /health          -> {"ok": true, "match_type": "..."}
  POST /scan {"text"}   -> {"is_valid": bool, "risk_score": float}

Standard library HTTP server only, so the image needs nothing beyond llm-guard itself.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from llm_guard.input_scanners import PromptInjection
from llm_guard.input_scanners.prompt_injection import MatchType

THRESHOLD = float(os.getenv("LLM_GUARD_THRESHOLD", "0.5"))
# FULL truncates to the classifier's 512-token window, so an injection deep inside a long
# transcript would never be seen. CHUNKS scores the whole text window by window.
_match_name = os.getenv("LLM_GUARD_MATCH_TYPE", "CHUNKS").upper()
MATCH_TYPE = getattr(MatchType, _match_name, MatchType.FULL)

SCANNER = PromptInjection(threshold=THRESHOLD, match_type=MATCH_TYPE)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "match_type": MATCH_TYPE.name, "threshold": THRESHOLD})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/scan":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            text = json.loads(self.rfile.read(length) or b"{}").get("text", "")
            _, is_valid, risk_score = SCANNER.scan(text)
            self._send(200, {"is_valid": bool(is_valid), "risk_score": float(risk_score),
                             "threshold": THRESHOLD, "match_type": MATCH_TYPE.name})
        except Exception as e:  # report, don't crash the server
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):  # keep transcripts out of the container log
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"llm-guard sidecar on :{port} (match_type={MATCH_TYPE.name}, threshold={THRESHOLD})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
