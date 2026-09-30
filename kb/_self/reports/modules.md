# Co-change of the large modules

How often each section of `_tools/kbgit.py`, `_tools/benchmarks.py`, `_tools/kbfacts.py`, `_tools/factdiff.py` and `_tools/backlog.py` changed alone and together with the others across the repository's git history, and one Verdict line per module: which sections are independent and can move to their own module, and which change together and should stay together. **Setup:** the repository's whole history (its first commit is 2026-09-25) up to the commit of `main` the tables were run at, `612711c9` (2026-09-30); stdlib Python only, no model, no change to the files measured. The method below is complete: the script re-runs every table with the command it names, and the tables are replaced, not appended, when a run supersedes them.

## Method

- **Sections.** A section is the run of top-level statements (functions, classes, assignments, any other statement) under one banner comment of the file (`# ---- name` or `# -- name`), as the file reads at the revision the run starts from. The module docstring and the imports are the file's frame, not a section: a usage line for a new command, or a new import, would tie every section to every other. Where one banner holds more than one boundary the script's `MOVES` table draws it (`kbgit.py`'s sync banner holds four sections, its history banner two, and its `main` is apart; `benchmarks.py`'s registry and `main`), and `FAMILIES` groups `benchmarks.py`'s scenarios by what they measure, each helper joining the one family whose scenarios reach it through the names they use, or the shared helpers when several do.
- **Commits.** Every non-merge commit that changed the file, oldest first, after the one that added it (`git log --follow`; none of the five files was renamed). The file is parsed at the commit and at its parent; a top-level statement changed when it was added, removed, or its source with blank lines left out differs. A changed statement counts in the section it has at the run's revision; one that is gone there counts in its banner's section when the revision has a section of that name, and not at all otherwise. A commit that changed more than half of a file's sections is a sweep: listed, and left out of every count.
- **Counts.** Per section: the commits that changed it, how many of them changed nothing else, how many changed only sections of its own module, how many also changed another module's. Per module: the commits that changed it, the ones that changed only it, and per pair of modules the commits that changed both over the commits that changed either. Names used: for each top-level statement, the top-level names of the file it reads (names it binds itself left out); a module uses a name of another when one of its statements reads it. Attribute access and strings are not followed.
- **Marks.** The first module of a file's group is the one that stays (its entry point), so its pairs are listed but never mark anything: a new command or scenario is expected to touch its registry. Another module is **coupled** when it changed together with a candidate in at least 2 commits and in more than a quarter of the commits that changed either (`COUPLED`), or when it and a candidate use each other's names (a cycle: moving both needs a third module). Otherwise it is **independent** when at least 3 commits changed it (`PROVEN`), else **unproven**: too few commits to say anything, not evidence either way. The cuts are judgment, not derived; the two marginal cases are named where they occur.
- **Verdict.** A module whose mark is independent is split off, the coupled modules stay together with the staying file, an unproven one is named and counted neither way.
- **Limits.** The history is days long, so every count is small and a single commit moves a share by ten points or more. The names used are approximate: a name read in a statement counts even when a string or a dynamic lookup does the real work. The script was also run on a planted history of four sections, two of them always changed together: it marked those two coupled and the others independent. Sections and modules are fixed in the script for the revision in the heading; after a file is split, its sections are files and the script is run on those.

Re-run (from the repository root, at the commit the tables were made at; a later revision needs `MOVES` and `MODULES` brought up to its banners):

```
python3 cochange.py --at 612711c9 _tools/kbgit.py _tools/benchmarks.py _tools/kbfacts.py _tools/factdiff.py _tools/backlog.py
```

with `cochange.py` the script below, saved anywhere (it reads git only).

