from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.agent import analyze_prompt
from app.schema import KycAnalysisResponse


class KycHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/api/kyc-intelligence/analyze":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8") or "{}")
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "prompt is required"})
                return

            result = analyze_prompt(prompt)
            validated = KycAnalysisResponse.model_validate(result)
            self._write_json(HTTPStatus.OK, validated.model_dump(mode="json"))
        except NotImplementedError as exc:
            self._write_json(
                HTTPStatus.NOT_IMPLEMENTED,
                {"error": "not_implemented", "detail": str(exc)},
            )
        except Exception as exc:  # pragma: no cover - starter server safety net
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "server_error", "detail": str(exc)},
            )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    host = os.getenv("KYC_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("KYC_AGENT_PORT", "8011"))
    server = ThreadingHTTPServer((host, port), KycHandler)
    print(f"KYC starter server listening on http://{host}:{port}")
    server.serve_forever()
