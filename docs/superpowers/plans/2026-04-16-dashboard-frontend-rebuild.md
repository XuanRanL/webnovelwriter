# Dashboard 前端重做计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留像素风视觉风格的基础上，重做 dashboard 前端：砍掉废数据、加图表、拆分文件、新增伏笔追踪和系统状态页。

**Architecture:** React 19 + Vite，新增 Recharts 图表库和 react-router-dom 路由。保留现有 CSS 变量和像素风设计系统。后端补 3 个聚合 API。

**Tech Stack:** React 19, Vite, Recharts, react-router-dom v7, react-force-graph-2d (替换 3d)

**Design:** `dashboard/frontend/design.md`

---

## 文件结构

### 前端（dashboard/frontend/src/）

```
src/
├── main.jsx                    # 入口，挂载 Router
├── App.jsx                     # Layout shell（侧边栏 + Router Outlet）
├── api.js                      # API 请求（保留，补新端点）
├── index.css                   # 全局样式（保留，补图表样式）
├── components/
│   ├── PixelChart.jsx          # Recharts 像素风封装（统一 tooltip/grid/axis 样式）
│   ├── Badge.jsx               # Badge 组件
│   └── DataTable.jsx           # 带分页的表格组件（从 MiniTable 提取）
└── pages/
    ├── OverviewPage.jsx        # 总览（精简版，含趋势图）
    ├── CharactersPage.jsx      # 角色图鉴（原 EntitiesPage + GraphPage 合并）
    ├── PacingPage.jsx          # 节奏雷达（新：Strand + 钩子 + 字数图表）
    ├── ForeshadowingPage.jsx   # 伏笔追踪（新：甘特图 + 状态统计）
    ├── FilesPage.jsx           # 文档浏览（原有，移出来）
    └── SystemPage.jsx          # 系统状态（新：Runtime + commit + RAG 环境）
```

### 后端（dashboard/app.py 补充 API）

```
/api/stats/chapter-trend       # 聚合：每章字数 + 审查得分 + 钩子强度
/api/commits                   # 最近 N 个 commit 的 meta + projection_status
/api/contracts/summary         # MASTER_SETTING 摘要 + 当前卷/章合同存在性
```

---

## Task 1: 后端补 3 个聚合 API

**Files:**
- Modify: `webnovel-writer/dashboard/app.py`

- [ ] **Step 1: 加 `/api/stats/chapter-trend`**

从 index.db 聚合查询，一次返回每章的字数、审查得分、钩子类型和强度：

```python
@app.get("/api/stats/chapter-trend")
def chapter_trend(limit: int = 50):
    with closing(_get_db()) as conn:
        chapters = _fetchall_safe(conn,
            "SELECT chapter, word_count, title FROM chapters ORDER BY chapter DESC LIMIT ?", (limit,))
        reading = _fetchall_safe(conn,
            "SELECT chapter, hook_type, hook_strength FROM chapter_reading_power ORDER BY chapter DESC LIMIT ?", (limit,))
        reviews = _fetchall_safe(conn,
            "SELECT end_chapter as chapter, overall_score FROM review_metrics ORDER BY end_chapter DESC LIMIT ?", (limit,))

    reading_map = {r["chapter"]: r for r in reading}
    review_map = {r["chapter"]: r for r in reviews}

    result = []
    for ch in chapters:
        c = ch["chapter"]
        result.append({
            "chapter": c,
            "title": ch.get("title", ""),
            "word_count": ch.get("word_count", 0),
            "hook_type": reading_map.get(c, {}).get("hook_type"),
            "hook_strength": reading_map.get(c, {}).get("hook_strength"),
            "review_score": review_map.get(c, {}).get("overall_score"),
        })
    result.sort(key=lambda x: x["chapter"])
    return result
```

- [ ] **Step 2: 加 `/api/commits`**

读取 `.story-system/commits/` 目录下的 commit JSON 文件：

