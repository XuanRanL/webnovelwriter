---
name: webnovel-dashboard
description: 启动只读小说管理面板，查看项目状态、实体图谱与章节内容。
allowed-tools: Bash Read
---

# Webnovel Dashboard

## 目标

- 在本地启动只读 Web 面板。
- 实时查看创作进度、设定词典、关系图谱、章节内容与追读力数据。
- 允许监听 `.webnovel/` 变化，但不得修改项目内容。

## 执行流程

### Step 1：确认环境与模块目录

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"

if [ -z "${CLAUDE_PLUGIN_ROOT}" ] || [ ! -d "${CLAUDE_PLUGIN_ROOT}/dashboard" ]; then
  echo "ERROR: 未找到 dashboard 模块: ${CLAUDE_PLUGIN_ROOT}/dashboard" >&2
  exit 1
fi

export DASHBOARD_DIR="${CLAUDE_PLUGIN_ROOT}/dashboard"
```

### Step 2：安装依赖并解析项目根目录

```bash
python -m pip install -r "${DASHBOARD_DIR}/requirements.txt" --quiet
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
echo "项目路径: ${PROJECT_ROOT}"
```

补充要求：
- `PROJECT_ROOT` 必须解析成功
- 若依赖已安装，可重复执行，不视为错误

### Step 3：准备 Python 模块路径并校验前端产物

```bash
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}:${PYTHONPATH}"
else
  export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}"
fi

if [ ! -f "${DASHBOARD_DIR}/frontend/dist/index.html" ]; then
  echo "ERROR: 缺少前端构建产物 ${DASHBOARD_DIR}/frontend/dist/index.html" >&2
  exit 1
fi
```

### Step 4：启动 Dashboard

```bash
python -m dashboard.server --project-root "${PROJECT_ROOT}"
```

如不需要自动打开浏览器：

```bash
python -m dashboard.server --project-root "${PROJECT_ROOT}" --no-browser
```

## 注意事项

- Dashboard 为纯只读面板，不提供修改接口。
- 文件读取必须限制在 `PROJECT_ROOT` 范围内。
- 如需自定义端口，使用 `--port 9000`。
