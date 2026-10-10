"""后端地址持久化 —— 真跑 `src/api/baseUrlStore.ts` 的行为校验。

## 为什么需要它

2026-10-08 用户实报 BUG 1：「我的 → 网络线路」里改的后端地址，
App 重启就丢 —— `setApiBaseUrl` 原来只换内存单例，从不写盘。

扫源码只能证明"写了 setItem 这行字"，证明不了"读回来的确实是
写进去的那个"。本测试真正**执行** `baseUrlStore.ts`（Node 类型擦除，
无依赖），用内存假存储走一遍 存 → 读 → 覆盖 → 清除 完整链路。

没有 Node 时跳过（而不是失败）：见 test_ring24_parity.py 的同款说明。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/baseurl_store_probe.ts"


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过后端地址持久化校验")
    if not _PROBE.exists():
        pytest.skip(f"未找到探针脚本：{_PROBE}")

    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=60,
    )
    if proc.returncode != 0:
        pytest.fail(
            "baseUrlStore 探针执行失败（可能是 baseUrlStore.ts 有语法/类型错误）：\n"
            f"{proc.stderr.strip()[:2000]}"
        )
    try:
        # 探针可能先打一条 Node 的模块类型警告到 stderr，stdout 只有最后一行 JSON
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        return json.loads(lines[-1])
    except (json.JSONDecodeError, IndexError) as exc:  # pragma: no cover
        pytest.fail(f"探针输出不是合法 JSON：{exc}\n原始输出前 500 字：{proc.stdout[:500]}")


def test_override_key_is_stable(probe: dict) -> None:
    """存储 key 稳定 —— 改 key 会导致老用户存的地址读不回来，视为破坏性变更。"""
    assert probe["key"] == "@xuanpan:api_base_url"


def test_empty_storage_reads_null(probe: dict) -> None:
    """没设过地址时读出来是 null —— 调用方据此决定走自动探活。"""
    assert probe["empty_read_is_null"] is True


def test_roundtrip_same_url(probe: dict) -> None:
    """BUG 1 的核心回归：存进去的地址，读回来必须是同一个。"""
    assert probe["roundtrip"] == "http://192.168.1.10:8360"


def test_trailing_slashes_normalized(probe: dict) -> None:
    """尾斜杠在写入时规范化掉 —— 避免 'http://x:8360/' 与 'http://x:8360'
    被当成两个地址，或拼出双斜杠路径。"""
    assert probe["stored_raw"] == "http://192.168.1.10:8360"


def test_overwrite_wins(probe: dict) -> None:
    """用户改第二次地址时，后写的覆盖先写的。"""
    assert probe["overwrite"] == "http://10.0.0.5:8360"


def test_clear_removes_override(probe: dict) -> None:
    """「恢复默认」后读出来是 null —— 下次启动回到自动探活。"""
    assert probe["after_clear_is_null"] is True


def test_blank_url_treated_as_no_override(probe: dict) -> None:
    """存了空字符串当作没设 —— 不允许出现空地址的客户端。"""
    assert probe["blank_is_null"] is True


def test_broken_storage_never_throws(probe: dict) -> None:
    """存储坏了（磁盘异常）也不炸：读返回 null，清不抛异常。

    这是 BUG 1 修法里的刻意取舍 —— 存盘失败不能把一次成功的
    「测试并应用」变成报错，读失败就当没设过，走自动探活。
    """
    assert probe["broken_read_threw"] is False
    assert probe["broken_read_is_null"] is True
    assert probe["broken_clear_threw"] is False
