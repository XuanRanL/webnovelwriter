# STORYTELLER 落地实施方案

## 文档目标

本文档基于前面对 `STORYTELLER` 论文、当前 `webnovel-writer` 架构和落地边界的讨论，给出一份从 `skills` 与 `agents` 视角出发的修正版实施方案。

目标不是复制论文原系统，而是以最小破坏、最高复用的方式，将“中层情节结构”前移到规划阶段，并让写作、审查、数据回写围绕结构化章纲形成闭环。

## 一句话结论

最优方案不是新增独立的 `webnovel-structure` 主流程，而是：

- 升级 `webnovel-plan`，输出结构化详细大纲
- 增强 `context-agent`，把结构化章纲组装进写作包
- 增强 `continuity-checker` 与 `consistency-checker`，分别负责节点覆盖与结构冲突
- 增强 `data-agent`，负责落库覆盖结果与偏差说明

这样可以在不打碎现有系统的前提下，为写作链补上 `STORYTELLER` 最核心的中层结构层。

## 核心原则

1. 不新增独立主流程 `webnovel-structure`
2. 结构前移到 `webnovel-plan`
3. `context-agent` 只聚合，不生成节点
4. `continuity-checker` 负责结构覆盖
5. `consistency-checker` 负责结构冲突
6. `data-agent` 负责落库，不做主判断
7. 全程向后兼容，无节点章纲照常运行

## 总体架构

```text
/webnovel-init
    -> 初始化项目骨架与状态

/webnovel-plan
    -> 节拍表
    -> 时间线
    -> 结构化详细大纲（新增节点字段）

/webnovel-write
    -> Step 0.5 轻量节点预检
    -> Step 1 context-agent 组装写作包
    -> Step 2A writer 按节点扩写
    -> Step 3 review agents
    -> Step 5 data-agent 持久化覆盖与偏差
```

## Skills 视角实施方案

### 1. `webnovel-init`

定位：保留，不做大改。

职责：

- 初始化 `.webnovel/state.json`
- 初始化 `index.db / vectors.db`
- 初始化 `大纲/`、`设定集/`、摘要目录等骨架

建议新增但不强制：

- 为后续结构化章纲预留约定说明
- 为 `index.db` 预留结构化章纲缓存或索引的升级入口

### 2. `webnovel-plan`

定位：本次改造的主战场。

目标：把现有“详细大纲”升级成“结构化详细大纲”。

现有输出保留：

- `大纲/第{volume_id}卷-节拍表.md`
- `大纲/第{volume_id}卷-时间线.md`
- `大纲/第{volume_id}卷-详细大纲.md`

每章新增字段：

- `章节起点（CBN）`
- `推进节点（CPNs）`
- `章节终点（CEN）`
- `必须覆盖节点`
- `本章禁区`

节点格式建议：

`主体 | 动作/变化 | 对象/结果`

示例：

- `萧炎 | 抵达 | 迦南学院入口`
- `萧炎 | 展示 | 异火控制力`
- `药老 | 对萧炎产生 | 明确兴趣`

节点数量约束：

- `1 个 CBN`
- `2-4 个 CPN`
- `1 个 CEN`

必须覆盖规则：

- 每章必须覆盖节点最多 `4` 个
- 建议为：`CBN + CEN + 1~2 个核心 CPN`

章间衔接规则：

- 相邻章节 `CEN -> 下一章 CBN` 必须逻辑承接
- 若为时间跳转章，需在时间字段中明确说明

本章禁区规则：

- 不超过 `5` 条
- 只写硬禁区，不写风格建议

批次建议：

- 默认 `10章/批`
- 复杂题材 `8章/批`
- 简单升级流上限 `12章/批`

不建议：

- 再单独新增常规 `/webnovel-structure`
- 在 `plan` 之外再维护一份平行节点文件作为主数据源

### 3. `webnovel-write`

定位：保留为唯一主写作入口。

建议流程：

1. `Step 0.5` 轻量节点预检
2. `Step 1` `context-agent` 读取结构化章纲、状态和记忆，组装写作包
3. `Step 2A` writer 按 `CBN -> CPNs -> CEN` 扩写正文
4. `Step 3` review agents 执行结构覆盖与设定一致性检查
5. `Step 5` `data-agent` 持久化覆盖结果与偏差说明

新增 Step 0.5 的边界：

- 只检查主角或 POV 角色相关节点
- 第一版仅检查地点、境界/实力层级
- 仅附加警告，不阻断流程
- 不做复杂关系推理或自动重规划

### 4. `webnovel-review`

定位：保留，主要用于区间复盘和独立质量检查。

建议增强：

- 支持读取结构化章纲中的节点字段
- 支持基于章节范围回看 `plan vs actual` 偏移趋势

## Agents 视角实施方案

### 1. `context-agent`

定位：保留，增强为“结构化章纲聚合器”。

新增读取：

- `CBN`
- `CPNs`
- `CEN`
- `必须覆盖节点`
- `本章禁区`

新增输出板块：

- `情节结构`
  - `章节起点`
  - `推进节点`
  - `章节终点`
  - `必须覆盖节点`
  - `本章禁区`

Context Contract 新增字段：

- `plot_structure`
  - `cbn`
  - `cpns`
  - `cen`
  - `mandatory_nodes`
  - `prohibitions`

Step 2A 节拍映射：

- 有节点时：`CBN触发 -> CPN推进 -> CPN受阻/变化 -> CEN收束 -> 章末钩子`
- 无节点时：保持旧节拍

