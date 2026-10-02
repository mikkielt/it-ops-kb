#!/usr/bin/env python3
"""Prove a test-suite speed-up lost no test, and time a suite run against a bound. Standard library only; described in kb/_self/tools.md.

  perfcheck.py ids                              print the test ids tests.py and stress_test.py collect at HEAD (the working
                                                tree), one per line, sorted
  perfcheck.py ids --write FILE                 write them to FILE (the baseline); a second run changes nothing
  perfcheck.py ids --against FILE               compare them with the ids in FILE; a baseline id not collected now fails
  perfcheck.py ids --base REV                   compare them with the ids collected at git revision REV, in a temporary
                                                worktree that is removed afterwards (the working tree is never touched)
  --allow-removed FILE                          ids in FILE (one per line, `#` comments) may be missing
  perfcheck.py time --max-seconds N [--stress] [ARGS...]
                                                run tests.py (stress_test.py with --stress) with ARGS and fail when it
                                                takes longer than N seconds, or fails itself

The ids are what `pytest --collect-only -q` prints for the two selections the runners use: `_tools` with -m "not stress"
(tests.py) and `_tools/test_stress.py` with -m stress (stress_test.py). Nothing runs and nothing touches the network.
Ids added since the baseline are listed and do not fail; the baseline file is appended to by whoever adds tests.

Exit codes: 0 no id lost (or the run was within its bound); 1 an id is missing and not allowed, or a run was over its
bound or failed; 2 it could not do what was asked (bad arguments, an unreadable file, a failed collection, not a clone).
"""
import argparse, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SELECTIONS = (  # (pytest arguments after the collect options, a path that must exist for the selection to apply)
    (["_tools", "-m", "not stress"], "_tools"),  # tests.py: FULL_M over every test module
    (["_tools/test_stress.py", "-m", "stress"], "_tools/test_stress.py"),  # stress_test.py
)
REPO_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_PREFIX")


PLACEHOLDER = "<root>"
ABSOLUTE = re.compile(r"(?<![\w<>~.])(/(?:Users|private/var|var/folders|home/(?!jan\.kowalski/))|[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/])")  # a clone's or user's absolute path in an id


class PerfError(Exception):
    """Something perfcheck could not do (exit 2)."""


def clean_env():
    env = {k: v for k, v in os.environ.items() if k not in REPO_VARS}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def pytest_command():
    sys.path.insert(0, str(TOOLS))
    import tests
    cmd = tests.pytest_cmd()
    if cmd is None:
        raise PerfError("pytest is needed: install uv (https://docs.astral.sh/uv/) and rerun, or `pip install pytest`")
    return cmd


def normalize(test_id, root):
    """`test_id` with the repository root, in any spelling (posix or Windows, forward or back slashes, as given or
    resolved), replaced by <root>, so an id that carries a fixture's absolute path is the same in every clone."""
    spellings = set()
    for r in (Path(root), Path(root).resolve()):
        for sp in (str(r), r.as_posix(), str(r).replace("/", "\\"), str(r).replace("\\", "/")):
            spellings.add(sp.rstrip("/\\"))
    for sp in sorted(spellings, key=len, reverse=True):
        if sp:
            test_id = test_id.replace(sp, PLACEHOLDER)
    return re.sub(re.escape(PLACEHOLDER) + r"[^\]\s]*", lambda m: m.group(0).replace("\\", "/"), test_id)


def parse_collected(text):
    """The test ids in `pytest --collect-only -q` output: lines with `::` that are not summary or error lines."""
    ids = set()
    for line in text.splitlines():
        if "::" not in line or line[:1] in (" ", "=", "<", "-", "E", "!") or " " in line.split("::", 1)[0]:
            continue
        path, rest = line.split("::", 1)
        ids.add(path.replace("\\", "/") + "::" + rest.rstrip())
    return ids


