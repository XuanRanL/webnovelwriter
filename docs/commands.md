# 命令详解

## `/webnovel-init`

用途：初始化小说项目（目录、设定模板、状态文件）。

产出：

- `.webnovel/state.json`
- `设定集/`
- `大纲/总纲.md`

## `/webnovel-plan [卷号]`

用途：生成卷级规划与章节大纲。

示例：

```bash
/webnovel-plan 1
/webnovel-plan 2-3
```

## `/webnovel-write [章号]`

用途：执行完整章节创作流程（上下文 → 草稿 → 审查 → 润色 → 数据落盘）。

示例：

```bash
/webnovel-write 1
/webnovel-write 45
```

常见模式：

- 标准模式：全流程
- 快速模式：`--fast`
- 极简模式：`--minimal`

## `/webnovel-review [范围]`

用途：对历史章节做多维质量审查。

示例：

```bash
/webnovel-review 1-5
/webnovel-review 45
```

## `/webnovel-query [关键词]`

用途：查询角色、伏笔、节奏、状态等运行时信息。

示例：

```bash
/webnovel-query 萧炎
/webnovel-query 伏笔
/webnovel-query 紧急
```

## `/webnovel-resume`

用途：任务中断后自动识别断点并恢复。

示例：

```bash
/webnovel-resume
```

## `/webnovel-dashboard`

用途：启动只读可视化面板，查看项目状态、实体关系、章节与大纲内容。

示例：

```bash
/webnovel-dashboard
```

说明：

- 默认只读，不会修改项目文件
- 适合排查上下文、实体关系和章节进度

## `/webnovel-learn [内容]`

用途：从当前会话或用户输入中提取可复用写作模式，并写入项目记忆。

示例：

```bash
/webnovel-learn "本章的危机钩设计很有效，悬念拉满"
```

产出：

- `.webnovel/project_memory.json`