```python
#!/usr/bin/env python3
"""Co-change of the top-level sections of a Python module across git history (stdlib only).

  python3 cochange.py [--at REV] FILE [FILE ...]     run from the repository root, e.g. python3 cochange.py --at 612711c9 _tools/kbgit.py
"""
import ast, collections, itertools, re, subprocess, sys

BANNER = re.compile(r"^# ?-{10,} ?(.*?)$|^# -- (.*)$")
TOP = "header before the first banner"
REV = "HEAD"  # the revision whose sections are read; --at sets it
COUPLED = 0.25  # two modules are coupled when they changed together in at least 2 commits and in more than this share
PROVEN = 3  # a module changed by fewer commits than this is unproven, not independent
SWEEP = 0.5  # a commit touching more than this share of a file's sections is a sweep and is left out of the counts
MOVES = {  # banner sections that hold more than one boundary: {file: {section: names of the top-level statements}}
    "_tools/kbgit.py": {
        "sync: rebase and fix": "mechanical gitx tool in_progress rebasing dirty_paths names short fix_args renumbered "
            "conflict_help do_rebase commit_fix refresh_trailers MECHANICAL IN_PROGRESS NO_EDITOR MERGE_CFG REBASE "
            "REBASE_HINT FIX_COMMIT REJECTED",
        "sync: gate": "gate_paths artifact_paths gate_needs gate",
        "sync: push and lanes": "CODE_BRANCH_PREFIX LANE_BRANCH NO_PUSH_OPTIONS push_options lane_plan push_branch "
            "sync_once new_report cmd_sync",
        "sync: bridge": "bridge_dry_run cmd_bridge BRIDGE_PREFIX",
        "main": "main If",
        "trailers: check-trailers and lanes": "log_records default_range cmd_lane cmd_check_lanes commit_changes "
            "BlobReader trailer_audit work_ok work_state at_or_parent on_origin_main cmd_check_trailers _WANT WORKED "
            "BACKLOG_FILE",
        "history: log, blame, asof, census": "id_regex split_arg classify cmd_log blame_line cmd_blame cmd_asof "
            "census_message cmd_tag_census"},
    "_tools/benchmarks.py": {"registry and cli": "SCENARIOS main If"},
}
FAMILIES = {  # the scenario functions of each family; a helper joins the one family whose functions reach it
    "scenarios: lookup": "s_headless s_subagents s_models s_router s_route_by_verdict s_howto s_partial "
        "s_files_subagents s_files_headless s_new_model s_kb_lookup_agent",
    "scenarios: retrieval": "s_retrieval s_verdict s_doc2query s_tool_speed",
    "scenarios: querylog": "s_querylog_hooks s_querylog_pipeline s_redaction s_research",
    "scenarios: install": "s_host_lookups s_always_on s_ingest s_host_roots s_kbpy"}
SHARED = "scenarios: helpers used by several families"
MODULES = {  # the candidate modules: {file: {module: [sections]}}; the first is the one that stays
    "_tools/kbgit.py": {
        "kbgit.py": [TOP, "main"],
        "merge": ["io and git", "text helpers", "_sources.csv", "citations of renumbered ids", "answer ids",
                  "_fetch_state.csv", "Markdown ledgers", "lint baseline, .gitattributes", "commands"],
        "trailers": ["history: trailers", "history: hooks", "trailers: check-trailers and lanes"],
        "history": ["history: log, blame, asof, census"],
        "sync": ["sync: rebase and fix", "sync: gate", "sync: push and lanes", "sync: bridge"]},
    "_tools/benchmarks.py": {
        "benchmarks.py": ["registry and cli"],
        "core (harness)": [TOP, "results file", "isolation", "a run", SHARED],
        "report": ["report tables"],
        "lookup": ["scenarios: lookup"], "retrieval": ["scenarios: retrieval"], "querylog": ["scenarios: querylog"],
        "install": ["scenarios: install"]},
    "_tools/kbfacts.py": {
        "kbfacts.py": [TOP],
        "parse": ["tags", "files", "fact units", "ledgers", "audit"],
        "pack": ["pack (fact-level retrieval)", "the pack index (postings; persisted with sqlite3)"],
        "host": ["topics for code (host workspace signals)"]},
    "_tools/factdiff.py": {
        "factdiff.py": [TOP],
        "text": ["text units", "similarity"],
        "data": ["sources, facts and the cache", "anchors file", "snapshots of copy sources"],
        "calibration": ["calibration"],
        "detection": ["detection", "review and apply"]},
    "_tools/backlog.py": {
        "backlog.py": [TOP, "commands"],
        "store": ["storage", "validation", "host and user names"],
        "knowledge": ["knowledge", "code and its docs", "knowledge state"],
        "git": ["readiness", "git and checks"]},
}


def git(*a):
    r = subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def units(text):
    """{key: (banner, source, names)} per top-level statement: a def, class or assignment is keyed by its name, any
    other by its kind. The docstring and the imports are the file's frame, not a section."""
    lines, out, seen = text.splitlines(), {}, collections.Counter()
    banners = [(i, (m.group(1) or m.group(2)).strip()) for i, l in enumerate(lines) if (m := BANNER.match(l))]
    for n in ast.parse(text).body:
        if isinstance(n, (ast.Import, ast.ImportFrom)) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)):
            continue
        start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])]) - 1
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            key = n.name
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            ts = n.targets if isinstance(n, ast.Assign) else [n.target]
            key = ",".join(sorted(x.id for t in ts for x in ast.walk(t) if isinstance(x, ast.Name))) or "assign"
        else:
            key = type(n).__name__
        seen[key] += 1
        key += f"#{seen[key]}" if seen[key] > 1 else ""
        src = "\n".join(l for l in lines[start:n.end_lineno] if l.strip())
        out[key] = (next((b for i, b in reversed(banners) if i < start), TOP), src,
                    {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
                    - {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and not isinstance(x.ctx, ast.Load)}
                    - {a.arg for a in ast.walk(n) if isinstance(a, ast.arg)})
    return out


def sections_at_head(path):
    """(units at REV, {key: section}): a statement's section is its banner, or the MOVES section or scenario family."""
    head = units(git("show", f"{REV}:{path}"))
    smap = {k: b for k, (b, _, _) in head.items()}
    for sec, names in MOVES.get(path, {}).items():
        for k in head:
            if k.split("#")[0] in names.split() or k.split(",")[0] in names.split():
                smap[k] = sec
    if path.endswith("benchmarks.py"):
        of, reach = {n: k for k in head for n in k.split(",")}, collections.defaultdict(set)
        for fam, fns in FAMILIES.items():
            for fn in fns.split():
                todo, seen = [fn], {fn}
                while todo:
                    for n in head[todo.pop()][2]:
                        k = of.get(n)
                        if k and k not in seen and smap[k] in ("scenarios", "query log"):
                            seen.add(k)
                            todo.append(k)
                for k in seen:
                    reach[k].add(fam)
        for k, fams in reach.items():
            smap[k] = next(iter(fams)) if len(fams) == 1 else SHARED
    return head, smap


def history(path, smap):
    """One {sections, rev, subject} per commit after the one that added the file. A statement that is no longer at REV
    counts in its banner's section when REV has a section of that name, else it is not counted."""
    out = []
    for line in git("log", "--no-merges", "--follow", "--reverse", "--format=%H %s", REV, "--", path).splitlines():
        rev, subject = line.split(" ", 1)
        old, new = git("show", f"{rev}^:{path}"), git("show", f"{rev}:{path}")
        if old is None:
            continue
        a, b = units(old), units(new)
        hit = {smap.get(k) or (x[0] if x[0] in smap.values() else None)
               for k in set(a) | set(b) if k not in a or k not in b or a[k][1] != b[k][1] for x in [(b.get(k) or a[k])]}
        out.append({"rev": rev[:8], "subject": subject, "sections": hit - {None}})
    return out


def report(path):
    head, smap = sections_at_head(path)
    secs = list(dict.fromkeys(smap.values()))
    mod = {s: m for m, ss in MODULES[path].items() for s in ss}
    stays, cand = next(iter(MODULES[path])), list(MODULES[path])[1:]
    commits = history(path, smap)
    live = [c for c in commits if c["sections"]]
    sweeps = [c for c in live if len(c["sections"]) > SWEEP * len(secs)]
    plain = [c for c in live if c not in sweeps]
    print(f"\n## {path}: {len(commits)} commits after the first, {len(live)} change a section, sweeps left out: "
          f"{len(sweeps)} ({', '.join(c['rev'] for c in sweeps) or 'none'}), {len(plain)} counted\n")
    print("| section | module | commits | alone | with its module only | with another module |\n|---|---|---|---|---|---|")
    for s in secs:
        t = [c for c in plain if s in c["sections"]]
        al = sum(len(c["sections"]) == 1 for c in t)
        own = sum(len(c["sections"]) > 1 and {mod[x] for x in c["sections"]} == {mod[s]} for c in t)
        print(f"| {s} | {mod[s]} | {len(t)} | {al} | {own} | {len(t) - al - own} |")
    touched = {m: [c for c in plain if any(mod[x] == m for x in c["sections"])] for m in MODULES[path]}
    refs = collections.defaultdict(set)
    of = {n: k for k in head for n in k.split(",")}
    for k, (_, _, names) in head.items():
        for n in names:
            if n in of and mod[smap[of[n]]] != mod[smap[k]]:
                refs[mod[smap[k]], mod[smap[of[n]]]].add(n)
    together = {(a, b): sum(any(mod[x] == b for x in c["sections"]) for c in touched[a])
                for a, b in itertools.permutations(MODULES[path], 2)}
    print("\n| module | commits | only it | coupled with | uses each other | mark |\n|---|---|---|---|---|---|")
    for m in cand:
        only = sum({mod[x] for x in c["sections"]} == {m} for c in touched[m])
        cp = [o for o in cand if o != m and together[m, o] >= 2
              and together[m, o] / (len(touched[m]) + len(touched[o]) - together[m, o]) > COUPLED]
        cy = [o for o in cand if o != m and refs[m, o] and refs[o, m]]
        mark = "coupled" if cp or cy else "independent" if len(touched[m]) >= PROVEN else "unproven"
        print(f"| {m} | {len(touched[m])} | {only} | {', '.join(cp) or '-'} | {', '.join(cy) or '-'} | {mark} |")
    print("\nmodule pairs, commits that changed both / either: " + ", ".join(
        f"{a} + {b} {together[a, b]}/{len(touched[a]) + len(touched[b]) - together[a, b]}"
        for a, b in itertools.combinations(MODULES[path], 2)))
    print("\nnames a module uses from another: " + ", ".join(
        f"{a} -> {b} {len(v)}" for (a, b), v in sorted(refs.items()) if v and stays not in (a, b)))
    print("\nnames the staying file uses from a candidate: " + (", ".join(
        f"{b} {len(v)}" for (a, b), v in sorted(refs.items()) if v and a == stays) or "none"))
    print("\nnames a candidate uses from the staying file: " + (", ".join(
        f"{a} {len(v)}" for (a, b), v in sorted(refs.items()) if v and b == stays) or "none"))
    wp = collections.Counter()
    for c in plain:
        wp.update(q for q in itertools.combinations(sorted(c["sections"]), 2) if mod[q[0]] == mod[q[1]])
    print("\nsections of one module that changed together in 3 commits or more: " +
          ("; ".join(f"{a} + {b} {k}" for (a, b), k in wp.most_common() if k >= 3) or "none"))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--at"]:
        REV, args = args[1], args[2:]
    for f in args:
        report(f)
```

