---
topic: python/pytest-xdist
priority: P2
applies_to: [pytest-xdist, pytest]
retrieved_utc: 2026-09-29
sources: [S-t7c2nvll, S-lthpihsc, S-ng5lgn3p, S-qejsavhl, S-ew7mucsg, S-d77lvlq4]
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
- `-n auto` uses as many worker processes as the machine has physical CPU cores; `-n logical` uses
  logical cores instead (needs `psutil`, and falls back to `-n auto` behaviour if `psutil` is missing
  or fails); `-n 0` disables xdist and runs everything in the main process; `-n <N>` requests exactly
  `N` workers. `--maxprocesses=N` caps the worker count and `--max-worker-restart` bounds how many
  crashed workers get restarted. [DOC S-t7c2nvll]
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
- `pytest -n auto --dist load` (`_tools/stress_test.py`'s mode) distributes tests one at a time with
  no grouping, which is fine when each test builds its own isolated fixture rather than sharing a
  module- or class-scoped one.
