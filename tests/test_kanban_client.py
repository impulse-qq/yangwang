import json, time, hmac, hashlib, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from kanban_client.client import KanbanClient


class _FakeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        body = json.loads(raw)
        # Verify hmac is present and agentId is set
        assert "hmac" in body
        assert body.get("agentId") == "strategy"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, *a):
        pass


def test_client_signs_and_sends():
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
    srv.shutdown()
