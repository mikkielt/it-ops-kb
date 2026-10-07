---
topic: python/stdlib-datetime-iso-week
priority: P3
applies_to: [python, datetime, iso-8601]
retrieved_utc: 2026-10-07
sources: [S-gaeidf4e]
status: complete
---

# stdlib datetime: ISO 8601 weeks (deciding in code whether a week has closed)

## Summary
A tool that counts events per calendar week, or that waits for a week to end before it judges it, needs one
definition of the week. `datetime` follows ISO 8601: a week runs Monday to Sunday, week 1 of a year is the
one with the year's first Thursday, and a year has 52 or 53 weeks, so the ISO year of a January or December
date can differ from its calendar year. `date.isocalendar()` and `date.fromisocalendar()` convert both
ways in plain Python; the `%G`, `%V` and `%u` format codes do the same through the platform's C library and
must be used together. Pages read at CPython 3.14.8 (`Doc/library/datetime.rst` at tag `v3.14.8`); the
probes ran on Python 3.13.2, macOS (Darwin 25.5.0), 2026-10-07.

## Facts
- `date.isocalendar()` returns a named tuple with the components `year`, `week` and `weekday`; since 3.9 it
  is a named tuple, before that a plain tuple. `datetime.isocalendar()` is the same as
  `self.date().isocalendar()`. [DOC S-gaeidf4e]
- The ISO year has 52 or 53 full weeks; a week starts on Monday and ends on Sunday. The first week of an ISO
  year is the first calendar week of the year containing a Thursday, and the ISO year of that Thursday equals
  its Gregorian year. [DOC S-gaeidf4e]
- The docs' example: 2004 begins on a Thursday, so ISO week 1 of 2004 begins Monday 29 Dec 2003 and ends
  Sunday 4 Jan 2004; `date(2003, 12, 29).isocalendar()` is `year=2004, week=1, weekday=1` and
  `date(2004, 1, 4).isocalendar()` is `year=2004, week=1, weekday=7`. [DOC S-gaeidf4e]
- `date.weekday()` numbers Monday 0 to Sunday 6 and `date.isoweekday()` Monday 1 to Sunday 7 (the
  `datetime` methods are the same as the ones of `self.date()`); the `%u` code is the ISO weekday with 1 as
  Monday, while `%w` is 0 as Sunday to 6 as Saturday. [DOC S-gaeidf4e]
- `date.fromisocalendar(year, week, day)` (added in 3.8) returns the `date` of that ISO year, week and
  weekday; the docs call it the inverse of `date.isocalendar()`. [DOC S-gaeidf4e]
- Given an ISO week and weekday that do not exist, `fromisocalendar` raises `ValueError`: on 3.13.2,
  `fromisocalendar(2021, 53, 1)` and `fromisocalendar(2025, 53, 1)` gave `Invalid week: 53`, week 0 gave
  `Invalid week: 0` and day 8 gave `Invalid day: 8 (range is [1, 7])`. The page does not state the
  exception. [DER S-gaeidf4e: the inverse-of-`isocalendar` text; the errors observed on 3.13.2, macOS, 2026-10-07]
- The `%G` code is the ISO 8601 year "that contains the greater part of the ISO week (`%V`)", `%V` is the ISO
  week number 01 to 53 with Monday as the first day, "Week 01 is the week containing Jan 4", and `%u` is the
  ISO weekday 1 to 7. All three were added in 3.6. [DOC S-gaeidf4e]
- The docs say `%G` and `%Y` are not interchangeable, and the ISO week code `%V` is not the same as `%U` or
  `%W`, which count weeks from the first Sunday or Monday of the year and put the days before it in week 0. [DOC S-gaeidf4e]
- At a year boundary the wrong pairing gives a wrong label: on 3.13.2, `date(2021, 1, 1).strftime("%G-W%V")`
  printed `2020-W53` but `"%Y-W%V"` printed `2021-W53`, and for 2024-12-30 `"%G-W%V"` printed `2025-W01`
  where `"%Y-W%V"` printed `2024-W01`; so a week label is `%G-W%V`, never `%Y-W%V`. [DER S-gaeidf4e: the `%G`/`%Y` text; the outputs observed on 3.13.2, macOS, 2026-10-07]
- For `strptime`, `%V` is only used in calculations when the day of the week and the ISO year (`%G`) are also
  in the format string; the leading zero of `%V` is optional when parsing. [DOC S-gaeidf4e]
