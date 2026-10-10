"""The shared ground of backlog.py's modules (kb/_self/backlog.md): the project settings (`SETTINGS`, read once from
backlog.json by `read_settings`, with the kb's current values as the defaults, for the root the process runs on:
`load_settings`) and the accessors that give them at call time (`setting`, `rel_dir`, `kinds`, `id_re`, ...), the
two refusals, the Backlog class that reads and writes the item files, git, the claims ledger's path (`claims_ledger`)
and the command runner, the scope helpers,
the host and user name guard behind everything the tool prints, the external tracker id helpers (`external_problems`,
`external_refs`, `external_lines`, `external_trailers`, `external_description`), the helpers that commit the item files a
command wrote, and what an item waits on (`waits`, `open_gates`) with the one-line `line` that names it. Standard library only;
backlog.py and the bl_ modules import it, and it imports no bl_ module at load and never backlog (`run`
reaches bl_intake.run_argv by an import in the function, so a caller that patches the reader is heard).
"""
import base64, copy, functools, getpass, json, os, re, secrets, socket, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ project settings

CONFIG_NAME = "backlog.json"  # at the repository root
CONFIG_ENV = "KB_BACKLOG_CONFIG"  # a path in the environment: read from there instead of the root's file
KIND_NAMES = ("epic", "story", "task", "subtask", "bug", "sprint")
TRACKER_NAME_RE = re.compile(r"[a-z][a-z0-9_-]*")  # a tracker's name in backlog.json's trackers and an item's external
# One place lists the settings: key -> (type, the kb's current value). A type is a TYPES name; a key not here is refused
# in backlog.json, and a key the file leaves out takes its value from here.
SETTINGS = {
    "item_dir": ("path", "kb/_self/backlog"),  # the item files, under the root
    "id_prefixes": ("prefixes", {"epic": "EP", "story": "ST", "task": "TK", "subtask": "SB", "bug": "BG",
                                 "sprint": "SP"}),
    "always_in_scope": ("strs", ["kb/_self/backlog/**", "kb/*/_coverage.csv", "kb/*/_coverage.md"]),  # any item's
    "review_checks": ("checks", [{"run": ["python3", "_tools/backlog.py", "check"]},
                                 {"run": ["python3", "_tools/tests.py"]}]),  # the review story's, once
    "research_checks": ("checks", [{"run": ["python3", "_tools/backlog.py", "researched", "{id}"]}]),  # `{id}`: the story
    "land_stale": ("argv", ["_tools/selfdoc.py", "stale", "--since"]),  # + the integration main; [] = no such step
    "land_eval": ("argv", ["_tools/rag.py", "eval"]),
    "land_lint": ("argv", [".claude/skills/kb-verify/lint.py"]),
    "lane_module": ("module", "kblane"),  # the module that says which lane a path belongs to
    "worktree_dir": ("path", ".claude/worktrees"),  # a worker's worktrees, under the clone's main checkout
    "scratch_dir": ("path", "_cache/scratch"),  # + /<id>/: a worker's throwaway files and staging copies, under the clone's top
    "forge": ("forge", "gitlab"),  # the integration remote's forge: gitlab (read with glab) or github (read with gh)
    "forge_project": ("str", ""),  # the forge project of the integration remote; "" = read from the remote's URL
    # the external trackers an item's `external` ids may name: tracker -> {pattern, url, ref?}; {} = none accepted
    "trackers": ("trackers", {}),
    "docs_map": ("optpath", "kb/_self/map.csv"),  # a doc,pattern CSV: the docs a brief lists for an item's touches; "" = none
    "kb_root": ("rootname", "_self"),  # the kb root whose cited fact lines a brief carries; "" = the project is no root
    # the repositories of a multi-repository workspace: name -> checkout path under the workspace, which an item's
    # `repos` and `repos_if_needed` name; {} = the project is the one repository the root is
    "repositories": ("repositories", {}),
}
WORKSPACE_NAME = "workspace"  # the name the workspace's own files take in a touch, so no repository's


class ConfigError(Exception):
    """backlog.json (or the file KB_BACKLOG_CONFIG names) cannot be read or holds a key `read_settings` refuses."""


