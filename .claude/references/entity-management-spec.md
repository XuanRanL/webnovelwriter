# 实体管理规范 (Entity Management Specification)

> **版本**: 5.0
> **适用范围**: 所有实体类型（角色/地点/物品/势力/招式）
> **核心目标**: AI 驱动的实体提取、别名管理、版本追踪

---

## v5.0 变更

1. **AI 提取替代 XML 标签**: Data Agent 从纯正文语义提取实体，不再依赖 `extract_entities.py`
2. **alias_index 一对多**: 同一别名可映射到多个实体，内嵌在 `state.json`
3. **entities_v3 分组格式**: 按类型分组（角色/地点/物品/势力/招式）
4. **置信度消歧**: >0.8 自动采用，0.5-0.8 警告，<0.5 人工确认
5. **无向后兼容**: 不保留旧版 `entities` 列表格式
6. **双 Agent 架构**: Context Agent (读) + Data Agent (写)

> **注意**: XML 标签仍可用于手动标注场景，但 v5.0 主流程不再要求。

---

## 一、问题分析

### 1.1 当前问题

1. **别名问题**: 同一角色在不同章节有不同称呼
   - 第1章: "废物" (贬称)
   - 第10章: "林天" (真名)
   - 第50章: "林宗主" (地位称呼)
   - 第200章: "不灭战神" (称号)

2. **创建/更新问题**: 当前使用 `setdefault()` 只能创建，无法更新

3. **版本追踪问题**: 无法追踪属性变更历史

### 1.2 各类实体特点

| 实体类型 | 别名复杂度 | 属性变化 | 层级关系 |
|---------|-----------|---------|---------|
| 角色    | 高（多种称呼）| 高（境界/位置/关系）| 无 |
| 地点    | 中（简称/全称）| 低（状态变化）| 有（省>市>区）|
| 物品    | 低（别称较少）| 中（升级/转移）| 无 |
| 势力    | 中（简称/别称）| 中（等级/领地）| 有（总部>分部）|
| 招式    | 低（别名少见）| 中（升级）| 无 |

---

## 二、标签体系设计

### 2.1 新建实体 (`<entity>`)

首次出场时使用，**推荐**包含 `id` 属性作为唯一标识（便于后续更新/加别名）；不写 `id` 时脚本会自动生成并注册 `name/alias`。

```xml
<entity type="角色" id="lintian" name="林天" desc="主角，觉醒吞噬金手指" tier="核心">
  <alias>废物</alias>
  <alias>那个少年</alias>
</entity>

<entity type="地点" id="tianyunzong" name="天云宗" desc="东域三大宗门之一" tier="核心">
  <alias>宗门</alias>
  <alias>天云</alias>
</entity>

<entity type="地点" id="tianyunzong_waimen" name="天云宗外门" parent="tianyunzong" desc="外门弟子修炼区" tier="支线">
  <alias>外门</alias>
</entity>
```

> 注：当前脚本不解析 `<sub-location>` 这种嵌套子标签；子地点请用独立 `<entity>` + `parent` 字段表达。

### 2.2 添加别名 (`<entity-alias>`)

后续章节出现新称呼时使用：

```xml
<!-- 方式1: 通过 id 引用 -->
<entity-alias id="lintian" alias="林宗主" context="成为天云宗主后"/>

<!-- 方式2: 通过已知别名引用（自动解析） -->
<entity-alias ref="林天" alias="不灭战神" context="晋升战神称号后"/>
```

### 2.3 更新属性 (`<entity-update>`)

属性发生重大变化时使用（v5.0 支持多种操作）：

