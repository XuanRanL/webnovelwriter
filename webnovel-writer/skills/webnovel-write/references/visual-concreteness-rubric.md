---
name: visual-concreteness-rubric
purpose: 画面感硬规则 · 视觉锚点 / 5+1 感官色谱 / 抽象动作改写
---

# 画面感 3 子规则（Round 19 Phase H）

> **核心 insight**：读者投诉“看不到画面”是网文头号差评。比“AI 味重”更直接的杀手投诉。本规则把“画面感”从综合感官评分细化成 3 项可硬扫的子规则。

## 子规则 1: 场景首句视觉锚点（critical）

每个新场景的**首句**必须含至少 1 项视觉锚点：

| 锚点类型 | 示例 |
|---|---|
| 光线 | 窗外的光斜斜地切过他的左肩。 |
| 空间 | 地下室只有三步深，墙在他左手边发凉。 |
| 物体 | 刀就摆在桌角，刀尖朝着她。 |

**禁止**：场景首句写心理活动 / 抽象状态 / 时间流逝 / 概括性描述。

判断“新场景”：

- 空行隔开 + 时间 / 地点切换标志（“次日清晨” / “三天后” / “他到了医院” / “回到家中”）
- 第一段也算“新场景首句”

扣分：每违例 -10 critical（直接 blocking 给 reader_critic）。

## 子规则 2: 5+1 感官色谱覆盖（high）

每章必须有以下感官覆盖：

| 感官 | 必到 | 示例 |
|---|---|---|
| 视觉（visual） | ✅ | 光 / 空间 / 物体 / 颜色 |
| 听觉（auditory） | ✅ | 声音 / 沉默 |
| 嗅觉（olfactory） | 至少 1 个 | 血腥味 / 消毒水味 / 雨后泥土 |
| 触觉（tactile） | 嗅或触至少 1 个 | 门把冰 / 衬衫粗 |
| 温度（thermal） | — | 风凉 / 阳光烫 |
| 味觉（gustatory） | — | 舌尖铁锈 / 口干 |
| +1 体感（kinesthetic） | — | 重心一沉 / 身体绷直 |

### 评分梯度

| 覆盖项数（视+听必到，其余至少 1 个） | 评分 |
|---|---|
| ≥ 4 项（视+听+嗅+触/温/味/体 中至少 1 个） | 100 |
| 3 项（视+听+ 嗅或触/温/味/体之一） | 80 |
| 2 项（仅视+听） | 60 |
| < 2 项 | 0（critical） |

### 末世重生历史命中

- Ch4 汽修厂段：视+听+触全有，嗅味缺（机油味未写）→ medium 命中
- Ch8 城市傍晚：视主导，听+嗅+触缺 → medium 命中
- Ch9 桃源空间二度入境：视+触有，嗅缺（“南雾/麦穗”应有谷子香未写）→ medium 命中

Phase H 起这类章节将自动 high warn → polish 必须补嗅觉。

## 子规则 3: 抽象动作触发改写（high）

下列抽象动作短语**必须**改为具象描写：

| 抽象动作 | 改写要求 | 示例 |
|---|---|---|
| 展开攻势 | 具体动作链 | 试探 / 突进 / 拨开 / 反手 |
| 陷入沉思 | 微动作 | 拧笔帽 / 摸下巴 / 看窗外 / 数手指 |
| 气氛凝固 | 感官锚点 | 声音消失 / 温度下降 / 谁的呼吸声 |
| 心潮澎湃 | 生理反应 | 指节发白 / 心跳乱拍 / 呼吸不稳 |
| 目光交汇 | 时长 + 动作 | 多久 / 谁先移开 |
| 浑身一震 | 具体反射 | 手指抖 / 后退半步 / 重心一沉 |
| 缓缓睁开眼 | 删副词 + 前置 / 后置动作 | 睁眼，光太亮，他立刻又闭上 |
| 微微点头 | 删副词 | 他点了下头 |

扣分：每出现 1 处未改写抽象动作 -3，单章 ≥ 5 处 → high。

### 末世重生 N1 / N5 根因联动

- N1 刻度量词外溢（半度/半秒/半指）—— 本规则不重复扫，由 Phase A anti-ai-guide.md + Phase B polish-guide 兜底
- N5 AI 腔具身模板（后颈凉/手心汗/喉咙紧/掌心印记跳）—— 本规则补充扫“浑身一震”等具身模板

## prose-quality-checker 输出 schema 扩展

```json
{
  "checker": "prose-quality-checker",
  "chapter": 12,
  "prose_quality": 88,
  "visual_subdimensions": {
    "scene_visual_anchor": 95,
    "sensory_coverage_score": 80,
    "sensory_present": ["visual","auditory","olfactory","tactile"],
    "sensory_missing": ["thermal","gustatory","kinesthetic"],
    "abstract_action_count": 2,
    "abstract_action_locations": ["第3段:展开攻势","第8段:浑身一震"]
  },
  "issues": [
    {"category": "visual", "subcategory": "non_visual_sensory", "severity": "high", "evidence": "...", "fix_hint": "..."}
  ]
}
```

主分加权：

```
prose_quality = round(原综合 × 0.6 + visual_subdimensions 平均 × 0.4, 2)
```

其中 visual_subdimensions 平均 = mean(scene_visual_anchor, sensory_coverage_score, max(0, 100 - 10 × abstract_action_count))。

## 与 Phase A / Phase F 的关系

- Phase A anti-ai-guide.md 起草前预防（含 N5 AI 腔模板）
- Phase F ai-replacement-vocab.csv 私库回灌（命中 recurring_violation 升级 severity）
- Phase H 本规则 prose-quality 评分硬卡（visual subdimensions 加权 0.4 入主分）

三者协同：起草前预防 + 复测时回灌 + 评分硬卡，从根源根治画面感。

## SKILL.md 加载

writer 在 Step 2A 起草时**必读**本文件作为参考；prose-quality-checker 在 Step 3 审查时强制走 3 子规则。
