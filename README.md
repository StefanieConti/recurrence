# Recurrence

A readable subset of RFC 5545 RRULE for daily, weekly, and monthly repeats. Zero third-party dependencies; standard library only.

## Usage

```python
from recurrence import Rule, iter_recurrences, parse
import datetime as dt

rule = Rule(
    freq="WEEKLY",
    dtstart=dt.datetime(2024, 1, 1),
    byday=["MO", "WE"],
    count=4,
)
for occurrence in iter_recurrences(rule):
    print(occurrence)

# Or parse an RRULE string:
rule = parse("RRULE:FREQ=MONTHLY;DTSTART=20240101T000000;BYMONTHDAY=15;COUNT=3")
for occurrence in iter_recurrences(rule):
    print(occurrence)
```

## Why this exists

Full RFC 5545 RRULE is sprawling: BYSETPOS, WKST, BYHOUR, BYYEARDAY, timezone negotiation. Most applications need a small, predictable slice. This library implements that slice with semantics that are easy to reason about, and refuses (via `ValueError`) the parts it does not support rather than silently misinterpreting them.

## Supported parts

- `FREQ`: `DAILY`, `WEEKLY`, `MONTHLY`
- `DTSTART`: the first occurrence
- `INTERVAL`: positive integer (default 1)
- `COUNT`: positive integer, limits the number of occurrences
- `UNTIL`: inclusive upper bound
- `BYDAY`: weekday codes (`MO`, `TU`, `WE`, `TH`, `FR`, `SA`, `SU`); weekly and monthly
- `BYMONTHDAY`: day of month (1-31, negatives allowed); monthly only

## Edge cases you will hit

- **February 30 is skipped.** A monthly rule starting on the 31st yields January 31, March 31, May 31 — the months that have a 31st. This matches RFC 5545's skip-invalid semantics.
- **Negative BYMONTHDAY** (e.g. `-1`) resolves to the last day of the month, correctly handling February in leap and non-leap years.
- **BYDAY + BYMONTHDAY in MONTHLY rules** is an intersection: a date must satisfy both to be yielded. This is a deliberate, documented choice rather than the full RFC BYxxx interaction model.
- **UNTIL is inclusive.** If `UNTIL` equals an occurrence, that occurrence is yielded.
- **Ordinal BYDAY** (e.g. `2MO` for the second Monday) is not supported. Use `BYMONTHDAY` or compose multiple rules if you need that.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

