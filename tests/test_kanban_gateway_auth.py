import time, hashlib, hmac, json, pathlib
from kanban_gateway.auth import HMACVerifier, load_agent_keys


def _sign(body: dict, key: str) -> str:
    canonical = HMACVerifier.canonicalize(body)
    return hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def test_valid_request():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "abc"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) == "strategy"


def test_expired_request():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=10)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()) - 20, "nonce": "n1"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_replay_rejected():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "n2"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) == "strategy"
    assert v.verify(body) is None  # same nonce = replay


def test_unknown_agent_id():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "unknown", "ts": int(time.time()), "nonce": "n3"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_missing_agent_id():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "ts": int(time.time()), "nonce": "n4"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_missing_ts():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "nonce": "n5"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_missing_nonce():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time())}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_missing_hmac():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "n6"}
    assert v.verify(body) is None


def test_bad_signature_wrong_secret():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "n7"}
    sig = _sign(body, "wrongsecret")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_wrong_sha256_prefix():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "n8"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"md5={sig}"
    assert v.verify(body) is None


def test_missing_sha256_prefix():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": int(time.time()), "nonce": "n9"}
    sig = _sign(body, "secret123")
    body["hmac"] = sig
    assert v.verify(body) is None


def test_ts_non_numeric():
    keys = {"strategy": "secret123"}
    v = HMACVerifier(keys, time_window=300)
    body = {"taskId": "T1", "agentId": "strategy", "ts": "not_a_number", "nonce": "n10"}
    sig = _sign(body, "secret123")
    body["hmac"] = f"sha256={sig}"
    assert v.verify(body) is None


def test_load_agent_keys_single_workspace(tmp_path: pathlib.Path):
    ws = tmp_path / "workspace-strategy"
    ws.mkdir()
    (ws / ".kanban_key").write_text("secret123\n")
    keys = load_agent_keys(tmp_path)
    assert keys == {"strategy": "secret123"}


def test_load_agent_keys_skips_missing_key(tmp_path: pathlib.Path):
    ws = tmp_path / "workspace-finance"
    ws.mkdir()
    keys = load_agent_keys(tmp_path)
    assert "finance" not in keys
    assert keys == {}


def test_load_agent_keys_multiple_workspaces(tmp_path: pathlib.Path):
    ws1 = tmp_path / "workspace-strategy"
    ws1.mkdir()
    (ws1 / ".kanban_key").write_text("secretA\n")
    ws2 = tmp_path / "workspace-review"
    ws2.mkdir()
    (ws2 / ".kanban_key").write_text("secretB\n")
    keys = load_agent_keys(tmp_path)
    assert keys == {"review": "secretB", "strategy": "secretA"}