```xml
<!-- 基础操作 -->
<entity-update id="lintian">
  <set key="realm" value="筑基期一层" reason="血煞秘境突破"/>
  <set key="location" value="天云宗"/>
</entity-update>

<!-- 删除属性 -->
<entity-update id="lintian">
  <unset key="bottleneck"/>
</entity-update>

<!-- 数组操作 -->
<entity-update id="lintian">
  <add key="titles" value="不灭战神"/>
  <remove key="allies" value="张三"/>
</entity-update>

<!-- 计数操作 -->
<entity-update id="lintian">
  <inc key="kill_count" delta="1"/>
</entity-update>

<!-- 顶层字段修改 -->
<entity-update id="lintian">
  <set key="tier" value="核心"/>
  <set key="canonical_name" value="林不灭" reason="觉醒后改名"/>
</entity-update>

<!-- 通过别名引用（需 type 消歧） -->
<entity-update ref="林宗主" type="角色">
  <set key="realm" value="金丹期"/>
</entity-update>
```

**顶层字段白名单**: `tier`, `desc`, `canonical_name`, `importance`, `status`, `parent`

**操作类型**:
| 操作 | 语法 | 说明 |
|------|------|------|
| set | `<set key="k" value="v"/>` | 设置属性值 |
| unset | `<unset key="k"/>` | 删除属性 |
| add | `<add key="k" value="v"/>` | 向数组添加元素 |
| remove | `<remove key="k" value="v"/>` | 从数组删除元素 |
| inc | `<inc key="k" delta="1"/>` | 数值递增（默认+1） |

### 2.4 简化写法（自动检测模式）

对于简单场景，可使用传统标签格式，系统自动检测：

```xml
<!-- 系统自动查询 alias_index，判断是创建还是更新 -->
<entity type="角色" name="林宗主" realm="金丹期"/>
```

**自动检测逻辑**:
1. 查询 `alias_index`，检查 `name` 是否已是某个实体的别名
2. 如找到 → 更新该实体
3. 如未找到 → 视为新实体，创建并生成 `id`

---

## 三、存储结构设计

### 3.1 state.json 结构

```json
{
  "entities_v3": {
    "角色": {
      "lintian": {
        "id": "lintian",
        "canonical_name": "林天",
        "aliases": ["废物", "那个少年", "林宗主", "不灭战神"],
        "tier": "核心",
        "desc": "主角，觉醒吞噬金手指",
        "current": {
          "realm": "金丹期",
          "location": "天云宗",
          "last_chapter": 100
        },
        "history": [
          {"chapter": 1, "changes": {"realm": "练气期一层"}, "reasons": {"realm": "初始状态"}, "added_at": "2026-01-01 00:00:00"},
          {"chapter": 10, "changes": {"realm": "练气期九层"}, "reasons": {"realm": "吞噬突破"}, "added_at": "2026-01-01 00:00:00"},
          {"chapter": 50, "changes": {"realm": "筑基期一层"}, "reasons": {"realm": "血煞秘境突破"}, "added_at": "2026-01-01 00:00:00"}
        ],
        "created_chapter": 1,
        "first_appearance": "正文/第0001章.md"
      }
    },
    "地点": {},
    "物品": {},
    "势力": {},
    "招式": {}
  },

  "alias_index": {
    "废物": [{"type": "角色", "id": "lintian"}],
    "林天": [{"type": "角色", "id": "lintian"}],
    "林宗主": [{"type": "角色", "id": "lintian"}],
    "天云宗": [
      {"type": "地点", "id": "loc_tianyunzong"},
      {"type": "势力", "id": "faction_tianyunzong"}
    ],
    "外门": [{"type": "地点", "id": "tianyunzong_waimen"}]
  }
}
```

**注意**: v5.0 的 `alias_index` 值为数组（一对多），不再是单个对象。

### 3.2 ID 生成规则

```python
import hashlib
from pypinyin import lazy_pinyin

def generate_entity_id(entity_type: str, name: str, existing_ids: set) -> str:
    """
    生成唯一实体 ID

    规则:
    1. 优先使用拼音（去空格、小写）
    2. 冲突时追加数字后缀
    3. 特殊前缀按类型
    """
    # 类型前缀映射
    prefix_map = {
        "物品": "item_",
        "势力": "faction_",
        "招式": "skill_",
        "地点": "loc_"
        # 角色无前缀
    }

    # 生成基础 ID
    pinyin = ''.join(lazy_pinyin(name))
    base_id = prefix_map.get(entity_type, '') + pinyin.lower()

    # 处理冲突
    final_id = base_id
    counter = 1
    while final_id in existing_ids:
        final_id = f"{base_id}_{counter}"
        counter += 1

    return final_id
```

