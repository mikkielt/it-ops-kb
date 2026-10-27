"""The planning checks of backlog.py (kb/_self/backlog.md, What done refuses; kb/_self/tools.md): `researched`, the goal
research story's check by done's rules (`research_rows`, `unanswered_questions`, `research_without_facts`), and
`precheck`, which runs a sprint's checks once before any work and warns of each that passes already, with the clause
mapping it prints (`clause_map`), and `item_commits`, the commits an item's trailers name, which both read.

Standard library only; imports `bl_base`, `bl_check`, `bl_cli`, `bl_intake`, `bl_peers` and `bl_plan` and never `bl_land` or
`backlog`: `bl_land` imports this module, so every name the other modules read as `bl_land.NAME` stays importable
from there. It registers `researched` and `precheck` with `bl_cli` itself when imported (`backlog.py`'s USAGE puts each in
its usage position)."""
import csv, datetime, importlib, io, json, re, shlex, sys

import bl_cli
import bl_intake
import bl_peers
import bl_plan
from bl_base import (
    CLAUSE_SPLIT, Refused, clause_commands, git, goal_clauses, id_re, item_file, need, research_story, run_check, say,
    setting,
)
from bl_check import other_clone
from bl_plan import shared_doc, touch_files, touch_paths


def item_commits(root, ids):
    """{commit: [paths]} of the commits on HEAD whose KB-Work trailer names any of the ids, oldest first. Only work
    counts: a commit that changes nothing but item files (a claim, a gate, a sprint's plan) is not the item's work."""
    log = git(root, "log", "HEAD", "--reverse", "--no-merges",
              "--format=%H%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)%x1e")
    out = {}
    for rec in log.split("\x1e"):
        sha, _, vals = rec.strip().partition("\x00")
        if sha and set(id_re().findall(vals)) & set(ids):
            paths = [p for p in git(root, "show", "--no-renames", "--name-only", "--format=", sha).splitlines() if p]
            if any(not item_file(p) for p in paths):
                out[sha] = paths
    return out


# a goal research story that needs no outside facts is done with no work commit when its notes say why: the notes hold
# `No outside facts: <reason>` at their start, on a line of its own or after a sentence's end (`set --add-notes` joins
# notes with a space)
NO_OUTSIDE_FACTS = re.compile(r"(?:^|(?<=[.;!?]) |\n)No outside facts:[ \t]*\S")


def research_without_facts(it):
    """True for a story that is the sprint's goal research and whose notes say `No outside facts: <reason>`."""
    return bool(it.get("kind") == "story" and it.get("goal_research") and NO_OUTSIDE_FACTS.search(it.get("notes") or ""))


QUESTION_LEAD_WORDS = 8  # a lead-in of at most this many words before `: ` is no part of a narrowed goal's question


# a numbered piece whose text before `: ` starts with one of these is itself the question, not a lead-in
QUESTION_WORDS = frozenset("what which who whom whose when where why how does do did is are was were can could should would will may must has have".split())


TOUCH_ROOT = re.compile(r"kb/([^/*?\[\]]+)/")  # a touch inside a named kb root (`kb/public/**`: root `public`)


SELF_ROOT = "_self"  # the root of the project's own rules, read beside the roots the touches name


COVERAGE_ORDER = ("none", "weak", "good")


NUMBERED_PIECE = re.compile(r"(?:\(\d+\)|\d+[.)])\s+")  # `(1) `, `1) `, `1. `: a piece of a goal written as a numbered list


