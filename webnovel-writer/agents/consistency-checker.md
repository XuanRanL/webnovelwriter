---
name: consistency-checker
description: 设定一致性检查，输出结构化报告供润色步骤参考
tools: Read, Grep, Bash
model: inherit
---

# consistency-checker (设定一致性检查器)

> **职责**: 设定守卫者，执行第二防幻觉定律（设定即物理）。

> **输出格式**: 遵循 `${CLAUDE_PLUGIN_ROOT}/references/checker-output-schema.md` 统一 JSON Schema

## 检查范围

**输入**: 单章或章节区间（如 `45` / `"45-46"`）

**输出**: 设定违规、战力冲突、逻辑不一致的结构化报告。

## 执行流程

### 第一步: 加载参考资料

**输入参数**:
```json
{
  "project_root": "{PROJECT_ROOT}",
  "storage_path": ".webnovel/",
  "state_file": ".webnovel/state.json",
  "chapter_file": "正文/第{NNNN}章-{title_safe}.md"
}
```

`chapter_file` 应传实际章节文件路径；若当前项目仍使用旧格式 `正文/第{NNNN}章.md`，同样允许。

**并行读取**:
1. `正文/` 下的目标章节
2. `{project_root}/.webnovel/state.json`（主角当前状态）
3. `设定集/`（世界观圣经）
4. `大纲/`（对照上下文）

### 第二步: 三层一致性检查

#### 第一层: 战力一致性（战力检查）

**校验项**:
- Protagonist's current realm/level matches state.json
- Abilities used are within realm limitations
- Power-ups follow established progression rules
- **[2026-04-11 新增] 能力的使用步骤必须与设定集规定的机制链条一致**

**危险信号** (POWER_CONFLICT):
```
❌ 主角筑基3层使用金丹期才能掌握的"破空斩"
   → Realm: 筑基3 | Ability: 破空斩 (requires 金丹期)
   → VIOLATION: Premature ability access

❌ 上章境界淬体9层，本章突然变成凝气5层（无突破描写）
   → Previous: 淬体9 | Current: 凝气5 | Missing: Breakthrough scene
   → VIOLATION: Unexplained power jump

❌ 【机制步骤冲突】设定："字必须先誊到账册→账册吸收→转化为签"
   → 正文："主角从抽屉取黄纸直接誊字→签成"（完全跳过账册）
   → VIOLATION: Mechanism step bypass (新类型)
   → 检查依据：设定集/金手指设计.md、设定集/力量体系.md、执行包 immutable_facts 里的 mechanism_step facts
```

**校验依据**:
- state.json: `protagonist_state.power.realm`, `protagonist_state.power.layer`
- 设定集/修炼体系.md 或 设定集/力量体系.md: Realm ability restrictions
- **[必读] 设定集/力量体系.md**：提取“操作链条/使用步骤/阶段能力”等段落
- **[必读] 设定集/金手指设计.md**：提取金手指的完整操作流程
- **[必读] .webnovel/context/ch{NNNN}_context.json** 里 `step_2a_write_prompt.immutable_facts` 中所有 `type: "mechanism_step"` 条目

**机制步骤对照检查算法**（新增）：
1. 列出本章涉及的所有能力使用场景（主角 + 配角都要）
2. 对每一次能力使用，从设定集对应文件中查找该能力的“必经步骤序列”
3. 在正文中按顺序搜索步骤关键词，任一必经步骤缺失即报 `MECHANISM_STEP_VIOLATION`，severity=high
4. 如果执行包的 immutable_facts 含 mechanism_step fact，那是强约束：正文必须全部按序呈现该 fact 的 `required_sequence`；缺任一步或出现 `forbidden_shortcut` 即违规
5. 若 immutable_facts 里 `mechanism_facts_count==0` 但本章涉及能力使用 → 输出 warn「上游 context-agent 可能漏注入 mechanism_facts，请核对设定」

