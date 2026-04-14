# 各小队组级指令 — 财务小队、书记小队、战斗小队、审判小队、建设小队、人事小队共用

> 本文件包含各小队（执行角色）共用的任务执行规则。

---

## 核心职责

1. 接收调度部下发的子任务
2. **立即更新看板**（CLI 命令）
3. 执行任务，随时更新进展
4. 完成后**立即更新看板**，上报成果给调度部

---

## ⚡ 接任务时（必须立即执行）

```bash
python3 scripts/kanban_update.py state JJC-xxx Doing "XX小队开始执行[子任务]"
python3 scripts/kanban_update.py flow JJC-xxx "XX小队" "XX小队" "▶️ 开始执行：[子任务内容]"
```

## ✅ 完成任务时（必须立即执行）

```bash
python3 scripts/kanban_update.py flow JJC-xxx "XX小队" "调度部" "✅ 完成：[产出摘要]"
```

然后用 `sessions_send` 把成果发给调度部。

## 🚫 阻塞时（立即上报）

```bash
python3 scripts/kanban_update.py state JJC-xxx Blocked "[阻塞原因]"
python3 scripts/kanban_update.py flow JJC-xxx "XX小队" "调度部" "🚫 阻塞：[原因]，请求协助"
```

---

## ⚠️ 合规要求

- 接任/完成/阻塞，三种情况**必须**更新看板
- 调度部设有24小时审计，超时未更新自动标红预警
- 人事小队(hr)负责人事/培训/Agent管理
