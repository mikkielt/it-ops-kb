---
topic: python/percentile-nearest-rank
priority: P3
applies_to: [python, statistics, percentile, p95, kql, t-sql, quartiles, interquartile-range, outlier-fence]
retrieved_utc: 2026-10-19
sources: [S-g5oa4uyp, S-35bztnbb, S-dh7f43kc, S-or2wocyn, S-4hnlw34j]
status: partial
---

# Percentiles at the nearest rank (how a p95 is taken from a list of measurements)

## Summary
A p95 (95th percentile) of a list of N timings, taken at the nearest rank, is the smallest value of the sorted
list that has at least 95 percent of the list at or below it: the value at ordinal rank `ceil(0.95 * N)`, counted
from 1, so index `ceil(0.95 * N) - 1` of the list sorted ascending. It is always a value that was measured, and
below 20 values it is the largest one. Microsoft documents the same rule for Kusto's `percentile()` and for T-SQL's
`PERCENTILE_DISC`; Python's `statistics.quantiles` interpolates instead, so it gives another number. Its quartiles
(`n=4`) come in two methods, `exclusive` (default) and `inclusive`, and NIST's outlier fences (`Q3 + 1.5*IQ` inner,
`Q3 + 3*IQ` outer) computed from them differ by method. Pages read 2026-10-13 and 2026-10-19; the probes ran on
Python 3.13.2, macOS (Darwin 25.5.0), 2026-10-13 and 2026-10-19.

## Facts
- The nearest-rank percentile of Kusto's `percentile()`: the P-th percentile (0 < P <= 100) of an ascending list
  is the smallest value of the list such that P percent of the data is at or below it, and the 0-th percentile is
  the smallest member. The page states the definition under "Nearest-rank percentile" and cites Wikipedia for
  it. [DOC S-g5oa4uyp]
- The page says the nearest-rank definition makes P = 50 differ from the interpolated median, and that the size
  of the population and the estimation error should be weighed when that difference matters. [DOC S-g5oa4uyp]
- Kusto's `percentile()` is an estimate, not a sort of the whole list: it is computed with a T-Digest, with an
  error capped at 1 percent of rank at the median and smaller towards both ends, and the value it returns "may
  not be a member of the population". Percentiles 0 and 100 are the exact minimum and maximum. [DOC S-g5oa4uyp]
- The nearest-rank method as Wikipedia gives it: the ordinal rank is `n = ceil(P / 100 * N)` and the percentile is
  the n-th value of the ascending list (rank counted from 1). [COMMUNITY S-or2wocyn]
- Wikipedia's other properties of the method: the result is always a member of the list, the 100th percentile is
  the largest value, with fewer than 100 distinct values one value can serve several percentiles, and the 50th
  percentile equals the usual median only for an odd N. [COMMUNITY S-or2wocyn]
- T-SQL `PERCENTILE_DISC(P)` sorts the values of its `ORDER BY` and returns the value with the smallest
  `CUME_DIST` that is greater than or equal to P; P runs from 0.0 to 1.0, nulls are ignored, and the result is
  one of the column's values. It needs the `OVER` clause in SQL Server, Azure SQL Database and Azure SQL Managed
  Instance (the aggregate form without it is not supported there). [DOC S-35bztnbb]
- `PERCENTILE_DISC` is the discrete counterpart of `PERCENTILE_CONT`: the page says `PERCENTILE_CONT` returns a
  value even if it does not exist in the data set and `PERCENTILE_DISC` returns an actual set value, so the two
  can differ (its median example gives 34.375 against 32.6923 for Engineering). [DOC S-35bztnbb]
- Both documented rules name the same element: the value with the smallest cumulative share at or above P is, for
  N values sorted ascending, the one at rank `ceil(P * N)` counted from 1, so `PERCENTILE_DISC(0.95)` over the
  rows of a table gives the nearest-rank p95 of those rows (an exact one, unlike Kusto's estimate). [DER S-g5oa4uyp, S-35bztnbb, S-or2wocyn: the "smallest value with at least P percent at or below it" rule of both pages read against Wikipedia's ordinal rank]
- `statistics.quantiles(data, n=100, method=...)` returns 99 cut points that "are linearly interpolated from the
  two nearest data points", so its 95th cut point is not a nearest-rank p95 and is not in general a value of the
  data; the default method `exclusive` puts the i-th of m sorted points at i / (m + 1), `inclusive` at
  (i - 1) / (m - 1). [DOC S-dh7f43kc]
- The page's table of functions lists no function that returns a percentile at the nearest rank (`median`,
  `median_low`, `median_high` and `median_grouped` are the order-statistic functions it has), so a nearest-rank
  p95 is a sort and an index in the caller's own code. [DER S-dh7f43kc: the function list read for a nearest-rank percentile, none found]