---

## 四、处理流程

> **v5.0 说明**: 以下流程描述的是 XML 标签解析流程，仅适用于**手动标注场景**。
> v5.0 主流程使用 Data Agent 从纯正文 AI 提取实体，参见 `agents/data-agent.md`。

### 4.1 完整流程图（手动标注场景）

```
章节内容
    ↓
extract_entities.py
    ↓
┌─────────────────────────────────────────────────────────┐
│ 1. 解析所有 XML 标签                                      │
│    - <entity> 标签 → 新实体候选                           │
│    - <entity-alias> 标签 → 别名注册                       │
│    - <entity-update> 标签 → 属性更新                      │
│                                                          │
│ 2. 加载 state.json 的 alias_index                        │
│                                                          │
│ 3. 对每个 <entity> 标签:                                  │
│    ├─ 有 id 属性 → 使用指定 id                            │
│    └─ 无 id 属性 → 查询 alias_index:                      │
│        ├─ 找到 → 更新模式（使用找到的 id）                  │
│        └─ 未找到 → 创建模式（生成新 id）                    │
│                                                          │
│ 4. 创建模式:                                              │
│    - 生成唯一 id                                         │
│    - 初始化 entity 对象（canonical_name, aliases, etc.）  │
│    - 设置 current 初始属性                                │
│    - 记录 history[0] 初始状态                             │
│    - 更新 alias_index（所有别名 → id）                    │
│                                                          │
│ 5. 更新模式:                                              │
│    - 合并新属性到 current                                 │
│    - 追加 history 记录（如有重要变更）                     │
│    - 更新 last_chapter                                   │
│    - 添加新别名到 aliases 和 alias_index                  │
│                                                          │
│ 6. 处理 <entity-alias>:                                   │
│    - 解析 id 或 ref                                       │
│    - 添加 alias 到 aliases 列表                           │
│    - 更新 alias_index                                    │
│                                                          │
│ 7. 处理 <entity-update>:                                  │
│    - 解析 id 或 ref（通过 alias_index 解析）               │
│    - 应用 <set> 更新到 current                            │
│    - 追加 history 记录                                    │
└─────────────────────────────────────────────────────────┘
    ↓
state.json 更新
```

### 4.2 别名解析函数

```python
def resolve_entity_by_alias(alias: str, entity_type: str, state: dict) -> tuple:
    """
    通过别名解析实体 ID

    Args:
        alias: 别名或名称
        entity_type: 实体类型（角色/地点/物品/势力/招式）
        state: state.json 内容

    Returns:
        (entity_id, entity_data) 或 (None, None)
    """
    alias_index = state.get("alias_index", {})

    # 1. 精确匹配
    if alias in alias_index:
        ref = alias_index[alias]
        if ref["type"] == entity_type:
            entity_id = ref["id"]
            entity_data = state["entities_v3"].get(entity_type, {}).get(entity_id)
            return (entity_id, entity_data)

    # 2. 模糊匹配（可选，适用于"云长老" vs "云长老（天云宗）"）
    for key, ref in alias_index.items():
        if ref["type"] == entity_type and alias in key:
            entity_id = ref["id"]
            entity_data = state["entities_v3"].get(entity_type, {}).get(entity_id)
            return (entity_id, entity_data)

    return (None, None)
```

---

## 五、特殊场景处理

### 5.1 角色改名

当角色正式改名（如赐名、觉醒后改名）：

```xml
<!-- 保留旧别名，添加新的 canonical_name -->
<entity-update id="lintian">
  <set key="canonical_name" value="林不灭" reason="觉醒战神血脉后改名"/>
</entity-update>
<entity-alias id="lintian" alias="林不灭"/>
```

### 5.2 地点层级

子地点作为独立实体，但记录父子关系：

```xml
<entity type="地点" id="tianyunzong_neimen" name="天云宗内门"
        parent="tianyunzong" desc="核心弟子修炼区域" tier="支线">
  <alias>内门</alias>
</entity>
```

