"""The query log's delivery (kb/_self/querylog.md, Delivery): `apply --push`, and the push of mode `auto` after a
distill. Under the distill lock, in the worktree beside the spool reset to origin/main: the CI check of the last
automatic commit (a revert when red), the local store's new files gated and committed, the worktree's own learn and
apply, and one `kbgit.py sync --push` to origin only. A conflict sync cannot resolve goes to a `querylog/<run-id>`
branch with the merge-request push options. Plugin hosts push from a managed clone of their install source; cloud
sessions push to the branch they have checked out.
"""
import json, os, re, shutil, sys, urllib.parse
from pathlib import Path
from urllib.parse import urlsplit

import kbpublic
from ql_base import (DISABLED_NAME, HOME, STORE_REL, acquire, now, places, plugin_data, read_json, release, run_cmd,
                     write_text)
from ql_distill import spool_delivered
from ql_research import edit_problems
from ql_store import (APPLY_FAILED, FINDINGS, LEARN_STATES, USAGE, finding_states, findings_files, leak_problems,
                      load_run, run_files, store_entries, usage_files, write_findings)

REMOTE, BRANCH = "origin", "main"  # the repository the clone came from, and the branch automatic commits land on
CONFLICT_BRANCH_PREFIX = "querylog/"  # a conflict sync cannot resolve goes to querylog/<run-id>, as a merge request
MR_OPTIONS = ("merge_request.create", f"merge_request.target={BRANCH}")  # push options: no token, no auto-merge
FALLBACK_GITLAB_HOST = "gitlab.com"  # only when origin's url names no host
WORKTREE_NAME = "worktree"  # beside the spool: automatic commits are made there, never in the person's checkout
CLONE_NAME = "clone"  # beside a plugin host's spool: its managed clone of the repository the plugin was installed from
GITLAB_RED = ("failed",)
GITLAB_UNFINISHED = ("created", "waiting_for_resource", "preparing", "waiting_for_callback", "pending", "running",
                     "canceling", "scheduled")
GITHUB_RED = ("failure", "timed_out", "startup_failure")  # conclusions of a completed run
LOOKBACK = 200  # first-parent commits of origin/main searched for the last automatic commit
REFUSALS = (  # a push refused for want of rights, as the remote words it (kb: gitlab/automated-merge-requests.md)
    ("gitlab", re.compile(r"You are not allowed to (?:push code|force push code|upload code)\b[^\n]*")),
    ("github", re.compile(r"Permission to \S+ denied to [^\n]*|GH006: Protected branch update failed[^\n]*")),
    ("http-403", re.compile(r"The requested URL returned error: 403\b[^\n]*")),
)


# ---------------------------------------------------------------- origin's forge and its CI

def origin_forge(url):
    """(forge, host, project path) of a remote url: https or ssh urls and the scp form user@host:path. A url that
    names no host (a local path, file://) gets FALLBACK_GITLAB_HOST and its last two path segments. `github` for
    github.com, else `gitlab`."""
    u = (url or "").strip()
    host, path = None, u
    if re.match(r"[a-z][a-z0-9+.-]*://", u, re.I):
        s = urlsplit(u)
        host, path = (s.hostname if s.scheme.lower() != "file" else None), s.path
    else:
        m = re.fullmatch(r"(?:[^@/\\]+@)?([^:/\\]{2,}):(?!//)(.*)", u)  # a Windows drive (C:\...) is no host
        if m:
            host, path = m.group(1), m.group(2)
    path = path.replace("\\", "/").strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not host:
        return "gitlab", FALLBACK_GITLAB_HOST, "/".join(path.split("/")[-2:])
    host = host.lower()
    return ("github" if host == "github.com" else "gitlab"), host, path


def forge_list(url, run, github_argv, gitlab_api, named=2):
    """(the JSON list origin's forge answers, the CLI's name, a note) for a `gh` argument list (its first `named`
    words name it in a note) or a `glab api` path: `glab auth status` or `gh auth status` for origin's host first. The
    list is None, and the note says why, when the CLI is not signed in or the call fails."""
    forge, host, project = origin_forge(url)
    cli = "gh" if forge == "github" else "glab"
    code, _, err = run([cli, "auth", "status", "--hostname", host])
    if code:
        return None, cli, f"{cli} is not signed in to {host} ({(err.strip().splitlines() or ['not installed'])[-1][:80]})"
    if forge == "github":
        argv = github_argv(f"{host}/{project}")
        name = " ".join(argv[:named])
    else:
        argv = ["glab", "api", "--hostname", host, gitlab_api(urllib.parse.quote(project, safe=""))]
        name = "glab api"
    code, o, err = run(argv)
    try:
        data = json.loads(o) if code == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        return None, cli, f"{name} failed ({(err.strip().splitlines() or ['no JSON list'])[-1][:80]})"
    return data, cli, f"{cli} on {host}"


