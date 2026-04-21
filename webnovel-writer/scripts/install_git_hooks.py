#!/usr/bin/env python3
"""Install optional git pre-commit hook that enforces polish_cycle.py usage.

Round 14.5.2 · 根治"裸跑 polish commit"从 SKILL 规则升级到**技术闸门**。

背景：
    SKILL.md 的"禁止裸跑 polish commit"只是文档规定。AI / 用户仍可能手滑跑
    `git add . && git commit -m "polish"`，完全绕过 polish_cycle.py。
    直到下次 preflight / hygiene_check 才会被检测到，中间可能已经写了几段
    新内容或污染了上下文。

闸门设计：
    1. 检测 staged 的章节文件（``正文/第{NNNN}章*.md``）
    2. 读取 commit message 的候选字符（从 .git/COMMIT_EDITMSG）
    3. 规则：
       - 若 commit message 第一行 以 ``[polish:`` 结尾（被 polish_cycle.py 所产出）
         → 放行
       - 若 commit message 第一行以 ``第{N}章:`` / ``第{N}章 v{X}:`` 开头
         且包含 polish_cycle.py 的签名（state.json + workflow_state.json + 正文）
         → 放行
       - 其它情况（比如用户手写 "polish" / "fix" / "修" / "改"等关键词
         但 workflow_state.json 未 staged）→ **拒绝 commit** 并打印修复提示
    4. 若章节文件未 staged（纯设定集 / 大纲 commit）→ 放行

安装方法：
    # 方案 A：一次性安装到当前 project 的 .git/hooks/pre-commit
    python webnovel-writer/scripts/install_git_hooks.py --project-root .

    # 方案 B：卸载
    python webnovel-writer/scripts/install_git_hooks.py --uninstall --project-root .

设计原则：
    - **非强制**：不在 SKILL.md 里要求安装（因为会改用户的 git 配置）
    - **可绕过**：`git commit --no-verify` 仍可跳过。但这是用户的明示意图
    - **幂等**：重复跑安装无副作用
    - **可卸载**：`--uninstall` 清理

退出码：
    0 = 安装/卸载成功
    1 = 项目根不存在或不是 git 仓库
    2 = 参数错误
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


HOOK_NAME = "pre-commit"

# 钩子脚本内容：用 bash 调用 python 做检查
HOOK_SCRIPT = r"""#!/usr/bin/env bash
# Webnovel-Writer pre-commit hook (Round 14.5.2)
# 拦截"裸跑 polish commit": 章节文件 staged 但不符合 polish_cycle.py 产出的 commit 格式。
# 可绕过：git commit --no-verify

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
MSG_FILE="$PROJECT_ROOT/.git/COMMIT_EDITMSG"
if [ ! -f "$MSG_FILE" ]; then
    exit 0
fi

# 用 python 做精确判断（比 bash 字符串匹配更可靠处理中文）
python3 - "$MSG_FILE" "$PROJECT_ROOT" << 'PYEOF'
import sys, subprocess, os, re
from pathlib import Path

msg_path = Path(sys.argv[1])
project_root = Path(sys.argv[2])

# 只有当工作区含 .webnovel/state.json 才认为是 webnovel 项目
if not (project_root / ".webnovel" / "state.json").exists():
    sys.exit(0)

try:
    msg = msg_path.read_text(encoding="utf-8")
except Exception:
    sys.exit(0)
first = msg.strip().split("\n", 1)[0] if msg.strip() else ""

# 扫描 staged 文件
try:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=project_root, capture_output=True, text=True, check=True,
        encoding="utf-8",
    )
except Exception:
    sys.exit(0)
staged = [l.strip() for l in out.stdout.splitlines() if l.strip()]

# 有无章节文件 staged？
chapter_staged = [p for p in staged if p.startswith("正文/") and "章" in p and p.endswith(".md")]
if not chapter_staged:
    # 非章节 commit 一律放行（设定集/大纲/调研笔记）
    sys.exit(0)

# 规则 1：polish_cycle.py 产出的 commit message 格式
#   "第N章 v{X}: {reason} [polish:{round_tag}]"
is_polish_commit = bool(re.match(r"^第\d+章\s+v[\d.]+:.*\[polish:", first))

# 规则 2：主流程 Step 7 的 commit message 格式
#   "第N章: {title}"  可能后缀 "[audit:warn:layerX]"
is_step7_commit = bool(re.match(r"^第\d+章:\s*\S+", first)) and "polish" not in first

if is_polish_commit or is_step7_commit:
    sys.exit(0)

