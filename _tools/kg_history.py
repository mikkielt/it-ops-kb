"""The history commands of kbgit.py (kb/_self/git.md, Commands): `log` (the commits that touched a source id, topic,
answer id or path), `blame` (the commit that introduced a line and the sources it cites), `asof` (a file as of a date or
a tag) and `tag-census`, with the repository paths they take. Runs git in KB, this module's own copy of the repository
directory (a caller may point it at a scratch clone). Standard library only; kbgit.py imports it, and it imports no
facade.
"""
import csv, datetime, io, os, re, sys

import build_index
import kbcommon
import kbid
import kbpublic
import kg_merge
from kg_base import KB, repo_roots
from kg_merge import id_key, lf
from kg_trailers import blob, is_content, log_records, parse_trailers, source_rows_of, valid_date


def user_path(arg):
    """A path given on the command line as a repository path: qualified (`public/auth/kerberos.md`), bare
    root-relative (`auth/kerberos.md`: the public root) or repository-relative; as given when it names nothing."""
    arg = arg[2:] if arg.startswith("./") else arg
    head, _, rest = arg.partition("/")
    for r in repo_roots():
        if head == r.name and rest and os.path.exists(os.path.join(r.path, rest)):
            return kbcommon.repo_rel(rest, r.path)
    return kbcommon.repo_rel(arg, kbcommon.PUBLIC) if os.path.exists(os.path.join(kbcommon.PUBLIC, arg)) else arg


def with_legacy(path):
    """[path] plus, for a file under the public root, its path before the kb moved (root-relative), for history."""
    rel = kbcommon.kb_rel(path, kbcommon.PUBLIC)
    return [path] + ([rel] if rel and rel != path else [])


def git_run(*args, stdin=None):
    return kg_merge.git_run(*args, stdin=stdin, kb=KB)


def git(*args, stdin=None):
    return kg_merge.git(*args, stdin=stdin, kb=KB)


def read(rel):
    return kg_merge.read(rel, kb=KB)


def show(rev, rel):
    return kg_merge.show(rev, rel, kb=KB)


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


def id_regex(sid):
    """POSIX ERE for a source id as a whole word (git log -G)."""
    return rf"(^|[^A-Za-z0-9_-]){re.escape(sid)}([^A-Za-z0-9_-]|$)"


def split_arg(arg):
    """(Root, rest) of a history argument: `<root>/<rest>` or `<root>:<answer id>` names that root; anything else is
    the public root's."""
    for sep in ("/", ":"):
        head, s, rest = arg.partition(sep)
        if s and rest:
            for r in repo_roots():
                if r.name == head:
                    return r, rest
    return kbcommon.public(), arg


def classify(arg):
    """(kind, what, root): a source id, an answer id, a topic (qualified or bare = public) or a path."""
    if kbid.is_source_id(kbid.canonical_id(arg)) and not os.path.exists(os.path.join(KB, user_path(arg))):
        sid = kbid.canonical_id(arg)
        return "source", sid, kbcommon.root_of_prefix(sid.split("-", 1)[0] if "-" in sid else "S") or kbcommon.public()
    r, rest = split_arg(arg)
    ans = kbcommon.read(os.path.join(r.path, kbcommon.ANSWERS)) or ""
    if (kbid.QK_ID.fullmatch(rest) and ":" in arg) or kbid.QK_ID.fullmatch(arg) or rest in kbid.answer_ids(ans):
        return "answer", rest, r
    topics = {x["topic"] for x in csv.DictReader(io.StringIO(lf(kbcommon.read(os.path.join(r.path, kbcommon.COVERAGE_CSV)) or "")))}
    if rest in topics or (os.path.isfile(os.path.join(r.path, rest + ".md"))
                          and is_content(kbcommon.repo_rel(rest + ".md", r.path))):
        return "topic", rest, r
    return "path", user_path(arg), None


