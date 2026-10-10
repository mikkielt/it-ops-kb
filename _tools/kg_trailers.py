"""The trailers of kbgit.py (kb/_self/git.md, Commit trailers): the KB-* trailers a commit's change computes, their
application to a message (`kbgit.py trailers`), the audit of a range of commits (`check-trailers`, the pre-push hook and
sync's gate) and the work state of the KB-Work items a commit names (work_state). Runs git in KB, this module's own copy
of the repository directory (a caller may point it at a scratch clone). Standard library only; kbgit.py imports it, and
it imports no facade.
"""
import csv, datetime, io, json, os, re, subprocess

import build_index
import kbcommon
import kbid
import kbpublic
import kg_lane
import kg_merge
from kg_base import KB, Problem
from kg_merge import id_key, lf, strip_markers

KB_DIR_REL = kbcommon.repo_rel(kbcommon.KB_DIR)  # `kb`: the roots are the directories kb/<name>/


def git_run(*args, stdin=None):
    return kg_merge.git_run(*args, stdin=stdin, kb=KB)


def git(*args, stdin=None):
    return kg_merge.git(*args, stdin=stdin, kb=KB)


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


def root_of_path(path):
    """(root name, path in the root) of a repository path under kb/<name>/, else (None, None)."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == KB_DIR_REL and not parts[1].startswith(("_", ".")):
        return parts[1], "/".join(parts[2:])
    return None, None


# The last commit before KB-* trailers existed: it and its ancestors are exempt from check-trailers.
TRAILERS_SINCE = "e5dadde122a08111128e48eec9656c5d617ab631"
MAX_IDS = 40  # more values than this: "N ids (see diff)" instead of the list
KEYS = ("KB-Topics", "KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded", "KB-Answers")
VERIFIED = "KB-Verified"
AUTO = "KB-Auto"  # querylog.py's automatic commits (kb/_self/querylog.md, Delivery)
REF = "KB-Ref"  # an external tracker id of a backlog item (backlog.py claim and done --commit): one per line, one word
AUTO_VALUES = ("querylog", "eval", "alias", "expansion", "gap", "research", "revert")
WORK = kg_lane.WORK  # the backlog items a commit works on (kb/_self/backlog.md); written by the agent, never computed
WORK_ID = re.compile(r"(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}")
BACKLOG = "kb/_self/backlog"
WORK_LINE = re.compile(r"KB-Work\s*:\s*(.*\S)\s*$", re.I)
NOUN = {"KB-Topics": "topics", "KB-Answers": "answers"}
SUMMARY = re.compile(r"^(\d+) (?:ids|topics|answers) \(see diff\)$")
KEY_LINE = re.compile(r"^(" + "|".join(re.escape(k) for k in KEYS) + r")\s*:", re.I)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
INDEX = None  # compute() target: the index (staged changes)


def valid_date(s):
    if not DATE.fullmatch(s or ""):
        return False
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return False
    return True




def empty_tree():
    return (git("hash-object", "-t", "tree", "--stdin", stdin=b"") or "").strip()




def blob(rev, rel):
    """Text of rel at a commit, in the index (rev INDEX) or nowhere (rev "" = the empty tree): None when absent."""
    if rev == "":
        return None
    return git("cat-file", "blob", (":" if rev is INDEX else rev + ":") + "./" + rel)  # not `git show` (see show)


def changed_paths(base, target):
    """Paths that differ between base (a commit or the empty tree) and target (a commit, or INDEX)."""
    base = base or empty_tree()
    out = (git("diff-index", "--cached", "--name-only", "-z", base) if target is INDEX
           else git("diff-tree", "-r", "--name-only", "-z", base, target))
    if out is None:
        raise Problem(f"git diff {base[:12]} {'(index)' if target is INDEX else target[:12]} failed")
    return sorted(p for p in out.split("\0") if p)


def content_rel(path):
    """(root name, path in the root) of a repository path of a domain file (under kb/<root>/, in a directory not
    named `_*` or `.*`), else (None, None)."""
    name, rel = root_of_path(path)
    if rel and "/" in rel and not rel.split("/", 1)[0].startswith(("_", ".")):
        return name, rel
    return None, None


def is_content(path):
    """A repository path of a domain file of a root."""
    return content_rel(path)[0] is not None


def legacy_content_rel(path):
    """The path of a domain file in the flat layout before the kb moved (`intune/x.md` at the repository root), or
    None: history before the move is the public root's."""
    top = path.split("/", 1)[0]
    return path if "/" in path and not top.startswith(("_", ".")) and top != KB_DIR_REL else None