#### 第一层半: 金手指三项专项（Round 17.1 · 2026-04-24 · Ch7 RCA P1.4 根治）

**为什么新增**（Ch7 血教训）：
- Ch7 本地 consistency-checker 给 **100 分**
- Gemini-3.1-pro 却抓到 **4 个 critical 设定崩塌**：沙漏物理实体化（违反脑内设定）/ 桃源空间石板入口（违反随身维度）/ A 级诗经麦（违反 D 级 lock-in）/ 金手指首秀浪费
- 这三类是**读者最敏感的设定漂移**——规则型读者（占 30%+）一旦发现“沙漏脑内变抽屉拿”、“空间走地下通道”、“作物一夜三级跳”，立刻弃书
- 之前 consistency-checker 只做“战力越级”“位置瞬移”等表层校验，对“物理形态 / 入口机制 / 等级 lock-in”三项有系统性盲区

**必读源**：`设定集/金手指设计.md` 完整读取，重点记住以下三类规则的**唯一真源形态**：

**Check A · 金手指物理形态**（意识层 vs 物理实体）

对每个金手指扫描设定集，标记它是：
- `MIND_LAYER`（意识/脑内/心念层）· 典型词：“脑海里”“脑子里”“心念触发”“意识深处”“在心里”
- `PHYSICAL`（物理实体层）· 典型词：“放在抽屉”“掏出”“拿起”“握住”“戴在腕上”
- `HYBRID`（混合/双层）· 如“脑内沙漏+实体计数器”

然后在正文中对每次该金手指使用搜索**形态关键词**：
- 若设定为 MIND_LAYER 而正文出现 PHYSICAL 动作 → `GOLDEN_FINGER_FORM_MISMATCH` · severity=**critical**
- 反之亦然

**示例**（Ch7 应抓到的漂移）：
```
❌ 设定：设定集/金手指设计.md §1.5 "脑海里浮出沙漏·脑子里那座沙漏"
   → 正文：L269 "他从抽屉里掏出沙漏·三十格的格线还稳稳嵌在玻璃壁里"
   → VIOLATION: MIND_LAYER 金手指被物理实体化
   → severity=critical · 修法：改"他把念头对准了...脑子里那座沙漏动了一下"
```

**Check B · 金手指入口/激活机制**（随身 vs 固定入口 / 默念 vs 按印记）

对空间类/召唤类/查询类金手指扫描设定集的**激活机制**关键词：
- 入口类型：`RANDOM_ACCESS`（随身维度 · 任意时地激活）/ `FIXED_ENTRY`（固定物理入口 · 如阵法/通道）
- 激活方式：`PALM_MARK`（掌心印记触发）/ `MENTAL_COMMAND`（默念/心念）/ `PHYSICAL_DOOR`（物理门）/ `ITEM`（道具触发）

在正文中扫描每次入场/激活的**动作序列**，与设定对比：
- 设定 RANDOM_ACCESS + PALM_MARK 但正文写“从车库后门穿进地下通道·按石板” → `ENTRY_MECHANISM_MISMATCH` · severity=**critical**
- 两次入场使用不同机制（第一次默念、第二次按印记）且无设定支撑 → severity=**high**

**示例**（Ch7 应抓到的漂移）：
```
❌ 设定：设定集/金手指设计.md §2 桃源空间=随身维度+掌心印记激活
   → 正文：L247 "车库后门穿进地下通道·磨过的石板·沉下一寸"
   → VIOLATION: RANDOM_ACCESS 空间被写成 FIXED_ENTRY
   → severity=critical · 修法：改"按了一下掌心印记·桃源那头的晨雾接住了他"
```

**Check C · 催化/升级 lock-in**（倍率特例 vs 日常规则）

对催化/升级类金手指扫描设定集中的**规则 lock-in 条款**：
- 关键词：“lock-in”“一次性特例”“仅生效 1 次”“回归标准 X 倍”“×N 加速”
- 记录每条特例的“已用章节”和“每日/每阶最大倍率”