def pipeline_verdict(forge, statuses):
    """`red`, `pending` or `ok` from the CI states of one commit: only a finished failure is red (`failed` on
    GitLab; a completed run concluded failure, timed_out or startup_failure on GitHub); an unfinished state is
    pending; manual, skipped, canceled and success are ok. GitHub: `statuses` are (status, conclusion) pairs."""
    if forge == "github":
        if any(s == "completed" and c in GITHUB_RED for s, c in statuses):
            return "red"
        return "pending" if any(s != "completed" for s, _ in statuses) else "ok"
    if any(s in GITLAB_RED for s in statuses):
        return "red"
    return "pending" if any(s in GITLAB_UNFINISHED for s in statuses) else "ok"


def ci_pipeline(url, sha, run):
    """(verdict, detail, pipeline) of the CI of commit `sha` on origin's forge: verdict `red`, `pending`, `ok`,
    `none` (no pipeline) or `skip` (no signed-in glab or gh, or the call failed: the check is skipped). `pipeline`
    is {id, url, status} of the newest pipeline (GitHub: the first red run), or None."""
    forge = origin_forge(url)[0]
    data, cli, note = forge_list(
        url, run, lambda repo: ["gh", "run", "list", "--commit", sha, "-R", repo, "--json",
                                "status,conclusion,databaseId,url", "-L", "100"],
        lambda project: f"projects/{project}/pipelines?sha={sha}&per_page=1")
    if data is None:
        return "skip", note, None
    if forge == "github":
        runs = [r for r in data if isinstance(r, dict)]
        states = [(r.get("status"), r.get("conclusion")) for r in runs]
        shown = ", ".join(f"{s}/{c}" if c else str(s) for s, c in states)
        pick = next((r for r in runs if r.get("conclusion") in GITHUB_RED), runs[0] if runs else {})
        pipe = {"id": pick.get("databaseId"), "url": pick.get("url"),
                "status": f"{pick.get('status')}/{pick.get('conclusion')}"}
    else:
        runs = [r for r in data[:1] if isinstance(r, dict)]  # the newest pipeline of the commit
        states = [r.get("status") for r in runs]
        shown = ", ".join(map(str, states))
        pipe = {"id": runs[0].get("id"), "url": runs[0].get("web_url"), "status": runs[0].get("status")} if runs else {}
    if not states:
        return "none", f"no pipeline for {sha[:9]} on {origin_forge(url)[1]}", None
    return pipeline_verdict(forge, states), f"{note}: {shown}", pipe


def pipeline_failure(url, pipe, run):
    """(failure, fingerprint) of the red pipeline `pipe` ({id, ...}) on origin's forge, computed as backlog.py does
    for main's pipeline: the first failed job by name, what failed first in its log (`backlog.first_failure`), and
    `backlog.failure_fingerprint` of the two. ('', None) when no failed job can be read (no id, a failed call)."""
    import backlog
    pid = pipe.get("id")
    if pid is None:
        return "", None
    forge, host, project = origin_forge(url)
    if forge == "github":
        code, o, _ = run(["gh", "run", "view", str(pid), "-R", f"{host}/{project}", "--json", "jobs"])
        key, bad, field, idkey = "jobs", ("failure", "timed_out", "startup_failure"), "conclusion", "databaseId"
    else:
        quoted = urllib.parse.quote(project, safe="")
        code, o, _ = run(["glab", "api", "--hostname", host,
                          f"projects/{quoted}/pipelines/{pid}/jobs?scope=failed&per_page=100"])
        key, bad, field, idkey = None, ("failed",), "status", "id"
    try:
        js = json.loads(o) if code == 0 else []
        js = js.get(key, []) if key and isinstance(js, dict) else js
        failed = [j for j in js if isinstance(j, dict) and j.get(field) in bad and j.get("name")]
    except (ValueError, AttributeError, TypeError):
        failed = []
    if not failed:
        return "", None
    first = min(failed, key=lambda j: str(j["name"]))
    log, jid = "", first.get(idkey)
    if jid is not None:
        argv = (["gh", "api", "--hostname", host, f"repos/{project}/actions/jobs/{jid}/logs"] if forge == "github" else
                ["glab", "api", "--hostname", host, f"projects/{quoted}/jobs/{jid}/trace"])
        code, o, _ = run(argv)
        log = o if code == 0 else ""
    failure = backlog.first_failure(log)
    return failure, backlog.failure_fingerprint(first["name"], failure)


def ci_status(url, sha, run):
    """(verdict, detail) of `ci_pipeline`."""
    return ci_pipeline(url, sha, run)[:2]


