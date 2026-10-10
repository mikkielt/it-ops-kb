"""The one place `backlog.py` reads a forge (kb/_self/backlog.md, Project settings; kb/_self/tools.md): a merge request
by branch or title prefix (merged, opened with its pipeline status and detailed merge status, closed), the newest
pipeline of a ref, and the merge of the item's own `code/<id>` request. The forge is the `forge` setting of
backlog.json (`gitlab`, read and merged through glab; `github`, read through gh, whose merge verb refuses, so no agent
merges on the public home) and the project is `forge_project`, else the integration remote's URL. Both arms answer in
GitLab's words (`opened`, `merged`, `closed`; a pipeline `success`, `failed`, `canceled`, `skipped`, `manual`,
`running`, `pending`), so a caller reads one vocabulary. A read that cannot be made raises `ForgeError`; no such
request or pipeline is None. Standard library only; imports `bl_base` at load, and `ql_deliver` (the remote url's
parser), `kbpublic` and `kg_lane` where it reads them, never `backlog`.
"""
import json, re, urllib.parse
from collections import namedtuple
from pathlib import Path

import bl_base
from bl_base import Refused, setting

LIST_LIMIT = 100  # merge requests read to find one: newest first
STATE_ORDER = ("opened", "merged", "closed")  # which request of a branch with several answers: an open one, else a merged one
GH_REQUEST_FIELDS = "number,title,headRefName,state,url,mergedAt,mergeStateStatus,autoMergeRequest,statusCheckRollup"
GH_MERGEABLE = ("CLEAN", "UNSTABLE", "HAS_HOOKS")  # mergeStateStatus values of a pull request that can merge now
GH_STATES = {"OPEN": "opened", "MERGED": "merged", "CLOSED": "closed"}

Target = namedtuple("Target", "forge host project")
# state: opened, merged or closed; pipeline: the status of the request's head pipeline or None; merge_status: the
# forge's own word (GitLab's detailed_merge_status, GitHub's mergeStateStatus); mergeable: it can merge now
Request = namedtuple("Request", "state iid title branch url pipeline merge_status mergeable auto_merge merged_at")
Pipeline = namedtuple("Pipeline", "id sha status url ref")


class ForgeError(Exception):
    """The forge could not be read: the CLI is not installed or signed in, a call failed, or its answer is no JSON
    of the shape."""


def last_line(text, fallback):
    return ((text or "").strip().splitlines() or [fallback])[-1][:80]


def as_json(code, out, err, name, kind):
    """The JSON value (an instance of KIND) a CLI call answered, or ForgeError naming the call."""
    if code:
        raise ForgeError(f"{name} failed ({last_line(err, 'not installed')})")
    try:
        data = json.loads(out)
    except ValueError:
        data = None
    if not isinstance(data, kind):
        raise ForgeError(f"{name} answered no JSON {kind.__name__} ({last_line(err, 'unreadable')})")
    return data


def newest_request(found, key):
    """The one request of FOUND (dicts) the caller means: an open one, else a merged one, else a closed one, the
    highest number first (`key` names the field of the number)."""
    for want in STATE_ORDER:
        mine = [m for m in found if m.get("state") == want and isinstance(m.get(key), int)]
        if mine:
            return max(mine, key=lambda m: m[key])
    return None


