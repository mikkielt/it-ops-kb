"""The query log's delivery (kb/_self/querylog.md, Delivery): `apply --push`, and the push of mode `auto` after a
distill. Under the distill lock, in the worktree beside the spool reset to origin/main: the CI check of the last
automatic commit (a revert when red), the local store's new files gated, the worktree's own learn and apply, one
commit of all of them and one `kbgit.py sync --push` to origin only. A conflict sync cannot resolve goes to a
`querylog/<run-id>` branch with the merge-request push options. Plugin hosts push from a managed clone of their install source; cloud
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
from ql_store import (APPLY_FAILED, FINDINGS, LEARN_STATES, OPS, USAGE, WORK, finding_states, findings_files,
                      leak_problems, load_run, ops_files, run_files, store_entries, usage_files, work_files,
                      write_findings)

REMOTE = kbpublic.integration_remote(HOME)  # the integration remote of this clone (git config kb.integrationRemote); a Pusher asks its own home
BRANCH = "main"  # the branch automatic commits land on
CONFLICT_BRANCH_PREFIX = "querylog/"  # a conflict sync cannot resolve goes to querylog/<run-id>, as a merge request
MR_OPTIONS = ("merge_request.create", f"merge_request.target={BRANCH}")  # push options: no token, no auto-merge
FALLBACK_GITLAB_HOST = "gitlab.com"  # only when origin's url names no host
WORKTREE_NAME = "worktree"  # beside the spool: automatic commits are made there, never in the person's checkout
CLONE_NAME = "clone"  # beside a plugin host's spool: its managed clone of the repository the plugin was installed from
GITLAB_RED = ("failed",)
GITLAB_UNFINISHED = ("created", "waiting_for_resource", "preparing", "waiting_for_callback", "pending", "running",
                     "canceling", "scheduled")
GITHUB_RED = ("failure", "timed_out", "startup_failure")  # conclusions of a completed run
# The jobs that must succeed for a GitLab pipeline to count as green. None: every job in .gitlab-ci.yml is manual
# with allow_failure, so a pipeline is never held for a job nobody started, and its own status says success whatever
# the jobs did. A job whose script ran and failed makes it red (whichever job, kb-tests-windows included). Naming jobs
# here makes a pipeline in which one did not succeed `unverified`.
GATE_JOBS = ()
# A failed job's failure_reason when someone started it and it failed for its own sake: its script exited non-zero,
# ran past the job timeout, or got stuck (no runner took it in time).
RAN_AND_FAILED = ("script_failure", "job_execution_timeout", "stuck_or_timeout_failure")
SHA_PIPELINES = 20  # pipelines of one commit read to find the newest one in which a job ran
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


def latest_jobs(jobs):
    """{name: the newest entry of that job} of a GitLab job list (newest first); {} for no list."""
    latest = {}
    for j in jobs if isinstance(jobs, list) else []:
        if isinstance(j, dict) and j.get("name") and j["name"] not in latest:
            latest[j["name"]] = j
    return latest


def job_ran(j):
    """Whether a GitLab job ran: it has a start time, succeeded, is running, or failed for a reason in
    RAN_AND_FAILED, and was not canceled. A manual, skipped or created job, a canceled one (started or not: someone
    stopped it, so it holds no verdict) and one that failed without running (such as ci_quota_exceeded) did not."""
    s = j.get("status")
    if s == "canceled":
        return False
    return bool(j.get("started_at")) or s in ("success", "running") or (
        s == "failed" and j.get("failure_reason") in RAN_AND_FAILED)


def job_decided(j):
    """Whether a GitLab job reached a verdict on itself: it succeeded, or failed for a reason in RAN_AND_FAILED.
    `red-pipeline --job` reads only a pipeline where its job did, and a red-main bug's repro names a job only when it
    failed so: a job canceled, manual or skipped (started or not) or failed without its script (ci_quota_exceeded,
    runner_system_failure) says nothing of it."""
    s = j.get("status")
    return s == "success" or (s == "failed" and j.get("failure_reason") in RAN_AND_FAILED)



def any_ran(jobs):
    """Whether a job of a GitLab job list ran (its newest entry by name, `job_ran`)."""
    return any(job_ran(j) for j in latest_jobs(jobs).values())


def job_verdict(jobs, gate=None):
    """(verdict, failed, unpassed) of a GitLab pipeline read by its jobs (the list `pipelines/<id>/jobs` answers,
    newest first; None when it could not be read), not by its status:
    - `red` when a job's script ran and failed (status `failed`, failure_reason in RAN_AND_FAILED), whichever job;
    - else `pending` when a gate job (GATE_JOBS, none by default) is unfinished;
    - else `unverified` when a gate job did not succeed: manual, skipped, canceled, failed without running (such as
      ci_quota_exceeded), missing from the pipeline, or the list unreadable;
    - else `ok`.
    `failed` names the jobs whose script failed, sorted; `unpassed` says how each gate job did not succeed
    (`kb-tests manual`, `kb-tests failed (ci_quota_exceeded)`, `kb-trailers not in the pipeline`)."""
    gate = GATE_JOBS if gate is None else gate
    if not isinstance(jobs, list):
        return "unverified", [], ["the pipeline's jobs could not be read"]
    latest = latest_jobs(jobs)
    failed = sorted(n for n, j in latest.items()
                    if j.get("status") == "failed" and j.get("failure_reason") in RAN_AND_FAILED)
    unpassed, waiting = [], False
    for name in gate:
        j = latest.get(name)
        if j is None:
            unpassed.append(f"{name} not in the pipeline")
            continue
        s = j.get("status")
        if s == "success":
            continue
        waiting = waiting or s in GITLAB_UNFINISHED
        why = j.get("failure_reason") if s == "failed" else None
        unpassed.append(f"{name} {s}" + (f" ({why})" if why else ""))
    if failed:
        return "red", failed, unpassed
    if waiting:
        return "pending", [], unpassed
    return ("unverified" if unpassed else "ok"), [], unpassed


def gitlab_jobs(host, quoted, pid, run):
    """The jobs of GitLab pipeline `pid` in project `quoted` (URL-encoded path), as `glab api` answers them, or None
    when the call fails or answers no JSON list."""
    code, o, _ = run(["glab", "api", "--hostname", host, f"projects/{quoted}/pipelines/{pid}/jobs?per_page=100"])
    try:
        data = json.loads(o) if code == 0 else None
    except ValueError:
        data = None
    return data if isinstance(data, list) else None


# ---------------------------------------------------------------- ops rows of the CI reads and the other tools

CI_STATE_FILE = "ci-state.json"  # beside the spool: the last state each pipeline was recorded in, so only a change is a row
CI_STATES_KEPT = 50  # pipelines that file remembers
CI_ROW_STATES = ("red", "pending", "green", "unverified")  # `ok` is `green`; `none` and `skip` read no pipeline


TEST_SPOOL_ENV = "KB_OPS_TEST_SPOOL"  # set by a test that points the spool at a directory of its own (and its subprocesses)


def inside_test():
    """True in a run started by a test (pytest sets PYTEST_CURRENT_TEST, which a subprocess inherits): its ops rows
    never reach the clone's own spool, as `tests.inside_test`; False when the test has set TEST_SPOOL_ENV, having
    pointed CLAUDE_PLUGIN_DATA at a spool of its own."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and os.environ.get(TEST_SPOOL_ENV) != "1"