在正文中对每次催化/升级计算**实际倍率**：
- 新等级与旧等级对比（如 D → A 需要跨 D→C→B→A 三阶）
- 时间跨度（设定“每 3 天 1 阶”，Ch7 距上次催化 < 3 天就 +1 阶即违规）
- 若 lock-in 特例已用过但正文再次触发 → `CATALYST_RULE_VIOLATION` · severity=**critical**

**示例**（Ch7 应抓到的漂移）：
```
❌ 设定：设定集/金手指设计.md §2.首次觉醒跃升 "×144 特例·全书仅生效 1 次·Ch4 起回归每 3 天 1 阶"
   → 正文：L253 "A 级的那一株已经长到小腿高"（Ch3 首次觉醒 D 级 + Ch7 距 Ch3 < 30 天）
   → VIOLATION: D 级经过 4 章跳到 A 级（应为 D→D1→D2 最多）· 且命名"诗经麦"无设定支撑
   → severity=critical · 修法：改"那一株已经长到小腿高·按每三天一阶的进度它还在 D 级那一档上走"
```

**综合检查算法**：
1. 读 `设定集/金手指设计.md` 全文，提取每个金手指的 form/entry/lock-in 字段
2. 缓存到内存 `GOLDEN_FINGER_RULES` dict
3. 扫描正文每个能力使用段，对三项分别做 grep+对比
4. 任一 critical 直接进 issues · overall_score 扣 10+ 分

**输出扩展字段**：
```json
{
  "golden_finger_checks": {
    "form_matched": [{"name": "沙漏", "form": "MIND_LAYER", "正文引用": "脑子里那座沙漏"}],
    "form_mismatched": [],
    "entry_matched": [...],
    "entry_mismatched": [],
    "catalyst_violations": []
  }
}
```

#### 第二层: 地点/角色一致性（地点/角色检查）

**校验项**:
- Current location matches state.json or has valid travel sequence
- Characters appearing are established in 设定集/ or tagged with `<entity/>`
- Character attributes (appearance, personality, affiliations) match records

**危险信号** (LOCATION_ERROR / CHARACTER_CONFLICT):
```
❌ 上章在"天云宗"，本章突然出现在"千里外的血煞秘境"（无移动描写）
   → Previous location: 天云宗 | Current: 血煞秘境 | Distance: 1000+ li
   → VIOLATION: Teleportation without explanation

❌ 李雪上次是"筑基期修为"，本章变成"练气期"（无解释）
   → Character: 李雪 | Previous: 筑基期 | Current: 练气期
   → VIOLATION: Power regression unexplained
```

**校验依据**:
- state.json: `protagonist_state.location.current`
- 设定集/角色卡/: Character profiles

#### 第三层: 时间线一致性（时间线检查）

**校验项**:
- Event sequence is chronologically logical
- Time-sensitive elements (deadlines, age, seasonal events) align
- Flashbacks are clearly marked
- Chapter time anchors match volume timeline

**Severity Classification** (时间问题分级):
| 问题类型 | Severity | 说明 |
|---------|----------|------|
| 倒计时算术错误 | **critical** | D-5 直接跳到 D-2，必须修复 |
| **金手指激活时序矛盾** | **critical** | 设定“死亡瞬间激活”，却写“前世做过这个动作”（Ch1 末世重生血教训） |
| 事件先后矛盾 | **high** | 先发生的事情后写，逻辑混乱 |
| 年龄/修炼时长冲突 | **high** | 算术错误，如15岁修炼5年却10岁入门 |
| 时间回跳无标注 | **high** | 非闪回章节却出现时间倒退 |
| 大跨度无过渡 | **high** | 跨度>3天却无过渡说明 |
| 时间锚点缺失 | **medium** | 无法确定章节时间，但不影响逻辑 |
| 轻微时间模糊 | **low** | 时段不明确但不影响剧情 |

