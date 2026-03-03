# 命令详解

## `/webnovel-init`

用途：初始化小说项目（目录、设定模板、状态文件）。

产出：

- `.webnovel/state.json`
- `设定集/`
- `大纲/总纲.md`

## `/webnovel-plan [卷号]`

用途：生成卷级规划与节拍。

示例：

```bash
/webnovel-plan 1
/webnovel-plan 2-3
```

## `/webnovel-write [章号]`

用途：执行完整章节创作流水线（上下文 → 草稿 → 审查 → 数据落盘）。

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
