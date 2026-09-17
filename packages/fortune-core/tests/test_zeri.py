"""择日决策测试 —— 用独立复算与真实锚点验证筛选逻辑。

测试策略（RULE-007 / RULE-009，不复制被测实现）：

1. **锚点 + 前提复算**：测试硬编码真实日期做锚点，同时**独立重算该日的黄历值**
   并断言前提成立。若 lunar-python 或历法数据变化，测试会**明确失败**，
   而不是静默换一组条件继续通过。

2. **评分独立复算**：从规则表读取权重，按公式独立算出分数，与
   `evaluate_day` 的结果比对 —— 验证「实现是否正确应用了规则表」。

3. **否决不变量**：忌项命中 / 诸事不宜 / 破日 / 生肖相冲 → 必为「不宜」，
   且**不因高分翻案**。

4. **规则表词目真实性**：事件表的每个 yi/ji 词，都必须在 366 天实测中
   被 lunar-python 真实发出过 —— 防止造词导致的「死规则」。
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from fortune_core import (
    evaluate_day,
    list_zeri_events,
    list_zeri_schools,
    select_auspicious_days,
)
from fortune_core.almanac import calculate_almanac
from fortune_core.exceptions import (
    DomainDataMissingError,
    InvalidInputError,
    SchoolNotFoundError,
)
from fortune_core.zeri import (
    GRADE_BUXUAN,
    GRADE_CIJI,
    GRADE_JI,
    GRADE_PING,
    MAX_RANGE_DAYS,
    VETO_CHONG,
    VETO_JI_HIT,
    VETO_PO_DAY,
    VETO_YU_SHI,
    VETO_ZHU_SHI,
    load_zeri_table,
)

# ---------------------------------------------------------------------------
# 真实锚点（[已确认] 由探针实测取得，测试内会再次复算前提）
# ---------------------------------------------------------------------------

# A: 忌嫁给/开市/入宅/动土/安葬 + 宜含「馀事勿取」，开日、天德黄道、宿亢凶、冲牛
DAY_A = date(2026, 9, 18)
# B: 破日 + 宜「诸事不宜」，但天神金匮（黄道）、宿箕（吉）—— 用于验证「高分不翻案」
DAY_B = date(2024, 6, 5)
# C: 宜含「馀事勿取」且宜命中「安葬」，忌不含安葬 —— 用于验证条件否决不误杀
DAY_C = date(2024, 1, 4)
# D: 嫁娶满分级（宜嫁娶 + 黄道 + 宿吉 + 除日 + 吉神8）
DAY_D = date(2026, 12, 17)
# E: 冲羊且忌不含嫁娶 —— 用于验证生肖相冲否决
DAY_E = date(2026, 10, 6)
# F: 宜安葬 + 启钻，黑道 + 宿凶（用于验证正向命中与减分并存）
DAY_F = date(2026, 1, 4)


def _alm_facts(d: date) -> dict:
    return calculate_almanac(d).to_facts()


# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------


class TestZeriTable:
    def test_table_loads_with_events_and_default_school(self) -> None:
        table = load_zeri_table()
        assert "events" in table and "schools" in table
        assert "default" in table["schools"]
        assert len(table["events"]) == 17

    def test_list_events_covers_expected_keys(self) -> None:
        events = list_zeri_events()
        keys = {e["event"] for e in events}
        for expected in ("jiaqu", "kaiye", "dongtu", "yiru", "anzang"):
            assert expected in keys
        # 每个事件都带 label 与非空 yi
        for e in events:
            assert e["label"] and e["yi"]

    def test_list_schools_carries_unverified_notes(self) -> None:
        schools = list_zeri_schools()
        assert schools[0]["id"] == "default"
        # RULE-006：流派必须显式声明未覆盖项，供上层生成免责标注
        assert schools[0]["unverified"]

    def test_missing_table_raises_domain_data_missing(self, tmp_path) -> None:
        """规则表缺失必须显式报错，不得凭理论推算（RULE-001）。"""
        with pytest.raises(DomainDataMissingError):
            load_zeri_table(str(tmp_path / "not-exist.json"))

    def test_malformed_table_raises_value_error(self, tmp_path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"events": {}, "schools": {}}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_zeri_table(str(bad))

    def test_incomplete_jianchu_tier_rejected(self, tmp_path) -> None:
        """建除档位必须覆盖十二神，否则会静默按「平」处理。"""
        p = tmp_path / "t.json"
        p.write_text(json.dumps({
            "events": {"jiaqu": {"label": "嫁娶", "yi": ["嫁娶"], "ji": ["嫁娶"]}},
            "schools": {"default": {"name": "x", "jianchu_tier": {"建": "平"},
                                    "weights": {}, "grade_thresholds": {"吉": 6, "次吉": 3}}},
        }), encoding="utf-8")
        with pytest.raises(ValueError, match="建除十二神"):
            load_zeri_table(str(p))

    def test_unknown_event_raises_with_available_list(self) -> None:
        with pytest.raises(InvalidInputError, match="未注册的择日事件"):
            evaluate_day("not_an_event", date(2026, 1, 1))

    def test_unknown_school_raises(self) -> None:
        with pytest.raises(SchoolNotFoundError):
            evaluate_day("jiaqu", date(2026, 1, 1), school="sanhe")

    def test_invalid_shengxiao_raises(self) -> None:
        with pytest.raises(InvalidInputError, match="非法属相"):
            evaluate_day("jiaqu", date(2026, 1, 1), shengxiao="猫")


class TestRuleTableWordsAreReal:
    """RULE-001：事件词目必须来自 lunar-python 真实发出的宜忌词汇。"""

    def test_every_event_word_is_emitted_by_calendar(self) -> None:
        from lunar_python import Solar

        yi_all: set[str] = set()
        ji_all: set[str] = set()
        d0 = date(2024, 1, 1)
        for i in range(366):
            d = d0 + timedelta(days=i)
            lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
            yi_all |= set(lunar.getDayYi())
            ji_all |= set(lunar.getDayJi())

        table = load_zeri_table()
        for key, ev in table["events"].items():
            for w in ev["yi"]:
                assert w in yi_all, f"[{key}] 宜词 {w!r} 不在真实宜词表中（疑似造词）"
            for w in ev["ji"]:
                assert w in ji_all, f"[{key}] 忌词 {w!r} 不在真实忌词表中（疑似造词）"

    def test_no_word_appears_in_both_yi_and_ji(self) -> None:
        """前提守卫：同词既宜又忌会让「忌优先」的 veto 产生歧义。

        经实测为 0 例。若本测试失败，说明历法数据或库行为变了，
        必须重新设计否决规则，而不是让歧义悄悄存在。
        """
        from lunar_python import Solar

        d0 = date(2024, 1, 1)
        conflicts = []
        for i in range(366):
            d = d0 + timedelta(days=i)
            lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
            both = set(lunar.getDayYi()) & set(lunar.getDayJi())
            if both:
                conflicts.append((d.isoformat(), sorted(both)))
        assert conflicts == []


# ---------------------------------------------------------------------------
# 单日评价 —— 否决不变量
# ---------------------------------------------------------------------------


class TestEvaluateDayVeto:
    def test_ji_hit_vetoes(self) -> None:
        """2026-09-18 忌含「嫁娶」→ 嫁娶必为不宜。"""
        f = _alm_facts(DAY_A)
        assert "嫁娶" in f["ji"], "锚点前提失效：该日忌项中应含「嫁娶」"

        d = evaluate_day("jiaqu", DAY_A)
        assert d.grade == GRADE_BUXUAN
        assert not d.is_usable
        assert d.matched_ji == ("嫁娶",)
        assert VETO_JI_HIT in d.veto_kinds

    def test_zhushi_buyi_vetoes_every_event(self) -> None:
        """2024-06-05 宜「诸事不宜」→ 任意事件均不宜。"""
        f = _alm_facts(DAY_B)
        assert f["yi"] == ["诸事不宜"], "锚点前提失效"

        for event in ("jiaqu", "kaiye", "anzang", "chuxing"):
            d = evaluate_day(event, DAY_B)
            assert d.grade == GRADE_BUXUAN
            assert VETO_ZHU_SHI in d.veto_kinds

    def test_high_score_does_not_override_veto(self) -> None:
        """2024-06-05 同时是黄道 + 宿吉 + 高分，但破日+诸事不宜 → 仍为不宜。"""
        d = evaluate_day("jiaqu", DAY_B)
        # 前提：该日确实拿到了正分（黄道 +2、宿吉 +1），说明 veto 压过了高分
        assert d.score > 0, "锚点前提失效：该日应有正向加分"
        assert d.grade == GRADE_BUXUAN
        assert VETO_PO_DAY in d.veto_kinds
        assert VETO_ZHU_SHI in d.veto_kinds

    def test_po_day_vetoed(self) -> None:
        """破日属规则表 veto_jianchu，无条件否决。"""
        d = evaluate_day("chuxing", DAY_B)
        assert VETO_PO_DAY in d.veto_kinds

    def test_yushi_wuqu_vetoes_only_without_yi_hit(self) -> None:
        """「馀事勿取」的条件否决边界。

        DAY_A：宜含「馀事勿取」且嫁娶无宜项命中 → 应被此项否决。
        DAY_C：宜含「馀事勿取」但安葬**有**宜项命中 → **不应**因该项否决。
        """
        fa = _alm_facts(DAY_A)
        assert "馀事勿取" in fa["yi"], "锚点 A 前提失效"
        assert "嫁娶" not in fa["yi"], "锚点 A 前提失效：嫁娶不应在宜项中"
        assert VETO_YU_SHI in evaluate_day("jiaqu", DAY_A).veto_kinds

        fc = _alm_facts(DAY_C)
        assert "馀事勿取" in fc["yi"] and "安葬" in fc["yi"], "锚点 C 前提失效"
        d_c = evaluate_day("anzang", DAY_C)
        assert VETO_YU_SHI not in d_c.veto_kinds
        assert d_c.matched_yi == ("安葬",)
        assert d_c.is_usable

    def test_shengxiao_chong_vetoes(self) -> None:
        """生肖相冲否决：仅在显式提供属相时生效。"""
        f = _alm_facts(DAY_E)
        assert f["chong"]["shengxiao"] == "羊", "锚点 E 前提失效"
        assert "嫁娶" not in f["ji"], "锚点 E 前提失效：该日忌项不应含嫁娶（否则无法隔离冲的效应）"

        no_sx = evaluate_day("jiaqu", DAY_E)
        assert VETO_CHONG not in no_sx.veto_kinds

        with_sx = evaluate_day("jiaqu", DAY_E, shengxiao="羊")
        assert with_sx.grade == GRADE_BUXUAN
        assert VETO_CHONG in with_sx.veto_kinds

        # 换成不冲的属相则不受此项影响
        other = evaluate_day("jiaqu", DAY_E, shengxiao="鼠")
        assert VETO_CHONG not in other.veto_kinds

    def test_veto_reasons_are_readable(self) -> None:
        d = evaluate_day("jiaqu", DAY_A)
        assert d.veto, "被否决的日子必须给出可读原因"
        assert any("嫁娶" in v for v in d.veto)
        assert any(v.startswith("否决：") for v in d.reasons)


# ---------------------------------------------------------------------------
# 单日评价 —— 评分与分级
# ---------------------------------------------------------------------------


class TestEvaluateDayScoring:
    def test_score_matches_independent_recomputation(self) -> None:
        """按规则表权重独立复算评分，与实现结果比对。"""
        table = load_zeri_table()
        prof = table["schools"]["default"]
        w = prof["weights"]
        many = prof["many_threshold"]

        for event, d in (("jiaqu", DAY_D), ("anzang", DAY_F), ("kaiye", DAY_A)):
            f = _alm_facts(d)
            ev = table["events"][event]
            matched_yi = [x for x in f["yi"] if x in ev["yi"]]
            tier = prof["jianchu_tier"][f["jian_chu"]]

            expect = 0
            if matched_yi:
                expect += w["yi_hit"]
            expect += w["huang_dao"] if f["tian_shen"]["type"] == "黄道" else w["hei_dao"]
            expect += w["xiu_ji"] if f["xiu"]["luck"] == "吉" else w["xiu_xiong"]
            tier_key = {"吉": "jianchu_ji", "次吉": "jianchu_ciji", "凶": "jianchu_xiong"}.get(tier)
            if tier_key:
                expect += w[tier_key]
            if len(f["ji_shen"]) >= many:
                expect += w["many_ji_shen"]
            if len(f["xiong_sha"]) >= many:
                expect += w["many_xiong_sha"]

            got = evaluate_day(event, d)
            assert got.score == expect, f"{event}@{d} 评分复算不符：实现 {got.score} vs 独立算 {expect}"

    def test_full_score_day_graded_ji(self) -> None:
        """2026-12-17：宜嫁娶 + 黄道 + 宿吉 + 除日 + 吉神充足 → 满分级。"""
        f = _alm_facts(DAY_D)
        assert "嫁娶" in f["yi"], "锚点 D 前提失效"
        assert "嫁娶" not in f["ji"], "锚点 D 前提失效"
        assert f["tian_shen"]["type"] == "黄道"
        assert f["xiu"]["luck"] == "吉"
        assert f["jian_chu"] == "除"

        d = evaluate_day("jiaqu", DAY_D)
        assert d.grade == GRADE_JI
        assert d.score >= 6
        assert d.is_usable

    def test_grade_boundaries(self) -> None:
        """分级边界：>=6 吉；>=3 次吉；否则平（由规则表阈值驱动）。"""
        table = load_zeri_table()
        th = table["schools"]["default"]["grade_thresholds"]

        # 扫描一段区间，覆盖到三种非否决分级，验证边界一致性
        seen = set()
        d0 = date(2026, 3, 1)
        for i in range(120):
            d = evaluate_day("jiaqu", d0 + timedelta(days=i))
            if not d.is_usable:
                continue
            seen.add(d.grade)
            if d.score >= th["吉"]:
                assert d.grade == GRADE_JI
            elif d.score >= th["次吉"]:
                assert d.grade == GRADE_CIJI
            else:
                assert d.grade == GRADE_PING
        assert {GRADE_JI, GRADE_CIJI, GRADE_PING} <= seen, f"样本未覆盖全部分级：{seen}"

    def test_positive_hit_adds_score(self) -> None:
        """2026-01-04 宜含安葬/启钻 → 正向命中加分（同时黑道+宿凶在减分）。"""
        f = _alm_facts(DAY_F)
        assert "安葬" in f["yi"], "锚点 F 前提失效"
        assert "安葬" not in f["ji"], "锚点 F 前提失效"

        d = evaluate_day("anzang", DAY_F)
        assert set(d.matched_yi) == {"安葬", "启钻"}
        assert d.is_usable
        assert any("宜项命中" in r for r in d.reasons)

    def test_grade_vocabulary_has_no_absolute_claims(self) -> None:
        """输出分级只允许四档，不得出现「大吉」「必」等绝对化断语。"""
        allowed = {GRADE_JI, GRADE_CIJI, GRADE_PING, GRADE_BUXUAN}
        d = evaluate_day("jiaqu", DAY_D)
        assert d.grade in allowed
        text = "".join(d.reasons)
        for word in ("大吉", "大利", "必有", "一定", "绝对"):
            assert word not in text


# ---------------------------------------------------------------------------
# 区间筛选
# ---------------------------------------------------------------------------


class TestSelectAuspiciousDays:
    def test_backfill_anchor_marriage_range(self) -> None:
        """2026-10-01~12-31 嫁娶：应给出候选，且最高分锚点为 2026-12-17。"""
        r = select_auspicious_days("jiaqu", "2026-10-01", "2026-12-31", limit=10)
        assert r.days_scanned == 92
        assert r.has_candidates
        assert r.best is not None
        assert r.best.solar_date == "2026-12-17"
        assert r.event_label == "嫁娶"

    def test_candidates_sorted_by_score_desc(self) -> None:
        r = select_auspicious_days("kaiye", "2026-01-01", "2026-06-30", limit=20)
        scores = [c.score for c in r.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_candidates_are_usable_by_default(self) -> None:
        r = select_auspicious_days("jiaqu", "2026-01-01", "2026-03-31", limit=50)
        assert all(c.is_usable for c in r.candidates)
        assert all(c.grade != GRADE_BUXUAN for c in r.candidates)

    def test_include_unfavorable_returns_all_days(self) -> None:
        r = select_auspicious_days(
            "jiaqu", "2026-01-01", "2026-02-28", limit=0, include_unfavorable=True
        )
        assert len(r.candidates) == r.days_scanned == 59

    def test_excluded_count_is_partition_of_scanned(self) -> None:
        r = select_auspicious_days("jiaqu", "2026-01-01", "2026-03-31", limit=0)
        usable = len(r.candidates)
        assert usable + r.excluded_count == r.days_scanned

    def test_limit_is_respected(self) -> None:
        r = select_auspicious_days("jiaqu", "2026-01-01", "2026-12-31", limit=3)
        assert len(r.candidates) == 3
        assert r.limit == 3

    def test_range_is_inclusive_of_both_ends(self) -> None:
        r = select_auspicious_days("jiaqu", "2026-05-01", "2026-05-01", limit=0)
        assert r.days_scanned == 1
        assert r.start == r.end == "2026-05-01"

    def test_no_candidate_is_a_valid_result(self) -> None:
        """2024-06-05（诸事不宜 + 破日）单日区间 → 候选为空但**不报错**。"""
        r = select_auspicious_days("jiaqu", DAY_B, DAY_B, limit=5)
        assert r.days_scanned == 1
        assert not r.has_candidates
        assert r.best is None
        assert r.excluded_count == 1
        assert r.excluded_reasons.get(VETO_ZHU_SHI) == 1
        summary = r.to_tradition()["summary"]
        assert "未筛出" in summary
        # 必须说明这是筛选结果，而非「绝无吉日」的断言
        assert any("绝无吉日" in u for u in r.to_tradition()["uncertainties"])

    def test_shengxiao_filters_out_chong_days(self) -> None:
        """属相筛选应真正减少候选或在否决原因里体现。"""
        base = select_auspicious_days("jiaqu", "2026-01-01", "2026-12-31", limit=0)
        sx = select_auspicious_days("jiaqu", "2026-01-01", "2026-12-31", limit=0, shengxiao="羊")
        assert sx.excluded_count >= base.excluded_count
        assert sx.excluded_reasons.get(VETO_CHONG, 0) > 0

    def test_rejects_reversed_range(self) -> None:
        with pytest.raises(InvalidInputError, match="早于"):
            select_auspicious_days("jiaqu", "2026-05-01", "2026-04-01")

    def test_rejects_overlong_range(self) -> None:
        with pytest.raises(InvalidInputError, match="超出上限"):
            select_auspicious_days("jiaqu", date(2000, 1, 1), date(2011, 1, 2))
        assert MAX_RANGE_DAYS == 3660

    def test_rejects_bad_date_string(self) -> None:
        with pytest.raises(InvalidInputError, match="非法日期字符串"):
            select_auspicious_days("jiaqu", "2026-13-01", "2026-12-31")


class TestZeriResultOutput:
    def _result(self):
        return select_auspicious_days("jiaqu", "2026-10-01", "2026-12-31", limit=5)

    def test_to_dict_has_facts_and_tradition(self) -> None:
        d = self._result().to_dict()
        assert set(d) == {"facts", "tradition"}
        f = d["facts"]
        for key in ("event", "event_label", "range", "candidates",
                    "candidate_count", "excluded_count", "excluded_reasons"):
            assert key in f
        assert len(f["candidates"]) == f["candidate_count"]

    def test_tradition_carries_school_and_uncertainties(self) -> None:
        """RULE-006：结果必须显式带流派与不确定性标注。"""
        t = self._result().to_tradition()
        assert t["school"] == "default"
        assert t["school_name"]
        assert len(t["uncertainties"]) >= 3
        assert any("流派" in u for u in t["uncertainties"])

    def test_excluded_reason_text_flags_non_exclusive_counts(self) -> None:
        """否决原因计数可重复（同一日多项），文案必须说明，避免被当互斥分类。"""
        summary = self._result().to_tradition()["summary"]
        assert "不互斥" in summary

    def test_day_dict_shape(self) -> None:
        c = self._result().best
        assert c is not None
        d = c.to_dict()
        assert d["usable"] is True
        assert d["grade"] != GRADE_BUXUAN
        assert set(d["xiu"]) == {"name", "luck"}
        assert set(d["tian_shen"]) == {"name", "type"}

    def test_day_reflects_almanac_facts(self) -> None:
        """择日结果中的黄历字段必须与 almanac 层一致（不得自行推算）。"""
        c = self._result().best
        assert c is not None
        f = _alm_facts(date.fromisoformat(c.solar_date))
        assert c.day_ganzhi == f["gan_zhi"]["day"]
        assert c.jian_chu == f["jian_chu"]
        assert c.tian_shen == f["tian_shen"]["name"]
        assert c.xiu == f["xiu"]["name"]
        assert c.chong_shengxiao == f["chong"]["shengxiao"]
        assert c.sha_direction == f["chong"]["sha_direction"]


class TestCrossEventConsistency:
    def test_all_events_produce_structured_results(self) -> None:
        """全部事件在半年区间上都能正常产出结构化结果（含空候选）。"""
        for e in list_zeri_events():
            r = select_auspicious_days(e["event"], "2026-01-01", "2026-06-30", limit=5)
            assert r.days_scanned == 181
            assert r.event_label == e["label"]
            assert isinstance(r.to_dict()["facts"]["candidates"], list)
            assert r.to_tradition()["summary"]

    def test_veto_and_usable_are_mutually_exclusive(self) -> None:
        r = select_auspicious_days(
            "anzang", "2026-01-01", "2026-03-31", limit=0, include_unfavorable=True
        )
        for c in r.candidates:
            assert c.is_usable == (not c.veto)
            assert (c.grade == GRADE_BUXUAN) == bool(c.veto)
