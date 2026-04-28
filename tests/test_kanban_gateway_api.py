import json
import hmac
import hashlib
import threading
import time
import urllib.error
import urllib.request

import pytest

from kanban_gateway.gateway import KanbanGateway


@pytest.fixture
def gateway(tmp_path):
    gw = KanbanGateway(
        data_dir=str(tmp_path),
        port=0,
        keys={"vice": "kv", "strategy": "ks", "review": "kr", "dispatch": "kd", "finance": "kf"},
    )
    t = threading.Thread(target=gw.serve_forever, daemon=True)
    t.start()
    yield gw
    gw.shutdown()


def _sign(body: dict, key: bytes) -> dict:
    payload = dict(body)
    payload.pop("hmac", None)
    sig = hmac.new(key, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    payload["hmac"] = f"sha256={sig}"
    return payload


def _post(port, path, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_create_and_state_flow(gateway):
    port = gateway.server_port

    # Create task
    body = {
        "taskId": "T001",
        "title": "测试任务创建",
        "state": "Strategy",
        "org": "策划部",
        "official": "策划部长",
    }
    status, resp = _post(port, "/api/v1/kanban/create", body)
    assert status == 200
    assert resp["ok"] is True
    assert resp["taskId"] == "T001"

    # State transition Strategy -> AuditReview
    payload = _sign(
        {
            "taskId": "T001",
            "newState": "AuditReview",
            "agentId": "strategy",
            "ts": int(time.time()),
            "nonce": "n1",
        },
        b"ks",
    )
    status, resp = _post(port, "/api/v1/kanban/state", payload)
    assert status == 200
    assert resp["ok"] is True
    assert resp["newState"] == "AuditReview"


def test_create_duplicate_returns_409(gateway):
    port = gateway.server_port
    body = {
        "taskId": "T002",
        "title": "测试重复创建",
        "state": "Pending",
        "org": "策划部",
        "official": "策划部长",
    }
    status, resp = _post(port, "/api/v1/kanban/create", body)
    assert status == 200
    status, resp = _post(port, "/api/v1/kanban/create", body)
    assert status == 409
    assert resp["code"] == "TASK_EXISTS"


def test_auth_missing_hmac_returns_401(gateway):
    port = gateway.server_port
    payload = {
        "taskId": "T003",
        "newState": "AuditReview",
        "agentId": "strategy",
        "ts": int(time.time()),
        "nonce": "n2",
        # no hmac
    }
    status, resp = _post(port, "/api/v1/kanban/state", payload)
    assert status == 401
    assert resp["code"] == "UNAUTHORIZED"


def test_permission_failure_returns_403(gateway):
    port = gateway.server_port
    # finance does not have "state" permission
    payload = _sign(
        {
            "taskId": "T004",
            "newState": "AuditReview",
            "agentId": "finance",
            "ts": int(time.time()),
            "nonce": "n3",
        },
        b"kf",
    )
    status, resp = _post(port, "/api/v1/kanban/state", payload)
    assert status == 403
    assert resp["code"] == "FORBIDDEN"


def test_invalid_state_transition_returns_409(gateway):
    port = gateway.server_port
    # Create task in Pending
    body = {
        "taskId": "T005",
        "title": "测试无效状态转换",
        "state": "Pending",
        "org": "策划部",
        "official": "策划部长",
    }
    status, resp = _post(port, "/api/v1/kanban/create", body)
    assert status == 200

    # Pending -> Done is invalid
    payload = _sign(
        {
            "taskId": "T005",
            "newState": "Done",
            "agentId": "vice",
            "ts": int(time.time()),
            "nonce": "n4",
        },
        b"kv",
    )
    status, resp = _post(port, "/api/v1/kanban/state", payload)
    assert status == 409
    assert resp["code"] == "INVALID_TRANSITION"


def test_high_risk_transition_returns_202(gateway):
    port = gateway.server_port
    # Create task in Doing so we can test a valid high-risk transition
    body = {
        "taskId": "T006",
        "title": "测试高风险转换",
        "state": "Doing",
        "org": "执行中",
        "official": "执行部长",
    }
    status, resp = _post(port, "/api/v1/kanban/create", body)
    assert status == 200

    # Doing -> Cancelled is high-risk per HIGH_RISK_TRANSITIONS
    payload = _sign(
        {
            "taskId": "T006",
            "newState": "Cancelled",
            "agentId": "strategy",
            "ts": int(time.time()),
            "nonce": "n5",
        },
        b"ks",
    )
    status, resp = _post(port, "/api/v1/kanban/state", payload)
    assert status == 202
    assert resp["code"] == "HIGH_RISK_PENDING"
    assert resp["pendingConfirm"] is True

    # Verify task is in PendingConfirm
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/kanban/task/T006")
    resp = json.loads(urllib.request.urlopen(req).read())
    assert resp["task"]["state"] == "PendingConfirm"


def test_get_task_200_and_404(gateway):
    port = gateway.server_port
    body = {
        "taskId": "T007",
        "title": "测试获取任务",
        "state": "Pending",
        "org": "策划部",
        "official": "策划部长",
    }
    _post(port, "/api/v1/kanban/create", body)

    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/kanban/task/T007")
    resp = json.loads(urllib.request.urlopen(req).read())
    assert resp["ok"] is True
    assert resp["task"]["id"] == "T007"

    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/kanban/task/NOTFOUND")
    try:
        urllib.request.urlopen(req)
        assert False, "should 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_flow_404_for_missing_task(gateway):
    port = gateway.server_port
    payload = _sign(
        {
            "taskId": "MISSING",
            "fromDept": "策划部",
            "toDept": "监察部",
            "agentId": "strategy",
            "ts": int(time.time()),
            "nonce": "n6",
        },
        b"ks",
    )
    status, resp = _post(port, "/api/v1/kanban/flow", payload)
    assert status == 404
    assert resp["code"] == "TASK_NOT_FOUND"


def test_done_bypasses_state_machine(gateway):
    port = gateway.server_port
    body = {
        "taskId": "T008",
        "title": "测试完成状态机",
        "state": "Pending",
        "org": "策划部",
        "official": "策划部长",
    }
    _post(port, "/api/v1/kanban/create", body)

    # Pending -> Done is invalid according to state machine; vice lacks "done" permission,
    # so we use finance (which has "done") to test state-machine rejection.
    payload = _sign(
        {
            "taskId": "T008",
            "outputPath": "/tmp/out",
            "summary": "完成了",
            "agentId": "finance",
            "ts": int(time.time()),
            "nonce": "n7",
        },
        b"kf",
    )
    status, resp = _post(port, "/api/v1/kanban/done", payload)
    assert status == 409
    assert resp["code"] == "INVALID_TRANSITION"

    # Move to Doing first (via valid path) using vice/state, then finance/done
    for st, key, nonce, agent in [
        ("Vice", b"kv", "n8", "vice"),
        ("Strategy", b"ks", "n9", "strategy"),
        ("AuditReview", b"ks", "n10", "strategy"),
        ("Assigned", b"ks", "n11", "strategy"),
        ("Doing", b"ks", "n12", "strategy"),
    ]:
        payload = _sign(
            {"taskId": "T008", "newState": st, "agentId": agent, "ts": int(time.time()), "nonce": nonce},
            key,
        )
        status, resp = _post(port, "/api/v1/kanban/state", payload)
        assert status == 200, resp

    # Doing -> Done is valid for finance
    payload = _sign(
        {
            "taskId": "T008",
            "outputPath": "/tmp/out",
            "summary": "完成了",
            "agentId": "finance",
            "ts": int(time.time()),
            "nonce": "n13",
        },
        b"kf",
    )
    status, resp = _post(port, "/api/v1/kanban/done", payload)
    assert status == 200
    assert resp["ok"] is True


def test_concurrent_state_changes(gateway):
    port = gateway.server_port
    body = {
        "taskId": "T009",
        "title": "测试并发状态变更",
        "state": "Strategy",
        "org": "策划部",
        "official": "策划部长",
    }
    _post(port, "/api/v1/kanban/create", body)

    results = []

    def transition(nonce):
        payload = _sign(
            {
                "taskId": "T009",
                "newState": "AuditReview",
                "agentId": "strategy",
                "ts": int(time.time()),
                "nonce": nonce,
            },
            b"ks",
        )
        status, resp = _post(port, "/api/v1/kanban/state", payload)
        results.append((status, resp))

    threads = [threading.Thread(target=transition, args=(f"c{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # With atomic_update, exactly one thread wins the race and transitions;
    # the rest see the already-updated state. All responses are valid (200 or 409).
    # Final state must be AuditReview.
    assert all(status in (200, 409) for status, _ in results), results
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/kanban/task/T009")
    resp = json.loads(urllib.request.urlopen(req).read())
    assert resp["task"]["state"] == "AuditReview"


def test_payload_too_large(gateway):
    port = gateway.server_port
    # Use a payload just over the 1 MB limit so the server rejects it quickly
    payload = _sign(
        {
            "taskId": "T010",
            "newState": "AuditReview",
            "agentId": "strategy",
            "ts": int(time.time()),
            "nonce": "n14",
            "big": "x" * 999_900,
        },
        b"ks",
    )
    status, resp = _post(port, "/api/v1/kanban/state", payload)
    assert status == 413
    assert resp["code"] == "PAYLOAD_TOO_LARGE"