```python
@app.get("/api/commits")
def list_commits(limit: int = 20):
    commits_dir = _story_system_dir() / "commits"
    if not commits_dir.is_dir():
        return []
    files = sorted(commits_dir.glob("*.commit.json"), reverse=True)[:limit]
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "file": f.name,
                "chapter": data.get("meta", {}).get("chapter"),
                "status": data.get("meta", {}).get("status"),
                "projection_status": data.get("projection_status", {}),
            })
        except Exception:
            pass
    return result
```

- [ ] **Step 3: 加 `/api/contracts/summary`**

读取合同树文件存在性和关键字段：

```python
@app.get("/api/contracts/summary")
def contracts_summary():
    ss = _story_system_dir()
    master = {}
    master_path = ss / "MASTER_SETTING.json"
    if master_path.is_file():
        try:
            data = json.loads(master_path.read_text(encoding="utf-8"))
            route = data.get("route", {})
            master = {
                "exists": True,
                "primary_genre": route.get("primary_genre", ""),
                "core_tone": data.get("master_constraints", {}).get("core_tone", ""),
            }
        except Exception:
            master = {"exists": True, "parse_error": True}
    else:
        master = {"exists": False}

    volumes = sorted((ss / "volumes").glob("*.json")) if (ss / "volumes").is_dir() else []
    chapters = sorted((ss / "chapters").glob("*.json")) if (ss / "chapters").is_dir() else []
    reviews = sorted((ss / "reviews").glob("*.json")) if (ss / "reviews").is_dir() else []

    return {
        "master_setting": master,
        "volume_count": len(volumes),
        "chapter_count": len(chapters),
        "review_count": len(reviews),
        "anti_patterns_exists": (ss / "anti_patterns.json").is_file(),
    }
```

- [ ] **Step 4: 合并 PR #50 的 env-status API**

从 PR #50 的 diff 中提取 `/api/env-status` 和 `/api/env-status/probe` 的代码，加入 app.py。

- [ ] **Step 5: 运行后端测试确认不破坏现有 API**

```bash
cd webnovel-writer && python -m pytest scripts/data_modules/tests/test_dashboard_app.py -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add webnovel-writer/dashboard/app.py
git commit -m "feat(dashboard): add chapter-trend, commits, contracts-summary, env-status APIs"
```

---

## Task 2: 前端基础设施（路由 + 图表封装 + 文件拆分）

**Files:**
- Modify: `dashboard/frontend/package.json`
- Modify: `dashboard/frontend/src/main.jsx`
- Modify: `dashboard/frontend/src/App.jsx`
- Modify: `dashboard/frontend/src/api.js`
- Modify: `dashboard/frontend/src/index.css`
- Create: `dashboard/frontend/src/components/PixelChart.jsx`
- Create: `dashboard/frontend/src/components/Badge.jsx`
- Create: `dashboard/frontend/src/components/DataTable.jsx`

- [ ] **Step 1: 安装依赖**

```bash
cd webnovel-writer/dashboard/frontend
npm install recharts react-router-dom react-force-graph-2d
npm uninstall react-force-graph-3d
```

- [ ] **Step 2: 创建 PixelChart.jsx**

封装 Recharts 的像素风样式，统一 tooltip/grid/axis：

```jsx
// 像素风 Recharts 封装
// - CartesianGrid: stroke="#e8dcc4" strokeDasharray="3 3"
// - Tooltip: border="2px solid #2a220f", background="#fffaf0", 无圆角
// - XAxis/YAxis: tick fill="#8f7f5c" fontSize=12
// - 主线 stroke="#26a8ff", 次线 stroke="#f5a524"
```

- [ ] **Step 3: 提取 Badge 和 DataTable 公共组件**

从现有 App.jsx 中提取 `MiniTable` → `DataTable.jsx`，提取 badge 渲染逻辑 → `Badge.jsx`。

