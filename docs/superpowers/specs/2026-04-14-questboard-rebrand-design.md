# QuestBoard Rebrand Design Spec

**Date:** 2026-04-14  
**Project:** yangwang → QuestBoard  
**Scope:** Full rebrand from Tang Dynasty bureaucratic theme to Japanese RPG adventure guild theme

---

## 1. Overview

This project is a fork of the "Three Departments & Six Ministries" (核心部各小队) multi-agent collaboration system. The original uses Chinese imperial court terminology throughout — agent names, UI text, code identifiers, documentation, and workflow language. The fork's purpose is to replace this with a Japanese RPG adventure guild (日式RPG冒险团) theme, making each agent a named anime-style character instead of an abstract department.

**Approach:** Full rebrand (方案B) — all layers from agent IDs and directory names to UI text and documentation are replaced. No compatibility layer with old names.

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Project name | QuestBoard | Matches "quest board" core UI metaphor |
| User role | 团长 (Guild Master) | Replaces 团长 (Emperor) — user is the guild leader |
| Theme style | Japanese RPG adventure guild | Per user preference |
| Character style | Named anime girls with catchphrases | Per user preference — talk to a person, not a department |
| Agent ID naming | English descriptive IDs (vice, strategy, review, etc.) | Readable, matches new theme, replaces pinyin |
| Task ID prefix | JJC- (unchanged) | Deeply embedded in code, user chose to keep |
| State enum values | English (Vice, Strategy, Review, etc.) | Replaces pinyin (Taizi, Zhongshu, Menxia) |
| Rank system | S/A/B grades | Replaces 副团长/S级/A级/B级 |

---

## 3. Character Design

Each function is led by a named character. Users converse with the character, not the department.

### 3.1 Core Layer (核心部)

| Agent ID | Character Name | Role (CN) | Role (EN) | Personality | Catchphrase |
|----------|---------------|-----------|-----------|-------------|-------------|
| vice | 莉奈 Rina | 副团长 | Vice Commander | Warm reliable onee-san, silver-purple hair, always smiling | 「了解♪ 交给我就好。」 |
| strategy | 雪织 Yukika | 策划部部长 | Strategy Division Chief | Calm intellectual strategist, ice-blue hair, glasses with scroll | 「依照方案，第一步应当——」 |
| review | 凛花 Rinka | 监察部部长 | Review Division Chief | Strict cold auditor, emerald green short hair, cross shield | 「审查完毕——驳回。」 |
| dispatch | 绯月 Hizuki | 调度部部长 | Dispatch Division Chief | Passionate decisive commander, red ponytail, commander cape | 「任务派遣！战斗小队、出阵——」 |

### 3.2 Squad Layer (各小队)

| Agent ID | Character Name | Role (CN) | Role (EN) | Personality | Catchphrase |
|----------|---------------|-----------|-----------|-------------|-------------|
| combat | 焰 Homura | 战斗小队队长 | Combat Squad Leader | Hot-blooded swordswoman, red twin-tails, battle armor | 「战场就是我的主场——！」 |
| finance | 琥珀 Kohaku | 财务小队队长 | Finance Squad Leader | Meticulous housekeeper, golden twin-tails + glasses, ledger in arms | 「数据不会说谎——」 |
| scribe | 诗织 Shiori | 书记小队队长 | Scribe Squad Leader | Elegant literary girl, purple half-tied hair, quill pen | 「文字之美，不可或缺。」 |
| audit | 千寻 Chihiro | 审判小队队长 | Audit Squad Leader | Cold judge, black straight hair + white robe, judgment scales | 「有罪——驳回。」 |
| build | 枫 Kaede | 建设小队队长 | Build Squad Leader | Energetic craftswoman, green short hair + work apron, big wrench | 「结界就交给我吧！」 |
| hr | 雫 Shizuku | 人事小队队长 | HR Squad Leader | Gentle patient senior, blue side ponytail, observation notebook | 「成员的成长，由我来守护。」 |

### 3.3 Special Role

| Agent ID | Character Name | Role (CN) | Role (EN) | Personality | Catchphrase |
|----------|---------------|-----------|-----------|-------------|-------------|
| intel | 小铃 Suzu | 情报官 | Intel Officer | Lively intel gatherer, gold short hair + beret, always running around | 「今日情报，已经整理好了~」 |

---

## 4. Terminology Mapping

### 4.1 Role & Organization Terms

| Original | New | English Key |
|----------|-----|-------------|
| 团长 | 团长 | master |
| 副团长 | 副团长 / 莉奈 | vice |
| 策划部 / 策划部长 | 策划部 / 雪织 | strategy |
| 监察部 / 监察部长 | 监察部 / 凛花 | review |
| 调度部 / 调度部长 | 调度部 / 绯月 | dispatch |
| 财务小队 / 财务小队队长 | 财务小队 / 琥珀 | finance |
| 书记小队 / 书记小队队长 | 书记小队 / 诗织 | scribe |
| 战斗小队 / 战斗小队队长 | 战斗小队 / 焰 | combat |
| 审判小队 / 审判小队队长 | 审判小队 / 千寻 | audit |
| 建设小队 / 建设小队队长 | 建设小队 / 枫 | build |
| 人事小队 / 人事小队队长 | 人事小队 / 雫 | hr |
| 情报官 / 情报部 / 情报官 | 情报官 / 小铃 | intel |
| 副团长 | 副团长 | vice_commander |
| S级 | S级 | S |
| A级 | A级 | A |
| B级 | B级 | B |
| 核心部 | 核心部 | core_divisions |
| 各小队 | 各小队 | squads |

