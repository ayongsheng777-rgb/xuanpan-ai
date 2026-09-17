"""奇门遁甲 —— 固定属性表与局数表。

对应 RULE-005：术数规则不得散落在 UI 或 Prompt 中，必须集中在本模块。
本模块只放**固定属性**；流派相关项（拆补法 / 置闰法、八神名目）在 `pan.py` 显式声明。

可信度标注：

- `[已确认]` 洛书九宫配卦、九星配宫、八门配宫、三奇六仪顺序、
  节气上元局数表 —— 古籍通行，且已与多个独立开源实现逐宫对拍一致
  （对拍锚点见 `tests/test_qimen.py`）
- `[待验证]` 八神名目存在两派（「白虎 + 玄武」与「勾陈 + 朱雀」），
  本模块取前者；三元起算「交节当日算第 1 天」亦属流派口径
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# 洛书九宫
# --------------------------------------------------------------------------

#: 宫序 -> 卦名。**这是奇门的地盘序号**，与「后天八卦数」一致：
#:
#:     巽4   离9   坤2
#:     震3   中5   兑7
#:     艮8   坎1   乾6
GONG_GUA: Final[dict[int, str]] = {
    1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离",
}

#: 宫序 -> 方位
GONG_DIRECTION: Final[dict[int, str]] = {
    1: "北", 2: "西南", 3: "东", 4: "东南", 5: "中", 6: "西北", 7: "西", 8: "东北", 9: "南",
}

#: 宫序 -> 五行
GONG_ELEMENT: Final[dict[int, str]] = {
    1: "water", 2: "earth", 3: "wood", 4: "wood", 5: "earth",
    6: "metal", 7: "metal", 8: "earth", 9: "fire",
}

#: 九宫在盘面上的行列表格位置（用于渲染 ASCII 盘面 / 前端九宫格）
GONG_GRID_POS: Final[dict[int, tuple[int, int]]] = {
    4: (0, 0), 9: (0, 1), 2: (0, 2),
    3: (1, 0), 5: (1, 1), 7: (1, 2),
    8: (2, 0), 1: (2, 1), 6: (2, 2),
}

#: 外八宫沿**顺时针**排列的环序。天盘/九星/八门/八神都沿此环转动。
#:
#: 坎1 → 艮8 → 震3 → 巽4 → 离9 → 坤2 → 兑7 → 乾6 → 回到坎1
#: （对应盘面：下中 → 左下 → 左中 → 左上 → 上中 → 右上 → 右中 → 右下）
RING_ORDER: Final[tuple[int, ...]] = (1, 8, 3, 4, 9, 2, 7, 6)

#: 中宫寄坤 —— 中五宫无门无星（天禽寄坤二宫）
CENTER_PALACE: Final[int] = 5
CENTER_HOST: Final[int] = 2

# --------------------------------------------------------------------------
# 三奇六仪
# --------------------------------------------------------------------------

#: 地盘布局顺序：**六仪在前、三奇在后**。
#: 甲隐于六仪之下（甲子戊、甲戌己、甲申庚、甲午辛、甲辰壬、甲寅癸），
#: 故盘面上**看不到「甲」**。
LIUYI: Final[tuple[str, ...]] = ("戊", "己", "庚", "辛", "壬", "癸")
SANQI: Final[tuple[str, ...]] = ("丁", "丙", "乙")
Qiyi_ORDER: Final[tuple[str, ...]] = LIUYI + SANQI

#: 旬首（六甲）-> 所隐之仪。用于快速由旬首取「值符」所依之干。
XUNSHOU_TO_YI: Final[dict[str, str]] = {
    "甲子": "戊", "甲戌": "己", "甲申": "庚",
    "甲午": "辛", "甲辰": "壬", "甲寅": "癸",
}

#: 六仪 -> 所隐之旬首（反向查表）
YI_TO_XUNSHOU: Final[dict[str, str]] = {v: k for k, v in XUNSHOU_TO_YI.items()}

#: 天干 -> 五行（本地复用，避免与根 constants 循环导入）
GAN_ELEMENT: Final[dict[str, str]] = {
    "甲": "wood", "乙": "wood", "丙": "fire", "丁": "fire", "戊": "earth",
    "己": "earth", "庚": "metal", "辛": "metal", "壬": "water", "癸": "water",
}

# --------------------------------------------------------------------------
# 九星 / 八门 / 八神
# --------------------------------------------------------------------------

#: 九星「原位」——按宫序。值符星 = 旬首所落宫的原始九星。
JIUXING_BY_GONG: Final[dict[int, str]] = {
    1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽",
    6: "天心", 7: "天柱", 8: "天任", 9: "天英",
}

#: 八门「原位」——按宫序。值使门 = 旬首所落宫的原始八门。
#: 中五宫无门（寄坤二宫）。
BAMEN_BY_GONG: Final[dict[int, str]] = {
    1: "休门", 2: "死门", 3: "伤门", 4: "杜门",
    6: "开门", 7: "惊门", 8: "生门", 9: "景门",
}

#: 八门吉凶（[已确认] 通行说法）
BAMEN_JIXIONG: Final[dict[str, str]] = {
    "开门": "吉", "休门": "吉", "生门": "吉",
    "景门": "平",
    "杜门": "凶", "伤门": "凶", "惊门": "凶", "死门": "凶",
}

#: 九星吉凶（[待验证] 各派略有出入，此处取通行说法）
JIUXING_JIXIONG: Final[dict[str, str]] = {
    "天心": "吉", "天任": "吉", "天辅": "吉", "天禽": "吉",
    "天冲": "平", "天英": "平",
    "天蓬": "凶", "天芮": "凶", "天柱": "凶",
}

#: 八神顺序（阳遁顺布、阴遁逆布）。
#: [待验证] 流派差异：部分体系把「白虎 / 玄武」写作「勾陈 / 朱雀」。
BASHEN_ORDER: Final[tuple[str, ...]] = (
    "值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天",
)

#: 八神别名（另一派名目），供 UI 在流派切换时展示
BASHEN_ALIAS: Final[dict[str, str]] = {
    "白虎": "勾陈", "玄武": "朱雀",
}

# --------------------------------------------------------------------------
# 驿马 / 旬空
# --------------------------------------------------------------------------

#: 三合局 -> 驿马所在地支（申子辰马在寅，寅午戌马在申，巳酉丑马在亥，亥卯未马在巳）
YIMA_BY_SANHE: Final[dict[tuple[str, ...], str]] = {
    ("申", "子", "辰"): "寅",
    ("寅", "午", "戌"): "申",
    ("巳", "酉", "丑"): "亥",
    ("亥", "卯", "未"): "巳",
}

# --------------------------------------------------------------------------
# 二十四节气局数表
# --------------------------------------------------------------------------

#: 冬至 → 芒种为**阳遁**
YANG_DUN_JIEQI: Final[tuple[str, ...]] = (
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
)

#: 夏至 → 大雪为**阴遁**
YIN_DUN_JIEQI: Final[tuple[str, ...]] = (
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
)

#: 各节气的**上元局数**（[已确认] 通行局数表）。
#: 中元 / 下元由 `jushu_table()` 按固定偏移派生 —— 不手抄第二、三列，
#: 避免「上元对了、中元抄错」这类最难发现的错误。
SHANGYUAN_JUSHU: Final[dict[str, int]] = {
    # 阳遁
    "冬至": 1, "小寒": 2, "大寒": 3,
    "立春": 8, "雨水": 9, "惊蛰": 1,
    "春分": 3, "清明": 4, "谷雨": 5,
    "立夏": 4, "小满": 5, "芒种": 6,
    # 阴遁
    "夏至": 9, "小暑": 8, "大暑": 7,
    "立秋": 2, "处暑": 1, "白露": 9,
    "秋分": 7, "寒露": 6, "霜降": 5,
    "立冬": 6, "小雪": 5, "大雪": 4,
}

#: 三元偏移：阳遁「中元 +6、下元 +3」，阴遁反是。
#: 规则来源：对 24 节气逐一验算（如冬至上元 1 → 中元 7 → 下元 4）。
_YANG_OFFSETS: Final[tuple[int, int]] = (6, 3)
_YIN_OFFSETS: Final[tuple[int, int]] = (3, 6)


def _wrap9(n: int) -> int:
    """把局数归一到 1~9（超 9 减 9）。

    >>> _wrap9(7), _wrap9(10), _wrap9(15)
    (7, 1, 6)
    """
    return (n - 1) % 9 + 1


def is_yang_dun(jieqi: str) -> bool:
    """该节气是否属阳遁。未知节气抛 `ValueError`。"""
    if jieqi in YANG_DUN_JIEQI:
        return True
    if jieqi in YIN_DUN_JIEQI:
        return False
    raise ValueError(f"未知节气：{jieqi!r}")


def jushu_of(jieqi: str, yuan: int) -> int:
    """节气 + 元（1=上元 / 2=中元 / 3=下元）→ 局数（1~9）。

    >>> jushu_of("冬至", 1), jushu_of("冬至", 2), jushu_of("冬至", 3)
    (1, 7, 4)
    >>> jushu_of("夏至", 1), jushu_of("夏至", 2), jushu_of("夏至", 3)
    (9, 3, 6)
    """
    if jieqi not in SHANGYUAN_JUSHU:
        raise ValueError(f"未知节气：{jieqi!r}")
    if yuan not in (1, 2, 3):
        raise ValueError(f"元必须是 1/2/3，得到 {yuan!r}")
    shang = SHANGYUAN_JUSHU[jieqi]
    if yuan == 1:
        return shang
    offsets = _YANG_OFFSETS if is_yang_dun(jieqi) else _YIN_OFFSETS
    return _wrap9(shang + offsets[yuan - 2])


def jushu_table() -> dict[str, tuple[int, int, int]]:
    """完整局数表：节气 -> (上元, 中元, 下元)。供 UI 展示与测试对拍。"""
    return {
        jq: (jushu_of(jq, 1), jushu_of(jq, 2), jushu_of(jq, 3))
        for jq in SHANGYUAN_JUSHU
    }


__all__ = [
    "GONG_GUA", "GONG_DIRECTION", "GONG_ELEMENT", "GONG_GRID_POS", "RING_ORDER",
    "CENTER_PALACE", "CENTER_HOST",
    "LIUYI", "SANQI", "Qiyi_ORDER", "XUNSHOU_TO_YI", "YI_TO_XUNSHOU", "GAN_ELEMENT",
    "JIUXING_BY_GONG", "BAMEN_BY_GONG", "BAMEN_JIXIONG", "JIUXING_JIXIONG",
    "BASHEN_ORDER", "BASHEN_ALIAS",
    "YIMA_BY_SANHE",
    "YANG_DUN_JIEQI", "YIN_DUN_JIEQI", "SHANGYUAN_JUSHU",
    "is_yang_dun", "jushu_of", "jushu_table",
]
