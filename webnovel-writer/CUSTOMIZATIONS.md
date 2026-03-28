# Webnovel-Writer Customizations Log

> Fork: https://github.com/XuanRanL/webnovel-writer
> Upstream: https://github.com/lingfengQAQ/webnovel-writer
> This file tracks all custom modifications made to this fork.
> When merging upstream updates, use this file to verify no customizations are lost.

---

## [2026-03-27] Step 3.5 外部模型审查

**Commit:** d1015e1

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | 模式定义加入 3.5、引用清单、step-id、充分性闸门、步骤定义 |
| `scripts/external_review.py` | 新增 | 调用硅基流动 API (Qwen3.5 + GLM-5) 双模型审查脚本 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 新增 | Step 3.5 执行规范文档 |

**背景：**
- 7模型对比测试（DeepSeek-V3.2, Qwen3.5-397B, MiniMax-M2.5, GLM-5, Kimi-K2.5, GLM-4.7, DS-Terminus）
- 最终选定 Qwen3.5-397B（设定/逻辑，区分度80-93）+ GLM-5（编辑/读者感受，区分度80-93）
- 淘汰原因：DS-Terminus 零区分度、MiniMax 格式不稳、DeepSeek-V3.2 区分度低

**SKILL.md 具体改动点（合并时注意）：**
1. 第26-28行：三个模式定义加入 `→ 3.5`
2. 第62-64行：references 清单新增 `step-3.5-external-review.md` 条目
3. 第152行：`--step-id` 允许列表加入 `Step 3.5`
4. 第259-280行：插入完整的 `### Step 3.5` 段落（在 Step 3 和 Step 4 之间）
5. 第370行：充分性闸门新增第3条（Step 3.5 外部审查必须完成）

---

<!-- 新的改动记录追加在此线下方 -->
