---
name: webnovel-learn
description: 从当前会话提取成功模式并写入 project_memory.json
allowed-tools: Read Write Bash
---

# /webnovel-learn

## Project Root Guard（必须先确认）

- 必须在项目根目录执行（需存在 `.webnovel/state.json`）
- 若当前目录不存在该文件，先询问用户项目路径并 `cd` 进入
- 进入后设置变量：`$PROJECT_ROOT = (Resolve-Path ".").Path`

## 目标
- 提取可复用的写作模式（钩子/节奏/对话/微兑现等）
- 追加到 `.webnovel/project_memory.json`

## 输入
```bash
/webnovel-learn "本章的危机钩设计很有效，悬念拉满"
```

## 输出
```json
{
  "status": "success",
  "learned": {
    "pattern_type": "hook",
    "description": "危机钩设计：悬念拉满",
    "source_chapter": 100,
    "learned_at": "2026-02-02T12:00:00Z"
  }
}
```

## 执行流程
1. 读取 `"$PROJECT_ROOT/.webnovel/state.json"`，获取当前章节号（progress.current_chapter）
2. 读取 `"$PROJECT_ROOT/.webnovel/project_memory.json"`，若不存在则初始化 `{"patterns": []}`
3. 解析用户输入，归类 pattern_type（hook/pacing/dialogue/payoff/emotion）
4. 追加记录并写回文件

## 约束
- 不删除旧记录，仅追加
- 避免完全重复的 description（可去重）

## 去重规则

- 追加前扫描已有 `patterns` 数组
- 若存在 `pattern_type` + `description` 完全相同的记录，跳过并告知用户
- 部分相似不去重，由用户判断

## 成功标准

- `project_memory.json` 存在且格式合法
- 新 pattern 已追加到 `patterns` 数组
- 输出包含 `status: success` 和完整 `learned` 对象

## 失败恢复

| 故障 | 恢复方式 |
|------|---------|
| `project_memory.json` 不存在 | 自动初始化 `{"patterns": []}` 后继续 |
| JSON 解析失败 | 不写入脏数据，告知用户文件损坏并建议手动修复 |
| `state.json` 缺失导致无法获取章节号 | 使用 `source_chapter: null`，不阻断 |
| 用户输入无法归类 | 使用 `pattern_type: "other"`，不阻断 |
