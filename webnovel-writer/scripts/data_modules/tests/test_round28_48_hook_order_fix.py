"""Round 28.48 · Ch47 v2 RCA · 1 P0 顺序 bug 根治测试.

测试范围:
- Fix · set-hook-close secondary 别名映射顺序 bug
  根因: R28.47 加 HOOK_ALIASES 含 行动钩→动作钩, 但 sec 在别名映射前被 reject (not in VALID_HOOK_TYPES) → sec=None → 永远 None
  现象: Ch47 实测 secondary_type=None 但用户明明传 行动钩
  修法: 别名映射先行 (R28.48 顺序 bug 根治)
"""
import json
import sys
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _ensure_scripts_on_path():
    p = str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def _make_project(tmp_path):
    pr = tmp_path / "book"
    (pr / ".webnovel").mkdir(parents=True)
    (pr / "正文").mkdir()
    state = {
        "project_info": {"name": "test", "word_count_policy": {"hard_min": 2200, "hard_max": 3800}},
        "chapter_meta": {
            "0047": {"chapter": 47, "narrative_version": "v1"},
        },
        "entities_v3": {},
        "progress": {"current_chapter": 47},
        "last_completed_chapter": 47,
        "current_chapter": 47,
    }
    (pr / ".webnovel" / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return pr


def test_r28_48_hook_alias_order_fix_secondary_xingdongou_not_rejected(tmp_path):
    """R28.48 顺序 bug 根治: secondary='行动钩' 必须先别名映射再 enum 校验."""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm

    src = inspect.getsource(sm)
    # 找 set_hook_close 块中 sec 处理段
    hook_block_start = src.find("if args.set_hook_close:")
    hook_block_end = src.find("            cm = manager._state.setdefault", hook_block_start)
    assert hook_block_start > 0 and hook_block_end > hook_block_start
    block = src[hook_block_start:hook_block_end]

    # 找 sec = payload.get("secondary") 位置
    sec_get_pos = block.find('sec = payload.get("secondary")')
    assert sec_get_pos > 0

    # 找 别名映射 if sec and sec in HOOK_ALIASES 位置
    alias_map_pos = block.find('if sec and sec in HOOK_ALIASES:')
    assert alias_map_pos > 0, "未找到 HOOK_ALIASES 别名映射段"

    # 找 enum reject if sec and sec not in VALID_HOOK_TYPES 位置
    reject_pos = block.find('if sec and sec not in VALID_HOOK_TYPES:')
    assert reject_pos > 0, "未找到 sec enum reject"

    # R28.48 顺序硬约束: 别名映射 必须在 reject 之前
    assert alias_map_pos < reject_pos, (
        f"FAIL: R28.48 顺序 bug 复发. "
        f"别名映射位置={alias_map_pos} 必须 < enum reject 位置={reject_pos}. "
        f"否则 sec='行动钩' 会被先 reject 置 None, 永远不会触发别名映射."
    )


def test_r28_48_hook_alias_xingdongou_secondary_end_to_end(tmp_path):
    """端到端 subprocess 测试: set-hook-close secondary='行动钩' → '动作钩'."""
    import subprocess

    pr = _make_project(tmp_path)
    entry = SCRIPTS_DIR / "webnovel.py"
    payload = json.dumps({
        "chapter": 47,
        "primary": "决策钩",
        "secondary": "行动钩",  # R28.47 加了别名但 R28.48 才修了顺序
        "text_excerpt": "test excerpt",
        "strength": 89,
    }, ensure_ascii=False)
    r = subprocess.run(
        ["python", "-X", "utf8", str(entry),
         "--project-root", str(pr),
         "state", "update", "--set-hook-close", payload],
        capture_output=True, text=True, encoding="utf-8"
    )
    assert r.returncode == 0, f"FAIL CLI: stdout={r.stdout!r} stderr={r.stderr!r}"

    state = json.loads((pr / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    hc = state["chapter_meta"]["0047"]["hook_close"]
    assert hc["primary_type"] == "决策钩"
    assert hc["secondary_type"] == "动作钩", \
        f"FAIL R28.48: secondary 行动钩 应映射为 动作钩, 实际={hc.get('secondary_type')}"
