""".env.example 自称「穷尽」，这条测试负责让那句话保持为真。

`.env.example` 开头写着「后端实际读取的全部 N 个环境变量都在这里」，
但此前没有任何机制保证它。新增一个环境变量却忘了同步该文件时，
部署方会以为「我配了」而实际走的是默认值 —— 而「配了没生效」与「用默认值」
在现象上完全一样，是最难排查的一类问题（本次新增 XUANPAN_ADMIN_TOKEN
就同时要改 config.py / .env.example / docker-compose.yml 三处）。

自「运行时可调配置」（`runtime_config.SPECS`）落地后，新增一个变量要看 **4 处**：
`config.py`（环境基线解析）、`runtime_config.SPECS`（注册表，决定能否从管理台改）、
`.env.example`（声明）、`docker-compose.yml`（透传进容器）。本测试守住第 3、4 处。

本测试**直接扫源码**而不是数数：数出来的结论第二天就会过期。
"""

from __future__ import annotations

import re
from pathlib import Path

ENV_EXAMPLE = Path(__file__).parents[2] / ".env.example"

#：代码里读取环境变量的写法。漏掉一种就会让某个变量隐形 ——
#：而"隐形"恰恰是本测试要防的东西，所以每一种都要覆盖。
_PATTERNS = (
    re.compile(r"os\.environ\.get\(\s*[\"'](XUANPAN_[A-Z0-9_]+)[\"']"),
    re.compile(r"os\.environ\[\s*[\"'](XUANPAN_[A-Z0-9_]+)[\"']"),
    re.compile(r"_env_(?:bool|int|float|str)\(\s*[\"'](XUANPAN_[A-Z0-9_]+)[\"']"),
    #：第四种：在 `runtime_config.SPECS` 注册表里声明（`env_var="XUANPAN_…"`）。
    #：读取发生在 `_baseline()` 的 `env.get(spec.env_var)`，变量名不再以字面量
    #：出现在 `os.environ` 调用里。少了这一条，**整套可调配置的变量都会被
    #：误判成"没人读"**，于是守卫会反过来逼人删掉 .env.example 里正确的条目。
    re.compile(r"env_var\s*=\s*[\"'](XUANPAN_[A-Z0-9_]+)[\"']"),
)


def _vars_read_in_code() -> dict[str, set[str]]:
    root = ENV_EXAMPLE.parent
    found: dict[str, set[str]] = {}
    for base in ("services", "packages", "scripts"):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in _PATTERNS:
                for name in pattern.findall(text):
                    found.setdefault(name, set()).add(str(path.relative_to(root)))
    return found


def _vars_declared_in_example() -> set[str]:
    declared: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)\s*=", line)
        if match:
            declared.add(match.group(1))
    return declared


def test_example_declares_every_variable_code_reads() -> None:
    """代码读取的每个变量都必须在 .env.example 里出现。"""
    used = _vars_read_in_code()
    declared = _vars_declared_in_example()

    missing = sorted(set(used) - declared)
    assert not missing, (
        "以下变量代码在读取，但 .env.example 未声明 —— "
        "部署时会静默走默认值，而这种现象与「配了但没生效」无法区分：\n"
        + "\n".join(f"  {name}  ← {', '.join(sorted(used[name]))}" for name in missing)
    )


def test_example_has_no_stale_variable() -> None:
    """.env.example 里不该留已经没人读的变量。

    过时条目会误导人去配置一个根本不生效的值，比缺条目更难发现。
    """
    stale = sorted(_vars_declared_in_example() - set(_vars_read_in_code()))
    assert not stale, f".env.example 声明了但代码未读取（疑似过时）：{stale}"


def test_declared_count_matches_claim() -> None:
    """文件开头自称的变量个数必须与实际一致。

    数字对不上时，读者会以为自己漏看了一段，而不是怀疑那句话说错了 ——
    所以这个数字本身也需要被守住。
    """
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    match = re.search(r"全部\s*(\d+)\s*个环境变量", text)
    assert match, ".env.example 开头那句「全部 N 个环境变量」不见了，请恢复或更新本测试"

    claimed = int(match.group(1))
    actual = len(_vars_declared_in_example())
    assert claimed == actual, f"文件自称 {claimed} 个环境变量，实际声明了 {actual} 个"


def test_compose_passes_through_every_secret_free_variable() -> None:
    """compose 必须把变量透传进容器，否则 .env 配了也不进容器。

    只查「容器里会被 env 覆盖」这类变量（如 XUANPAN_HOST 由 Dockerfile 固定），
    故这里只要求：在 .env.example 声明、且不属于 Dockerfile 已固定项的变量，
    都出现在 docker-compose.yml 的 environment 段里。
    """
    compose = (ENV_EXAMPLE.parent / "docker-compose.yml").read_text(encoding="utf-8")
    # Dockerfile 里已用 ENV 固定、compose 中另行显式赋值的几个不在此列
    fixed_elsewhere = {"XUANPAN_HOST", "XUANPAN_PORT", "XUANPAN_DB_PATH"}

    declared = _vars_declared_in_example()
    absent = sorted(
        name for name in declared
        if name not in fixed_elsewhere and f"{name}:" not in compose
    )
    # 进程级变量（__main__.py 读取）不需要进 compose
    process_level = {"XUANPAN_RELOAD"}
    absent = [name for name in absent if name not in process_level]

    assert not absent, (
        "以下变量在 .env.example 有声明，但 docker-compose.yml 没有透传 —— "
        f"容器里配不到：{absent}"
    )
