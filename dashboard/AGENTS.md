# Dashboard — Real-time Monitoring Interface

## OVERVIEW

Embedded dashboard serving API + UI via pure Python stdlib (`http.server`). No build step, no npm, no dependencies — just open `server.py` and it runs.

---

## KEY FILES

| File | Purpose |
|------|---------|
| `server.py` | HTTP server (~2800 lines), port 7891, serves API + static files |
| `dashboard.html` | Embedded UI (~2500 lines), zero dependencies, 10 functional panels |
| `auth.py` | Dashboard login authentication |
| `court_discuss.py` | Multi-agent LLM debate engine |
| `dist/` | Optional React build output (embedded HTML is default) |

---

## CONVENTIONS

- **Zero-dependency**: Use only `http.server`, `json`, `urllib` from stdlib
- **Embedded first**: Always update `dashboard.html` before React build
- **No build step for embedded**: `server.py` + `dashboard.html` must work standalone
- **API prefix**: All endpoints under `/api/`
- **Chinese domain naming**: 旨意 (zhuyi/tasks), 奏折 (zouzhe/memorials), 圣旨 (shengzhi/edicts)

---

## ANTI-PATTERNS

1. **Never import external packages in server.py** — breaks zero-dep philosophy
2. **Don't serve from `dist/` if embedded HTML exists** — embedded is always available
3. **No hardcoded port in code** — use argument or default to 7891
4. **Don't edit `dist/` directly** — React builds there, not source files
