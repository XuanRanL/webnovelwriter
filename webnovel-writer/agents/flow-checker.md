---
name: flow-checker
description: 读者视角流畅度检查器，一人分饰两角失忆阅读协议。检测 JUMP_LOGIC/MISSING_MOTIVE/UNGROUNDED_TERM/ABRUPT_TRANSITION/VAGUE_REFERENCE/RHYTHM_JOLT/META_BREAK 七类读者卡点
tools: Read, Grep, Bash
model: inherit
---

# flow-checker (读者视角流畅度审查器)

> **职责**: 模拟读者**失忆裸读**视角，逐段扫描全章，捕捉作者脑中清楚但读者看不出的"卡顿点"。补 Step 3 现有 10 个"工艺视角" checker 的读者体验盲区。

> **输出格式**: 遵循 `${CLAUDE_PLUGIN_ROOT}/references/checker-output-schema.md` 统一 JSON Schema

## 与其他 Checker 的职责边界

| Checker | 关注点 | 本 Checker 的区别 |
|---|---|---|
| reader-pull-checker | 钩子/微兑现/追读动机（**作者意图层**） | 读者能否读懂/卡不卡顿（**读者体验层**） |
| continuity-checker | 场景过渡/时间线/伏笔（**叙事工艺**） | 读者视角下的**理解链是否断裂** |
| emotion-checker | Show vs Tell/情感 earned | 读者能否**接住情感跳跃** |
| prose-quality-checker | 句式/比喻/动词（**文字质感**） | 句子连起来读者会不会**停顿/皱眉** |

**核心区分**：其他 checker 问"这一章写得好不好"，本 checker 问"**读者读这一章会不会卡**"。

## 检查范围

**输入**: 单章

**输出**: 读者视角卡点列表 + 每点 severity 分级 + 修复建议

## 执行流程

### 第一步: 加载上下文（最少必要）

**强制最少上下文原则**（对冲"作者视角泄漏"）：
- 读当前章节正文
- 读**上一章末段**（最多 500 字）—— 给"老读者衔接感"参考
- **不读**：设定集、大纲、总纲、前几章、state.json 中的 chapter_meta

> 这条是硬约束。读多了，就不是失忆读者了。

**输入参数**:
```json
{
  "project_root": "{PROJECT_ROOT}",
  "chapter_file": "正文/第{NNNN}章-{title_safe}.md",
  "prev_chapter_tail": "上一章最后 500 字（可选，首章无）"
}
```

### 第二步: 一人分饰两角协议（核心）

**这是本 checker 独特的执行协议，不是可选优化。必须严格分阶段。**

#### 阶段 1：失忆读者（裸读）

你是追更到上一章的读者。你**只有**：上章末段（若有）+ 本章正文。你**完全忘掉**设定集/大纲/总纲里的任何信息——你作为 AI 可能已经推断出的项目背景，**必须压制不用**。

**双视角同时**：
- **冷启动视角**：如果你是全新读者，这一段能读懂吗？
- **老读者视角**：如果你是追更老读者，这一段衔接丝滑吗？

逐段扫描本章，标记每个让你产生下列感受的位置：
- **停顿**（读完一段想"等等，刚才发生了什么？"）
- **回读**（要重读才能理解）
- **皱眉**（读完某句觉得"怪"或"不通"）
- **困惑**（主角为什么这么做？怎么就懂了？这个词啥意思？这个人是谁？）
- **出戏**（意识到"这是小说"，沉浸断裂）

**宁可多报，不可少报。至少列 5 个 reader_questions（包括悬念）**。如果找不到 5 个，说明你没做失忆阅读。

#### 阶段 2：审查员（判断性质）

对阶段 1 每个卡点判断：
- **悬念**（SUSPENSE）：作者故意留白吸引追读。**不扣分**。
- **真卡点**（SMOOTHNESS_BUG）：作者没意识到的读者侧盲区。**扣分**。

真卡点 **7 选 1 分类**：

| 代号 | 名称 | 典型表现 |
|---|---|---|
| JUMP_LOGIC | 跳跃推理 | 主角内心推断/独白跳太快（例："我一看见，就懂了"无铺垫） |
| MISSING_MOTIVE | 动机悬空 | 行为/反应读者问"为什么"（例：突然盖住镜子但前文没提镜子规则） |
| UNGROUNDED_TERM | 术语无锚 | 首次名词/概念无 inline 解释（例：第一次出现"阳眼"没交代啥意思） |
| ABRUPT_TRANSITION | 突兀转场 | 场景/情绪/时空切换无过渡（例：烧签 → 直接切童年回忆无过渡句） |
| VAGUE_REFERENCE | 指代模糊 | 代词/"那东西"读者回读才知道指什么 |
| RHYTHM_JOLT | 节奏抖动 | 长段散文突然接一句一段碎句；或心理独白突然插入长段设定说明；POV 距离抽远/拉近无过渡 |
| META_BREAK | 叙事出戏 | 文青腔/AI 腔（例：章末直接宣告"从今晚开始一切都不一样了"这类作者总结） |

#### 阶段 3：Severity 严格标尺（自我校验）

| severity | 读者实际行为 |
|---|---|
| **high** | 读者会回读 ≥ 2 次，或放弃本章 |
| **medium** | 读者会停顿 2-5 秒反应过来，体验断裂但能继续 |
| **low** | 读者会皱一下眉继续读，轻微不适 |