def cmd_log(a):
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    kind, what, r = classify(a.target)
    keys = {"source": ("KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded"),
            "topic": ("KB-Topics",), "answer": ("KB-Answers",), "path": ()}[kind]
    # trailer values: topics qualified (bare in commits from before roots), answers `<root>:<id>` outside public
    if kind == "topic":
        want = {f"{r.name}/{what}"} | ({what} if r.name == "public" else set())
    elif kind == "answer":
        want = {what} if r.name == "public" else {f"{r.name}:{what}"}
    else:
        want = {what}
    recs = log_records("HEAD") or []
    how = {}
    for sha, _, _, _, trailers in recs:
        t = parse_trailers(trailers)
        if any(want & {x.strip() for v in t.get(k, []) for x in v.split(",")} for k in keys):
            how[sha] = "trailer"
    fallback = []
    if kind == "source":
        fallback = [("diff", ["-G", id_regex(what)])]
    elif kind == "answer":
        fallback = [("diff", ["-G", rf"^## {re.escape(what)}\. ", "--",
                              *with_legacy(kbcommon.repo_rel(kbcommon.ANSWERS, r.path))])]
    elif kind == "topic":
        cov = lf(kbcommon.read(os.path.join(r.path, kbcommon.COVERAGE_CSV)) or "")
        row = {x["topic"]: x for x in csv.DictReader(io.StringIO(cov))}.get(what)
        files = [f for f in (row["files"].split(";") if row else [what + ".md"]) if f]
        fallback = [("path", ["--"] + [p for f in files for p in with_legacy(kbcommon.repo_rel(f, r.path))])]
    if kind == "topic":
        what = f"{r.name}/{what}"
    elif kind == "answer" and r.name != "public":
        what = f"{r.name}:{what}"
    if kind == "path":
        fallback = [("path", ["--follow", "--", what])]
    for label, args in fallback:
        for sha in (git("log", "--format=%H", "HEAD", *args) or "").split():
            how.setdefault(sha, label)
    hits = [r for r in recs if r[0] in how]
    print(f"# {kind} {what}: {len(hits)} commit(s)" + (f", newest {a.n}" if len(hits) > a.n else ""))
    for sha, short, date, subject, _ in hits[:a.n]:
        print(f"{short}  {date}  {subject[:80]}  [{how[sha]}]")
    return 0 if hits else 1


def blame_line(path, n, ignore_ws):
    args = ["blame", "--porcelain", "-M", "-C", "-L", f"{n},{n}"] + (["-w"] if ignore_ws else []) + ["--", path]
    out = git(*args)
    if not out:
        return None
    lines = out.splitlines()
    info = {"sha": lines[0].split()[0]}
    for ln in lines[1:]:
        if ln.startswith("\t"):
            info["text"] = ln[1:]
            break
        k, _, v = ln.partition(" ")
        info[k] = v
    return info


def cmd_blame(a):
    path, _, line = a.target.rpartition(":")
    if not path or not line.isdigit() or int(line) < 1:
        print(f"{a.target!r}: expected PATH:LINE")
        return 2
    shown = path[2:] if path.startswith("./") else path
    path = user_path(shown)
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    b = blame_line(path, int(line), True)
    if b is None:
        print(f"{shown}:{line}: no such tracked file or line")
        return 1
    zero = set(b["sha"]) == {"0"}
    when = datetime.datetime.fromtimestamp(int(b.get("author-time", "0")), datetime.timezone.utc).date() if not zero else ""
    print(f"{shown}:{line}: {b.get('text', '')}")
    if zero:
        print("  introduced by: not committed yet")
    else:
        rec = (log_records("-1", b["sha"]) or [("", b["sha"][:7], str(when), b.get("summary", ""), "")])[0]
        print(f"  introduced by: {rec[1]}  {rec[2]}  {rec[3][:80]}  ({b.get('author', '?')})"
              + (f"  [as {b['filename']}]" if b.get("filename") and b["filename"] != path else ""))
        plain = blame_line(path, int(line), False)
        later = int((git("rev-list", "--count", f"{b['sha']}..HEAD", "--", path) or "0").strip() or 0)
        if plain and plain["sha"] != b["sha"]:
            print(f"  touched since: whitespace only, in {plain['sha'][:7]}")
        else:
            print("  touched since: no" + (f" (the file changed in {later} later commit(s))" if later else ""))
    ids = sorted(set(build_index.CITE.findall(b.get("text", ""))), key=id_key)
    rows, ledgers = {}, []
    for root in (repo_roots() if ids else []):
        led = kbcommon.repo_rel(kbcommon.SOURCES, root.path)
        ledgers += with_legacy(led)
        rows.update((x.get("id"), x) for x in source_rows_of(read(led)).values())
    for sid in ids:
        r = rows.get(sid)
        added = (git("log", "--reverse", "--format=%h %cs", "-G", rf"^{re.escape(sid)},", "HEAD", "--", *ledgers) or "").split("\n")[0]
        sup = (r or {}).get("superseded_by", "").strip()
        print(f"  {sid}  {(r or {}).get('url') or 'UNKNOWN id'}" + (f"  superseded by {sup}" if sup else "")
              + (f"  (row added in {added})" if added else ""))
    return 0


