---
name: chapter-end-hook-taxonomy
purpose: 章末钩子 4 分类规范 + 跨章趋势规则
---

# 章末钩子 4 分类（Round 19 Phase G）

> **核心 insight**：reader_pull 0-100 单数字看不出“读者疲劳”。钩子强度 88 但连续 5 章都是“信息钩”，读者会期待“动作钩”或“决策钩”打破节奏。4 类对应 4 种读者心理动机。

## 与既有 hook_type 字段的关系

- Ch1-11 既有 `chapter_meta[NNNN].hook_type` 自由文本（“主线单钩”/“意象钩”等 7+ 种）—— 历史遗留，**不动**
- Round 19 平行新增 `chapter_meta[NNNN].hook_close` 强约束 4 类枚举对象
- Phase G 之后两个字段**并存**；hygiene H25 不要求历史章节回填 hook_close（启发式回填脚本主动跑一次）

## 4 类定义

| 类型 | 触发读者动机 | 示例 | 强信号 |
|---|---|---|---|
| **信息钩** | 想知道“是什么” / “为什么” / “谁” | 她终于看清了那张脸——是十年前应该已经死去的人。 | 揭示 / 反转 / 真相缺片 |
| **情绪钩** | 想知道“她怎么应对” / “他下一步什么心情” | 他没有回头，把那枚戒指扔进了海里。 | 决断 / 离别 / 隐忍 |
| **决策钩** | 想知道“她选哪边” / “他怎么选” | 面前两扇门，左边是父亲，右边是仇人。她伸出了手—— | 二选 / 道德困境 / 立场抉择 |
| **动作钩** | 想知道“打赢了吗” / “逃掉了吗” / “接住了吗” | 刀光起处，他终于看清了那双眼睛。 | 战斗 / 追逐 / 关键瞬间 / 危机降临 |

## 评判标准

每章末由 reader-pull-checker 二选：

1. `primary_type`（必填）：4 类之一
2. `secondary_type`（可选）：4 类之一（多重钩子）/ null

判断窗口：章末**最后 200 字**。

## 跨章趋势规则（H25 联动）

| 规则 | 严重度 | 理由 |
|---|---|---|
| 连续 5 章 primary 相同 | medium（H25 P1 warn） | 节奏疲劳 |
| 连续 3 章 primary+secondary 组合相同 | high | 模式可预测 |
| 连续 8 章无“决策钩” | medium | 主角失去主动性 |
| 连续 8 章无“情绪钩” | medium | 关系线断档 |
| 单卷（默认 20 章）内 4 类全缺 1 类 | medium | 情绪面单一 |

## reader-pull-checker 输出 schema 扩展

```json
{
  "checker": "reader-pull-checker",
  "chapter": 12,
  "reader_pull": 88,
  "hook_close": {
    "primary_type": "信息钩",
    "secondary_type": "情绪钩",
    "strength": 88,
    "text_excerpt": "章末最后 200 字"
  },
  "cross_chapter_trend": {
    "recent_5_primary": ["信息钩","信息钩","情绪钩","信息钩","信息钩"],
    "warnings": [
      {"rule": "连续 5/5 章信息钩", "severity": "medium", "fix_hint": "Ch12 切换为决策钩或动作钩"}
    ]
  }
}
```

## 末世重生 Ch1-11 钩子分布（Round 19 启发式回填后）

参 `chapter_meta.hook_close` 实测数据（H25 hygiene 检查依赖此字段）。

| 章 | 既有 hook_type | 启发式映射 4 类 |
|---|---|---|
| 0001 | 主线单钩·规则代价钩 | 动作钩（救援） |
| 0002 | 冷钩·备忘录异常A级 | 信息钩 |
| 0003 | 悬念钩+认知钩 | 信息钩 |
| 0004 | 新设定钩·第2次暗示不止我一个 | 信息钩 |
| 0005 | 情感+神秘钩 | 信息钩 + 情绪钩 |
| 0006 | ambient+mystery | 信息钩 + 情绪钩 |
| 0007 | mystery+threat | 信息钩 + 动作钩 |
| 0008 | crisis+mystery | 动作钩 + 信息钩 |
| 0009 | 情感钩+伏笔钩 | 情绪钩 + 信息钩 |
| 0010 | 悬念钩+信息钩 | 信息钩 |
| 0011 | 意象钩 | 信息钩（弱） |

**RCA §3 揭示的连发模式**：

- Ch3-4-5 三章信息钩主导 → 已属于“连续 3 章 primary 相同”high warn
- Ch6-9-10-11 远处声音锚四连（同型钩子） → reader-pull Ch6=80 / Ch11=82 谷底命中

Phase G 起这类连发将自动 H25 P1 warn，reader-pull-checker 必须在 issue 中提示切换。

## CLI 集成

- `webnovel.py state update --set-hook-close '{...}'` 写入字段
- `webnovel.py state get-hook-trend --last-n 5` 查询趋势 + 自动判定
- data-agent Step K 自动从 reader_pull_ch{NNNN}.json 提取 hook_close 并落库
- hygiene_check H25 扫描最近 5 章 primary_type，命中“连续 5 章相同” P1 warn