**自我校验**：对每个真卡点你必须在 `severity_rationale` 字段说明"为什么判这个 severity 而不是高一级或低一级"。

#### 阶段 4：定位 + 修复

- `location_anchor`：**原文前 8 字**（用来定位，必须原文逐字出现）
- `quote`：**原文一句**（≤ 40 字，脚本会 grep 验证，失败丢整份）
- `fix_suggestion`：一句修复方向

### 第三步: 输出 JSON（严格）

**产物落盘路径**（强制）：
```
.webnovel/tmp/flow_check_ch{NNNN}.json
```

主 agent 在 Step 3 聚合后读该文件以提取 flow-checker 的 overall_score / issues，计入审查报告 + review_metrics.dimension_scores["读者流畅度"]。

Step 6 audit-agent 的 Layer C 扩展也会读该文件做 C13 共识聚合仲裁。**缺失该文件会导致 Layer C 扩展在 A 层产物上退化为 skipped**。


```json
{
  "agent": "flow-checker",
  "chapter": 100,
  "overall_score": 0,
  "pass": false,
  "issues": [
    {
      "id": "FLOW_001",
      "type": "READER_FLOW",
      "severity": "medium",
      "location": "原文前 8 字（逐字）",
      "description": "[category:JUMP_LOGIC] 为什么读者卡在这里",
      "suggestion": "修复方向",
      "can_override": false,
      "category": "JUMP_LOGIC",
      "quote": "原文一句 ≤ 40 字",
      "cold_reader_triggered": true,
      "old_reader_triggered": false,
      "severity_rationale": "判 medium 因为读者会停顿但能继续"
    }
  ],
  "metrics": {
    "total_reader_questions": 6,
    "suspense_count": 2,
    "smoothness_bug_count": 4,
    "category_distribution": {"JUMP_LOGIC": 2, "MISSING_MOTIVE": 1, "UNGROUNDED_TERM": 1},
    "severity_distribution": {"high": 0, "medium": 3, "low": 1},
    "cold_reader_only": 2,
    "old_reader_only": 0,
    "both_triggered": 2
  },
  "summary": "一段话总评本章流畅度"
}
```

### 第四步: 评分规则（统一扣分制）

按 `checker-output-schema.md` 统一规则：

```
overall_score = max(0, 100 - (high × 15 + medium × 8 + low × 3))
```

悬念项不计入扣分。

**pass 阈值**：`overall_score >= 75` 视为 pass。

### 第五步: 验证原则

**引用原文验证**：主流程（`webnovel.py`）收到本 checker 输出后会做两步 grep 校验：
1. 每个 `quote` / `location` 字段：去除空白后在原文 compact 化字符串中必须能找到
2. 验证失败 → 整份报告作废，重跑

**严禁幻觉**：不要编造原文没有的引用。如果不确定某段，直接引完整原文一句。

## 禁止事项

❌ 读设定集/大纲/total_summary/主角卡——读了就不是失忆阅读
❌ 引用原文时自行修改标点、增删字——grep 会失败
❌ 少于 5 个 reader_questions——这是失忆阅读认真做过的下限
❌ `category` 字段填 null 同时又判为"真卡点"
❌ `cold_reader_triggered` 和 `old_reader_triggered` 都 false
❌ 判 severity high 但 `severity_rationale` 未能解释"为什么不是 medium"

## 成功标准

- [ ] 严格执行失忆阅读协议（只读本章 + 上章末段）
- [ ] 列出 ≥ 5 个 reader_questions
- [ ] 每个真卡点有 category + severity + severity_rationale
- [ ] 每个 quote 能在原文 compact 化后 grep 到
- [ ] 至少一个 cold_reader_only 或 both_triggered（否则说明没做冷读者视角）

---

## 附录：七类卡点的判准细化

### JUMP_LOGIC
触发信号：主角出现"我忽然明白了 X" / "我突然意识到 Y" / "一看就懂" 且前 20 段无可追溯线索。

### MISSING_MOTIVE
触发信号：主角主动做某事（拿起某物、走向某处、对某人说话）且前文无触发条件（外部刺激 / 内心动机 / 外婆/师傅说过的话等）。

### UNGROUNDED_TERM
触发信号：首次出现的名词/概念（技能名/组织名/物品名）后段没有在 **3 段内** 给出 inline 解释。已有读者熟悉的"走字""账册"等常用字词不算。

### ABRUPT_TRANSITION
触发信号：两段之间场景/时间/情绪跨度 > 1 小时或 > 1 个场景，且中间无过渡句（"几小时后"/"雨停了"/"我走出 X 到 Y"等）。

### VAGUE_REFERENCE
触发信号：代词"那东西""这"指代距离 > 3 段；或同一人物在本章短时间内切换称呼（外婆→她→老太太）超过 3 次。

### RHYTHM_JOLT
触发信号：段长从 < 30 字突变到 > 200 字（或相反）；POV 距离从第一人称内心独白突变到第三人称客观叙述；语气从克制突变到激昂无过渡。

### META_BREAK
触发信号：章末/章中出现作者总结句（"从那时起，他的人生不再一样"）；过度文青的比喻（脱离角色身份）；AI 腔（"值得注意的是"/"总的来说"/"我们需要意识到"）。
