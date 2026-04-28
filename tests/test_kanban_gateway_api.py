import json
import threading
import time
import urllib.request

from kanban_gateway.gateway import KanbanGateway


def test_create_and_state_flow():
    gw = KanbanGateway(
        data_dir="/tmp/test_kg_data",
        port=0,  # auto-assign
        keys={"vice": "kv", "strategy": "ks"},
    )
    t = threading.Thread(target=gw.serve_forever, daemon=True)
    t.start()
    port = gw.server_port

    # Create task
    body = {
        "taskId": "T001",
        "title": "测试任务创建",
        "state": "Strategy",
        "org": "策划部",
        "official": "策划部长",
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/kanban/create",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    assert resp["ok"] is True
    assert resp["taskId"] == "T001"

    # State transition
    import hmac, hashlib

    payload = {
        "taskId": "T001",
        "newState": "AuditReview",
        "agentId": "strategy",
        "ts": int(time.time()),
        "nonce": "n1",
    }
    sig = hmac.new(
        b"ks", json.dumps(payload, sort_keys=True).encode(), hashlib.sha256
    ).hexdigest()
    payload["hmac"] = f"sha256={sig}"
    req2 = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/kanban/state",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp2 = json.loads(urllib.request.urlopen(req2).read())
    assert resp2["ok"] is True
    assert resp2["newState"] == "AuditReview"

    gw.shutdown()
