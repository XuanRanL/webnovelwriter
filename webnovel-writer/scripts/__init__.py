"""
webnovel-writer scripts package

This package contains all Python scripts for the webnovel-writer plugin.

注意：
- 采用延迟导入（lazy import），避免在包被 pytest 或其他工具通过
  scripts.data_modules.xxx 路径触发时，因 security_utils → runtime_compat
  的裸导入链在 scripts/ 不在 sys.path 时失败。
- 与 data_modules/__init__.py 保持一致的 lazy 模式。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "5.5.4"
__author__ = "lcy"

__all__ = [
    "security_utils",
    "project_locator",
    "chapter_paths",
]

_LAZY_SUBMODULES = {
    "security_utils": ".security_utils",
    "project_locator": ".project_locator",
    "chapter_paths": ".chapter_paths",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_SUBMODULES:
        raise AttributeError(name)
    module = import_module(_LAZY_SUBMODULES[name], __name__)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_LAZY_SUBMODULES.keys())))