## `_tools/kbgit.py`

Commits that changed the file after the one that added it: 37 commits after the first, 35 change a section, sweeps left out: 1 (79495077), 34 counted.

| section | module | commits | alone | with its module only | with another module |
|---|---|---|---|---|---|
| header before the first banner | kbgit.py | 1 | 0 | 0 | 1 |
| io and git | merge | 3 | 0 | 1 | 2 |
| text helpers | merge | 4 | 0 | 2 | 2 |
| _sources.csv | merge | 5 | 1 | 1 | 3 |
| citations of renumbered ids | merge | 5 | 1 | 1 | 3 |
| answer ids | merge | 3 | 0 | 1 | 2 |
| _fetch_state.csv | merge | 1 | 0 | 1 | 0 |
| Markdown ledgers | merge | 2 | 0 | 1 | 1 |
| lint baseline, .gitattributes | merge | 1 | 0 | 0 | 1 |
| commands | merge | 9 | 2 | 2 | 5 |
| history: trailers | trailers | 8 | 0 | 2 | 6 |
| history: hooks | trailers | 8 | 0 | 0 | 8 |
| trailers: check-trailers and lanes | trailers | 9 | 0 | 2 | 7 |
| history: log, blame, asof, census | history | 4 | 0 | 0 | 4 |
| sync: rebase and fix | sync | 10 | 0 | 1 | 9 |
| sync: gate | sync | 4 | 2 | 0 | 2 |
| sync: push and lanes | sync | 10 | 2 | 1 | 7 |
| sync: bridge | sync | 1 | 0 | 0 | 1 |
| main | kbgit.py | 9 | 1 | 0 | 8 |

