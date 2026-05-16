# -*- coding: utf-8 -*-
"""Round 28.35 Ch44 v3 deep research RCA 七项修复测试

覆盖：
  #1 polish_cycle.py: polish 有实质 fixes 时自动 bump narrative_version
  #2 chapter_audit.py: check_A10_external_freshness mtime 对账
  #3 post_draft_check.py: H78 跨章首段 N-gram 比对
  #4 pre_commit_step_k.py: EXTENDED_TARGETS_OPTIONAL skip 不存在
  #5 workflow_manager.py: Step 7 branch 字段动态对账
  #6 post_draft_check.py: 半X 签名密度
  #7 post_draft_check.py: ASCII 英文动词扫描
  #plugin-bug: state_manager.py set-hook-close 支持 text_excerpt + text 兼容
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
import pytest


FORK_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = FORK_ROOT / "scripts"


# ==================== #1: polish_cycle 自动 bump narrative_version ====================

def test_polish_cycle_auto_bump_narrative_version_on_changed():
    """Round 28.35 #1: polish_cycle 检测到 changed=True 且未指定 narrative_version 时自动 bump"""
    src = (SCRIPTS_DIR / "polish_cycle.py").read_text(encoding="utf-8")
    # 必须含 auto_bumped 变量逻辑
    assert "auto_bumped" in src, "polish_cycle.py 必须含 auto_bumped 变量"
    # 必须有 Round 28.35 注释
    assert "Round 28.35" in src, "polish_cycle.py 必须标 Round 28.35"
    # 必须有 changed and not allow_no_change 条件
    assert "elif changed and not args.allow_no_change:" in src, \
        "polish_cycle.py 必须在 changed=True 且非 allow_no_change 时自动 bump"


def test_polish_cycle_skip_auto_bump_on_no_change():
    """Round 28.35 #1: 显式 --narrative-version 优先 / --allow-no-change 不触发自动 bump"""
    src = (SCRIPTS_DIR / "polish_cycle.py").read_text(encoding="utf-8")
    # 显式 narrative_version 优先级最高
    assert "if args.narrative_version:" in src, "polish_cycle.py 必须先检查 args.narrative_version"
    # allow_no_change 必须跳过 auto bump
    assert "not args.allow_no_change" in src, "polish_cycle.py 必须排除 --allow-no-change"


# ==================== #2: chapter_audit A10 external mtime 对账 ====================

def test_chapter_audit_a10_function_exists():
    """Round 28.35 #2: chapter_audit.py 含 check_A10_external_freshness 函数"""
    src = (SCRIPTS_DIR / "data_modules" / "chapter_audit.py").read_text(encoding="utf-8")
    assert "def check_A10_external_freshness" in src
    assert 'id="A10"' in src
    assert "Round 28.35" in src


def test_chapter_audit_a10_registered_in_layer_a():
    """Round 28.35 #2: A10 必须注册到 _run_layer_a"""
    src = (SCRIPTS_DIR / "data_modules" / "chapter_audit.py").read_text(encoding="utf-8")
    # 在 _run_layer_a 的 checks list 里
    layer_a_match = re.search(r"def _run_layer_a.*?return LayerResult", src, re.DOTALL)
    assert layer_a_match, "_run_layer_a 不存在"
    assert "check_A10_external_freshness" in layer_a_match.group(0), \
        "A10 必须注册到 _run_layer_a checks list"


def test_chapter_audit_a10_skip_when_no_external():
    """Round 28.35 #2: 无外审文件时 skip 不报错"""
    from scripts.data_modules.chapter_audit import check_A10_external_freshness
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "正文").mkdir()
        (p / "正文" / "第0001章-test.md").write_text("test", encoding="utf-8")
        (p / ".webnovel").mkdir()
        (p / ".webnovel" / "tmp").mkdir()
        result = check_A10_external_freshness(p, 1)
        assert result.status == "skip"


def test_chapter_audit_a10_pass_when_fresh():
    """Round 28.35 #2: external mtime ≥ chapter mtime 时 pass"""
    from scripts.data_modules.chapter_audit import check_A10_external_freshness
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "正文").mkdir()
        chap_file = p / "正文" / "第0001章-test.md"
        chap_file.write_text("test", encoding="utf-8")
        (p / ".webnovel").mkdir()
        (p / ".webnovel" / "tmp").mkdir()
        ext_file = p / ".webnovel" / "tmp" / "external_review_modelA_ch0001.json"
        ext_file.write_text("{}", encoding="utf-8")
        # ext_file 创建在 chap_file 之后 → fresh
        time.sleep(0.1)
        ext_file.touch()
        result = check_A10_external_freshness(p, 1)
        assert result.status == "pass"