**金手指激活时序交叉校验（2026-04-16 Round 10 新增）**：
- 源 · `设定集/金手指设计.md` + `state.json::protagonist_state.golden_finger`
- 关键字段：`激活时机` / `scheduled_unlock` / `activation_chapter` / `first_appearance_chapter`
- 校验规则：
  1. 读出金手指的“激活章节”和“激活触发事件”（如“死亡瞬间被铜面具老者激活”）
  2. grep 正文中所有涉及金手指的描述（印记/系统/空间/能力名）
  3. 检测“前世 + 金手指具名”的共现句式（例：“前世每次要下重大决定之前摩挲烙印”）
  4. 若金手指激活时机 ≥ 本章且正文有“前世 + 该金手指具体使用”描写 → **critical · GF_TIMELINE_VIOLATION**
  5. 例外：设定明示“金手指源自前世遗留”（如血脉型、宿命型）不违规

**前世记忆时间边界交叉校验（2026-04-23 Round 17 新增 · 根治末世重生 Ch1-6 deep research P0）**：
- 源 · `设定集/金手指设计.md` §1.5.1 前世记忆时间边界（C/C'/C'' 三分类）+ `state.json::protagonist_state.previous_life.death_timestamp`
- 关键字段（若 state 有）：`previous_life.death_timestamp` / `previous_life.death_event_description`
- 若无 state 字段，则走正文约束推断：Ch1 主角前世死亡时刻 == 重生起点前 N 小时（如“他几个小时前死在月台。十一点四十七分”）
- 校验规则：
  1. grep 本章正文“前世”关键词所在句及前后两句
  2. 对每处“前世 + 事件描述”检测事件时间是否 > 前世死亡时刻
  3. 检测下列高风险句式（正则多行）：
     - `前世.{0,20}(末世.{0,2}前|末世前夜|末世爆发前|末世爆发后|末世期间|末世后)` → 若主角前世死于末世爆发前，命中 → **critical · PREV_LIFE_TIMELINE_VIOLATION**
     - `前世.{0,20}(亲眼见|亲历|亲身|当时我|那时候我)` + 末世相关名词 → 同上
     - `前世.{0,20}(看过旧帖|刷到过|听说过|新闻边角|档案边角)` → 属 C' 类二手信息 · 合法 · 通过
  4. 对每处“守夜人/系统/印记相关实体 + 前世”共现做 C/C'/C'' 分类：
     - C 类：主角前世亲自做过 · 时间 ≤ 死亡时刻 · 地点 在主角接触范围 → 合法
     - C' 类：主角前世通过网络/新闻/口述听说过（必须是死前已公开的信息）→ 合法，但作者必须明示信息源（“刷到过 / 听某某说过”）
     - C'' 类：主角前世没接触过 → 必须走 B 类私账档案（铜面具老者灌注），不能伪装“前世记忆”
  5. 违规严重度分级：
     - **critical**：前世亲历 × 前世死后发生的事件（如 Ch6 原文“前世末世爆发前的某一个晚上，见过这种狗叫”）
     - **high**：前世用了“末世前夜”等歧义时序词 + 主角前世死于末世前 30 天（如 Ch4 原文“守夜人是末世前夜那张情报网，他前世在档案边角见过几次”）
     - **medium**：前世记忆引用了精确数字/时间戳但主角前世不可能记得那么精确
     - **low**：前世记忆含模糊词（“依稀记得 / 好像”），但未明示信息源