| module | commits | only it | coupled with | uses each other | mark |
|---|---|---|---|---|---|
| merge | 18 | 8 | - | - | independent |
| trailers | 15 | 2 | history, sync | sync | coupled |
| history | 4 | 0 | trailers | - | coupled |
| sync | 18 | 5 | trailers | trailers | coupled |

module pairs, commits that changed both / either: kbgit.py + merge 4/24, kbgit.py + trailers 7/18, kbgit.py + history 3/11, kbgit.py + sync 6/22, merge + trailers 6/27, merge + history 3/19, merge + sync 7/29, trailers + history 4/15, trailers + sync 8/25, history + sync 2/20

names a module uses from another: history -> merge 5, history -> trailers 7, sync -> merge 4, sync -> trailers 7, trailers -> merge 5, trailers -> sync 4

names the staying file uses from a candidate: history 4, merge 1, sync 2, trailers 7

names a candidate uses from the staying file: history 6, merge 22, sync 3, trailers 6

sections of one module that changed together in 3 commits or more: history: hooks + history: trailers 4; history: hooks + trailers: check-trailers and lanes 4; history: trailers + trailers: check-trailers and lanes 4; sync: push and lanes + sync: rebase and fix 4; _sources.csv + text helpers 3

Reading. Nine of the 34 counted commits changed `commands` (the `fix` and `fmt` bodies) and 9 changed `main`; the candidate modules changed in 4 to 18 commits each: `merge` 18 (8 of them nothing outside it), `trailers` 15, `sync` 18, `history` 4. The three trailer sections changed together in 4 commits for each pair, and `sync: rebase and fix` with `sync: push and lanes` in 4: those stay as units. `merge` is the file's leaf: `trailers`, `history` and `sync` use 5, 5 and 4 of its names, and it uses none of theirs; its pairs with them are 22%, 16% and 24%, the last just under the cut. `trailers` and `sync` use each other's names (`hook_pre_push` reads the gate, `dirty_paths` and the lane names of `sync`; `sync` reads the trailer computation, `trailer_audit` and `rev_parse` of `trailers`) and changed together in 8 of 25 commits. `history` changed in only 4 commits, each of them with `trailers` (27%, the other marginal case: a cut of a third would call it independent), and uses 7 of its names. The other candidates read 22 (`merge`), 6 (`trailers`), 6 (`history`) and 3 (`sync`) names of the header (roots, paths, constants, `Problem`): if no split-off module may import `kbgit.py`, those names need a home of their own.