class Glab:
    """GitLab, through `glab api` for reads and `glab mr merge` for the merge."""
    merge_refusal = None

    def __init__(self, target, run, cwd=None):
        self.target, self.run, self.cwd = target, run, cwd
        self.quoted = urllib.parse.quote(target.project, safe="")

    def api(self, path, kind):
        code, out, err = self.run(["glab", "api", "--hostname", self.target.host, path], cwd=self.cwd)
        return as_json(code, out, err, "glab api", kind)

    def request(self, branch=None, title_prefix=None):
        q = (f"source_branch={urllib.parse.quote(branch, safe='')}" if branch
             else f"search={urllib.parse.quote(title_prefix, safe='')}&in=title")
        listed = self.api(f"projects/{self.quoted}/merge_requests?{q}&state=all&order_by=created_at&sort=desc"
                          f"&per_page={LIST_LIMIT}", list)
        found = [m for m in listed if isinstance(m, dict)
                 and (m.get("source_branch") == branch if branch else str(m.get("title", "")).startswith(title_prefix))]
        mr = newest_request(found, "iid")
        if mr is None:
            return None
        if mr.get("state") == "opened":  # the list holds no head pipeline: the single request does
            mr = self.api(f"projects/{self.quoted}/merge_requests/{mr['iid']}", dict)
        detailed = mr.get("detailed_merge_status")
        merge_status = detailed if detailed is not None else mr.get("merge_status")
        pipe = mr.get("head_pipeline") if isinstance(mr.get("head_pipeline"), dict) else {}
        return Request(
            state=mr.get("state"), iid=mr.get("iid"), title=mr.get("title"), branch=mr.get("source_branch"),
            url=mr.get("web_url"), pipeline=pipe.get("status"), merge_status=merge_status,
            mergeable=mr.get("state") == "opened" and merge_status in ("mergeable", "can_be_merged"),
            auto_merge=mr.get("merge_when_pipeline_succeeds") is True, merged_at=mr.get("merged_at"))

    def pipeline(self, ref):
        listed = self.api(f"projects/{self.quoted}/pipelines?ref={urllib.parse.quote(ref, safe='')}"
                          f"&order_by=id&sort=desc&per_page=1", list)
        p = next((p for p in listed if isinstance(p, dict)), None)
        return None if p is None else Pipeline(p.get("id"), p.get("sha"), p.get("status"), p.get("web_url"), ref)

    def merge(self, request):
        """(merged, output) of `glab mr merge IID --auto-merge=false --yes`: at once, never queued behind the pipeline."""
        t = self.target
        code, out, err = self.run(["glab", "mr", "merge", str(request.iid), "--auto-merge=false", "--yes",
                                   "-R", f"https://{t.host}/{t.project}"], cwd=self.cwd)
        return code == 0, (out or err or "").strip()


def check_state(check):
    """(unfinished, word) of one GitHub check or run: a check run, a status context (SUCCESS, FAILURE, ERROR, PENDING,
    EXPECTED) or a workflow run. The word is its status when it is unfinished, else its conclusion, lower case."""
    if "state" in check and "status" not in check:
        state = str(check.get("state") or "").lower()
        return state in ("pending", "expected"), state
    status = str(check.get("status") or "").lower()
    return status != "completed", status if status != "completed" else str(check.get("conclusion") or "").lower()


def gh_status(unfinished, word):
    """GitLab's pipeline word for one GitHub run or check (`check_state`'s pair): running when it is in progress,
    pending when it waits, else its conclusion's word."""
    from ql_deliver import GITHUB_RED
    if unfinished:
        return "running" if word == "in_progress" else "pending"
    if word in GITHUB_RED + ("error",):
        return "failed"
    return {"success": "success", "neutral": "success", "cancelled": "canceled", "stale": "canceled",
            "skipped": "skipped", "action_required": "manual"}.get(word, word or None)


def rollup_status(checks):
    """The one pipeline word of a pull request's status check rollup: unfinished while any check is (running when one
    is in progress, else pending), else failed, canceled, manual, skipped (all of them) or success; None for no check."""
    words = [gh_status(*check_state(c)) for c in checks if isinstance(c, dict)]
    if not words:
        return None
    for word in ("running", "pending", "failed", "canceled", "manual"):
        if word in words:
            return word
    return "skipped" if all(w == "skipped" for w in words) else "success"