def topic_map(coverage_texts):
    """({file: {topic}}, [(dir/, topic)]) from _coverage.csv texts."""
    files, dirs = {}, []
    for t in coverage_texts:
        if not t:
            continue
        try:
            t = strip_markers(lf(t), kg_merge.COVERAGE)[0]
            rows = list(csv.DictReader(io.StringIO(t)))
        except (Problem, csv.Error):
            continue
        for r in rows:
            for f in (r.get("files") or "").split(";"):
                f = f.strip()
                if f.endswith("/"):
                    dirs.append((f, r.get("topic", "")))
                elif f:
                    files.setdefault(f, set()).add(r.get("topic", ""))
    return files, dirs


def source_rows_of(text):
    if not text:
        return {}
    try:
        text = strip_markers(lf(text), kg_merge.SOURCES)[0]
    except Problem:
        pass
    try:
        return {r["id"]: r for r in csv.DictReader(io.StringIO(text)) if r.get("id") and r["id"] != "id"}
    except csv.Error:
        return {}


def answer_sections(text):
    """{answer id: section text} of _answers.md."""
    out = {}
    for part in re.split(r"(?m)^(?=## )", text or ""):
        m = kbid.ANSWER_HEAD.match(part)
        if m:
            out[m.group(1)] = out.get(m.group(1), "") + part.rstrip() + "\n"
    return out


def trailers_from(paths, old, new):
    """{key: sorted values} for a change of `paths` (repository paths); old(rel)/new(rel) give a file's text
    before/after (None: absent). Every root under kb/ counts; topics are qualified (`public/intune/win32-apps`),
    source ids are bare (unique by their root's prefix), answer ids are `<root>:<id>` outside the public root. A
    commit from before the kb moved (a flat tree with `_sources.csv` at the top) is the public root's."""
    groups = {}  # root name -> (repository prefix of the root, [content paths in the root])
    for p in paths:
        name, rel = content_rel(p)
        if name:
            groups.setdefault(name, (f"{KB_DIR_REL}/{name}/", []))[1].append(rel)
    flat = new(kbcommon.SOURCES) is not None or old(kbcommon.SOURCES) is not None
    if flat:
        legacy = [r for r in map(legacy_content_rel, paths) if r]
        if legacy:
            groups.setdefault("public", ("", []))[1].extend(legacy)
    roots_touched = {n: pre for n, (pre, _) in groups.items()}
    for p in paths:
        name, rel = root_of_path(p)
        if name and rel in (kbcommon.SOURCES, kbcommon.ANSWERS):
            roots_touched.setdefault(name, f"{KB_DIR_REL}/{name}/")
        elif flat and p in (kbcommon.SOURCES, kbcommon.ANSWERS):
            roots_touched.setdefault("public", "")
    out = {}
    topics = set()
    for name, (pre, rels) in groups.items():
        files, dirs = topic_map([new(pre + kbcommon.COVERAGE_CSV), old(pre + kbcommon.COVERAGE_CSV)])
        for rel in rels:  # _coverage.csv names files relative to its root
            t = set(files.get(rel, ())) | {topic for d, topic in dirs if rel.startswith(d)}
            if not t and rel.endswith(".md"):
                fm = build_index.front_matter(lf(new(pre + rel) or old(pre + rel) or ""))
                if fm is not None:
                    t.add(rel[:-3])
            topics |= {f"{name}/{x}" for x in t if x}
    if topics:
        out["KB-Topics"] = sorted(topics)
    strip = lambda r: {k: v for k, v in r.items() if k != "used_in" and v}  # noqa: E731  (a new empty column is no edit)
    for name, pre in sorted(roots_touched.items()):
        src = pre + kbcommon.SOURCES
        if src in paths:
            a, b = source_rows_of(old(src)), source_rows_of(new(src))
            sup = {i for i in b if (b[i].get("superseded_by") or "").strip()
                   and not (a.get(i, {}).get("superseded_by") or "").strip() and i in a}
            out.setdefault("KB-Sources-Added", []).extend(set(b) - set(a))
            out.setdefault("KB-Sources-Superseded", []).extend(sup)
            out.setdefault("KB-Sources-Changed", []).extend(
                ({i for i in a if i in b and strip(a[i]) != strip(b[i])} - sup) | (set(a) - set(b)))
        ans = pre + kbcommon.ANSWERS
        if ans in paths:
            a, b = answer_sections(old(ans)), answer_sections(new(ans))
            q = "" if name == "public" else f"{name}:"
            out.setdefault("KB-Answers", []).extend(q + i for i in set(a) | set(b) if a.get(i) != b.get(i))
    for k in ("KB-Sources-Added", "KB-Sources-Superseded", "KB-Sources-Changed"):
        if k in out:
            out[k] = sorted(set(out[k]), key=id_key)
    if "KB-Answers" in out:
        out["KB-Answers"] = sorted(set(out["KB-Answers"]))
    return {k: out[k] for k in KEYS if out.get(k)}


