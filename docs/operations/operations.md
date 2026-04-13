# 项目结构与运维

## 目录层级（真实运行）

在 Claude Code + Marketplace 安装下，至少有 4 层概念：

1. `WORKSPACE_ROOT`（Claude 工作区根，通常是 `${CLAUDE_PROJECT_DIR}`）
2. `WORKSPACE_ROOT/.claude/`（工作区级指针与配置）
3. `PROJECT_ROOT`（真实小说项目根，`/webnovel-init` 按书名创建）
4. `CLAUDE_PLUGIN_ROOT`（插件缓存目录，不在项目内）

### A) Workspace 目录（含 `.claude`）

```text
workspace-root/
├── .claude/
│   ├── .webnovel-current-project   # 指向当前小说项目根
│   └── settings.json
├── 小说A/
├── 小说B/
└── ...
```

### B) 小说项目目录（`PROJECT_ROOT`）

```text
project-root/
├── .webnovel/            # 运行时数据（state/index/vectors/summaries）
├── 正文/                  # 正文章节
├── 大纲/                  # 总纲与卷纲
└── 设定集/                # 世界观、角色、力量体系
```

## 插件目录（Marketplace 安装）

插件不在小说项目目录内，而在 Claude 插件缓存目录。运行时统一用 `CLAUDE_PLUGIN_ROOT` 引用：

```text
${CLAUDE_PLUGIN_ROOT}/
├── skills/
├── agents/
├── scripts/
└── references/
```

### C) 用户级全局映射（兜底）

当工作区没有可用指针时，会使用用户级 registry 做 `workspace -> current_project_root` 映射：

```text
${CLAUDE_HOME:-~/.claude}/webnovel-writer/workspaces.json
```

## 模拟目录实测（2026-03-03）

基于 `D:\wk\novel skill\plugin-sim-20260303-012048` 的实际结果：

- `WORKSPACE_ROOT`：`D:\wk\novel skill\plugin-sim-20260303-012048`
- 指针文件：`D:\wk\novel skill\plugin-sim-20260303-012048\.claude\.webnovel-current-project`
- 指针内容：`D:\wk\novel skill\plugin-sim-20260303-012048\凡人资本论-二测`
- 已创建项目示例：`凡人资本论/`、`凡人资本论-二测/`

## 常用运维命令

统一前置（手动 CLI 场景）：

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

### 索引重建

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index process-chapter --chapter 1
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index stats
```

### 健康报告

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus all
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus urgency
```

### 向量重建

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag index-chapter --chapter 1
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag stats
```

### 测试入口

```bash
pwsh "${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.ps1" -Mode smoke
pwsh "${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.ps1" -Mode full
```

## Story System 运维

### preflight

检查统一入口与事件链目录是否可用：

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" preflight
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" story-events --health
```

重点看三项：

- `.story-system/events/` 是否可读
- `.webnovel/index.db` 中 `story_events` 是否可查
- `override_contracts` 是否能统计 `amend_proposal`

### health

最小健康检查命令：

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" story-events --health
```

返回字段：

- `sqlite_rows`
- `event_files`
- `ok`

### backup

做 Story System 相关备份时，至少同时备这两块：

```bash
.story-system/
.webnovel/index.db
```

如果要做章节级回溯，建议连同 `.webnovel/summaries/` 一起备份。
