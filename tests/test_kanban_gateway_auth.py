import time, hashlib, hmac, json
from kanban_gateway.auth import HMACVerifier


def test_valid_request():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "abc"}
    sig = hmac.new(b"secret123", json.dumps(body, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) == "strategy"


def test_expired_request():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=10)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()) - 20, "nonce": "n1"}
    sig = hmac.new(b"secret123", json.dumps(body, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_replay_rejected():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "n2"}
    sig = hmac.new(b"secret123", json.dumps(body, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) == "strategy"
    assert v.verify(body) is None  # same nonce = replay
