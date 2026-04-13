# EDICT BACKEND · 尚书省

## OVERVIEW

Async services layer for task orchestration via SQLAlchemy + Redis Streams. Implements EventBus pub/sub and Outbox pattern for reliable cross-service messaging.

## KEY MODULES

### Models (`app/models/`)
| File | Role |
|------|------|
| `task.py` | State machine: 皇上→太子分拣→中书规划→...→已完成 |
| `audit.py` | Immutable audit log for all state transitions |
| `outbox.py` |.Transactional outbox for exactly-once delivery |

### Services (`app/services/`)
| File | Role |
|------|------|
| `event_bus.py` | Redis Streams pub/sub; stream groups for consumers |
| `task_service.py` | Task CRUD + state transition enforcement |

### Workers (`app/workers/`)
| File | Role |
|------|------|
| `dispatch_worker.py` | Parallel task dispatch with exponential retry |
| `orchestrator_worker.py` | DAG-based task orchestration |
| `outbox_relay.py` | Polls outbox table, publishes to EventBus, marks delivered |

## CONVENTIONS

- Async throughout (`async def`, `await`)
- SQLAlchemy 2.0 style (async sessions, `select()` statements)
- Outbox relay runs as separate process; must poll reliably
- State machine transitions ONLY via `task_service.py` (never direct update)

## ARCHITECTURE NOTES

**EventBus Pattern:**
```
Producer → Redis Stream → Consumer Group → Worker
                              ↓
                      XREADGROUP (blocking)
```

**Outbox Pattern:**
```
DB Transaction → outbox table (unpublished)
                         ↓
              outbox_relay.py polls & publishes
                         ↓
              Marks row published (idempotent)
```

**Dispatch Retry:** Exponential backoff (base 2), max 5 attempts, task marked `待审查` on final failure.