Verdict: split along one boundary, `merge` (io and git, text helpers, `_sources.csv`, citations of renumbered ids, answer ids, `_fetch_state.csv`, Markdown ledgers, lint baseline and `.gitattributes`, and `commands`): independent, changed in 18 of 34 counted commits and together with each other module in at most 7 of 29 (24%), using none of their names; `trailers` (history: trailers, history: hooks, check-trailers and lanes), `history` (log, blame, asof, census) and `sync` (rebase and fix, gate, push and lanes, bridge) co-change and stay together in `kbgit.py` with the header and `main`: `trailers` with `sync` in 8 of 25 commits and through names used both ways, `trailers` with `history` in 4 of 15, every `history` commit also a `trailers` commit.

## `_tools/benchmarks.py`

Commits that changed the file after the one that added it: 15 commits after the first, 15 change a section, sweeps left out: 1 (3e837546), 14 counted.

| section | module | commits | alone | with its module only | with another module |
|---|---|---|---|---|---|
| header before the first banner | core (harness) | 0 | 0 | 0 | 0 |
| results file | core (harness) | 0 | 0 | 0 | 0 |
| report tables | report | 5 | 3 | 0 | 2 |
| isolation | core (harness) | 1 | 0 | 0 | 1 |
| a run | core (harness) | 1 | 0 | 0 | 1 |
| scenarios: lookup | lookup | 4 | 1 | 0 | 3 |
| scenarios: helpers used by several families | core (harness) | 0 | 0 | 0 | 0 |
| scenarios: install | install | 3 | 1 | 0 | 2 |
| scenarios: retrieval | retrieval | 2 | 0 | 0 | 2 |
| scenarios: querylog | querylog | 5 | 3 | 0 | 2 |
| registry and cli | benchmarks.py | 4 | 0 | 0 | 4 |