def goal_questions(goal, skipped=None):
    """The questions a narrowed goal names: each sentence of the goal that ends in `?`, and each numbered piece
    (`(1) does git record a change`) that has no `?`, the number and a lead-in of up to QUESTION_LEAD_WORDS words
    ending in `: ` left off (not when the number leads the piece and its words before the `: ` start with a question
    word, QUESTION_WORDS: `(4) What token cost does coordination add: agent teams ...?` is one question), in order,
    each once. The goal is cut where `goal_clauses` cuts it, but a question is read
    whole: a piece that names no question is joined to the next across a `, and ` (a question's own comma-and, `which
    item ..., and what does it print?`) and left unread at a `; `, which ends a clause, or at the goal's end: SKIPPED,
    when a list, takes each such piece, so a caller says what it did not read. A goal with no such sentence (the
    default goal of a research story, which `new sprint` files) names none."""
    parts = re.split(f"({CLAUSE_SPLIT.pattern})", str(goal or ""))
    out, cur = [], ""

    def question(piece):
        piece = piece.strip()
        numbered_first = bool(NUMBERED_PIECE.match(piece))  # the number leads the text: the words before `: ` are the question's own
        piece = NUMBERED_PIECE.sub("", piece, count=1)
        lead, sep, rest = piece.partition(": ")
        own = numbered_first and lead.split()[:1] and lead.split()[0].lower() in QUESTION_WORDS
        if sep and rest.strip() and len(lead.split()) <= QUESTION_LEAD_WORDS and not own:
            piece = rest.strip()
        return piece

    for n in range(0, len(parts), 2):
        cur = parts[n] if not cur else cur + parts[n - 1] + parts[n]
        sentences = [x.strip() for x in re.split(r"(?<=\?)\s+", cur.strip()) if x.strip()]
        tail = sentences.pop() if sentences and not sentences[-1].endswith("?") else ""  # the text a `?` has not ended
        out.extend(question(piece) for piece in sentences)
        if n + 2 < len(parts) and not parts[n + 1].startswith(";"):
            cur = tail
            continue
        cur = ""
        if NUMBERED_PIECE.match(tail) and question(tail):
            out.append(question(tail))
        elif tail and skipped is not None:
            skipped.append(tail)
    return list(dict.fromkeys(out))


def joined_lead_in(goal):
    """The lead-in (text before `: `) that `goal_questions` joins to a numbered piece's question because it is longer
    than QUESTION_LEAD_WORDS words (`Research with the kb tools first ... through /kb-research: (1) Which ...?`), the
    first such one, else ''. The pack of the whole piece then reads the lead-in's words as part of the question. Any
    whitespace between the colon and the number (a line break, two spaces) counts as the `: `."""
    for q in goal_questions(goal):
        colon = re.search(r":\s+", q)
        lead, rest = (q[:colon.start()], q[colon.end():]) if colon else (q, "")
        if rest.strip() and len(lead.split()) > QUESTION_LEAD_WORDS \
                and re.search(re.escape(lead) + r":\s+" + NUMBERED_PIECE.pattern, str(goal)):
            return lead
    return ""


def research_roots(it):
    """The kb roots an item's touches name (`kb/public/**`: `public`), in order, and `_self` after them (the root of
    this project's own rules, which a question about a tool of the project is answered in, not in a public article);
    [] when none does, which reads every root, and when `_self` is the only root named (a story touching just the
    `_self` eval file), which would otherwise read `_self` alone."""
    found = (TOUCH_ROOT.match(t) for t in it.get("touches") or [] if isinstance(t, str))
    roots = list(dict.fromkeys(m.group(1) for m in found if m))
    if roots == [SELF_ROOT]:
        return []
    return roots + [SELF_ROOT] if roots else roots


def question_coverage(question, roots):
    """(verdict, gap, error): the best coverage of QUESTION over ROOTS (None: every root), `good`, `weak` or `none`
    (`kbfacts.pack`'s verdict, the one `rag.py pack` prints); GAP, the `path:line` of an open `_gaps.md` entry whose
    title holds the question's key words (`kbfacts._gap_items`, the entry a `kb lacks:` route reads) or ''; ERROR,
    why the pack could not run, with the verdict `none`, or ''."""
    import kbfacts
    best, gap = "none", ""
    try:
        for root in roots or [None]:
            verdict = kbfacts.pack(question, root=root)["verdict"]
            if COVERAGE_ORDER.index(verdict) > COVERAGE_ORDER.index(best):
                best = verdict
            if not gap and verdict != "good":
                items = kbfacts._gap_items(question, None, root, False)
                gap = "{}:{}".format(*items[0]["key"]) if items else ""
    except Exception as ex:  # a kb the pack cannot read proves nothing
        return "none", "", f"the pack could not run: {type(ex).__name__}: {ex}"
    return best, gap, ""


