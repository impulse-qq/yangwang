# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuestBoard (formerly Edict / 核心部各小队) is an AI multi-agent collaboration platform inspired by Tang Dynasty bureaucracy. It runs 12 specialized agents through the OpenClaw framework with strict institutional review gates (plan → review → dispatch → execute). The system includes a real-time dashboard and supports both a lightweight JSON-file runtime and a full Postgres+Redis event-driven backend.

**Language**: Python 3.9+ / TypeScript  
**Agent Runtime**: OpenClaw (external dependency, not in this repo)

---

## Development Commands

### Setup
```bash
./install.sh          # One-time setup: creates agent workspaces, symlinks, API keys
```

### Development
```bash
./start.sh            # Launch dashboard server + data refresh loop (port 7891)
python3 dashboard/server.py           # Start dashboard server only
bash scripts/run_loop.sh &            # Start data refresh loop only (requires OpenClaw)
```

### Production Service Management
```bash
./edict.sh start      # Start services with pidfiles/logs
./edict.sh stop       # Stop services
./edict.sh status     # Check service status
./edict.sh restart    # Restart services
```

### Testing
```bash
pytest tests/ -v                                          # Run all tests
pytest tests/test_e2e_kanban.py -v                        # Run E2E kanban tests
python3 tests/test_state_machine_consistency.py           # Validate state machine drift
python3 -m py_compile dashboard/server.py                 # Syntax check a single file
find scripts dashboard -name '*.py' | while read f; do python3 -m py_compile "$f"; done
```

### Frontend (React)
```bash
cd edict/frontend
npm install
npm run dev          # Vite dev server
npm run build        # Build to dashboard/dist/
```

### Docker
```bash
docker run -p 7891:7891 cft0808/sansheng-demo     # Demo image (pre-built)
docker compose up                                  # Local compose (edict/ subdir)
```

### Backend (edict/backend)
```bash
cd edict/backend
pip install -r requirements.txt
python -m alembic upgrade head                     # Run migrations
cd edict/backend && python -c "from app.main import app"   # Verify imports
```

### Kanban CLI
```bash
python3 scripts/kanban_update.py create <id> <title> <state> <dept> <owner>
python3 scripts/kanban_update.py state <id> <new_state> <reason>
python3 scripts/kanban_update.py flow <id> <from> <to> <note>
python3 scripts/kanban_update.py done <id> <output_path> <summary>
```

### Skill Management
```bash
python3 scripts/skill_manager.py add-remote --agent <agent> --name <skill> --source <url>
python3 scripts/skill_manager.py import-official-hub --agents strategy,review,dispatch
python3 scripts/skill_manager.py list-remote
```

---

## High-Level Architecture

### Dual Runtime Modes

The codebase supports **two independent runtime modes** that do NOT share data automatically:

1. **JSON File Mode (Legacy / Default)**
   - `dashboard/server.py` serves API + static files using **only Python stdlib** (`http.server`)
   - Task state stored in `data/tasks_source.json` and `data/tasks.json`
   - `scripts/kanban_update.py` is the CLI for this mode
   - `scripts/run_loop.sh` refreshes data every 15 seconds from OpenClaw runtime
   - No database or external dependencies required

2. **Postgres + Redis Backend Mode (Edict Backend)**
   - `edict/backend/app/main.py` is a FastAPI application
   - SQLAlchemy + asyncpg for persistence; Alembic for migrations
   - Redis Streams EventBus for inter-service messaging
   - Workers: `dispatch_worker.py`, `orchestrator_worker.py`, `outbox_relay.py`
   - Migration path: `edict/migration/migrate_json_to_pg.py`

**Important**: If both modes are running, they operate on separate data stores. Choose one mode and stick to it.

### Agent Architecture & Permission Matrix

12 agents form a strict governance hierarchy. Agents communicate via OpenClaw's subagent mechanism (local mode) or Redis Streams EventBus (backend mode). The permission matrix is enforced — not all agents can message all others.

| Agent | ID | Can Message |
|-------|-----|-------------|
| 副团长 | `vice` | `strategy` |
| 策划部 | `strategy` | `review`, `dispatch` |
| 监察部 | `review` | `strategy`, `dispatch` |
| 调度部 | `dispatch` | `strategy`, `review`, `finance`, `scribe`, `combat`, `audit`, `build`, `hr` |
| 各小队 | `finance`, `scribe`, `combat`, `audit`, `build`, `hr` | `dispatch` |
| 晨报官 | `intel` | (none) |

Agent configurations live in `agents/<id>/SOUL.md` (personality + workflow rules) and `agents.json` (runtime mapping).

