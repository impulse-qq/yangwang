"""Task 模型 — 核心部各小队任务核心表。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


class TaskState(str, enum.Enum):
    """任务状态枚举 — 映射核心部各小队流程。"""

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


TERMINAL_STATES = {TaskState.Done, TaskState.Cancelled}

STATE_TRANSITIONS = {
    TaskState.Pending: {TaskState.Vice, TaskState.Cancelled},
    TaskState.Vice: {TaskState.Strategy, TaskState.Cancelled},
    TaskState.Strategy: {TaskState.AuditReview, TaskState.Cancelled, TaskState.Blocked},
    TaskState.AuditReview: {
        TaskState.Assigned,
        TaskState.Strategy,
        TaskState.Cancelled,
    },
    TaskState.Assigned: {
        TaskState.Doing,
        TaskState.Next,
        TaskState.Cancelled,
        TaskState.Blocked,
    },
    TaskState.Next: {TaskState.Doing, TaskState.Cancelled, TaskState.Blocked},
    TaskState.Doing: {
        TaskState.Review,
        TaskState.Done,
        TaskState.Blocked,
        TaskState.Cancelled,
    },
    TaskState.Review: {
        TaskState.Done,
        TaskState.AuditReview,
        TaskState.Doing,
        TaskState.Cancelled,
        TaskState.PendingConfirm,
    },
    TaskState.PendingConfirm: {TaskState.Done, TaskState.Review, TaskState.Cancelled},
    TaskState.Blocked: {
        TaskState.Vice,
        TaskState.Strategy,
        TaskState.AuditReview,
        TaskState.Assigned,
        TaskState.Next,
        TaskState.Doing,
        TaskState.Review,
        TaskState.Cancelled,
    },
}

STATE_AGENT_MAP = {
    TaskState.Vice: "vice",
    TaskState.Strategy: "strategy",
    TaskState.AuditReview: "review",
    TaskState.Assigned: "dispatch",
    TaskState.Review: "dispatch",
    TaskState.PendingConfirm: "dispatch",
    TaskState.Pending: "strategy",
}

ORG_AGENT_MAP = {
    "财务小队": "finance",
    "书记小队": "scribe",
    "战斗小队": "combat",
    "审判小队": "audit",
    "建设小队": "build",
    "人事小队": "hr",
}

STATE_ORG_MAP = {
    TaskState.Vice: "副团长",
    TaskState.Strategy: "策划部",
    TaskState.AuditReview: "监察部",
    TaskState.Assigned: "调度部",
    TaskState.Review: "调度部",
    TaskState.PendingConfirm: "调度部",
    TaskState.Pending: "策划部",
}


class Task(Base):
    """核心部各小队任务表。"""

    __tablename__ = "tasks"

    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(
        String(64),
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="追踪链路 ID",
    )
    title = Column(String(200), nullable=False, comment="任务标题")
    description = Column(Text, default="", comment="任务描述")
    priority = Column(String(10), default="中", comment="优先级")
    state = Column(
        Enum(TaskState, name="task_state", native_enum=False, validate_strings=True),
        nullable=False,
        default=TaskState.Vice,
        comment="任务状态",
    )
    assignee_org = Column(String(50), nullable=True, comment="目标执行部门")
    creator = Column(String(50), default="master", comment="创建者")
    tags = Column(JSONB, default=list, comment="标签")
    meta = Column(JSONB, default=dict, comment="扩展元数据")

    # 兼容旧看板字段，避免新后端与现有前端/迁移数据脱节
    org = Column(String(32), nullable=False, default="副团长", comment="当前执行部门")
    official = Column(String(32), default="", comment="责任官员")
    now = Column(Text, default="", comment="当前进展描述")
    eta = Column(String(64), default="-", comment="预计完成时间")
    block = Column(Text, default="无", comment="阻塞原因")
    output = Column(Text, default="", comment="最终产出")
    archived = Column(Boolean, default=False, comment="是否归档")

    flow_log = Column(JSONB, default=list, comment="流转日志 [{at, from, to, remark}]")
    progress_log = Column(
        JSONB, default=list, comment="进展日志 [{at, agent, text, todos}]"
    )
    todos = Column(JSONB, default=list, comment="子任务 [{id, title, status, detail}]")
    scheduler = Column(JSONB, default=dict, comment="调度器元数据")
    template_id = Column(String(64), default="", comment="模板ID")
    template_params = Column(JSONB, default=dict, comment="模板参数")
    ac = Column(Text, default="", comment="验收标准")
    target_dept = Column(String(64), default="", comment="目标部门")

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tasks_trace_id", "trace_id"),
        Index("ix_tasks_assignee_org", "assignee_org"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_state", "state"),
        Index("ix_tasks_state_archived", "state", "archived"),
        Index("ix_tasks_updated_at", "updated_at"),
    )

    @staticmethod
    def org_for_state(state: TaskState, assignee_org: str | None = None) -> str:
        if state in {TaskState.Doing, TaskState.Next}:
            return assignee_org or "各小队"
        return STATE_ORG_MAP.get(state, assignee_org or "副团长")

    def to_dict(self) -> dict[str, Any]:
        """序列化为 API 响应格式，并兼容旧 live_status 字段。"""

        state_value = (
            self.state.value
            if isinstance(self.state, TaskState)
            else str(self.state or "")
        )
        meta = self.meta or {}
        scheduler = self.scheduler or {}
        task_id = str(self.task_id) if self.task_id else ""
        updated_at = self.updated_at.isoformat() if self.updated_at else ""
        legacy_output = (
            self.output or meta.get("output") or meta.get("legacy_output", "")
        )

        return {
            "task_id": task_id,
            "trace_id": self.trace_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "state": state_value,
            "assignee_org": self.assignee_org,
            "creator": self.creator,
            "tags": self.tags or [],
            "meta": meta,
            "flow_log": self.flow_log or [],
            "progress_log": self.progress_log or [],
            "todos": self.todos or [],
            "scheduler": scheduler,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": updated_at,
            # 旧前端兼容字段
            "id": task_id,
            "org": self.org or self.org_for_state(self.state, self.assignee_org),
            "official": self.official or self.creator,
            "now": self.now or self.description,
            "eta": self.eta if self.eta != "-" else updated_at,
            "block": self.block,
            "output": legacy_output,
            "archived": self.archived,
            "templateId": self.template_id,
            "templateParams": self.template_params or {},
            "ac": self.ac,
            "targetDept": self.target_dept,
            "_scheduler": scheduler,
            "createdAt": self.created_at.isoformat() if self.created_at else "",
            "updatedAt": updated_at,
        }