def auto_log(run, cwd, *revs, sha="%H"):
    """[(sha, subject, [KB-Auto values])] of `git log REVS`, newest first; `sha` is the hash's format (%H, %h)."""
    fmt = f"{sha}%x1f%s%x1f%(trailers:key=KB-Auto,valueonly,separator=%x2C)%x1e"
    code, o, _ = run(["git", "log", f"--format={fmt}", *revs], cwd=str(cwd))
    out = []
    for rec in o.split("\x1e") if code == 0 else []:
        parts = rec.strip("\n").split("\x1f")
        if len(parts) == 3:
            out.append((parts[0], parts[1], [v.strip() for v in parts[2].split(",") if v.strip()]))
    return out


def auto_kinds(paths):
    """The KB-Auto values of a commit changing `paths`; ValueError naming a path apply never writes."""
    kinds = set()
    for p in paths:
        if p.startswith(STORE_REL + "/"):
            kinds.add("querylog")
        elif re.fullmatch(r"kb/[^/]+/_retrieval/lookup_eval\.csv", p):
            kinds.add("eval")
        elif re.fullmatch(r"kb/_self/backlog/[A-Z]{2}-[a-z0-9]+\.json", p):  # the bug item of a revert
            kinds.add("revert")
        elif p == "_tools/aliases.csv" or re.fullmatch(r"kb/[^/]+/_retrieval/aliases\.csv", p):
            kinds.add("alias")
        elif re.fullmatch(r"kb/[^/]+/_retrieval/doc2query/expansions\.csv", p):
            kinds.add("expansion")
        elif re.fullmatch(r"kb/[^/]+/_gaps\.md", p):
            kinds.add("gap")
        elif re.fullmatch(r"kb/[^/_][^/]*/(?:_sources\.csv|_conflicts\.md|_coverage\.csv|_coverage\.md)", p) \
                or re.fullmatch(r"kb/[^/_][^/]*/[^/_][^/]*/(?:[^/]+/)*[^/_][^/]*\.md", p):
            kinds.add("research")
        else:
            raise ValueError(p)
    return sorted(kinds)


def push_refusal(text):
    """`<kind>: <text>` for the first refusal for want of rights in a push's output (REFUSALS: GitLab's `You are not
    allowed to push code ...`, GitHub's `Permission to ... denied` or `GH006`, an HTTP 403), else None. A generic
    `(pre-receive hook declined)`, a DNS or connection error and a `remote failure` are no refusal."""
    for kind, pat in REFUSALS:
        m = pat.search(text or "")
        if m:
            return f"{kind}: {m.group(0).strip()[:200]}"
    return None


def cloud_session():
    """Whether this runs in a Claude Code cloud session: its VM's environment carries CLAUDE_CODE_REMOTE=true."""
    return os.environ.get("CLAUDE_CODE_REMOTE") == "true"


# ---------------------------------------------------------------- the push

