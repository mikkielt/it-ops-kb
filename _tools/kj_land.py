"""A land job across its merge request (stdlib only; kb/_self/coordination.md, section "Operation jobs: kbjob.py serve").

  drive(job, run_pass, merged, sleep, post, out, poll)  -> (exit, state): the whole of one land job

`land` of a code item is two passes with its merge request between them. The job layer runs it as one job: the first pass
(`backlog.py land ID --wait-merge 0`, which pushes the `code/<id>` branch and stops), a wait as `waiting-merge` while the
request merges, and the second pass (the same command, which then finishes the item as a content landing). The wait takes
no executor slot and no landing lock: no child runs during it, the executor only reads the integration main every POLL_S
seconds for up to the job's `wait_merge` option (WAIT_MERGE_S when it names none). The job never merges the request: the
agent's one merge is `backlog.py merge ID`, the operator's the forge's. A content landing is one pass and never waits.

The callbacks are the executor's (`kj_exec.LandRun`) or a test's:

  run_pass(second)  -> (exit, text, pending): one pass of the CLI, SECOND true for the pass after the wait; TEXT its output;
                       PENDING (shas, branch) as `bl_land.pending_merge` reads it when the first pass left a merge request
                       to wait for, else None
  merged(shas)      -> whether every one of SHAS is on the integration main (`bl_land.merged_on_main`)
  sleep(seconds)    -> waits
  post(state, **f)  -> moves the job: running, waiting-merge (step `merge:<branch>`, pending (shas, branch)), then succeeded,
                       refused or failed with the exit and the step `kj_exec.classify` names

A job `drive` is given in waiting-merge with a recorded `pending` (`{shas, branch}`: an executor restarted) goes on from the
wait without a first pass.
"""
import sys

POLL_S = 60  # seconds between two reads of the integration main (bl_land.WAIT_POLL)
WAIT_MERGE_S = 1800  # the wait when the job names no `wait_merge` option (bl_land.WAIT_MERGE_DEFAULT)


def recorded_pending(job):
    """(shas, branch) a job in waiting-merge recorded, else None."""
    pending = job.get("pending")
    if job.get("state") == "waiting-merge" and isinstance(pending, dict) and pending.get("shas") and pending.get("branch"):
        return list(pending["shas"]), pending["branch"]
    return None


def finish(code, text, post):
    """Move the job to the state `kj_exec.classify` gives for a pass that ended with exit CODE and output TEXT: (exit, state)."""
    import kj_exec  # imported here: kj_exec imports this module
    state, step = kj_exec.classify(code, text)
    post(state, exit=code, **({"step": step} if step else {}))
    return code, state


def drive(job, run_pass, merged, sleep, post, out=None, poll=POLL_S):
    """Run the land JOB (the job record: job, subject, options, and for a restarted one state and pending) to its end through
    the callbacks above: (exit, state). The first pass; when it left a merge request (and the wait is above 0 s), waiting-merge
    with the branch in the step and a read of the integration main every POLL seconds for up to `wait_merge` seconds, then
    running and the second pass; a wait that runs out ends refused at step wait-merge with the text land says for it."""
    out = out or sys.stdout
    bound = (job.get("options") or {}).get("wait_merge", WAIT_MERGE_S)
    pending = recorded_pending(job)
    if pending is None:
        post("running")
        code, text, found = run_pass(False)
        if code != 0 or not found or not bound:
            return finish(code, text, post)
        pending = (list(found[0]), found[1])
        post("waiting-merge", step=f"merge:{pending[1]}", pending=pending)
    shas, branch = pending
    print(f"land: wait-merge: reading the integration main every {poll} s for up to {bound} s for the merge request of "
          f"branch {branch}", file=out, flush=True)
    waited = 0
    while not merged(shas):
        if waited + poll > bound:
            print(f"land stopped at step wait-merge: the merge request of branch {branch} has not merged within {bound} s: "
                  f"merge it (backlog.py merge {job.get('subject')}), then submit land {job.get('subject')} again",
                  file=out, flush=True)
            post("refused", exit=1, step="wait-merge")
            return 1, "refused"
        sleep(poll)
        waited += poll
    print("land: merged on the integration main: second pass", file=out, flush=True)
    post("running")
    code, text, _ = run_pass(True)
    return finish(code, text, post)