def compute(base, target):
    """Trailers for base (commit sha, or "" for the empty tree) -> target (commit sha, or INDEX)."""
    return trailers_from(changed_paths(base, target), lambda rel: blob(base, rel), lambda rel: blob(target, rel))


def first_parent(rev):
    """The commit a commit's trailers are computed against: its first parent, or "" (empty tree) for a root."""
    parents = (git("rev-list", "--parents", "-n", "1", rev) or "").split()[1:]
    return parents[0] if parents else ""


def trailer_lines(computed, verified=None):
    out = []
    for k in KEYS:
        v = computed.get(k)
        if v:
            out.append(f"{k}: " + (", ".join(v) if len(v) <= MAX_IDS else f"{len(v)} {NOUN.get(k, 'ids')} (see diff)"))
    if verified:
        out.append(f"{VERIFIED}: {verified}")
    return out


def parse_trailers(text):
    """{canonical key: [values]} of the KB-* trailers in `git log %(trailers:only,unfold)` output."""
    out = {}
    canon = {k.lower(): k for k in KEYS + (VERIFIED, AUTO, WORK, REF)}
    for ln in (text or "").splitlines():
        k, sep, v = ln.partition(":")
        if sep and k.strip().lower() in canon:
            out.setdefault(canon[k.strip().lower()], []).append(v.strip())
    return out


def values_match(actual, want):
    """Does a trailer value (list of occurrences) state exactly the ids `want`? A public topic matches with or
    without its root (`public/intune/x` or `intune/x`, as trailers wrote it before topics were qualified)."""
    if not actual:
        return not want
    if len(actual) > 1:
        return False
    m = SUMMARY.match(actual[0])
    if m:
        return len(want) > MAX_IDS and int(m.group(1)) == len(want)
    bare = lambda v: v[len("public/"):] if v.startswith("public/") else v  # noqa: E731
    return sorted(bare(x.strip()) for x in actual[0].split(",") if x.strip()) == sorted(map(bare, want))


def comment_char():
    c = (git("config", "--get", "core.commentChar") or "#").strip()
    return c if len(c) == 1 else "#"


def apply_trailers(message, computed, verified=None):
    """The message with its KB-* trailers replaced by the computed ones (appended with git interpret-trailers).
    An empty message (the user aborted in the editor) is returned unchanged, so the commit still aborts."""
    cc = comment_char()
    if not any(ln.strip() and not ln.startswith(cc) for ln in message.splitlines()):
        return message
    drop = lambda ln: KEY_LINE.match(ln) or (verified and ln.lower().startswith(VERIFIED.lower() + ":"))  # noqa: E731
    kept = "".join(ln for ln in message.splitlines(keepends=True) if not drop(ln))
    lines = trailer_lines(computed, verified)
    if not lines:
        return kept
    args = ["interpret-trailers", "--if-exists", "replace"]
    for ln in lines:
        args += ["--trailer", ln]
    out = git(*args, stdin=kept.encode("utf-8"))
    if out is None:
        raise Problem("git interpret-trailers failed")
    return out