class Pusher:
    """One `apply --push` in the worktree `wt` of the clone at `home`, whose query log directory `qdir` holds the
    spool and the local store. `run` starts every command (git, kbgit.py sync, glab, gh); `apply_step(wt, store,
    hold, out)` learns and applies the store's findings in the worktree. `research` is the argument pair that names
    whose research setting applies (default: `--clone home`). `cloud` (default: cloud_session()) pushes to the
    branch `home` has checked out instead of main."""

    def __init__(self, home, qdir, run, apply_step, out, now_dt=None, research=None, cloud=None):
        self.home, self.qdir, self.run, self.out = Path(home), Path(qdir), run, out
        self.wt = self.qdir / WORKTREE_NAME
        self.apply_step = apply_step or self.learn_and_apply
        self.research = list(research or ["--clone", str(self.home)])
        self.cloud = cloud_session() if cloud is None else cloud
        self.branch = BRANCH  # the branch automatic commits are pushed to
        self.up = f"refs/remotes/{REMOTE}/{BRANCH}"  # the ref the worktree starts from
        self.landed = False  # set when deliver pushed to self.branch
        self.refused = None  # the push output line that refused a push for want of rights (push_refusal)
        self.now_dt = now_dt  # the time the spool is read at (default: now)

    def git(self, *args, cwd=None):
        return self.run(["git", *args], cwd=str(cwd or self.wt))

    def tool(self, name, *args):
        """The worktree's own copy of _tools/NAME, run in the worktree."""
        return self.run([sys.executable, str(self.wt / "_tools" / name), *args], cwd=str(self.wt))

    def say(self, text):
        self.out(f"apply --push: {text}")

    def fetch(self):
        """origin's main and its conflict branches (pruned: a merged branch that GitLab deleted goes); in a cloud
        session on another branch, that branch too, which the worktree then starts from once origin has it."""
        main = f"refs/remotes/{REMOTE}/{BRANCH}"
        code, o, e = self.git("fetch", "--quiet", "--prune", REMOTE, f"+refs/heads/{BRANCH}:{main}",
                              f"+refs/heads/{CONFLICT_BRANCH_PREFIX}*:refs/remotes/{REMOTE}/{CONFLICT_BRANCH_PREFIX}*",
                              cwd=self.home)
        if code or self.branch == BRANCH:
            return code, o, e
        ref = f"refs/remotes/{REMOTE}/{self.branch}"
        code, o, e = self.git("fetch", "--quiet", REMOTE, f"+refs/heads/{self.branch}:{ref}", cwd=self.home)
        if code == 0:
            self.up = ref
        elif re.search(r"couldn't find remote ref", o + e, re.I):
            return 0, "", ""  # the branch is not on origin yet: the worktree starts from main
        return code, o, e

    def working_branch(self):
        """The branch `home` has checked out, or None (a detached HEAD)."""
        code, o, _ = self.git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=self.home)
        return (o.strip() or None) if code == 0 else None

    def reset(self):
        """The worktree at origin/main, detached and clean (a rebase or revert left over is abandoned)."""
        if not (self.wt / ".git").exists():
            self.git("worktree", "prune", cwd=self.home)
            return self.git("worktree", "add", "--quiet", "--detach", str(self.wt), self.up, cwd=self.home)
        for op in (("rebase", "--abort"), ("revert", "--abort"), ("cherry-pick", "--abort")):
            self.git(*op)
        code, o, e = self.git("checkout", "--quiet", "--force", "--detach", self.up)
        if code == 0:
            code, o, e = self.git("clean", "-fdq")
        return code, o, e

    def last_automatic(self):
        """(sha of the last commit on origin/main with a KB-Auto trailer, its values, the push tip: the same commit or
        the kbgit fix commits sync added right after it), or None."""
        import kbgit
        recs = auto_log(self.run, self.wt, "--first-parent", "-n", str(LOOKBACK), self.up)
        for i, (sha, _, values) in enumerate(recs):
            if values:
                tip = i
                while tip > 0 and recs[tip - 1][1] == kbgit.FIX_COMMIT:
                    tip -= 1
                return sha, values, [r[0] for r in reversed(recs[tip:i + 1])]
        return None

    def held(self):
        """Finding ids pending on a conflict branch of origin that main does not hold yet: the records of the
        findings files the branch adds."""
        code, o, _ = self.git("for-each-ref", "--format=%(refname)", f"refs/remotes/{REMOTE}/{CONFLICT_BRANCH_PREFIX}")
        ids = set()
        for ref in o.split() if code == 0 else []:
            if self.git("merge-base", "--is-ancestor", ref, self.up)[0] == 0:
                continue
            base = self.git("merge-base", ref, self.up)[1].strip()
            if not base:
                continue
            files = self.git("diff", "--name-only", "--diff-filter=A", base, ref, "--", f"{STORE_REL}/{FINDINGS}")[1]
            for f in files.split():
                text = self.git("show", f"{ref}:{f}")[1]
                for line in text.splitlines()[1:]:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                        ids.add(rec["id"])
        return ids

    def learn_and_apply(self, wt, store, hold, out):
        """The worktree's own querylog.py learn, then its apply, on its own kb and store."""
        ql = [sys.executable, str(wt / "_tools" / "querylog.py")]
        applying = ql + ["apply", "--store", str(store)] + self.research
        for h in sorted(hold):
            applying += ["--hold", h]
        for argv in (ql + ["learn", "--store", str(store)], applying):
            code, o, e = self.run(argv, cwd=str(wt))
            for line in (o + (e if code else "")).strip().splitlines():
                out(line)
            if code:
                return code
        return 0

    def local_files(self):
        """(entry ids of the local store's run files that origin/main holds, [(source, published path, entry ids)]
        of the local files to copy, [published paths] of the local findings files that stay local). A run file or a
        usage sidecar is copied when origin/main lacks its path; a findings file when origin/main lacks its path,
        all its records are in a state learn writes (not apply's outcomes for this clone's working tree) and
        origin/main records none of its findings yet."""
        local, store = self.qdir / "store", self.wt / STORE_REL
        delivered, new, kept = set(), [], []
        for p in run_files(local):
            rel = p.relative_to(local).as_posix()
            try:
                ids = {e["id"] for _, e in load_run(p)[1:] if isinstance(e.get("id"), str)}
            except (OSError, ValueError):
                ids = set()  # copied all the same: `check` refuses it
            if (store / rel).exists():
                delivered |= ids
            else:
                new.append((p, rel, ids))
        recorded = finding_states(store)
        for p in findings_files(local):
            rel = p.relative_to(local).as_posix()
            if (store / rel).exists():
                continue
            try:
                recs = [r for _, r in load_run(p)[1:]]
            except (OSError, ValueError):
                recs = None
            if recs is not None and all(r.get("state") in LEARN_STATES and r.get("id") not in recorded for r in recs):
                new.append((p, rel, set()))
            else:
                kept.append(rel)
        for p in usage_files(local):
            rel = p.relative_to(local).as_posix()
            if not (store / rel).exists():
                new.append((p, rel, set()))
        return delivered, new, kept

    def forget(self, ids):
        """The spool rows of the entries `ids`, whose run file is on origin/main, are deleted."""
        n = spool_delivered(self.qdir, ids, self.now_dt)
        if n:
            self.say(f"deleted the spool rows of {n} entries whose run file is on {REMOTE}/{self.branch}")

    def bring(self, new, kept):
        """The local files `new` copied into the worktree's store, the worktree's `querylog.py check` and the leak
        scan over them, then one commit with `KB-Auto: querylog`. 0, or 1 when a gate fails (nothing committed)."""
        store = self.wt / STORE_REL
        for src, rel, _ in new:
            write_text(store / rel, Path(src).read_text(encoding="utf-8"))
        if kept:
            self.say(f"{len(kept)} local findings file(s) stay local (apply's outcomes, or findings "
                     f"{REMOTE}/{BRANCH} already records)")
        code, o, e = self.tool("querylog.py", "check", str(store))
        problems = [ln for ln in o.splitlines() if ln.strip() and not ln.startswith("querylog check:")] if code else []
        if code and not problems:
            problems = [(o + e).strip()[-300:] or f"querylog.py check exit {code}"]
        problems += leak_problems(store, [rel for _, rel, _ in new])
        if problems:
            self.say("refused: the store gates fail on the local store's files; nothing committed or pushed\n  " +
                     "\n  ".join(problems[:10]))
            return 1
        runs = sorted(Path(rel).stem for _, rel, _ in new if not rel.startswith((FINDINGS + "/", USAGE + "/")))
        found = sum(1 for _, rel, _ in new if rel.startswith(FINDINGS + "/"))
        used = sum(1 for _, rel, _ in new if rel.startswith(USAGE + "/"))
        what = (f"{len(runs)} run file(s)" + (f", {found} findings file(s)" if found else "")
                + (f", {used} usage sidecar(s)" if used else ""))
        body = (f"Automatic commit of querylog.py: the local store's {what} ({', '.join(runs) or 'no run file'}), "
                "copied into kb/_querylog/ after querylog.py check and the leak scan (kb/_self/querylog.md, "
                "Delivery).")
        return self.commit(f"chore(kb): query log store, {what}", body, ["querylog"])

    def edited(self, paths):
        """The existing lines the worktree's change removes or edits in an article, a ledger or a source row
        (edit_problems against HEAD): apply's changes add only."""
        out = []
        for p in paths:
            f = self.wt / p
            code, old, _ = self.git("show", f"HEAD:{p}")
            if code == 0:
                out += edit_problems(p, old, f.read_text(encoding="utf-8") if f.is_file() else "")
        return out

    def changed(self):
        code, o, _ = self.git("status", "--porcelain", "--untracked-files=all", "-z")
        paths = []
        for rec in o.split("\0") if code == 0 else []:
            if len(rec) > 3:
                paths.append(rec[3:])
        return sorted(set(paths))

    def commit(self, subject, body, kinds):
        """One commit of the worktree's changes with its KB-Auto trailer, then its KB-* trailers. The data files
        apply appends rows to change no doc that describes them (kb/_self/map.csv), so those docs are named in a
        Self-Reviewed trailer, which keeps `selfdoc.py stale` in sync's gate quiet."""
        import kbgit, selfdoc
        assert all(k in kbgit.AUTO_VALUES for k in kinds), kinds
        trailers = [f"{kbgit.AUTO}: " + ", ".join(kinds)]
        reviewed = sorted(selfdoc.describing(selfdoc.load_map(str(self.wt)), self.changed()))
        if reviewed:
            trailers.append(f"{selfdoc.REVIEWED}: " + ", ".join(reviewed))
        code, o, e = self.git("add", "--all")
        if code == 0:
            code, o, e = self.git("commit", "--quiet", "--no-verify", "-m", subject, "-m", body,
                                  "-m", "\n".join(trailers))
        if code == 0:
            code, o, e = self.tool("kbgit.py", "trailers", "--amend")
        if code:
            self.say(f"commit failed: {(o + e).strip()[-300:]}")
        return code

    def deliver(self, run_id):
        """kbgit.py sync --push from the worktree (fetch, rebase on origin/<branch>, fix, gate, push to origin). A
        conflict it cannot resolve (exit 3) pushes the commits as they were before the rebase to
        querylog/<run-id> with the merge-request push options, and main stays as it was; in a cloud session on
        another branch, whose proxy takes pushes to that branch only, nothing is pushed then. A push the remote
        refused for want of rights is recorded in `refused`."""
        mine = self.git("rev-parse", "HEAD")[1].strip()
        code, o, e = self.tool("kbgit.py", "sync", "--push", "--remote", REMOTE, "--branch", self.branch)
        report = [ln for ln in (o + e).splitlines() if ln.startswith(("gate ", "pushed:", "needs-human:", "CONFLICT"))]
        for ln in report:
            self.out("  " + ln)
        if code == 0:
            self.say(f"pushed {mine[:9]} to {REMOTE}/{self.branch}")
            self.landed = True
            return 0
        if code != 3:
            self.refused = push_refusal(o + e)
            self.say(f"kbgit.py sync exit {code}: nothing pushed to {self.branch}" +
                     (f" (refused for want of rights: {self.refused})" if self.refused else "") +
                     ("" if report else f"\n{(o + e).strip()[-600:]}"))
            return code
        self.git("rebase", "--abort")
        if self.branch != BRANCH:
            self.say(f"conflict with {REMOTE}/{self.branch}: nothing pushed (this session pushes to its working "
                     f"branch only); its findings stay pending")
            return 1
        branch = CONFLICT_BRANCH_PREFIX + run_id
        argv = ["push"]
        for opt in MR_OPTIONS:
            argv += ["-o", opt]
        code, o, e = self.git(*argv, REMOTE, f"{mine}:refs/heads/{branch}")
        if code:
            self.refused = push_refusal(o + e)
            self.say(f"conflict, and the push of {branch} failed: {(o + e).strip()[-300:]}")
            return 1
        self.say(f"conflict: pushed {branch} with a merge request for {BRANCH}; its findings stay pending")
        return 0

    def check_ci(self, url):
        """Before any new push: the CI of the last automatic commit's push. Red: a revert commit (an int exit code
        is returned); pending: None (nothing pushed this run); else True."""
        last = self.last_automatic()
        if last is None:
            return True
        sha, values, commits = last
        if "revert" in values:
            return True
        verdict, detail, pipe = ci_pipeline(url, commits[-1], self.run)
        if verdict == "skip":
            self.say(f"note: CI status not checked: {detail}")
            return True
        if verdict == "pending":
            self.say(f"CI of the last automatic commit {sha[:9]} is not finished ({detail}); nothing pushed this run")
            return None
        if verdict == "red" and values == ["querylog"]:
            self.say(f"note: CI of the last automatic commit {sha[:9]} is red ({detail}); it changed only "
                     f"{STORE_REL}, whose files a revert keeps: nothing to revert")
            return True
        if verdict == "red":
            self.say(f"CI of the last automatic commit {sha[:9]} is red ({detail}): reverting it")
            failure, fp = pipeline_failure(url, pipe or {}, self.run)
            return self.revert(sha, commits, detail, {**(pipe or {}), "failure": failure, "fingerprint": fp})
        return True

    def file_bug(self, sha, applied, pipe):
        """One bug item (severity S2) in the worktree for the red pipeline of the reverted push, unless the
        backlog already names that pipeline; its id, or None. Its repro is backlog.py red-pipeline --status: it fails
        while main's latest finished pipeline is red."""
        import backlog
        bl = backlog.Backlog(self.wt)
        pid = pipe.get("id") if pipe.get("id") is not None else f"of commit {sha[:12]}"
        marker = f"pipeline {pid}"
        if any(backlog.names_pipeline(it, marker) for it in bl.items.values()):
            return None
        fp = pipe.get("fingerprint")
        dup = backlog.bug_with_fingerprint(bl, fp) if fp else None
        if dup:  # an open bug already carries this way of failing: the pipeline joins it
            backlog.add_pipeline(bl, dup, pid)
            return dup
        ids = sorted(applied)
        extra = (f"Its push {sha[:12]} was reverted (KB-Auto: revert); reverted findings: "
                 f"{', '.join(ids) or 'none applied'}; the pipeline's status was "
                 f"{pipe.get('status') or 'failed'}."
                 + (f" It failed first on: {pipe['failure']}." if pipe.get("failure") else ""))
        it = backlog.red_bug(pid, sha, "S2", (), pipe.get("url"), extra, fingerprint=fp)
        it["title"] = f"Red main {marker}: query log push {sha[:9]} reverted"
        bl.save(it)
        return it["id"]

    def revert(self, sha, commits, detail, pipe=None):
        """A revert commit (KB-Auto: revert) of the automatic push `commits` that keeps the store's files, with one
        findings file recording apply-failed for every finding those commits applied and one bug item (severity
        S2, repro: main's latest pipeline status) naming the failed pipeline and the reverted findings."""
        code, o, e = self.git("revert", "--no-commit", *reversed(commits))
        if code:
            self.git("revert", "--abort")
            self.say(f"the revert of {sha[:9]} does not apply cleanly; nothing pushed ({(o + e).strip()[-200:]})")
            return 1
        self.git("checkout", "HEAD", "--", STORE_REL)
        store = self.wt / STORE_REL
        added = self.git("diff", "--name-only", "--diff-filter=A", f"{commits[0]}^", commits[-1], "--",
                         f"{STORE_REL}/{FINDINGS}")[1].split()
        applied = {}
        for f in added:
            try:
                objs = load_run(self.wt / f)
            except (OSError, ValueError):
                continue
            for _, rec in objs[1:]:
                if rec.get("state") == "applied" and isinstance(rec.get("id"), str):
                    applied[rec["id"]] = rec
        run_id = f"revert-{sha[:12]}"
        if applied:
            new = [{**{k: v for k, v in r.items() if k != "observed"}, "state": APPLY_FAILED,
                    "observed": {"ci": detail[:200], "commit": sha[:12]}} for r in applied.values()]
            run_id, _ = write_findings(store, store_entries(store), new, (APPLY_FAILED,),
                                       self.git("rev-parse", "HEAD")[1].strip())
        filed = self.file_bug(sha, applied, pipe or {})
        body = (f"This reverts commit {sha}" + (f" and the {len(commits) - 1} commit(s) after it" if len(commits) > 1
                                                else "") +
                f".\n\nIts pipeline is red ({detail}). The store's files stay; the {len(applied)} finding(s) it "
                f"applied are recorded {APPLY_FAILED} and are never applied again." +
                (f" Bug item {filed} records the red pipeline." if filed else ""))
        if self.commit(f"revert: query log commit {sha[:9]}", body, ["revert"]):
            return 1
        return self.deliver(run_id)

    def __call__(self):
        code, url, _ = self.git("remote", "get-url", REMOTE, cwd=self.home)
        if code:
            self.say(f"refused: {self.home} is not a git clone with a remote {REMOTE}")
            return 2
        if kbpublic.is_public(REMOTE, str(self.home), url.strip()):
            self.say(f"refused: {REMOTE} ({url.strip()}) is the public home, which never gets {STORE_REL} "
                     f"(kb/_self/git.md, Public home); the run files stay in the local store and the spool")
            return 2
        if self.cloud:
            branch = self.working_branch()
            if branch is None:
                self.say("refused: a cloud session pushes to the branch it has checked out, and HEAD is detached")
                return 2
            self.branch = branch
            if branch != BRANCH:
                self.say(f"cloud session: automatic commits go to its working branch {branch}")
        code, o, e = self.fetch()
        if code:
            self.say(f"git fetch {REMOTE} failed; nothing pushed ({(o + e).strip()[-300:]})")
            return 1
        code, o, e = self.reset()
        if code:
            self.say(f"the worktree {self.wt} could not be set to {self.up}: {(o + e).strip()[-300:]}")
            return 1
        delivered, new, kept = self.local_files()
        self.forget(delivered)
        ok = self.check_ci(url.strip())
        if ok is None:
            return 0
        if ok is not True:
            return ok
        hold = self.held()
        if hold:
            self.say(f"{len(hold)} finding(s) wait on a {CONFLICT_BRANCH_PREFIX} branch and are left alone")
        store = self.wt / STORE_REL
        if new and self.bring(new, kept):
            return 1
        code = self.apply_step(self.wt, store, hold, self.out)
        if code:
            return code
        paths = self.changed()
        if not paths and not new:
            self.say("nothing to push")
            return 0
        runs = [Path(p).stem for p in paths if p.startswith(f"{STORE_REL}/{FINDINGS}/") and p.endswith(".jsonl")]
        run_id = max(runs or [Path(rel).stem for _, rel, _ in new]
                     or [self.git("rev-parse", "--short=12", "HEAD")[1].strip()])
        if paths:
            try:
                kinds = auto_kinds(paths)
            except ValueError as e:
                self.say(f"refused: apply changed {e}, which it never writes; nothing committed")
                return 1
            edits = self.edited(paths)
            if edits:
                self.say("refused: " + "; ".join(edits[:3]) + "; nothing committed")
                return 1
            body = (f"Automatic commit of querylog.py apply --push, findings run {run_id}: the findings learn wrote, "
                    "the eval rows with their fixes, gap entries, opt-in research, and the findings file that "
                    "records each outcome (kb/_self/querylog.md, Delivery).")
            if self.commit(f"chore(kb): query log apply {run_id}", body, kinds):
                return 1
        code = self.deliver(run_id)
        if self.landed:
            self.forget(set().union(*(ids for _, _, ids in new)))
        return code