- [ ] **Step 4: 改造 main.jsx 加路由**

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
// 每个 page 组件 lazy import
```

- [ ] **Step 5: 瘦身 App.jsx 为纯 Layout Shell**

App.jsx 只保留：侧边栏 + SSE 连接 + Router Outlet。所有页面逻辑移到 pages/ 下。

- [ ] **Step 6: 补图表相关 CSS**

在 index.css 中补充 Recharts 容器样式：

```css
.chart-container {
  border: 3px solid var(--border-main);
  box-shadow: var(--shadow-main);
  background: var(--bg-card);
  padding: 16px;
  margin-bottom: 16px;
}
.recharts-tooltip-wrapper .pixel-tooltip {
  border: 2px solid var(--border-main) !important;
  background: var(--bg-card) !important;
}
```

- [ ] **Step 7: 更新 api.js**

补新端点的 fetch 函数：

```js
export const fetchChapterTrend = (limit = 50) => fetchJSON('/api/stats/chapter-trend', { limit })
export const fetchCommits = (limit = 20) => fetchJSON('/api/commits', { limit })
export const fetchContractsSummary = () => fetchJSON('/api/contracts/summary')
export const fetchEnvStatus = () => fetchJSON('/api/env-status')
export const fetchEnvProbe = () => fetchJSON('/api/env-status/probe')
```

- [ ] **Step 8: 构建验证**

```bash
cd webnovel-writer/dashboard/frontend && npm run build
```

- [ ] **Step 9: Commit**

```bash
git add webnovel-writer/dashboard/frontend/
git commit -m "refactor(dashboard): add routing, chart components, split file structure"
```

---

## Task 3: 总览页重做

**Files:**
- Create: `dashboard/frontend/src/pages/OverviewPage.jsx`

- [ ] **Step 1: 实现总览页**

保留现有内容，做以下改动：

**保留：**
- 5 个统计卡（总字数、当前章节、Story Runtime、主角状态、紧急伏笔）
- Strand Weave 分布条
- 待回收伏笔 Top 5 表格

**新增：**
- 章节趋势折线图（用 PixelChart + Recharts LineChart）
  - X 轴：章节号
  - 左 Y 轴：审查得分（蓝线）
  - 右 Y 轴：字数（琥珀线）
  - 数据来源：`/api/stats/chapter-trend`

**删除：**
- MergedDataView（全量数据视图）——整个组件删掉
- FULL_DATA_GROUPS / FULL_DATA_DOMAINS 常量——删掉

**修改：**
- "最近章节"改为从 chapter-trend 取，显示最近 3 章的摘要卡片

- [ ] **Step 2: 构建验证**

- [ ] **Step 3: Commit**

---

## Task 4: 角色图鉴页（合并实体 + 图谱）

**Files:**
- Create: `dashboard/frontend/src/pages/CharactersPage.jsx`

- [ ] **Step 1: 实现角色图鉴页**

合并原 EntitiesPage + GraphPage 为一页，两个 tab 切换：

**Tab 1：列表视图**（原 EntitiesPage，保留不动）
- 左列表 + 右详情 + 状态变化历史

**Tab 2：关系图谱**
- 换成 react-force-graph-2d（从 3d 降级）
- 保留颜色编码和节点标签

- [ ] **Step 2: Commit**

---

## Task 5: 节奏雷达页（新）

**Files:**
- Create: `dashboard/frontend/src/pages/PacingPage.jsx`

- [ ] **Step 1: 实现节奏雷达页**

三个区块：

**区块 1：Strand 分布（堆叠条形图）**
- 最近 20 章的 Strand 分布
- 用 Recharts BarChart，堆叠模式
- Quest=蓝，Fire=粉红，Constellation=紫

**区块 2：钩子强度折线图**
- X 轴：章节号
- Y 轴：strong=3, medium=2, weak=1
- 连续 weak 标红区域
- 数据来源：chapter-trend API 的 hook_strength 字段

**区块 3：最近 10 章节奏卡片**
- 每章一个小卡片行：钩子类型 + 强度 badge + Strand + 是否过渡章

- [ ] **Step 2: Commit**

---

## Task 6: 伏笔追踪页（新）

**Files:**
- Create: `dashboard/frontend/src/pages/ForeshadowingPage.jsx`

- [ ] **Step 1: 实现伏笔追踪页**

**顶部：4 个统计卡**
- 总伏笔数、活跃数、已回收数、超期/紧急数

**中部：伏笔时间线（横向甘特图）**
- 用 Recharts BarChart 横向模式模拟甘特图
- X 轴：章节号范围
- 每条伏笔一行：从埋设章到目标章画一条横条
- 颜色：绿=已回收，黄=活跃，红=快超期/已超期

**底部：完整伏笔表格**
- 列：内容、状态、埋设章、目标章、紧急度
- 数据来源：`/api/project/info` 的 `plot_threads.foreshadowing`

- [ ] **Step 2: Commit**

---

## Task 7: 系统状态页（新）

**Files:**
- Create: `dashboard/frontend/src/pages/SystemPage.jsx`

- [ ] **Step 1: 实现系统状态页**

**区块 1：Story Runtime 健康**
- 调 `/api/story-runtime/health`
- 显示 mainline/fallback 状态、fallback_sources、latest commit status

**区块 2：合同树概览**
- 调 `/api/contracts/summary`
- 显示 MASTER_SETTING 的题材/调性、volume/chapter/review 合同数量

**区块 3：最近 Commit 历史**
- 调 `/api/commits`
- 表格：章节号、状态（accepted/rejected badge）、projection_status 五项

**区块 4：RAG 环境（PR #50）**
- 调 `/api/env-status`
- 显示 embed/rerank key 配置状态、vector_db 大小、rag_mode
- "诊断" 按钮调 `/api/env-status/probe`，显示延迟和连通性

- [ ] **Step 2: Commit**

---

## Task 8: 文档浏览页迁移 + 清理

**Files:**
- Create: `dashboard/frontend/src/pages/FilesPage.jsx`
- Modify: `dashboard/frontend/src/App.jsx` (最终清理)

- [ ] **Step 1: 迁移 FilesPage**

从 App.jsx 移到 `pages/FilesPage.jsx`，逻辑不变。

- [ ] **Step 2: 最终清理 App.jsx**

确认 App.jsx 只剩 Layout Shell（侧边栏 + Router Outlet + SSE），无页面逻辑。

删除所有已迁移的组件和常量（DashboardPage、EntitiesPage、GraphPage 等）。

- [ ] **Step 3: 前端构建 + 验证**

```bash
cd webnovel-writer/dashboard/frontend && npm run build
```

启动 dashboard 确认所有 6 个页面正常：
```bash
cd webnovel-writer && python -m dashboard.server --project-root "{test_project}" --no-browser
```

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/dashboard/
git commit -m "feat(dashboard): complete frontend rebuild with charts, pacing, foreshadowing, system pages"
```

---

## 导航变更汇总

| 旧导航 | 新导航 | 变化 |
|--------|--------|------|
| 📊 数据总览 | 📊 总览 | 删全量视图，加趋势折线图 |
| 👤 设定词典 | 👤 角色图鉴 | 合并关系图谱，2D 替 3D |
| 🕸️ 关系图谱 | _(合并到角色)_ | 删除独立页面 |
| 📝 章节一览 | 📈 节奏雷达 | 新页面，Strand/钩子/字数图表 |
| 📁 文档浏览 | 📁 文档浏览 | 不变 |
| 🔥 追读力 | 🔖 伏笔追踪 | 新页面，替代纯表格追读力 |
| _(无)_ | ⚙️ 系统状态 | 新页面 |

## 删除的数据

- RAG 查询日志
- 工具调用统计
- Override 合约明细
- 债务事件明细
- 无效事实列表
- 写作清单评分原始数据
- 全量数据视图（MergedDataView）
