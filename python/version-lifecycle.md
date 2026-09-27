---
topic: python/version-lifecycle
priority: P2
applies_to: [python]
retrieved_utc: 2026-09-27
sources: [S-4sqhclzg, S-gcphwjqj, S-6wn73ixe, S-sgovapjd, S-lob25y46, S-tqvuutrg, S-mpeiuyoe, S-2ue7gffd]
status: complete
files: [python/version-lifecycle.csv]
---

# CPython release and support lifecycle

## Summary
CPython has released one new feature version per year, in October, since Python 3.9 (PEP 602). Each
version then goes through bugfix releases (~every 2 months, for roughly the first 18-24 months) and
then source-only security-fix releases on an as-needed basis, ending five years after that version's
first release. Python 3.9 is the oldest version this kb's tools claim to support
(`requires-python = ">=3.9"` in this repository's own `pyproject.toml`) and it has already reached
end-of-life. The full table of first-release/status/end-of-life dates is `python/version-lifecycle.csv`.

## Facts
- Since Python 3.9 (PEP 602, "Annual Release Cycle for Python"), CPython ships one new feature version
  every year, "in October every year." [DOC S-4sqhclzg]
- Five phases exist per the devguide's status key (drawing on PEP 602): **feature** (before the first
  beta, still accepts new features), **prerelease** (after the first beta, only fixes), **bugfix**
  ("maintenance"/"stable": bug and security fixes, new binaries roughly every two months),
  **security** (source-only fixes, no more binaries; starts after 2 years for 3.13+, or 18 months for
  versions before 3.13), **end-of-life** (five years after release; the branch is frozen, no further
  changes of any kind). [DOC S-2ue7gffd]
- Python **3.9** reached end-of-life on **2025-10-31**, which PEP 596 calls 5 years after its 2020-10-05 final
  release; 3.9.25 (2025-10-31) was its final security release, and the devguide/PEP both state the
  codebase "is now frozen and no further updates will be provided nor issues of any kind will be
  accepted on the bug tracker." [DOC S-gcphwjqj]
- Python **3.10** (final release 2021-10-04) had its last regular
  bugfix release with binary installers on 2023-04-05 (3.10.11); source-only security fixes continue
  on an as-needed basis, documented as expected "until approximately October 2026" (five years after
  the 3.10.0 final release) — as of this article's retrieval date (2026-09-27) that end-of-life point
  has not yet been confirmed as having occurred. [DOC S-6wn73ixe]
- Python **3.11** (final release 2022-10-24) had its last regular bugfix release with installers on
  2024-04-02 (3.11.9); source-only security fixes are documented as provided "until October 2027".
  [DOC S-sgovapjd]
- Python **3.12** (final release 2023-10-02) had its last regular bugfix release with installers on
  2025-04-08 (3.12.10); source-only security fixes are documented as provided "until October 2028".
  [DOC S-lob25y46]
- Python **3.13** (final release 2024-10-07) is, as of this article's retrieval date, still in its
  regular bugfix phase; its documented schedule expects the final regular bugfix release with
  installers (3.13.16) on 2026-10-06, after which only source-only security fixes continue, documented
  as provided "until October 2029". [DOC S-tqvuutrg]
- Python **3.14** (final release 2025-10-07) is the newest released feature version; it is documented
  as expected to "receive bugfix updates approximately every two months for approximately 24 months"
  (longer than the ~18 months typical of 3.9-3.12), with source-only security fixes thereafter
  documented as provided "until October 2030". [DOC S-mpeiuyoe]
- "Security-only" (the **security** phase) means: no more binary installers are built for that
  version, and only source patches for security vulnerabilities are released, on an as-needed (not
  fixed-cadence) basis, up to that version's five-year end-of-life cutoff. [DOC S-2ue7gffd, S-6wn73ixe]

## Reference
Full table: `python/version-lifecycle.csv` (version, first_release, status_as_of_2026-09-27,
end_of_life, source id).

## Examples
- A tool declaring `requires-python = ">=3.9"` (as this repository's `pyproject.toml` does) targets a
  floor that is already past end-of-life; the floor only affects which Python *syntax and stdlib
  features* the tool may assume are unavailable (e.g. `python/stdlib-sqlite3-csv.md` notes
  `csv.QUOTE_STRINGS` needs 3.12+), not whether that exact version still receives fixes upstream.
- Before relying on a Python 3.10 or 3.11 install still receiving security patches, check the current
  date against `python/version-lifecycle.csv`'s `end_of_life` column rather than assuming from memory.