def push(home=None, qdir=None, run=None, apply_step=None, out=print, now_dt=None, root=None):
    """`apply --push`: under the distill lock, the CI check of the last automatic commit (a revert when red), then in
    the worktree beside the spool the local store's new files (a commit of their own), learn and apply, one commit
    with its KB-Auto trailer, and kbgit.py sync --push to origin; the spool rows of pushed entries go after it. In a
    plugin host (no `home`, this copy running as the plugin) the push runs from the managed clone (host_push).
    0 done (pushed, nothing to push, CI pending, or a conflict branch pushed), 1 a step failed, 2 refused, 3 another
    distill or push holds the lock."""
    qdir = Path(qdir or places()[0])
    lock = acquire(qdir)
    if lock is None:
        out("apply --push: another distill or push holds the lock")
        return 3
    try:
        if home is None and plugin_data() is not None:
            return host_push(qdir, run or run_cmd, apply_step, out, now_dt, root)
        return Pusher(home or HOME, qdir, run or run_cmd, apply_step, out, now_dt)()
    finally:
        release(lock)


# ---------------------------------------------------------------- plugin hosts

def install_url(root=None, run=None):
    """The git url the plugin copy at `root` (default CLAUDE_PLUGIN_ROOT, `<plugins>/cache/<marketplace>/<plugin>/
    <version>`) was installed from, or None: its marketplace's `source` in <plugins>/known_marketplaces.json (a `git`
    source's `url`, a `github` source's repository over https), else the `origin` url of the marketplace's git
    clone or directory (its `installLocation`, `marketplaces/<name>`)."""
    run = run or run_cmd
    root = root or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    parts = Path(os.path.normpath(str(root))).parts
    if len(parts) < 5 or parts[-4] != "cache":
        return None
    plugins, name = Path(*parts[:-4]), parts[-3]
    known = read_json(plugins / "known_marketplaces.json", {})
    entry = known.get(name) if isinstance(known, dict) else None
    entry = entry if isinstance(entry, dict) else {}
    src = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    if src.get("source") == "git" and isinstance(src.get("url"), str) and src["url"].strip():
        return src["url"].strip()
    if src.get("source") == "github" and isinstance(src.get("repo"), str) \
            and re.fullmatch(r"[\w.-]+/[\w.-]+", src["repo"]):
        return f"https://github.com/{src['repo']}.git"
    for d in (entry.get("installLocation"), src.get("path"), plugins / "marketplaces" / name):
        if isinstance(d, (str, Path)) and str(d) and (Path(d) / ".git").exists():
            code, o, _ = run(["git", "remote", "get-url", REMOTE], cwd=str(d))
            if code == 0 and o.strip():
                return o.strip()
    return None


