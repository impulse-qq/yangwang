"""KanbanGateway HTTP server — the control plane for all task mutations."""
import json
import logging
import pathlib
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from .store import atomic_read, atomic_write, atomic_update
from .auth import HMACVerifier, load_agent_keys
from .policy import PolicyEngine

log = logging.getLogger("kanban.gateway")

STATE_ORG_MAP = {
    "Vice": "副团长",
    "Strategy": "策划部",
    "AuditReview": "监察部",
    "Review": "调度部",
    "Assigned": "调度部",
    "Next": "调度部",
    "Doing": "执行中",
    "Done": "完成",
    "Blocked": "阻塞",
    "PendingConfirm": "调度部",
    "Pending": "策划部",
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default logging

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        p = urlparse(self.path).path
        if p.startswith("/api/v1/kanban/task/"):
            task_id = p.replace("/api/v1/kanban/task/", "")
            tasks = atomic_read(self.server._tasks_file, [])
            task = next((t for t in tasks if t.get("id") == task_id), None)
            if task:
                self._send_json({"ok": True, "task": task})
            else:
                self._send_json({"ok": False, "error": "TASK_NOT_FOUND"}, 404)
        else:
            self._send_json({"ok": False, "error": "NOT_FOUND"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            self._send_json({"ok": False, "error": "INVALID_JSON"}, 400)
            return

        if p == "/api/v1/kanban/create":
            self._handle_create(body)
        elif p == "/api/v1/kanban/state":
            self._handle_state(body)
        elif p == "/api/v1/kanban/flow":
            self._handle_flow(body)
        elif p == "/api/v1/kanban/progress":
            self._handle_progress(body)
        elif p == "/api/v1/kanban/todo":
            self._handle_todo(body)
        elif p == "/api/v1/kanban/done":
            self._handle_done(body)
        elif p == "/api/v1/kanban/review-action":
            self._handle_review(body)
        else:
            self._send_json({"ok": False, "error": "NOT_FOUND"}, 404)

    def _auth(self, body: dict) -> str:
        agent_id = self.server._verifier.verify(body)
        if not agent_id:
            self._send_json(
                {"ok": False, "error": "UNAUTHORIZED", "code": "UNAUTHORIZED"}, 401
            )
            return ""
        return agent_id

    def _check_perm(self, agent_id: str, cmd: str) -> bool:
        if not self.server._policy.check_permission(agent_id, cmd):
            self._send_json(
                {
                    "ok": False,
                    "error": f"Agent {agent_id} cannot execute {cmd}",
                    "code": "FORBIDDEN",
                },
                403,
            )
            return False
        return True

    def _now_iso(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _handle_create(self, body):
        title = self.server._policy.sanitize_title(body.get("title", ""))
        ok, reason = self.server._policy.validate_task_title(title)
        if not ok:
            self._send_json(
                {"ok": False, "error": reason, "code": "INVALID_TITLE"}, 400
            )
            return

        task_id = body.get("taskId")
        state = body.get("state", "Pending")
        org = STATE_ORG_MAP.get(state, body.get("org", ""))
        official = body.get("official", "")
        remark = self.server._policy.sanitize_remark(body.get("remark", ""))

        def modifier(tasks):
            tasks = [t for t in tasks if t.get("id") != task_id]
            tasks.insert(
                0,
                {
                    "id": task_id,
                    "title": title,
                    "official": official,
                    "org": org,
                    "state": state,
                    "now": remark or f"已发布委托，等待{org}接令",
                    "eta": "-",
                    "block": "无",
                    "output": "",
                    "ac": "",
                    "flow_log": [
                        {
                            "at": self._now_iso(),
                            "from": "团长",
                            "to": org,
                            "remark": remark,
                        }
                    ],
                    "updatedAt": self._now_iso(),
                },
            )
            return tasks

        atomic_update(self.server._tasks_file, modifier, [])
        self._send_json({"ok": True, "taskId": task_id})

    def _handle_state(self, body):
        agent_id = self._auth(body)
        if not agent_id or not self._check_perm(agent_id, "state"):
            return
        task_id = body.get("taskId")
        new_state = body.get("newState")
        now_text = body.get("nowText", "")
        tasks = atomic_read(self.server._tasks_file, [])
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if not task:
            self._send_json(
                {"ok": False, "error": "Task not found", "code": "TASK_NOT_FOUND"}, 404
            )
            return

        old_state = task.get("state", "")
        if not self.server._policy.check_transition(old_state, new_state):
            self._send_json(
                {
                    "ok": False,
                    "error": f"Invalid transition {old_state} → {new_state}",
                    "code": "INVALID_TRANSITION",
                },
                409,
            )
            return

        if self.server._policy.is_high_risk(old_state, new_state):
            task["state"] = "PendingConfirm"
            task["pending_confirm"] = {
                "target_state": new_state,
                "requested_by": agent_id,
                "requested_at": self._now_iso(),
                "confirm_by": self.server._policy.get_confirm_authority(old_state)
                or "dispatch",
            }
            task["now"] = f"待确认: {old_state}→{new_state}"
            atomic_write(self.server._tasks_file, tasks)
            self._send_json(
                {
                    "ok": True,
                    "pendingConfirm": True,
                    "taskId": task_id,
                    "code": "HIGH_RISK_PENDING",
                },
                202,
            )
            return

        task["state"] = new_state
        if new_state in STATE_ORG_MAP:
            task["org"] = STATE_ORG_MAP[new_state]
        if now_text:
            task["now"] = now_text
        task["updatedAt"] = self._now_iso()
        atomic_write(self.server._tasks_file, tasks)
        self._send_json(
            {
                "ok": True,
                "taskId": task_id,
                "oldState": old_state,
                "newState": new_state,
            }
        )

    def _handle_flow(self, body):
        agent_id = self._auth(body)
        if not agent_id or not self._check_perm(agent_id, "flow"):
            return
        task_id = body.get("taskId")
        from_dept = body.get("fromDept", "")
        to_dept = body.get("toDept", "")
        remark = self.server._policy.sanitize_remark(body.get("remark", ""))

        def modifier(tasks):
            t = next((x for x in tasks if x.get("id") == task_id), None)
            if not t:
                return tasks
            t.setdefault("flow_log", []).append(
                {
                    "at": self._now_iso(),
                    "from": from_dept,
                    "to": to_dept,
                    "remark": remark,
                }
            )
            t["org"] = to_dept
            t["updatedAt"] = self._now_iso()
            return tasks

        atomic_update(self.server._tasks_file, modifier, [])
        self._send_json({"ok": True})

    def _handle_progress(self, body):
        agent_id = self._auth(body)
        if not agent_id or not self._check_perm(agent_id, "progress"):
            return
        # Progress is stored as a log entry; minimal implementation for now
        self._send_json({"ok": True})

    def _handle_todo(self, body):
        agent_id = self._auth(body)
        if not agent_id or not self._check_perm(agent_id, "todo"):
            return
        # TODO tracking minimal for now
        self._send_json({"ok": True})

    def _handle_done(self, body):
        agent_id = self._auth(body)
        if not agent_id or not self._check_perm(agent_id, "done"):
            return
        task_id = body.get("taskId")
        output = body.get("outputPath", "")
        summary = body.get("summary", "")

        def modifier(tasks):
            t = next((x for x in tasks if x.get("id") == task_id), None)
            if not t:
                return tasks
            t["state"] = "Done"
            t["output"] = output
            t["now"] = summary or "任务已完成"
            t["updatedAt"] = self._now_iso()
            return tasks

        atomic_update(self.server._tasks_file, modifier, [])
        self._send_json({"ok": True})

    def _handle_review(self, body):
        agent_id = self._auth(body)
        if not agent_id or not self._check_perm(agent_id, "confirm"):
            return
        task_id = body.get("taskId")
        action = body.get("action")
        comment = body.get("comment", "")
        tasks = atomic_read(self.server._tasks_file, [])
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if not task:
            self._send_json(
                {"ok": False, "error": "Task not found", "code": "TASK_NOT_FOUND"}, 404
            )
            return

        if action == "approve":
            pc = task.get("pending_confirm")
            if pc:
                task["state"] = pc.get("target_state", task["state"])
                task.pop("pending_confirm", None)
            else:
                task["state"] = "Done"
            task["now"] = comment or "审批通过"
        elif action == "reject":
            task["state"] = "Strategy"
            task["review_round"] = task.get("review_round", 0) + 1
            task["now"] = f"驳回：{comment}"
        else:
            self._send_json({"ok": False, "error": "Invalid action"}, 400)
            return

        task["updatedAt"] = self._now_iso()
        atomic_write(self.server._tasks_file, tasks)
        self._send_json({"ok": True})


class KanbanGateway(HTTPServer):
    def __init__(self, data_dir: str, port: int = 7892, keys: dict = None):
        self._data_dir = pathlib.Path(data_dir)
        self._tasks_file = self._data_dir / "tasks_source.json"
        self._audit_file = self._data_dir / "audit_log.json"
        self._verifier = HMACVerifier(keys or {}, time_window=300)
        self._policy = PolicyEngine()
        super().__init__(("127.0.0.1", port), _Handler)

    @property
    def server_port(self):
        return self.server_address[1]

    @server_port.setter
    def server_port(self, value):
        # Allow socketserver to set the attribute during bind, but we ignore it
        # because we always read from server_address.
        pass