def _type_problem(kind, v):
    """Why V is no value of the settings type KIND (the type names SETTINGS uses), or None."""
    def strs(x):
        return isinstance(x, list) and all(isinstance(s, str) for s in x)
    if kind == "str":
        return None if isinstance(v, str) else "a string"
    if kind == "forge":
        return None if v in ("gitlab", "github") else '"gitlab" or "github"'
    if kind == "path":
        ok = isinstance(v, str) and v != "" and not v.startswith("/") and ".." not in v.split("/")
        return None if ok else "a non-empty path with forward slashes, relative to the root, with no `..`"
    if kind == "optpath":
        return None if v == "" or _type_problem("path", v) is None else \
            "a path with forward slashes, relative to the root, with no `..` (\"\" for none)"
    if kind == "rootname":
        ok = isinstance(v, str) and (v == "" or re.fullmatch(r"_?[a-z0-9][a-z0-9-]*", v) is not None)
        return None if ok else "a kb root's name: lower case letters, digits and hyphens, `_self` allowed (\"\" for none)"
    if kind == "module":
        return None if isinstance(v, str) and v.isidentifier() else "a Python module name"
    if kind == "strs":
        return None if strs(v) else "a list of strings"
    if kind == "argv":
        return None if strs(v) else "a list of strings (the command's arguments; [] for no step)"
    if kind == "checks":
        ok = isinstance(v, list) and all(
            isinstance(c, dict) and strs(c.get("run")) and c["run"] and set(c) <= {"run", "exit", "match"}
            and type(c.get("exit", 0)) is int and isinstance(c.get("match", ""), str) for c in v)
        return None if ok else 'a list of checks, each {"run": [argv], "exit": N, "match": REGEX} with a non-empty run'
    if kind == "prefixes":
        ok = (isinstance(v, dict) and set(v) == set(KIND_NAMES)
              and all(isinstance(p, str) and re.fullmatch(r"[A-Z]{2}", p) for p in v.values())
              and len(set(v.values())) == len(v))
        return None if ok else ("an object with one distinct two-capital-letter prefix for each of "
                                + ", ".join(KIND_NAMES))
    if kind == "repositories":
        ok = (isinstance(v, dict) and all(isinstance(n, str) and re.fullmatch(r"[a-z][a-z0-9_-]*", n)
                                          and n != WORKSPACE_NAME and _type_problem("path", p) is None
                                          for n, p in v.items())
              and len(set(v.values())) == len(v))
        return None if ok else ("an object of repository name (lower case letters, digits, hyphens and underscores, "
                                f"not {WORKSPACE_NAME!r}) to a distinct checkout path with forward slashes, relative "
                                "to the workspace, with no `..`")
    if kind == "trackers":
        def tracker_ok(name, t):
            if not (isinstance(name, str) and TRACKER_NAME_RE.fullmatch(name) and isinstance(t, dict)):
                return False
            if not {"pattern", "url"} <= set(t) <= {"pattern", "url", "ref"} or not all(
                    isinstance(x, str) and x for x in t.values()):
                return False
            ref = t.get("ref", "{id}")
            try:
                re.compile(t["pattern"])
            except re.error:
                return False
            return "{id}" in t["url"] and "{id}" in ref and re.search(r"\s", ref) is None
        ok = isinstance(v, dict) and all(tracker_ok(n, t) for n, t in v.items())
        return None if ok else ('an object of tracker name (lower case) to {"pattern": a regex the whole id matches, '
                                '"url": a template with {id}, "ref": an optional template with {id} and no space}')
    raise ValueError(f"unknown settings type {kind!r}")


def config_path(root, env=None):
    env = os.environ if env is None else env
    given = env.get(CONFIG_ENV)
    return Path(given) if given else Path(root) / CONFIG_NAME


