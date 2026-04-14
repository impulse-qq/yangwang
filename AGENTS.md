# PROJECT KNOWLEDGE BASE: 核心部各小队 · Edict

**Generated:** 2026-04-11  
**Commit:** 70cd997  
**Branch:** main  
**Language:** Python 3.9+ / TypeScript  
**Stack:** OpenClaw Multi-Agent Framework

---

## OVERVIEW

AI multi-agent collaboration architecture inspired by Tang Dynasty's "Three Departments & Six Ministries" system. 12 specialized agents (11 roles + 1 compatibility) form a governance hierarchy with institutional review gates.

**Key Differentiator:** True separation of powers — planning (中书), review (门下), execution (各小队) are distinct with explicit approval chains. Not metaphor — actual workflow enforcement.

---

## STRUCTURE

```
yangwang/
├── dashboard/           # Real-time dashboard (Python stdlib, zero deps)
│   ├── server.py        # ~2800 lines, serves API + static files
│   ├── dashboard.html   # Embedded UI (~2500 lines, zero deps)
│   └── court_discuss.py # Multi-agent LLM debate engine
├── edict/
│   ├── frontend/        # React 18 + Vite + Zustand + Tailwind
│   └── backend/         # Async services (SQLAlchemy + Redis Streams)
├── agents/              # 12 Agent SOUL.md files (personality templates)
│   ├── vice/           # Crown Prince — message routing
│   ├── strategy/        # Chancellery — planning
│   ├── review/          # Secretariat — review/rejection
│   ├── dispatch/        # Secretariat — dispatch
│   ├── finance/            # Revenue — data
│   ├── scribe/            # Rites — documentation
│   ├── combat/          # War — code
│   ├── audit/          # Justice — security/compliance
│   ├── build/          # Works — infrastructure
│   ├── hr/         # Personnel — agent management
│   └── intel/         # Morning Court Official — news aggregation
├── scripts/             # CLI tools & workflow orchestration
│   ├── kanban_update.py    # Kanban state machine + data cleaning
│   ├── skill_manager.py    # Remote skill management
│   ├── agentrec_advisor.py # Model recommendation + cost optimization
│   └── linucb_router.py    # LinUCB intelligent routing
├── tests/               # pytest-based test suite
├── docs/                # Architecture docs + screenshots
└── data/                # Runtime data (gitignored)
```

---

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| **Start services** | `./start.sh` or `./edict.sh start` | One-click startup (server + data loop) |
| **Dashboard** | `dashboard/server.py` port 7891 | Zero-dependency Python stdlib HTTP server |
| **Agent configs** | `agents/*/SOUL.md` | Personality + workflow rules per agent |
| **Frontend** | `edict/frontend/` | React 18 + Vite + Zustand |
| **Backend services** | `edict/backend/app/` | Async workers, EventBus, Outbox Relay |
| **Kanban state machine** | `scripts/kanban_update.py` | State transitions validated, illegal jumps rejected |
| **Tests** | `tests/` | pytest; run with `pytest tests/ -v` |
| **Install** | `./install.sh` | Sets up workspaces, symlinks, API keys |

---

## CODE MAP

### Key Symbols

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `server.py` | Module | `dashboard/` | Main API server (~2800 lines) |
| `kanban_update.py` | Module | `scripts/` | CLI + state machine |
| `event_bus.py` | Service | `edict/backend/app/services/` | Redis Streams EventBus |
| `task.py` | Model | `edict/backend/app/models/` | Task state machine |
| `dispatch_worker.py` | Worker | `edict/backend/app/workers/` | Parallel dispatch + retry |

---

## CONVENTIONS

### File Naming
- Test files: `test_*.py`
- Agent configs: `SOUL.md` (per agent directory)
- Scripts: Descriptive names with underscores (`kanban_update.py`)

### State Machine
```
团长 → 副团长分拣 → 中书规划 → 监察审核 → 已派遣 → 执行中 → 待审查 → ✅ 已完成
              ↑          │                              │
              └──── 驳回 ─┘                    阻塞 Blocked
```
- **State transitions protected**: `kanban_update.py` validates `_VALID_TRANSITIONS`
- **Illegal jumps rejected**: e.g., Doing→Vice blocked with error log

### Agent Communication
- Permission matrix enforced — not all agents can message all others
- Messages routed through Redis Streams (EventBus)
- Session visibility set to `all` for cross-agent communication

---

## ANTI-PATTERNS (THIS PROJECT)

1. **Never skip 监察部 (review) review** — mandatory quality gate, no exceptions
2. **No agent-to-agent direct messaging** — must go through 调度部 coordination
3. **State machine violations rejected** — illegal transitions throw errors
4. **Don't edit data/*.json directly** — use `kanban_update.py` CLI
5. **No `requirements.txt` in subdirs** (except `edict/backend/`) — root deps only

---

## UNIQUE STYLES

### Zero-Dependency Philosophy
- `dashboard/server.py` uses only Python stdlib (`http.server`)
- `dashboard/dashboard.html` embedded UI, no build step required

### Dual Dashboard Architecture
- **Embedded**: `dashboard/dashboard.html` (single file, ~2500 lines)
- **React**: `edict/frontend/` built to `dashboard/dist/` (optional)

### Domain-Driven Naming
- File/function names use Chinese bureaucratic terms (任务, 战报, 委托)
- Agent IDs: `vice`, `strategy`, `review`, `dispatch`, `finance`, etc.

---

## COMMANDS

```bash
# Install & setup
./install.sh

# Start services (development)
./start.sh                    # Launches server.py + run_loop.sh

# Production (systemd)
sudo cp edict.service /etc/systemd/system/
sudo systemctl enable --now edict

# Docker
docker run -p 7891:7891 cft0808/sansheng-demo

# Tests
pytest tests/ -v

# Kanban CLI
python3 scripts/kanban_update.py --help

# Skill management
python3 scripts/skill_manager.py add-remote --agent strategy --name code_review --source <url>
```

---

## NOTES

- **OpenClaw Required**: This project runs on OpenClaw multi-agent platform
- **Broken symlinks**: `scripts/agentrec_advisor.py` and `linucb_router.py` are broken (absolute paths to `/Users/bingsen/`)
- **Python version**: 3.9+ required; CI tests 3.10-3.13
- **No formal Python packaging**: Uses `requirements.txt` directly, no `pyproject.toml`
- **Frontend optional**: React build outputs to `dashboard/dist/`; embedded HTML is default
- **State machine drift detection**: `tests/test_state_machine_consistency.py` parses source code to catch inconsistencies

---

## AGENT ARCHITECTURE QUICK REF

| Agent | Role | Can Send To |
|-------|------|-------------|
| vice | Crown Prince (routing) | strategy |
| strategy | Chancellery (planning) | vice, review, dispatch |
| review | Secretariat (review) | strategy, dispatch |
| dispatch | Secretariat (dispatch) | strategy, review, 各小队 |
| finance | Revenue (data) | dispatch |
| scribe | Rites (docs) | dispatch |
| combat | War (code) | dispatch |
| audit | Justice (security) | dispatch |
| build | Works (infra) | dispatch |
| hr | Personnel (HR) | dispatch |
| intel | Morning Court (news) | — |

See `docs/task-dispatch-architecture.md` for full 9500+ word architecture deep-dive.