def collect_ids(root, cmd=None):
    """The sorted ids both selections collect under `root`; PerfError when pytest fails to collect."""
    cmd = cmd or pytest_command()
    ids = set()
    for args, needs in SELECTIONS:
        if not (Path(root) / needs).exists():
            continue
        out = subprocess.run(cmd + ["--collect-only", "-q", "-p", "no:cacheprovider"] + args, cwd=str(root), env=clean_env(),
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if out.returncode not in (0, 5):
            raise PerfError(f"collecting {' '.join(args)} in {root} failed (exit {out.returncode}): "
                            + (out.stdout + out.stderr).strip()[-600:])
        ids |= {normalize(i, root) for i in parse_collected(out.stdout)}
    return sorted(ids)


def collect_at(rev, collect=collect_ids, repo=ROOT):
    """The ids at git revision `rev`, collected in a temporary detached worktree that is removed afterwards."""
    tmp = Path(tempfile.mkdtemp(prefix="perfcheck-"))
    wt = tmp / "wt"
    git = ["git", "-C", str(repo)]
    added = False
    try:
        out = subprocess.run(git + ["worktree", "add", "--detach", str(wt), rev], env=clean_env(), capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        if out.returncode != 0:
            raise PerfError(f"cannot check out {rev}: {out.stderr.strip()}")
        added = True
        return collect(wt)
    finally:
        if added:
            subprocess.run(git + ["worktree", "remove", "--force", str(wt)], env=clean_env(), capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(git + ["worktree", "prune"], env=clean_env(), capture_output=True)


def read_ids(path):
    """The ids in a text file: one per line, blank lines and `#` comments left out."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise PerfError(f"cannot read {path}: {e.strerror or e}") from e
    ids = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    bad = [i for i in ids if ABSOLUTE.search(i.split("::", 1)[-1])]
    if bad:
        raise PerfError(f"{path} holds an absolute path in an id (regenerate it with `ids --write`): {bad[0]}")
    return ids


def compare(baseline, head, allowed=()):
    """(removed, added, allowed_removed): baseline ids missing at head and not allowed, ids new at head, baseline ids missing
    at head that the allow list names."""
    base, now, ok = set(baseline), set(head), set(allowed)
    missing = base - now
    return sorted(missing - ok), sorted(now - base), sorted(missing & ok)


def write_baseline(path, ids):
    """Write the ids whole or not at all; the same ids give the same bytes."""
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("".join(i + "\n" for i in sorted(set(ids))), encoding="utf-8", newline="\n")
    os.replace(tmp, p)


def run_ids(a, collect=collect_ids, root=ROOT):
    head = collect(root)
    if a.write:
        write_baseline(a.write, head)
        print(f"wrote {a.write}")
    if not (a.against or a.base):
        if not a.write:
            sys.stdout.write("".join(i + "\n" for i in head))
        return 0
    baseline = read_ids(a.against) if a.against else collect_at(a.base, collect, root)
    removed, added, allowed = compare(baseline, head, read_ids(a.allow_removed) if a.allow_removed else ())
    for i in added:
        print(f"added: {i}")
    for i in allowed:
        print(f"removed (allowed): {i}")
    for i in removed:
        print(f"MISSING: {i}")
    where = a.against or f"revision {a.base}"
    print(f"perfcheck ids: {len(removed)} missing, {len(added)} added, {len(allowed)} removed on the allow list, against {where}")
    return 1 if removed else 0


def run_suite(args, stress=False):
    script = TOOLS / ("stress_test.py" if stress else "tests.py")
    return subprocess.run([sys.executable, str(script)] + args, cwd=str(ROOT), env=clean_env()).returncode


def run_time(a, extra, runner=run_suite, clock=time.monotonic):
    start = clock()
    code = runner(extra, a.stress)
    seconds = clock() - start
    if code != 0:
        print(f"perfcheck time: the suite run failed (exit {code}) after {seconds:.1f} s")
        return 1
    if seconds > a.max_seconds:
        print(f"perfcheck time: {seconds:.1f} s is over the bound of {a.max_seconds:g} s")
        return 1
    print(f"perfcheck time: {seconds:.1f} s within the bound of {a.max_seconds:g} s")
    return 0


def main(argv=None, collect=collect_ids, runner=run_suite, clock=time.monotonic, root=ROOT):
    ap = argparse.ArgumentParser(prog="perfcheck.py", description="Prove a test-suite speed-up lost no test.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ids = sub.add_parser("ids", help="collect the test ids and compare them with a baseline")
    ids.add_argument("--against", help="a text file of ids, one per line")
    ids.add_argument("--base", help="a git revision whose ids are collected in a temporary worktree")
    ids.add_argument("--allow-removed", help="a file of ids that may be missing")
    ids.add_argument("--write", help="write the ids at HEAD to this file")
    tm = sub.add_parser("time", help="time a suite run against a bound; other arguments go to tests.py")
    tm.add_argument("--max-seconds", type=float, required=True)
    tm.add_argument("--stress", action="store_true", help="run stress_test.py instead of tests.py")
    a, extra = ap.parse_known_args(argv)
    try:
        if a.cmd == "ids":
            if extra:
                ap.error(f"unrecognized arguments: {' '.join(extra)}")
            if a.against and a.base:
                ap.error("--against and --base are exclusive")
            if a.allow_removed and not (a.against or a.base):
                ap.error("--allow-removed needs --against or --base")
            return run_ids(a, collect, root)
        return run_time(a, extra, runner, clock)
    except PerfError as e:
        print(f"perfcheck: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
