# SCRIPTS · Edict

CLI tools and workflow orchestration for 三省六部 system.

---

## OVERVIEW

Scripts power data synchronization, task dispatch, skill management, and dashboard refresh. `run_loop.sh` drives 15-second data refresh cycle; `kanban_update.py` enforces state machine transitions.

---

## KEY SCRIPTS

| Script | Purpose |
|--------|---------|
| `kanban_update.py` | Kanban CLI — state transitions, data cleaning, validation |
| `skill_manager.py` | Remote skill CRUD — add/update/remove/list skills |
| `run_loop.sh` | Data refresh loop — 15-second sync cycle |
| `sync_officials_stats.py` | Agent statistics aggregation |
| `fetch_morning_news.py` | News aggregation pipeline |
| `apply_model_changes.py` | Hot-switch LLM models |
| `refresh_live_data.py` | Dashboard data refresh |

---

## CONVENTIONS

- File naming: `snake_case.py`, `snake_case.sh`
- Symlinks allowed for workspace-relative paths
- Stdlib only — no external dependencies in scripts

---

## KNOWN ISSUES

| File | Status |
|------|--------|
| `agentrec_advisor.py` | BROKEN SYMLINK → `/Users/bingsen/...` |
| `linucb_router.py` | BROKEN SYMLINK → `/Users/bingsen/...` |