- The docs say `%G`, `%u` and `%V` "may not be available on all platforms when used with the `strftime()`
  method", because Python calls the platform's C `strftime` and "platform variations are common"; the
  `isocalendar()` entry carries no such caveat. So a tool that must give the same week on Windows, macOS
  and Linux takes the week from `isocalendar()` and formats the label itself, for example
  `f"{y}-W{w:02d}"`. [DER S-gaeidf4e: the platform caveat for the codes against the `isocalendar` entry, which has none]
- `date.isoformat()` returns only `YYYY-MM-DD`. `date.fromisoformat()` (since 3.7) takes "any valid ISO 8601
  format" with three exceptions, reduced-precision (`YYYY-MM`, `YYYY`), extended-year and ordinal
  (`YYYY-OOO`) dates; it was widened in 3.11 from `YYYY-MM-DD` only, and the docs' example
  `date.fromisoformat('2021-W01-1')` gives `datetime.date(2021, 1, 4)`. [DOC S-gaeidf4e]
- Run on 3.13.2, `date.fromisoformat` also accepted the week form without a day (`2021-W01`, `2021W01`) and
  the basic form `2021W011`, all giving 2021-01-04, the Monday; the docs show only the full `YYYY-Www-D` example, so
  code that needs older Pythons or the documented form writes the day. [DER S-gaeidf4e: the example and the "any valid ISO 8601 format" rule; the day-less forms observed on 3.13.2, macOS, 2026-10-07]
- `date2 = date1 + timedelta` moves forward by `timedelta.days` days, backward when it is negative, and
  `timedelta.seconds` and `timedelta.microseconds` are ignored. [DOC S-gaeidf4e]
- So the first day after ISO week `(y, w)` is `date.fromisocalendar(y, w, 1) + timedelta(days=7)`, which also
  crosses a year end (on 3.13.2 week 53 of 2020 gives 2021-01-04, week 52 of 2024 gives 2024-12-30), while
  `fromisocalendar(y, w + 1, 1)` raises `ValueError` for the last week of a year. A week has closed on every
  date on or after that Monday; the Sunday itself is still inside the week. [DER S-gaeidf4e: the week, Monday and `timedelta` rules above; the year-end cases observed on 3.13.2, macOS, 2026-10-07]
- The ISO year's last week is the one that contains 28 December, because week 1 contains 4 January and so
  starts between 29 December and 4 January. On 3.13.2 that week's number for 2019 to 2030 was 52, except
  2020 and 2026 with 53, so the week count is read from `date(y, 12, 28).isocalendar().week`, not assumed. [DER S-gaeidf4e: the week 1 rule; the counts observed on 3.13.2, macOS, 2026-10-07]
- `isocalendar()` reads the date fields as stored and does no time zone conversion: on 3.13.2
  `datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc)` is week 40, and the same instant after
  `astimezone` to UTC+2 (2026-10-05 01:30) is week 41. So a detector that closes weeks fixes one zone, normally UTC, before
  it takes the week. [DER S-gaeidf4e: `datetime.isocalendar()` is `self.date().isocalendar()`; the two weeks observed on 3.13.2, macOS, 2026-10-07]

## Reference
- Related: `python/pytest.md` (`-k` selection and exit code 5 for a selector that matches no test).
- Source: https://docs.python.org/3/library/datetime.html (the `date` class, `isocalendar`, `fromisocalendar`, and "`strftime()` and `strptime()` Behavior").

## Examples
- SNIPPET: the first day after an ISO week, whether it has closed, and the latest closed week; context:
  Python 3.9+ stdlib (the `tuple[int, int]` hint), dates already in one zone; checked: run (3.13.2, macOS, 2026-10-07: `(2026, 41)` closes on
  2026-10-12, `(2026, 40)` is open on 2026-10-04 and closed on 2026-10-05, and the latest closed week of
  2026-10-07 is `(2026, 40)`, of 2027-01-04 `(2026, 53)`, of 2027-01-03 `(2026, 52)`) [DER S-gaeidf4e: `fromisocalendar`, `timedelta` addition and `isocalendar`]
```python
import datetime as dt


def next_week_start(year: int, week: int) -> dt.date:
    return dt.date.fromisocalendar(year, week, 1) + dt.timedelta(days=7)


def week_is_closed(year: int, week: int, today: dt.date) -> bool:
    return today >= next_week_start(year, week)


def last_closed_week(today: dt.date) -> tuple[int, int]:
    year, week, _ = (today - dt.timedelta(days=7)).isocalendar()
    return year, week
```
