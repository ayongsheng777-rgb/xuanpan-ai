"""把文档里的示例当测试跑 —— 文档与实现不一致是一种隐性缺陷。

为什么需要它：`geometric.otsu_threshold` 的 docstring 长期写着"阈值落在两类之间"，
而实现（`argmax` 取平台左端）返回的是紧贴暗类的一侧。因为 doctest 从未纳入
测试，这处不一致一直没被发现 —— 直到把示例真正执行了一次。

本项目大量使用 docstring 承载"为什么这样算"的说明，示例若与实现脱节，
读者（和后续的 AI 协作者）会被文档误导，故必须由测试守住。
"""

from __future__ import annotations

import doctest
import importlib
import pkgutil
from typing import Iterator

import pytest

#：需要校验 doctest 的包（顺序即报错顺序）
PACKAGES = ("fortune_core", "xuanpan_vision")


def _iter_modules(pkg_name: str) -> Iterator[object]:
    """包自身 + 其下所有子模块。"""
    pkg = importlib.import_module(pkg_name)
    yield pkg
    for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{pkg_name}."):
        try:
            yield importlib.import_module(info.name)
        except Exception as exc:  # pragma: no cover - 导入失败本身就是缺陷
            pytest.fail(f"导入 {info.name} 失败：{exc!r}")


@pytest.mark.parametrize("pkg_name", PACKAGES)
def test_docstring_examples_execute(pkg_name: str) -> None:
    failures: list[str] = []
    checked = 0

    for module in _iter_modules(pkg_name):
        result = doctest.testmod(module, verbose=False, report=False)  # type: ignore[arg-type]
        checked += result.attempted
        if result.failed:
            failures.append(f"{module.__name__}：{result.failed} 例失败")

    # 至少跑过一些示例，否则这条测试是"假绿"
    assert checked > 0, f"{pkg_name} 下没有收集到任何 doctest —— 检查是否被漏掉"
    assert not failures, "doctest 与实现不一致：" + "；".join(failures)