def managed_clone(qdir, url, run, out):
    """The clone of `url` under `qdir` (CLONE_NAME), made on first use without a checkout (the worktree beside the
    spool is where commits are made) and pointed at `url` when the install source moved; None when `git clone`
    failed (nothing is left behind)."""
    clone = Path(qdir) / CLONE_NAME
    if (clone / ".git").exists():
        code, o, _ = run(["git", "remote", "get-url", REMOTE], cwd=str(clone))
        if code or o.strip() != url:
            run(["git", "remote", "set-url", REMOTE, url], cwd=str(clone))
        return clone
    if clone.exists():
        shutil.rmtree(clone, ignore_errors=True)
    clone.parent.mkdir(parents=True, exist_ok=True)
    code, o, e = run(["git", "clone", "--quiet", "--no-checkout", url, str(clone)], cwd=str(clone.parent))
    if code:
        shutil.rmtree(clone, ignore_errors=True)
        out(f"apply --push: git clone of the install source failed; nothing pushed ({(o + e).strip()[-300:]})")
        return None
    return clone


def disable(qdir, why, out):
    """Logging off for good: the DISABLED marker (why and when) beside the spool, and the spool deleted."""
    qdir = Path(qdir)
    write_text(qdir / DISABLED_NAME, f"push refused for want of rights on {now()[:10]}: {why}\n")
    shutil.rmtree(qdir / "spool", ignore_errors=True)
    out(f"apply --push: the push was refused for want of rights ({why}): wrote {DISABLED_NAME} and deleted the "
        "spool; this host logs nothing from now on")


def host_push(qdir, run=None, apply_step=None, out=print, now_dt=None, root=None):
    """The push of a plugin host, whose querylog directory `qdir` is under ${CLAUDE_PLUGIN_DATA}: the managed clone
    of the install source (install_url, managed_clone), then the push of `apply --push` from it, the research
    setting and count read from `qdir`. A push refused for want of rights writes DISABLED and deletes the spool
    (disable); a network error or a red gate leaves both. Runs under the distill lock."""
    run = run or run_cmd
    url = install_url(root, run)
    if not url:
        out("apply --push: refused: the plugin's install source is not recorded (known_marketplaces.json, the "
            "marketplace clone); nothing pushed")
        return 2
    clone = managed_clone(qdir, url, run, out)
    if clone is None:
        return 1
    p = Pusher(clone, qdir, run, apply_step, out, now_dt, research=["--plugin-data", str(qdir)], cloud=False)
    rc = p()
    if p.refused:
        disable(qdir, p.refused, out)
    return rc
