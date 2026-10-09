from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Callable, Iterator, List, Optional

__all__ = ["Rule", "iter_recurrences", "parse"]


_FREQS = ("DAILY", "WEEKLY", "MONTHLY")
_WEEKDAYS = (
    "MO", "TU", "WE", "TH", "FR", "SA", "SU",
)


def _parse_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _parse_int_list(value: object, name: str, valid: tuple, *, allow_zero: bool) -> List[int]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a list or tuple")
    out: List[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{name} entries must be ints, got {type(item).__name__}")
        if allow_zero:
            if item == 0:
                continue
            if not (1 <= abs(item) <= len(valid)):
                raise ValueError(f"{name} entry {item} out of range")
        else:
            if not (1 <= item <= len(valid)):
                raise ValueError(f"{name} entry {item} out of range")
        out.append(item)
    return out


def _parse_weekday_list(value: object) -> List[str]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("byday must be a list or tuple")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError("byday entries must be strings")
        upper = item.upper()
        if upper not in _WEEKDAYS:
            raise ValueError(f"invalid weekday: {item!r}")
        out.append(upper)
    return out


@dataclass(frozen=True)
class Rule:
    """A readable subset of RFC 5545 RRULE.

    Supported frequencies: DAILY, WEEKLY, MONTHLY.
    Supported parts: INTERVAL, COUNT, UNTIL, BYDAY, BYMONTHDAY.

    Design decisions (documented because they are not obvious):

    - BYDAY in WEEKLY rules supports plain weekday codes (MO, TU, ...). The
      ordinal form "2MO" is rejected because it interacts with WKST in a way
      that is easy to get wrong; we refuse the feature rather than ship a
      subtle bug.
    - BYMONTHDAY supports negative values (e.g. -1 for the last day of the
      month). Days that do not exist in a given month (e.g. 31 in February)
      are silently skipped, matching RFC 5545's "skip invalid" semantics.
    - When both BYDAY and BYMONTHDAY are set in a MONTHLY rule, a date must
      satisfy BOTH to be yielded. This is the simplest unambiguous rule and
      avoids the combinatorial explosion of full RFC BYxxx interaction.
    - UNTIL is inclusive. COUNT counts yielded occurrences (including the
      first). The first occurrence is always the DTSTART itself.
    - Time components are preserved exactly as given in DTSTART; no timezone
      conversions are performed.
    """

    freq: str
    dtstart: _dt.datetime
    interval: int = 1
    count: Optional[int] = None
    until: Optional[_dt.datetime] = None
    byday: Optional[List[str]] = None
    bymonthday: Optional[List[int]] = None

    def __post_init__(self) -> None:
        freq_upper = self.freq.upper() if isinstance(self.freq, str) else self.freq
        if freq_upper not in _FREQS:
            raise ValueError(f"freq must be one of {_FREQS}, got {self.freq!r}")
        object.__setattr__(self, "freq", freq_upper)

        if not isinstance(self.dtstart, _dt.datetime):
            raise TypeError("dtstart must be a datetime.datetime")

        object.__setattr__(self, "interval", _parse_int(self.interval, "interval"))

        if self.count is not None:
            if isinstance(self.count, bool) or not isinstance(self.count, int):
                raise TypeError("count must be an int")
            if self.count <= 0:
                raise ValueError("count must be positive")

        if self.until is not None:
            if not isinstance(self.until, _dt.datetime):
                raise TypeError("until must be a datetime.datetime")

        if self.byday is not None:
            object.__setattr__(self, "byday", _parse_weekday_list(self.byday))

        if self.bymonthday is not None:
            object.__setattr__(
                self,
                "bymonthday",
                _parse_int_list(
                    self.bymonthday, "bymonthday", tuple(range(1, 32)), allow_zero=True
                ),
            )

        if self.freq == "DAILY":
            if self.byday is not None or self.bymonthday is not None:
                raise ValueError("DAILY rules do not support BYDAY or BYMONTHDAY")
        elif self.freq == "WEEKLY":
            if self.bymonthday is not None:
                raise ValueError("WEEKLY rules do not support BYMONTHDAY")


def _weekday_code(d: _dt.date) -> str:
    return _WEEKDAYS[d.weekday()]


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_first = _dt.date(year + 1, 1, 1)
    else:
        next_first = _dt.date(year, month + 1, 1)
    return (next_first - _dt.date(year, month, 1)).days


def _resolve_monthday(day: int, year: int, month: int) -> Optional[int]:
    if day > 0:
        return day if day <= _days_in_month(year, month) else None
    neg = -day
    dim = _days_in_month(year, month)
    resolved = dim - neg + 1
    return resolved if resolved >= 1 else None


def _iter_daily(rule: Rule) -> Iterator[_dt.datetime]:
    current = rule.dtstart
    step = _dt.timedelta(days=rule.interval)
    emitted = 0
    while True:
        if rule.count is not None and emitted >= rule.count:
            return
        if rule.until is not None and current > rule.until:
            return
        yield current
        emitted += 1
        current = current + step


def _iter_weekly(rule: Rule) -> Iterator[_dt.datetime]:
    if rule.byday is None:
        yield from _iter_daily_like(rule)
        return

    wanted = {d.upper() for d in rule.byday}
    interval = rule.interval
    emitted = 0

    dtstart = rule.dtstart
    start_week_monday = dtstart.date() - _dt.timedelta(days=dtstart.weekday())

    week_index = 0
    while True:
        week_start = start_week_monday + _dt.timedelta(weeks=week_index * interval)
        for offset in range(7):
            candidate_date = week_start + _dt.timedelta(days=offset)
            if candidate_date < dtstart.date():
                continue
            candidate = _dt.datetime.combine(candidate_date, dtstart.time())
            if rule.until is not None and candidate > rule.until:
                return
            if rule.count is not None and emitted >= rule.count:
                return
            if _weekday_code(candidate_date) in wanted:
                yield candidate
                emitted += 1
        week_index += 1


def _iter_daily_like(rule: Rule) -> Iterator[_dt.datetime]:
    current = rule.dtstart
    step = _dt.timedelta(weeks=rule.interval)
    emitted = 0
    while True:
        if rule.count is not None and emitted >= rule.count:
            return
        if rule.until is not None and current > rule.until:
            return
        yield current
        emitted += 1
        current = current + step


def _iter_monthly(rule: Rule) -> Iterator[_dt.datetime]:
    emitted = 0
    year = rule.dtstart.year
    month = rule.dtstart.month

    while True:
        candidates: List[_dt.datetime] = []

        if rule.bymonthday is not None:
            for day in rule.bymonthday:
                resolved = _resolve_monthday(day, year, month)
                if resolved is not None:
                    d = _dt.date(year, month, resolved)
                    if rule.byday is None or _weekday_code(d) in {wd.upper() for wd in rule.byday}:
                        try:
                            candidates.append(
                                _dt.datetime(year, month, resolved, rule.dtstart.hour, rule.dtstart.minute, rule.dtstart.second, rule.dtstart.microsecond)
                            )
                        except ValueError:
                            pass

        if rule.bymonthday is None and rule.byday is not None:
            wanted = {d.upper() for d in rule.byday}
            dim = _days_in_month(year, month)
            for day in range(1, dim + 1):
                d = _dt.date(year, month, day)
                if _weekday_code(d) in wanted:
                    candidate = _dt.datetime(year, month, day, rule.dtstart.hour, rule.dtstart.minute, rule.dtstart.second, rule.dtstart.microsecond)
                    if candidate not in candidates:
                        candidates.append(candidate)

        if rule.bymonthday is None and rule.byday is None:
            resolved = _resolve_monthday(rule.dtstart.day, year, month)
            if resolved is not None:
                try:
                    candidates.append(
                        _dt.datetime(year, month, resolved, rule.dtstart.hour, rule.dtstart.minute, rule.dtstart.second, rule.dtstart.microsecond)
                    )
                except ValueError:
                    pass

        candidates.sort()
        for candidate in candidates:
            if candidate < rule.dtstart:
                continue
            if rule.until is not None and candidate > rule.until:
                return
            if rule.count is not None and emitted >= rule.count:
                return
            yield candidate
            emitted += 1

        month += 1
        if month > 12:
            month = 1
            year += 1


def iter_recurrences(rule: Rule) -> Iterator[_dt.datetime]:
    """Yield occurrences for *rule* in ascending order.

    The iterator is unbounded unless *rule.count* or *rule.until* is set.
    """
    if rule.freq == "DAILY":
        yield from _iter_daily(rule)
    elif rule.freq == "WEEKLY":
        yield from _iter_weekly(rule)
    elif rule.freq == "MONTHLY":
        yield from _iter_monthly(rule)
    else:
        raise ValueError(f"unknown freq: {rule.freq!r}")


def parse(text: str) -> Rule:
    """Parse a minimal RRULE string into a :class:`Rule`.

    Only the parts this library supports are understood. Unknown parts raise
    ValueError so callers do not silently get a rule that means something
    other than what they wrote.
    """
    if not isinstance(text, str):
        raise TypeError("parse expects a str")
    s = text.strip()
    if not s.startswith("RRULE:"):
        raise ValueError("input must start with 'RRULE:'")
    s = s[len("RRULE:"):].strip()

    parts: dict = {"freq": None, "dtstart": None}
    for raw in s.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        if "=" not in raw:
            raise ValueError(f"bad part: {raw!r}")
        key, value = raw.split("=", 1)
        key = key.upper()
        if key == "FREQ":
            parts["freq"] = value.upper()
        elif key == "INTERVAL":
            parts["interval"] = int(value)
        elif key == "COUNT":
            parts["count"] = int(value)
        elif key == "UNTIL":
            parts["until"] = _parse_until(value)
        elif key == "BYDAY":
            parts["byday"] = [v.strip().upper() for v in value.split(",")]
        elif key == "BYMONTHDAY":
            parts["bymonthday"] = [int(v) for v in value.split(",")]
        elif key == "DTSTART":
            parts["dtstart"] = _parse_datetime(value)
        else:
            raise ValueError(f"unsupported part: {key}")

    if parts["freq"] is None:
        raise ValueError("RRULE must specify FREQ")
    if parts["dtstart"] is None:
        raise ValueError("RRULE must specify DTSTART")

    return Rule(
        freq=parts["freq"],
        dtstart=parts["dtstart"],
        interval=parts.get("interval", 1),
        count=parts.get("count"),
        until=parts.get("until"),
        byday=parts.get("byday"),
        bymonthday=parts.get("bymonthday"),
    )


def _parse_until(value: str) -> _dt.datetime:
    v = value.strip()
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M%SZ", "%Y%m%d"):
        try:
            return _dt.datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise ValueError(f"cannot parse UNTIL: {value!r}")


def _parse_datetime(value: str) -> _dt.datetime:
    v = value.strip()
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M%SZ", "%Y%m%d"):
        try:
            return _dt.datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise ValueError(f"cannot parse DTSTART: {value!r}")
