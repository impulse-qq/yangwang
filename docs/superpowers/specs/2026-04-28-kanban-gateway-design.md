# QuestBoard 看板网关化设计文档

**日期**: 2026-04-28  
**主题**: 将现有 JSON 文件模式的看板系统升级为网关控制架构  
**状态**: 待实现  

---

## 1. 背景与问题

当前看板系统采用"Agent → CLI → 文件"的直接通路模式，存在以下结构性缺陷：

- **数据防篡改薄弱**: Agent 进程可直接读写 `tasks_source.json`，绕过所有校验逻辑
- **身份识别不可靠**: `kanban_update.py` 通过环境变量和路径推断 Agent ID，容易被伪造或误判
- **校验在客户端**: 状态机、权限、数据清洗全部在 CLI 端执行，`server.py` 无二次校验
- **调度滞后**: `handle_scheduler_scan()` 每 15 秒全量轮询，Agent 卡死需等待扫描周期才被发现
- **竞态与重复刷新**: `kanban_update.py` 每次操作 fork 子进程刷新，多 Agent 并发时产生大量僵尸进程
- **已知 Bug**: `CONFIRM_AUTHORITY` 字典存在键冲突（`"Review"` 出现两次）

## 2. 设计目标

1. **数据主权回收**: 网关独占 `tasks_source.json` 写入权，Agent 不再直接触碰文件
2. **服务端统一校验**: 身份认证、权限、状态机、数据清洗全部在网关内完成
3. **即时调度响应**: 状态变更事件即时触发调度器，告别轮询盲区
4. **向后兼容**: 现有 `kanban_update.py` 命令在迁移期内继续可用
5. **零外部依赖**: 保持 Python 标准库即可运行，不引入 Postgres/Redis 等依赖

## 3. 总体架构

### 3.1 架构演进

**改造前（当前）**:
```
Agent 进程 ──→ kanban_update.py ──→ tasks_source.json
                                      ↑
DashboardServer ←── run_loop.sh ──────┘ (15秒轮询刷新)
```

**改造后（目标）**:
```
Agent 进程 ──→ KanbanClient ──→ KanbanGateway ──→ tasks_source.json
                                     │
                                     ├──→ Audit Logger (append-only)
                                     ├──→ Scheduler (即时派发/纠偏)
                                     └──→ Refresh Handler (debounced)
                                              │
DashboardServer ←── live_status.json ────────┘
```

### 3.2 组件职责

| 组件 | 职责 | 部署形态 |
|------|------|---------|
| **KanbanGateway** | 接收 Agent 请求，统一完成认证/授权/校验/写入/审计/调度 | 单进程，单线程事件循环 |
| **KanbanClient** | 轻量级客户端（~100行），负责签名、发现网关、重试 | 部署在每个 Agent workspace |
| **DashboardServer** | 现有 `server.py`，职责缩减为只读服务（静态资源 + API） | 与网关同进程（开发）或独立进程（生产） |
| **Policy Engine** | 状态机校验、权限检查、数据清洗规则 | 内嵌在网关内 |
| **Scheduler** | 状态变更即时派发 Agent，停滞检测与自动纠偏 | 内嵌在网关内 |

### 3.3 开发环境部署

单进程双线程，对外仍然只暴露 `7891` 端口：
- **Thread-1**: DashboardServer（HTTP，对外）
- **Thread-2**: KanbanGateway（Unix Socket `/tmp/kanban.sock`，对内）

两者通过内存 Queue 共享任务缓存。

### 3.4 生产环境部署

- **KanbanGateway** 作为 systemd 服务独占运行，拥有 `tasks_source.json` 写权限
- **DashboardServer** 可水平扩展多个只读实例，通过读取 `live_status.json` 服务前端

## 4. 网关 API 设计

### 4.1 端点

所有端点接受 JSON，返回 JSON。

```
POST /api/v1/kanban/create
  body: {taskId, title, state, org, official, remark?, targetDept?}
  → {ok, taskId} | {ok: false, error, code}

POST /api/v1/kanban/state
  body: {taskId, newState, nowText?, agentId, ts, nonce, hmac}
  → {ok, taskId, oldState, newState} | {ok: false, error, code}

POST /api/v1/kanban/flow
  body: {taskId, fromDept, toDept, remark, agentId, ts, nonce, hmac}
  → {ok}

POST /api/v1/kanban/progress
  body: {taskId, summary, plan, agentId, ts, nonce, hmac}
  → {ok}

POST /api/v1/kanban/todo
  body: {taskId, todoId, title, status, detail?, agentId, ts, nonce, hmac}
  → {ok}

POST /api/v1/kanban/done
  body: {taskId, outputPath, summary, agentId, ts, nonce, hmac}
  → {ok}

POST /api/v1/kanban/review-action
  body: {taskId, action: "approve"|"reject", comment, agentId, ts, nonce, hmac}
  → {ok}

GET  /api/v1/kanban/task/{taskId}
  → {task}  # 只读查询，无需签名
```