def cmd_asof(a):
    if valid_date(a.when):
        rev = (git("rev-list", "-1", "--first-parent", f"--before={a.when} 23:59:59", "HEAD") or "").strip()
        if not rev:
            print(f"no commit on or before {a.when}", file=sys.stderr)
            return 1
    else:
        rev = rev_parse(a.when)
        if not rev:
            print(f"{a.when!r}: neither YYYY-MM-DD nor a tag or commit here", file=sys.stderr)
            return 2
    path = a.path[2:] if a.path.startswith("./") else a.path
    for cand in with_legacy(user_path(path)):  # before the kb moved, a root file sat at its root-relative path
        p = git_run("cat-file", "blob", f"{rev}:./{cand}")  # not `git show` (see show)
        if p is not None and not p.returncode:
            break
    rec = (log_records("-1", rev) or [("", rev[:7], "", "", "")])[0]
    if p is None or p.returncode:
        print(f"{path} did not exist at {rec[1]} ({rec[2]})", file=sys.stderr)
        return 1
    print(f"# {path} at {rec[1]}  {rec[2]}  {rec[3][:80]}", file=sys.stderr)
    sys.stdout.flush()
    sys.stdout.buffer.write(p.stdout)
    return 0


def census_message(date):
    lines = [f"kb confirmed current as of {date}", ""]
    rows = source_rows_of(blob("HEAD", kg_merge.SOURCES))
    sup = sum(1 for r in rows.values() if (r.get("superseded_by") or "").strip())
    lines.append(f"sources: {len(rows)} in {kg_merge.SOURCES} ({sup} superseded)")
    st = blob("HEAD", kg_merge.STATE)
    if st:
        state = list(csv.DictReader(io.StringIO(lf(st))))
        ok = [r for r in state if r.get("checked_utc") and not (r.get("error") or "").strip()]
        err = sum(1 for r in state if (r.get("error") or "").strip())
        latest = max((r.get("checked_utc", "") for r in state), default="")
        never = len(set(rows) - {r.get("id") for r in state})
        lines.append(f"fetch state: {len(ok)} sources verified (checked without error), {err} with an error, "
                     f"{never} never checked; latest check {latest[:10] or 'none'}")
    else:
        lines.append(f"fetch state: none ({kg_merge.STATE} is not committed)")
    return "\n".join(lines) + "\n"


def cmd_tag_census(a):
    if not valid_date(a.date):
        print(f"{a.date!r}: expected YYYY-MM-DD")
        return 2
    head = rev_parse("HEAD")
    if not head:
        print("not a git clone, or no commits")
        return 2
    name = f"census-{a.date}"
    if rev_parse(f"refs/tags/{name}"):
        print(f"tag {name} already exists")
        return 2
    if a.date > datetime.date.today().isoformat():
        print(f"WARN {a.date} is in the future")
    if (git("status", "--porcelain", "--untracked-files=no") or "").strip():
        print("WARN uncommitted changes are not part of the census (the tag is on HEAD)")
    msg = census_message(a.date)
    p = git_run("tag", "-a", name, "-F", "-", head, stdin=msg.encode("utf-8"))
    if p is None or p.returncode:
        print("git tag failed: " + (p.stderr.decode("utf-8", "replace") if p else "no git"))
        return 2
    print(f"created annotated tag {name} on {head[:12]}\n" + msg.rstrip())
    print(f"not pushed; to share it: git push {kbpublic.integration_remote(KB)} {name}")
    return 0