def unanswered_questions(bl, it):
    """([question] of the narrowed goal's questions that the kb leaves unanswered, a line saying why nothing was read
    or ''): a question is answered when its coverage in the roots the touches name (every root with none) is `good`,
    or an open gap entry names it. Nothing is read, and the line says so, when the project's `kb_root`
    setting is empty (it is no kb), when `bl` is another clone than the one these tools run from (its pack reads this
    clone's kb), and when the goal names no question. Each question read is said on a line of its own, and each piece
    of the goal that is read as no question on a `skip:` line, which leaves the verdict as it is."""
    if not setting("kb_root"):
        return [], "coverage not read: the project's kb_root is empty"
    if other_clone(bl):
        return [], "coverage not read: --root names another clone, whose kb this process does not read"
    unread = []
    questions = goal_questions(it.get("goal"), unread)
    if not questions:
        return [], "coverage not read: the goal names no question (a sentence ending in `?` or a numbered piece)"
    for piece in unread:
        say(f"  skip: not read as a question (no `?`, not numbered): {piece}")
    roots = research_roots(it)
    left = []
    for q in questions:
        verdict, gap, error = question_coverage(q, roots)
        answered = verdict == "good" or bool(gap)
        said = f"{verdict} + gap entry {gap}" if gap else f"{verdict} ({error})" if error else verdict
        say(f"  {'ok  ' if answered else 'FAIL'} {said}: {q}")
        if not answered:
            left.append(q)
    return left, ""