| module | commits | only it | coupled with | uses each other | mark |
|---|---|---|---|---|---|
| core (harness) | 2 | 0 | - | - | unproven |
| report | 5 | 3 | - | - | independent |
| lookup | 4 | 1 | - | - | independent |
| retrieval | 2 | 0 | - | - | unproven |
| querylog | 5 | 3 | - | - | independent |
| install | 3 | 1 | - | - | independent |

module pairs, commits that changed both / either: benchmarks.py + core (harness) 2/4, benchmarks.py + report 2/7, benchmarks.py + lookup 2/6, benchmarks.py + retrieval 1/5, benchmarks.py + querylog 1/8, benchmarks.py + install 1/6, core (harness) + report 1/6, core (harness) + lookup 0/6, core (harness) + retrieval 1/3, core (harness) + querylog 1/6, core (harness) + install 1/4, report + lookup 1/8, report + retrieval 1/6, report + querylog 0/10, report + install 0/8, lookup + retrieval 0/6, lookup + querylog 0/9, lookup + install 1/6, retrieval + querylog 1/6, retrieval + install 0/5, querylog + install 1/7

names a module uses from another: install -> core (harness) 17, lookup -> core (harness) 16, querylog -> core (harness) 7, report -> core (harness) 1, retrieval -> core (harness) 7

names the staying file uses from a candidate: core (harness) 11, install 5, lookup 11, querylog 4, report 2, retrieval 4

names a candidate uses from the staying file: none

sections of one module that changed together in 3 commits or more: none

Reading. The four scenario families changed in 2 to 5 commits each (`retrieval` 2, `install` 3, `lookup` 4, `querylog` 5), `report tables` in 5, the harness in 2 (`isolation` once, `a run` once) and the shared scenario helpers and results file in none. The six candidates never changed together in more than one commit for any pair (at most 1 of 3 to 10 commits that changed either), the four families use no name of each other or of the report, and every one of them uses only the harness (17, 16, 7 and 7 names; the report 1). The registry (`SCENARIOS`) and `main` changed in 4 commits, each time with a scenario, the report or the harness: adding a scenario adds a registry entry, and that stays in `benchmarks.py`. The family grouping is this report's (lookup answers, retrieval quality and speed, the query log, installs and host projects); a scenario moved between families changes that family's counts and nothing else in the table.

Verdict: split along the harness (`core`), the report and the four scenario families: `report`, `lookup`, `querylog` and `install` are independent (5, 4, 5 and 3 commits; no pair of the six changed together in more than 1 commit, and no family uses any name of another or of the report), `core` and `retrieval` changed in 2 commits each and are unproven, not contradicted (both harness commits, a per-run stream and a shim fix, also changed scenarios, as an interface change does; `retrieval` changed once with the harness and the report and once with `querylog`); `SCENARIOS` and `main` stay in `benchmarks.py`.