### 4.2 错误码

| code | 含义 | HTTP 状态码 |
|------|------|------------|
| `UNAUTHORIZED` | HMAC 签名无效或 agentId 未注册 | 401 |
| `FORBIDDEN` | Agent 无权执行此命令（越权） | 403 |
| `INVALID_TRANSITION` | 状态转换非法 | 409 |
| `HIGH_RISK_PENDING` | 已转入 PendingConfirm，等待确认 | 202 |
| `TASK_NOT_FOUND` | 任务不存在 | 404 |
| `INVALID_TITLE` | 标题未通过清洗/校验 | 400 |
| `REQUEST_EXPIRED` | ts 超出 300 秒窗口 | 400 |
| `REPLAY_DETECTED` | nonce 已使用 | 400 |

## 5. 身份认证

### 5.1 HMAC 请求签名

每个 Agent 在 `install.sh` 初始化时生成一个 256-bit 随机密钥，写入 `~/.openclaw/workspace-<agent>/.kanban_key`。网关持有所有密钥的映射表。

请求体格式：
```json
{
  "taskId": "JJC-20260428-001",
  "newState": "AuditReview",
  "agentId": "strategy",
  "ts": 1714291200,
  "nonce": "a3f9e2b1...",
  "hmac": "sha256=abc123..."
}
```

`hmac` 计算方式：
```
hmac = HMAC_SHA256(key, canonical_json(body_without_hmac))
```

### 5.2 验证流程

1. **时间窗口**: `|now - ts| <= 300` 秒（5 分钟），覆盖系统休眠恢复和队列积压
2. **Nonce 唯一性**: `nonce` 在 300 秒滑动窗口内未出现过（内存 `set` + TTL 清理）
3. **HMAC 匹配**: 用该 agent 的密钥重新计算，与请求中的 `hmac` 比对

### 5.3 为什么选择 HMAC 而非 JWT

- 无状态：不需要 token 颁发、刷新、撤销机制
- 无令牌泄露风险：每个请求独立签名，截获后无法重放（nonce + ts 双重保护）
- 适合本地进程间通信：不需要 CA 证书或 OAuth 服务器

## 6. Agent 客户端（KanbanClient）

### 6.1 职责

- 自动发现网关地址（先查 Unix Socket `/tmp/kanban.sock`，fallback 到 `localhost:7892`）
- 自动推断 `agentId`（从 `OPENCLAW_AGENT_ID` 环境变量或 workspace 路径）
- 读取 `.kanban_key` 并附加 HMAC 签名
- 失败自动重试（指数退避，最多 3 次）
- 返回结构化结果，方便 Agent 脚本判断下一步

### 6.2 CLI 接口

```bash
# 兼容旧命令风格
python3 -m kanban_client state JJC-xxx AuditReview "方案提交审核"
python3 -m kanban_client flow JJC-xxx "策划部" "监察部" "方案提交审核"
python3 -m kanban_client progress JJC-xxx "正在分析..." "步骤1✅|步骤2🔄"
```

### 6.3 SOUL.md 改造示例

**改造前**:
```bash
python3 scripts/kanban_update.py state JJC-xxx Strategy "策划部已接令"
```

**改造后**:
```bash
python3 -m kanban_client state JJC-xxx Strategy "策划部已接令"
```

参数和语义完全一致，仅替换命令入口。

## 7. 网关内部数据流

### 7.1 请求处理管道