def cmd_trailers(a):
    if a.verified and not valid_date(a.verified):
        print(f"--verified {a.verified!r}: expected YYYY-MM-DD")
        return 2
    if a.amend:
        head = rev_parse("HEAD")
        if not head:
            print("no commit to amend")
            return 2
        if (git("rev-list", "--parents", "-n", "1", "HEAD") or "").count(" ") > 1:
            print("HEAD is a merge commit: merges carry no trailers")
            return 2
        if git("diff-index", "--cached", "--quiet", "HEAD") is None:
            print("staged changes present: commit or unstage them first (--amend only rewrites the message)")
            return 2
        msg = git("log", "-1", "--format=%B", "HEAD") or ""
        new = apply_trailers(msg, compute(first_parent(head), head), a.verified)
        if new.strip() == msg.strip():
            print("trailers already correct")
            return 0
        p = git_run("commit", "--amend", "--no-verify", "--allow-empty", "--cleanup=whitespace", "-F", "-", stdin=new.encode("utf-8"))
        if p is None or p.returncode:
            print("git commit --amend failed: " + (p.stderr.decode("utf-8", "replace") if p else "no git"))
            return 2
        print(git("log", "-1", "--format=%h %s%n%(trailers:only,unfold)", "HEAD") or "")
        return 0
    if a.rev and not a.staged:
        rev = rev_parse(a.rev)
        if not rev:
            print(f"{a.rev}: not a commit here")
            return 2
        computed = compute(first_parent(rev), rev)
    else:
        computed = compute(rev_parse("HEAD") or "", INDEX)
    for ln in trailer_lines(computed, a.verified):
        print(ln)
    return 0



def log_records(*args, body=False):
    """[(sha, short, date, subject, trailers text)] of `git log ARGS`, newest first; with `body`, each also ends in
    the commit's whole message."""
    out = git("log", "--format=%H%x1f%h%x1f%cs%x1f%s%x1f%(trailers:only,unfold)" + ("%x1f%B" if body else "") + "%x1e", *args)
    if out is None:
        return None
    recs = []
    for r in out.split("\x1e"):
        f = r.strip("\n").split("\x1f")
        if len(f) == 5 + bool(body):
            recs.append(tuple(f))
    return recs


def default_range():
    before, sha = os.environ.get("CI_COMMIT_BEFORE_SHA", ""), os.environ.get("CI_COMMIT_SHA", "")
    if sha:
        if before and set(before) != {"0"} and rev_parse(before):
            return f"{before}..{sha}"
        return sha
    return "@{upstream}..HEAD" if rev_parse("@{upstream}") else "HEAD"




def commit_changes(spec):
    """{sha: (first parent or "", [changed paths])} for the non-merge commits of `git log SPEC`, from one git call:
    the paths diff-tree gives against the first parent (no rename detection; a root commit lists every file)."""
    out = git("-c", "log.showRoot=true", "log", "--no-merges", "--no-renames", "--name-only", "-z",
              "--format=%x1e%H%x1f%P", *spec)
    if out is None:
        return None
    res = {}
    for rec in out.split("\x1e")[1:]:
        head, _, rest = rec.partition("\0")
        sha, _, parents = head.partition("\x1f")
        res[sha] = ((parents.split() or [""])[0], sorted(p for p in rest.lstrip("\n").split("\0") if p))
    return res


class BlobReader:
    """File texts at commits through one `git cat-file --batch` process (blob() starts a git process per file)."""

    def __init__(self):
        try:
            self.p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=KB, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        except OSError:
            self.p = None

    def __call__(self, rev, rel):
        if rev == "" or self.p is None:
            return blob(rev, rel)
        self.p.stdin.write(f"{rev}:./{rel}\n".encode())
        self.p.stdin.flush()
        head = self.p.stdout.readline().split()
        if len(head) != 3:  # "<name> missing" (or ambiguous): not in that commit
            return None
        data = self.p.stdout.read(int(head[2]))
        self.p.stdout.read(1)
        return data.decode("utf-8", "replace") if head[1] == b"blob" else None

    def close(self):
        if self.p is not None:
            self.p.stdin.close()
            self.p.wait()


_WANT = {}  # sha -> computed trailers: sync audits the same commits twice


def forget_audits():
    """Drop the computed trailers of the commits audited so far (a caller that rewrote them audits afresh)."""
    _WANT.clear()


