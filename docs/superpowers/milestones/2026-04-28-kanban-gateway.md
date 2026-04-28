# Milestone: Kanban Gateway v1.0

**Date:** 2026-04-28  
**Branch:** main  
**Commits:** 15  
**Status:** Complete

---

## Summary

Implemented the Kanban Gateway architecture — an authenticated HTTP control plane that replaces direct file mutations with a centralized API, while maintaining full backward compatibility with the existing `kanban_update.py` CLI.

**Key principle:** All task mutations now flow through `Agent → KanbanClient → KanbanGateway → tasks_source.json`, with unified validation (authz / state-machine / sanitization) and atomic file operations.

---

## What Was Built

### 1. Atomic Store Layer (`kanban_gateway/store.py`)

- `atomic_read` — shared-lock JSON read with graceful fallback to default
- `atomic_write` — temp-file + `os.replace` under exclusive `flock`
- `atomic_update` — read-modify-write under exclusive `flock` (eliminates TOCTOU races)
- Zero external dependencies; uses `fcntl.flock` directly on the data file (no separate `.lock` files)

### 2. HMAC Authentication (`kanban_gateway/auth.py`)

- `HMACVerifier` with 300-second time window and nonce deduplication via `collections.deque`
- Canonicalization: `json.dumps(..., sort_keys=True, ensure_ascii=False)`
- `load_agent_keys()` discovers `.kanban_key` files from `workspace-*/` directories
- 13 tests covering valid/expired/replay/missing-field/wrong-signature scenarios

### 3. Policy Engine (`kanban_gateway/policy.py`)

- State machine validation imported dynamically from `edict/backend/app/models/task.py` (SSOT), with inline fallback
- Agent permission matrix (`AGENT_POLICY`) enforcing command whitelists per agent
- Data sanitization: strips file paths, URLs, Conversation metadata, code blocks, system IDs
- Title validation: length check, junk-title filter, path-pattern detection
- High-risk transition detection (`HIGH_RISK_TRANSITIONS`) with `CONFIRM_AUTHORITY` metadata

### 4. Gateway HTTP Server (`kanban_gateway/gateway.py`)

- Single-threaded `HTTPServer` on `127.0.0.1:7892` (port configurable)
- Endpoints:
  - `POST /api/v1/kanban/create` — create task (unauthenticated, title validation)
  - `POST /api/v1/kanban/state` — state transition (authz + state-machine + high-risk intercept)
  - `POST /api/v1/kanban/flow` — flow log entry
  - `POST /api/v1/kanban/done` — mark done with state-machine check
  - `POST /api/v1/kanban/review-action` — approve/reject PendingConfirm
  - `POST /api/v1/kanban/progress`, `/todo` — stubs for future implementation
  - `GET /api/v1/kanban/task/<id>` — read task by ID
- Structured errors via `GatewayError` (message, code, HTTP status)
- Request body size limit: 1 MB → 413
- CORS headers for dashboard integration
- 11 end-to-end tests covering auth, permissions, transitions, concurrency, payload limits

### 5. KanbanClient (`kanban_client/client.py`)

- Zero-dependency stdlib client for agents
- Auto-discovers `agent_id` from env vars → cwd path pattern → "unknown"
- Auto-loads HMAC key from `~/.openclaw/workspace-{id}/.kanban_key`
- Auto-discovers gateway URL (Unix socket or `http://127.0.0.1:7892`)
- Exponential backoff retry: 3 attempts, distinguishes 4xx (fail-fast) from 5xx/network (retry)
- Secure nonce via `secrets.token_hex(8)`
- 3 tests: HMAC verification, 5xx retry, 4xx no-retry

### 6. Backward-Compatibility Wrapper (`scripts/kanban_update.py`)

- Refactored `if __name__ == "__main__"` into `main()` with gateway probe at top
- If `KanbanGateway` is available on `127.0.0.1:7892` (or `KANBAN_GATEWAY_URL`), CLI commands are routed through the gateway
- If gateway unavailable or call fails, falls back seamlessly to legacy direct-file operations
- Preserves all existing CLI behavior and argument parsing

### 7. Install Script Key Generation (`install.sh`)

- Generates 256-bit hex `.kanban_key` per agent during workspace creation
- Idempotent: skips if key already exists
- Prefers `openssl rand -hex 32`, falls back to Python `secrets.token_hex(32)`
- Sets `chmod 600` on key files

---

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Store | 8 | PASS |
| Auth | 13 | PASS |
| Policy | 10 | PASS |
| Gateway API | 11 | PASS |
| KanbanClient | 3 | PASS |
| **Total new** | **47** | **PASS** |

Full suite: 85 passed, 6 pre-existing failures unrelated to this milestone (`test_sync_symlinks.py` ×5, `test_e2e_kanban.py::test_state_update` ×1).

---

## Files Added / Modified

**New packages:**
- `kanban_gateway/__init__.py`
- `kanban_gateway/store.py`
- `kanban_gateway/auth.py`
- `kanban_gateway/policy.py`
- `kanban_gateway/gateway.py`
- `kanban_client/__init__.py`
- `kanban_client/client.py`

**New tests:**
- `tests/test_kanban_gateway_store.py`
- `tests/test_kanban_gateway_auth.py`
- `tests/test_kanban_gateway_policy.py`
- `tests/test_kanban_gateway_api.py`
- `tests/test_kanban_client.py`

**Modified:**
- `scripts/kanban_update.py` — gateway fallback wrapper
- `install.sh` — `.kanban_key` generation
- `pytest.ini` — `pytest-order` plugin config

**Documentation:**
- `docs/superpowers/plans/2026-04-28-kanban-gateway.md`
- `docs/superpowers/specs/2026-04-28-kanban-gateway-design.md`
- `docs/superpowers/milestones/2026-04-28-kanban-gateway.md` (this file)

---

## Architecture Impact

```
Before:  Agent → kanban_update.py → direct file write → tasks_source.json
After:   Agent → KanbanClient → KanbanGateway → atomic_update → tasks_source.json
                      ↓ (fallback if gateway unavailable)
                kanban_update.py → direct file write → tasks_source.json
```

The existing `dashboard/server.py` remains read-only; the gateway is the sole mutation path when running. Both modes (gateway-first and legacy-fallback) coexist safely.

---

## Known Limitations / Follow-up

1. **Scheduler deferred** — Event-driven dispatch, stalled-task detection with lazy heap, retry/escalate/rollback is not yet implemented. Planned as Task 9 in a follow-up milestone.
2. **Unix socket transport** — `KanbanClient._discover_gateway()` returns `http+unix://` scheme, but `urllib.request` does not natively support Unix sockets. A custom opener would be needed to make this functional.
3. **`kanban_update.py` `create` command** — Not yet exposed via `KanbanClient`; always falls through to legacy path. Can be added once the gateway `create` endpoint accepts authenticated requests.
4. **High-risk transition set** — Currently only covers `(AuditReview, Done)`, `(Doing, Cancelled)`, `(AuditReview, Cancelled)`. Expand as operational needs evolve.

---

## Deployment Notes

1. Run `./install.sh` (or re-run) to generate `.kanban_key` files for all agents
2. Start gateway: `python3 -c "from kanban_gateway.gateway import KanbanGateway; KanbanGateway('./data').serve_forever()"`
3. Existing `kanban_update.py` CLI calls will automatically use the gateway when it's available
4. Set `KANBAN_GATEWAY_URL` env var if gateway runs on a non-default host/port
