#!/usr/bin/env python3
"""
安全工具函数库
用于webnovel-writer系统的通用安全函数

创建时间: 2026-01-02
创建原因: 安全审计发现路径遍历和命令注入漏洞
修复方案: 集中管理所有安全相关的输入清理函数
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union

# 尝试导入 filelock（可选依赖）
try:
    from filelock import FileLock
    HAS_FILELOCK = True
except ImportError:
    HAS_FILELOCK = False


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    清理文件名，防止路径遍历攻击 (CWE-22)

    安全关键函数 - 修复extract_entities.py路径遍历漏洞

    Args:
        name: 原始文件名（可能包含路径遍历字符）
        max_length: 文件名最大长度（默认100字符）

    Returns:
        安全的文件名（仅包含基本文件名，移除所有路径信息）

    示例:
        >>> sanitize_filename("../../../etc/passwd")
        'passwd'
        >>> sanitize_filename("C:\\Windows\\System32")
        'System32'
        >>> sanitize_filename("正常角色名")
        '正常角色名'

    安全验证:
        - ✅ 防止目录遍历（../、..\\）
        - ✅ 防止绝对路径（/、C:\\）
        - ✅ 移除特殊字符
        - ✅ 长度限制
    """
    # Step 1: 仅保留基础文件名（移除所有路径）
    safe_name = os.path.basename(name)

    # Step 2: 移除路径分隔符（双重保险）
    safe_name = safe_name.replace('/', '_').replace('\\', '_')

    # Step 3: 只保留安全字符
    # 允许：中文(\u4e00-\u9fff)、字母(a-zA-Z)、数字(0-9)、下划线(_)、连字符(-)
    safe_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', safe_name)

    # Step 4: 移除连续的下划线（美化）
    safe_name = re.sub(r'_+', '_', safe_name)

    # Step 5: 长度限制
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]

    # Step 6: 移除首尾下划线
    safe_name = safe_name.strip('_')

    # Step 7: 确保非空（防御性编程）
    if not safe_name:
        safe_name = "unnamed_entity"

    return safe_name


def sanitize_commit_message(message: str, max_length: int = 200) -> str:
    """
    清理Git提交消息，防止命令注入 (CWE-77)

    安全关键函数 - 修复backup_manager.py命令注入漏洞

    Args:
        message: 原始提交消息（可能包含Git标志）
        max_length: 消息最大长度（默认200字符）

    Returns:
        安全的提交消息（移除Git特殊标志和危险字符）

    示例:
        >>> sanitize_commit_message("Test\\n--author='Attacker'")
        'Test  author Attacker'
        >>> sanitize_commit_message("--amend Chapter 1")
        'amend Chapter 1'

    安全验证:
        - ✅ 防止多行注入（换行符）
        - ✅ 防止Git标志注入（--xxx）
        - ✅ 防止参数分隔符混淆（引号）
        - ✅ 防止单字母标志（-x）
    """
    # Step 1: 移除换行符（防止多行参数注入）
    safe_msg = message.replace('\n', ' ').replace('\r', ' ')

    # Step 2: 移除Git特殊标志（--开头的参数）
    safe_msg = re.sub(r'--[\w-]+', '', safe_msg)

    # Step 3: 移除引号（防止参数分隔符混淆）
    safe_msg = safe_msg.replace("'", "").replace('"', '')

    # Step 4: 移除前导的-（防止单字母标志如-m）
    safe_msg = safe_msg.lstrip('-')

    # Step 5: 移除连续空格（美化）
    safe_msg = re.sub(r'\s+', ' ', safe_msg)

    # Step 6: 长度限制
    if len(safe_msg) > max_length:
        safe_msg = safe_msg[:max_length]

    # Step 7: 移除首尾空格
    safe_msg = safe_msg.strip()

    # Step 8: 确保非空
    if not safe_msg:
        safe_msg = "Untitled commit"

    return safe_msg