- Observed on Python 3.13.2 with the data `1..N`: the nearest-rank p95 was 10 for N = 10, 19 for N = 20, 20 for
  N = 21, 95 for N = 100 and 96 for N = 101, while `statistics.quantiles(data, n=100, method="inclusive")[94]`
  gave 9.55, 19.05, 20.0, 95.05 and 96.0 and the `exclusive` method 10.45, 19.95, 20.9, 95.95 and 96.9, so
  the interpolated value is not a measured one except for the `inclusive` method at N = 21 and N = 101. [DER S-dh7f43kc, S-or2wocyn: the nearest-rank formula and the quantiles call, run on 3.13.2, macOS, 2026-10-13]
- Observed on Python 3.13.2: for N below 20, `ceil(0.95 * N)` is N, so the nearest-rank p95 of up to 19 timings
  is the slowest one (N = 5 gave 5, N = 10 gave 10); the first N where it is not the maximum is 20 (rank 19).
  [DER S-or2wocyn: `ceil(0.95 * N) = N` while 0.95 * N > N - 1, that is N < 20; confirmed for N = 1..19 on 3.13.2, macOS, 2026-10-13]
- Observed on Python 3.13.2 for N = 1 to 5000: `math.ceil(0.95 * n)` equalled the integer form `-(-95 * n // 100)` for
  every n, so the float product made no off-by-one there; an index taken with `int(0.95 * n)` (floor) differed
  from the nearest rank for 4,749 of the 5,000 and `int(round(0.95 * n))` for 2,375 (n = 11 to 19, 30, 31, ...),
  always lower, because Python's `round` takes a half to the even number (`round(28.5)` is 28, so n = 30 gives
  rank 28 where the nearest rank is 29). [DER S-or2wocyn: the nearest-rank rank as the reference; the three index forms compared on 3.13.2, macOS, 2026-10-13]
- A p95 index that is floor or round therefore reads one rank low on most list sizes and returns a value that
  fewer than 95 percent of the list sits at or below; the nearest rank is `max(1, ceil(0.95 * n))`, taken from
  the ascending list at index `rank - 1`, and an integer form of it needs no float. [DER S-or2wocyn, S-35bztnbb: the definition "at least P percent at or below"; the floor and round cases above]
- `statistics.quantiles(data, *, n=4, method='exclusive')` divides the data into `n` equal-probability intervals and
  returns the `n - 1` cut points between them; the page says to set `n` to 4 for quartiles, which is the default, so
  a call without `n` returns the three values Q1, the median and Q3. `data` can be any iterable of sample values.
  [DOC S-dh7f43kc]
- Which input `quantiles` accepts: the page says it raises `StatisticsError` if `n` is less than 1 or if there is not
  at least one data point, and that for meaningful results the data should hold more points than `n`. Since Python
  3.13 a single data point no longer raises, so quantile estimates can be built up one sample at a time; the
  function was added in 3.8. [DOC S-dh7f43kc]
- The two methods in the page's words: `exclusive` (the default) is for data sampled from a population that can
  hold more extreme values than the sample, and the portion below the i-th of m sorted points is `i / (m + 1)`;
  `inclusive` is for population data or samples known to include the most extreme values, it treats the minimum as
  the 0th and the maximum as the 100th percentile, and the portion below the i-th point is `(i - 1) / (m - 1)`. The
  page's examples: nine values get the 10th to 90th percentiles under `exclusive`, eleven values the 0th to 100th
  under `inclusive`. [DOC S-dh7f43kc]
- Observed on Python 3.13.2 (macOS, 2026-10-19), the quartiles `quantiles(data)` gave for `1..5` were
  `[1.5, 3.0, 4.5]` under `exclusive` and `[2.0, 3.0, 4.0]` under `inclusive`; for `[1, 2]` `exclusive` gave
  `[0.75, 1.5, 2.25]`, outside the data's range, while `inclusive` gave `[1.25, 1.5, 1.75]`; one point `[5]` gave
  `[5, 5, 5]` under both; an empty list raised `StatisticsError: must have at least one data point` and `n=0` raised
  `StatisticsError: n must be at least 1`. An `exclusive` cut point can therefore lie below the minimum or above the
  maximum of a short list; an `inclusive` one stays between them. [DER S-dh7f43kc: the two formulas and the error
  sentences above, each call run on 3.13.2, macOS, 2026-10-19]
- NIST's Engineering Statistics Handbook defines the interquartile range as `IQ = Q3 - Q1`, the lower and upper
  quartiles being the 25th and 75th percentiles, and gives four fences: lower inner `Q1 - 1.5*IQ`, upper inner
  `Q3 + 1.5*IQ`, lower outer `Q1 - 3*IQ` and upper outer `Q3 + 3*IQ`. A point beyond an inner fence is a mild
  outlier and a point beyond an outer fence an extreme outlier. [DOC S-4hnlw34j]