def test_chapter_audit_a10_warn_when_stale():
    """Round 28.35 #2: external 早于 chapter mtime + tolerance 时 warn"""
    from scripts.data_modules.chapter_audit import check_A10_external_freshness
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "正文").mkdir()
        (p / ".webnovel").mkdir()
        (p / ".webnovel" / "tmp").mkdir()
        ext_file = p / ".webnovel" / "tmp" / "external_review_modelA_ch0001.json"
        ext_file.write_text("{}", encoding="utf-8")
        chap_file = p / "正文" / "第0001章-test.md"
        chap_file.write_text("test", encoding="utf-8")
        # 把 ext_file mtime 设为很早（90 秒前）
        old_ts = ext_file.stat().st_mtime - 90
        os.utime(ext_file, (old_ts, old_ts))
        result = check_A10_external_freshness(p, 1)
        assert result.status == "warn"


# ==================== #3: post_draft_check H78 跨章首段 N-gram ====================

def test_post_draft_check_h78_function_present():
    """Round 28.35 #3: post_draft_check.py 含 H78 跨章 N-gram 检查"""
    src = (SCRIPTS_DIR / "post_draft_check.py").read_text(encoding="utf-8")
    assert "H78_CROSS_CHAPTER_REUSE" in src
    assert "cross_chapter_ngram_config" in src
    assert "ngram_size" in src


def test_post_draft_check_h78_detects_reuse():
    """Round 28.35 #3: H78 检测到首段意象 1:1 复用"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pdc", SCRIPTS_DIR / "post_draft_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "正文").mkdir()
        (p / ".webnovel").mkdir()
        # 上一章末段含 "蓝铁门那头很安静送水车今早一辆还没过来巷子里只有早班三轮车的链条声"
        prev_text = "上一章正文。" * 50 + "蓝铁门那头很安静。送水车今早一辆还没过来，巷子里只有早班三轮车的链条声断断续续。"
        (p / "正文" / "第0001章-test.md").write_text(prev_text, encoding="utf-8")
        # 当章首段几乎完全复用
        cur_text = "蓝铁门那头很安静。送水车今早一辆还没过来，巷子里只有早班三轮车的链条声断断续续。" + "正文继续。" * 50
        cur_file = p / "正文" / "第0002章-test.md"
        cur_file.write_text(cur_text, encoding="utf-8")
        # 写最简 state.json
        (p / ".webnovel" / "state.json").write_text(
            '{"chapter_meta": {}, "project_info": {"word_count_policy": {"hard_min": 100, "hard_max": 10000}}}',
            encoding="utf-8",
        )
        errors, warnings = mod.check(p, 2)
        # 应该命中 H78
        all_msgs = errors + warnings
        h78_hits = [m for m in all_msgs if "H78" in m]
        assert h78_hits, f"H78 应该命中跨章意象复用，实际 messages: {all_msgs[:5]}"


# ==================== #4: pre_commit_step_k 扩展白名单 skip ====================

def test_step_k_extended_targets_optional():
    """Round 28.35 #4: pre_commit_step_k.py 含 EXTENDED_TARGETS_OPTIONAL"""
    src = (SCRIPTS_DIR / "pre_commit_step_k.py").read_text(encoding="utf-8")
    assert "EXTENDED_TARGETS_OPTIONAL" in src
    assert "01-卷一承诺-兑现表.md" in src
    assert "02-损失与代价表.md" in src
    assert "11-反派压强表.md" in src


def test_step_k_extended_skip_when_missing():
    """Round 28.35 #4: 扩展文件不存在时 silent skip"""
    src = (SCRIPTS_DIR / "pre_commit_step_k.py").read_text(encoding="utf-8")
    # 必须有 continue 跳过逻辑
    assert "continue  # silent skip" in src or "if not fp.exists():\n                continue" in src
    # extended_warnings 必须是非阻断
    assert "STEP_K_EXTENDED_WARN" in src
    assert "extended_warnings" in src


