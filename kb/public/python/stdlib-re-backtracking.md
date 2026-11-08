---
topic: python/stdlib-re-backtracking
priority: P3
applies_to: "Python stdlib re: backtracking, possessive quantifiers and atomic groups (3.11+), and bounding a match's time; probes on Python 3.13.2, macOS, 2026-11-08"
retrieved_utc: 2026-11-08
sources: [S-allbto7m, S-rr7gtgt5, S-ysz5zha6]
status: partial
---

# stdlib re: backtracking, and bounding a match's time

## Summary
The `re` module matches by backtracking: a greedy quantifier gives characters back when what follows it fails.
Two quantifiers next to each other that can take the same characters (`\w*\w*x`) therefore split a run of
letters in many ways before a failing search gives up, and the time grows with a power of the line's length.
Possessive quantifiers and atomic groups, added in Python 3.11, forbid the giving back. The `re` page documents
no timeout and no way to stop a running match; a signal handler that raises, in the main thread on Unix, stops
one.

## Facts
### What the docs say
- Greedy quantifiers backtrack: in `a*a` on `aaaa` the `a*` first takes all four letters and is then backtracked to three, so the final `a` can match. [DOC S-allbto7m]
- A possessive quantifier (`*+`, `++`, `?+`, `{m,n}+`) "do[es] not allow back-tracking when the expression following it fails to match"; `x*+`, `x++` and `x?+` are equivalent to `(?>x*)`, `(?>x+)` and `(?>x?)`, and `x{m,n}+` to `(?>x{m,n})`; the docs mark each "Added in version 3.11". [DOC S-allbto7m]
- An atomic group `(?>...)` matches the pattern inside it as if it were a separate expression and, once left, "has thrown away all stack points within itself", so a later failure cannot reopen it; the docs' example is that `(?>.*).` never matches anything. Added in 3.11. [DOC S-allbto7m]
- The `re` page read on 2026-11-08 holds neither the word "timeout" nor "interrupt": it documents no time limit on a match and no way to stop one. The third-party `regex` module that Presidio uses does take a per-match timeout (`privacy/presidio-recognizer-yaml.md`). [DER S-allbto7m: absence on the page, read in full by word search]
- A Python signal handler runs in the main thread of the main interpreter, and only that thread may set a new handler; `signal.setitimer` and `SIGALRM` are marked "Availability: Unix", so neither exists on Windows. [DOC S-rr7gtgt5]

### Measured here
- On Python 3.13.2 (macOS, 2026-11-08), `re.compile(r'\w*\w*x').search('a' * n)` on a line with no `x` took about 7.5 times longer for each doubling of `n` from 100 to 400, and `\w*\w*\w*x` about 15 times longer: with k adjacent quantifiers that take the same characters, a failing search grows about as `n` to the power k + 1. At `n` = 400 the three-quantifier form took seconds and the two-quantifier form tens of milliseconds. [DER S-allbto7m: one run, one host; the growth ratios are the finding, the times depend on the host]
- The same lines with the quantifiers made possessive (`\w*+\w*+x`) or atomic (`(?>\w*)\w*x`) took well under a millisecond at `n` = 400, and the time per doubling was about 4 times, one factor of `n` for the start positions of `search`. [DER S-allbto7m: same run; possessive and atomic forms behaved alike]
- In the same run a `signal.setitimer(signal.ITIMER_REAL, 0.2)` whose `SIGALRM` handler raised an exception stopped a `\w*\w*\w*x` search at `n` = 400 after 0.2 s, in the main thread, instead of letting it run for seconds. [DER S-allbto7m, S-rr7gtgt5, S-ysz5zha6: one run; the handler ran during the C-level match, not after it, as the signal check in the matcher (next section) allows]

### What the source does
- In CPython 3.14.7 the matcher function in `sre_lib.h` keeps a counter, `sigcount`, and its `DISPATCH` step (and the `dispatch:` label where computed gotos are not used) runs `MAYBE_CHECK_SIGNALS`, which calls `PyErr_CheckSignals()` each time the low 12 bits of the counter are zero, that is every 4096 opcodes, and returns `SRE_ERROR_INTERRUPTED` when it reports an exception. [CODE S-ysz5zha6: Modules/_sre/sre_lib.h#_MAYBE_CHECK_SIGNALS, DISPATCH; read for the matcher function only, not for which `re` entry points reach it]

### How it fits
- A check that refuses a pattern row whose adjacent quantifiers can take the same characters closes the cause of a failing search that grows with the line's length; a deadline tested between lines or files bounds a file's work only while each single match is short, because a deadline is read between match calls. A time limit that must also cut one slow match needs a main-thread Unix signal timer or a separate process, and has no portable stdlib form on Windows. [DER S-allbto7m, S-rr7gtgt5: the documented backtracking and possessive forms, the absence of a timeout, the Unix-only signal timer and the probes above]
- Open: whether the check above is reached by every `re` function (`search` was probed, `fullmatch`, `findall` and `sub` were not) and whether it is the same on other CPython versions and on Windows. [UNK: see `_gaps.md`]

## Reference
- Python `re` module: https://docs.python.org/3/library/re.html
- Python `signal` module: https://docs.python.org/3/library/signal.html
- Related: `privacy/presidio-recognizer-yaml.md` (the `regex` module's per-match timeout), `python/stdlib-windows-portability.md`.

## Examples
- SNIPPET: the same match written with overlapping adjacent quantifiers and in the possessive form; context: Python 3.11+ (possessive quantifiers and atomic groups do not exist before 3.11); checked: run [DER S-allbto7m: forms from the `re` page; run 2026-11-08 on Python 3.13.2, macOS]
```python
import re

slow = re.compile(r"\w*\w*\w*x")   # adjacent quantifiers take the same letters
fast = re.compile(r"\w*+\w*+x")    # possessive: no giving back

line = "a" * 400
assert fast.search(line) is None   # returns at once; slow.search(line) takes seconds
```