### Task State Machine

Tasks follow a mandatory lifecycle with protected transitions. The canonical state machine is defined in `edict/backend/app/models/task.py` as `STATE_TRANSITIONS`.

```
Pending → Vice → Strategy → AuditReview → Assigned → (Next/Doing) → Review → Done
                ↑______________↵ (reject loop, max 3 rounds)
```

`scripts/kanban_update.py` dynamically parses `task.py` to load the same transition table (single source of truth). `tests/test_state_machine_consistency.py` parses source code to detect drift between the backend model and CLI tool.

Terminal states: `Done`, `Cancelled`.

### Dashboard Dual Architecture

The dashboard UI ships in two forms:
- **Embedded**: `dashboard/dashboard.html` — single self-contained HTML file (~2500 lines, zero dependencies, no build step)
- **React**: `edict/frontend/` — React 18 + Vite + Zustand + Tailwind, builds to `dashboard/dist/`

`server.py` serves `dashboard/dashboard.html` by default. If `dashboard/dist/` exists, it serves that instead. The Docker image includes the pre-built React bundle.

### EventBus & Outbox Relay (Backend Mode)

- **Redis Streams EventBus** (`edict/backend/app/services/event_bus.py`): publish/subscribe with consumer groups and ACKs. Topics include `task.created`, `task.planning.request`, `agent.thoughts`, `agent.todo.update`, etc.
- **Outbox Relay** (`edict/backend/app/workers/outbox_relay.py`): transactional outbox pattern ensures events are reliably delivered (at-least-once semantics).
- **Dispatch Worker** (`edict/backend/app/workers/dispatch_worker.py`): parallel execution with exponential backoff retry and resource locks.
- **Orchestrator Worker** (`edict/backend/app/workers/orchestrator_worker.py`): DAG-based task decomposition and dependency resolution.

### Data Flow (JSON Mode)

```
OpenClaw Runtime → session JSONL files
                        ↓
          scripts/sync_from_openclaw_runtime.py
                        ↓
              data/tasks_source.json
                        ↓
          scripts/refresh_live_data.py
                        ↓
              data/tasks.json (enriched for UI)
                        ↓
              dashboard/server.py (API)
                        ↓
              dashboard/dashboard.html
```

### Known Issues

- `scripts/agentrec_advisor.py` and `scripts/linucb_router.py` are **broken symlinks** (point to absolute paths under `/Users/bingsen/`). They are non-functional in this checkout.
- No `pyproject.toml` or formal Python packaging — root deps are in `requirements.txt` (mostly stdlib), backend deps in `edict/backend/requirements.txt`.

---

## File Organization

| Path | Purpose |
|------|---------|
| `dashboard/server.py` | Zero-dependency stdlib HTTP server + API (~2800 lines, high churn) |
| `dashboard/court_discuss.py` | Multi-agent LLM debate engine |
| `scripts/kanban_update.py` | Kanban CLI + state machine + data cleaning (~350 lines) |
| `scripts/skill_manager.py` | Remote skill add/update/remove |
| `edict/backend/app/models/task.py` | Canonical task state machine (SSOT) |
| `edict/backend/app/services/event_bus.py` | Redis Streams event bus |
| `edict/backend/app/workers/` | Async workers (dispatch, orchestrator, outbox relay) |
| `agents/<id>/SOUL.md` | Per-agent personality and workflow rules |
| `data/` | Runtime JSON files (gitignored) |

---

## Conventions

- **Python**: PEP 8, prefer `pathlib` over `os.path`.
- **TypeScript/React**: Function components + Hooks. CSS variables prefixed with `--`.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`).
- **Agent IDs**: Use English IDs (`vice`, `strategy`, `review`, `dispatch`, `finance`, `scribe`, `combat`, `audit`, `build`, `hr`, `intel`) in code, even though UI and docs use Chinese titles.
- **State changes**: Do NOT edit `data/*.json` directly — use `kanban_update.py` CLI or backend API.

---

## CI / Testing

GitHub Actions (`.github/workflows/ci.yml`) runs:
1. Shell script lint (`bash -n`)
2. Python syntax check (`py_compile`) for `scripts/`, `dashboard/`, `edict/backend/`
3. `pytest tests/ -v` on Python 3.10–3.13
4. Docker build verification
5. Backend verification: Alembic migrations + FastAPI import check against Postgres + Redis services

---

## External Dependencies

- **OpenClaw**: Required for agent runtime and data sync. Install separately from https://openclaw.ai
- **Node.js 18+**: Required only to build the React frontend (optional).
- **Postgres + Redis**: Required only for edict backend mode (optional).