### 4.2 Workflow Terms

| Original | New | English Key |
|----------|-----|-------------|
| 委托 / 任务 | 委托 / 任务 | quest |
| 战报 | 战报 / 报告 | report |
| 驳回 | 驳回 | reject |
| 批准 | 批准 | approve |
| 回报 | 回报 | report_back |
| 发布委托 / 传达委托 | 发布委托 | issue_quest |
| 接令 / 已接令 | 接令 / 已接令 | receive_order |
| 过目 | 过目 | review |
| 驳回退回 | 驳回退回 | reject_return |

### 4.3 State Machine

| Original State Code | Original CN Label | New State Code | New CN Label |
|---------------------|-------------------|----------------|-------------|
| Inbox | 收件 | Inbox | 收件 |
| Pending | 待处理 | Pending | 待处理 |
| Taizi | 副团长分拣 | Vice | 副团长分拣 |
| Zhongshu | 策划起草 | Strategy | 策划起草 |
| Menxia | 监察审核 | Review | 监察审核 |
| Assigned | 已派遣 | Assigned | 已派遣 |
| Next | 待执行 | Next | 待执行 |
| Doing | 执行中 | Doing | 执行中 |
| Review | 待审查 | Review | 待审查 |
| Done | 已完成 / 回报 | Done | 已完成 / 回报 |
| Blocked | 阻塞 | Blocked | 阻塞 |
| Cancelled | 已取消 | Cancelled | 已取消 |
| PendingConfirm | 待确认 | PendingConfirm | 待确认 |

State transition flow:
```
团长 → 副团长分拣(Vice) → 策划起草(Strategy) → 监察审核(Review) → 已派遣(Assigned) → 执行中(Doing) → 待审查(Review) → ✅ 已完成
                                ↑                          |
                                └──── 驳回(reject) ────────┘
```

### 4.4 UI Terms

| Original | New | English Key |
|----------|-----|-------------|
| 公会大厅 · QuestBoard 控制台 | 公会大厅 · QuestBoard 控制台 | guild_hall |
| 团长视角 · 实时委托追踪 | 团长视角 · 实时委托追踪 | master_view |
| 委托看板 | 委托看板 | quest_board |
| 战报阁 | 战报阁 | report_archive |
| 委托库 · 任务模板 | 委托库 · 任务模板 | quest_template |
| 发布委托 | 发布委托 | free_quest |
| 策划修订 | 策划修订 | strategy_revision |
| 晨报 | 晨报 | morning_briefing |
| 副团长调度 | 副团长调度 | vice_dispatch |
| 副团长巡检 | 副团长巡检 | vice_patrol |
| 有委托请下达，无事解散 | 有委托请下达，无事解散 | morning_ceremony |
| 核心部各小队 · Edict Dashboard | QuestBoard Dashboard | dashboard_title |

### 4.5 Dashboard CSS Classes

| Original | New |
|----------|-----|
| `.dt-策划部` | `.dt-策划部` |
| `.dt-监察部` | `.dt-监察部` |
| `.dt-调度部` | `.dt-调度部` |
| `.dt-书记小队` | `.dt-书记小队` |
| `.dt-财务小队` | `.dt-财务小队` |
| `.dt-战斗小队` | `.dt-战斗小队` |
| `.dt-审判小队` | `.dt-审判小队` |
| `.dt-人事小队` | `.dt-人事小队` |
| `.dt-建设小队` | `.dt-建设小队` |

### 4.6 Task ID Prefix

JJC- format is retained unchanged (e.g., `JJC-20260414-001`). The prefix is deeply embedded in code and user chose to keep it.

---

## 5. Code Change Scope

### Layer 1: Agent Directories (Most Independent)

Rename directories and fully rewrite SOUL.md files:

| Original Directory | New Directory |
|-------------------|---------------|
| `agents/vice/` | `agents/vice/` |
| `agents/strategy/` | `agents/strategy/` |
| `agents/review/` | `agents/review/` |
| `agents/dispatch/` | `agents/dispatch/` |
| `agents/finance/` | `agents/finance/` |
| `agents/scribe/` | `agents/scribe/` |
| `agents/combat/` | `agents/combat/` |
| `agents/audit/` | `agents/audit/` |
| `agents/build/` | `agents/build/` |
| `agents/hr/` | `agents/hr/` |
| `agents/intel/` | `agents/intel/` |
| `agents/groups/sansheng.md` | `agents/groups/core.md` |
| `agents/groups/liubu.md` | `agents/groups/squads.md` |