def read_settings(root, env=None):
    """(values, sources, path, problems): the effective project settings of the repository at ROOT. Each key of
    SETTINGS takes the file's value (source "file") or the kb's own (source "default"); a key the file holds wrongly
    keeps its default and gives a problem naming it. No file at the root is no problem (all defaults); a
    KB_BACKLOG_CONFIG that names no file is."""
    env = os.environ if env is None else env
    path = config_path(root, env)
    values = {k: copy.deepcopy(d) for k, (_, d) in SETTINGS.items()}
    sources = dict.fromkeys(SETTINGS, "default")
    problems = []
    named = path.name if path.parent == Path(root) else str(path)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not a JSON object")
        except (OSError, ValueError) as e:  # json.JSONDecodeError is a ValueError
            data, problems = {}, [f"{named}: {e}"]
        for k, v in data.items():
            if k not in SETTINGS:
                problems.append(f"{named}: unknown key {k!r} (keys: {', '.join(SETTINGS)})")
                continue
            why = _type_problem(SETTINGS[k][0], v)
            if why:
                problems.append(f"{named}: key {k!r} must be {why}")
                continue
            values[k], sources[k] = v, "file"
    elif env.get(CONFIG_ENV):
        problems.append(f"{CONFIG_ENV} names {path}, which is no file")
    return values, sources, path, problems


_LOADED = []  # [read_settings(root)] of the root this process runs on; empty until load_settings or a first read


def load_settings(root, env=None):
    """Read the project settings of the repository at ROOT (its backlog.json, or KB_BACKLOG_CONFIG's file) for the
    rest of this process: `backlog.main` calls it once, with the root the command runs on, before it builds the
    parser, so every reader below follows that root and not the tool's own clone. Returns read_settings' tuple."""
    _LOADED[:] = [read_settings(root, env)]
    return _LOADED[0]


def setting(name):
    """The effective value of one project setting of the root the process runs on (load_settings; the tool's own
    root's until then): the one function the other modules read a setting through, at call time, never at import."""
    if not _LOADED:
        load_settings(ROOT)
    return copy.deepcopy(_LOADED[0][0][name])


def rel_dir():
    """The item files' directory under the root (`item_dir`)."""
    return setting("item_dir")


def kinds():
    """{kind: two-letter id prefix} of the project, in KIND_NAMES order."""
    prefixes = setting("id_prefixes")
    return {k: prefixes[k] for k in KIND_NAMES}


def prefix_kind():
    return {v: k for k, v in kinds().items()}


def id_re():
    """The pattern an item id of this project matches, word-bounded."""
    return re.compile(r"\b(?:" + "|".join(kinds().values()) + r")-[a-z2-7]{8}\b")


def sprint_id_re():
    return re.compile(kinds()["sprint"] + r"-[a-z2-7]{8}")


def always_in_scope():
    """The globs any item's commits may change besides its `touches`: the tracker itself and what build_index.py
    regenerates."""
    return tuple(setting("always_in_scope"))


def worker_dir():
    """The worker worktrees' directory under the clone's main checkout (`worktree_dir`), as path parts."""
    return tuple(setting("worktree_dir").split("/"))


def scratch_dir():
    """The workers' scratch directory under the clone's top (`scratch_dir`), as path parts."""
    return tuple(setting("scratch_dir").split("/"))


def repositories():
    """{name: checkout path} of the workspace's repositories (`repositories`); {} = the root is the one repository."""
    return setting("repositories")


def review_checks():
    """The review story's checks, run once before review."""
    return setting("review_checks")


def research_checks():
    """The goal research story's checks, with RESEARCH_ID in place of its id (`new sprint` fills it)."""
    return setting("research_checks")

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
         "repro", "repro_reason", "checks", "touches", "repos", "repos_if_needed", "depends_on", "relates_to", "gates", "trigger", "knowledge",
         "links", "external", "notes", "delegates", "recurs", "claimed_by", "evidence")
FIELDS = set(ORDER)
CHECK_TIMEOUT_S = 1800
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")  # colour and title codes a check prints
TEXT_MAX = 2000  # one field's text; a longer one is an essay, not a work item
START_GATE = "start"
APPROVALS = ("approve", "approved", "yes")  # the start gate's answers that let backlog.py start run
# horizon's cause for the items of a sprint the operator approved but nobody started: backlog.py start is what remains,
# not a question for the operator (a "change" or "cancel" answer is no approval and stays the operator's question)
STARTS = "the sprint's start: approved, not started; run python3 _tools/backlog.py start "
OPEN = ("draft", "todo", "doing")
# similar and new: an open item whose title and goal hold at least SIMILAR_MIN of the query's words, and at least
# SIMILAR_WORDS of them, is a near-duplicate; words are lowercased runs of letters and digits, stop words left out
SIMILAR_MIN = 0.6
SIMILAR_WORDS = 2
SIMILAR_SHOWN = 10
STOP_WORDS = frozenset("""a an and are as at be by for from has have in into is it its of on or that the their them
    then there these this those to was were what when which with without""".split())
