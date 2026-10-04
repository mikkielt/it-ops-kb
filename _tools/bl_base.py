"""The shared ground of backlog.py's modules (kb/_self/backlog.md): the constants, the two refusals, the Backlog class
that reads and writes the item files, git and the command runner, the scope helpers, the host and user name guard
behind everything the tool prints, the helpers that commit the item files a command wrote, and what an item waits on
(`waits`, `open_gates`) with the one-line `line` that names it. Standard library only;
backlog.py and the bl_ modules import it, and it imports no bl_ module at load and never backlog (`run`
reaches bl_intake.run_argv by an import in the function, so a caller that patches the reader is heard).
"""
import base64, functools, getpass, json, os, re, secrets, socket, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REL_DIR = "kb/_self/backlog"
KINDS = {"epic": "EP", "story": "ST", "task": "TK", "subtask": "SB", "bug": "BG", "sprint": "SP"}
PREFIX_KIND = {v: k for k, v in KINDS.items()}
ID_RE = re.compile(r"\b(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}\b")
STATUSES = ("draft", "todo", "doing", "done", "dropped")
WORKED = ("todo", "doing", "done")  # statuses an item of a planned sprint cannot have: it stays draft until start
SPRINT_STATUSES = ("planned", "active")
# a research item: a story, task or subtask whose touches (its own and its descendants') all lie inside one named kb
# root each (kb/public/**; never kb/_self/, _tools/, .claude/, .githooks/ or CI). In a planned sprint it may be claimed
# from draft, worked and done before the sprint starts (kb/_self/backlog.md, Sprints)
RESEARCH_KINDS = ("story", "task", "subtask")
KB_CONTENT_RE = re.compile(r"kb/[^/_*?\[\]][^/*?\[\]]*/.+")  # the root's name spelled out, no `..` (research_touches)
PRIORITIES = ("P1", "P2", "P3")
SEVERITIES = ("S1", "S2", "S3", "S4")
GATE_KINDS = ("blocking", "provisional")
PARENTS = {"epic": (), "story": ("epic",), "bug": ("epic",), "task": ("story", "bug"), "subtask": ("task",),
           "sprint": ()}
IN_SPRINT = ("story", "bug")  # the kinds a sprint commits to; their tasks and subtasks come with them
NEEDS_CHECKS = ("story", "bug", "task")
NEEDS_TOUCHES = ("task", "subtask")
ORDER = ("id", "kind", "title", "status", "parent", "sprint", "review", "goal_research", "priority", "rank", "severity", "goal",
         "repro", "repro_reason", "checks", "touches", "depends_on", "relates_to", "gates", "trigger", "knowledge",
         "links", "notes", "recurs", "claimed_by", "evidence")
FIELDS = set(ORDER)
# files any item's commits may change besides its `touches`: the tracker itself and what build_index.py regenerates
ALWAYS_IN_SCOPE = ("kb/_self/backlog/**", "kb/*/_coverage.csv", "kb/*/_coverage.md")
CHECK_TIMEOUT_S = 1800
TEXT_MAX = 2000  # one field's text; a longer one is an essay, not a work item
START_GATE = "start"
APPROVALS = ("approve", "approved", "yes")  # the start gate's answers that let backlog.py start run
# horizon's cause for the items of a sprint the operator approved but nobody started: backlog.py start is what remains,
# not a question for the operator (a "change" or "cancel" answer is no approval and stays the operator's question)
STARTS = "the sprint's start: approved, not started; run python3 _tools/backlog.py start "
SPRINT_ID_RE = re.compile(r"SP-[a-z2-7]{8}")
OPEN = ("draft", "todo", "doing")
# similar and new: an open item whose title and goal hold at least SIMILAR_MIN of the query's words, and at least
# SIMILAR_WORDS of them, is a near-duplicate; words are lowercased runs of letters and digits, stop words left out
SIMILAR_MIN = 0.6
SIMILAR_WORDS = 2
SIMILAR_SHOWN = 10
STOP_WORDS = frozenset("""a an and are as at be by for from has have in into is it its of on or that the their them
    then there these this those to was were what when which with without""".split())