### 5.3 物品转移

物品更换主人：

```xml
<entity-update ref="混沌珠">
  <set key="owner" value="李雪" reason="林天将混沌珠赠予李雪"/>
</entity-update>
```

### 5.4 势力合并/覆灭

```xml
<entity-update id="xueshamen">
  <set key="status" value="覆灭" reason="被天云宗剿灭"/>
  <set key="destroyed_chapter" value="75"/>
</entity-update>
```

---

## 六、迁移策略（已移除）

本插件不再提供旧格式迁移与向后兼容。v5.0 推荐做法：

1. 删除 `.webnovel/index.db`（索引可重建）
2. 保留章节文件不动（纯正文是唯一真相）
3. 运行 `python -m data_modules.index_manager rebuild --project-root .` 重建索引
4. Data Agent 会在后续章节中自动提取实体

> **注意**: v5.0 不再依赖 `extract_entities.py`，实体提取由 Data Agent 自动完成。

---

## 七、查询接口

### 7.1 通过别名查询实体

```python
def query_entity(name_or_alias: str, entity_type: str = None) -> dict:
    """
    通过名称或别名查询实体完整信息

    返回:
    {
        "id": "lintian",
        "type": "角色",
        "canonical_name": "林天",
        "aliases": [...],
        "current": {...},
        "history": [...]
    }
    """
```

### 7.2 查询实体变更历史

```python
def query_entity_history(entity_id: str, entity_type: str) -> list:
    """
    查询实体的属性变更历史

    返回:
    [
        {"chapter": 1, "changes": {"realm": "练气期一层"}, "reasons": {"realm": "初始"}, "added_at": "YYYY-MM-DD HH:MM:SS"},
        {"chapter": 50, "changes": {"realm": "筑基期"}, "reasons": {"realm": "突破"}, "added_at": "YYYY-MM-DD HH:MM:SS"},
        ...
    ]
    """
```

### 7.3 查询某章节实体状态

```python
def query_entity_at_chapter(entity_id: str, entity_type: str, chapter: int) -> dict:
    """
    查询实体在特定章节时的状态（通过历史回溯）

    用于一致性检查：验证描述是否与当时状态匹配
    """
```

---

## 八、错误处理

### 8.1 别名冲突

v5.0 允许 **alias_index 一对多**：同一别名可以指向多个实体（跨类型或同类型）。

当你用 `ref="别名"` 进行引用，但命中多个实体且无法消歧时，脚本会直接报错：

```
⚠️ 别名歧义: '宗主' 命中 2 个实体，请改用 id 或补充 type 属性

解决方案:
  1. 改用稳定 id：<entity-update id="...">...</entity-update>
  2. 补充 type（仅能消歧跨类型；同类型重名仍需 id）
  3. 追加更具体的 alias（避免以后持续歧义）
```

### 8.2 未知引用

当 `<entity-update ref="xxx">` 找不到对应实体：

```
⚠️ 未知实体引用: "xxx" 在 alias_index 中未找到
   建议: 先使用 <entity> 创建，或检查拼写
```

---

## 九、总结

### 9.1 核心改进

1. **统一 ID 系统**: 所有实体有唯一 ID，别名映射到 ID
2. **自动检测**: 无需显式指定创建/更新，系统自动判断
3. **版本追踪**: history 数组记录重要属性变更
4. **v5.0 架构**: 使用 `entities_v3` 分组格式，XML 标签为可选（手动标注场景）

### 9.2 新增标签

| 标签 | 用途 | 必填属性 |
|------|------|---------|
| `<entity>` | 创建/更新实体 | type, name |
| `<entity-alias>` | 添加别名 | id/ref, alias |
| `<entity-update>` | 更新属性 | id/ref, `<set>`/`<unset>`/`<add>`/`<remove>`/`<inc>` |

### 9.3 实现优先级

1. **P0**: alias_index 和自动检测（解决核心问题）
2. **P1**: 属性更新和历史记录
3. **P2**: 索引主键迁移（entity_id）+ Context Pack