def create_secure_directory(path: str, mode: int = 0o700) -> Path:
    """
    创建安全目录（仅所有者可访问）

    安全关键函数 - 修复文件权限配置缺失漏洞

    Args:
        path: 目录路径
        mode: 权限模式（默认0o700，仅所有者可读写执行）

    Returns:
        Path对象

    示例:
        >>> create_secure_directory('.webnovel')
        PosixPath('.webnovel')  # drwx------ (700)

    安全验证:
        - ✅ 仅所有者可访问（0o700）
        - ✅ 防止同组用户读取
        - ✅ 跨平台兼容（Windows/Linux/macOS）
    """
    path_obj = Path(path)

    # 创建目录（设置安全权限）
    os.makedirs(path, mode=mode, exist_ok=True)

    # 双重保险：显式设置权限（某些系统可能忽略makedirs的mode参数）
    if os.name != 'nt':  # Unix系统（Linux/macOS）
        os.chmod(path, mode)

    return path_obj


def create_secure_file(file_path: str, content: str, mode: int = 0o600) -> None:
    """
    创建安全文件（仅所有者可读写）

    Args:
        file_path: 文件路径
        content: 文件内容
        mode: 权限模式（默认0o600，仅所有者可读写）

    安全验证:
        - ✅ 仅所有者可读写（0o600）
        - ✅ 防止其他用户访问
    """
    # 创建文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 设置权限（仅Unix系统）
    if os.name != 'nt':
        os.chmod(file_path, mode)


def validate_integer_input(value: str, field_name: str) -> int:
    """
    验证并转换整数输入（严格模式）

    安全关键函数 - 修复update_state.py弱验证漏洞

    Args:
        value: 输入值（字符串）
        field_name: 字段名称（用于错误消息）

    Returns:
        转换后的整数

    Raises:
        ValueError: 输入不是有效整数

    示例:
        >>> validate_integer_input("123", "chapter_num")
        123
        >>> validate_integer_input("abc", "level")
        ValueError: ❌ 错误：level 必须是整数，收到: abc
    """
    try:
        return int(value)
    except ValueError:
        print(f"❌ 错误：{field_name} 必须是整数，收到: {value}", file=sys.stderr)
        raise ValueError(f"Invalid integer input for {field_name}: {value}")


# ============================================================================
# Git 环境检测（优雅降级支持）
# ============================================================================

# 缓存 Git 可用性检测结果
_git_available: Optional[bool] = None


def is_git_available() -> bool:
    """
    检测 Git 是否可用

    Returns:
        bool: Git 是否可用

    说明：
        - 检测结果会被缓存，避免重复检测
        - 用于支持在无 Git 环境下优雅降级
    """
    global _git_available

    if _git_available is not None:
        return _git_available

    import subprocess

    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        _git_available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _git_available = False

    return _git_available


def is_git_repo(path: Union[str, Path]) -> bool:
    """
    检测指定目录是否是 Git 仓库

    Args:
        path: 目录路径

    Returns:
        bool: 是否是 Git 仓库
    """
    if not is_git_available():
        return False

    path = Path(path)
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def git_graceful_operation(
    args: list,
    cwd: Union[str, Path],
    *,
    fallback_msg: str = "Git 不可用，跳过版本控制操作"
) -> tuple:
    """
    优雅执行 Git 操作（Git 不可用时静默降级）

    Args:
        args: Git 命令参数（不含 'git'）
        cwd: 工作目录
        fallback_msg: 降级时的提示消息

    Returns:
        (success: bool, output: str, was_skipped: bool)
        - success: 操作是否成功
        - output: 输出内容
        - was_skipped: 是否因 Git 不可用而跳过

    示例:
        >>> success, output, skipped = git_graceful_operation(
        ...     ["add", "."], cwd="/path/to/project"
        ... )
        >>> if skipped:
        ...     print("Git not available, using fallback")
    """
    if not is_git_available():
        print(f"⚠️  {fallback_msg}", file=sys.stderr)
        return False, "", True

    import subprocess

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=60
        )
        return result.returncode == 0, result.stdout, False
    except subprocess.TimeoutExpired:
        print(f"⚠️  Git 操作超时: git {' '.join(args)}", file=sys.stderr)
        return False, "", False
    except OSError as e:
        print(f"⚠️  Git 操作失败: {e}", file=sys.stderr)
        return False, "", False


