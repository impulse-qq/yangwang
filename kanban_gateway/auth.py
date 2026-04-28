"""HMAC request signing and verification."""
import hmac, hashlib, json, time
from typing import Optional, Dict
import pathlib
from collections import deque

__all__ = ["HMACVerifier", "load_agent_keys"]


class HMACVerifier:
    def __init__(self, keys: Dict[str, str], time_window: int = 300):
        self._keys = keys
        self._time_window = time_window
        self._seen_nonces: set = set()
        self._nonce_window: deque = deque()  # (expire_at, nonce)

    @staticmethod
    def canonicalize(body: dict) -> str:
        payload = {k: v for k, v in body.items() if k != "hmac"}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def _clean_nonces(self):
        now = time.time()
        while self._nonce_window and self._nonce_window[0][0] < now:
            _, nonce = self._nonce_window.popleft()
            self._seen_nonces.discard(nonce)

    def verify(self, body: dict) -> Optional[str]:
        """Returns agent_id if valid, else None."""
        agent_id = body.get("agentId")
        ts = body.get("ts")
        nonce = body.get("nonce")
        received_hmac = body.get("hmac", "")

        if not agent_id or not ts or not nonce or not received_hmac:
            return None

        if not isinstance(ts, (int, float)):
            return None

        key = self._keys.get(agent_id)
        if not key:
            return None

        now = time.time()
        if abs(now - ts) > self._time_window:
            return None

        self._clean_nonces()
        if nonce in self._seen_nonces:
            return None

        canonical = self.canonicalize(body)
        expected = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()

        if not received_hmac.startswith("sha256="):
            return None
        if not hmac.compare_digest(received_hmac[len("sha256="):], expected):
            return None

        self._seen_nonces.add(nonce)
        self._nonce_window.append((now + self._time_window, nonce))
        return agent_id


def load_agent_keys(base_dir: pathlib.Path) -> Dict[str, str]:
    """Load .kanban_key from each workspace-*/ directory."""
    keys = {}
    for ws in sorted(base_dir.glob("workspace-*")):
        key_file = ws / ".kanban_key"
        if key_file.exists():
            agent_id = ws.name.replace("workspace-", "")
            keys[agent_id] = key_file.read_text().strip()
    return keys