def trailer_audit(rng, quiet=False, work_state_on=True):
    """(commits checked, kb commits, [(sha, lines describing what is wrong)]) for a range A..B or one commit;
    None when the range is not valid here. `work_state_on`: also judge the KB-Work items of the commits not yet on
    origin/main (work_state); refresh_trailers leaves it off, since rewriting trailers cannot fix that."""
    spec = [rng] if ".." in rng else [rng + "^!"]
    since = rev_parse(TRAILERS_SINCE)
    if since:
        spec.append("^" + since)
    elif not quiet:
        print(f"note: exemption cutoff {TRAILERS_SINCE[:12]} is not in this clone; every commit in the range is checked")
    recs = log_records("--no-merges", *spec, body=True)
    if recs is None:
        return None
    changes = commit_changes(spec) or {}
    blobs = BlobReader()
    pending = None  # the range's commits not on origin/main, read at the first KB-Work trailer that needs it
    bad, kb = [], 0
    try:
        for sha, *_ in recs:
            if sha in _WANT:
                continue
            if sha in changes:
                base, paths = changes[sha]
                _WANT[sha] = trailers_from(paths, lambda rel: blobs(base, rel), lambda rel: blobs(sha, rel))
            else:
                _WANT[sha] = compute(first_parent(sha), sha)
        for sha, short, date, subject, trailers, message in recs:
            want = _WANT[sha]
            have = parse_trailers(trailers)
            wrong = [k for k in KEYS if not values_match(have.get(k), want.get(k, []))]
            v = have.get(VERIFIED)
            if v and (len(v) > 1 or not valid_date(v[0])):
                wrong.append(VERIFIED)
            auto = have.get(AUTO)
            if auto and (len(auto) > 1 or not all(x.strip() in AUTO_VALUES for x in auto[0].split(","))):
                wrong.append(AUTO)
            if any(re.fullmatch(r"\S+", x) is None for x in have.get(REF, [])):
                wrong.append(REF)
            work = have.get(WORK)
            state = []
            paths = changes[sha][1] if sha in changes else changed_paths(first_parent(sha), sha)
            stray = stray_lines(message, trailers)
            if not work and not auto and not any(WORK_LINE.match(ln) for ln in stray) and any(code_path(p) for p in paths):
                state.append(MISSING_WORK)  # a stray KB-Work line says it already: move it into the trailer block
            if work and not work_ok(sha, work, blobs):
                wrong.append(WORK)
            elif work and work_state_on:
                if pending is None:
                    pending = off_origin_main(spec, [r[0] for r in recs])
                if sha in pending:
                    state += work_state(work, paths, lambda rel: at_or_parent(sha, rel, blobs))
            kb += bool(want)
            if wrong or state or stray:
                lines = [f"BAD {short} {date} {subject[:70]}"]
                lines += [f"    not a trailer: {ln!r}" for ln in stray] + ([f"    {STRAY}"] if stray else [])
                for k in wrong:
                    exp = next((ln for ln in trailer_lines(want) if ln.startswith(k + ":")), {VERIFIED: "YYYY-MM-DD, once", AUTO: "once, of " + "|".join(AUTO_VALUES),
                                                                                                     WORK: "once, backlog item ids that exist at the commit or its parent",
                                                                                                     REF: "one tracker id on each line, with no space"}.get(k, f"(no {k})"))
                    lines.append(f"    {k}: has {', '.join(have.get(k, [])) or '(none)'}; expected {exp}")
                for why in state:
                    lines.append(f"    {WORK}: {why}" + ("" if why in FORM_ONLY else
                                                         "; work lands only for a claimed item of a started sprint"))
                if WORK in wrong or any(why not in FORM_ONLY for why in state):
                    lines.append(f"    the rule: {WORK_RULE}")
                bad.append((sha, lines))
    finally:
        blobs.close()
    return len(recs), kb, bad


STRAY = ("git reads trailers only in the message's last paragraph (a blank line before Co-Authored-By starts a new one, "
         "and a line there that is no trailer can stop git reading it): move each KB-* or Self-Reviewed line named into "
         "that paragraph, one block with Co-Authored-By and the other trailers")