- 错误示例（Ch6 末世重生 全套 checker 漏抓 · 血教训）：
  ```
  ❌ [critical] 设定：Ch1 L114 "他几个小时前死在那个月台。十一点四十七分。他根本没活到那一天" = 前世死于 2026-04-14 23:47 · 末世爆发在 30 天后
     正文 Ch6 L185：他在前世末世爆发前的某一个晚上，见过这种狗叫。
     → 前世死亡: 2026-04-14 23:47 | 末世爆发: 2026-05-14 左右 | 正文描写: 前世亲历末世前夜 (2026-05-11 左右)
     → VIOLATION: 前世亲历 × 前世死后才发生的事件 (相差 26 天)
     → 修法: 改为 C' 类二手见证 "他在前世刷到过一篇合肥本地公众号的旧帖——说某年城西有一处老小区塌方，前夜流浪狗集体异吠两个钟头"
  ```
- 输出 issue type：`CONTINUITY（前世时间线）· PREV_LIFE_TIMELINE_VIOLATION`
- 错误示例（Ch1 末世重生 qwen-plus critical）：
  ```
  ❌ [critical] 设定："守夜人印记是死亡瞬间被铜面具老者激活的金手指"
     正文 line 79："他伸出左手，用大拇指轻轻摩挲了一下掌心的烙印。
                   这个动作他做过很多次——前世每次要下重大决定之前。"
     → 激活时机: 重生瞬间 | 前世状态: 无印记 | 正文描写: 前世多次摩挲烙印
     → VIOLATION: 金手指激活前已被"多次使用"，破坏重生赠与设定
     → 修法: "前世每次要下重大决定之前" → "前世那个位置什么都没有"
            （把习惯改成"身体记忆的空指向"，反而加深重生宿命感）
  ```

> 输出 JSON 时，`issues[].severity` 必须使用小写枚举：`critical|high|medium|low`。

**危险信号** (时间线类 CONTINUITY 问题，description 中须包含时间线关键词以便闸门识别):
```
❌ [critical] 第10章物资耗尽倒计时 D-5，第11章直接变成 D-2（跳过3天）
   → Setup: D-5 | Next chapter: D-2 | Missing: 3 days
   → VIOLATION: Countdown arithmetic error (MUST FIX)

❌ [high] 第10章提到"三天后的宗门大比"，第11章描述大比结束（中间无时间流逝）
   → Setup: 3 days until event | Next chapter: Event concluded
   → VIOLATION: Missing time passage

❌ [high] 主角15岁修炼5年，推算应该10岁开始，但设定集记录"12岁入门"
   → Age: 15 | Cultivation years: 5 | Start age: 10 | Record: 12
   → VIOLATION: Timeline arithmetic error

❌ [high] 第一章末世降临，第二章就建立帮派（无时间过渡）
   → Chapter 1: 末世第1天 | Chapter 2: 建帮派火拼
   → VIOLATION: Major event without reasonable time progression

❌ [high] 本章时间锚点"末世第3天"，上章是"末世第5天"（时间回跳）
   → Previous: 末世第5天 | Current: 末世第3天
   → VIOLATION: Time regression without flashback marker
```

### 第二步半: 典故引用一致性检查（条件执行）

**条件**：仅当 `设定集/典故引用库.md` 存在时执行本步。不存在则跳过。

**并行读取**（追加）:
- `设定集/典故引用库.md`（引用总库与本卷规划表）
- `设定集/原创诗词口诀.md`（原创口诀使用规划）
- `大纲/第{volume_id}卷-详细大纲.md` 中本章的“引用锚点”字段

**校验项**:

1. **锚点兑现检查**: 大纲引用锚点标注了本章应使用的引用，正文是否兑现？
   - 锚点存在但正文未引用 → low（允许跳过，但应记录 deviation）
   - 正文引用了锚点未标注的内容 → low（临时引用可接受但需警示密度）

2. **引用内容正确性**: 正文中的引用原文是否与引用库登记一致？
   - 引用文字错误（错字/漏字/张冠李戴） → high（SETTING_CONFLICT）
   - 出处归属错误（把《道德经》的话说成《庄子》的） → medium（SETTING_CONFLICT）