class Gh:
    """GitHub, through `gh pr list` and `gh run list`; it reads, and its merge verb refuses."""
    merge_refusal = "the gh arm only reads state: no agent merges on the public home, merge the pull request by hand"

    def __init__(self, target, run, cwd=None):
        self.target, self.run, self.cwd = target, run, cwd
        self.repo = f"{target.host}/{target.project}"

    def request(self, branch=None, title_prefix=None):
        argv = ["gh", "pr", "list", "--state", "all", "-L", str(LIST_LIMIT), "-R", self.repo, "--json",
                GH_REQUEST_FIELDS]
        argv += ["--head", branch] if branch else ["--search", f"{title_prefix} in:title"]
        code, out, err = self.run(argv, cwd=self.cwd)
        listed = as_json(code, out, err, "gh pr list", list)
        found = [dict(p, state=GH_STATES.get(p.get("state"), p.get("state"))) for p in listed if isinstance(p, dict)
                 and (p.get("headRefName") == branch if branch else str(p.get("title", "")).startswith(title_prefix))]
        pr = newest_request(found, "number")
        if pr is None:
            return None
        checks = pr.get("statusCheckRollup") if isinstance(pr.get("statusCheckRollup"), list) else []
        merge_status = pr.get("mergeStateStatus")
        return Request(
            state=pr["state"], iid=pr["number"], title=pr.get("title"), branch=pr.get("headRefName"),
            url=pr.get("url"), pipeline=rollup_status(checks), merge_status=merge_status and merge_status.lower(),
            mergeable=pr["state"] == "opened" and merge_status in GH_MERGEABLE,
            auto_merge=bool(pr.get("autoMergeRequest")), merged_at=pr.get("mergedAt"))

    def pipeline(self, ref):
        code, out, err = self.run(["gh", "run", "list", "--branch", ref, "-L", "1", "-R", self.repo, "--json",
                                   "databaseId,headSha,status,conclusion,url"], cwd=self.cwd)
        r = next((r for r in as_json(code, out, err, "gh run list", list) if isinstance(r, dict)), None)
        if r is None:
            return None
        return Pipeline(r.get("databaseId"), r.get("headSha"), gh_status(*check_state(r)), r.get("url"), ref)

    def merge(self, request):
        raise Refused(self.merge_refusal)


def target(root, run=None):
    """The Target of the `forge` setting and the project: `forge_project`, else the integration remote's URL. Refused
    when that remote names no forge project (a local path, no url) or names github.com while `forge` is gitlab."""
    import kbpublic
    from ql_deliver import origin_forge
    run = run or bl_base.run
    remote = kbpublic.integration_remote(root)
    code, url, _ = run(["git", "remote", "get-url", remote], cwd=root)
    url = (url or "").strip()
    if code or not url or url.lower().startswith("file:") or Path(url).exists():
        raise Refused(f"the integration remote {remote} names no forge project ({url or 'no url'})")
    named, host, project = origin_forge(url)
    forge = setting("forge")
    if named == "github" and forge != "github":
        raise Refused(f"the integration remote {remote} is on {host}, and the forge setting is {forge}: "
                      f"set \"forge\": \"github\" in backlog.json")
    return Target(forge, host, setting("forge_project") or project)


def arm(root, run=None):
    """The arm of the configured forge, Glab or Gh, for the project of `target`; `run` is bl_base.run's shape."""
    run = run or bl_base.run
    t = target(root, run)
    return (Gh if t.forge == "github" else Glab)(t, run, cwd=root)


def read_request(root, branch=None, title_prefix=None, run=None):
    """The Request of BRANCH (its source branch) or of the title starting with TITLE_PREFIX, an open one before a
    merged one before a closed one, or None for none. ForgeError when the forge cannot be read; Refused when the
    root's remote names no forge project."""
    if bool(branch) == bool(title_prefix):
        raise ValueError("read_request takes a branch or a title prefix, one of them")
    return arm(root, run).request(branch=branch, title_prefix=title_prefix)


def read_pipeline(root, ref, run=None):
    """The newest Pipeline of REF, or None when it has none. Errors as `read_request`."""
    return arm(root, run).pipeline(ref)


def merge_own(root, branch, run=None):
    """(outcome, request, output) of merging the item's own request: BRANCH must be `code/<id>` of this project,
    another branch is refused, and so is every merge on the gh arm, before any call. The request is read first, as
    auto-merge may have merged it seconds before: outcome `already` for a merged one, `closed`, `none` for no request
    of the branch, else `merged` or `failed` after `glab mr merge`."""
    from kg_lane import CODE_BRANCH_PREFIX
    if not re.fullmatch(re.escape(CODE_BRANCH_PREFIX) + bl_base.id_re().pattern, branch or ""):
        raise Refused(f"{branch!r} is no item's own {CODE_BRANCH_PREFIX}<id> branch: only that one merges")
    a = arm(root, run)
    if a.merge_refusal:
        raise Refused(a.merge_refusal)
    req = a.request(branch=branch)
    if req is None:
        return "none", None, ""
    if req.state == "merged":
        return "already", req, ""
    if req.state == "closed":
        return "closed", req, ""
    ok, text = a.merge(req)
    return ("merged" if ok else "failed"), req, text