```
HTTP Request
    │
    ▼
┌─────────────┐
│  1. Parse   │  ← 解析 JSON，提取 agentId / taskId / hmac
└──────┬──────┘
       ▼
┌─────────────┐
│  2. Verify  │  ← HMAC + ts（300s）+ nonce 唯一性
└──────┬──────┘
       ▼
┌─────────────┐
│  3. Resolve │  ← 推断真实 agentId
└──────┬──────┘
       ▼
┌─────────────┐
│  4. Authz   │  ← 查 AGENT_POLICY 白名单
└──────┬──────┘
       ▼
┌─────────────┐
│  5. Validate│  ← 状态机 + 数据清洗 + 高风险检测
└──────┬──────┘
       ▼
┌─────────────┐
│  6. Mutate  │  ← atomic_json_update 写入 tasks_source.json
└──────┬──────┘
       ▼
┌─────────────┐
│  7. Audit   │  ← 追加 audit_log.json
└──────┬──────┘
       ▼
┌─────────────┐
│  8. Notify  │  ← 触发 Scheduler + Refresh（异步，不阻塞响应）
└──────┬──────┘
       ▼
   HTTP Response
```

**关键原则**: 前 5 步全部是只读检查，第 6 步是唯一的写入点。任何前置失败都不会留下脏数据。

### 7.2 状态机校验

网关直接 import `edict/backend/app/models/task.py` 中的 `STATE_TRANSITIONS`，不再使用 `exec()` 解析源码的 trick：

```python
from edict.backend.app.models.task import STATE_TRANSITIONS, TaskState

class PolicyEngine:
    def check_transition(self, old_state: str, new_state: str) -> bool:
        allowed = STATE_TRANSITIONS.get(TaskState(old_state), set())
        return TaskState(new_state) in allowed
```

### 7.3 高风险操作与 PendingConfirm

延续现有 `HIGH_RISK_TRANSITIONS` 机制，修复 `CONFIRM_AUTHORITY` 键冲突：

```python
HIGH_RISK_TRANSITIONS = {
    ("AuditReview", "Done"),
    ("Doing", "Cancelled"),
    ("AuditReview", "Cancelled"),
}

CONFIRM_AUTHORITY = {
    "AuditReview": "review",   # 完结或取消前需监察部确认
    "Doing": "dispatch",       # 执行中取消需调度部确认
}
```

当检测到高风险转换时，任务状态被设为 `PendingConfirm`，并记录 `pending_confirm` 元数据，必须由 `CONFIRM_AUTHORITY` 指定的 Agent 确认后才生效。

### 7.4 并发模型

网关使用**单线程事件循环**处理所有请求。`atomic_json_update` 本身就是原子操作，无需额外互斥锁。

未来如果请求量增大，可将文件存储替换为 SQLite（Python 内置 `sqlite3` 模块），获得行级锁和事务能力，而 Agent 客户端完全无感知。

## 8. 调度器集成 — 事件驱动

### 8.1 核心变化

从"每 15 秒全量轮询"改为"事件即时响应 + 惰性超时兜底"。

### 8.2 事件触发路径

每次 `tasks_source.json` 写入完成后，网关调用 `_on_task_mutated()`：

```python
def _on_task_mutated(task_id: str, old_task: dict, new_task: dict):
    sched = _ensure_scheduler(new_task)

    # 1. 状态推进 → 重置停滞计时器，触发自动派发
    if new_task['state'] != old_task.get('state'):
        sched['lastProgressAt'] = now_iso()
        sched['stallSince'] = None
        sched['retryCount'] = 0
        sched['escalationLevel'] = 0
        dispatch_for_state(task_id, new_task, new_task['state'])
        return

    # 2. 非状态更新（progress/flow）→ 也重置计时器
    if new_task.get('updatedAt') != old_task.get('updatedAt'):
        sched['lastProgressAt'] = now_iso()
        return

    # 3. 静默检测：为活跃任务注册超时检查
    _schedule_check(task_id, threshold_sec)
```

### 8.3 惰性超时检测

使用最小堆（`heapq`）只关注最接近超时的任务，而非全量扫描：

```python
import heapq

_check_heap = []  # [(next_check_at, task_id), ...]

def _schedule_check(task_id: str, delay_sec: int):
    deadline = time.time() + delay_sec
    heapq.heappush(_check_heap, (deadline, task_id))

def _checker_loop():
    while True:
        if not _check_heap:
            time.sleep(1)
            continue
        deadline, task_id = _check_heap[0]
        now = time.time()
        if now < deadline:
            time.sleep(min(1, deadline - now))
            continue
        heapq.heappop(_check_heap)
        _check_stalled(task_id)  # 只检查这一个任务
```

**复杂度**: O(log n) 的堆操作 + 只检查超时任务。

### 8.4 停滞纠偏四级策略

当 `_check_stalled()` 发现任务超时时：

