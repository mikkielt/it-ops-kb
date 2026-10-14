---
topic: python/pytest-xdist
priority: P2
applies_to: [pytest-xdist, pytest]
retrieved_utc: 2026-10-14
sources: [S-t7c2nvll, S-lthpihsc, S-ng5lgn3p, S-qejsavhl, S-ew7mucsg, S-d77lvlq4, S-eaoeu53g, S-g7bkixrp, S-tt4fugbi, S-3cbnj3pk]
status: complete
---

# pytest-xdist parallel test distribution

## Summary
pytest-xdist runs a pytest suite across multiple worker processes with `-n`/`--numprocesses`, and
`--dist` picks how tests are grouped across those workers. `python/pytest.md` covers pytest
configuration itself; this article covers what changes when `-n` is used, which is exactly the setup
`_tools/tests.py` (`-n auto --dist loadscope`) and `_tools/stress_test.py` (`--dist load`, per its
comment "a class's scenario is built once, on one worker") use in this repository.

## Facts
- `-n auto` uses as many worker processes as the machine has physical CPU cores when `psutil` is
  importable, and otherwise the count comes from the fallbacks in the resolution order below;
  `-n logical` uses logical cores instead (needs `psutil`, and falls back to `-n auto` behaviour if
  `psutil` is missing or fails); `-n 0` disables xdist and runs everything in the main process;
  `-n <N>` requests exactly `N` workers. `--maxprocesses=N` caps the worker count and
  `--max-worker-restart` bounds how many crashed workers get restarted. [DER S-t7c2nvll, S-qejsavhl:
  the docs' physical-core statement, and the resolution order below, where physical cores come from
  `psutil` only]
- `--dist load` is the **default** distribution mode: pending tests go to any available worker with no
  guaranteed order or grouping. [DOC S-t7c2nvll]
- `--dist loadscope` groups tests by module (for plain test functions) and by class (for test
  methods, which takes priority over module grouping); each group is sent to one worker as a unit, so
  all tests sharing a module- or class-scoped fixture run in the same process. This is what this
  repository's `_tools/tests.py` uses (`XDIST = ["-n", "auto"]`, `--dist loadscope`, so "a class's
  scenario is built once, on one worker" per its own comment). [DOC S-t7c2nvll]
- `--dist loadfile` groups by containing file (whole file runs on one worker); `--dist loadgroup`
  groups by the `@pytest.mark.xdist_group(name=...)` marker (tests with the same group name always run
  on the same worker; ungrouped tests distribute as under `load`); `--dist worksteal` distributes
  tests evenly up front and then lets idle workers "steal" queued tests from busier ones once a worker
  has fewer than two tests left, which handles uneven test durations better than `load`; `--dist no`
  disables distribution (equivalent to `-n 0`, one test at a time, no parallelism). [DOC S-t7c2nvll]
- Each worker sets the `PYTEST_XDIST_WORKER` environment variable to its name (e.g. `"gw2"`) and
  `PYTEST_XDIST_WORKER_COUNT` to the total worker count for the session; the `worker_id` fixture
  returns the same worker name inside a test/fixture, or `"master"` if xdist is disabled (`-n0`).
  [DOC S-lthpihsc]
- A fixture with a scope higher than `function` (e.g. `session` or `module`) is **not** guaranteed to
  run only once overall when `-n` > 0: each worker does its own test collection and runs its own
  subset of tests, so a `session`-scoped fixture requested in more than one worker executes once *per
  worker*, not once for the whole run. pytest-xdist has no built-in way to force exactly one execution
  across all workers; the documented workaround is a `worker_id`-gated `FileLock` (e.g. via the
  `tmp_path_factory.getbasetemp().parent` shared temp directory) so only the first worker to reach the
  fixture computes the value and the rest read it back from a file. [DOC S-ng5lgn3p]