def ops_row(event, **fields):
    """Append one ops row (`ql_capture.record("ops", ...)`, which writes only a closed event with its closed keys) and
    return it; None when capture is off, when the row breaks its shape, inside a test run (its rows never reach the
    clone's own spool, as `tests.record_run`) or on any error: a tool never fails or waits for its log."""
    try:
        if inside_test():
            return None
        import ql_capture
        return ql_capture.record("ops", event=event, **fields)
    except Exception:  # noqa: BLE001 - see the docstring
        return None


def is_job_list(argv):
    """Whether a forge call reads one pipeline's job list (`glab api projects/<p>/pipelines/<id>/jobs`, `gh run view
    <id> --json jobs`), not a job's log or the pipeline list."""
    a = [str(x) for x in argv]
    return (a[:2] == ["glab", "api"] and any("/pipelines/" in x and "/jobs" in x for x in a)) or (
        a[:3] == ["gh", "run", "view"] and "jobs" in a)


def counting(run):
    """(run2, calls): `run2` is `run` and adds one to `calls[0]` for each job-list call (`is_job_list`) it makes."""
    calls = [0]

    def counted(argv, *args, **kw):
        if is_job_list(argv):
            calls[0] += 1
        return run(argv, *args, **kw)
    return counted, calls


def record_pipeline(pid, state, calls, sha=None):
    """Append the `ci.pipeline` ops row of pipeline `pid` read in `state` (`red`, `pending`, `green` or `unverified`; `ok`
    is `green`) with the `calls` it made for job lists, only when `pid` was last recorded in another state or never
    (the file CI_STATE_FILE beside the spool keeps the last CI_STATES_KEPT). Nothing when capture is off or inside a
    test run; never raises."""
    try:
        state = "green" if state == "ok" else state
        if inside_test() or pid is None or state not in CI_ROW_STATES:
            return None
        import ql_capture
        spool = ql_capture.spool_dir()
        if spool is None:
            return None
        path = Path(spool).parent / CI_STATE_FILE
        seen = read_json(path, {})
        seen = seen if isinstance(seen, dict) else {}
        key = str(pid)
        if seen.get(key) == state:
            return None
        seen.pop(key, None)
        seen[key] = state
        write_text(path, json.dumps(dict(list(seen.items())[-CI_STATES_KEPT:]), separators=(",", ":")))
        sha = str(sha)[:12] if sha and ql_capture.OPS_SHA.fullmatch(str(sha)[:12]) else None
        return ops_row("ci.pipeline", state=state, calls=int(calls or 0), sha=sha)
    except Exception:  # noqa: BLE001 - see ops_row
        return None


