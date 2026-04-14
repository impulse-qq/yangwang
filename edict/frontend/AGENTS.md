# AGENTS.md — edict/frontend

## OVERVIEW

React 18 dashboard for 核心部各小队 Kanban. 13 components, Zustand store, HTTP 5s polling.

## KEY FILES

| File | Role |
|------|------|
| `src/store.ts` | Zustand store — PIPE, DEPTS, TEMPLATES, useStore, startPolling() |
| `src/api.ts` | REST client — all /api/* calls |
| `src/App.tsx` | Root — tab router, polling orchestration |
| `src/components/*.tsx` | 13 panel components |
| `vite.config.ts` | Build → `dist/`, port 5173 dev |

## CONVENTIONS

- Components: functional, co-located in `src/components/`
- Store: single `useStore`, `startPolling()` / `stopPolling()` for lifecycle
- Types: imported from `api.ts` (Task, LiveStatus, AgentConfig, etc.)
- Styling: Tailwind CSS classes, no inline styles
- State labels: use `STATE_LABEL` / `stateLabel()` from store
- Colors: `DEPT_COLOR` / `deptColor()` for department染色

## COMMANDS

```bash
npm run dev      # Vite dev server :5173
npm run build    # TypeScript + Vite build → dist/
npm run preview  # Preview production build
```

Build output (`dist/`) is served by `dashboard/server.py` at `/`.