STRAY_WORK = STRAY  # the name kbgit.py re-exports
REVIEWED = "Self-Reviewed"  # selfdoc.py's trailer; kg_trailers does not import selfdoc
TRAILER_KEYS = (*KEYS, VERIFIED, AUTO, WORK, REF, REVIEWED)  # the trailers of ours: a prose line like `kb-sprint:` is none
STRAY_KEY = re.compile(r"(" + "|".join(re.escape(k) for k in TRAILER_KEYS) + r")[ \t]*:[ \t]*\S", re.I)  # by key, any case


MISSING_WORK = ("changes _tools/, .claude/, .githooks/ or .gitlab-ci.yml with no KB-Work and no KB-Auto trailer: "
                "name the item it works on")
FORM_ONLY = (MISSING_WORK,)
WORK_PATHS = ("_tools/", ".claude/", ".githooks/", ".gitlab-ci.yml")  # a change to these is work: it needs a KB-Work


def code_path(path):
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in WORK_PATHS)


def stray_lines(body, trailers):
    """The lines of a commit message BODY that start a KB-* or Self-Reviewed trailer git does not read as one. TRAILERS
    is git's own reading of the message's trailer block (`%(trailers:only,unfold)`, `interpret-trailers --parse`):
    per key, the lines beyond the number of its trailers there are stray, and since git reads trailers from the last
    paragraph only, they are the key's first lines (kb/public/gitlab/git-trailers-and-hooks.md)."""
    count = lambda text: [m.group(1).lower() for m in map(STRAY_KEY.match, (text or "").splitlines()) if m]  # noqa: E731
    read, lines = count(trailers), [ln for ln in (body or "").splitlines() if STRAY_KEY.match(ln)]
    keys, out, seen = count(body), [], {}
    for ln, key in zip(lines, keys):
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= keys.count(key) - read.count(key):
            out.append(ln.strip())
    return out


def read_message(message):
    """(the message's lines as the commit will keep them: comment lines and anything below a scissors line left out,
    the trailers `git interpret-trailers --parse` reads in them, as text)."""
    cc = comment_char()
    kept = []
    for ln in message.splitlines():
        if ln.startswith(cc + " ------------------------ >8 ------------------------"):
            break
        if not ln.startswith(cc):
            kept.append(ln)
    return kept, git("interpret-trailers", "--parse", stdin=("\n".join(kept) + "\n").encode("utf-8")) or ""


def message_trailers(message):
    """(the message's kept lines (read_message), {key: [values]} of the KB-* trailers git reads in them)."""
    kept, parsed = read_message(message)
    return kept, parse_trailers(parsed)


def message_strays(message):
    """The KB-* and Self-Reviewed lines of a commit message that git will not read as trailers (stray_lines)."""
    kept, parsed = read_message(message)
    return stray_lines("\n".join(kept), parsed)


def stray_work(message):
    """True when a commit message has a KB-* or Self-Reviewed line git does not read as a trailer (kbgit.py re-exports
    it)."""
    return bool(message_strays(message))


def work_ok(sha, values, read=blob):
    """A KB-Work trailer: one line of comma-separated backlog ids, each an item file at the commit or its parent (a
    commit that closes a sprint deletes the files). `read(rev, rel)` is a file's text at a commit, or None."""
    return work_ids_ok(values, lambda rel: at_or_parent(sha, rel, read))


def work_ids_ok(values, load):
    """work_ok's rule with `load(rel)` the file's text (or None): one KB-Work line of existing backlog ids."""
    if len(values) != 1:
        return False
    ids = [x.strip() for x in values[0].split(",") if x.strip()]
    return bool(ids) and all(WORK_ID.fullmatch(i) and load(f"{BACKLOG}/{i}.json") is not None for i in ids)


WORK_RULE = ("a commit's KB-Work names, on one line, only items claimed (doing or done) in a started sprint, or a "
             "sprint or review item; a backlog-planning commit (it changes only item files: a claim, a release, a "
             "gate, a plan) names exactly the items whose files it changes, so a release commit names the released "
             "item and no other, and no later work commit names that item until it is claimed again")


WORKED = ("doing", "done")  # a claimed item (done drops claimed_by but was claimed to get there)
BACKLOG_FILE = re.compile(re.escape(BACKLOG) + r"/[^/]+\.json")