def ci_pipeline(url, sha, run):
    """(verdict, detail, pipeline) of the CI of commit `sha` on origin's forge: verdict `red`, `pending`, `ok`,
    `unverified` (GitLab: a gate job did not succeed, `job_verdict`), `none` (no pipeline) or `skip` (no signed-in
    glab or gh, or the call failed: the check is skipped). On GitLab it reads the commit's newest pipeline that failed,
    is unfinished or in which a job ran (`job_ran`), else its newest one: every job is manual, so a newer pipeline no
    one started hides nothing. One whose status is no failure and not unfinished is read by its jobs. `pipeline` is
    {id, url, status} of the pipeline read (GitHub: the first red run), or None."""
    forge = origin_forge(url)[0]
    run, calls = counting(run)
    data, cli, note = forge_list(
        url, run, lambda repo: ["gh", "run", "list", "--commit", sha, "-R", repo, "--json",
                                "status,conclusion,databaseId,url", "-L", "100"],
        lambda project: f"projects/{project}/pipelines?sha={sha}&per_page={SHA_PIPELINES}")
    if data is None:
        return "skip", note, None
    jobs = None
    if forge == "github":
        runs = [r for r in data if isinstance(r, dict)]
        states = [(r.get("status"), r.get("conclusion")) for r in runs]
        shown = ", ".join(f"{s}/{c}" if c else str(s) for s, c in states)
        pick = next((r for r in runs if r.get("conclusion") in GITHUB_RED), runs[0] if runs else {})
        pipe = {"id": pick.get("databaseId"), "url": pick.get("url"),
                "status": f"{pick.get('status')}/{pick.get('conclusion')}"}
    else:
        _, host, project = origin_forge(url)
        quoted = urllib.parse.quote(project, safe="")
        runs, newest = [], None
        for r in (r for r in data if isinstance(r, dict)):  # newest first
            if r.get("status") in GITLAB_RED + GITLAB_UNFINISHED:  # decided by its status, no job list needed
                runs, jobs = [r], None
                break
            js = gitlab_jobs(host, quoted, r.get("id"), run)
            newest = newest or (r, js)
            if js is None or any_ran(js):  # an unreadable list is no proof that nothing ran
                runs, jobs = [r], js
                break
        if not runs and newest:
            runs, jobs = [newest[0]], newest[1]
        states = [r.get("status") for r in runs]
        shown = ", ".join(map(str, states))
        pipe = {"id": runs[0].get("id"), "url": runs[0].get("web_url"), "status": runs[0].get("status")} if runs else {}
        first = next((r for r in data if isinstance(r, dict)), None)
        if runs and first is not None and first is not runs[0]:
            shown = f"pipeline {pipe['id']}, the newest where a job ran: {shown}"
    if not states:
        return "none", f"no pipeline for {sha[:9]} on {origin_forge(url)[1]}", None
    verdict = pipeline_verdict(forge, states)
    if forge == "gitlab" and verdict == "ok":  # a status that is no failure is read by the pipeline's jobs
        verdict, failed, unpassed = job_verdict(jobs)
        if failed:
            shown += f"; script failed in {', '.join(failed)}"
        elif unpassed:
            shown += f"; {', '.join(unpassed)}"
    record_pipeline(pipe.get("id"), verdict, calls[0], sha)  # a row only when this pipeline's state changed
    return verdict, f"{note}: {shown}", pipe