# 其它：检查是否疑似 polish 意图（message 含 polish/修复/润色/修正）
suspicious_keywords = ["polish", "润色", "修复", "修正", "改", "优化", "fix"]
has_polish_intent = any(kw in first.lower() for kw in suspicious_keywords)

# 若 message 没有 polish 意图 + workflow_state.json 没 staged，可能是其它合理 commit（如 .gitignore）
# 但有章节文件 staged 却无 [polish:] 标签也无 "第N章:" 前缀，这是异常的
print("=" * 70, file=sys.stderr)
print("⚠ Webnovel-Writer pre-commit 闸门拦截（Round 14.5.2）", file=sys.stderr)
print("=" * 70, file=sys.stderr)
print(f"Staged 章节文件: {chapter_staged[:3]}", file=sys.stderr)
print(f"Commit message 第一行: {first[:80]}", file=sys.stderr)
print("", file=sys.stderr)
print("本次 commit 似乎修改了章节文件，但 message 不符合以下任一格式：", file=sys.stderr)
print("  ✓ polish_cycle.py 产出: '第N章 vX: {reason} [polish:{round_tag}]'", file=sys.stderr)
print("  ✓ Step 7 主流程产出: '第N章: {title}' [audit:warn:layerX]", file=sys.stderr)
print("", file=sys.stderr)
print("修复建议:", file=sys.stderr)
print("  A) 若是 polish 修订：取消本次 commit，改用 polish_cycle.py：", file=sys.stderr)
print("     python webnovel-writer/scripts/polish_cycle.py <N> --reason '...' --narrative-version-bump", file=sys.stderr)
print("  B) 若确实是非 polish / 非写章的工具性 commit，请在 message 里", file=sys.stderr)
print("     明确说明，或临时绕过本 hook：", file=sys.stderr)
print("     git commit --no-verify -m '...'", file=sys.stderr)
print("", file=sys.stderr)
print("参考规范: skills/webnovel-write/references/post-commit-polish.md", file=sys.stderr)
print("=" * 70, file=sys.stderr)
sys.exit(1)
PYEOF
"""


def _hooks_dir(project_root: Path) -> Path:
    git_dir_p = project_root / ".git"
    if git_dir_p.is_dir():
        return git_dir_p / "hooks"
    if git_dir_p.is_file():
        text = git_dir_p.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("gitdir:"):
                p = Path(line.split("gitdir:", 1)[1].strip())
                if not p.is_absolute():
                    p = (project_root / p).resolve()
                return p / "hooks"
    raise SystemExit(1)


def _install(project_root: Path) -> int:
    hooks_dir = _hooks_dir(project_root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / HOOK_NAME

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8", errors="replace")
        if "Webnovel-Writer pre-commit hook" in existing:
            print(f"[install_git_hooks] 已存在 webnovel hook（幂等跳过）: {hook_path}")
            return 0
        backup = hook_path.with_suffix(".backup")
        hook_path.rename(backup)
        print(f"[install_git_hooks] 已备份现有 hook 到: {backup}")

    hook_path.write_text(HOOK_SCRIPT, encoding="utf-8", newline="\n")
    try:
        st = os.stat(hook_path)
        os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass

    print(f"[install_git_hooks] ✓ 安装成功: {hook_path}")
    print("[install_git_hooks]   拦截规则: staged 章节文件 + 非 polish_cycle/Step 7 格式的 commit")
    print("[install_git_hooks]   绕过方法: git commit --no-verify")
    return 0


def _uninstall(project_root: Path) -> int:
    hooks_dir = _hooks_dir(project_root)
    hook_path = hooks_dir / HOOK_NAME

    if not hook_path.exists():
        print(f"[install_git_hooks] hook 不存在，无需卸载: {hook_path}")
        return 0

    try:
        content = hook_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        print(f"[install_git_hooks] 无法读取 hook 文件: {hook_path}")
        return 1

    if "Webnovel-Writer pre-commit hook" not in content:
        print(f"[install_git_hooks] hook 不是 webnovel 产出，拒绝卸载: {hook_path}")
        return 1

    hook_path.unlink()
    print(f"[install_git_hooks] ✓ 卸载成功: {hook_path}")

    backup = hook_path.with_suffix(".backup")
    if backup.exists():
        backup.rename(hook_path)
        print(f"[install_git_hooks]   恢复备份: {backup} → {hook_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--uninstall", action="store_true", help="卸载 hook")
    args = ap.parse_args()

    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"ERROR: project_root 不存在: {project_root}")
        return 2
    if not (project_root / ".git").exists():
        print(f"ERROR: {project_root} 不是 git 仓库")
        return 1

    return _uninstall(project_root) if args.uninstall else _install(project_root)


if __name__ == "__main__":
    sys.exit(main())