def work_state(values, paths, load):
    """[problem lines] for the KB-Work ids of a commit not yet on origin/main (kb/_self/backlog.md, Git): each id's
    item must be claimed (doing, or done) and in a started (active) sprint, read from the backlog at the commit.
    `load(rel)` is a file's text at the commit, else at its parent (a sprint close deletes the files), or None.
    Exempt: a backlog-planning commit (it changes only item files: new items, claims, gates, a sprint's plan, start
    or close), and the sprint and review items themselves. A research item of a planned sprint (its own touches all
    inside kb roots, bl_base.research_touches) may land claimed, on a commit that changes only kb content and item
    files. An id with no item file is work_ok's to report. A backlog-planning commit must change the item file of
    every id it names: one naming two items and changing one is refused for the other."""
    ids = [x.strip() for x in values[0].split(",") if x.strip()]
    if paths and all(BACKLOG_FILE.fullmatch(p) for p in paths):
        return [f"{i}: a backlog-planning commit names it but does not change {BACKLOG}/{i}.json (edit items with "
                f"backlog.py set, or drop the id from KB-Work)"
                for i in ids if f"{BACKLOG}/{i}.json" not in paths and load(f"{BACKLOG}/{i}.json")]
    from bl_base import RESEARCH_KINDS, research_touches  # the rules, never the backlog facade
    cache = {}

    def get(i):
        if i not in cache:
            text = load(f"{BACKLOG}/{i}.json")
            try:
                cache[i] = json.loads(text) if text else None
            except ValueError:
                cache[i] = None
        return cache[i] if isinstance(cache[i], dict) else None

    out = []
    for i in ids:
        it = get(i)
        if it is None or it.get("kind") == "sprint" or it.get("review"):
            continue
        if it.get("status") not in WORKED:
            out.append(f"{i} is {it.get('status')}, not claimed (backlog.py claim)")
        sp, cur, seen = None, it, {i}
        while cur is not None:
            sp = cur.get("sprint")
            if sp or not cur.get("parent") or cur["parent"] in seen:
                break
            seen.add(cur["parent"])
            cur = get(cur["parent"])
        state = (get(sp) or {}).get("status") if sp else None
        research = it.get("kind") in RESEARCH_KINDS and research_touches(it.get("touches"))
        if state == "planned" and research:
            # a research item of a planned sprint: its kb content lands before the sprint starts, nothing else does
            other = sorted(p for p in paths if not BACKLOG_FILE.fullmatch(p) and not research_touches([p]))
            if other:
                out.append(f"{i} is a research item of a planned sprint ({sp}): its commit changes only kb content "
                           f"and item files, not {', '.join(other[:5])}")
        elif state != "active":
            out.append(f"{i} is not in a started sprint" + (f" ({sp} is {state or 'missing'})" if sp else " (no sprint)"))
    return out


def at_or_parent(sha, rel, read=blob):
    """A file's text at a commit, else at its first parent (a sprint close deletes the item files), else None."""
    text = read(sha, rel)
    return text if text is not None else read(sha + "^", rel)


def off_origin_main(spec, shas):
    """{sha} of SHAS, the non-merge commits of `git log SPEC`, that are not yet on the integration remote's main, from
    one git call: the others are history, their KB-Work items judged when they landed. With no such main in this
    clone (the call fails), every one of them."""
    out = git("log", "--no-merges", "--format=%H", *spec, "^" + f"refs/remotes/{kbpublic.integration_remote(KB)}/main")
    return set(shas) if out is None else set(out.split())


def cmd_check_trailers(a):
    rng = a.range or default_range()
    audit = trailer_audit(rng)
    if audit is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    n, kb, bad_list = audit
    for _, lines in bad_list:
        print("\n".join(lines))
    bad = len(bad_list)
    print(f"check-trailers {rng}: commits={n} kb_commits={kb} bad={bad}")
    if bad:
        print("fix unpushed commits: python3 _tools/kbgit.py trailers --amend (HEAD), or "
              "git rebase --exec \"python3 _tools/kbgit.py trailers --amend\" <base>; "
              "install the hook once per clone: python3 _tools/kbgit.py install-hooks")
    if any(f"    {STRAY}" in lines for _, lines in bad_list):
        print("a line that is not a trailer: rewrite the unpushed commit's message (HEAD: git commit --amend -F FILE, "
              "then python3 _tools/kbgit.py check-trailers); pushed history is never rewritten")
    return 1 if bad else 0