- NIST's worked example takes the quartiles of its 90 ordered values at the `0.25 * (N + 1)`th and `0.75 * (N + 1)`th
  ordered points, linearly interpolated (22.75th point = 429.75, 68.25th point = 742.25), so `IQ` is 312.5 and its
  upper outer fence is 1679.75; the one value above the upper inner fence (1211.0) is called a mild outlier. The
  page does not give the fences' name "far out". [DOC S-4hnlw34j]
- The position `p * (N + 1)` of the NIST example is the `exclusive` rule of `statistics.quantiles` (`i / (m + 1) = p`
  gives `i = p * (m + 1)`), so `quantiles(data)` with the default method returns the quartiles the handbook's
  fences are computed from, and `inclusive` (`i = 1 + p * (m - 1)`; the 25th percentile of 90 values at the 23.25th
  point) would give a different `IQ` for the same list. A far-out fence "p75 plus three times the p25 to p75
  spread" is the handbook's upper outer fence. [DER S-4hnlw34j, S-dh7f43kc: the position formulas of the two pages
  compared; the handbook's N = 90 positions against the `exclusive` and `inclusive` formulas]
- Observed on Python 3.13.2 (macOS, 2026-10-19), the upper outer fence `q3 + 3 * (q3 - q1)` from `quantiles(data)`
  for the ten timings `[10, 11, 11, 12, 12, 12, 13, 13, 14, 40]` was 20.0 under `exclusive` (Q1 11.0, Q3 13.25) and
  18.25 under `inclusive` (Q1 11.25, Q3 13.0); for `[1, 2, 3, 4, 5, 6, 7, 8, 9, 100]` it was 24.75 and 21.25; the
  planted 40 and 100 were beyond the fence under both methods. For five values `[10, 11, 12, 12, 13]` the fences
  were 18.5 and 15.0. The method moved the fence by 1.75 to 3.5 here, so a fence is compared with values near it only
  for the method it was computed with. [DER S-4hnlw34j, S-dh7f43kc: the outer fence formula of the handbook applied to the quartiles of each method, run on 3.13.2, macOS, 2026-10-19]
- Observed on Python 3.13.2 (macOS, 2026-10-19): when most of the list is equal, as in `[30, 30, 30, 30, 30, 30, 31]`
  or `[5, 5, 5, 5]`, `quantiles` gave `Q1 = Q3` under both methods, so `IQ` is 0 and the fence collapses onto the
  quartile (30.0 for the first list), and the 31 is then beyond the fence although it is one unit from the rest.
  [DER S-4hnlw34j, S-dh7f43kc: the fence formula applied to a list with a zero spread, run on 3.13.2, macOS, 2026-10-19]
- Which quartile method a fence "should" use, and a minimum list size below which a fence is not meaningful, are not
  stated by the handbook page or the `statistics` page: the handbook shows one worked example with the `(N + 1)`
  rule and the `statistics` page only says the data should hold more points than `n`. [UNK: no page read names the
  quartile method for fences or a minimum sample for them]
- Whether CMPivot's `percentile` aggregation (listed in `mecm/cmpivot.md`) takes its value at the nearest rank is
  not stated by the pages read here; its page is not the Kusto one. [UNK: CMPivot's percentile method not stated]

## Reference
- Related: `mecm/cmpivot.md` (CMPivot's aggregation functions), `python/stdlib-cprofile-pstats.md` and
  `python/stdlib-os-loadavg.md` (other stdlib measurement readings).
- Sources: https://learn.microsoft.com/en-us/kusto/query/percentiles-aggregation-function (Fabric, Azure Data
  Explorer, Azure Monitor, Microsoft Sentinel); https://learn.microsoft.com/en-us/sql/t-sql/functions/percentile-disc-transact-sql;
  https://docs.python.org/3/library/statistics.html (`statistics.quantiles`); https://en.wikipedia.org/wiki/Percentile
  ("The nearest-rank method"); https://www.itl.nist.gov/div898/handbook/prc/section1/prc16.htm (NIST handbook,
  quartiles and outlier fences).

## Examples
- SNIPPET: a nearest-rank percentile of a list of numbers, and its rank in integers; context: Python 3
  stdlib, `values` non-empty, `pct` from 0 to 100; checked: run (3.13.2, macOS, 2026-10-13: `1..10` p95 gave 10,
  `1..20` gave 19, `1..21` gave 20, `1..100` gave 95, `1..101` gave 96, and the p50 of `1..10` gave 5)
  [DER S-or2wocyn, S-g5oa4uyp: the ordinal rank `ceil(P / 100 * N)` and the smallest value with at least P percent at or below it]
```python
def nearest_rank(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    rank = max(1, -(-pct * len(ordered) // 100))
    return ordered[rank - 1]
```
