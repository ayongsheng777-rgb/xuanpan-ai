"""历法输入归一 —— 公历 / 农历 / 时区 / 真太阳时。

对应材料 §13：工程上必须固定「公历 / 农历 / 节气 / 时区 / 真太阳时 / 夏令时 / 出生地」。

可信度：
- `[已确认]` 公历、农历、时区换算（`lunar-python` + `zoneinfo`）
- `[已确认]` 经度时差修正（标准经线法，确定性公式）
- `[待验证]` **均时差（Equation of Time，±16 分钟）本版未计入** —— 需真太阳时高精度时再补
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..exceptions import InvalidInputError

CalendarType = Literal["solar", "lunar"]
Gender = Literal["male", "female", "other"]

#：`zoneinfo` 在无 tzdata 的环境下的兜底偏移（小时）。仅覆盖常用时区。
FALLBACK_UTC_OFFSET: dict[str, float] = {
    "Asia/Shanghai": 8.0,
    "Asia/Chongqing": 8.0,
    "Asia/Harbin": 8.0,
    "Asia/Urumqi": 8.0,
    "Asia/Hong_Kong": 8.0,
    "Asia/Macau": 8.0,
    "Asia/Taipei": 8.0,
    "Asia/Tokyo": 9.0,
    "Asia/Seoul": 9.0,
    "Asia/Singapore": 8.0,
    "Asia/Bangkok": 7.0,
    "UTC": 0.0,
    "America/New_York": -5.0,
    "America/Los_Angeles": -8.0,
    "Europe/London": 0.0,
    "Europe/Paris": 1.0,
    "Australia/Sydney": 10.0,
}


@dataclass(frozen=True, slots=True)
class BirthInput:
    """出生信息原始输入。字段与材料 §12 的 JSON 契约一致。"""

    year: int
    month: int
    day: int
    hour: int
    minute: int = 0
    calendar: CalendarType = "solar"
    gender: Gender | None = None
    timezone: str = "Asia/Shanghai"
    longitude: float | None = None       # 出生地经度（东经为正），给定时启用真太阳时
    latitude: float | None = None
    location: str | None = None
    is_leap_month: bool = False          # 仅农历有效
    name: str | None = None

    def validate(self) -> None:
        if self.calendar not in ("solar", "lunar"):
            raise InvalidInputError(f"calendar 须为 solar/lunar，收到 {self.calendar!r}")
        if not 0 <= self.hour <= 23:
            raise InvalidInputError(f"hour 须在 0..23，收到 {self.hour}")
        if not 0 <= self.minute <= 59:
            raise InvalidInputError(f"minute 须在 0..59，收到 {self.minute}")
        if self.calendar == "solar":
            try:
                datetime(self.year, self.month, self.day)
            except ValueError as exc:
                raise InvalidInputError(f"非法公历日期：{self.year}-{self.month}-{self.day}（{exc}）") from exc
        else:
            if not 1 <= self.month <= 12:
                raise InvalidInputError(f"农历月份须在 1..12，收到 {self.month}")
            if not 1 <= self.day <= 30:
                raise InvalidInputError(f"农历日期须在 1..30，收到 {self.day}")
        if self.longitude is not None and not -180.0 <= self.longitude <= 180.0:
            raise InvalidInputError(f"经度须在 -180..180，收到 {self.longitude}")
        if not 1900 <= self.year <= 2100:
            raise InvalidInputError(f"年份须在 1900..2100，收到 {self.year}")


@dataclass(frozen=True, slots=True)
class ResolvedBirth:
    """归一后的出生信息 —— 后续一切历法计算都以它为唯一输入。"""

    input: BirthInput
    local_dt: datetime           # 出生地当地钟表时间（未修正）
    utc_offset_hours: float      # 该时刻的 UTC 偏移（含夏令时）
    solar_dt: datetime           # 换算后的公历时间（真太阳时修正后，用于排盘）
    solar_term_shift_minutes: float = 0.0
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def lunar_label(self) -> str:
        return f"{self.input.year}年{'闰' if self.input.is_leap_month else ''}{self.input.month}月{self.input.day}日"

    def to_dict(self) -> dict[str, Any]:
        return {
            "input": {
                "calendar": self.input.calendar,
                "year": self.input.year,
                "month": self.input.month,
                "day": self.input.day,
                "hour": self.input.hour,
                "minute": self.input.minute,
                "gender": self.input.gender,
                "timezone": self.input.timezone,
                "longitude": self.input.longitude,
                "location": self.input.location,
            },
            "local_datetime": self.local_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_offset_hours": self.utc_offset_hours,
            "solar_datetime_used": self.solar_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "true_solar_time_applied": self.solar_term_shift_minutes != 0.0,
            "true_solar_shift_minutes": round(self.solar_term_shift_minutes, 2),
            "warnings": list(self.warnings),
        }


def resolve_utc_offset(dt: datetime, tz_name: str) -> tuple[float, str | None]:
    """解析该时刻的 UTC 偏移（含夏令时）。

    Returns:
        (offset_hours, warning) —— warning 非空表示走了兜底路径。
    """
    try:
        tz = ZoneInfo(tz_name)
        offset = dt.replace(tzinfo=tz).utcoffset()
        return (offset.total_seconds() / 3600.0 if offset else 0.0), None
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        if tz_name in FALLBACK_UTC_OFFSET:
            return FALLBACK_UTC_OFFSET[tz_name], f"时区库不可用，{tz_name} 使用固定偏移兜底（未计夏令时）"
        return FALLBACK_UTC_OFFSET["Asia/Shanghai"], (
            f"未知时区 {tz_name!r}，已按 Asia/Shanghai(+8) 处理，请核对出生地"
        )


def true_solar_time(local_dt: datetime, longitude: float, utc_offset_hours: float) -> datetime:
    """经度时差修正（标准经线法）。

    地球每 15° 经度差 1 小时 → 每 1° 差 4 分钟。
    标准经线 = UTC 偏移 × 15°。
    东经偏东 → 真太阳时更早，故修正量为 ``(经度 - 标准经线) × 4`` 分钟。

    >>> true_solar_time(datetime(2000, 1, 1, 12, 0), 120.0, 8.0)
    datetime.datetime(2000, 1, 1, 12, 0)
    >>> true_solar_time(datetime(2000, 1, 1, 12, 0), 116.4, 8.0)
    datetime.datetime(2000, 1, 1, 11, 45, 36)
    """
    standard_meridian = utc_offset_hours * 15.0
    delta_minutes = (longitude - standard_meridian) * 4.0
    return local_dt + timedelta(minutes=delta_minutes)


def _hour_branch_boundary_warning(dt: datetime) -> str | None:
    """真太阳时后若距时辰边界 < 30 分钟，提示用户复核。

    时辰边界在奇数整点（23/01/03/…）。跨边界会改变时柱，属于高影响歧义。
    """
    minute_of_day = dt.hour * 60 + dt.minute
    nearest_boundary = min(
        (abs(minute_of_day - b) for b in range(0, 24 * 60, 120)),
        default=0,
    )
    # 时辰边界：23:00 起每 2 小时
    boundaries = [(23 + 2 * i) % 24 * 60 for i in range(12)]
    nearest = min(abs(minute_of_day - b) for b in boundaries)
    if nearest < 30:
        return "修正后时间距时辰边界不足 30 分钟，时柱存在歧义，建议核对出生时间精度"
    return None


def resolve_birth(birth: BirthInput) -> ResolvedBirth:
    """把用户输入归一为可用于排盘的公历时间。

    - 农历输入先转公历
    - 时区解析出 UTC 偏移（含夏令时）
    - 若提供经度 → 施加真太阳时修正
    """
    birth.validate()
    warnings: list[str] = []

    if birth.calendar == "lunar":
        from lunar_python import Lunar

        lunar = (
            Lunar.fromYmdHms(birth.year, -birth.month, birth.day, birth.hour, birth.minute, 0)
            if birth.is_leap_month
            else Lunar.fromYmdHms(birth.year, birth.month, birth.day, birth.hour, birth.minute, 0)
        )
        solar = lunar.getSolar()
        local_dt = datetime(
            solar.getYear(), solar.getMonth(), solar.getDay(),
            solar.getHour(), solar.getMinute(), solar.getSecond(),
        )
    else:
        local_dt = datetime(birth.year, birth.month, birth.day, birth.hour, birth.minute)

    offset_hours, tz_warning = resolve_utc_offset(local_dt, birth.timezone)
    if tz_warning:
        warnings.append(tz_warning)

    shift_minutes = 0.0
    solar_dt = local_dt
    if birth.longitude is not None:
        standard_meridian = offset_hours * 15.0
        shift_minutes = (birth.longitude - standard_meridian) * 4.0
        solar_dt = true_solar_time(local_dt, birth.longitude, offset_hours)
        warnings.append(
            f"已应用真太阳时修正 {shift_minutes:+.1f} 分钟"
            f"（经度 {birth.longitude:.2f}° vs 标准经线 {standard_meridian:.0f}°）；均时差未计入"
        )
        boundary_warning = _hour_branch_boundary_warning(solar_dt)
        if boundary_warning:
            warnings.append(boundary_warning)

    return ResolvedBirth(
        input=birth,
        local_dt=local_dt,
        utc_offset_hours=offset_hours,
        solar_dt=solar_dt,
        solar_term_shift_minutes=shift_minutes,
        warnings=tuple(warnings),
    )


__all__ = [
    "BirthInput", "ResolvedBirth", "CalendarType", "Gender",
    "FALLBACK_UTC_OFFSET",
    "resolve_utc_offset", "true_solar_time", "resolve_birth",
]