def cmd_researched(bl, a):
    """The goal research story's check (bl_base.RESEARCH_CHECKS): exit 0 once its research is written, by done's own
    rules, a work commit on HEAD naming it or one of its descendants (`item_commits`) or its notes' `No outside facts:
    <reason>` (`research_without_facts`), and each question its narrowed goal names (`goal_questions`) is answered in
    the kb (`unanswered_questions`); exit 1 before. Read-only."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    if research_without_facts(it):
        proof = "its notes say No outside facts"
    else:
        commits = item_commits(bl.root, [iid] + bl.descendants(iid))
        if not commits:
            say(f"not researched {bl.label(iid)}: no commit on HEAD carries KB-Work: {iid} and changes a file other "
                "than item files, and its notes hold no `No outside facts: <reason>`")
            return 1
        proof = f"{len(commits)} work commit(s), the first {next(iter(commits))[:10]}"
    left, skipped = unanswered_questions(bl, it)
    if left:
        say(f"not researched {bl.label(iid)}: {len(left)} question(s) of its goal the kb leaves unanswered (a FAIL line "
            "above; coverage good, or an open _gaps.md entry whose title holds the question's key words, answers one)")
        return 1
    say(f"researched {bl.label(iid)}: {proof}" + (f"; {skipped}" if skipped else ""))
    return 0


CONFLICT_KINDS = ("textual", "semantic")  # what a predicted conflict is: lines collide, or the changes disagree in meaning


def read_conflicts(bl, source):
    """[(refs, path, kind)] of the predicted conflicts in SOURCE, a file or `-` for standard input: one JSON object a
    line, {"items": [two branches or item ids], "path": P, "kind": "textual" or "semantic"}, written by any conflict
    predictor; blank lines are skipped. A line that is no such object is refused naming its number."""
    try:
        text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    except OSError as ex:
        raise Refused(f"--conflicts: cannot read {source}: {ex}")
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            d = None
        refs = d.get("items") if isinstance(d, dict) else None
        if not (isinstance(refs, list) and len(refs) == 2 and all(isinstance(r, str) and r for r in refs)
                and isinstance(d.get("path"), str) and d["path"] and d.get("kind") in CONFLICT_KINDS):
            raise Refused(f"--conflicts: line {n} of {source} is no {{\"items\": [two branches or item ids], \"path\": P, "
                          f"\"kind\": {' or '.join(CONFLICT_KINDS)}}} object")
        out.append((refs, d["path"], d["kind"]))
    return out


def conflict_item(bl, ref):
    """The item id a conflict's branch or id names (the first id of the project's shape in REF, `work/ST-x` too) when
    the backlog holds it, else None."""
    m = id_re().search(ref)
    return m.group(0) if m and m.group(0) in bl.items else None


def planned_overlaps(bl, ids):
    """[(item id, item id, [paths])] of the pairs of IDS whose touches name a common path (globs read against the
    tracked files; a kb/_self doc is left out, as `check` leaves it), in order."""
    files = touch_files(bl.root)
    paths = {i: touch_paths(bl.items[i], files, []) for i in ids}
    out = []
    for n, a in enumerate(ids):
        for c in ids[n + 1:]:
            shared = sorted(p for p in paths[a] & paths[c] if not shared_doc(p))
            if shared:
                out.append((a, c, shared))
    return out


def conflict_lines(bl, sid, source):
    """The lines `precheck --conflicts` prints: the sprint's own overlap of planned files (`planned_overlaps` over the
    open committed items), then each predicted conflict whose two items are both in the sprint, then, apart, each
    that names an item outside it or one the backlog does not hold."""
    ids = precheck_items(bl, sid)
    members = set(bl.sprint_items(sid))
    lines = ["planned file overlaps of the sprint's items (their touches):"]
    found = planned_overlaps(bl, ids)
    lines += [f"  {bl.label(a)} and {bl.label(c)}: {', '.join(shared)}" for a, c, shared in found] or ["  none"]
    inside, apart = [], []
    for refs, path, kind in read_conflicts(bl, source):
        named = [conflict_item(bl, r) for r in refs]
        names = " and ".join(bl.label(i) if i else f"{r} (no item of the backlog)" for i, r in zip(named, refs))
        text = f"  {kind}: {names} at {path}"
        (inside if all(i in members for i in named) else apart).append(text)
    lines.append("predicted conflicts between the sprint's items (from the conflict predictor):")
    lines += inside or ["  none"]
    if apart:
        lines.append("predicted conflicts that name an item outside the sprint (listed apart):")
        lines += apart
    return lines


PRECHECK_NOTE = "passes before the work"  # an item's notes saying so keep its passing checks out of precheck's warnings


PRECHECK_TAIL = 20  # lines of a failing check's output that precheck prints under the check's line


TRACEBACK = "Traceback (most recent call last)"


def precheck_items(bl, sid):
    """The ids of the sprint's open committed items precheck reads, in order: the review and research stories are left
    out, since the review's checks pass by design and the research story's (`researched`) fails until its research is
    written."""
    return [iid for iid in sorted(bl.sprint_items(sid))
            if bl.items[iid].get("status") in ("draft", "todo", "doing")
            and not bl.items[iid].get("review") and not bl.items[iid].get("goal_research")]


def research_rows(bl, sid):
    """The kb/_self docs (sorted paths) that the rows of `bl_plan.SELF_EVAL` added by the sprint's goal research story
    name in expect_paths: for each commit on HEAD that carries the story's KB-Work (`item_commits`) and changes the eval
    file, the rows it has that its first parent's file lacks. [] when the sprint has no research story, none of its
    commits changed the file, or the file is unreadable in a revision."""
    story = research_story(bl, sid)
    if not story:
        return []
    docs = set()
    for sha, paths in item_commits(bl.root, [story]).items():
        if bl_plan.SELF_EVAL not in paths:
            continue
        try:
            now = git(bl.root, "show", f"{sha}:{bl_plan.SELF_EVAL}")
        except Refused:
            continue
        try:
            before = git(bl.root, "show", f"{sha}^:{bl_plan.SELF_EVAL}")
        except Refused:
            before = ""
        known = {tuple(r) for r in csv.reader(io.StringIO(before))}
        table = list(csv.reader(io.StringIO(now)))
        if not table or "expect_paths" not in table[0]:
            continue
        col = table[0].index("expect_paths")
        for row in table[1:]:
            if tuple(row) in known or len(row) <= col:
                continue
            docs.update(f"kb/_self/{p.strip()}" for p in row[col].split(";") if p.strip())
    return sorted(docs)


def precheck_rows(bl, sid):
    """[(item id, check, exit code, passed, output)] of each check, and of a bug its repro after them, of the sprint's
    open committed items (`precheck_items`), run once on the checkout as it is (before any work commit), as `done`
    runs them."""
    rows = []
    for iid in precheck_items(bl, sid):
        for c in clause_commands(bl.items[iid]):
            ok, code, out = run_check(bl.root, c)
            rows.append((iid, c, code if code is not None else -1, ok, out))
    return rows


def clause_map(bl, iid):
    """(lines, warnings, unread) of an item's goal clauses and the check or repro that reads each, from its `clauses`
    mapping ({clause, check} entries, the check an index into `clause_commands`): a line for each clause and a warning
    for each that no check reads (the mapping names it with no index in range, or has no entry for it), and for an
    entry that names no clause of the goal. An item whose goal is one clause with no mapping has nothing to say; one
    of several clauses with no mapping gets one warning, so the planner records which check reads each."""
    it = bl.items[iid]
    clauses = goal_clauses(it.get("goal"))
    cmds = clause_commands(it)
    entries = [e for e in it.get("clauses") or [] if isinstance(e, dict)]
    if len(clauses) < 2 and not entries:
        return [], [], 0
    label = bl.label(iid)
    if not entries:
        lines = [f"  {n}. {c[:120]}: no check recorded" for n, c in enumerate(clauses, 1)]
        return lines, [f"warning: {label}: its goal has {len(clauses)} clauses and the item records no clauses mapping: "
                       f"say which check or repro reads each (set {iid} --add-clause CLAUSE=N, N the index of the "
                       "check, the repro after them)"], len(clauses)
    lines, warns, unread = [], [], 0
    for n, c in enumerate(clauses, 1):
        at = sorted({e.get("check") for e in entries if e.get("clause") == c
                     and isinstance(e.get("check"), int) and 0 <= e["check"] < len(cmds)})
        if at:
            lines.append(f"  {n}. {c[:120]}: "
                         + "; ".join(f"check {i} `{shlex.join(map(str, cmds[i].get('run') or []))}`" for i in at))
            continue
        unread += 1
        lines.append(f"  {n}. {c[:120]}: no check reads it")
        warns.append(f"warning: {label}: goal clause {n} ({c[:80]}) is read by no check or repro: add one that proves "
                     f"it, then map it (set {iid} --add-clause CLAUSE=N), or reword the goal")
    for e in entries:
        if e.get("clause") not in clauses:
            warns.append(f"warning: {label}: its clauses mapping names {str(e.get('clause'))[:80]!r}, which is no "
                         "clause of its goal: reword the entry to a clause as the goal spells it")
    return lines, warns, unread


DELIVERY_READ = re.compile(r"_querylog|\bbl_cost\b|\bbacklog\.py\W+(?:--root\W+\S+\W+)?cost\b")


def after_merge_proof(bl, iid):
    """The command (argument list) of a code-lane item's check or repro that reads the committed query-log store or
    backlog.py's cost figures (DELIVERY_READ), else None. Only a query-log delivery after the merge changes what it
    reads, and `land` runs a code item's checks and repro before it pushes the merge request, so it stops there. A
    project with no `lane_module` has no code lane: None."""
    name = setting("lane_module")
    it = bl.items[iid]
    if not name or not it.get("touches"):
        return None
    kblane = importlib.import_module(name)
    if kblane.paths_lane(it["touches"])[0] != kblane.CODE:
        return None
    return next((c["run"] for c in clause_commands(it)
                 if DELIVERY_READ.search(" ".join(str(x) for x in c.get("run") or []))), None)


def intake_fingerprint(c):
    """The fingerprint FP of a check that is `backlog.py intake --status FP` (bl_intake.STATUS_REPRO and one more
    word), else None."""
    argv = c.get("run") or []
    n = len(bl_intake.STATUS_REPRO)
    if len(argv) == n + 1 and list(argv[:n]) == bl_intake.STATUS_REPRO and bl_intake.FP_RE.fullmatch(str(argv[n])):
        return argv[n]
    return None


def windowed_detector(root, fp, calls):
    """(detector, what it judges, when the check can first pass) when the fingerprint `fp` is a finding of a detector
    that judges a window of time, so the check follows time and no work: `trailers` (the commits within
    bl_intake.TRAILER_WINDOW_DAYS days of main's tip, so it passes once main has moved that far past the newest
    flagged commit, whatever the clock says) and `repeats` (the latest closed ISO week, so it can first pass once the
    running week has closed); else None. `calls` is a dict that holds the command classes of the committed ops
    sidecars once read, for the first repeats fingerprint that INSTEAD's keys do not name."""
    today = datetime.datetime.now(datetime.timezone.utc).date()
    days = bl_intake.TRAILER_WINDOW_DAYS
    if fp == bl_intake.fingerprint("trailers", bl_intake.WHOLE_KEY):
        when = (f"once main's tip is more than {days} days past the commits it names: the window follows main's tip, "
                "not the calendar")
        try:
            found = bl_intake.trailer_findings(root)
            times = git(root, "log", "--no-walk=unsorted", "--format=%ct", *[s for s, _ in found]).split() if found else []
        except (Refused, RuntimeError, OSError, ValueError):
            found, times = [], []
        if found and len(times) == len(found):
            newest = max(zip((int(t) for t in times), (s for s, _ in found)))
            day = datetime.datetime.fromtimestamp(newest[0], datetime.timezone.utc).date() + datetime.timedelta(days=days)
            when = (f"no earlier than {day}, and only once main's tip is more than {days} days past the newest commit it "
                    f"names ({newest[1]}): the window follows main's tip, not the calendar")
        return "trailers", f"the commits within {days} days of main's tip", when
    classes = set(bl_intake.INSTEAD)
    if not any(fp == bl_intake.fingerprint("repeats", k) for k in classes):
        if "classes" not in calls:
            try:
                calls["classes"] = {k for _, k in bl_intake.committed_calls(root)[0]}
            except (OSError, ValueError):
                calls["classes"] = set()
        classes = calls["classes"]
    if any(fp == bl_intake.fingerprint("repeats", k) for k in classes):
        year, week, _ = today.isocalendar()
        monday = today + datetime.timedelta(days=8 - today.isoweekday())  # the Monday after the running week
        return "repeats", "the latest closed ISO week", f"on {monday}, once the week {year}-W{week:02d} has closed"
    return None