# ============================================================================
# 原子化文件写入（防止并发冲突和数据损坏）
# ============================================================================


class AtomicWriteError(Exception):
    """原子写入失败异常"""
    pass


def atomic_write_json(
    file_path: Union[str, Path],
    data: Dict[str, Any],
    *,
    use_lock: bool = True,
    backup: bool = True,
    indent: int = 2
) -> None:
    """
    原子化写入 JSON 文件，防止并发冲突和数据损坏 (CWE-362, CWE-367)

    安全关键函数 - 修复 state.json 并发写入风险

    实现策略:
    1. 写入临时文件（同目录，确保同文件系统）
    2. 可选：使用 filelock 获取排他锁
    3. 可选：备份原文件
    4. 原子重命名（os.replace 在 POSIX 上是原子的）

    Args:
        file_path: 目标文件路径
        data: 要写入的字典数据
        use_lock: 是否使用文件锁（需要 filelock 库）
        backup: 是否在写入前备份原文件
        indent: JSON 缩进（默认 2）

    Raises:
        AtomicWriteError: 写入失败时抛出

    示例:
        >>> atomic_write_json('.webnovel/state.json', {'progress': {'chapter': 10}})

    安全验证:
        - ✅ 防止写入中断导致的数据损坏（先写临时文件）
        - ✅ 防止并发写入冲突（filelock）
        - ✅ 支持回滚（备份机制）
        - ✅ 跨平台兼容
    """
    file_path = Path(file_path)
    parent_dir = file_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    # 准备 JSON 内容
    try:
        json_content = json.dumps(data, ensure_ascii=False, indent=indent)
    except (TypeError, ValueError) as e:
        raise AtomicWriteError(f"JSON 序列化失败: {e}")

    # 锁文件路径
    lock_path = file_path.with_suffix(file_path.suffix + '.lock')
    backup_path = file_path.with_suffix(file_path.suffix + '.bak')

    # 创建临时文件（同目录确保同文件系统，os.replace 才能原子操作）
    fd, temp_path = tempfile.mkstemp(
        suffix='.tmp',
        prefix=file_path.stem + '_',
        dir=parent_dir
    )

    try:
        # Step 1: 写入临时文件
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json_content)
            f.flush()
            os.fsync(f.fileno())  # 确保写入磁盘

        # Step 2: 获取锁（如果可用且启用）
        lock = None
        if use_lock and HAS_FILELOCK:
            lock = FileLock(str(lock_path), timeout=10)
            lock.acquire()

        try:
            # Step 3: 备份原文件（如果存在且启用备份）
            if backup and file_path.exists():
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                except OSError:
                    pass  # 备份失败不阻止写入

            # Step 4: 原子重命名
            os.replace(temp_path, file_path)
            temp_path = None  # 标记已成功，不需要清理

        finally:
            if lock is not None:
                lock.release()

    except Exception as e:
        raise AtomicWriteError(f"原子写入失败: {e}")

    finally:
        # 清理：删除临时文件（如果仍存在说明写入失败）
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def read_json_safe(
    file_path: Union[str, Path],
    default: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    安全读取 JSON 文件（带默认值和错误处理）

    Args:
        file_path: 文件路径
        default: 文件不存在或解析失败时的默认值

    Returns:
        解析后的字典，或默认值

    示例:
        >>> state = read_json_safe('.webnovel/state.json', {})
    """
    file_path = Path(file_path)
    if default is None:
        default = {}

    if not file_path.exists():
        return default

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ 读取 JSON 失败 ({file_path}): {e}", file=sys.stderr)
        return default


def restore_from_backup(file_path: Union[str, Path]) -> bool:
    """
    从备份恢复文件

    Args:
        file_path: 原文件路径

    Returns:
        是否成功恢复

    示例:
        >>> restore_from_backup('.webnovel/state.json')
        True
    """
    file_path = Path(file_path)
    backup_path = file_path.with_suffix(file_path.suffix + '.bak')

    if not backup_path.exists():
        print(f"⚠️ 备份文件不存在: {backup_path}", file=sys.stderr)
        return False

    try:
        import shutil
        shutil.copy2(backup_path, file_path)
        print(f"✅ 已从备份恢复: {file_path}")
        return True
    except OSError as e:
        print(f"❌ 恢复失败: {e}", file=sys.stderr)
        return False


# ============================================================================
# 单元测试（内置自检）
# ============================================================================

def _run_self_tests():
    """运行内置安全测试"""
    print("🔍 运行安全工具函数自检...")

    # Test 1: sanitize_filename
    assert sanitize_filename("../../../etc/passwd") == "passwd", "路径遍历测试失败"
    assert sanitize_filename("C:\\Windows\\System32") == "System32", "Windows路径测试失败"
    assert sanitize_filename("正常角色名") == "正常角色名", "中文测试失败"
    assert sanitize_filename("/tmp/../../../../../etc/hosts") == "hosts", "复杂路径遍历测试失败"
    assert sanitize_filename("test///file...name") == "file_name", "特殊字符测试失败"  # . 会被替换
    print("  ✅ sanitize_filename: 所有测试通过")

    # Test 2: sanitize_commit_message
    result = sanitize_commit_message("Test\n--author='Attacker'")
    assert "\n" not in result, "换行符未移除"
    assert "--author" not in result, "Git标志未移除"
    assert "Attacker" in result, "内容被错误移除"

    assert sanitize_commit_message("--amend Chapter 1") == "Chapter 1", "Git标志测试失败"  # --amend被完全移除
    assert "'" not in sanitize_commit_message("Test'message"), "引号测试失败"
    assert sanitize_commit_message("-m Test") == "m Test", "单字母标志测试失败"  # -m被移除后是"m Test"
    print("  ✅ sanitize_commit_message: 所有测试通过")

    # Test 3: validate_integer_input
    assert validate_integer_input("123", "test") == 123, "整数验证测试失败"
    try:
        validate_integer_input("abc", "test")
        assert False, "应该抛出ValueError"
    except ValueError:
        pass
    print("  ✅ validate_integer_input: 所有测试通过")

    # Test 4: atomic_write_json
    import tempfile as tf
    test_dir = Path(tf.mkdtemp())
    test_file = test_dir / "test_state.json"

    # 写入测试
    test_data = {"chapter": 10, "中文键": "中文值"}
    atomic_write_json(test_file, test_data, use_lock=False, backup=False)
    assert test_file.exists(), "原子写入未创建文件"

    # 读取验证
    with open(test_file, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    assert loaded == test_data, "原子写入数据不匹配"

    # 备份测试
    atomic_write_json(test_file, {"updated": True}, use_lock=False, backup=True)
    backup_file = test_file.with_suffix('.json.bak')
    assert backup_file.exists(), "备份未创建"

    # 恢复测试
    restore_from_backup(test_file)
    with open(test_file, 'r', encoding='utf-8') as f:
        restored = json.load(f)
    assert restored == test_data, "恢复数据不匹配"

    # 清理
    import shutil
    shutil.rmtree(test_dir)
    print("  ✅ atomic_write_json: 所有测试通过")
    if HAS_FILELOCK:
        print("  ℹ️  filelock 可用，已启用文件锁支持")
    else:
        print("  ⚠️  filelock 未安装，文件锁功能不可用")

    print("\n✅ 所有安全工具函数测试通过！")


if __name__ == "__main__":
    # Windows UTF-8 编码修复（必须在打印前执行）
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # 运行自检测试
    _run_self_tests()