RECURRING_MIN = 2  # start: an open P1 item with this many sprint ids in its recurs list belongs in the sprint
REVIEW_CHECKS = [{"run": ["python3", "_tools/backlog.py", "check"]}, {"run": ["python3", "_tools/tests.py"]}, {"run": ["python3", "_tools/stress_test.py"]}]  # once, before review
RESEARCH_CHECKS = [{"run": ["python3", "_tools/check.py"]}]  # the goal research story's: the kb it wrote passes the checks


class Refused(Exception):
    pass


class Rejected(Refused):
    """A refusal that exits 2: `set`, `gate add` and `new` (a text-only repro with no reason, `--sprint` on a task or
    subtask) could not do what was asked."""


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
        self.withheld = set()  # items holding a piece of a host or user name: label() never prints their title
        self.written = []  # repository paths of the item files this run wrote or deleted, first first (--commit)
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
        self.wrote(item["id"])

    def delete(self, iid):
        (self.dir / f"{iid}.json").unlink()
        self.items.pop(iid, None)
        self.wrote(iid)

    def wrote(self, iid):
        rel = f"{REL_DIR}/{iid}.json"
        if rel not in self.written:
            self.written.append(rel)

    def get(self, iid):
        if iid not in self.items:
            raise KeyError(iid)
        return self.items[iid]

    def label(self, iid):
        it = self.items.get(iid)
        if iid in self.withheld:
            return f"{iid} (title withheld: the item holds a host or user name)"
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


# ------------------------------------------------------------------ host and user names

# A backlog item is published with the repository, so it must not hold this host's computer name or the user's
# name (BG-477tasb3: checks written to keep the names out spelled pieces of them). The names are read from the
# environment at run time and never spelled in code, tests or docs, and no output prints a name or a piece of one.
HOST_ENV = ("COMPUTERNAME", "HOSTNAME")  # Windows, then the shells that export it
USER_ENV = ("USERNAME", "USER", "LOGNAME")
PROFILE_ENV = ("USERPROFILE", "HOME")  # the profile folder's name is the user's too (TEMP paths carry it)
# Names a CI runner, container or fresh install gives every machine (a GitLab runner is
# runner-<token>-project-<id>-concurrent-<n>, a Windows one DESKTOP-<serial>): a piece equal to one names no one
# host or person, and matching it would refuse ordinary text.
GENERIC_NAMES = frozenset("""
    admin administrator agent build builder buildkite circleci codespace codespaces computer concurrent container
    default desktop developer docker github gitlab guest instance jenkins laptop local localhost owner project public
    runner runneradmin server service system tester travis ubuntu users vagrant vscode windows workstation
""".split())
NAME_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z0-9]+")  # CamelCase parts; digits stay on


def host_user_names(env=None):
    """[(kind, name)]: this host's computer name and the user's name, from the environment's variables, the socket
    host name's first label, and getpass when no user variable is set."""
    env = os.environ if env is None else env
    out = [("host", env.get(k, "")) for k in HOST_ENV] + [("user", env.get(k, "")) for k in USER_ENV]
    try:
        out.append(("host", socket.gethostname().split(".")[0]))
    except OSError:
        pass
    if not any(env.get(k) for k in USER_ENV):
        try:
            out.append(("user", getpass.getuser()))
        except Exception:  # noqa: BLE001 - no user name found: nothing to guard
            pass
    out += [("user", re.split(r"[\\/]", env.get(k, "").rstrip("\\/"))[-1]) for k in PROFILE_ENV]
    return [(k, n.strip()) for k, n in out if n and n.strip()]


def name_piece_ok(piece):
    """A piece long enough to name one host or person rather than an ordinary word: a letter in it, not a generic
    name, and at least 5 characters, or 4 with a digit (a host serial such as `pc01`)."""
    return (re.search(r"[a-z]", piece) is not None and piece not in GENERIC_NAMES
            and (len(piece) >= 5 or (len(piece) == 4 and re.search(r"[0-9]", piece) is not None)))


