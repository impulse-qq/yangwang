import json, time, hmac, hashlib, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from kanban_client.client import KanbanClient


class _FakeHandler(BaseHTTPRequestHandler):
    verification_error = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        body = json.loads(raw)

        # Verify agentId
        if body.get("agentId") != "strategy":
            _FakeHandler.verification_error = f"bad agentId: {body.get('agentId')}"
            self.send_response(400)
            self.end_headers()
            return

        # Extract and verify HMAC
        received_hmac = body.pop("hmac", "")
        if not received_hmac.startswith("sha256="):
            _FakeHandler.verification_error = f"bad hmac prefix: {received_hmac}"
            self.send_response(400)
            self.end_headers()
            return
        received_sig = received_hmac.split("=", 1)[1]

        canonical = json.dumps({k: v for k, v in body.items() if k != "hmac"},
                               sort_keys=True, ensure_ascii=False)
        expected_sig = hmac.new("secret".encode(), canonical.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received_sig, expected_sig):
            _FakeHandler.verification_error = (
                f"hmac mismatch: received={received_sig}, expected={expected_sig}"
            )
            self.send_response(403)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, *a):
        pass


def test_client_signs_and_sends():
    _FakeHandler.verification_error = None
    srv = HTTPServer(("127.0.0.1", 0), _FakeHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    port = srv.server_address[1]

    client = KanbanClient(
        agent_id="strategy",
        key="secret",
        base_url=f"http://127.0.0.1:{port}"
    )
    result = client.state("T001", "AuditReview", "方案提交审核")
    assert result["ok"] is True
    assert _FakeHandler.verification_error is None, _FakeHandler.verification_error
    srv.shutdown()
