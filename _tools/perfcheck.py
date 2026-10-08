#!/usr/bin/env python3
"""Prove a test-suite speed-up lost no test, and time a suite run against a bound. Standard library only; described in kb/_self/tools.md.

  perfcheck.py ids                              print the test ids tests.py collects at HEAD (the working tree), one per
                                                line, sorted
  perfcheck.py ids --write FILE                 write them to FILE (the baseline); a second run changes nothing
  perfcheck.py ids --against FILE               compare them with the ids in FILE; a baseline id not collected now fails
                                                unless its test now lives in another file (reported as `moved:`)
  perfcheck.py ids --base REV                   compare them with the ids collected at git revision REV, in a temporary
                                                worktree that is removed afterwards (the working tree is never touched)
  --allow-removed FILE                          ids in FILE (one per line, `#` comments) may be missing
  perfcheck.py dropped [--file FILE] [--since REV]  warn of a dropped test id (FILE, default _tools/test_ids_dropped.txt) of a
                                                test file that still exists whose reason names no removed file or symbol
                                                and no successor test, and of a dropped test file whose local imports are
                                                all still present (tests of live code); exit 0 with or without warnings
  perfcheck.py time [--max-seconds N] [ARGS...]
                                                run tests.py with ARGS and fail when it takes longer than N seconds, or
                                                fails itself; without N, the bound is the running platform's max_seconds
                                                in _tools/tests_ceiling.json, times KB_TEST_TIMEOUT_FACTOR on a CI runner
                                                (as tests.py reads them)

The ids are what `pytest --collect-only -q` prints for the selection tests.py runs: `_tools`. Nothing runs and nothing
touches the network.
Ids added since the baseline are listed and do not fail; the baseline file is appended to by whoever adds tests.
A test that moved to another file keeps its class and name: a baseline id missing at head whose part after the file path
(`Class::test_name[param]`, or `test_name[param]`) is the same as that of an id added in another file is reported as
`moved:` and does not fail, so a split of a test module needs no baseline edit. Each added id answers one missing id (two
files that each gained `Class::test_name` cover two missing ids, not three), and a test that only lost its file's copy while
the same class and name still exists in a file the baseline already held stays MISSING.

Exit codes: 0 no id lost (or the run was within its bound); 1 an id is missing and not allowed, or a run was over its
bound or failed; 2 it could not do what was asked (bad arguments, an unreadable file, a failed collection, not a clone).
"""
import argparse, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SELECTIONS = (  # (pytest arguments after the collect options, a path that must exist for the selection to apply)
    (["_tools"], "_tools"),  # the one selection tests.py runs
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


def tests_module():
    sys.path.insert(0, str(TOOLS))
    import tests
    return tests


def pytest_command():
    tests = tests_module()
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
    """The sorted ids the selection collects under `root`; PerfError when pytest fails to collect."""
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


def test_key(test_id):
    """The part of an id after the file path: `Class::test_name[param]`, or `test_name[param]`."""
    return test_id.split("::", 1)[-1]


def match_moved(missing, added):
    """(moved, still_missing, new): split the baseline ids `missing` at head by whether an id in `added` (new at head) has the
    same class and test name in another file. Each added id answers one missing id, in sorted order, so the same input gives
    the same split. `moved` holds (old id, new id) pairs; `new` the added ids no missing id claimed."""
    free = {}
    for a in sorted(added):
        free.setdefault(test_key(a), []).append(a)
    moved, left = [], []
    for m in sorted(missing):
        found = free.get(test_key(m))
        if found:
            moved.append((m, found.pop(0)))
        else:
            left.append(m)
    return moved, left, sorted(i for ids in free.values() for i in ids)


def compare(baseline, head, allowed=()):
    """(removed, added, allowed_removed, moved): baseline ids missing at head that are not allowed and did not move to another
    file, ids new at head (those a moved id came from included), baseline ids missing at head that the allow list names, and
    the (old id, new id) pairs of the ids that moved."""
    base, now, ok = set(baseline), set(head), set(allowed)
    missing = base - now
    added = now - base
    moved, removed, _ = match_moved(missing - ok, added)
    return removed, sorted(added), sorted(missing & ok), moved


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
    removed, added, allowed, moved = compare(baseline, head, read_ids(a.allow_removed) if a.allow_removed else ())
    came_from = {new for _, new in moved}
    for i in added:
        if i not in came_from:
            print(f"added: {i}")
    for old, new in moved:
        print(f"moved: {old} -> {new}")
    for i in allowed:
        print(f"removed (allowed): {i}")
    for i in removed:
        print(f"MISSING: {i}")
    where = a.against or f"revision {a.base}"
    print(f"perfcheck ids: {len(removed)} missing, {len(added) - len(moved)} added, {len(moved)} moved to another file, "
          f"{len(allowed)} removed on the allow list, against {where}")
    return 1 if removed else 0


def run_suite(args):
    return subprocess.run([sys.executable, str(TOOLS / "tests.py")] + args, cwd=str(ROOT), env=clean_env()).returncode


def ceiling_seconds(platform=None):
    """The running platform's max_seconds in the test ceiling, times the CI factor, read with tests.py's own functions;
    PerfError when the ceiling is refused or names no bound for the platform."""
    tests = tests_module()
    platform = platform or sys.platform
    try:
        c = tests.read_ceiling()
    except tests.CeilingError as e:
        raise PerfError(f"ceiling refused: {e}") from None
    limit = c["max_seconds"].get(platform)
    if limit is None:
        raise PerfError(f"{os.path.basename(tests.CEILING)} has no max_seconds for {platform}: pass --max-seconds")
    return limit * tests.seconds_factor()


def run_time(a, extra, runner=run_suite, clock=time.monotonic):
    if a.max_seconds is None:
        a.max_seconds = ceiling_seconds()
    start = clock()
    code = runner(extra)
    seconds = clock() - start
    if code != 0:
        print(f"perfcheck time: the suite run failed (exit {code}) after {seconds:.1f} s")
        return 1
    if seconds > a.max_seconds:
        print(f"perfcheck time: {seconds:.1f} s is over the bound of {a.max_seconds:g} s")
        return 1
    print(f"perfcheck time: {seconds:.1f} s within the bound of {a.max_seconds:g} s")
    return 0


DROPPED_FILE = "_tools/test_ids_dropped.txt"
REASON_TOKEN = re.compile(r"`([^`]+)`|([A-Za-z_][\w./-]*\.py)\b|(--[a-z][a-z-]+)|\b([A-Z][A-Z0-9_]{3,})\b|\b(test_\w+|Test[A-Z]\w*)")
HELPER_MODULES = ("conftest",)  # imports a test file makes that name no code under test


def dropped_groups(text):
    """[(reason or None, [ids])] of a dropped-ids file: the `#` lines before a run of ids are its reason."""
    out, reason, fresh = [], None, True
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("#"):
            reason = (reason + " " if reason and not fresh else "") + ln.lstrip("# ").strip()
            fresh = False
            continue
        if ln:
            if not out or not fresh or out[-1][0] != reason:
                out.append((reason, []))
            out[-1][1].append(ln)
            fresh = True
    return out


def code_text(root):
    """The text of the repository's tools and tests (_tools/*.py), where a named symbol or test is looked for."""
    return "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in sorted((Path(root) / "_tools").glob("*.py")))


def names_removed_or_successor(reason, root, code):
    """True when REASON names a file that no longer exists, a symbol, flag or test the code no longer holds, or a
    successor test (`test_*`, `Test*`) that it does hold."""
    for m in REASON_TOKEN.finditer(reason or ""):
        tok = next(g for g in m.groups() if g)
        if m.group(5):
            return True  # a test name: removed (gone) or its successor (present) either way names the change
        if tok.endswith(".py"):
            if not (Path(root) / tok).exists() and not (Path(root) / "_tools" / Path(tok).name).exists():
                return True
        elif tok.split()[0] not in code:
            return True
    return False


def last_text(root, path):
    """The text PATH had in the last commit before it was deleted, or None."""
    p = subprocess.run(["git", "log", "-1", "--format=%H", "--diff-filter=D", "--", path], cwd=root, capture_output=True,
                       text=True)
    sha = p.stdout.strip()
    if p.returncode or not sha:
        return None
    # cat-file, not show: `git show REV:PATH` checks its argument as a file name ("Filename too long" on Windows)
    q = subprocess.run(["git", "cat-file", "blob", f"{sha}^:{path}"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return q.stdout if q.returncode == 0 else None


def dropped_warnings(root, text, only=None):
    """The warnings of `dropped` for a dropped-ids file's TEXT in the clone ROOT; ONLY, a set of ids, keeps the groups
    holding one of them (the ids a range added)."""
    code = code_text(root)
    out, files_gone, reasons = [], {}, {}
    for reason, ids in dropped_groups(text):
        if only is not None and not set(ids) & only:
            continue
        files = sorted({i.split("::")[0] for i in ids})
        live = [f for f in files if (Path(root) / f).exists()]
        if live and not names_removed_or_successor(reason, root, code):
            out.append(f"dropped: {len(ids)} id(s) of {', '.join(live)}: the reason names no removed file or symbol "
                       f"and no successor test: {reason or '(no reason)'}")
        for f in files:
            if f not in live:
                files_gone.setdefault(f, 0)
                files_gone[f] += len([i for i in ids if i.startswith(f + "::")])
                reasons.setdefault(f, []).append((reason, ids))
    for f, n in sorted(files_gone.items()):
        old = last_text(root, f)
        if old is None:
            continue
        present = sorted(m for m in local_imports_at(old, root, f) if (Path(root) / "_tools" / f"{m}.py").exists())
        if present and not any(names_successor(r, ids, root, code) for r, ids in reasons[f]):
            out.append(f"dropped: {f} ({n} id(s)) is gone, but modules it tested are still present: "
                       f"{', '.join(present)}; the reason names no successor test or test file where their tests went")
    return out


RETIRED_PHRASE = "live-module calls went with"  # a retired feature's dropped tests: the live module's calls went too


def names_removed(reason, root, code, skip=()):
    """True when REASON names a file that no longer exists, or a symbol or flag the code no longer holds; a token whose
    last path part is in SKIP (the dropped ids' own files and tests) names nothing."""
    for m in REASON_TOKEN.finditer(reason or ""):
        tok = next(g for g in m.groups() if g)
        if m.group(5) or tok.rsplit("/", 1)[-1] in skip:
            continue
        if tok.endswith(".py"):
            if not (Path(root) / tok).exists() and not (Path(root) / "_tools" / Path(tok).name).exists():
                return True
        elif tok.split()[0] not in code:
            return True
    return False


def names_successor(reason, ids, root, code):
    """True when REASON names where the dropped tests went: a test (`test_*`, `Test*`) the code still holds that is
    not one of the dropped ids' own, or a test file (`test_*.py`) that exists and is not the dropped one; or it says the
    live module's calls went with a retired feature (RETIRED_PHRASE) and names a removed module, file or symbol that is
    not one of the dropped ids' own file or test. A reason that names only the dropped test or its file, with or without
    that phrase, or a removed module without that phrase, excuses nothing."""
    gone = {i.split("::")[-1] for i in ids} | {i.split("::")[0].rsplit("/", 1)[-1] for i in ids}
    if RETIRED_PHRASE in (reason or "") and names_removed(reason, root, code, gone):
        return True  # a retired feature: its live modules' calls went with the removed code the reason names
    for m in REASON_TOKEN.finditer(reason or ""):
        tok = next(g for g in m.groups() if g)
        name = tok.rsplit("/", 1)[-1]
        if name in gone:
            continue
        if m.group(5) and re.search(rf"\bdef {re.escape(tok)}|\bclass {re.escape(tok)}", code):
            return True
        if tok.endswith(".py") and name.startswith("test_") and (
                (Path(root) / tok).exists() or (Path(root) / "_tools" / name).exists()):
            return True
    return False


def local_imports_at(text, root, path):
    """The _tools/ modules TEXT (the last version of the deleted test file PATH) imports, helpers left out: a module is
    local when _tools/<name>.py exists now or existed in the commit before the file was deleted."""
    import ast
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    p = subprocess.run(["git", "log", "-1", "--format=%H", "--diff-filter=D", "--", path], cwd=root, capture_output=True,
                       text=True)
    sha = p.stdout.strip()
    q = subprocess.run(["git", "ls-tree", "--name-only", f"{sha}^", "_tools/"], cwd=root, capture_output=True, text=True)
    then = {Path(x).stem for x in q.stdout.split()} if sha and q.returncode == 0 else set()
    return {n for n in names if n not in HELPER_MODULES and not n.startswith("test_")
            and ((Path(root) / "_tools" / f"{n}.py").exists() or n in then)}


def run_dropped(a, root=ROOT):
    path = Path(a.file) if a.file else Path(root) / DROPPED_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise PerfError(f"cannot read {path}: {e}")
    only = None
    if getattr(a, "since", None):  # the ids the range since SINCE added to the file
        p = subprocess.run(["git", "diff", "--unified=0", a.since, "--", str(path)], cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if p.returncode:
            raise PerfError(f"git diff {a.since} failed: {p.stderr.strip()[:200]}")
        only = {ln[1:].strip() for ln in p.stdout.splitlines()
                if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip() and not ln[1:].lstrip().startswith("#")}
    warnings = dropped_warnings(root, text, only)
    for w in warnings:
        print(w)
    print(f"perfcheck dropped: {len(warnings)} warning(s)")
    return 0


def main(argv=None, collect=collect_ids, runner=run_suite, clock=time.monotonic, root=ROOT):
    ap = argparse.ArgumentParser(prog="perfcheck.py", description="Prove a test-suite speed-up lost no test.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ids = sub.add_parser("ids", help="collect the test ids and compare them with a baseline")
    ids.add_argument("--against", help="a text file of ids, one per line")
    ids.add_argument("--base", help="a git revision whose ids are collected in a temporary worktree")
    ids.add_argument("--allow-removed", help="a file of ids that may be missing")
    ids.add_argument("--write", help="write the ids at HEAD to this file")
    dr = sub.add_parser("dropped", help="warn of dropped test ids that name no removed code")
    dr.add_argument("--file", help=f"a dropped-ids file (default {DROPPED_FILE})")
    dr.add_argument("--since", metavar="REV", help="only the groups whose ids the range since REV added (sync's gate)")
    tm = sub.add_parser("time", help="time a suite run against a bound; other arguments go to tests.py")
    tm.add_argument("--max-seconds", type=float, help="the bound (default: this platform's max_seconds in the test ceiling)")
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
        if a.cmd == "dropped":
            if extra:
                ap.error(f"unrecognized arguments: {' '.join(extra)}")
            return run_dropped(a, root)
        return run_time(a, extra, runner, clock)
    except PerfError as e:
        print(f"perfcheck: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
