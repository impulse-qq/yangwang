"""KanbanGateway HTTP server — the control plane for all task mutations."""
from datetime import datetime, timezone
import json
import logging
import pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from .store import atomic_read, atomic_update
from .auth import HMACVerifier
from .policy import PolicyEngine

__all__ = ["KanbanGateway", "GatewayError"]

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


class GatewayError(Exception):
    def __init__(self, message: str, code: str, status: int = 400):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(message)


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
        if length > 1_000_000:
            # Discard the oversize body so the client receives the 413 cleanly.
            self.rfile.read(length)
            self._send_json({"ok": False, "error": "PAYLOAD_TOO_LARGE", "code": "PAYLOAD_TOO_LARGE"}, 413)
            return
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            self._send_json({"ok": False, "error": "INVALID_JSON"}, 400)
            return

        try:
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
        except GatewayError as e:
            self._send_json({"ok": False, "error": e.message, "code": e.code}, e.status)
        except Exception as e:
            log.exception("Unhandled error in %s", p)
            self._send_json({"ok": False, "error": "INTERNAL_ERROR", "code": "INTERNAL_ERROR"}, 500)

    def _auth(self, body: dict) -> str:
        agent_id = self.server._verifier.verify(body)
        if not agent_id:
            raise GatewayError("UNAUTHORIZED", "UNAUTHORIZED", 401)
        return agent_id

    def _check_perm(self, agent_id: str, cmd: str) -> bool:
        if not self.server._policy.check_permission(agent_id, cmd):
            raise GatewayError(
                f"Agent {agent_id} cannot execute {cmd}", "FORBIDDEN", 403
            )
        return True

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _handle_create(self, body):
        title = self.server._policy.sanitize_title(body.get("title", ""))
        ok, reason = self.server._policy.validate_task_title(title)
        if not ok:
            raise GatewayError(reason, "INVALID_TITLE", 400)

        task_id = body.get("taskId")
        if not task_id:
            raise GatewayError("taskId is required", "MISSING_TASK_ID", 400)
        state = body.get("state", "Pending")
        org = STATE_ORG_MAP.get(state, body.get("org", ""))
        official = body.get("official", "")
        remark = self.server._policy.sanitize_remark(body.get("remark", ""))

        def modifier(tasks):
            if any(t.get("id") == task_id for t in tasks):
                raise GatewayError("Task already exists", "TASK_EXISTS", 409)
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
        self._check_perm(agent_id, "state")
        task_id = body.get("taskId")
        new_state = body.get("newState")
        now_text = body.get("nowText", "")
        high_risk = False
        old_state = None

        def modifier(tasks):
            nonlocal high_risk, old_state
            task = next((t for t in tasks if t.get("id") == task_id), None)
            if not task:
                raise GatewayError("Task not found", "TASK_NOT_FOUND", 404)

            old_state = task.get("state", "")
            if not self.server._policy.check_transition(old_state, new_state):
                raise GatewayError(
                    f"Invalid transition {old_state} → {new_state}",
                    "INVALID_TRANSITION",
                    409,
                )

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
                task["updatedAt"] = self._now_iso()
                high_risk = True
                return tasks

            task["state"] = new_state
            if new_state in STATE_ORG_MAP:
                task["org"] = STATE_ORG_MAP[new_state]
            if now_text:
                task["now"] = now_text
            task["updatedAt"] = self._now_iso()
            return tasks

        atomic_update(self.server._tasks_file, modifier, [])
        if high_risk:
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
        self._check_perm(agent_id, "flow")
        task_id = body.get("taskId")
        from_dept = body.get("fromDept", "")
        to_dept = body.get("toDept", "")
        remark = self.server._policy.sanitize_remark(body.get("remark", ""))

        def modifier(tasks):
            t = next((x for x in tasks if x.get("id") == task_id), None)
            if not t:
                raise GatewayError("Task not found", "TASK_NOT_FOUND", 404)
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
        self._check_perm(agent_id, "progress")
        # TODO: stub — progress log entry not yet implemented
        self._send_json({"ok": True})

    def _handle_todo(self, body):
        agent_id = self._auth(body)
        self._check_perm(agent_id, "todo")
        # TODO: stub — todo tracking not yet implemented
        self._send_json({"ok": True})

    def _handle_done(self, body):
        agent_id = self._auth(body)
        self._check_perm(agent_id, "done")
        task_id = body.get("taskId")
        output = body.get("outputPath", "")
        summary = body.get("summary", "")

        def modifier(tasks):
            t = next((x for x in tasks if x.get("id") == task_id), None)
            if not t:
                raise GatewayError("Task not found", "TASK_NOT_FOUND", 404)
            old_state = t.get("state", "")
            if not self.server._policy.check_transition(old_state, "Done"):
                raise GatewayError(
                    f"Invalid transition {old_state} → Done",
                    "INVALID_TRANSITION",
                    409,
                )
            t["state"] = "Done"
            t["output"] = output
            t["now"] = summary or "任务已完成"
            t["updatedAt"] = self._now_iso()
            return tasks

        atomic_update(self.server._tasks_file, modifier, [])
        self._send_json({"ok": True})

    def _handle_review(self, body):
        agent_id = self._auth(body)
        self._check_perm(agent_id, "confirm")
        task_id = body.get("taskId")
        action = body.get("action")
        comment = body.get("comment", "")

        def modifier(tasks):
            task = next((t for t in tasks if t.get("id") == task_id), None)
            if not task:
                raise GatewayError("Task not found", "TASK_NOT_FOUND", 404)

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
                raise GatewayError("Invalid action", "INVALID_ACTION", 400)

            task["updatedAt"] = self._now_iso()
            return tasks

        atomic_update(self.server._tasks_file, modifier, [])
        self._send_json({"ok": True})


class KanbanGateway(HTTPServer):
    def __init__(self, data_dir: str, port: int = 7892, keys: dict = None):
        self._data_dir = pathlib.Path(data_dir)
        self._tasks_file = self._data_dir / "tasks_source.json"
        # TODO: implement audit logging
        self._audit_file = self._data_dir / "audit_log.json"
        self._verifier = HMACVerifier(keys or {}, time_window=300)
        self._policy = PolicyEngine()
        super().__init__(("127.0.0.1", port), _Handler)

    @property
    def server_port(self):
        return self.server_address[1]

    @server_port.setter
    def server_port(self, value):
        # Necessary no-op: socketserver sets this during bind with port=0.
        # We ignore writes because the canonical value lives in server_address.
        pass
