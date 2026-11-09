"""kj_ci: start a GitLab pipeline for a job placed on ci (stdlib only; kb/_self/coordination.md, section "Operation jobs").

A job `kbjob.py submit` places on the ci executor runs in a CI pipeline, and the pipeline is started through GitLab's pipeline
trigger API, `POST <gitlab>/api/v4/projects/<id>/trigger/pipeline`, a form with `token` (the trigger token, read from a file of mode
0600), `ref` (the branch the pushed commit is on) and `variables[KB_JOB]` (the job's id). The `kb-job` job of `.gitlab-ci.yml` runs
only for such a pipeline (`$CI_PIPELINE_SOURCE == "trigger"`) and serves that one job (`kbjob.py serve --kind ci --job $KB_JOB --once`).

  trigger_config(gitlab, project, token_file, ref, plain_http)  -> Config | None: the flags as one value, a kj_ops.Refusal for a bad
                                                                    combination, a url or a token file; None when none is given
  start(remote, record, config)                                 -> reason | None: post the trigger, keep `pipeline` ({id, web_url})
                                                                    in the job's record and `JOB queued step=pipeline-ID` in its
                                                                    events; a failed trigger leaves the job queued and keeps
                                                                    `trigger_reason` (`pipeline trigger failed: HTTP 401`)
  members(body, record)                                         -> BODY (a job's status JSON) with `pipeline` and, for a queued job
                                                                    whose trigger failed, its `reason`

The token is read at the post and is in no record, event, log or message of this module.
"""
import json
import os
import re
import stat
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple
from pathlib import Path

import coord
import kj_ops

TRIGGER_PATH = "/api/v4/projects/{project}/trigger/pipeline"
TIMEOUT_S = 20
PROJECT = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")  # a numeric project id, or a path with namespace
Config = namedtuple("Config", "gitlab project token_file ref")


def branch_of(root):
    """The branch the clone at ROOT is on; a refusal for a detached HEAD, which names no ref a pipeline can start on."""
    found = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(root), capture_output=True, text=True, encoding="utf-8", timeout=30)
    name = found.stdout.strip()
    if found.returncode != 0 or not name or name == "HEAD":
        raise kj_ops.Refusal("no branch to start a pipeline on: pass --ref BRANCH (this clone's HEAD is on none)")
    return name


def trigger_config(root, gitlab, project, token_file, ref, plain_http=False):
    """The Config of --gitlab, --project, --trigger-token-file and --ref (ref defaults to the clone's branch), None when none of the
    first three is given; a kj_ops.Refusal for one or two of them, for a url that is no http(s) url, a plain http one beyond loopback
    without --plain-http, a project that is no id or path, and a token file that is missing, empty, no regular file or open to others."""
    given = [gitlab, project, token_file]
    if not any(given) and ref is None:
        return None
    if not all(given):
        raise kj_ops.Refusal("starting a pipeline needs --gitlab, --project and --trigger-token-file together")
    parts = urllib.parse.urlsplit(gitlab)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise kj_ops.Refusal(f"--gitlab is an http(s) url, not {gitlab[:40]!r}")
    if parts.scheme == "http" and not plain_http and not coord.is_loopback(parts.hostname):
        raise kj_ops.Refusal(coord.plain_http_refusal("--gitlab host", parts.hostname).replace("coord.py: ", ""))
    if not PROJECT.fullmatch(project):
        raise kj_ops.Refusal(f"--project is a project id or its path, not {project[:40]!r}")
    try:
        info = os.stat(token_file)
    except OSError:
        raise kj_ops.Refusal(f"--trigger-token-file {token_file}: no such file") from None
    if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
        raise kj_ops.Refusal(f"--trigger-token-file {token_file} is no regular file with a token in it")
    if os.name == "posix" and info.st_mode & 0o077:
        raise kj_ops.Refusal(f"--trigger-token-file {token_file} has mode {stat.S_IMODE(info.st_mode):04o}: it must be 0600 (no group or other bit)")
    return Config(gitlab.rstrip("/"), project, str(token_file), ref or branch_of(root))


def post(config, job):
    """(pipeline, reason) of the trigger call for JOB: the pipeline {id, web_url} GitLab answered, else None and a reason with the HTTP status
    (or the kind of the network error), never the token or the url's query."""
    token = Path(config.token_file).read_text(encoding="utf-8").strip()
    url = config.gitlab + TRIGGER_PATH.format(project=urllib.parse.quote(config.project, safe=""))
    form = urllib.parse.urlencode({"token": token, "ref": config.ref, "variables[KB_JOB]": job}).encode("utf-8")
    request = urllib.request.Request(url, data=form, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as reply:
            body = json.loads(reply.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as error:
        return None, f"pipeline trigger failed: HTTP {error.code}"
    except (urllib.error.URLError, OSError, ValueError) as error:
        return None, f"pipeline trigger failed: {type(getattr(error, 'reason', error)).__name__}"
    if not isinstance(body, dict) or not isinstance(body.get("id"), int):
        return None, "pipeline trigger failed: the reply names no pipeline id"
    return {"id": body["id"], "web_url": str(body.get("web_url") or "")}, None


def start(remote, record, config):
    """Start the pipeline of the job RECORD (queued, placed on ci) on the queue REMOTE (`kj_store.Remote` or `LocalRemote`): None when
    started, the reason when the trigger failed. A job that has a pipeline starts none. The job stays queued either way: the pipeline's
    own `kb-job` takes it."""
    if record.get("pipeline"):
        return None
    pipeline, reason = post(config, record["job"])
    if pipeline is None:
        remote.amend(record["job"], trigger_reason=reason)
        remote.note(record["job"], "pipeline-trigger-failed")
        return reason
    remote.amend(record["job"], pipeline=pipeline, trigger_reason=None)
    remote.note(record["job"], f"pipeline-{pipeline['id']}")
    return None


def members(body, record):
    """BODY, the status JSON of a job, with the member `pipeline` ({id, web_url}) its record keeps and, for a job still queued after a
    failed trigger, the member `reason` (the HTTP status). BODY as it is for a job with neither."""
    record = record or {}
    out = dict(body)
    if isinstance(record.get("pipeline"), dict):
        out["pipeline"] = record["pipeline"]
    elif record.get("trigger_reason") and body.get("state") == "queued":
        out["reason"] = record["trigger_reason"]
    return out