## `_tools/kbfacts.py`

Commits that changed the file after the one that added it: 33 commits after the first, 33 change a section, sweeps left out: 2 (06058059, 3c8f9128), 31 counted.

| section | module | commits | alone | with its module only | with another module |
|---|---|---|---|---|---|
| header before the first banner | kbfacts.py | 5 | 1 | 0 | 4 |
| tags | parse | 3 | 2 | 0 | 1 |
| files | parse | 7 | 2 | 0 | 5 |
| fact units | parse | 3 | 0 | 0 | 3 |
| ledgers | parse | 2 | 0 | 0 | 2 |
| audit | parse | 0 | 0 | 0 | 0 |
| pack (fact-level retrieval) | pack | 13 | 1 | 3 | 9 |
| the pack index (postings; persisted with sqlite3) | pack | 20 | 10 | 3 | 7 |
| topics for code (host workspace signals) | host | 3 | 1 | 0 | 2 |

| module | commits | only it | coupled with | uses each other | mark |
|---|---|---|---|---|---|
| parse | 13 | 4 | - | pack | coupled |
| pack | 23 | 14 | - | parse | coupled |
| host | 3 | 1 | - | - | independent |

module pairs, commits that changed both / either: kbfacts.py + parse 4/14, kbfacts.py + pack 2/26, kbfacts.py + host 0/8, parse + pack 7/29, parse + host 0/16, pack + host 2/24

names a module uses from another: host -> pack 1, host -> parse 1, pack -> parse 14, parse -> pack 4

names the staying file uses from a candidate: none

names a candidate uses from the staying file: pack 4, parse 8

sections of one module that changed together in 3 commits or more: pack (fact-level retrieval) + the pack index (postings; persisted with sqlite3) 10

Reading. `the pack index` is the most changed section (20 commits, 10 of them alone) and changed together with `pack` in 10 of the 23 commits that changed either section, so they are one unit. `parse` and `pack` changed together in 7 of 29 commits (24%, just under the cut) but use each other's names (`pack` 14 of `parse`'s, `parse` 4 of `pack`'s), a cycle. `host` (topics for code) changed in 3 commits, 2 with `pack` and none with `parse`, reads one name of each, and nothing reads its names.

Verdict: split along one boundary, `host` (topics for code, host workspace signals): independent (3 commits, none with `parse`, 2 of 24 with `pack`, using 1 name of each and used by neither); `parse` (tags, files, fact units, ledgers, audit) and `pack` (pack, the pack index) stay together: they changed together in 7 of 29 commits and use each other's names.

## `_tools/factdiff.py`

Commits that changed the file after the one that added it: 8 commits after the first, 8 change a section, sweeps left out: 0 (none), 8 counted.

| section | module | commits | alone | with its module only | with another module |
|---|---|---|---|---|---|
| header before the first banner | factdiff.py | 0 | 0 | 0 | 0 |
| text units | text | 1 | 0 | 0 | 1 |
| similarity | text | 0 | 0 | 0 | 0 |
| sources, facts and the cache | data | 1 | 0 | 0 | 1 |
| anchors file | data | 1 | 0 | 0 | 1 |
| snapshots of copy sources | data | 2 | 1 | 0 | 1 |
| calibration | calibration | 2 | 0 | 0 | 2 |
| detection | detection | 4 | 0 | 1 | 3 |
| review and apply | detection | 4 | 2 | 1 | 1 |

| module | commits | only it | coupled with | uses each other | mark |
|---|---|---|---|---|---|
| text | 1 | 0 | - | - | unproven |
| data | 4 | 1 | detection | detection | coupled |
| calibration | 2 | 0 | detection | - | coupled |
| detection | 7 | 3 | data, calibration | data | coupled |

module pairs, commits that changed both / either: factdiff.py + text 0/1, factdiff.py + data 0/4, factdiff.py + calibration 0/2, factdiff.py + detection 0/7, text + data 1/4, text + calibration 0/3, text + detection 1/7, data + calibration 1/5, data + detection 3/8, calibration + detection 2/7

