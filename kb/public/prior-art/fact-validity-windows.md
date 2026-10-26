---
topic: prior-art/fact-validity-windows
priority: P3
applies_to: "validity windows on stored facts: SQL Server system-versioned temporal tables, Graphiti (getzep/graphiti) edges, git revision ranges"
retrieved_utc: 2026-10-26
sources: [S-fircu2ge, S-jew5vvlr, S-ybdqnjmp, S-g2oco2hj, S-x44tjiek, S-zflhytlw, S-gvt5wbk7, S-gaeidf4e]
status: partial
---

# Prior art: validity windows on facts

## Summary
Two systems that store changing facts both keep the old version and record when it stopped being true, instead of
rewriting it: SQL Server's system-versioned temporal tables (a start and an end column on every row, the end set to the
transaction time of the change) and Graphiti's knowledge-graph edges (`valid_at` and `invalid_at` on each fact, a
contradicting newer fact closing the older one at its own start). Both treat the end of a window as exclusive, so the
instant of a change belongs to the new version only. Git names a commit range `r1..r2` with the start excluded, which a
commit-range marker must not be confused with. Whether a commit lies inside a range cannot be decided without the
repository; no source read says how a documentation store should do it.

## Facts
- SQL Server system-versioned temporal tables record the period of validity of every row in two `datetime2` period columns, a start (typically `ValidFrom`) and an end (typically `ValidTo`); the current table holds the current value and a history table holds each earlier version with its start and end. [DOC S-fircu2ge]
- An insert sets `ValidTo` to the maximum value `9999-12-31`, which marks the row open: an open end is a maximum value, not a null. [DOC S-fircu2ge]
- An update stores the previous row in the history table with `ValidTo` set to the begin time of the current transaction, which closes it, and gives the new current row that same time as `ValidFrom`; a delete closes the old row the same way and removes it from the current table. So the old version's end and the new version's start are one instant. [DOC S-fircu2ge]
- The `AS OF` query returns rows where `ValidFrom <= date_time AND ValidTo > date_time`, so a period includes its start and excludes its end, and at the instant of a change only the new version qualifies. The `BETWEEN` form is documented separately as also returning rows that became active exactly on its upper bound. [DOC S-fircu2ge]
- A fact window that ends on the day the next version starts (end of one window equal to the start of the next) answers an as-of date unambiguously only if one bound is exclusive; with both bounds inclusive, the change date matches both versions. [DER S-fircu2ge: the `AS OF` predicate shows the closed-open choice that avoids it]
- Graphiti's project description says its facts have validity windows and that when information changes the old facts are invalidated, not deleted, so one can query what is true now or at any past point in time. [DOC S-g2oco2hj]
- A Graphiti `EntityEdge` carries `valid_at` ("when the fact became true"), `invalid_at` ("when the fact stopped being true"), both optional, and separately `created_at` and `expired_at` (when the edge was invalidated in the store): one pair for when the fact held, one for when the store knew. Its field descriptions say soft deadlines are not `invalid_at` and that a future-tense plan takes the episode's reference time as `valid_at`, not the date it is planned for. [CODE S-jew5vvlr: graphiti_core/edges.py#EntityEdge]
- When a new edge contradicts an older one that became valid earlier, Graphiti sets the older edge's `invalid_at` to the new edge's `valid_at` and fills its `expired_at` with the current time; the older edge is kept. [CODE S-ybdqnjmp: graphiti_core/utils/maintenance/edge_operations.py#resolve_edge_contradictions]
- The same function skips a candidate whose `invalid_at` is at or before the new edge's `valid_at` (or the reverse), so two windows that only touch at one instant do not count as overlapping: its window test is closed-open too. [CODE S-ybdqnjmp: graphiti_core/utils/maintenance/edge_operations.py#resolve_edge_contradictions]
- A Graphiti edge that arrives with an `invalid_at` already set, or that a later edge's `valid_at` supersedes, is stored as already expired. [CODE S-ybdqnjmp: graphiti_core/utils/maintenance/edge_operations.py#_apply_temporal_invalidation]
- Git's `r1..r2` means the commits reachable from `r2` excluding those reachable from `r1`, a shorthand for `^r1 r2`: the start commit is excluded and the end is included. [DOC S-x44tjiek]
- A commit-range marker on a fact that reuses the `..` of git therefore reads, by git's own meaning, as "after the first commit, up to and including the second"; a date window starts on its first date. A rule for such a marker states which end is included. [DER S-x44tjiek: the git range definition]
- Git accepts an abbreviated object name when it is a leading substring unique in the repository, and `core.abbrev` (unset or `auto`) abbreviates to a length computed from the approximate number of packed objects, "hopefully" enough to stay unique for some time; the minimum length is 4. [DOC S-x44tjiek, S-zflhytlw]
- So a short commit id that was unique when a fact was written can become ambiguous as the source repository grows; a check that sees only the text of the fact can test the form of the id (hexadecimal, a length) and not its uniqueness. [DER S-x44tjiek, S-zflhytlw: uniqueness is relative to the repository, the abbreviation length grows with its size]
- `git merge-base --is-ancestor A B` exits 0 when `A` is an ancestor of `B`, 1 when not, and another non-zero status on error; run as `git merge-base --is-ancestor HEAD HEAD` on git 2.50.1 (macOS, 2026-10-26) it exited 0, so a commit counted as its own ancestor. [DER S-gvt5wbk7: the documented exit statuses; the same-commit case observed once on 2.50.1]
- Whether a revision X lies in a range A to B of a source repository takes two ancestry tests (A before X and X before B) against that repository, and holds only on one line of history: two commits on different branches are neither ancestors of each other. A kb that holds only the fact text cannot decide it. [DER S-gvt5wbk7: the ancestor test is defined on the commit graph]
- `datetime.date.fromisoformat` on Python 3.13.2 (macOS, 2026-10-26) rejected `2024-13-45` and `2024-02-30` with `ValueError` ("month must be in 1..12", "day is out of range for month") and accepted `2025-09-30`, but also accepted `20240301` and `2024-W10-1`; a window checker that wants only `YYYY-MM-DD` matches that form with a pattern first and lets `fromisoformat` check the calendar. [DER S-gaeidf4e: the accepted forms are documented in the kb's stdlib-datetime-iso-week article; the cases observed on 3.13.2]
- No source read states how a Markdown documentation store should mark the window of a fact in its text, or whether any documentation tool does; only database and graph-store designs were found. [UNK: logged in `_gaps.md`]

## Reference
| system | start field | end field | open end | end bound | old version on change |
|---|---|---|---|---|---|
| SQL Server temporal table | `ValidFrom` | `ValidTo` | `9999-12-31` | exclusive (`ValidTo > t`) | moved to the history table, `ValidTo` = transaction time |
| Graphiti edge | `valid_at` | `invalid_at` | `None` | exclusive in its overlap test | kept, `invalid_at` = new edge's `valid_at`, `expired_at` = now |
| git range `r1..r2` | `r1` (excluded) | `r2` (included) | not defined | included | not applicable |

See `python/stdlib-datetime-iso-week.md` for the date parsing forms and `gitlab/git-trailers-and-hooks.md` for the
`--is-ancestor` exit statuses.

## Examples
- SNIPPET: the closed-open test a window check uses for an as-of date; context: Python 3.11 or later, ISO dates; checked: syntax [DER S-fircu2ge: the `AS OF` predicate applied to dates]
```python
from datetime import date

def holds(start: date, end: date | None, as_of: date) -> bool:
    # start inclusive, end exclusive, an open end is None
    return start <= as_of and (end is None or as_of < end)
```
