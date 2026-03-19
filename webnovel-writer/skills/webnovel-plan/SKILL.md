---
name: webnovel-plan
description: 基于总纲生成卷纲、时间线和章纲，并把新增设定增量写回现有设定集。
---

# Outline Planning

## 目标

- 基于总纲细化卷纲、时间线与章纲，不重做全局故事。
- 先补齐设定基线，再产出可直接进入写作的章纲。
- 卷纲完成后，把新增设定增量写回现有设定集。

## 执行原则

1. 只做增量补齐，不重写整份总纲或设定集。
2. 先锁定卷级节奏，再批量拆章。
3. 时间线是硬约束，所有章纲都必须带时间字段。
4. 若发现总纲与设定冲突，先阻断，再等用户裁决。

## 环境准备

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

## References

- Step 4：`../../templates/output/大纲-卷节拍表.md`
- Step 5：`../../templates/output/大纲-卷时间线.md`
- Step 6：`../../references/genre-profiles.md`
- Step 6：`../../references/shared/strand-weave-pattern.md`
- Step 6：`../../references/shared/cool-points-guide.md`（按需）
- Step 6/7：`references/outlining/conflict-design.md`（按需）
- Step 7：`../../references/reading-power-taxonomy.md`（按需）
- Step 7：`references/outlining/chapter-planning.md`（按需）
- Step 6/7：`references/outlining/genre-volume-pacing.md`（特定题材按需）

## 执行流程

### Step 1：加载项目数据并确认前置条件

```bash
cat "$PROJECT_ROOT/.webnovel/state.json"
cat "$PROJECT_ROOT/大纲/总纲.md"
```

按需读取：
- `设定集/世界观.md`
- `设定集/力量体系.md`
- `设定集/主角卡.md`
- `设定集/反派设计.md`
- `.webnovel/idea_bank.json`

阻断条件：
- 总纲缺少卷名、章节范围、核心冲突或卷末高潮

### Step 2：补齐设定基线

目标：让设定集从骨架模板进入“可规划、可写作”的状态。

必须补齐：
- `设定集/世界观.md`：世界边界、社会结构、关键地点用途
- `设定集/力量体系.md`：境界链、限制、代价与冷却
- `设定集/主角卡.md`：欲望、缺陷、初始资源与限制
- `设定集/反派设计.md`：小/中/大反派层级与镜像关系

硬规则：
- 只增量补齐，不清空、不重写整文件
- 发现冲突时先列出冲突并阻断

### Step 3：选择目标卷并确认范围

必须确认：
- 卷名
- 章节范围
- 核心冲突
- 是否存在特殊要求，例如视角、情感线、题材偏移

### Step 4：生成卷节拍表

执行前加载模板：

```bash
cat "${SKILL_ROOT}/../../templates/output/大纲-卷节拍表.md"
```

硬要求：
- 必须填写中段反转；若确实没有，写“无（理由：...）”
- 危机链至少 3 次递增
- 卷末新钩子必须能落到最后一章的章末未闭合问题

输出文件：`大纲/第{volume_id}卷-节拍表.md`

### Step 5：生成卷时间线表

执行前加载模板：

```bash
cat "${SKILL_ROOT}/../../templates/output/大纲-卷时间线.md"
```

硬要求：
- 必须明确时间体系
- 必须明确本卷时间跨度
- 有倒计时事件时必须列出并标记 D-N

输出文件：`大纲/第{volume_id}卷-时间线.md`

### Step 6：生成卷纲骨架

必须加载：

```bash
cat "${SKILL_ROOT}/../../references/genre-profiles.md"
cat "${SKILL_ROOT}/../../references/shared/strand-weave-pattern.md"
```

按需加载：

```bash
cat "${SKILL_ROOT}/../../references/shared/cool-points-guide.md"
cat "${SKILL_ROOT}/references/outlining/conflict-design.md"
cat "${SKILL_ROOT}/references/outlining/genre-volume-pacing.md"
cat "$PROJECT_ROOT/.webnovel/idea_bank.json"
```

卷纲必须明确：
- 卷摘要
- 关键人物与反派层级
- Strand 分布
- 爽点密度规划
- 伏笔规划
- 约束触发规划

### Step 7：批量生成章纲

批次规则：
- `<=20` 章：1 批
- `21-40` 章：2 批
- `41-60` 章：3 批
- `>60` 章：4 批及以上

按需加载：

```bash
cat "${SKILL_ROOT}/../../references/reading-power-taxonomy.md"
cat "${SKILL_ROOT}/references/outlining/chapter-planning.md"
```

每章必须包含：
- 目标
- 阻力
- 代价
- 时间锚点
- 章内时间跨度
- 与上章时间差
- 倒计时状态
- 爽点
- Strand
- 反派层级
- 视角/主角
- 关键实体
- 本章变化
- 章末未闭合问题
- 钩子

输出文件：`大纲/第{volume_id}卷-详细大纲.md`

### Step 8：把新增设定写回现有设定集

输入来源：
- 卷节拍表
- 卷时间线表
- 卷详细大纲
- 现有设定集文件

写回规则：
- 只增量补充相关段落
- 新角色写入角色卡或角色组
- 新势力、地点、规则写入世界观或力量体系
- 新反派层级写入反派设计

硬规则：
- 若发现与总纲或既有设定冲突，标记 `BLOCKER` 并停止后续更新

### Step 9：验证、保存并更新状态

必须通过以下检查：
- 节拍表存在且非空
- 时间线表存在且非空
- 详细大纲存在且非空
- 每章时间字段齐全
- 时间线单调递增
- 倒计时推进正确
- 新设定已回写到现有设定集
- `BLOCKER=0`

更新状态：

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" update-state -- \
  --volume-planned {volume_id} \
  --chapters-range "{start}-{end}"
```

## 硬失败条件

- 节拍表不存在或为空
- 中段反转缺失且未给出理由
- 时间线表不存在或为空
- 详细大纲不存在或为空
- 任一章节缺少时间字段
- 时间回跳且未标注闪回
- 倒计时算术冲突
- 与总纲核心冲突或卷末高潮明显冲突
- 存在 `BLOCKER` 未裁决

## 恢复规则

1. 只重做失败批次，不覆盖整卷文件。
2. 最后一个批次无效时，只删除并重写该批次。
3. 仅在全部验证通过后更新状态。