红线新增：

- 情节结构与任务书方向冲突

边界：

- 不生成节点
- 不修改节点
- 只负责读取、聚合、压缩成写作包

### 2. `plot-node-agent`

当前判断：第一阶段不作为必须组件。

原因：

- 既然决定把结构前移到 `plan`
- 那 `CBN/CPN/CEN` 的主产物应由 `plan` 直接生成
- 不需要在 `write` 阶段再新增重量级 agent 重复规划

保留可能性：

- 若后续发现章纲与正文脱节严重
- 再考虑引入轻量 `plot-node-agent`
- 只做写前局部修正，不做整章重规划

### 3. `continuity-checker`

定位：负责“结构覆盖”和“事件承接”。

新增检查：

1. `CBN 承接`
2. `CEN 落地`
3. `必须节点覆盖`
4. `可选节点覆盖（仅统计）`

输出：

- 节点覆盖表
- 覆盖评级：`A / B / C / F`

成功标准：

- 有节点时，覆盖评级至少 `B`

边界：

- 不判断设定是否越界
- 不判断禁区是否违背世界规则
- 只判断“写到了没有、接顺了没有、收住了没有”

### 4. `consistency-checker`

定位：负责“结构与设定冲突”。

新增检查：

1. 是否违反 `本章禁区`
2. 正文开头方向是否与 `CBN` 冲突
3. 正文结尾方向是否与 `CEN` 冲突
4. 关键节点对应的能力、身份、地点是否违背设定

严重度建议：

- 禁区违反：`high`
- `CEN` 方向冲突：`medium`
- `CBN` 方向冲突：`medium`

边界：

- 不负责覆盖率评级
- 不与 `continuity-checker` 重叠

### 5. `ooc-checker`

定位：保留。

增强方式：

- 读取更结构化的角色状态上下文
- 结合当前章的节点、角色行为红线和本章变化判断 OOC 风险

### 6. `reader-pull-checker / high-point-checker / pacing-checker`

定位：保留，但执行层收口。

建议：

- 默认写作流程强制启用：
  - `consistency-checker`
  - `continuity-checker`
  - `ooc-checker`
- 其余按题材、章节类型或区间复盘按需启用

原因：

- 新架构已经把部分“晚审”前移到 `plan`
- 再全量六并发常驻会过重

### 7. `data-agent`

定位：从“主判断者”改成“持久化与偏差记录器”。

继续保留：

- 实体抽取
- 状态变更
- 关系更新
- 摘要生成
- `memory facts`
- 向量切片

新增 Step 5B：

- 写入 `plot_coverage`
- 写入 `plan_deviation_note`

关键规则：

- `data-agent` 不自己重复做完整覆盖判断
- 优先消费 `continuity-checker` 与 `consistency-checker` 的结果，再写入 `chapter_meta`

推荐写入结构：

```json
{
  "plot_coverage": {
    "cbn_covered": true,
    "cen_covered": true,
    "mandatory_hit_rate": 1.0,
    "coverage_grade": "A",
    "prohibitions_violated": []
  },
  "plan_deviation_note": ""
}
```

填写规则：

- `mandatory_hit_rate < 0.8` 时必须填写 `plan_deviation_note`
- 存在禁区违反时必须填写 `plan_deviation_note`

边界：

- 不重规划后续章纲
- 不做复杂 SVO 主链重建
- 不代替 review

## 实施顺序

### Phase 1：最小闭环

1. `skills/webnovel-plan/SKILL.md`
2. `agents/context-agent.md`
3. `skills/webnovel-write/SKILL.md`
4. `agents/continuity-checker.md`
5. `agents/consistency-checker.md`
6. `agents/data-agent.md`

原因：

- 所有下游都依赖 `plan` 的新字段
- 其余模块都只是消费这些字段

### Phase 2：轻量状态增强

1. 在 `index.db` 中补充结构化章纲缓存或索引
2. 为 `context-agent` 增加“最近实际承接摘要”读取
3. 为 `review` 增加区间级偏移复盘

### Phase 3：按需局部修正

1. 若出现大量“章纲和正文脱节”
2. 再评估是否引入轻量 `plot-node-agent`
3. 仅做写前局部修正，不做完整重规划

## 验证方案

1. **结构化章纲验证**
   - 执行 `/webnovel-plan`
   - 确认详细大纲新增：
     - `CBN`
     - `CPNs`
     - `CEN`
     - `必须覆盖节点`
     - `本章禁区`

2. **写作包验证**
   - 执行 `/webnovel-write`
   - 确认 `context-agent` 输出包含“情节结构”板块

3. **审查验证**
   - 确认 `continuity-checker` 输出节点覆盖评级
   - 确认 `consistency-checker` 输出禁区/方向冲突检查

4. **数据回写验证**
   - 确认 `chapter_meta` 写入 `plot_coverage`
   - 确认偏差时有 `plan_deviation_note`

5. **向后兼容验证**
   - 用旧章纲执行 `/webnovel-write`
   - 全流程不阻断、不报错

## 最终判断

这版方案的重点不是“多加一个系统层”，而是：

- 让 `plan` 产出更可执行的章纲
- 让 `context-agent` 成为结构化章纲聚合器
- 让 `review` 围绕节点覆盖与结构冲突形成清晰分工
- 让 `data-agent` 成为持久化和偏差记录器

这条路线既吸收了 `STORYTELLER` 的核心思想，又避免了额外主流程和重复组件的膨胀。