def pipeline_failure(url, pipe, run):
    """(failure, fingerprint) of the red pipeline `pipe` ({id, ...}) on origin's forge, computed as backlog.py does
    for main's pipeline: the first failed job by name (among the jobs whose script ran and failed, when there are
    any), what failed first in its log (`bl_ci.first_failure`), and
    `bl_ci.failure_fingerprint` of the two. ('', None) when no failed job can be read (no id, a failed call).
    The first failed job's name goes into `pipe["job"]`, which the bug's repro names with `--job`, only when its
    script ran and failed (`job_decided`; on GitHub, any failed job): `--job` reads only a pipeline where the job
    reached a verdict, so a job that failed without running (ci_quota_exceeded, runner_system_failure) leaves the
    repro plain `--status`, which reads the red pipeline itself. On GitLab a job counts by its newest attempt
    (`latest_jobs`): one that failed and was retried to success is no failed job."""
    import bl_ci  # the red-pipeline rules themselves, not the backlog facade, which reaches every bl_ module
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
                          f"projects/{quoted}/pipelines/{pid}/jobs?per_page=100"])  # all jobs: a retry is in it
        key, bad, field, idkey = None, ("failed",), "status", "id"
    try:
        js = json.loads(o) if code == 0 else []
        js = js.get(key, []) if key and isinstance(js, dict) else js
        if forge != "github":
            js = list(latest_jobs(js).values())  # a job that failed and was retried to success is not failed
        failed = [j for j in js if isinstance(j, dict) and j.get(field) in bad and j.get("name")]
    except (ValueError, AttributeError, TypeError):
        failed = []
    failed = [j for j in failed if j.get("failure_reason") in RAN_AND_FAILED] or failed  # a script that ran first
    if not failed:
        return "", None
    first = min(failed, key=lambda j: str(j["name"]))
    if forge == "github" or job_decided(first):
        pipe["job"] = str(first["name"])
    log, jid = "", first.get(idkey)
    if jid is not None:
        argv = (["gh", "api", "--hostname", host, f"repos/{project}/actions/jobs/{jid}/logs"] if forge == "github" else
                ["glab", "api", "--hostname", host, f"projects/{quoted}/jobs/{jid}/trace"])
        code, o, _ = run(argv)
        log = o if code == 0 else ""
    failure = bl_ci.first_failure(log)
    return failure, bl_ci.failure_fingerprint(first["name"], failure)


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
        self.remote = kbpublic.integration_remote(self.home)  # the remote automatic commits go to
        self.branch = BRANCH  # the branch automatic commits are pushed to
        self.up = f"refs/remotes/{self.remote}/{BRANCH}"  # the ref the worktree starts from
        self.landed = False  # set when deliver pushed to self.branch
        self.refused = None  # the push output line that refused a push for want of rights (push_refusal)
        self.now_dt = now_dt  # the time the spool is read at (default: now)

    def git(self, *args, cwd=None):
        return self.run(["git", *args], cwd=str(cwd or self.wt))

    def blob(self, rev, path):
        """(exit code, text, stderr) of the file `path` at `rev`. `cat-file` names the object without checking the
        argument as a file name, which `git show REV:PATH` does and which fails as too long a file name on Windows in a
        deep worktree."""
        return self.git("cat-file", "blob", f"{rev}:{path}")

    def tool(self, name, *args):
        """The worktree's own copy of _tools/NAME, run in the worktree."""
        return self.run([sys.executable, str(self.wt / "_tools" / name), *args], cwd=str(self.wt))

    def say(self, text):
        self.out(f"apply --push: {text}")

    def fetch(self):
        """origin's main and its conflict branches (pruned: a merged branch that GitLab deleted goes); in a cloud
        session on another branch, that branch too, which the worktree then starts from once origin has it."""
        main = f"refs/remotes/{self.remote}/{BRANCH}"
        code, o, e = self.git("fetch", "--quiet", "--prune", self.remote, f"+refs/heads/{BRANCH}:{main}",
                              f"+refs/heads/{CONFLICT_BRANCH_PREFIX}*:refs/remotes/{self.remote}/{CONFLICT_BRANCH_PREFIX}*",
                              cwd=self.home)
        if code or self.branch == BRANCH:
            return code, o, e
        ref = f"refs/remotes/{self.remote}/{self.branch}"
        code, o, e = self.git("fetch", "--quiet", self.remote, f"+refs/heads/{self.branch}:{ref}", cwd=self.home)
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
        findings files the branch adds. OSError when a git call it reads fails (for-each-ref, merge-base, diff) or such
        a file cannot be read, so a held finding is never applied for want of reading it."""
        def failed(what, code, o, e):
            return OSError(f"cannot {what} (git exit {code}): {(o + e).strip()[-300:]}")
        code, o, e = self.git("for-each-ref", "--format=%(refname)", f"refs/remotes/{self.remote}/{CONFLICT_BRANCH_PREFIX}")
        if code:
            raise failed("list the conflict branches", code, o, e)
        ids = set()
        for ref in o.split():
            code, o2, e2 = self.git("merge-base", "--is-ancestor", ref, self.up)
            if code == 0:
                continue
            if code != 1:  # 1: not an ancestor; anything else is an error
                raise failed(f"tell whether {ref} is on {self.up}", code, o2, e2)
            code, o2, e2 = self.git("merge-base", ref, self.up)
            base = o2.strip()
            if code or not base:
                raise failed(f"find the merge base of {ref} and {self.up}", code, o2, e2)
            code, files, e2 = self.git("diff", "--name-only", "--diff-filter=A", base, ref, "--", f"{STORE_REL}/{FINDINGS}")
            if code:
                raise failed(f"list the findings files {ref} adds", code, files, e2)
            for f in files.split():
                code, text, err = self.blob(ref, f)
                if code:
                    raise OSError(f"cannot read {ref}:{f}: {(text + err).strip()[-300:]}")
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
        usage, work or ops sidecar is copied when origin/main lacks its path; a findings file when origin/main lacks its path,
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
        for p in usage_files(local) + work_files(local) + ops_files(local):
            rel = p.relative_to(local).as_posix()
            if not (store / rel).exists():
                new.append((p, rel, set()))
        return delivered, new, kept

    def forget(self, ids):
        """The spool rows of the entries `ids`, whose run file is on origin/main, are deleted."""
        n = spool_delivered(self.qdir, ids, self.now_dt)
        if n:
            self.say(f"deleted the spool rows of {n} entries whose run file is on {self.remote}/{self.branch}")

    def bring(self, new, kept):
        """The local files `new` copied into the worktree's store, then the worktree's `querylog.py check` and the
        leak scan over them, before learn and apply run: the run's one commit holds them. 0, or 1 when a gate fails
        (nothing committed or pushed)."""
        store = self.wt / STORE_REL
        for src, rel, _ in new:
            write_text(store / rel, Path(src).read_text(encoding="utf-8"))
        if kept:
            self.say(f"{len(kept)} local findings file(s) stay local (apply's outcomes, or findings "
                     f"{self.remote}/{BRANCH} already records)")
        code, o, e = self.tool("querylog.py", "check", str(store))
        problems = [ln for ln in o.splitlines() if ln.strip() and not ln.startswith("querylog check:")] if code else []
        if code and not problems:
            problems = [(o + e).strip()[-300:] or f"querylog.py check exit {code}"]
        problems += leak_problems(store, [rel for _, rel, _ in new])
        if problems:
            self.say("refused: the store gates fail on the local store's files; nothing committed or pushed\n  " +
                     "\n  ".join(problems[:10]))
            return 1
        return 0

    @staticmethod
    def brought(new):
        """(what the local files `new` are, in words; the stems of their run files)."""
        runs = sorted(Path(rel).stem for _, rel, _ in new if not rel.startswith((FINDINGS + "/", USAGE + "/", WORK + "/", OPS + "/")))
        found = sum(1 for _, rel, _ in new if rel.startswith(FINDINGS + "/"))
        used = sum(1 for _, rel, _ in new if rel.startswith(USAGE + "/"))
        worked = sum(1 for _, rel, _ in new if rel.startswith(WORK + "/"))
        measured = sum(1 for _, rel, _ in new if rel.startswith(OPS + "/"))
        return (f"{len(runs)} run file(s)" + (f", {found} findings file(s)" if found else "")
                + (f", {used} usage sidecar(s)" if used else "")
                + (f", {worked} work sidecar(s)" if worked else "")
                + (f", {measured} ops sidecar(s)" if measured else "")), runs

    def edited(self, paths):
        """The existing lines the worktree's change removes or edits in an article, a ledger or a source row
        (edit_problems against HEAD): apply's changes add only."""
        out = []
        for p in paths:
            f = self.wt / p
            if self.git("cat-file", "-e", f"HEAD:{p}")[0]:
                continue  # a new file: nothing to remove or edit
            code, old, err = self.blob("HEAD", p)
            if code:
                out.append(f"{p}: cannot read it at HEAD: {(old + err).strip()[-300:]}")
                continue
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
        code, o, e = self.tool("kbgit.py", "sync", "--push", "--remote", self.remote, "--branch", self.branch)
        report = [ln for ln in (o + e).splitlines() if ln.startswith(("gate ", "pushed:", "needs-human:", "CONFLICT"))]
        for ln in report:
            self.out("  " + ln)
        if code == 0:
            self.say(f"pushed {mine[:9]} to {self.remote}/{self.branch}")
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
            self.say(f"conflict with {self.remote}/{self.branch}: nothing pushed (this session pushes to its working "
                     f"branch only); its findings stay pending")
            return 1
        branch = CONFLICT_BRANCH_PREFIX + run_id
        argv = ["push"]
        for opt in MR_OPTIONS:
            argv += ["-o", opt]
        code, o, e = self.git(*argv, self.remote, f"{mine}:refs/heads/{branch}")
        if code:
            self.refused = push_refusal(o + e)
            self.say(f"conflict, and the push of {branch} failed: {(o + e).strip()[-300:]}")
            return 1
        self.say(f"conflict: pushed {branch} with a merge request for {BRANCH}; its findings stay pending")
        return 0

    def check_ci(self, url):
        """Before any new push: the CI of the last automatic commit's push. Red: a revert commit (an int exit code
        is returned); pending or unverified (a gate job did not pass): None (nothing pushed this run); else True."""
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
        if verdict == "unverified":
            self.say(f"CI of the last automatic commit {sha[:9]} is not verified: a gate job did not pass ({detail}); "
                     "nothing pushed this run")
            return None
        if verdict == "red" and values == ["querylog"]:
            self.say(f"note: CI of the last automatic commit {sha[:9]} is red ({detail}); it changed only "
                     f"{STORE_REL}, whose files a revert keeps: nothing to revert")
            return True
        if verdict == "red":
            self.say(f"CI of the last automatic commit {sha[:9]} is red ({detail}): reverting it")
            pipe = dict(pipe or {})
            failure, fp = pipeline_failure(url, pipe, self.run)
            return self.revert(sha, commits, detail, {**pipe, "failure": failure, "fingerprint": fp})
        return True

    def file_bug(self, sha, applied, pipe):
        """One bug item (severity S2) in the worktree for the red pipeline of the reverted push, unless the
        backlog already names that pipeline; its id, or None. Its repro is backlog.py red-pipeline --status --job
        <the first failed job> (plain --status when none was read): it fails until that job passes on main again."""
        import bl_ci
        from bl_base import Backlog
        bl = Backlog(self.wt)
        pid = pipe.get("id") if pipe.get("id") is not None else f"of commit {sha[:12]}"
        marker = f"pipeline {pid}"
        if any(bl_ci.names_pipeline(it, marker) for it in bl.items.values()):
            return None
        fp = pipe.get("fingerprint")
        dup = bl_ci.bug_with_fingerprint(bl, fp) if fp else None
        if dup:  # an open bug already carries this way of failing: the pipeline joins it
            bl_ci.add_pipeline(bl, dup, pid)
            return dup
        ids = sorted(applied)
        extra = (f"Its push {sha[:12]} was reverted (KB-Auto: revert); reverted findings: "
                 f"{', '.join(ids) or 'none applied'}; the pipeline's status was "
                 f"{pipe.get('status') or 'failed'}."
                 + (f" It failed first on: {pipe['failure']}." if pipe.get("failure") else ""))
        it = bl_ci.red_bug(pid, sha, "S2", (), pipe.get("url"), extra, fingerprint=fp, job=pipe.get("job"))
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
        code, url, _ = self.git("remote", "get-url", self.remote, cwd=self.home)
        if code:
            self.say(f"refused: {self.home} is not a git clone with a remote {self.remote}")
            return 2
        if kbpublic.is_public(self.remote, str(self.home), url.strip()):
            self.say(f"refused: {self.remote} ({url.strip()}) is the public home, which never gets {STORE_REL} "
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
            self.say(f"git fetch {self.remote} failed; nothing pushed ({(o + e).strip()[-300:]})")
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
        try:
            hold = self.held()
        except OSError as e:
            self.say(f"the findings a {CONFLICT_BRANCH_PREFIX} branch holds could not be read; nothing pushed ({e})")
            return 1
        if hold:
            self.say(f"{len(hold)} finding(s) wait on a {CONFLICT_BRANCH_PREFIX} branch and are left alone")
        store = self.wt / STORE_REL
        if new and self.bring(new, kept):
            return 1
        code = self.apply_step(self.wt, store, hold, self.out)
        if code:
            return code
        paths = self.changed()
        if not paths:
            self.say("nothing to push")
            return 0
        copied = {f"{STORE_REL}/{rel}" for _, rel, _ in new}
        applied = [p for p in paths if p not in copied]
        runs = [Path(p).stem for p in applied if p.startswith(f"{STORE_REL}/{FINDINGS}/") and p.endswith(".jsonl")]
        run_id = max(runs or [Path(rel).stem for _, rel, _ in new]
                     or [self.git("rev-parse", "--short=12", "HEAD")[1].strip()])
        try:
            kinds = auto_kinds(paths)
        except ValueError as e:
            self.say(f"refused: apply changed {e}, which it never writes; nothing committed")
            return 1
        edits = self.edited(applied)
        if edits:
            self.say("refused: " + "; ".join(edits[:3]) + "; nothing committed")
            return 1
        what, stems = self.brought(new)
        store_part = (f"the local store's {what} ({', '.join(stems) or 'no run file'}), copied into {STORE_REL}/ "
                      "after querylog.py check and the leak scan" if new else "")
        if applied:
            subject = f"chore(kb): query log apply {run_id}"
            body = (f"Automatic commit of querylog.py apply --push, findings run {run_id}: "
                    + (store_part + "; " if store_part else "") +
                    "the findings learn wrote, the eval rows with their fixes, gap entries, opt-in research, and the "
                    "findings file that records each outcome, in one commit (kb/_self/querylog.md, Delivery).")
        else:
            subject = f"chore(kb): query log store, {what}"
            body = f"Automatic commit of querylog.py: {store_part} (kb/_self/querylog.md, Delivery)."
        if self.commit(subject, body, kinds):
            return 1
        code = self.deliver(run_id)
        if self.landed:
            self.forget(set().union(*(ids for _, _, ids in new)))
        return code


def push(home=None, qdir=None, run=None, apply_step=None, out=print, now_dt=None, root=None):
    """`apply --push`: under the distill lock, the CI check of the last automatic commit (a revert when red), then in
    the worktree beside the spool the local store's new files (gated), learn and apply, one commit of all of them
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
            code, o, _ = run(["git", "remote", "get-url", kbpublic.CLONE_REMOTE], cwd=str(d))
            if code == 0 and o.strip():
                return o.strip()
    return None


def managed_clone(qdir, url, run, out):
    """The clone of `url` under `qdir` (CLONE_NAME), made on first use without a checkout (the worktree beside the
    spool is where commits are made) and pointed at `url` when the install source moved; None when `git clone`
    failed (nothing is left behind)."""
    clone = Path(qdir) / CLONE_NAME
    if (clone / ".git").exists():
        code, o, _ = run(["git", "remote", "get-url", kbpublic.CLONE_REMOTE], cwd=str(clone))
        if code or o.strip() != url:
            run(["git", "remote", "set-url", kbpublic.CLONE_REMOTE, url], cwd=str(clone))
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