- `-s`/`--capture=no` (disabling pytest's output capture) does not work under pytest-xdist: the
  underlying `execnet` transport between the controller and workers does not support forwarding
  worker stdout/stderr back to the terminal, and there are no plans to support it. For the same
  reason, `--pdb` is disabled when tests are distributed; debugging is best done by first finding a
  failing test under xdist and then re-running it without `-n`. [DOC S-ng5lgn3p]
- Test order and count must be identical across workers (e.g. a `pytest.mark.parametrize` value list
  must not be produced from a `set` or other unordered iterable), or xdist raises an error; converting
  to a `list` or sorting the values fixes it. [DOC S-ng5lgn3p]

### Worker count and scheduling
- The default `pytest_xdist_auto_num_workers` hook resolves `-n auto` and `-n logical` in this order: the `PYTEST_XDIST_AUTO_NUM_WORKERS` environment variable (an integer); else `psutil.cpu_count()` (physical cores for `auto`, logical for `logical`) when `psutil` is importable; else the length of `os.sched_getaffinity(0)` where that exists; else `os.cpu_count()`. [CODE S-qejsavhl: src/xdist/plugin.py#pytest_xdist_auto_num_workers]
- `os.cpu_count()` returns the number of logical CPUs in the system (`os.process_cpu_count()` the number usable by the current process), and on Python 3.13+ `-X cpu_count=N` or `PYTHON_CPU_COUNT` overrides both, which the docs suggest for limiting CPU use in a container. [DOC S-ew7mucsg, S-d77lvlq4]
- So without `psutil` on Windows, where `os.sched_getaffinity` does not exist (`hasattr` is False on CPython 3.14.7 for Windows, checked 2026-09-29), `-n auto` starts one worker per logical CPU, not per physical core as the docs describe; this repository's `uv.lock` has no `psutil`, so `tests.py` and `stress_test.py` start one worker per logical CPU (8 on an 8-thread host) on Windows, and on Linux as many as the process's CPU affinity allows. `PYTEST_XDIST_AUTO_NUM_WORKERS` sets the count on every Python version the suite runs on (3.11 included), where `PYTHON_CPU_COUNT` works only from 3.13. [DER S-qejsavhl, S-ew7mucsg, S-d77lvlq4, S-t7c2nvll: the resolution order above, the lock file's package list, and the 3.13 floor of `PYTHON_CPU_COUNT`]
- The environment variable and a `pytest_xdist_auto_num_workers(config)` hook in `conftest.py` both change what `auto` and `logical` mean; the hook wins when both are set and may return `None` to fall back to the default. [DOC S-t7c2nvll]
- `--maxschedchunk` caps how many tests `--dist load` sends to a worker in one step: `1` sends them one by one (for a few slow tests), larger values let a worker reuse fixtures across consecutive tests, and at least 2 tests go to each worker at the start. [CODE S-qejsavhl: src/xdist/plugin.py#pytest_addoption]
- With `--dist loadscope`, xdist by default reorders scopes by their number of tests (`--loadscope-reorder`) to improve parallelism, at the cost of the partial order of tests; `--no-loadscope-reorder` keeps the order for plugins that depend on it. [CODE S-qejsavhl: src/xdist/plugin.py#pytest_addoption]
- Under `loadscope` one test class or module is the unit of work: a class whose tests take minutes keeps one worker busy for all of it while the others go idle at the end of the run, and `worksteal` or `load` can spread a class that holds no shared class-scoped state. [DER S-t7c2nvll: the grouping and `worksteal` rules above]

### Wall time of a loadscope run
- The scheduler starts distributing only once every worker has sent its collection of the whole suite and the collections are identical (`collection_is_completed` needs a collection from each of `numnodes` workers); a mismatch aborts the run ("Different tests collected"). Each worker therefore imports and collects the full suite before the first test runs. [CODE S-eaoeu53g: src/xdist/scheduler/loadscope.py#LoadScopeScheduling.schedule]
- A work unit is the node id up to its last `::` (`nodeid.rsplit("::", 1)[0]`): a class for a test method, a module for a test function. Units go into the queue ordered by their number of tests, largest first, when `--loadscope-reorder` is on (the default), not by how long they take. [CODE S-eaoeu53g: src/xdist/scheduler/loadscope.py#LoadScopeScheduling._split_scope, schedule]
- When there are more workers than units the extra workers are shut down; every other worker first gets one unit, then a second if one is left (issue 277). After that a worker gets the next unit only when it has 2 or fewer pending tests, and a worker that finds the queue empty is told to shut down. A unit already sent to a worker stays there: it moves only when that worker crashes, and loadscope has no work stealing. [CODE S-eaoeu53g: src/xdist/scheduler/loadscope.py#LoadScopeScheduling._reschedule, schedule, remove_node]
- So the wall time of a `loadscope` run has three parts: the slowest worker's start and full-suite collection; then the run itself, which cannot end before the longest single unit has run on one worker nor before the summed test time divided by the worker count; then the shutdown of the workers. A unit that the queue puts last because it has few tests but that runs long can start late and then set the end of the run alone. [DER S-eaoeu53g, S-t7c2nvll: the collection barrier, the unit rule and the no-steal rule above]
- Load on the host does not change the worker count or the grouping: `-n auto` is resolved from CPU counts and an environment variable only (the order above), and the scheduler orders units by test count, so a loaded host runs the same units on the same number of workers with fewer CPU cycles for each. Each worker's start, collection and every unit then take longer, and the longest unit and the slowest worker's start are the parts that stretch the end of the run. [DER S-eaoeu53g, S-qejsavhl: the worker-count resolution order and the scheduler's inputs; the effect of load on duration follows from sharing CPUs]
- On macOS `os.sched_getaffinity` does not exist (`hasattr` is False on CPython 3.13.2 for macOS, checked 2026-10-13), so without `psutil` `-n auto` starts one worker per logical CPU there, as on Windows; `os.getloadavg()` reports how many threads are running or runnable against that count (`python/stdlib-os-loadavg.md`). [DER S-qejsavhl, S-ew7mucsg: the resolution order above and a run on macOS]

### Wall time of a load and a worksteal run
- `--dist load` hands out consecutive tests from the front of the collection, not single tests: with at least two tests per worker, each worker's first chunk is `max(min(len(collection) // workers // 4, maxschedchunk), 2)` tests, so with `--maxschedchunk` unset it is a quarter of a worker's even share; with fewer than two tests per worker, tests go one each, round-robin. [CODE S-g7bkixrp: src/xdist/scheduler/load.py#LoadScheduling.schedule]
- A `load` worker is topped up when its pending tests fall below `max(2, len(global pending) // workers // 4)`, to `max(2, len(global pending) // workers // 2)`, at most `max(2 - own pending, maxschedchunk)` tests per step; the step is skipped when the test that just finished took 0.1 s or more and the worker still holds two or more. Chunks therefore shrink as the global queue drains. [CODE S-g7bkixrp: src/xdist/scheduler/load.py#LoadScheduling.check_schedule]
- Only `--dist load --maxschedchunk 1` hands tests singly, and even then each worker holds two (the running test and the next): the first chunk is 2 and a finished test is replaced by one. A chunk already sent stays with its worker until that worker crashes; `load` has no stealing. [CODE S-g7bkixrp: src/xdist/scheduler/load.py#LoadScheduling.schedule, check_schedule, remove_node]
- Because `load` cuts the collection into consecutive chunks, tests of one module or class usually land on the same worker, and a long module is split only at chunk boundaries; `load` and `worksteal` both wait for every worker's identical full collection before the first test, as `loadscope` does. [DER S-g7bkixrp, S-tt4fugbi, S-eaoeu53g: the chunking above and the collection barrier]
- `--dist worksteal` first splits the whole collection into equal consecutive slices, one per worker (`len(pending) // workers_remaining` each). A worker with fewer than two pending tests is idle: when the global queue is empty, the scheduler asks the worker with the longest queue for `min(len // 2, len - 2)` of its last tests, one request at a time, and shuts idle workers down when nothing is stealable. [CODE S-tt4fugbi: src/xdist/scheduler/worksteal.py#WorkStealingScheduling.check_schedule]
- The worker gives back stolen tests only if every requested one is still queued, else none; a test it has started is never moved. `WorkStealingScheduling` never reads `--maxschedchunk`, whose help text names `--dist=load` only. [CODE S-3cbnj3pk, S-tt4fugbi, S-qejsavhl: src/xdist/remote.py#steal, src/xdist/scheduler/worksteal.py#WorkStealingScheduling.__init__, src/xdist/plugin.py#pytest_addoption]
- So a suite with two very slow modules runs unevenly under `load` with default chunks: each slow module's tests sit in the chunks of one or two workers, and the rest of the run waits for them. `worksteal` moves the unstarted tail of such a queue to an idle worker, and `load --maxschedchunk 1` lets every idle worker take the next test; each worker that runs any test of a module or class sets up that scope's fixtures itself, so spreading a scope costs one more setup per extra worker. [DER S-g7bkixrp, S-tt4fugbi, S-ng5lgn3p: the chunk, steal and per-worker fixture rules above]

## Reference
```toml
# this repo's pyproject.toml dev group provides pytest-xdist; _tools/tests.py invokes it as:
# uv run --frozen python -m pytest -n auto --dist loadscope -m "not stress" _tools
```
- SNIPPET: pin two tests to the same xdist worker with `xdist_group`, regardless of module/class grouping; context: pytest-xdist, `--dist loadgroup` (or any dist mode, since grouped tests always share a worker); checked: syntax [DOC S-t7c2nvll: `--dist loadgroup` groups by the `xdist_group` marker name]
```python
import pytest

@pytest.mark.xdist_group(name="group1")
def test1():
    pass

class TestA:
    @pytest.mark.xdist_group("group1")
    def test2():
        pass
# test1 and TestA::test2 are guaranteed to run on the same xdist worker.
```

## Examples
- `pytest -n auto --dist loadscope` (this repo's default) keeps every test in one module or class on
  a single worker, so a module-scoped fixture that copies the kb tree is built once per module rather
  than once per test.
- `pytest -n auto --dist load` (`_tools/stress_test.py`'s mode) sends each worker consecutive chunks
  of tests, which is fine when each test builds its own isolated fixture rather than sharing a
  module- or class-scoped one; adding `--maxschedchunk 1` makes it hand tests out singly (two held
  per worker).
