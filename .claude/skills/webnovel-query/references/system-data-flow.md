---
name: system-data-flow
purpose: 项目初始化和状态查询时加载，理解数据结构
version: "5.0"
---

<context>
此文件用于项目数据结构参考。Claude 已知一般文件组织，这里只补充网文工作流特定的目录约定和脚本职责。
</context>

<instructions>

## 目录约定

```
项目根目录/
├── 正文/           # 章节文件（第0001章.md 或 第1卷/第001章-标题.md）
├── 大纲/           # 卷纲/章纲/场景纲
├── 设定集/         # 世界观/力量体系/角色卡/物品卡
└── .webnovel/
    ├── state.json          # 权威状态（entities_v3 + alias_index + 进度/主角/strand_tracker）
    ├── workflow_state.json # 工作流断点（用于 /webnovel-resume）
    ├── index.db            # SQLite 索引（章节/实体/别名/关系/伏笔，可重建）
    └── archive/            # 归档数据（不活跃角色/已回收伏笔）
```

## v5.0 双 Agent 架构

```
写作前: Context Agent 读取数据 → 组装上下文包
写作中: Writer 使用上下文包生成纯正文（无 XML 标签）
写作后: Data Agent 处理正文 → AI 提取实体 → 写入数据链

Context Agent (读) ←→ 数据存储 ←→ Data Agent (写)
```

## 脚本/模块职责速查 (v5.0)

### 核心脚本

| 脚本 | 输入 | 输出 |
|------|------|------|
| `init_project.py` | 项目信息 | 生成 `.webnovel/state.json` 等 |
| `update_state.py` | 参数 | 原子更新 `state.json` 字段（进度/主角/strand_tracker） |
| `backup_manager.py` | 章节号 | 自动 Git 备份 |
| `status_reporter.py` | 无 | 生成健康报告/伏笔紧急度 |
| `archive_manager.py` | 无 | 归档不活跃数据 |

### data_modules 模块

| 模块 | 职责 |
|------|------|
| `state_manager.py` | 实体状态管理（读写 entities_v3） |
| `index_manager.py` | SQLite 索引管理（章节/实体/场景查询） |
| `entity_linker.py` | 别名注册与消歧（alias_index 管理） |
| `rag_adapter.py` | 向量嵌入与语义检索 |
| `style_sampler.py` | 风格样本提取与管理 |
| `api_client.py` | LLM API 调用封装 |
| `config.py` | 配置管理 |

## 每章数据链（v5.0 顺序）

```
1. Context Agent 组装上下文包
   → 读取大纲/state.json/index.db/RAG
   → 输出上下文包 JSON

2. Writer 生成章节内容
   → 纯正文，3000-5000 字
   → 无需写 XML 标签

3. 审查 (5 个 Agent 并行)
   → 爽点/一致性/节奏/OOC/连贯性检查
   → 输出审查报告

4. 润色
   → 基于审查报告修复问题
   → AI 痕迹清除

5. Data Agent 处理数据链
   → AI 实体提取（替代 XML 标签解析）
   → 实体消歧（置信度策略）
   → 更新 state.json (entities_v3 + alias_index + 进度/消歧记录)
   → 更新 index.db
   → 向量嵌入 (RAG)
   → 风格样本评估

6. Git 备份（强制）
```

> `update_state.py` 用于手动/脚本化更新 `progress`/`protagonist_state`/`strand_tracker` 等字段；主流程通常由 Data Agent 在处理数据链时同步推进进度。

## state.json 核心字段 (v5.0)

```json
{
  "project_info": {"title": "", "genre": ""},
  "progress": {"current_chapter": N, "total_words": W, "current_volume": 1},
  "protagonist_state": {
    "name": "",
    "power": {"realm": "", "layer": 1, "bottleneck": ""},
    "location": {"current": "", "last_chapter": 0},
    "golden_finger": {"name": "", "level": 1, "skills": []}
  },
  "entities_v3": {
    "角色": {"entity_id": {"canonical_name": "", "aliases": [], "tier": "", "current": {}, "history": []}},
    "地点": {},
    "物品": {},
    "势力": {},
    "招式": {}
  },
  "alias_index": {
    "别名": [{"type": "角色", "id": "entity_id"}]
  },
  "relationships": {},
  "structured_relationships": [],
  "disambiguation_warnings": [],
  "disambiguation_pending": [],
  "plot_threads": {"active_threads": [], "foreshadowing": []},
  "world_settings": {},
  "strand_tracker": {
    "last_quest_chapter": 0,
    "last_fire_chapter": 0,
    "last_constellation_chapter": 0,
    "current_dominant": "quest",
    "chapters_since_switch": 0,
    "history": []
  },
  "review_checkpoints": []
}
```

## Data Agent AI 提取流程

v5.0 不再要求 XML 标签，由 Data Agent 智能提取：

1. **实体识别**: 从正文语义识别角色/地点/物品/势力
2. **实体匹配**: 优先匹配已有实体（通过 alias_index）
3. **消歧处理**:
   - 置信度 > 0.8: 自动采用
   - 置信度 0.5-0.8: 采用但记录 warning
   - 置信度 < 0.5: 标记待人工确认
4. **状态变化识别**: 境界突破/位置移动/关系变化
5. **写入存储**: entities_v3 + alias_index + index.db

## 伏笔字段规范

| 字段 | 规范值 | 兼容值（历史） |
|------|--------|---------------|
| status | `未回收` / `已回收` | 待回收/进行中/active/pending |

**推荐字段**: content, status, planted_chapter, target_chapter, tier

## alias_index 格式 (v5.0 一对多)

```json
{
  "林天": [{"type": "角色", "id": "lintian"}],
  "天云宗": [
    {"type": "地点", "id": "loc_tianyunzong"},
    {"type": "势力", "id": "faction_tianyunzong"}
  ]
}
```

同一别名可映射到多个实体，消歧时根据 type 或上下文判断。

</instructions>

<examples>

<example>
<input>查询当前进度</input>
<output>
```bash
cat .webnovel/state.json | jq '.progress'
# 输出: { "current_chapter": 45, "total_words": 135000 }
```
</output>
</example>

<example>
<input>查询实体别名</input>
<output>
```bash
cat .webnovel/state.json | jq '.alias_index["林天"]'
# 输出: [{"type": "角色", "id": "lintian"}]
```
</output>
</example>

<example>
<input>检查伏笔紧急度</input>
<output>
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/status_reporter.py" --focus urgency
```
</output>
</example>

<example>
<input>查询实体出场记录</input>
<output>
```bash
python -m data_modules.index_manager entity-appearances --entity "lintian" --project-root "."
```
</output>
</example>

</examples>

<errors>
❌ 伏笔状态写成"待回收" → ✅ 使用规范值"未回收"
❌ 手工更新忘记加 planted_chapter → ✅ 脚本已自动补全
❌ 归档路径混淆 → ✅ 固定为 `.webnovel/archive/*.json`
❌ alias_index 期望单对象 → ✅ v5.0 使用数组格式（一对多）
❌ 期望 XML 标签提取 → ✅ v5.0 由 Data Agent AI 自动提取
❌ 使用旧版 data_modules.state_manager schema → ✅ 统一使用 entities_v3 结构
</errors>