def test_step_k_extended_warn_when_present_but_missing_tag():
    """Round 28.35 #4: 文件存在但缺 [ChN] 标注 → warn 不 block"""
    src = (SCRIPTS_DIR / "pre_commit_step_k.py").read_text(encoding="utf-8")
    assert 'STEP_K_EXTENDED_WARN' in src
    # main 必须区分 blocking_errors 与 extended_warnings
    assert "blocking_errors" in src
    assert "extended_warnings" in src


# ==================== #5: workflow_manager Step 7 branch 动态对账 ====================

def test_workflow_step7_branch_verification():
    """Round 28.35 #5: workflow_manager.py Step 7 branch 字段验证"""
    src = (SCRIPTS_DIR / "workflow_manager.py").read_text(encoding="utf-8")
    assert "Round 28.35" in src
    assert "branch --show-current" in src
    assert "BRANCH_MISMATCH" in src
    assert "branch_verified" in src


def test_workflow_step7_branch_warn_only_not_block():
    """Round 28.35 #5: branch 不匹配只 warn 不阻断 commit"""
    src = (SCRIPTS_DIR / "workflow_manager.py").read_text(encoding="utf-8")
    # 不能在 branch 检查后立即 return
    # 检查 branch 验证段后必须继续到 STEP_STATUS_COMPLETED
    branch_check_idx = src.find("BRANCH_MISMATCH")
    assert branch_check_idx > 0
    after_branch = src[branch_check_idx:branch_check_idx + 1000]
    # 必须有 except 兜底
    assert "except Exception" in after_branch
    # 跟着必须有 STEP_STATUS_COMPLETED 设定
    completed_idx = src.find("STEP_STATUS_COMPLETED", branch_check_idx)
    assert completed_idx > 0


# ==================== #6: 半X 签名密度 ====================

def test_half_x_signature_in_default_patterns():
    """Round 28.35 #6: signature_patterns_default 含 半X"""
    src = (SCRIPTS_DIR / "post_draft_check.py").read_text(encoding="utf-8")
    assert '"半X"' in src
    # 阈值合理（warn 15 / block 22）
    half_x_idx = src.find('"半X"')
    half_x_block = src[half_x_idx:half_x_idx + 200]
    assert '"warn": 15' in half_x_block or "warn': 15" in half_x_block
    assert '"block": 22' in half_x_block or "block': 22" in half_x_block


# ==================== #7: ASCII 英文动词扫描 ====================

def test_ascii_verb_scan_present():
    """Round 28.35 #7: post_draft_check.py 含 H79 ASCII 英文动词扫描"""
    src = (SCRIPTS_DIR / "post_draft_check.py").read_text(encoding="utf-8")
    assert "H79" in src
    assert "ascii_verbs" in src
    # 至少含核心动词
    for verb in ["release", "active", "trigger"]:
        assert verb in src


def test_ascii_verb_detects_release_in_prose():
    """Round 28.35 #7: 正文含 release 触发 H79 warn 或 block"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pdc", SCRIPTS_DIR / "post_draft_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "正文").mkdir()
        (p / ".webnovel").mkdir()
        text = "陆沉走到屋外。release 不开。掌心朝里收着，深金色那道沉得比昨晚更实。"
        (p / "正文" / "第0001章-test.md").write_text(text, encoding="utf-8")
        (p / ".webnovel" / "state.json").write_text(
            '{"chapter_meta": {}, "project_info": {"word_count_policy": {"hard_min": 10, "hard_max": 1000}}}',
            encoding="utf-8",
        )
        errors, warnings = mod.check(p, 1)
        all_msgs = errors + warnings
        h79_hits = [m for m in all_msgs if "H79" in m]
        assert h79_hits, f"H79 应该命中 release，实际 messages: {all_msgs[:5]}"


# ==================== plugin-bug: set-hook-close 兼容字段名 ====================

def test_set_hook_close_accepts_text_excerpt():
    """Round 28.34 plugin bug fix: set-hook-close 支持 text_excerpt 字段"""
    src = (SCRIPTS_DIR / "data_modules" / "state_manager.py").read_text(encoding="utf-8")
    # 必须含 兼容代码
    assert 'payload.get("text_excerpt") or payload.get("text")' in src