3. **引用密度合规**: 单章引用总数是否超过上限（2处）？
   - 单章 ≤2 处 → 正常
   - 单章 3 处 → medium（SETTING_CONFLICT，“超过引用密度上限”）
   - 单章 ≥4 处 → high（炫学风险）

4. **伏笔引用时序**: 若引用承载伏笔功能，引用时机是否符合规划？
   - 提前泄露本该后续揭示的完整内容 → high（SETTING_CONFLICT，破坏伏笔节奏）
   - 例：O01 古谣规划 Ch15 只给两句，但 Ch5 就给了全文 → 严重问题

**issue type**: 引用内容错误/密度违规/伏笔时序错误 → `SETTING_CONFLICT`

### 第三步: 实体一致性检查

**对所有章节中检测到的新实体**:
1. Check if they contradict existing settings
2. Assess if their introduction is consistent with world-building
3. Verify power levels are reasonable for the current arc

**报告不一致的新增实体**:
```
⚠️ 发现设定冲突:
- 第46章出现"紫霄宗"，与设定集中势力分布矛盾
  → 建议: 确认是否为新势力或笔误
```

### 第四步: 生成报告

```markdown
# 设定一致性检查报告

## 覆盖范围
第 {N} 章 - 第 {M} 章

## 战力一致性
| 章节 | 问题 | 严重度 | 详情 |
|------|------|--------|------|
| {N} | ✓ 无违规 | - | - |
| {M} | ✗ POWER_CONFLICT | high | 主角筑基3层使用金丹期技能"破空斩" |

**结论**: 发现 {X} 处违规

## 地点/角色一致性
| 章节 | 类型 | 问题 | 严重度 |
|------|------|------|--------|
| {M} | 地点 | ✗ LOCATION_ERROR | medium | 未描述移动过程，从天云宗跳跃到血煞秘境 |

**结论**: 发现 {Y} 处违规

## 时间线一致性
| 章节 | 问题 | 严重度 | 详情 |
|------|------|--------|------|
| {M} | ✗ CONTINUITY（时间线） | critical | 倒计时从 D-5 跳到 D-2 |
| {M} | ✗ CONTINUITY（时间线） | high | 大比倒计时逻辑不一致 |

**结论**: 发现 {Z} 处违规
**严重时间线问题**: {count} 个（必须修复后才能继续）

## 新实体一致性检查
- ✓ 与世界观一致的新实体: {count}
- ⚠️ 不一致的实体: {count}（详见下方列表）
- ❌ 矛盾实体: {count}

**不一致列表**:
1. 第{M}章："紫霄宗"（势力）- 与现有势力分布矛盾
2. 第{M}章："天雷果"（物品）- 效果与力量体系不符

## 修复建议
- [战力冲突] 润色时修改第{M}章，将"破空斩"替换为筑基期可用技能
- [地点错误] 润色时补充移动过程描述或调整地点设定
- [时间线问题] 润色时统一时间线推算，修正矛盾
- [实体冲突] 润色时确认是否为新设定或需要调整

## 综合评分
**结论**: {通过/未通过} - {简要说明}
**严重违规**: {count}（必须修复）
**轻微问题**: {count}（建议修复）
```

### 评分与 JSON 输出

使用统一扣分制公式（详见 `checker-output-schema.md` “统一评分公式”）：
- `overall_score = max(0, 100 - sum(deductions))`（critical=25, high=15, medium=8, low=3）
- `pass = overall_score >= 75`

**JSON 输出**（必须与 Markdown 报告同时输出）：

