#!/usr/bin/env python3
"""The kb's own backlog: epics, stories, tasks, subtasks, bugs and sprints, one JSON file per item in
kb/_self/backlog/ (kb/_self/backlog.md is the runbook). Standard library only; no model, and no network except `red-pipeline`.

  backlog.py new KIND --title T [--parent ID] [--sprint ID] [--priority P1|P2|P3] [--rank N] [--goal TEXT]
                 [--severity S1..S4] [--check CMD]... [--touch GLOB]... [--depends ID]... [--repro CMD]
                                          a new item (KIND: epic, story, task, subtask, bug, sprint); prints its id
                                          and title. A bug's --repro must fail now; a sprint gets its start gate and
                                          its review story
  backlog.py check                        validate every item (fields, links, cycles, canonical form, and a planned
                                          sprint's items still draft); exit 1 on errors
  backlog.py fmt                          rewrite every item in canonical form
  backlog.py list [--kind K] [--status S] [--sprint ID]   one line per item: id, kind, status, priority, title
  backlog.py tree [ID] [--sprint ID]      the hierarchy under an item, a sprint or everything
  backlog.py show ID                      one item, its parent chain, children and what it waits on
  backlog.py next [--sprint ID] [--any] [--all]   the ready item to work on first (--all: every ready item in
                                          order; --any: items outside an active sprint too, for single-item work)
  backlog.py claim ID --by NAME           status doing, claimed by NAME;  backlog.py release ID  back to todo
  backlog.py answer ID GATE (--answer TEXT --by operator|agent | --provisional | --confirm)
                                          record a gate's answer: --provisional takes the recommendation as the
                                          agent's answer (provisional gates only); --confirm makes an agent's answer
                                          the operator's
  backlog.py fire ID                      mark an item's external trigger as fired
  backlog.py done ID [--dry-run]          run the item's checks at a clean HEAD, check its commits' scope, record the
                                          evidence and set status done; exit 1 with the reasons otherwise
  backlog.py drop ID --why TEXT           status dropped (an item outside any sprint is deleted: git keeps it)
  backlog.py start SPRINT                 activate a sprint whose start gate the operator answered; drafts become todo
  backlog.py close SPRINT                 delete a finished sprint, its items and the epics they finished
  backlog.py horizon [--sprint ID] [--hook]   how far each active sprint can go without the operator: reachable
                                          items, what waits on which gate or trigger, the critical path
  backlog.py goal ID                      a /goal condition for the item: its end state, checks and scope
  backlog.py red-pipeline [--status|--hook]   the newest finished pipeline of origin's main (glab api, gh on GitHub;
                                          a note when neither is signed in): when it failed and no automatic revert
                                          covers it, one bug (S1 when the kb-tests job failed, else S2) unless an item
                                          already names that pipeline. --status: exit 0 green, 1 red or unreadable
                                          (the bug's repro). --hook: the async SessionStart form, silent

--root DIR (before the command) runs against another clone. Exit: 0 ok, 1 a refused command or check errors,
2 bad arguments or an unknown id.

Every line that names an item prints its id and its title together.
"""
import argparse, base64, hashlib, json, re, secrets, shlex, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REL_DIR = "kb/_self/backlog"
KINDS = {"epic": "EP", "story": "ST", "task": "TK", "subtask": "SB", "bug": "BG", "sprint": "SP"}
PREFIX_KIND = {v: k for k, v in KINDS.items()}
ID_RE = re.compile(r"\b(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}\b")
STATUSES = ("draft", "todo", "doing", "done", "dropped")
WORKED = ("todo", "doing", "done")  # statuses an item of a planned sprint cannot have: it stays draft until start
SPRINT_STATUSES = ("planned", "active")
PRIORITIES = ("P1", "P2", "P3")
SEVERITIES = ("S1", "S2", "S3", "S4")
GATE_KINDS = ("blocking", "provisional")
PARENTS = {"epic": (), "story": ("epic",), "bug": ("epic",), "task": ("story", "bug"), "subtask": ("task",),
           "sprint": ()}
IN_SPRINT = ("story", "bug")  # the kinds a sprint commits to; their tasks and subtasks come with them
NEEDS_CHECKS = ("story", "bug", "task")
NEEDS_TOUCHES = ("task", "subtask")
ORDER = ("id", "kind", "title", "status", "parent", "sprint", "review", "priority", "rank", "severity", "goal",
         "repro", "checks", "touches", "depends_on", "relates_to", "gates", "trigger", "links", "notes",
         "claimed_by", "evidence")
FIELDS = set(ORDER)
# files any item's commits may change besides its `touches`: the tracker itself and what build_index.py regenerates
ALWAYS_IN_SCOPE = ("kb/_self/backlog/**", "kb/*/_coverage.csv", "kb/*/_coverage.md")
CHECK_TIMEOUT_S = 1800
TEXT_MAX = 2000  # one field's text; a longer one is an essay, not a work item
START_GATE = "start"
REVIEW_CHECKS = [{"run": ["python3", "_tools/backlog.py", "check"]}, {"run": ["python3", "_tools/tests.py"]}]


class Refused(Exception):
    pass


# ------------------------------------------------------------------ storage

def new_id(kind):
    return KINDS[kind] + "-" + base64.b32encode(secrets.token_bytes(5)).decode().lower()


def canonical(item):
    keys = [k for k in ORDER if k in item] + sorted(k for k in item if k not in FIELDS)
    return json.dumps({k: item[k] for k in keys}, ensure_ascii=False, indent=2) + "\n"