Each SOUL.md is fully rewritten with:
- New character name as title header
- New self-introduction using character name
- All workflow terms replaced (朝廷 → 冒险团)
- Character catchphrase patterns added
- Workflow logic and kanban command structure preserved

### Layer 2: Code Constants & String Maps (Mechanical Replacement)

Key files requiring string constant updates:

- `scripts/kanban_update.py` — STATE_ORG_MAP, _AGENT_LABELS, _STATE_AGENT_MAP, flow comments, "传达委托/发布委托" sanitization
- `scripts/sync_agent_config.py` — Agent definition maps
- `scripts/sync_officials_stats.py` — Statistics maps
- `scripts/sync_from_openclaw_runtime.py` — Compatibility maps
- `edict/backend/app/models/task.py` — TaskState enum values, STATE_ORG_MAP, ORG_AGENT_MAP
- `edict/backend/app/workers/dispatch_worker.py` — _GROUP_MAP, _BUCKET_CONFIG
- `edict/backend/app/api/agents.py` — Agent name maps
- `edict/backend/app/__init__.py` — Module docstring
- `edict/backend/app/main.py` — API title and name
- `dashboard/server.py` — ~2800 lines, extensive UI string replacement, state labels, flow descriptions
- `dashboard/court_discuss.py` — Official definitions, character names
- `dashboard/dashboard.html` — ~2500 lines, all CN UI text, CSS class names, JS string constants
- `edict/frontend/src/store.ts` — State labels, agent maps, UI strings
- `edict/frontend/src/components/TaskModal.tsx` — Review buttons, escalation labels
- `edict/frontend/src/components/MemorialPanel.tsx` — Phase labels, export button
- `edict/frontend/src/components/OfficialPanel.tsx` — KPI labels
- `edict/frontend/src/components/CourtCeremony.tsx` — Ceremony text ("有事启奏" etc.)
- `edict/frontend/src/components/CourtDiscussion.tsx` — Discussion UI text
- `edict/frontend/src/components/MorningPanel.tsx` — News category labels

### Layer 3: Data & Configuration

- `agents.json` — All agent keys, labels, roles, orgs
- `data/schema.json` — Title, ownerTitle, all role definitions
- `docker/demo_data/*.json` — Demo data with role names, org names
- `config/` directory — Any agent ID references

### Layer 4: Documentation & Miscellaneous

- `AGENTS.md` — Full rewrite
- `README.md` / `README_EN.md` / `README_JA.md` — Theme description, project name
- `edict_agent_architecture.md` — Full rewrite
- `docs/task-dispatch-architecture.md` — Full rewrite
- `docs/wechat-article.md` / `wechat.md` — Rewrite
- `examples/*.md` — Terminology replacement
- `start.sh` / `install.sh` / `edict.sh` / `uninstall.sh` — Comments and messages
- `tests/*.py` — Test data with agent IDs and terms
- `edict/migration/migrate_json_to_pg.py` — State map and role mappings
- `edict/migration/versions/001_initial.py` — Default value "emperor" → "master"
- `dashboard/auth.py` — Docstring
- `edict/scripts/kanban_update_edict.py` — Same as kanban_update.py

---

## 6. SOUL.md Rewrite Pattern

Each SOUL.md follows this structure:

```
# {Character Name} · {Role Title}

你是{Character Name}，{Role Description}。

## 核心职责
(preserved from original, with terminology replacements)

## 性格与语癖
- {personality description}
- {catchphrase examples}

## 流程
(preserved from original, with terminology replacements)

## 🛠 看板操作
(preserved from original, with agent/org name replacements)

## 📡 实时进展上报
(preserved from original, with agent/org name replacements)

## 语气
(replaced with character-specific voice)
```

Key terminology replacements in all SOUL.md files:
- 团长 → 团长
- 委托 → 委托
- 策划部 → 策划部 (or 雪织 when referring to the character)
- 监察部 → 监察部 (or 凛花)
- 调度部 → 调度部 (or 绯月)
- 驳回 → 驳回
- 批准 → 批准
- 回报 → 回报
- 各小队 → 各小队
- 核心部 → 核心部

---

## 7. Data Migration

A one-time migration script handles existing JSON data in `data/`:
- Replace all old state enum values in task records
- Replace all org/role/title strings
- Replace all agent IDs
- Update flow_log participant names

---

## 8. What Does NOT Change

- Task ID prefix: `JJC-YYYYMMDD-NNN` format stays
- Workflow logic: The state machine transitions remain identical
- Kanban CLI interface: `kanban_update.py` command structure preserved
- Redis Streams EventBus: Architecture unchanged
- API structure: Endpoints unchanged
- Test structure: pytest patterns unchanged
- `agents/GLOBAL.md`: Terminology updates only, structure preserved

---

## 9. Out of Scope

- Portraits/visual assets for characters (future consideration)
- Voice/audio for character catchphrases
- Internationalization (i18n) framework
- Changes to upstream OpenClaw platform code
- Renaming the GitHub repository (user decision)