names a module uses from another: calibration -> data 1, calibration -> text 9, data -> detection 3, data -> text 5, detection -> calibration 2, detection -> data 11, detection -> text 7

names the staying file uses from a candidate: none

names a candidate uses from the staying file: data 7, detection 7, text 5

sections of one module that changed together in 3 commits or more: none

Reading. Eight commits in all; `detection` (two sections) changed in 7 of them. `detection` changed together with `data` in 3 of 8 commits and with `calibration` in 2 of 7, and uses 11 of `data`'s names while `data` (the `anchor` and `snapshot` commands) uses 3 of its. `text` (text units, similarity) changed in one commit, which also changed `data` and `detection`; `data`, `detection` and `calibration` use 5, 7 and 9 of its names and it uses none of theirs: a leaf, but with too little history to mark.

Verdict: keep whole: eight commits are too few to prove a boundary, and of the four candidates `data` (sources, facts and the cache, anchors file, snapshots of copy sources), `calibration` and `detection` (detection, review and apply) co-change (detection with data in 3 of 8 commits, with calibration in 2 of 7) and `data` and `detection` use each other's names (11 and 3), while `text` (text units, similarity) changed in 1 commit and is unproven.

## `_tools/backlog.py`

Commits that changed the file after the one that added it: 32 commits after the first, 31 change a section, sweeps left out: 0 (none), 31 counted.

| section | module | commits | alone | with its module only | with another module |
|---|---|---|---|---|---|
| header before the first banner | backlog.py | 3 | 0 | 1 | 2 |
| storage | store | 2 | 0 | 0 | 2 |
| validation | store | 0 | 0 | 0 | 0 |
| host and user names | store | 3 | 1 | 0 | 2 |
| knowledge | knowledge | 2 | 0 | 0 | 2 |
| code and its docs | knowledge | 1 | 0 | 0 | 1 |
| knowledge state | knowledge | 5 | 1 | 0 | 4 |
| readiness | git | 0 | 0 | 0 | 0 |
| git and checks | git | 6 | 2 | 0 | 4 |
| commands | backlog.py | 27 | 15 | 1 | 11 |

| module | commits | only it | coupled with | uses each other | mark |
|---|---|---|---|---|---|
| store | 4 | 1 | - | - | independent |
| knowledge | 6 | 1 | - | - | independent |
| git | 6 | 2 | - | - | independent |

module pairs, commits that changed both / either: backlog.py + store 3/28, backlog.py + knowledge 5/28, backlog.py + git 4/29, store + knowledge 1/9, store + git 0/10, knowledge + git 0/12

names a module uses from another: knowledge -> git 3, knowledge -> store 4

names the staying file uses from a candidate: git 14, knowledge 4, store 6

names a candidate uses from the staying file: git 5, knowledge 15, store 6

sections of one module that changed together in 3 commits or more: commands + header before the first banner 3

Reading. `commands` is the file's centre: 27 of the 31 counted commits changed it, 15 of them nothing else. The three other candidates changed in 4 to 6 commits each and never together in more than 1 (`store` with `knowledge` once, `git` with neither), and each with `commands` in 3 to 5 of 28 or 29 commits (11% to 18%). `knowledge` uses 4 of `store`'s and 3 of `git`'s names and neither uses it; `commands` uses 14 of `git`'s, 6 of `store`'s and 4 of `knowledge`'s. The three read 6, 15 and 5 names of the header (`FIELDS`, `KINDS`, `IN_SPRINT`, `ID_RE` and the like), which a split has to place.

Verdict: split along three boundaries, `store` (storage, validation, host and user names), `knowledge` (knowledge, code and its docs, knowledge state) and `git` (readiness, git and checks): independent (4, 6 and 6 commits; no two changed together in more than 1, none coupled with `commands` above 18%, no cycle among them); `commands` (27 of 31 counted commits, 15 of them alone) and the header stay in `backlog.py`.