def cmd_precheck(bl, a):
    """precheck SP: run each committed item's checks, and a bug's repro, once before any work and warn (exit 0) of each
    that passes already: it proves nothing yet, unless the item's notes say the check passes before the work (one that
    pins behaviour that must stay). It also warns, whether the check or repro passes or not, of one that is the
    `intake --status` of a time-windowed detector (repeats, trailers), naming when it can first pass, so the item is
    moved or gated before the start. A check that fails prints its line and the last PRECHECK_TAIL lines of its output
    (stdout and stderr together) under it, so a planner sees whether it fails for the premise or for another reason; a
    traceback in that output is said to be a broken check, not a failing premise. After the checks it prints each
    committed item's goal clauses (split as close --summary splits a sprint goal) with the check or repro that reads each,
    from the item's `clauses` mapping (`set ID --add-clause CLAUSE=N`), and warns of a clause no check reads and of a
    goal of several clauses with no mapping (`clause_map`). It warns of a code-lane item whose check or repro reads the
    committed query-log store or backlog.py cost figures (`after_merge_proof`): land runs those before the merge
    request is pushed, so only a separate item done after the merge can prove them. It warns of an item whose goal
    words a DOC fact reworded or added (the words DOC, reword, reworded) and whose touches name an article of a kb root
    with no touch that covers that root's `_anchors.csv` (`bl_plan.anchors_warnings`), naming the root and the file to
    add. It warns of an item whose touches name a kb/_self doc that eval rows added by the sprint's goal research story
    (its commits, `research_rows`) name in expect_paths and have no touch that covers the _self eval file
    (`bl_plan.research_rows_warnings`), so a reworded line moves its row in the item; it reads those rows once the
    research story has landed, so the orchestrator runs it again then. It warns of an open goal research story whose
    goal has a numbered piece behind a lead-in of more than QUESTION_LEAD_WORDS words (`joined_lead_in`): `researched`
    reads that lead-in together with the first question, so the planner moves it to the notes or ends it with a
    semicolon. It warns of each committed item's file other than a kb/_self doc that another live session's plan or
    another active or planned sprint's item also plans (`bl_peers.peer_overlaps`), naming the item, the file and the
    other work as undecided until a depends_on between the two items or a `coordinate` event between them settles it.
    kb-sprint plan runs it before the start gate is asked, so start stays fast."""
    sid = need(bl, a.sprint)
    if bl.items[sid].get("kind") != "sprint":
        raise Refused(f"precheck needs a sprint: {bl.label(sid)} is a {bl.items[sid].get('kind')}")
    rows = precheck_rows(bl, sid)
    passing = 0
    calls = {}
    for iid, c, code, ok, out in rows:
        fp = intake_fingerprint(c)
        win = windowed_detector(bl.root, fp, calls) if fp else None
        if win:
            name, judges, when = win
            tail = (f"it passes now, but its result follows time, not the work: it can change {when}" if ok else
                    f"it can first pass {when}; move the item to a sprint that starts after that, or gate it, before the start")
            say(f"warning: {bl.label(iid)}: `{shlex.join(c['run'])}` is the intake --status of the time-windowed "
                f"detector {name}: it judges {judges}; {tail}")
        if not ok:
            lines = out.strip().splitlines()
            broken = ("; the output holds a traceback: the check is broken (an exception), not a failing premise"
                      if TRACEBACK in out else "")
            say(f"{bl.label(iid)}: `{shlex.join(c['run'])}` fails before the work (exit {code}){broken}; "
                + (f"the last {min(len(lines), PRECHECK_TAIL)} of {len(lines)} lines of its output:" if lines
                   else "it printed nothing"))
            for line in lines[-PRECHECK_TAIL:]:
                say(f"    {line}")
            continue
        if PRECHECK_NOTE in (bl.items[iid].get("notes") or ""):
            continue
        passing += 1
        say(f"warning: {bl.label(iid)}: `{shlex.join(c['run'])}` already exits {code} before the work: it proves "
            f"nothing yet; make it fail until the work is done, or say in the item's notes that it {PRECHECK_NOTE} "
            "and why (a check that pins behaviour that must stay)")
    unread = 0
    quoted = research_rows(bl, sid)
    for iid in sorted(bl.sprint_items(sid)):
        it = bl.items[iid]
        lead = joined_lead_in(it.get("goal")) if it.get("goal_research") and it.get("status") in ("draft", "todo", "doing") else ""
        if lead:
            say(f"warning: {bl.label(iid)}: researched would read the goal's lead-in of {len(lead.split())} words "
                f"(more than {QUESTION_LEAD_WORDS}: {lead[:60]}...) together with its first question, so the pack of "
                "the whole piece is weak: move the lead-in to the item's notes, or end it with a semicolon, before "
                "the start gate")
    for iid, path, others in bl_peers.peer_overlaps(bl, sid, precheck_items(bl, sid)):
        more = f" and {len(others) - bl_peers.HOLDERS_SHOWN} more" if len(others) > bl_peers.HOLDERS_SHOWN else ""
        say(f"warning: {bl.label(iid)}: {path} is also planned by {', '.join(others[:bl_peers.HOLDERS_SHOWN])}{more}: undecided; "
            f"order the two (set {iid} --add-depends OTHER) or settle it (kbask.py coordinate {iid} OTHER STRATEGY, OTHER "
            "the other item, topic or session) before the start")
    for iid in precheck_items(bl, sid):
        late = after_merge_proof(bl, iid)
        if late:
            say(f"warning: {bl.label(iid)}: `{shlex.join(late)}` reads the committed query-log store or backlog.py cost "
                "figures, which only a query-log delivery after the merge changes, and land runs a code item's checks "
                "and repro before it pushes the merge request, so it stops at checks: move that proof to a separate "
                "item, done after the merge")
        for text in bl_plan.anchors_warnings(bl, [iid]):
            say(text)
        for text in bl_plan.research_rows_warnings(bl, [iid], quoted):
            say(text)
        lines, warns, n = clause_map(bl, iid)
        unread += n
        if lines:
            say(f"goal clauses of {bl.label(iid)}, and the check or repro that reads each:")
            for text in lines:
                say(text)
        for text in warns:
            say(text)
    if a.conflicts:
        for text in conflict_lines(bl, sid, a.conflicts):
            say(text)
    say(f"precheck {bl.label(sid)}: checks={len(rows)} passing={passing} unread={unread}")
    return 0


bl_cli.register("researched", cmd_researched, lambda p: p.add_argument("id"))
def precheck_arguments(p):
    p.add_argument("sprint")
    p.add_argument("--conflicts", metavar="FILE|-",
                   help="JSON lines of predicted conflicts from any predictor, printed beside the sprint's own file overlaps")


bl_cli.register("precheck", cmd_precheck, precheck_arguments)