| 阶段 | 条件 | 动作 |
|------|------|------|
| **自动重试** | retry_count < max_retry | 重新派发当前 Agent |
| **升级协调** | 重试无效，level < 2 | 唤醒监察部/调度部介入 |
| **自动回滚** | 升级无效，有快照 | 回滚到上一个稳定状态 |
| **自动挂起** | 回滚 3 次仍失败 | 标记 `Blocked`，等待人工介入 |

### 8.5 全量扫描兜底

惰性堆覆盖 90% 场景，但防止事件丢失或堆腐败，每 **5 分钟**执行一次全量扫描：

```python
_FULL_SCAN_INTERVAL = 300  # 5 分钟
```

### 8.6 Refresh Debounce

网关内部维护 `_refresh_pending` 标志 + 2 秒 debounce 计时器：

```python
_refresh_pending = False
_refresh_timer = None

def _trigger_refresh():
    global _refresh_pending, _refresh_timer
    _refresh_pending = True
    if _refresh_timer:
        _refresh_timer.cancel()
    _refresh_timer = threading.Timer(2.0, _do_refresh)
    _refresh_timer.start()
```

多次密集操作（progress + flow + state）只会在最后一次操作后 2 秒触发一次 `refresh_live_data.py`。

## 9. 部署与迁移路径

### 9.1 阶段一：共存期（向后兼容）

- `kanban_update.py` 改造为**兼容层客户端**：内部调用网关 API，参数不变
- 如果网关未启动，fallback 到直接写文件，打印 deprecation warning
- SOUL.md 暂时不改，Agent 仍然执行同样的命令

### 9.2 阶段二：切换期

- 发布 `kanban_client` 模块（~100 行，纯标准库）
- `install.sh` 自动把客户端部署到每个 Agent workspace
- 更新 SOUL.md 示例：`scripts/kanban_update.py` → `python3 -m kanban_client`

### 9.3 阶段三：废弃期

- `tasks_source.json` 文件权限改为 `600`，只有网关进程可写
- 删除 `kanban_update.py` 的 `_legacy_direct_write` fallback
- 删除 `run_loop.sh`（调度器和刷新已内嵌到网关）

## 10. 与 edict/backend 的衔接

网关 API 的接口契约兼容将来迁移到后端模式：

| 当前组件 | 未来替换 | Agent 客户端是否感知 |
|---------|---------|-------------------|
| 文件存储 (`tasks_source.json`) | Postgres | 无感知 |
| 内存 EventBus (`Queue`) | Redis Streams | 无感知 |
| `dispatch_for_state()` 的 subprocess | 向后端发事件 | 无感知 |
| HMAC 认证 | JWT / API Key | 需要小幅改造 |

即：Agent 客户端的命令和参数保持不变，只有网关内部实现替换。

## 11. 错误处理与可观测性

### 11.1 日志分级

| 级别 | 场景 |
|------|------|
| `INFO` | 正常状态变更、派发成功、刷新完成 |
| `WARNING` | 非法状态转换被拒、HMAC 验证失败、网关未启动 fallback |
| `ERROR` | 文件写入失败、自动派发最终失败、调度器异常 |

### 11.2 健康检查

DashboardServer 的 `/healthz` 端点增加网关连通性检查：
```json
{
  "status": "ok",
  "checks": {
    "dataDir": true,
    "tasksReadable": true,
    "dataWritable": true,
    "gatewayReachable": true
  }
}
```

### 11.3 降级策略

- 网关崩溃 → DashboardServer 继续提供只读服务，Agent 操作失败（需人工重启网关）
- Agent 客户端连不上网关 → 返回明确错误码，Agent 可重试或上报

---

## 附录：关键参数汇总

| 参数 | 值 | 说明 |
|------|-----|------|
| `HMAC_TIME_WINDOW` | 300 秒 | 请求签名有效期 |
| `NONCE_TTL` | 300 秒 | nonce 去重窗口 |
| `REFRESH_DEBOUNCE` | 2 秒 | 刷新去抖动时间 |
| `FULL_SCAN_INTERVAL` | 300 秒 | 兜底全量扫描周期 |
| `MAX_RETRY` | 1-3 次 | 自动重试次数（可调） |
| `MAX_ROLLBACK` | 3 次 | 最大自动回滚次数 |
| `STALL_THRESHOLD` | 600 秒 | 默认停滞阈值 |
| `AGENT_DISPATCH_TIMEOUT` | 300 秒 | openclaw agent 调用超时 |
| `AGENT_DISPATCH_MAX_RETRIES` | 2 次 | 派发重试次数 |
