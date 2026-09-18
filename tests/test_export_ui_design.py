"""UI 设计导出脚本的守卫测试。

为什么需要它：导出包是给**外部智能体**看的材料，一旦缺页，收到包的一方会基于
不完整的信息下结论，而**双方都看不出问题** —— 这种缺失没有任何症状。
所以把「归档是否完整」从"跑一遍脚本看看"提升为可断言的契约。

这些用例全是静态检查（不写文件、不渲染、不联网），毫秒级。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "export_ui_design.py"
MOBILE = REPO / "apps" / "mobile"


@pytest.fixture(scope="module")
def exporter():
    """按文件路径加载导出脚本（scripts/ 不是包，不能直接 import）。"""
    if not SCRIPT.exists():
        pytest.skip("导出脚本不存在")
    spec = importlib.util.spec_from_file_location("export_ui_design", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # 必须先登记进 sys.modules：脚本里用了 @dataclass，而 dataclasses 在解析注解时
    # 会按 cls.__module__ 反查 sys.modules[..].__dict__ —— 不登记就抛
    # AttributeError: 'NoneType' object has no attribute '__dict__'，
    # 且报错位置在 dataclasses 内部，很难一眼看出是加载方式的问题。
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _sources_on_disk() -> set[str]:
    """界面代码全集：app/ 与 src/ 下的 .ts/.tsx（排除派生产物）。"""
    found: set[str] = set()
    for base in ("app", "src"):
        root = MOBILE / base
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
                continue
            if set(path.relative_to(MOBILE).parts) & {"node_modules", ".expo", "android", "ios"}:
                continue
            found.add(str(path.relative_to(MOBILE)).replace("\\", "/"))
    return found


def test_script_exists() -> None:
    assert SCRIPT.exists(), "导出脚本被删了？它是导出包的唯一生成入口"


def test_mobile_source_tree_is_readable() -> None:
    # 前置自检：如果源目录读不到，后面所有"无遗漏"的断言都会因为空集合而假绿
    assert len(_sources_on_disk()) >= 40, (
        f"只扫到 {len(_sources_on_disk())} 个界面源文件，明显少于预期 —— "
        "请先确认 apps/mobile 的目录结构与扫描逻辑是否还匹配"
    )


def test_all_sources_are_archived(exporter) -> None:
    """核心守卫：app/ 与 src/ 下不允许有未被任何一卷收录的源码。"""
    problems = exporter.assert_no_orphans()
    assert problems == [], "导出包会不完整：\n" + "\n".join(problems)


def test_volume_files_are_claimed_by_scan(exporter) -> None:
    """反向守卫：卷里声明的每个文件都必须真实存在于磁盘。

    与上一条的区别：上一条防"漏收"，这一条防"声明了不存在的文件"——
    后者会让导出脚本在运行时才报错，属于把失败推迟到了使用者手里。
    """
    declared = {f for vol in exporter.VOLUMES for f in vol.files}
    on_disk = _sources_on_disk()
    stale = sorted(declared - on_disk)
    assert stale == [], f"以下文件被卷声明但磁盘上不存在：{stale}"


def test_slugs_are_unique_and_numbered(exporter) -> None:
    """卷名必须是「两位数字-短横-名字」且唯一。

    编号不是装饰：导出的文件名靠它排序，重名或格式不一会让包里的顺序随机化，
    而收件方是按文件名顺序读的。
    """
    slugs = [vol.slug for vol in exporter.VOLUMES]
    assert len(slugs) == len(set(slugs)), f"卷名重复：{slugs}"
    bad = [s for s in slugs if not (len(s) > 3 and s[:2].isdigit() and s[2] == "-")]
    assert bad == [], f"卷名不符合「NN-name」约定：{bad}"


def test_no_file_is_claimed_twice(exporter) -> None:
    """同一文件不得出现在两卷里。

    重复归档会让包里出现两份同名代码，而其中一份很可能在后续更新时被漏掉 ——
    于是同一路径在同一个包里有两个版本。
    """
    seen: dict[str, str] = {}
    dupes: list[str] = []
    for vol in exporter.VOLUMES:
        for rel in vol.files:
            if rel in seen:
                dupes.append(f"{rel}（{seen[rel]} 与 {vol.slug}）")
            seen[rel] = vol.slug
    assert dupes == [], f"同一文件被多卷收录：{dupes}"


def test_every_volume_is_non_empty(exporter) -> None:
    empty = [vol.slug for vol in exporter.VOLUMES if not vol.files]
    assert empty == [], f"空卷会被生成成一个只有标题的文件：{empty}"


def test_intro_doc_exists() -> None:
    """导出的包必须有导读 —— 缺了它，收件方只能自己从 15,000 行源码里猜设计意图。"""
    assert exporter_path_intro().exists(), (
        "缺少导读源文档 docs/玄盘 AI — UI 设计导出导读.md；"
        "导出包会没有 README.md 入口"
    )


def exporter_path_intro() -> Path:
    return REPO / "docs" / "玄盘 AI — UI 设计导出导读.md"