class Backlog:
    def __init__(self, root):
        self.root = Path(root)
        self.dir = self.root / REL_DIR
        self.items, self.raw, self.load_errors = {}, {}, []
        if self.dir.is_dir():
            for p in sorted(self.dir.glob("*.json")):
                text = p.read_text(encoding="utf-8")
                try:
                    item = json.loads(text)
                except json.JSONDecodeError as e:
                    self.load_errors.append(f"{p.name}: not JSON ({e})")
                    continue
                if not isinstance(item, dict):
                    self.load_errors.append(f"{p.name}: not a JSON object")
                    continue
                self.items[p.stem] = item
                self.raw[p.stem] = text

    def save(self, item):
        self.dir.mkdir(parents=True, exist_ok=True)
        text = canonical(item)
        with open(self.dir / f"{item['id']}.json", "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        self.items[item["id"]] = item
        self.raw[item["id"]] = text

    def delete(self, iid):
        (self.dir / f"{iid}.json").unlink()
        self.items.pop(iid, None)

    def get(self, iid):
        if iid not in self.items:
            raise KeyError(iid)
        return self.items[iid]

    def label(self, iid):
        it = self.items.get(iid)
        return f"{iid} “{it.get('title', '')}”" if it else f"{iid} (no such item)"

    def children(self, iid):
        return [i for i, it in self.items.items() if it.get("parent") == iid]

    def descendants(self, iid):
        out, todo = [], self.children(iid)
        while todo:
            c = todo.pop()
            out.append(c)
            todo.extend(self.children(c))
        return out

    def ancestors(self, iid):
        out, cur, seen = [], self.items.get(iid, {}).get("parent"), set()
        while cur and cur in self.items and cur not in seen:
            seen.add(cur)
            out.append(cur)
            cur = self.items[cur].get("parent")
        return out

    def sprint_of(self, iid):
        """The sprint an item belongs to: its own `sprint`, or that of the story or bug above it."""
        for i in [iid] + self.ancestors(iid):
            s = self.items.get(i, {}).get("sprint")
            if s:
                return s
        return None

    def sprint_items(self, sid):
        return [i for i, it in self.items.items() if it.get("kind") != "sprint" and self.sprint_of(i) == sid]

    def order_key(self, iid):
        """Work order: S1 bugs first, then the priority and rank of the story or bug on top, then the item's own."""
        chain = [iid] + self.ancestors(iid)
        top = next((i for i in reversed(chain) if self.items[i].get("kind") in IN_SPRINT), iid)
        t, it = self.items[top], self.items[iid]
        s1 = 0 if t.get("kind") == "bug" and t.get("severity") == "S1" else 1
        return (s1, t.get("priority", "P3"), t.get("rank", 0), top, it.get("rank", 0), iid)


# ------------------------------------------------------------------ validation

def _text_ok(v):
    return isinstance(v, str) and v.strip() and len(v) <= TEXT_MAX


def _check_ok(c):
    return (isinstance(c, dict) and isinstance(c.get("run"), list) and c["run"]
            and all(isinstance(x, str) for x in c["run"]) and set(c) <= {"run", "exit", "match"}
            and isinstance(c.get("exit", 0), int) and isinstance(c.get("match", ""), str))


def validate(bl):
    errs = list(bl.load_errors)
    for iid, it in bl.items.items():
        e = lambda msg, iid=iid: errs.append(f"{bl.label(iid)}: {msg}")  # noqa: E731
        if it.get("id") != iid:
            e(f"id {it.get('id')!r} does not match its file name")
        if not ID_RE.fullmatch(iid):
            e("id is not <EP|ST|TK|SB|BG|SP>-<8 base32 characters>")
        kind = it.get("kind")
        if kind not in KINDS:
            e(f"kind {kind!r} is not one of {', '.join(KINDS)}")
            continue
        if ID_RE.fullmatch(iid) and PREFIX_KIND[iid[:2]] != kind:
            e(f"id prefix {iid[:2]} does not match kind {kind}")
        unknown = set(it) - FIELDS
        if unknown:
            e(f"unknown fields {sorted(unknown)}")
        if not _text_ok(it.get("title")):
            e("title missing or longer than TEXT_MAX")
        for f in ("goal", "notes"):
            if f in it and not _text_ok(it[f]):
                e(f"{f} empty or longer than TEXT_MAX")
        if bl.raw.get(iid) != canonical(it):
            e("not in canonical form (python3 _tools/backlog.py fmt)")
        if kind == "sprint":
            if it.get("status") not in SPRINT_STATUSES:
                e(f"sprint status must be one of {SPRINT_STATUSES}")
            if not _text_ok(it.get("goal")):
                e("a sprint needs a goal")
            if not any(g.get("id") == START_GATE for g in it.get("gates", []) if isinstance(g, dict)):
                e("a sprint needs its start gate")
            reviews = [i for i in bl.sprint_items(iid) if bl.items[i].get("review")]
            if len(reviews) != 1:
                e(f"a sprint needs exactly one review story (has {len(reviews)})")
        else:
            if it.get("status") not in STATUSES:
                e(f"status must be one of {STATUSES}")
            if it.get("priority") not in PRIORITIES:
                e(f"priority must be one of {PRIORITIES}")
            if not isinstance(it.get("rank", 0), int):
                e("rank must be an integer")
            if kind != "subtask" and kind != "epic" and not _text_ok(it.get("goal")):
                e("goal (the end state) missing")
        par = it.get("parent")
        if par:
            if par not in bl.items:
                e(f"parent {par} does not exist")
            elif bl.items[par].get("kind") not in PARENTS[kind]:
                e(f"a {kind} cannot sit under a {bl.items[par].get('kind')}")
        elif kind in ("task", "subtask"):
            e(f"a {kind} needs a parent ({' or '.join(PARENTS[kind])})")
        if "sprint" in it:
            s = it["sprint"]
            if kind not in IN_SPRINT:
                e("only stories and bugs name a sprint; tasks and subtasks follow theirs")
            elif s not in bl.items or bl.items[s].get("kind") != "sprint":
                e(f"sprint {s} does not exist")
        if it.get("review") and (kind != "story" or not it.get("sprint")):
            e("a review item is a story in a sprint")
        if kind == "bug":
            if it.get("severity") not in SEVERITIES:
                e(f"a bug needs a severity {SEVERITIES}")
            if not _check_ok(it.get("repro")):
                e("a bug needs a repro check (a command that fails until it is fixed)")
        elif "severity" in it or "repro" in it:
            e("severity and repro are for bugs only")
        checks = it.get("checks", [])
        if not isinstance(checks, list) or not all(_check_ok(c) for c in checks):
            e("checks must be a list of {run: [argv...], exit?: int, match?: regex}")
        elif kind in NEEDS_CHECKS and not checks and not (kind == "bug" and it.get("repro")):
            e("checks missing: the commands that prove the end state")
        for c in checks if isinstance(checks, list) else []:
            if isinstance(c, dict) and c.get("match"):
                try:
                    re.compile(c["match"])
                except re.error as x:
                    e(f"check match is not a regex: {x}")
        touches = it.get("touches", [])
        if not isinstance(touches, list) or not all(isinstance(t, str) and t for t in touches):
            e("touches must be a list of path globs")
        elif kind in NEEDS_TOUCHES and not touches:
            e("touches missing: the path globs this item may change")
        for f in ("depends_on", "relates_to"):
            for d in it.get(f, []):
                if d not in bl.items:
                    e(f"{f} names {d}, which does not exist")
                elif d == iid:
                    e(f"{f} names the item itself")
                elif f == "depends_on" and bl.items[d].get("status") == "dropped":
                    e(f"depends on dropped {bl.label(d)}")
        gate_ids = set()
        for g in it.get("gates", []):
            if not isinstance(g, dict) or not _text_ok(g.get("question", "")) or g.get("kind") not in GATE_KINDS:
                e("a gate needs id, kind (blocking|provisional) and question")
                continue
            if g.get("id") in gate_ids or not g.get("id"):
                e(f"gate id {g.get('id')!r} missing or repeated")
            gate_ids.add(g.get("id"))
            if g["kind"] == "provisional" and not g.get("recommendation"):
                e(f"provisional gate {g['id']} needs a recommendation")
            if "answer" in g and g.get("by") not in ("operator", "agent"):
                e(f"gate {g['id']}: an answer needs by: operator|agent")
            if g["kind"] == "blocking" and g.get("by") == "agent":
                e(f"gate {g['id']} is blocking: only the operator answers it")
        trig = it.get("trigger")
        if trig is not None and not (isinstance(trig, dict) and _text_ok(trig.get("when", ""))
                                     and isinstance(trig.get("fired", False), bool)):
            e("trigger must be {when: text, fired: bool}")
        st = it.get("status")
        if st == "doing" and not it.get("claimed_by"):
            e("status doing needs claimed_by")
        sp = bl.sprint_of(iid) if kind != "sprint" else None
        if st in WORKED and sp in bl.items and bl.items[sp].get("status") == "planned":
            e(f"status {st} while its sprint {bl.label(sp)} is planned: not in a started sprint "
              f"(a planned sprint's items stay draft until backlog.py start)")
        if st == "done" and kind in NEEDS_CHECKS + ("bug",) and not it.get("evidence"):
            e("status done without evidence (set only by backlog.py done)")
    # cycles over depends_on and parent
    state = {}

    def visit(i, path):
        state[i] = 1
        for d in bl.items[i].get("depends_on", []) + ([bl.items[i]["parent"]] if bl.items[i].get("parent") else []):
            if d not in bl.items:
                continue
            if state.get(d) == 1:
                errs.append(f"cycle: {' -> '.join(bl.label(x) for x in path + [d])}")
            elif not state.get(d):
                visit(d, path + [d])
        state[i] = 2

    for i in bl.items:
        if not state.get(i):
            visit(i, [i])
    return errs


# ------------------------------------------------------------------ readiness

def open_gates(it, kinds=("blocking",)):
    return [g for g in it.get("gates", []) if g.get("kind") in kinds and "answer" not in g]


def waits(bl, iid, any_sprint=False):
    """Why an item cannot be worked on now ([] = ready): its status, sprint, dependencies, gates, trigger, children."""
    it = bl.items[iid]
    out = []
    if it.get("kind") in ("sprint", "epic"):
        return ["not a work item"]
    if it.get("status") not in ("todo", "doing"):
        out.append(f"status {it.get('status')}")
    sp = bl.sprint_of(iid)
    if not any_sprint and (not sp or bl.items.get(sp, {}).get("status") != "active"):
        out.append("not in an active sprint")
    for i in [iid] + bl.ancestors(iid):
        a = bl.items[i]
        for g in open_gates(a):
            out.append(f"gate {i}/{g['id']}: {g['question']}")
        t = a.get("trigger")
        if t and not t.get("fired"):
            out.append(f"trigger on {bl.label(i)}: {t['when']}")
    for d in it.get("depends_on", []):
        if bl.items.get(d, {}).get("status") != "done":
            out.append(f"depends on {bl.label(d)}")
    if it.get("review"):
        for s in bl.sprint_items(sp):
            if s != iid and bl.items[s].get("kind") in IN_SPRINT and bl.items[s].get("status") not in ("done", "dropped"):
                out.append(f"review waits on {bl.label(s)}")
    open_children = [c for c in bl.children(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if open_children:
        out.append(f"{len(open_children)} open child item(s)")
    return out


def ready(bl, sprint=None, any_sprint=False):
    ids = [i for i in bl.items if not waits(bl, i, any_sprint)
           and (sprint is None or bl.sprint_of(i) == sprint)]
    return sorted(ids, key=bl.order_key)


# ------------------------------------------------------------------ git and checks

def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def glob_re(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def in_scope(path, globs):
    return any(glob_re(g).match(path) for g in list(globs) + list(ALWAYS_IN_SCOPE))


def scope(bl, iid):
    """The globs an item's commits may touch: its own and every descendant's."""
    out = list(bl.items[iid].get("touches", []))
    for d in bl.descendants(iid):
        out += bl.items[d].get("touches", [])
    return out


def item_commits(root, ids):
    """{commit: [paths]} of the commits on HEAD whose KB-Work trailer names any of the ids, oldest first."""
    log = git(root, "log", "HEAD", "--reverse", "--no-merges",
              "--format=%H%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)%x1e")
    out = {}
    for rec in log.split("\x1e"):
        sha, _, vals = rec.strip().partition("\x00")
        if sha and set(ID_RE.findall(vals)) & set(ids):
            out[sha] = [p for p in git(root, "show", "--name-only", "--format=", sha).splitlines() if p]
    return out


def blob_id(root, rev, path):
    p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{rev}:{path}"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 else None


def out_of_scope(root, commits, globs):
    """[(commit, path)] of the paths outside the globs that the item's commits changed and HEAD still has changed:
    a later commit that restored a file (a revert) clears it."""
    first = {}
    for sha, paths in commits.items():
        for p in paths:
            if not in_scope(p, globs):
                first.setdefault(p, sha)
    return [(sha, p) for p, sha in first.items() if blob_id(root, f"{sha}^", p) != blob_id(root, "HEAD", p)]


def run_check(root, c):
    """Run one check without a shell. A check that names python3 or python runs with the interpreter running this
    tool: on a host whose python3 is the Windows Store alias, or none on PATH, it still proves the item."""
    argv = list(c["run"])
    if argv and argv[0] in ("python3", "python"):
        argv[0] = sys.executable
    try:
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=CHECK_TIMEOUT_S)
        code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        code, out = None, str(e)
    ok = code == c.get("exit", 0) and (not c.get("match") or re.search(c["match"], out, re.M) is not None)
    return ok, code, out


def parse_cmd(s):
    return shlex.split(s, posix=True)


# ------------------------------------------------------------------ commands

def say(line=""):
    print(line)


def cmd_new(bl, a):
    kind = a.kind
    it = {"id": new_id(kind), "kind": kind, "title": a.title.strip()}
    if kind == "sprint":
        it.update(status="planned", goal=a.goal or a.title,
                  gates=[{"id": START_GATE, "kind": "blocking",
                          "question": "Approve this sprint's goal and committed items?",
                          "options": ["approve", "change", "cancel"], "recommendation": "approve"}])
        bl.save(it)
        rv = {"id": new_id("story"), "kind": "story", "title": f"Review sprint: {it['title']}"[:TEXT_MAX],
              "status": "draft", "sprint": it["id"], "review": True, "priority": "P1", "rank": 999999,
              "goal": "Every committed item is done or dropped, provisional answers are confirmed by the operator, "
                      "and a fresh-context review of the sprint's diff found no unfiled defect.",
              "checks": REVIEW_CHECKS}
        bl.save(rv)
        say(f"new sprint {bl.label(it['id'])}, review story {bl.label(rv['id'])}")
        return 0
    it.update(status="todo" if kind in ("task", "subtask") else "draft", priority=a.priority, rank=a.rank)
    for k in ("parent", "sprint", "goal"):
        if getattr(a, k):
            it[k] = getattr(a, k)
    if it["status"] == "todo" and a.parent in bl.items:  # a task of a planned sprint stays draft until its start
        sp = bl.sprint_of(a.parent)
        if bl.items.get(sp, {}).get("status") == "planned":
            it["status"] = "draft"
    if kind == "bug":
        if not a.severity or not a.repro:
            raise Refused("a bug needs --severity and --repro")
        it["severity"] = a.severity
        it["repro"] = {"run": parse_cmd(a.repro)}
        ok, code, _ = run_check(bl.root, it["repro"])
        if ok:
            raise Refused(f"--repro passes now (exit {code}): it must fail until the bug is fixed")
    if a.check:
        it["checks"] = [{"run": parse_cmd(c)} for c in a.check]
    if a.touch:
        it["touches"] = a.touch
    if a.depends:
        it["depends_on"] = a.depends
    bl.save(it)
    errs = [x for x in validate(bl) if x.startswith(it["id"])]
    say(f"new {kind} {bl.label(it['id'])}")
    for x in errs:
        say(f"  to fill in: {x.split(': ', 1)[1]}")
    return 0


def cmd_check(bl, a):
    errs = validate(bl)
    for x in errs:
        say(x)
    say(f"backlog check: items={len(bl.items)} errors={len(errs)}")
    return 1 if errs else 0


def cmd_fmt(bl, a):
    n = 0
    for iid, it in bl.items.items():
        if bl.raw.get(iid) != canonical(it):
            bl.save(it)
            n += 1
    say(f"fmt: rewrote {n}")
    return 0


def line(bl, iid):
    it = bl.items[iid]
    extra = f" {it['severity']}" if it.get("severity") else ""
    return f"{iid}  {it['kind']:<7} {it.get('status', ''):<7} {it.get('priority', ''):<2}{extra}  {it.get('title', '')}"


def cmd_list(bl, a):
    for iid in sorted(bl.items, key=lambda i: (bl.items[i].get("kind") != "sprint", bl.order_key(i)
                                               if bl.items[i].get("kind") != "sprint" else i)):
        it = bl.items[iid]
        if (a.kind and it.get("kind") != a.kind) or (a.status and it.get("status") != a.status) \
                or (a.sprint and bl.sprint_of(iid) != a.sprint and iid != a.sprint):
            continue
        say(line(bl, iid))
    return 0


def cmd_tree(bl, a):
    def walk(i, depth):
        say("  " * depth + line(bl, i))
        for c in sorted(bl.children(i), key=bl.order_key):
            walk(c, depth + 1)

    if a.id:
        walk(need(bl, a.id), 0)
        return 0
    if a.sprint:
        need(bl, a.sprint)
        say(line(bl, a.sprint))
        for i in sorted((i for i in bl.sprint_items(a.sprint) if bl.items[i].get("sprint")), key=bl.order_key):
            walk(i, 1)
        return 0
    for i in sorted((i for i, it in bl.items.items() if not it.get("parent") and it.get("kind") != "sprint"),
                    key=bl.order_key):
        walk(i, 0)
    return 0


def cmd_show(bl, a):
    iid = need(bl, a.id)
    say(canonical(bl.items[iid]).rstrip())
    for p in bl.ancestors(iid):
        say(f"parent: {bl.label(p)}")
    sp = bl.sprint_of(iid)
    if sp:
        say(f"sprint: {bl.label(sp)}")
    for c in bl.children(iid):
        say(f"child: {line(bl, c)}")
    w = waits(bl, iid)
    say("ready" if not w else "waits on:\n  " + "\n  ".join(w))
    return 0


def cmd_next(bl, a):
    ids = ready(bl, a.sprint, a.any)
    if not ids:
        say("nothing ready" + (f" in {bl.label(a.sprint)}" if a.sprint else "") + ": python3 _tools/backlog.py horizon")
        return 1
    for i in ids if a.all else ids[:1]:
        say(line(bl, i))
    return 0


def cmd_claim(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    w = [x for x in waits(bl, iid, any_sprint=True) if not x.startswith("status doing")]
    if w:
        raise Refused(f"{bl.label(iid)} is not ready:\n  " + "\n  ".join(w))
    if it.get("status") == "doing" and it.get("claimed_by") != a.by:
        raise Refused(f"{bl.label(iid)} is claimed by {it['claimed_by']}")
    it.update(status="doing", claimed_by=a.by)
    bl.save(it)
    say(f"claimed {bl.label(iid)} for {a.by}")
    return 0


def cmd_release(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    if it.get("status") != "doing":
        raise Refused(f"{bl.label(iid)} is {it.get('status')}, not doing")
    it["status"] = "todo"
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"released {bl.label(iid)}")
    return 0


def cmd_answer(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    g = next((g for g in it.get("gates", []) if g.get("id") == a.gate), None)
    if g is None:
        raise Refused(f"{bl.label(iid)} has no gate {a.gate}")
    if a.confirm:
        if g.get("by") != "agent":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} has no agent answer to confirm")
        g["by"] = "operator"
    elif a.provisional:
        if g["kind"] != "provisional":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} is blocking: only the operator answers it")
        g.update(answer=g["recommendation"], by="agent")
    else:
        if not a.answer or not a.by:
            raise Refused("--answer TEXT and --by operator|agent")
        if g["kind"] == "blocking" and a.by != "operator":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} is blocking: only the operator answers it")
        g.update(answer=a.answer, by=a.by)
    bl.save(it)
    say(f"gate {a.gate} of {bl.label(iid)}: {g['answer']} (by {g['by']})")
    return 0


def cmd_fire(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    if not it.get("trigger"):
        raise Refused(f"{bl.label(iid)} has no trigger")
    it["trigger"]["fired"] = True
    bl.save(it)
    say(f"trigger fired on {bl.label(iid)}: {it['trigger']['when']}")
    return 0


def cmd_done(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    kind = it["kind"]
    if kind == "sprint":
        raise Refused("a sprint is closed with backlog.py close")
    if kind == "epic":
        problems = [f"open child {line(bl, c)}" for c in bl.children(iid)
                    if bl.items[c].get("status") not in ("done", "dropped")]
    else:
        problems = [x for x in waits(bl, iid, any_sprint=True)
                    if not x.startswith(("status doing", "not in an active sprint"))]
    if it.get("status") not in ("todo", "doing", "draft" if kind == "epic" else "todo"):
        problems.append(f"status {it.get('status')}")
    if it.get("review"):
        sp = bl.sprint_of(iid)
        for s in bl.sprint_items(sp) + [sp]:
            for g in bl.items[s].get("gates", []):
                if g.get("by") == "agent":
                    problems.append(f"provisional answer to confirm: {bl.label(s)} gate {g['id']}: {g['answer']}")
    globs = scope(bl, iid)
    if globs:
        dirty = [ln[3:] for ln in git(bl.root, "status", "--porcelain").splitlines()
                 if in_scope(ln[3:].strip('"'), globs) and not in_scope(ln[3:].strip('"'), ())]
        if dirty:
            problems.append("uncommitted changes in scope (checks run on HEAD): " + ", ".join(dirty[:5]))
        for sha, path in out_of_scope(bl.root, item_commits(bl.root, [iid] + bl.descendants(iid)), globs):
            problems.append(f"commit {sha[:10]} changed {path}, outside touches (revert it, or widen touches)")
    if problems:
        raise Refused(f"{bl.label(iid)} is not done:\n  " + "\n  ".join(problems))
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    results, failed = [], []
    for c in checks:
        ok, code, out = run_check(bl.root, c)
        results.append({"run": c["run"], "exit": code, "sha256": hashlib.sha256(out.encode()).hexdigest()[:16]})
        say(f"{'ok  ' if ok else 'FAIL'} exit={code} {shlex.join(c['run'])}")
        if not ok:
            failed.append((c, code, out))
    if failed:
        for c, code, out in failed:
            tail = "\n".join(out.strip().splitlines()[-8:])
            say(f"--- {shlex.join(c['run'])} (want exit {c.get('exit', 0)}"
                + (f", output matching {c['match']!r}" if c.get("match") else "") + f"):\n{tail}")
        raise Refused(f"{bl.label(iid)} is not done: {len(failed)} check(s) failed")
    if a.dry_run:
        say(f"{bl.label(iid)} would be done")
        return 0
    head = git(bl.root, "rev-parse", "HEAD").strip()
    it.update(status="done", evidence={"commit": head, "checks": results})
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"done {bl.label(iid)} at {head[:10]}; commit this with the trailer KB-Work: {iid}")
    return 0


def cmd_drop(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    live = [c for c in bl.descendants(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if live:
        raise Refused(f"{bl.label(iid)} has open children: " + ", ".join(bl.label(c) for c in live[:5]))
    users = [i for i, x in bl.items.items() if iid in x.get("depends_on", []) and x.get("status") != "dropped"]
    if users:
        raise Refused(f"{bl.label(iid)} is a dependency of " + ", ".join(bl.label(u) for u in users[:5]))
    if not bl.sprint_of(iid):
        label = bl.label(iid)
        for d in bl.descendants(iid):
            bl.delete(d)
        bl.delete(iid)
        say(f"dropped and deleted {label} (not in a sprint; git keeps it): {a.why}")
        return 0
    it.update(status="dropped", notes=(it.get("notes", "") + " Dropped: " + a.why).strip()[:TEXT_MAX])
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"dropped {bl.label(iid)}: {a.why}")
    return 0


def cmd_start(bl, a):
    sid = need(bl, a.sprint)
    sp = bl.items[sid]
    if sp.get("kind") != "sprint":
        raise Refused(f"{bl.label(sid)} is not a sprint")
    g = next(g for g in sp["gates"] if g["id"] == START_GATE)
    if g.get("by") != "operator" or str(g.get("answer", "")).lower() not in ("approve", "approved", "yes"):
        raise Refused(f"{bl.label(sid)}: the operator has not approved it (gate {START_GATE}: {g.get('answer', 'open')})")
    items = bl.sprint_items(sid)
    if len(items) < 2:
        raise Refused(f"{bl.label(sid)} commits to no item besides its review")
    for i in items:
        if bl.items[i].get("status") == "draft":
            bl.items[i]["status"] = "todo"
            bl.save(bl.items[i])
    sp["status"] = "active"
    bl.save(sp)
    say(f"started {bl.label(sid)}: {sp['goal']}")
    return 0


def cmd_close(bl, a):
    sid = need(bl, a.sprint)
    items = bl.sprint_items(sid)
    left = [i for i in items if bl.items[i].get("status") not in ("done", "dropped")]
    if left:
        raise Refused(f"{bl.label(sid)} is not finished:\n  " + "\n  ".join(line(bl, i) for i in left))
    gone = set(items)
    epics = {p for i in items for p in bl.ancestors(i) if bl.items[p].get("kind") == "epic"}
    for e in epics:
        rest = [c for c in bl.descendants(e) if c not in gone]
        if bl.items[e].get("status") == "done" and not rest:
            gone.add(e)
    for i in gone:
        say(f"deleted {line(bl, i)}")
    for i in gone:
        bl.delete(i)
    label = bl.label(sid)
    bl.delete(sid)
    say(f"closed {label}; its items stay in git history (git log --grep 'KB-Work: <id>')")
    return 0


def horizon(bl, sid):
    """(reachable open ids, {cause: [stuck ids]}, critical path [ids], level widths) for a sprint."""
    items = [i for i in bl.sprint_items(sid) if bl.items[i].get("status") not in ("done", "dropped")]
    cause = {}
    if bl.items[sid].get("status") != "active":
        g = next((g for g in bl.items[sid].get("gates", []) if g.get("id") == START_GATE), {})
        cause = {i: f"the sprint's start gate: {g.get('question', 'not started')}" for i in items}
    for i in items:
        for x in [i] + bl.ancestors(i):
            it = bl.items[x]
            for g in open_gates(it):
                cause[i] = f"gate {x}/{g['id']} ({bl.items[x]['title']}): {g['question']}" + (
                    f" [recommended: {g['recommendation']}]" if g.get("recommendation") else "")
            if it.get("trigger") and not it["trigger"].get("fired"):
                cause[i] = f"trigger on {bl.label(x)}: {it['trigger']['when']}"
        for d in bl.items[i].get("depends_on", []):
            if d not in items and bl.items.get(d, {}).get("status") != "done":
                cause[i] = f"outside this sprint: {bl.label(d)}"
    # propagate: an item waits on what its dependencies, children and (for the review) the sprint wait on
    edges = {i: [d for d in bl.items[i].get("depends_on", []) if d in items]
             + [c for c in bl.children(i) if c in items] for i in items}
    for i in items:
        if bl.items[i].get("review"):
            edges[i] += [s for s in items if s != i and bl.items[s].get("kind") in IN_SPRINT]
    changed = True
    while changed:
        changed = False
        for i in items:
            if i not in cause:
                src = next((cause[d] for d in edges[i] if d in cause), None)
                if src:
                    cause[i], changed = src, True
    reach = [i for i in items if i not in cause]
    depth = {}

    def d(i, seen=()):
        if i not in depth:
            depth[i] = 1 + max((d(x, seen + (i,)) for x in edges[i] if x in reach and x not in seen), default=0)
        return depth[i]

    for i in reach:
        d(i)
    path = []
    if reach:
        cur = max(reach, key=lambda i: (depth[i], i))
        while cur:
            path.append(cur)
            nxt = [x for x in edges[cur] if x in reach and depth.get(x) == depth[cur] - 1]
            cur = min(nxt) if nxt else None
    widths = [sum(1 for i in reach if depth[i] == k) for k in range(1, (max(depth.values()) if depth else 0) + 1)]
    by_cause = {}
    for i, c in cause.items():
        by_cause.setdefault(c, []).append(i)
    return reach, by_cause, list(reversed(path)), widths


def cmd_horizon(bl, a):
    sprints = [a.sprint] if a.sprint else sorted(i for i, it in bl.items.items()
                                                  if it.get("kind") == "sprint" and it.get("status") == "active")
    lines = []
    if not sprints:
        planned = [i for i, it in bl.items.items() if it.get("kind") == "sprint"]
        n = sum(1 for it in bl.items.values() if it.get("kind") != "sprint" and it.get("status") not in ("done", "dropped"))
        lines.append(f"backlog: no active sprint; {n} open item(s)"
                     + (", planned: " + ", ".join(bl.label(s) for s in planned) if planned else "")
                     + " (python3 _tools/backlog.py tree)")
    for sid in sprints:
        need(bl, sid)
        items = bl.sprint_items(sid)
        done = sum(1 for i in items if bl.items[i].get("status") in ("done", "dropped"))
        reach, stuck, path, widths = horizon(bl, sid)
        lines.append(f"sprint {bl.label(sid)} [{bl.items[sid].get('status')}]: goal {bl.items[sid].get('goal')}")
        lines.append(f"  {done}/{len(items)} done; {len(reach)} more reachable without the operator; "
                     f"{sum(map(len, stuck.values()))} wait on the operator or a trigger")
        nxt = ready(bl, sid)
        if nxt:
            lines.append(f"  next: {bl.label(nxt[0])}")
        if path:
            lines.append(f"  critical path ({len(path)} steps, parallel width per step {widths}): "
                         + " -> ".join(bl.label(i) for i in path))
        for c, ids in stuck.items():
            lines.append(f"  waiting on {c}")
            for i in ids[:5 if a.hook else 50]:
                lines.append(f"    {bl.label(i)}")
    text = "\n".join(lines)
    if a.hook:
        print(json.dumps({"systemMessage": text, "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text + "\nThe backlog runbook is kb/_self/backlog.md."}}, ensure_ascii=False))
    else:
        say(text)
    return 0


GITLAB_FINISHED = ("success", "failed", "canceled", "skipped")
GATE_JOBS = ("kb-tests",)  # a red one means the gate every push runs fails on main itself: S1; any other job: S2
STATUS_REPRO = ["python3", "_tools/backlog.py", "red-pipeline", "--status"]


def run(argv, cwd=None):
    """(exit code, stdout, stderr) of a command given as an argument list (git, glab, gh); 127 when it cannot start."""
    from ql_base import run_cmd
    return run_cmd(argv, cwd=cwd, timeout=60)


def latest_pipeline(root):
    """(pipeline, note): the newest finished pipeline of origin's main as {id, sha, url, red, jobs}, or None with the
    note that says why not (no origin, glab or gh not signed in, a failed call, no finished pipeline)."""
    from ql_deliver import GITHUB_RED, forge_list, origin_forge
    code, url, _ = run(["git", "remote", "get-url", "origin"], cwd=root)
    if code:
        return None, "no origin remote"
    url = url.strip()
    forge, host, project = origin_forge(url)
    data, cli, note = forge_list(
        url, run, lambda repo: ["gh", "run", "list", "--branch", "main", "-R", repo, "--json",
                                "databaseId,headSha,status,conclusion,url", "-L", "30"],
        lambda p: f"projects/{p}/pipelines?ref=main&per_page=30", named=3)
    if data is None:
        return None, note
    for r in data:
        if not isinstance(r, dict):
            continue
        if forge == "github":
            if r.get("status") != "completed":
                continue
            p = {"id": r.get("databaseId"), "sha": r.get("headSha"), "url": r.get("url"),
                 "red": r.get("conclusion") in GITHUB_RED}
        else:
            if r.get("status") not in GITLAB_FINISHED:
                continue
            p = {"id": r.get("id"), "sha": r.get("sha"), "url": r.get("web_url"), "red": r.get("status") == "failed"}
        p["jobs"] = []
        if p["red"]:
            if forge == "github":
                code, o, _ = run(["gh", "run", "view", str(p["id"]), "-R", f"{host}/{project}", "--json", "jobs"])
                key, bad = "jobs", ("failure", "timed_out", "startup_failure")
                field = "conclusion"
            else:
                quoted = project.replace("/", "%2F")
                code, o, _ = run(["glab", "api", "--hostname", host,
                                  f"projects/{quoted}/pipelines/{p['id']}/jobs?scope=failed&per_page=100"])
                key, bad, field = None, ("failed",), "status"
            try:
                js = json.loads(o) if code == 0 else []
                js = js.get(key, []) if key and isinstance(js, dict) else js
                p["jobs"] = [j["name"] for j in js if isinstance(j, dict) and j.get(field) in bad and j.get("name")]
            except ValueError:
                pass
        return p, note
    return None, f"no finished pipeline of main on {host} ({cli})"


def covered_by_revert(root, sha):
    """True when an automatic revert (KB-Auto: revert) on origin/main reverts the automatic push that `sha` ends;
    None when the history cannot be read. The revert commit names the first commit of that push."""
    code, o, _ = run(["git", "log", f"{sha}..origin/main", "--format=%B%x1e"], cwd=root)
    if code:
        return None
    for body in o.split("\x1e"):
        m = re.search(r"^This reverts commit ([0-9a-f]{40})\b", body, re.M)
        if not m or "KB-Auto: revert" not in body:
            continue
        first = m.group(1)
        if sha == first:
            return True
        code, o2, _ = run(["git", "log", f"{first}..{sha}", "--format=%(trailers:key=KB-Auto,valueonly)%x1e"], cwd=root)
        recs = o2.split("\x1e")[:-1] if code == 0 else []
        if code == 0 and all(r.strip() for r in recs):
            return True
    return False


def red_bug(pid, sha, sev, jobs=(), url=None, extra=""):
    """A red-main bug item (not saved): it names `pipeline PID` (the marker red-pipeline files by), its repro is
    the status of main's latest finished pipeline, and `extra` closes its notes."""
    marker = f"pipeline {pid}"
    return {"id": new_id("bug"), "kind": "bug",
            "title": f"Red main {marker}: {', '.join(jobs) or 'no failed job read'}"[:200],
            "status": "draft", "priority": "P1" if sev == "S1" else "P2", "rank": 0, "severity": sev,
            "goal": f"The latest finished pipeline of main is green: `{' '.join(STATUS_REPRO)}` exits 0.",
            "repro": {"run": list(STATUS_REPRO)},
            "notes": (f"{marker.capitalize()} of commit {str(sha)[:12]} failed"
                      + (f" in {', '.join(jobs)}" if jobs else "") + (f": {url}" if url else "") + "."
                      + (" " + extra if extra else ""))[:TEXT_MAX]}


def cmd_red_pipeline(bl, a):
    if not a.status:
        run(["git", "fetch", "-q", "origin", "main"], cwd=bl.root)
    p, note = latest_pipeline(bl.root)
    if p is None:
        say(f"red-pipeline: not checked: {note}")
        return 1 if a.status else 0
    if a.status:
        say(f"red-pipeline: latest finished pipeline {p['id']} of main is {'red' if p['red'] else 'green'} ({note})")
        return 1 if p["red"] else 0
    if not p["red"]:
        say(f"red-pipeline: latest finished pipeline {p['id']} of main is green: nothing to file")
        return 0
    marker = f"pipeline {p['id']}"
    for iid, it in bl.items.items():
        if re.search(rf"\b{re.escape(marker)}\b", " ".join(str(it.get(f, "")) for f in ("title", "goal", "notes"))):
            say(f"red-pipeline: {marker} already filed as {bl.label(iid)}")
            return 0
    if covered_by_revert(bl.root, p["sha"]) is not False:
        say(f"red-pipeline: {marker} is covered by an automatic revert (or its history is unreadable): nothing to file")
        return 0
    jobs = p["jobs"]
    sev = "S1" if any(j in GATE_JOBS for j in jobs) else "S2"
    active = [i for i, it in bl.items.items() if it.get("kind") == "sprint" and it.get("status") == "active"]
    it = red_bug(p["id"], p["sha"], sev, jobs, p.get("url"))
    if sev == "S1" and len(active) == 1:
        it.update(sprint=active[0], status="todo")
    ok, code, _ = run_check(bl.root, it["repro"])
    if ok:
        say(f"red-pipeline: {marker} is green on a second read (repro exit {code}): nothing to file")
        return 0
    bl.save(it)
    say(f"red-pipeline: new bug {bl.label(it['id'])}")
    return 0


def cmd_goal(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    parts = [f"{bl.label(iid)} is done: {it.get('goal', it['title'])}"]
    for c in it.get("checks", []) + ([it["repro"]] if it.get("repro") else []):
        parts.append(f"`{shlex.join(c['run'])}` exits {c.get('exit', 0)}"
                     + (f" with output matching {c['match']!r}" if c.get("match") else ""))
    parts.append(f"`python3 _tools/backlog.py done {iid}` exits 0 and its output is shown")
    globs = scope(bl, iid)
    if globs:
        parts.append("no commit for it changes a file outside " + ", ".join(globs))
    say(", ".join(parts) + ", or stop after 60 turns")
    return 0


def need(bl, iid):
    if iid not in bl.items:
        raise KeyError(iid)
    return iid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=str(ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("kind", choices=list(KINDS))
    p.add_argument("--title", required=True)
    p.add_argument("--parent")
    p.add_argument("--sprint")
    p.add_argument("--priority", choices=PRIORITIES, default="P2")
    p.add_argument("--rank", type=int, default=0)
    p.add_argument("--goal")
    p.add_argument("--severity", choices=SEVERITIES)
    p.add_argument("--check", action="append")
    p.add_argument("--touch", action="append")
    p.add_argument("--depends", action="append")
    p.add_argument("--repro")
    sub.add_parser("check")
    sub.add_parser("fmt")
    p = sub.add_parser("list")
    p.add_argument("--kind", choices=list(KINDS))
    p.add_argument("--status")
    p.add_argument("--sprint")
    p = sub.add_parser("tree")
    p.add_argument("id", nargs="?")
    p.add_argument("--sprint")
    p = sub.add_parser("show")
    p.add_argument("id")
    p = sub.add_parser("next")
    p.add_argument("--sprint")
    p.add_argument("--any", action="store_true")
    p.add_argument("--all", action="store_true")
    p = sub.add_parser("claim")
    p.add_argument("id")
    p.add_argument("--by", required=True)
    p = sub.add_parser("release")
    p.add_argument("id")
    p = sub.add_parser("answer")
    p.add_argument("id")
    p.add_argument("gate")
    p.add_argument("--answer")
    p.add_argument("--by", choices=("operator", "agent"))
    p.add_argument("--provisional", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p = sub.add_parser("fire")
    p.add_argument("id")
    p = sub.add_parser("done")
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("drop")
    p.add_argument("id")
    p.add_argument("--why", required=True)
    p = sub.add_parser("start")
    p.add_argument("sprint")
    p = sub.add_parser("close")
    p.add_argument("sprint")
    p = sub.add_parser("horizon")
    p.add_argument("--sprint")
    p.add_argument("--hook", action="store_true")
    p = sub.add_parser("goal")
    p.add_argument("id")
    p = sub.add_parser("red-pipeline")
    p.add_argument("--status", action="store_true")
    p.add_argument("--hook", action="store_true")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):  # refusals go to stderr; on Windows a pipe defaults to the ANSI code page
        s.reconfigure(encoding="utf-8")
    if a.cmd == "red-pipeline" and a.hook:  # async SessionStart: files a bug at most, prints nothing, never fails
        try:
            cmd_red_pipeline(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            pass
        return 0
    if a.cmd == "horizon" and a.hook:  # the SessionStart event on stdin carries nothing the horizon needs
        try:
            return cmd_horizon(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            return 0
    bl = Backlog(a.root)
    try:
        return globals()["cmd_" + a.cmd.replace("-", "_")](bl, a)
    except KeyError as e:
        print(f"no item {e.args[0]}", file=sys.stderr)
        return 2
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