RECURRING_MIN = 2  # start: an open P1 item with this many sprint ids in its recurs list belongs in the sprint
# the goal research story's checks (setting research_checks): its research is written (a work commit naming it, or its
# notes' `No outside facts:`), so it fails until then; `new sprint` fills RESEARCH_ID with the story's id
RESEARCH_ID = "{id}"


class Refused(Exception):
    pass


class Rejected(Refused):
    """A refusal that exits 2: `set`, `gate add` and `new` (a text-only repro with no reason, `--sprint` on a task or
    subtask) could not do what was asked."""


# ------------------------------------------------------------------ storage

def new_id(kind):
    return kinds()[kind] + "-" + base64.b32encode(secrets.token_bytes(5)).decode().lower()


def canonical(item):
    keys = [k for k in ORDER if k in item] + sorted(k for k in item if k not in FIELDS)
    return json.dumps({k: item[k] for k in keys}, ensure_ascii=False, indent=2) + "\n"


class Backlog:
    def __init__(self, root):
        self.root = Path(root)
        self.dir = self.root / rel_dir()
        self.items, self.raw, self.load_errors = {}, {}, []
        self.withheld = set()  # items holding a piece of a host or user name: label() never prints their title
        self.written = []  # repository paths of the item files this run wrote or deleted, first first (--commit)
        self.load_errors += read_settings(self.root)[3]  # a backlog.json `check` refuses naming its key
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
        rel = f"{rel_dir()}/{iid}.json"
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
# host or person, and matching it would refuse ordinary text. A name whose every part is one of them (gitlab-runner,
# the shell executor's account; ContainerAdministrator and ContainerUser, a Windows container's) gives no piece.
GENERIC_NAMES = frozenset("""
    admin administrator agent build builder buildkite circleci codespace codespaces computer concurrent container
    default desktop developer docker github gitlab guest instance jenkins laptop local localhost owner project public
    runner runneradmin server service system tester travis ubuntu user users vagrant vscode windows workstation
""".split())
NAME_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z0-9]+")  # CamelCase parts; digits stay on
# The random suffix Kubernetes adds to a pod's name (generateName: five characters of an alphabet without vowels
# or 0, 1 and 3), which a CI job's host name ends in: it differs on every run and names no one host.
POD_SUFFIX = re.compile(r"-([bcdfghjklmnpqrstvwxz2456789]{5})$")


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
    without the number (`johnsm~`: a TEMP path's `JOHNSM~1` profile folder). A name made only of GENERIC_NAMES parts
    gives none, and a Kubernetes pod's random suffix (POD_SUFFIX) is no piece of its own."""
    toks = [t for t in re.split(r"[^0-9A-Za-z]+", name) if t]
    if toks and all(t.lower() in GENERIC_NAMES or all(x.lower() in GENERIC_NAMES for x in NAME_PART.findall(t))
                    for t in toks):
        return set()  # gitlab-runner, ContainerAdministrator: the name every such machine has
    pod = POD_SUFFIX.search(name)
    bare = re.sub(r"[^0-9A-Za-z]", "", name).lower()
    cands = {name.lower(), bare}
    if len(bare) > 8 and not any(g.startswith(bare[:6]) for g in GENERIC_NAMES):
        cands.add(bare[:6] + "~")
    for tok in re.split(r"[^0-9A-Za-z]+", name):
        cands.add(tok.lower())
        cands.update(x.lower() for x in NAME_PART.findall(tok))
    if pod:
        cands.discard(pod.group(1))  # a pod's random suffix: the whole name still counts
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
    """The project's own repository paths, lower case, from the git remotes' URLs (a URL, or the scp-like
    `[user@]host:path` with or without a user): `namespace/project` and its URL-encoded `namespace%2fproject`. An item
    may spell them although the namespace can be a user's name. git's output is read as UTF-8 with replacement."""
    try:
        r = subprocess.run(["git", "-C", str(root), "remote", "-v"], capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")  # a non-ASCII remote never crashes the read
    except (OSError, subprocess.SubprocessError):
        return set()
    out = set()
    for url in {line.split()[1] for line in r.stdout.splitlines() if len(line.split()) >= 2}:
        # a URL, or git's scp-like [user@]host:path, the user optional, recognized only with no slash before the
        # first colon (kb: gitlab/git-test-repositories); a one-letter host is a Windows drive, not a remote
        m = re.match(r"(?:[a-z+]+://(?:[^@/]+@)?[^/]+/|(?:[^@/:]+@)?[^@:/]{2,}:)(.+?)(?:\.git)?/?$", url, re.I)
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


CLAIMS_LEDGER = "kb-backlog-claims.json"  # in the git dir: the claims made in this working tree


def claims_ledger(root):
    """(top, ledger) of the working tree at ROOT: its git toplevel and the path of its claims ledger, a file in its own
    git dir, which git never commits (`claim` writes it, `dispatch` adds the worker's pid and session to a record).
    Where git cannot say (no repository): (str(root), None)."""
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel", "--absolute-git-dir"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    rev = p.stdout.split("\n")
    if len(rev) < 2 or not rev[1]:
        return str(root), None
    return rev[0], Path(rev[1]) / CLAIMS_LEDGER


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
    return any(glob_re(g).match(path) for g in list(globs) + list(always_in_scope()))


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
    base = rel_dir()
    return path.startswith(base + "/") and path.endswith(".json") and "/" not in path[len(base) + 1:]


def touches_overlap(a, b, files):
    """True when two touches globs can name one path: either, read as a path, matches the other (`_tools/**` and
    `_tools/x.py`), or a tracked file matches both (`_tools/*.py` and `_tools/back*`)."""
    ra, rb = glob_re(a), glob_re(b)
    return bool(ra.match(b) or rb.match(a) or any(ra.match(f) and rb.match(f) for f in files))


# ------------------------------------------------------------------ external tracker ids

REF_TRAILER = "KB-Ref"  # one commit trailer per external id, its value the tracker's ref form of the id
REF_VERBS = ("claim", "done")  # the --commit verbs whose commits carry the item's KB-Ref trailers
REF_HEADER = "Tracker references (KB-Ref):"  # the line that heads land's block in a merge request description


def external_problems(external, trackers=None):
    """[why] an item's `external` (tracker name -> list of ids) is refused against the project's TRACKERS (default:
    backlog.json's trackers key): not a map of lists, a tracker the file does not name (a project without a trackers
    key names none, so accepts none), an id that has a space or that the tracker's pattern does not match whole, or
    one listed twice. [] when it is sound."""
    trackers = setting("trackers") if trackers is None else trackers
    if not isinstance(external, dict) or not external:
        return ["external must be a map of tracker name to a list of ids (set ID --external TRACKER=ID)"]
    out = []
    for name, ids in external.items():
        if name not in trackers:
            named = ", ".join(sorted(trackers)) or "none: its trackers key is absent or empty"
            out.append(f"external names tracker {name!r}, which backlog.json does not name (it names {named})")
            continue
        if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x for x in ids):
            out.append(f"external {name}: ids must be a non-empty list of texts")
            continue
        pattern = trackers[name]["pattern"]
        for i, x in enumerate(ids):
            if x in ids[:i]:
                out.append(f"external {name}: id {x!r} is listed twice")
            elif re.search(r"\s", x) or re.fullmatch(pattern, x) is None:
                out.append(f"external {name}: id {x!r} does not match the tracker's pattern {pattern!r} "
                           f"(backlog.json, trackers.{name}.pattern)")
    return out


def external_refs(it, trackers=None):
    """[(tracker, id, ref, url)] for the external ids of an item: tracker names sorted, each one's ids in the order
    stored. `ref` is the form a commit trailer and a merge request description carry (the tracker's ref template, by
    default the id), `url` the tracker's url template filled in; an id of a tracker the file does not name has its
    id for ref and no url (`check` refuses it). Shapes `external_problems` refuses are skipped, never raised on."""
    trackers = setting("trackers") if trackers is None else trackers
    ext = it.get("external")
    out = []
    for name in sorted(ext) if isinstance(ext, dict) else ():
        t = trackers.get(name)
        for x in ext[name] if isinstance(ext[name], list) else ():
            if isinstance(x, str) and x:
                out.append((name, x, t.get("ref", "{id}").replace("{id}", x) if t else x,
                            t["url"].replace("{id}", x) if t else ""))
    return out


def external_lines(it, indent="", trackers=None):
    """One line for each external id of an item, `external TRACKER REF URL`: what `show` prints, and the helper the
    worker's brief calls for the item's tracker ids with their urls. [] for an item with none."""
    return [f"{indent}external {name} {ref}" + (f" {url}" if url else "")
            for name, _, ref, url in external_refs(it, trackers)]


def external_trailers(it, trackers=None):
    """[`KB-Ref: REF`] one for each distinct ref of an item's external ids, in external_refs' order: the trailer lines
    the claim and done commits carry (a Jira key anywhere in a commit message links the commit to the issue)."""
    refs = list(dict.fromkeys(ref for _, _, ref, _ in external_refs(it, trackers)))
    return [f"{REF_TRAILER}: {r}" for r in refs]


def external_description(it, trackers=None):
    """The block land writes into a merge request description: REF_HEADER, then `- TRACKER REF: URL` for each external
    id (no URL after a bare ref). It holds no closing keyword (a GitLab closing pattern, a Jira trigger word), so
    merging the request closes no issue. "" for an item with no external ids."""
    rows = external_refs(it, trackers)
    if not rows:
        return ""
    return "\n".join([REF_HEADER] + [f"- {name} {ref}" + (f": {url}" if url else "") for name, _, ref, url in rows])


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
    command's own, KB-Ref the item's external ids', the others are the commit-msg hook's)."""
    if not TRAILER_RE.fullmatch(t):
        return f"--trailer {t!r} is not one `Key: value` line"
    if t.split(":", 1)[0].strip().upper().startswith("KB-"):
        return (f"--trailer {t!r}: KB-* trailers are written by backlog.py (KB-Work, KB-Ref) and the commit-msg "
                "hook")
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
    refs = external_trailers(bl.items[iid]) if verb in REF_VERBS and iid in bl.items else []  # KB-Ref: one per id
    msg = commit_message(subject, ids or [iid], refs + list(getattr(a, "trailer", None) or ()),
                         withhold(body) if body else "")
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


def cmd_config(bl, a):
    """`config`: the effective project settings of the repository, one line each with its value and where it came
    from (file: backlog.json or the KB_BACKLOG_CONFIG file; default: the kb's own value). A file with a problem is
    refused, each problem naming its key (exit 2), and nothing is printed of the settings."""
    values, sources, path, problems = read_settings(bl.root)
    if problems:
        raise Rejected("\n".join(problems))
    shown = path.name if path.parent == Path(bl.root) else str(path)
    say(f"{shown}: " + ("read" if path.is_file() else "absent, every value is the default"))
    for k in SETTINGS:
        say(f"{k} = {json.dumps(values[k], ensure_ascii=False)}  ({sources[k]})")
    return 0


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


def colourless_env():
    """The environment with colour off: FORCE_COLOR (3 in a Claude Code background session) makes Python 3.13+
    colour its tracebacks and 3.14 argparse its usage errors, which would hide a repro's own error from own_failure
    and a check's output from its match."""
    env = {k: v for k, v in os.environ.items() if k not in ("FORCE_COLOR", "PYTHON_COLORS", "CLICOLOR_FORCE")}
    env["NO_COLOR"] = "1"
    return env


def main_worktree(root):
    """The checkout at ROOT, or the clone's main worktree when ROOT is a linked git worktree (its `.git` is a file
    naming `<common dir>/worktrees/<name>`): where kbfacts.index_dir keeps the clone's shared pack index (the
    clone_home of kbfacts and ql_base, which read kbcommon.HOME, not a path). A relative `gitdir:` (git worktree add
    --relative-paths) is relative to ROOT, not the working directory."""
    try:
        text = Path(root, ".git").read_text(encoding="utf-8").strip()
    except OSError:
        return str(root)
    if text.startswith("gitdir:"):
        gitdir = Path(os.path.normpath(Path(root, text[len("gitdir:"):].strip())))
        if gitdir.parent.name == "worktrees" and gitdir.parent.parent.name == ".git":
            return str(gitdir.parent.parent.parent)
    return str(root)


def check_env(root, home):
    """The environment of a check or a repro: colourless_env with an isolated query log home. CLAUDE_PLUGIN_DATA is
    HOME, a temporary directory whose querylog/config.json is mode local, and CLAUDE_PLUGIN_ROOT the clone at ROOT,
    which ql_base.plugin_data takes for this copy running as the plugin: capture still runs, into HOME, never into the
    clone's own spool. The pack index and the live-docs cache stay where the inherited environment keeps them (KB_INDEX,
    KB_DOCS_CACHE), not in HOME, which is deleted after the run: without them, the pack index is the clone's shared one
    (main_worktree's _cache/, as kbfacts.index_dir finds it from a linked worktree) and the live-docs cache ROOT's own
    _cache/live-docs (kb_mcp.docs_cache_dir). A check that sets its own CLAUDE_PLUGIN_DATA in its own code keeps it.
    KB_TEST_RUN_HOME names the query log directory this process would write to before the isolation (ql_base.places:
    the plugin data's, else the clone's own _cache/querylog, the main worktree's for a linked one), unless capture is
    off there: tests.py writes the `test.run` row of a run the check makes into that directory's spool, so the digest's
    ops block counts it; every other capture of the check stays in HOME. A value the environment already holds stays: a
    check that itself runs a check runs in an isolated home, and its run still names the clone's."""
    env = colourless_env()
    data = env.get("CLAUDE_PLUGIN_DATA")
    env["KB_INDEX"] = env.get("KB_INDEX") or data or os.path.join(main_worktree(root), "_cache")
    env["KB_DOCS_CACHE"] = env.get("KB_DOCS_CACHE") or os.path.join(data or os.path.join(root, "_cache"), "live-docs")
    if not env.get("KB_TEST_RUN_HOME"):
        import ql_base
        qdir, cfg = ql_base.places()
        if not ql_base.logging_off(qdir, cfg):
            env["KB_TEST_RUN_HOME"] = str(qdir)
    env["CLAUDE_PLUGIN_DATA"], env["CLAUDE_PLUGIN_ROOT"] = str(home), root
    return env


def run_check(root, c):
    """Run one check, or a bug's repro, without a shell and with colour off; its output comes back with any colour
    codes taken out. A check that names python3 or python runs with the interpreter running this tool: on a host
    whose python3 is the Windows Store alias, or none on PATH, it still proves the item. It runs with an isolated query
    log home (check_env), a fresh temporary directory removed afterwards, so no check or repro adds a row to the
    clone's own spool, except the `test.run` row of a tests.py run it makes (KB_TEST_RUN_HOME, check_env)."""
    argv = list(c["run"])
    if argv and argv[0] in ("python3", "python"):
        argv[0] = sys.executable
    with tempfile.TemporaryDirectory(prefix="kb-check-", ignore_cleanup_errors=True) as home:
        (Path(home) / "querylog").mkdir()
        (Path(home) / "querylog" / "config.json").write_text(json.dumps({"mode": "local"}), encoding="utf-8")
        try:
            p = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=CHECK_TIMEOUT_S, env=check_env(str(Path(root).resolve()), home))
            code, out = p.returncode, ANSI_RE.sub("", (p.stdout or "") + (p.stderr or ""))
        except OSError as e:
            code, out = None, f"cannot start: {e}"
        except subprocess.TimeoutExpired as e:
            code, out = None, str(e)
    ok = code == c.get("exit", 0) and (not c.get("match") or re.search(c["match"], out, re.M) is not None)
    return ok, code, out
