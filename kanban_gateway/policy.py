"""Policy engine: state machine, permissions, data sanitization."""
import re
from typing import Optional, Tuple

# Try to import canonical state machine from backend, fallback to inline
try:
    from edict.backend.app.models.task import STATE_TRANSITIONS, TaskState
except Exception:
    class TaskState:
        Vice = "Vice"
        Strategy = "Strategy"
        AuditReview = "AuditReview"
        Assigned = "Assigned"
        Next = "Next"
        Doing = "Doing"
        Review = "Review"
        Done = "Done"
        Blocked = "Blocked"
        Cancelled = "Cancelled"
        Pending = "Pending"
        PendingConfirm = "PendingConfirm"

    STATE_TRANSITIONS = {
        TaskState.Pending: {TaskState.Vice, TaskState.Cancelled},
        TaskState.Vice: {TaskState.Strategy, TaskState.Cancelled},
        TaskState.Strategy: {TaskState.AuditReview, TaskState.Cancelled, TaskState.Blocked},
        TaskState.AuditReview: {TaskState.Assigned, TaskState.Strategy, TaskState.Cancelled},
        TaskState.Assigned: {TaskState.Doing, TaskState.Next, TaskState.Cancelled, TaskState.Blocked},
        TaskState.Next: {TaskState.Doing, TaskState.Cancelled, TaskState.Blocked},
        TaskState.Doing: {TaskState.Review, TaskState.Done, TaskState.Blocked, TaskState.Cancelled},
        TaskState.Review: {TaskState.Done, TaskState.AuditReview, TaskState.Doing, TaskState.Cancelled, TaskState.PendingConfirm},
        TaskState.PendingConfirm: {TaskState.Done, TaskState.Review, TaskState.Cancelled},
        TaskState.Blocked: {TaskState.Vice, TaskState.Strategy, TaskState.AuditReview, TaskState.Assigned, TaskState.Next, TaskState.Doing, TaskState.Review, TaskState.Cancelled},
    }

AGENT_POLICY = {
    "vice":     {"commands": {"create", "state", "flow", "progress", "todo", "memory", "task-memo"}},
    "strategy": {"commands": {"state", "flow", "progress", "todo", "memory", "task-memo", "delegate"}},
    "review":   {"commands": {"state", "flow", "progress", "todo", "confirm", "memory", "task-memo"}},
    "dispatch": {"commands": {"state", "flow", "progress", "todo", "confirm", "delegate", "memory", "task-memo", "shared-memo"}},
    "intel":    {"commands": {"progress", "todo", "memory"}},
    "finance":  {"commands": {"progress", "todo", "done", "block", "memory", "task-memo", "delegate-result"}},
    "scribe":   {"commands": {"progress", "todo", "done", "block", "memory", "task-memo", "delegate-result"}},
    "combat":   {"commands": {"progress", "todo", "done", "block", "memory", "task-memo", "delegate-result"}},
    "audit":    {"commands": {"progress", "todo", "done", "block", "memory", "task-memo", "delegate-result"}},
    "build":    {"commands": {"progress", "todo", "done", "block", "memory", "task-memo", "delegate-result"}},
    "hr":       {"commands": {"progress", "todo", "done", "block", "memory", "task-memo", "delegate-result"}},
}

HIGH_RISK_TRANSITIONS = {
    ("AuditReview", "Done"),
    ("Doing", "Cancelled"),
    ("AuditReview", "Cancelled"),
}

CONFIRM_AUTHORITY = {
    "AuditReview": "review",
    "Doing": "dispatch",
}

_JUNK_TITLES = {"?", "？", "好", "好的", "是", "否", "不", "不是", "对", "了解", "收到", "嗯", "哦", "知道了", "ok", "yes", "no", "测试", "试试", "看看"}
_MIN_TITLE_LEN = 6


class PolicyEngine:
    def check_transition(self, old_state: str, new_state: str) -> bool:
        if not STATE_TRANSITIONS:
            return True  # fallback: permissive
        # Build string-keyed map once lazily (handles both backend enum keys and fallback string keys)
        if not hasattr(self, "_str_transitions"):
            def _to_str(x):
                return x.value if hasattr(x, "value") else str(x)
            self._str_transitions = {
                _to_str(k): {_to_str(v) for v in vals}
                for k, vals in STATE_TRANSITIONS.items()
            }
        return new_state in self._str_transitions.get(old_state, set())

    def check_permission(self, agent_id: str, cmd: str) -> bool:
        policy = AGENT_POLICY.get(agent_id)
        if policy is None:
            return True  # unregistered agents are not blocked
        return cmd in policy["commands"]

    def is_high_risk(self, old_state: str, new_state: str) -> bool:
        return (old_state, new_state) in HIGH_RISK_TRANSITIONS

    def get_confirm_authority(self, old_state: str) -> Optional[str]:
        return CONFIRM_AUTHORITY.get(old_state)

    @staticmethod
    def sanitize_text(raw: str, max_len: int = 80) -> str:
        t = (raw or "").strip()
        t = re.split(r"\n*Conversation\b", t, maxsplit=1)[0].strip()
        t = re.split(r"\n*```", t, maxsplit=1)[0].strip()
        t = re.sub(r"[/\\.~][A-Za-z0-9_\-./]+(?:\.(?:py|js|ts|json|md|sh|yaml|yml|txt|csv|html|css|log))?", "", t)
        t = re.sub(r"https?://\S+", "", t)
        t = re.sub(r"\bhttps?[:：]?\s*$", "", t)
        t = re.sub(r"^(传达委托|发布委托)([（(][^)）]*[)）])?[：:：]\s*", "", t)
        t = re.sub(r"(message_id|session_id|chat_id|open_id|user_id|tenant_key)\s*[:=]\s*\S+", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > max_len:
            t = t[:max_len] + "…"
        return t

    def sanitize_title(self, raw: str) -> str:
        return self.sanitize_text(raw, 80)

    def sanitize_remark(self, raw: str) -> str:
        return self.sanitize_text(raw, 120)

    def validate_task_title(self, title: str) -> Tuple[bool, str]:
        t = (title or "").strip()
        if len(t) < _MIN_TITLE_LEN:
            return False, f"标题过短（{len(t)}<{_MIN_TITLE_LEN}字），疑似非委托"
        if t.lower() in _JUNK_TITLES:
            return False, f'标题 "{t}" 不是有效委托'
        if re.fullmatch(r"[\s?？!！.。,，…·\-—~]+", t):
            return False, "标题只有标点符号"
        if re.match(r"^[/\\~.]", t) or re.search(r"/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+", t):
            return False, "标题看起来像文件路径，请用中文概括任务"
        if re.fullmatch(r"[\s\W]*", t):
            return False, "标题清洗后为空"
        return True, ""
