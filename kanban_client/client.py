"""Lightweight KanbanGateway client — zero dependencies, stdlib only."""
import hmac, hashlib, json, os, pathlib, random, time, urllib.request
from typing import Optional


class KanbanClient:
    def __init__(self, agent_id: Optional[str] = None, key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.agent_id = agent_id or self._detect_agent_id()
        self.key = key or self._load_key()
        self.base_url = base_url or self._discover_gateway()

    @staticmethod
    def _detect_agent_id() -> str:
        for k in ("OPENCLAW_AGENT_ID", "OPENCLAW_AGENT", "AGENT_ID"):
            v = os.environ.get(k, "").strip()
            if v:
                return v
        cwd = str(pathlib.Path.cwd())
        import re
        m = re.search(r"workspace-([a-zA-Z0-9_\-]+)", cwd)
        if m:
            return m.group(1)
        return "unknown"

    def _load_key(self) -> str:
        ws = pathlib.Path.home() / ".openclaw" / f"workspace-{self.agent_id}" / ".kanban_key"
        if ws.exists():
            return ws.read_text().strip()
        return ""

    def _discover_gateway(self) -> str:
        sock = pathlib.Path("/tmp/kanban.sock")
        if sock.exists():
            return "http+unix://" + str(sock)
        return "http://127.0.0.1:7892"

    def _sign(self, payload: dict) -> dict:
        payload = dict(payload)
        payload["agentId"] = self.agent_id
        payload["ts"] = int(time.time())
        payload["nonce"] = "%016x" % random.getrandbits(64)
        canonical = json.dumps({k: v for k, v in payload.items() if k != "hmac"},
                               sort_keys=True, ensure_ascii=False)
        sig = hmac.new(self.key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        payload["hmac"] = f"sha256={sig}"
        return payload

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(self._sign(payload)).encode()
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        max_retries = 3
        last_err = None
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except Exception as e:
                last_err = e
                time.sleep(2 ** attempt)
        return {"ok": False, "error": str(last_err)}

    def state(self, task_id: str, new_state: str, now_text: str = "") -> dict:
        return self._post("/api/v1/kanban/state", {
            "taskId": task_id, "newState": new_state, "nowText": now_text,
        })

    def flow(self, task_id: str, from_dept: str, to_dept: str, remark: str = "") -> dict:
        return self._post("/api/v1/kanban/flow", {
            "taskId": task_id, "fromDept": from_dept, "toDept": to_dept, "remark": remark,
        })

    def progress(self, task_id: str, summary: str, plan: str = "") -> dict:
        return self._post("/api/v1/kanban/progress", {
            "taskId": task_id, "summary": summary, "plan": plan,
        })

    def todo(self, task_id: str, todo_id: int, title: str, status: str, detail: str = "") -> dict:
        return self._post("/api/v1/kanban/todo", {
            "taskId": task_id, "todoId": todo_id, "title": title, "status": status, "detail": detail,
        })

    def done(self, task_id: str, output_path: str = "", summary: str = "") -> dict:
        return self._post("/api/v1/kanban/done", {
            "taskId": task_id, "outputPath": output_path, "summary": summary,
        })