def name_pieces(name):
    """The pieces of one name, lower case, kept by name_piece_ok: the whole name, it without separators, each part
    between non-alphanumerics and each CamelCase part of those (`JohnSmithCorp`: johnsmithcorp, john, smith;
    `ABC-PC01`: abc-pc01, abcpc01, pc01), and for a name of more than 8 letters and digits its Windows 8.3 short form
    without the number (`johnsm~`: a TEMP path's `JOHNSM~1` profile folder)."""
    bare = re.sub(r"[^0-9A-Za-z]", "", name).lower()
    cands = {name.lower(), bare}
    if len(bare) > 8 and not any(g.startswith(bare[:6]) for g in GENERIC_NAMES):
        cands.add(bare[:6] + "~")
    for tok in re.split(r"[^0-9A-Za-z]+", name):
        cands.add(tok.lower())
        cands.update(x.lower() for x in NAME_PART.findall(tok))
    return {c for c in cands if name_piece_ok(c)}


def host_user_pieces(env=None):
    """{piece: kind} over host_user_names; a piece of both names counts as the host's."""
    out = {}
    for kind, name in reversed(host_user_names(env)):
        for piece in name_pieces(name):
            out[piece] = kind
    return out


def _strings(v, path):
    """(field path, text) of every string in an item's JSON, keys included."""
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield path, k
            yield from _strings(x, f"{path}.{k}" if path else k)
    elif isinstance(v, list):
        for n, x in enumerate(v):
            yield from _strings(x, f"{path}[{n}]")