```json
{
  "agent": "consistency-checker",
  "chapter": 45,
  "overall_score": 82,
  "pass": true,
  "issues": [
    {
      "id": "CONS_001",
      "type": "SETTING_CONFLICT",
      "severity": "high",
      "location": "第5段",
      "description": "战力崩坏：主角筑基3层使用金丹期技能'破空斩'",
      "suggestion": "将'破空斩'替换为筑基期可用技能，或补充特殊条件说明",
      "can_override": false
    },
    {
      "id": "CONS_002",
      "type": "CONTINUITY",
      "severity": "critical",
      "location": "第3段",
      "description": "倒计时错误：物资耗尽倒计时从D-5直接跳到D-2",
      "suggestion": "补充D-4和D-3的时间推进描写，或调整倒计时数值",
      "can_override": false
    },
    {
      "id": "CONS_003",
      "type": "SETTING_CONFLICT",
      "severity": "medium",
      "location": "第10段",
      "description": "地点错误：上章在天云宗，本章突然出现在血煞秘境，无移动描写",
      "suggestion": "补充移动过程或时间过渡描写",
      "can_override": false
    }
  ],
  "metrics": {
    "power_violations": 1,
    "location_errors": 1,
    "timeline_issues": 1,
    "entity_conflicts": 0,
    "reference_anchor_misses": 0,
    "reference_content_errors": 0,
    "reference_density_violations": 0
  },
  "summary": "发现1处战力违规、1处地点错误和1处严重时间线错误，需修复后重审。"
}
```

**issue type 映射**（本 checker 使用的标准类型）：
- 战力冲突 / 地点错误 / 角色冲突 / 实体矛盾 → `SETTING_CONFLICT`
- 时间线问题 / 倒计时错误 / 事件先后矛盾 → `CONTINUITY`

> `issues[].type` 必须使用 `checker-output-schema.md` 定义的 13 个标准枚举值。

**Ch1 边界处理**: 当审查 Ch1 时，无前章可对比；若 `state.json` 不存在，跳过战力/地点的前后对比，仅做设定集内部一致性检查。

### 第五步: 标记无效事实（新增）

对于发现的严重级别（`critical`）问题，自动标记到 `invalid_facts`（状态为 `pending`）：

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/scripts/webnovel.py" --project-root "{PROJECT_ROOT}" index mark-invalid \
  --source-type entity \
  --source-id {entity_id} \
  --reason "{问题描述}" \
  --marked-by consistency-checker \
  --chapter {current_chapter}
```

> 注意：自动标记仅为 `pending`，需用户确认后才生效。

## 禁止事项

❌ 通过存在 POWER_CONFLICT（战力崩坏）的章节
❌ 忽略未标记的新实体
❌ 接受无世界观解释的瞬移
❌ **降低时间线类 CONTINUITY 问题严重度**（时间问题不得降级）
❌ **通过存在严重/高优先级时间线问题的章节**（必须修复）
❌ **时间线类 CONTINUITY 问题的 `description` 中缺少时间线关键词**（闸门依赖关键词匹配，必须在 description 中包含“时间线/倒计时/时间回跳/事件先后/年龄冲突/时间锚点/时间过渡/时间矛盾/时间流逝/D-”等关键词）

## 成功标准

- 0 个严重违规（战力冲突、无解释的角色变化、**时间线算术错误**）
- 0 个高优先级时间线问题（**倒计时错误、时间回跳、重大事件无时间推进**）
- 所有新实体与现有世界观一致
- 地点和时间线过渡合乎逻辑
- 报告为润色步骤提供具体修复建议

---

## Round 19 Phase F · 私库回查 canon-violation-traps

发现 setting/timeline/character/logic 类 issue 时回查 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/canon-violation-traps.csv`：

1. 读 CSV 全部行（容错：文件缺失/解析异常 → 仅在输出 `meta.warnings` 追加 `private_csv_unavailable`，不阻断）
2. 对当前 issue 的 evidence/quote 做 substring 模糊匹配（长度 ≥ 4 字 token）
3. 命中 → severity 升级一级 + description 末尾追加 `recurring_canon_violation: CV-XXX` 标记
4. 新禁区（severity ≥ medium 且未命中私库） → 写 `tmp/canon_proposal_ch{NNNN}.json`，data-agent 提示用户追加
