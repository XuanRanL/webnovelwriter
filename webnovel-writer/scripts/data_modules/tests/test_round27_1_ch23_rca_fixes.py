"""Round 27.1 · Ch23 RCA · 5 类根因防御回归测试 (2026-05-02)

测试目标：
- R3: foreshadowing add 时 anchor_text grep 上章正文 → 不存在标 evidence_missing=true
- R4: post_draft_check SIGNATURE_AGGREGATE 没/未/不曾 累计 ≥ 25/千字 block
- R6: data-agent _backfill_chapter_meta narrative_version 缺失时默认 v1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


# ============================================================================
# R6: data-agent narrative_version 默认 v1
# ============================================================================


def test_R6_narrative_version_default_v1(tmp_path):
    """Ch23 RCA R6: data-agent _backfill_chapter_meta 在 narrative_version 缺失/None
    时自动写入 v1 default (不算越权改 polish 字段, PROTECTED_FIELDS 检查会让真源
    CLI 优先生效)。"""
    from data_modules import state_manager as sm_mod

    proj = tmp_path
    (proj / ".webnovel").mkdir()
    (proj / "正文").mkdir()
    state_path = proj / ".webnovel" / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "project_info": {"title": "test"},
                "chapter_meta": {},
                "strand_tracker": {"history": [], "current_dominant": "quest"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (proj / "正文" / "第0099章-test.md").write_text("堂屋 " * 100, encoding="utf-8")

    # 用 mock config 绕过 lock 路径
    with patch.object(sm_mod, "get_config") as mc:
        cfg = MagicMock()
        cfg.state_file = state_path
        cfg.project_root = proj
        cfg.storage_dir = proj / ".webnovel"
        mc.return_value = cfg

        sm = sm_mod.StateManager(enable_sqlite_sync=False)
        sm._state = json.loads(state_path.read_text(encoding="utf-8"))

        # Case 1: narrative_version 缺失
        cm = {"word_count": 2000}
        sm._backfill_chapter_meta(99, cm)
        assert cm.get("narrative_version") == "v1", (
            f"R6 FAIL case1: 缺失时应默认 v1, 实际={cm.get('narrative_version')}"
        )

        # Case 2: narrative_version=None
        cm = {"word_count": 2000, "narrative_version": None}
        sm._backfill_chapter_meta(99, cm)
        assert cm.get("narrative_version") == "v1", (
            f"R6 FAIL case2: None 时应默认 v1, 实际={cm.get('narrative_version')}"
        )

        # Case 3: narrative_version=v3 (已有真源, 不应被覆盖到 v1)
        sm._state["chapter_meta"]["0099"] = {"narrative_version": "v3"}
        cm = {"word_count": 2000, "narrative_version": "v3"}
        sm._backfill_chapter_meta(99, cm)
        assert cm.get("narrative_version") == "v3", (
            f"R6 FAIL case3: 已有 v3 不应被覆盖, 实际={cm.get('narrative_version')}"
        )


# ============================================================================
# R4: post_draft_check SIGNATURE_AGGREGATE 否定签名累计上限
# ============================================================================


def test_R4_signature_aggregate_block(tmp_path):
    """Ch23 RCA R4: 没/未/不曾/无回信 累计 ≥ 25/千字 → block (避免没X→未X 替换循环)。"""
    import post_draft_check

    proj = tmp_path
    (proj / "正文").mkdir()
    (proj / ".webnovel").mkdir()
    # 项目级 SSOT
    (proj / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "project_info": {
                    "word_count_policy": {"hard_min": 1000, "hard_max": 5000}
                },
                "chapter_meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 1000 字章节, 注入 30 个 没X/未X/不曾 (= 30/千字 > 25 block)
    text = "堂屋。" * 200  # 占位 600 字
    text += "他没动。她没回。<protagonist>未出声。她到这会还无回信。" * 6  # 24 个否定
    text += "他不曾眨眼。他没看。他未碰。他没说话。他不曾出声。他没念。"  # 6 个否定
    (proj / "正文" / "第0099章-test.md").write_text(text, encoding="utf-8")

    # post_draft_check 函数签名: check(project_root, chapter)
    errors, warnings = post_draft_check.check(proj, 99)
    aggr_errors = [e for e in errors if "SIGNATURE_AGGREGATE" in e]
    assert aggr_errors, (
        f"R4 FAIL: 没/未/不曾 累计 30+/千字 应触发 SIGNATURE_AGGREGATE block; "
        f"errors={errors}"
    )


def test_R4_signature_aggregate_pass_under_threshold(tmp_path):
    """Ch23 RCA R4: 阈值以下不触发 block。"""
    import post_draft_check

    proj = tmp_path
    (proj / "正文").mkdir()
    (proj / ".webnovel").mkdir()
    (proj / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "project_info": {
                    "word_count_policy": {"hard_min": 1000, "hard_max": 5000}
                },
                "chapter_meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # 1000 字章节, 仅 5 个否定 (= 5/千字 < 20 warn)
    text = "堂屋。" * 250
    text += "他没动。他没说。他不曾眨眼。她未回。他没碰。"
    (proj / "正文" / "第0099章-test.md").write_text(text, encoding="utf-8")

    errors, warnings = post_draft_check.check(proj, 99)
    aggr_errors = [e for e in errors if "SIGNATURE_AGGREGATE" in e]
    assert not aggr_errors, f"R4 FAIL: 5/千字 不应 block; errors={aggr_errors}"


# ============================================================================
# R3: foreshadowing add anchor_text grep 验证
# ============================================================================


def test_R3_foreshadowing_anchor_text_missing_marks_evidence_missing(tmp_path):
    """Ch23 RCA R3: --add-foreshadowing 提供 anchor_text + planted_chapter 时,
    若 anchor_text 在该章正文 0 命中 → 标 evidence_missing=true (软警告, 不 reject)。"""
    proj = tmp_path
    (proj / ".webnovel").mkdir()
    (proj / "正文").mkdir()
    state_path = proj / ".webnovel" / "state.json"
    state_path.write_text(
        json.dumps(
            {"project_info": {"title": "t"}, "plot_threads": {"foreshadowing": []}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Ch99 正文不含 "<character-S>"
    (proj / "正文" / "第0099章-test.md").write_text(
        "堂屋的灯绳拉了两下。<protagonist>端着搪瓷缸。", encoding="utf-8"
    )

    # 调 webnovel.py state update --add-foreshadowing 子命令
    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            "-X", "utf8",
            str(ROOT / "webnovel.py"),
            "--project-root", str(proj),
            "state", "update",
            "--add-foreshadowing",
            json.dumps(
                {
                    "id": "F-CH99-TEST",
                    "description": "<character-S>电话埋点",
                    "planted_chapter": 99,
                    "anchor_text": "<character-S>",  # 正文 0 命中
                    "urgency": 30,
                    "level": "主线",
                },
                ensure_ascii=False,
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # 命令应成功 (软警告, 不 reject), 但 stderr 应有 [R3] 警告
    assert result.returncode == 0, f"R3 FAIL: 命令应成功, stderr={result.stderr}"
    stderr = (result.stderr or "")
    assert "[R3]" in stderr or "evidence_missing" in stderr, (
        f"R3 FAIL: 应有 R3 anchor_text 警告; stderr={stderr}"
    )

    # 验证落库 plot_threads.foreshadowing 含 evidence_missing=true
    state = json.loads(state_path.read_text(encoding="utf-8"))
    fs = state.get("plot_threads", {}).get("foreshadowing", [])
    target = [f for f in fs if f.get("id") == "F-CH99-TEST"]
    assert target, "R3 FAIL: foreshadowing 未落库"
    assert target[0].get("evidence_missing") is True, (
        f"R3 FAIL: 应标 evidence_missing=true, 实际={target[0]}"
    )


def test_R3_foreshadowing_anchor_text_found_no_warning(tmp_path):
    """Ch23 RCA R3: anchor_text 在正文存在时, 不标 evidence_missing。"""
    proj = tmp_path
    (proj / ".webnovel").mkdir()
    (proj / "正文").mkdir()
    state_path = proj / ".webnovel" / "state.json"
    state_path.write_text(
        json.dumps(
            {"project_info": {"title": "t"}, "plot_threads": {"foreshadowing": []}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Ch99 正文含 "<character-S>"
    (proj / "正文" / "第0099章-test.md").write_text(
        "堂屋的灯绳。<protagonist>给<character-S>发了一条短信。", encoding="utf-8"
    )

    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            "-X", "utf8",
            str(ROOT / "webnovel.py"),
            "--project-root", str(proj),
            "state", "update",
            "--add-foreshadowing",
            json.dumps(
                {
                    "id": "F-CH99-TEST",
                    "description": "<character-S>电话埋点",
                    "planted_chapter": 99,
                    "anchor_text": "<character-S>",
                    "urgency": 30,
                    "level": "主线",
                },
                ensure_ascii=False,
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    fs = state.get("plot_threads", {}).get("foreshadowing", [])
    target = [f for f in fs if f.get("id") == "F-CH99-TEST"]
    assert target, "R3 FAIL: foreshadowing 未落库"
    assert not target[0].get("evidence_missing"), (
        f"R3 FAIL: anchor 在正文存在时不应标 missing, 实际={target[0]}"
    )