def project_paths(root):
    """The project's own repository paths, lower case, from the git remotes' URLs: `namespace/project` and its
    URL-encoded `namespace%2fproject`. An item may spell them although the namespace can be a user's name."""
    try:
        r = subprocess.run(["git", "-C", str(root), "remote", "-v"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return set()
    out = set()
    for url in {line.split()[1] for line in r.stdout.splitlines() if len(line.split()) >= 2}:
        m = re.match(r"(?:[a-z+]+://(?:[^@/]+@)?[^/]+/|[^@/:]+@[^:/]+:)(.+?)(?:\.git)?/?$", url, re.I)
        if m and "/" in m.group(1):
            path = m.group(1).lower()
            out |= {path, path.replace("/", "%2f")}
    return out


def items_holding_names(bl, pieces=None, exempt=None):
    """{id: [(field path, kind)]} of the items whose JSON holds a piece of this host's or user's name, matched
    case-insensitively anywhere in a string outside the project's own repository paths (`exempt`, by default
    project_paths)."""
    pieces = host_user_pieces() if pieces is None else pieces
    exempt = sorted(project_paths(bl.root) if exempt is None and pieces else exempt or (), key=len, reverse=True)
    found = {}
    for iid, it in bl.items.items() if pieces else ():
        for path, text in _strings(it, ""):
            low = text.lower()
            for e in exempt:
                low = low.replace(e, " ")
            for kind in sorted({k for p, k in pieces.items() if p in low}):
                hit = (path or "(a key)", kind)
                if hit not in found.get(iid, []):
                    found.setdefault(iid, []).append(hit)
    return found


def withhold_names(text, pieces, exempt=()):
    """The text with every piece of a host or user name replaced, longest first, outside the `exempt` paths."""
    if exempt:
        parts = re.split("(" + "|".join(re.escape(e) for e in sorted(exempt, key=len, reverse=True)) + ")", text,
                         flags=re.I)
        return "".join(x if n % 2 else withhold_names(x, pieces) for n, x in enumerate(parts))
    for p in sorted(pieces, key=len, reverse=True):
        text = re.sub(re.escape(p), "<name withheld>", text, flags=re.I)
    return text


# ------------------------------------------------------------------ git and scope

def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def main_worktree_spool(root):
    """The spool of the main worktree of the git common dir `root` belongs to, where a session started in the main
    checkout writes the rows of the clone it orchestrates: `_cache/querylog/spool` there. None when git cannot say."""
    try:
        common = (Path(root) / git(root, "rev-parse", "--git-common-dir").strip()).resolve()
    except (Refused, OSError):
        return None
    return common.parent / "_cache" / "querylog" / "spool"


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


def research_touches(touches):
    """True for touches that are kb content only: at least one, each a path or glob inside a named kb root
    (KB_CONTENT_RE). kbgit.py check-trailers reads an item's own touches with it."""
    return bool(touches) and all(isinstance(t, str) and KB_CONTENT_RE.fullmatch(t) and ".." not in t.split("/")
                                 for t in touches)


def research_story(bl, sid):
    """The id of sprint SID's goal research story (the story `new sprint` files with `goal_research: true`), or None."""
    return next((i for i in bl.sprint_items(sid) if bl.items[i].get("goal_research")), None)


def research_in_planned(bl, iid):
    """True for a research item (RESEARCH_KINDS, its scope all kb content) whose sprint is planned: claim takes it
    from draft, check accepts it doing or done, and done proves it, all before the sprint starts."""
    it = bl.items[iid]
    sp = bl.sprint_of(iid)
    return (it.get("kind") in RESEARCH_KINDS and research_touches(scope(bl, iid))
            and bl.items.get(sp, {}).get("status") == "planned")


def item_file(path):
    """True for a backlog item file (kb/_self/backlog/<id>.json): what a planning commit changes."""
    return path.startswith(REL_DIR + "/") and path.endswith(".json") and "/" not in path[len(REL_DIR) + 1:]


def touches_overlap(a, b, files):
    """True when two touches globs can name one path: either, read as a path, matches the other (`_tools/**` and
    `_tools/x.py`), or a tracked file matches both (`_tools/*.py` and `_tools/back*`)."""
    ra, rb = glob_re(a), glob_re(b)
    return bool(ra.match(b) or rb.match(a) or any(ra.match(f) and rb.match(f) for f in files))


# ------------------------------------------------------------------ output and commits

OUTPUT_ROOT = [ROOT]  # the backlog main() reads: its remotes give the paths withhold() leaves alone


@functools.lru_cache(maxsize=8)
def _project_paths_cached(root):
    return frozenset(project_paths(root))


def withhold(text):
    """Every line backlog.py prints goes through here: a piece of this host's or user's name, in an item's text or a
    command's output, is never printed (BG-6u645atm), outside the project's repository paths."""
    pieces = host_user_pieces()
    return withhold_names(str(text), pieces, _project_paths_cached(str(OUTPUT_ROOT[0]))) if pieces else str(text)


def say(line=""):
    print(withhold(line))


# --commit: claim, done, new, start and close commit the item files they wrote, and nothing else
COMMITS = ("claim", "done", "new", "start", "close")
TRAILER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*:[ \t]*\S[^\r\n]*\Z")


def trailer_problem(t):
    """Why a --trailer value is refused, or None: one `Key: value` line whose key is not a KB-* one (KB-Work is the
    command's own, the others are the commit-msg hook's)."""
    if not TRAILER_RE.fullmatch(t):
        return f"--trailer {t!r} is not one `Key: value` line"
    if t.split(":", 1)[0].strip().upper().startswith("KB-"):
        return f"--trailer {t!r}: KB-* trailers are written by backlog.py (KB-Work) and the commit-msg hook"
    return None


def commit_message(subject, ids, trailers=(), body=""):
    """The commit message: the fixed subject, an optional body, and a last paragraph of trailers with KB-Work first
    and the session's own after it (git reads trailers only in the last paragraph)."""
    parts = [subject]
    if body.strip():
        parts.append(body.strip())
    parts.append("\n".join([f"KB-Work: {', '.join(ids)}"] + [t.strip() for t in trailers]))
    return "\n\n".join(parts) + "\n"


def commit_written(bl, a, verb, iid, ids=None, body="", title=None):
    """With --commit: commit exactly the item files this run wrote or deleted (`git commit --only`, so changes staged
    before it stay staged and out of the commit), subject `chore(backlog): VERB ID "title"`, KB-Work: the ids."""
    if not getattr(a, "commit", False):
        return
    tracked = set(git(bl.root, "ls-files", "--", *bl.written).splitlines()) if bl.written else set()
    paths = [p for p in bl.written if p in tracked or (bl.root / p).exists()]  # not an untracked file it deleted
    if not paths:
        say("--commit: no item file written, nothing committed")
        return
    git(bl.root, "add", "-A", "--", *paths)
    if not git(bl.root, "status", "--porcelain", "--", *paths).strip():
        say("--commit: the item files are unchanged, nothing committed")
        return
    if title is None:
        title = bl.items.get(iid, {}).get("title", "")
    subject = withhold(f'chore(backlog): {verb} {iid} "{title}"' if title else f"chore(backlog): {verb} {iid}")
    msg = commit_message(subject, ids or [iid], getattr(a, "trailer", None) or (), withhold(body) if body else "")
    p = subprocess.run(["git", "commit", "-q", "-F", "-", "--only", "--", *paths], cwd=bl.root, input=msg,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise Refused(f"--commit: the item files are written but git commit failed: {(p.stderr or p.stdout).strip()}")
    say(f"committed {git(bl.root, 'rev-parse', '--short=10', 'HEAD').strip()} {subject} ({len(paths)} item file(s))")


def run(argv, cwd=None):
    """(exit code, stdout, stderr) of a command given as an argument list (git, glab, gh); 127 when it cannot start."""
    import bl_intake
    return bl_intake.run_argv(argv, cwd=cwd)


def need(bl, iid):
    if iid not in bl.items:
        raise KeyError(iid)
    return iid


# ------------------------------------------------------------------ readiness

def open_gates(it, kinds=("blocking",)):
    return [g for g in it.get("gates", []) if g.get("kind") in kinds and "answer" not in g]


def waits(bl, iid, any_sprint=False, by=None):
    """Why an item cannot be worked on now ([] = ready): its status, sprint, dependencies, gates, trigger, children.
    With `by`, a dependency that is `doing` and claimed by that session does not wait (`claim --by`: one session works
    both items in order)."""
    it = bl.items[iid]
    out = []
    if it.get("kind") in ("sprint", "epic"):
        return ["not a work item"]
    if it.get("status") not in ("todo", "doing"):
        out.append(f"status {it.get('status')}")
    sp = bl.sprint_of(iid)
    if not any_sprint and (not sp or bl.items.get(sp, {}).get("status") != "active"):
        out.append("not in an active sprint")
    for i in [iid] + bl.ancestors(iid):  # an ancestor's gates, trigger and dependencies hold its descendants too
        a = bl.items[i]
        for g in open_gates(a):
            out.append(f"gate {i}/{g['id']}: {g['question']}")
        t = a.get("trigger")
        if t and not t.get("fired"):
            out.append(f"trigger on {bl.label(i)}: {t['when']}")
        for d in a.get("depends_on", []):
            dep = bl.items.get(d, {})
            if dep.get("status") == "doing" and by is not None and dep.get("claimed_by") == by:
                continue
            if dep.get("status") != "done":
                out.append(f"depends on {bl.label(d)}" + (f" (through {bl.label(i)})" if i != iid else ""))
    if it.get("review"):
        for s in bl.sprint_items(sp):
            if s != iid and bl.items[s].get("kind") in IN_SPRINT and bl.items[s].get("status") not in ("done", "dropped"):
                out.append(f"review waits on {bl.label(s)}")
    open_children = [c for c in bl.children(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if open_children:
        out.append(f"{len(open_children)} open child item(s)")
    return out


def line(bl, iid):
    it = bl.items[iid]
    extra = f" {it['severity']}" if it.get("severity") else ""
    return f"{iid}  {it['kind']:<7} {it.get('status', ''):<7} {it.get('priority', ''):<2}{extra}  {it.get('title', '')}"
