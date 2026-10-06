"""The item writers of the kb's backlog (kb/_self/backlog.md, Item commands): new, fmt, claim, release, answer with
its decision recording, set, move, reopen, gate with its size-cap rules, host-check, fire, drop, referrers and goal, with
parse_cmd, the shared write path changed_item(s) and their argument builders. Each writes item files through
changed_items and the shared refusals, so they live together; importing this module registers their commands with
bl_cli. backlog.py, the facade, keeps the usage text, the usage order and main's dispatch.

Standard library only; imports the bl_ modules and never backlog."""
import argparse, copy, re, shlex, subprocess, sys
from pathlib import Path

import bl_authority
import bl_cli
from bl_base import (
    IN_SPRINT, KINDS, PRIORITIES, RESEARCH_CHECKS, REVIEW_CHECKS, Refused, Rejected, SEVERITIES, START_GATE, TEXT_MAX, canonical,
    commit_message, commit_written, git, in_scope, item_file, need, new_id, research_in_planned, say, scope,
    trailer_problem, waits, withhold,
)
from bl_check import (
    ITEM_FILES_ROUTE, item_files_only, noop_warnings, text_only_repro, validate,
)
from bl_land import cleanup_gate_do, run_check, own_failure
from bl_view import (
    is_near, similar,
)
from bl_plan import (
    has_scope, host_gates, stale_touches, tracked_files,
)


# ------------------------------------------------------------------ git and checks

def parse_cmd(s):
    return shlex.split(s, posix=True)


# ------------------------------------------------------------------ commands

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
        rs = {"id": new_id("story"), "kind": "story", "title": f"Research sprint goal: {it['title']}"[:TEXT_MAX],
              "status": "draft", "sprint": it["id"], "goal_research": True, "priority": "P1", "rank": 0,
              "goal": "The sprint goal's open questions are answered with the kb tools first and the live docs for "
                      "the gaps, and the findings are written as kb facts and gap entries through the kb skills, so "
                      "each committed item can name the knowledge it needs.",
              "checks": RESEARCH_CHECKS, "touches": ["kb/public/**"]}
        bl.save(rs)
        say(f"new sprint {bl.label(it['id'])}, review story {bl.label(rv['id'])}, "
            f"research story {bl.label(rs['id'])}")
        commit_written(bl, a, "file", it["id"], [it["id"], rv["id"], rs["id"]])
        return 0
    if a.sprint and kind not in IN_SPRINT:
        raise Rejected(f"new {kind} refuses --sprint: only stories and bugs name a sprint; a {kind} follows its parent's")
    it.update(status="todo" if kind in ("task", "subtask") else "draft", priority=a.priority, rank=a.rank)
    for k in ("parent", "sprint", "goal"):
        if getattr(a, k):
            it[k] = getattr(a, k)
    if it["status"] == "todo" and a.parent in bl.items:  # a task of a planned sprint stays draft until its start
        sp = bl.sprint_of(a.parent)
        if bl.items.get(sp, {}).get("status") == "planned":
            it["status"] = "draft"
    if a.sprint and bl.items.get(a.sprint, {}).get("status") == "active":  # filed into a running sprint: ready now
        it["status"] = "todo"
    if kind == "bug":
        if not a.severity or not a.repro:
            raise Refused("a bug needs --severity and --repro")
        it["severity"] = a.severity
        it["repro"] = {"run": parse_cmd(a.repro)}
        ok, code, out = run_check(bl.root, it["repro"])
        if ok:
            raise Refused(f"--repro passes now (exit {code}): it must fail until the bug is fixed")
        why = own_failure(it["repro"]["run"], code, out, bl.root)
        if why:
            raise Refused(f"--repro fails for its own error, not the defect: {why}")
        why = text_only_repro(it["repro"]["run"])
        if why and not (a.repro_reason or "").strip():
            raise Rejected(f"--repro only matches text in a file ({why}): it proves the text, not the behaviour, and "
                           "can pass on a fix that does not work; run the behaviour (a tool call on a planted "
                           "input, a command with a match, or a test), or state why it cannot with --repro-reason TEXT")
        if (a.repro_reason or "").strip():
            it["repro_reason"] = a.repro_reason.strip()
    elif a.repro_reason:
        raise Rejected("--repro-reason is for a bug's --repro")
    if a.check:
        it["checks"] = [{"run": parse_cmd(c)} for c in a.check]
    warns = noop_warnings(it, out if kind == "bug" else "")
    if a.touch:
        it["touches"] = a.touch
        if kind in ("story", "task", "subtask", "bug") and item_files_only(a.touch):
            warns.append(ITEM_FILES_ROUTE)
    if a.depends:
        it["depends_on"] = a.depends
    bl.save(it)
    errs = [x for x in validate(bl) if x.startswith(it["id"])]
    say(f"new {kind} {bl.label(it['id'])}")
    for x in errs:
        say(f"  to fill in: {x.split(': ', 1)[1]}")
    for x in warns:
        say(f"  warning: {x}")
    for row in filter(is_near, similar(bl, f"{it['title']} {it.get('goal', '')}", exclude={it["id"]})):
        say(f"  warning: near-duplicate of open {bl.label(row[2])} (word overlap {row[0]:.2f}); "
            "drop this one if it is the same work")
    commit_written(bl, a, "file", it["id"])
    return 0


def cmd_fmt(bl, a):
    n = 0
    for iid, it in bl.items.items():
        if bl.raw.get(iid) != canonical(it):
            bl.save(it)
            n += 1
    say(f"fmt: rewrote {n}")
    return 0


def cmd_claim(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    # a research item of a planned sprint is claimed from draft: its kb content lands before the sprint starts
    ok = ("status doing", "status draft") if research_in_planned(bl, iid) else ("status doing",)
    w = [x for x in waits(bl, iid, any_sprint=True, by=a.by) if not x.startswith(ok)]
    if w:
        raise Refused(f"{bl.label(iid)} is not ready:\n  " + "\n  ".join(w))
    if it.get("status") == "doing" and it.get("claimed_by") != a.by:
        raise Refused(f"{bl.label(iid)} is claimed by {it['claimed_by']}")
    # one session per checkout: the claims made in this working tree (its git toplevel; a worktree has its own) are
    # recorded in its own git dir, which git never commits whatever the ignore rules, each with the session that made
    # it: CLAUDE_CODE_SESSION_ID, which Claude Code sets in every Bash subprocess, else the claimer's name. A claim
    # from another session while one of its claims is still doing here is refused before anything is written, so no
    # claim commit lands on another session's branch; one session (an orchestrator) claims for several names freely
    import json
    import os
    session = os.environ.get("CLAUDE_CODE_SESSION_ID") or f"by:{a.by}"
    rev = subprocess.run(["git", "-C", str(bl.root), "rev-parse", "--show-toplevel", "--absolute-git-dir"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.split("\n")
    top, gitdir = (rev + ["", ""])[:2] if len(rev) >= 2 and rev[1] else (str(bl.root), "")
    ledger = Path(gitdir) / "kb-backlog-claims.json" if gitdir else None
    try:
        here = json.loads(ledger.read_text(encoding="utf-8")) if ledger else {}
    except (OSError, ValueError):
        here = {}
    here = {i: (r if isinstance(r, dict) else {"by": r, "session": f"by:{r}"}) for i, r in here.items()}
    busy = sorted(i for i, r in here.items() if r.get("session") != session and i != iid and i in bl.items
                  and bl.items[i].get("status") == "doing" and bl.items[i].get("claimed_by") == r.get("by"))
    if busy:
        raise Refused(f"claim refuses {bl.label(iid)} for {a.by}: another session ({here[busy[0]].get('by')}) works "
                      f"in this checkout ({top}) on {', '.join(bl.label(i) for i in busy)}; each session works in its "
                      "own worktree (git worktree add), so its claim commits never land on another session's branch")
    it.update(status="doing", claimed_by=a.by)
    bl.save(it)
    here = {i: r for i, r in here.items() if i in bl.items and bl.items[i].get("status") == "doing"}
    here[iid] = {"by": a.by, "session": session}
    try:
        if ledger:
            ledger.write_text(json.dumps(here, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass  # the record guards the next claim; a checkout it cannot be written in is not refused for it
    say(f"claimed {bl.label(iid)} for {a.by}")
    commit_written(bl, a, "claim", iid)
    return 0


def cmd_release(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    if it.get("status") != "doing":
        raise Refused(f"{bl.label(iid)} is {it.get('status')}, not doing")
    it["status"] = "draft" if research_in_planned(bl, iid) else "todo"  # a planned sprint's items stay draft
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"released {bl.label(iid)}")
    return 0


def run_decide(bl, *argv):
    tool = Path(bl.root) / "_tools" / "kbdecide.py"
    p = subprocess.run([sys.executable, str(tool), *argv], cwd=str(bl.root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if p.returncode:
        raise Refused(f"--record: {(p.stdout + p.stderr).strip()}")
    return p.stdout.strip()


def record_decision(bl, iid, gate, text, by="operator"):
    """Keep a gate's answer as an active decision of kb/_self (`kbdecide.py record`, so check.py guards the write): its
    source names the item and the gate, its context is the item. Refused with kbdecide's reason."""
    argv = ["record", "--root", "_self", "--source", f"backlog item {iid} gate {gate}", "--context", f"item:{iid}",
            "--gate", gate, "--by", by, "--maker", by]
    say(run_decide(bl, *argv, "--", text))


DECISIONS_REL = "kb/_self/_decisions.csv"  # the file `kbdecide.py record` writes: --record commits it with the item file


def commit_answer(bl, a, iid, gate):
    """--record: commit what the answer wrote, as two commits so each passes `kbgit.py check-trailers` for an item that
    is not claimed: the item file (a backlog-planning commit, subject `chore(backlog): answer ID "title"`, KB-Work: the
    item, then each --trailer), then the decision row of kb/_self/_decisions.csv (no KB-Work: it is no planning commit
    and the item's scope is not its work). `git commit --only`, so what was staged before stays staged and out of both.
    A row left uncommitted would make the next `kbgit.py sync` refuse the dirty tree."""
    trailers = list(getattr(a, "trailer", None) or ())
    title = bl.items.get(iid, {}).get("title", "")
    for paths, msg in (
            ([p for p in bl.written if (bl.root / p).exists()],
             commit_message(withhold(f'chore(backlog): answer {iid} "{title}"'), [iid], trailers, f"Gate {gate}.")),
            ([DECISIONS_REL],
             "\n\n".join([withhold(f"chore(kb): decision for {iid} gate {gate}")] + (["\n".join(trailers)] if trailers else [])) + "\n")):
        git(bl.root, "add", "-A", "--", *paths)
        if not git(bl.root, "status", "--porcelain", "--", *paths).strip():
            continue
        p = subprocess.run(["git", "commit", "-q", "-F", "-", "--only", "--", *paths], cwd=bl.root, input=msg,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise Refused(f"--record: the answer and its decision are written but git commit failed: {(p.stderr or p.stdout).strip()}")
        say(f"committed {git(bl.root, 'rev-parse', '--short=10', 'HEAD').strip()} {msg.splitlines()[0]}")


def cmd_answer(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    g = next((g for g in it.get("gates", []) if g.get("id") == a.gate), None)
    if g is None:
        raise Refused(f"{bl.label(iid)} has no gate {a.gate}")
    if a.record and (a.provisional or a.confirm or a.by != "operator" or not a.answer):
        raise Rejected("--record keeps the operator's answer as a decision: --answer TEXT --by operator, never "
                       "--provisional or --confirm")
    if getattr(a, "trailer", None):
        if not a.record:
            raise Refused("--trailer goes with --record")
        why = next(filter(None, map(trailer_problem, a.trailer)), None)
        if why:
            raise Refused(why)
    members = [bl.items[i] for i in bl.sprint_items(iid)] if it.get("kind") == "sprint" else []
    scope = bl_authority.sprint_scope(it, g, members)
    if a.by is not None and a.by not in ("operator", "agent") and not re.fullmatch(r"delegate:[\w.-]+", a.by):
        raise Rejected(f"--by {a.by}: operator, agent or delegate:NAME")
    if a.confirm and not a.by:
        raise Rejected(f"gate {a.gate} of {bl.label(iid)}: --confirm needs --by operator, which an agent passes only "
                       "after the operator said so")
    if a.confirm and a.by == "agent":  # an agent's confirmation of its own answer would be recorded as the operator's
        raise Rejected(f"gate {a.gate} of {bl.label(iid)}: --confirm --by agent: an agent cannot confirm its own "
                       "provisional answer; the operator confirms (--by operator, passed only after the operator said "
                       "so) or a delegate the operator granted on the sprint (--by delegate:NAME)")
    delegate = a.by[len("delegate:"):] if (a.by or "").startswith("delegate:") else None
    if delegate is not None and not a.confirm:
        raise Rejected(f"--by delegate:{delegate} only confirms a provisional answer (--confirm), it answers nothing")
    if a.by != "operator" and (a.by or a.provisional):
        cls = bl_authority.derived_class(scope, g)
        if cls in bl_authority.OPERATOR_CLASSES:
            refuse = Rejected if a.provisional or a.confirm else Refused  # --answer by an agent: exit 1, as a blocking gate
            raise refuse(f"gate {a.gate} of {bl.label(iid)} is class {cls}: only the operator answers it "
                         "(--by operator)")
    if a.confirm:
        if g.get("by") != "agent":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} has no agent answer to confirm")
        if delegate is not None:  # a grant the operator wrote on the item's sprint names this delegate
            sp = it if it.get("kind") == "sprint" else bl.items.get(bl.sprint_of(iid) or "", {})
            if not any(isinstance(d, dict) and d.get("name") == delegate and d.get("by") == "operator"
                       for d in sp.get("delegates", []) or []):
                raise Refused(f"gate {a.gate} of {bl.label(iid)}: no operator grant names delegate {delegate} on its "
                              f"sprint (the operator grants one: set SP --delegate {delegate} --by operator)")
        g["by"] = a.by if delegate is not None else "operator"
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
        if a.record:
            record_decision(bl, iid, a.gate, a.answer, a.by)
    bl.save(it)
    say(f"gate {a.gate} of {bl.label(iid)}: {g['answer']} (by {g['by']})")
    if a.record:
        commit_answer(bl, a, iid, a.gate)
    return 0


def gone_touch_prefix(bl, iid):
    """How a `stale_touches` finding about the item's own touches begins."""
    return f"{bl.label(iid)}: touches names "


def changed_item(bl, iid, edit):
    """Apply `edit` to a copy of the item and write it when the copy differs and validates as `check` does: no error
    that was not there before (this item's, or another's that a dependency cycle or a review story's sprint would
    add). Returns True when it wrote the file, False when the edit leaves the item as it is; raises Rejected with the
    new errors and the item untouched."""
    return changed_items(bl, {iid: edit})


def changed_items(bl, edits, reveal=()):
    """`changed_item` for several items at once ({id: edit}): the copies are validated together, so either every
    changed item is written or none is. Returns True when it wrote any file. `reveal` names items whose own
    gone-path touches (`stale_touches`) may appear new: an item the edit opens again, which `check` did not flag for
    them while it was done, so the edit reveals them rather than adds them (`reopen`)."""
    olds = {i: bl.items[i] for i in edits}
    news = {}
    for i, edit in edits.items():
        news[i] = copy.deepcopy(olds[i])
        edit(news[i])
    news = {i: n for i, n in news.items() if canonical(n) != canonical(olds[i])}
    if not news:
        return False
    before = set(validate(bl) + stale_touches(bl))
    raws = {i: bl.raw[i] for i in news}
    for i, n in news.items():
        bl.items[i], bl.raw[i] = n, canonical(n)
    try:
        own = tuple(gone_touch_prefix(bl, i) for i in reveal)
        fresh = [x for x in validate(bl) + [s for s in stale_touches(bl) if not s.startswith(own)] if x not in before]
    finally:
        for i in news:
            bl.items[i], bl.raw[i] = olds[i], raws[i]
    if fresh:
        raise Rejected(f"{', '.join(bl.label(i) for i in news)} unchanged: the change would make `check` fail:\n  "
                       + "\n  ".join(fresh))
    for n in news.values():
        bl.save(n)
    return True


SET_LISTS = ("links", "touches", "checks", "depends_on", "relates_to")
SET_FIELDS = ("notes", "priority", "rank", "sprint", "title", "goal", "repro", "repro_reason", "severity",
              "parent", "delegates") + SET_LISTS  # what set changes; the others are refused
SET_REFUSED = {  # a field set refuses, with the rule it states
    "status": "changes only through claim, release, start, close, drop and done",
    "claimed_by": "changes only through claim and release",
    "evidence": "is written only by done",
    "id": "is the item's identity",
    "kind": "is the item's identity",
    "gates": "changes through gate add and answer",
}


def set_refusal(field):
    """The rule that refuses `set` the field, or None when set changes it."""
    if field in SET_FIELDS:
        return None
    return f"set refuses {field}: it {SET_REFUSED.get(field, 'is not a field set changes')}"


def appended(old, values):
    """`old` with each of `values` it lacks added at the end, in order."""
    return old + [v for i, v in enumerate(values) if v not in old and v not in values[:i]]


def reclass_gate(item, gate):
    """Store the stricter of the gate's class and the one `item`'s touches and the gate's text derive now, so widened
    touches re-class a gate already written; a class never goes down here. An unanswered provisional gate that
    becomes one only the operator answers is made blocking, as `gate add` does."""
    stored = gate.get("class")
    d = bl_authority.derived_class(item, gate)
    if stored not in bl_authority.CLASSES or bl_authority.rank(d) < bl_authority.rank(stored):
        gate["class"] = d
    if bl_authority.gate_class(item, gate) in bl_authority.OPERATOR_CLASSES and gate.get("kind") != "blocking" \
            and "answer" not in gate:
        gate["kind"] = "blocking"


def cmd_set(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    for f in SET_REFUSED:
        if getattr(a, "no_" + f, None) is not None:
            raise Rejected(set_refusal(f))
    for f in a.clear:
        if set_refusal(f):
            raise Rejected(set_refusal(f))
    given = {"notes": a.notes, "priority": a.priority, "rank": a.rank, "sprint": a.sprint}
    given.update({f: getattr(a, f) for f in ("title", "goal", "repro", "repro_reason", "severity", "parent")})
    if a.delegate or "delegates" in a.clear:  # a grant the operator gives: never an agent's own word
        if a.set_by != "operator":
            raise Rejected("set refuses delegates without --by operator: a grant to confirm provisional answers is the "
                           "operator's, never an agent's")
        if it.get("kind") != "sprint":
            raise Rejected(f"set refuses delegates on {bl.label(iid)}: a grant is a sprint's")
    if a.delegate:
        bad = [n for n in a.delegate if not re.fullmatch(r"[\w.-]+", n)]
        if bad:
            raise Rejected(f"set: --delegate {bad[0]!r} is not a name (letters, digits, . _ -)")
        have = [d for d in it.get("delegates", []) or [] if isinstance(d, dict)]
        given["delegates"] = have + [{"name": n, "by": "operator"} for n in dict.fromkeys(a.delegate)
                                     if not any(d.get("name") == n for d in have)]
    given.update({f: getattr(a, f) for f in SET_LISTS})
    given = {f: v for f, v in given.items() if v is not None}
    both = sorted(set(given) & set(a.clear))
    if both:
        raise Rejected(f"set: {', '.join(both)} given a value and --clear together")
    if not given and not a.clear:
        raise Rejected("set: nothing to change: name a field (" + ", ".join(SET_FIELDS) + ")")
    named = sorted(set(given) | set(a.clear))
    if it.get("kind") == "sprint" and set(named) - {"notes", "links", "delegates"}:
        raise Rejected(f"set refuses {', '.join(sorted(set(named) - {'notes', 'links', 'delegates'}))} on a sprint: "
                       "a sprint takes notes, links and delegates only")
    if it.get("status") == "done" and {"checks", "touches", "goal", "repro", "repro_reason"} & set(named):
        raise Rejected(f"set refuses {', '.join(sorted({'checks', 'touches', 'goal', 'repro', 'repro_reason'} & set(named)))} "
                       f"on {bl.label(iid)}: it is done, and its evidence proves the goal, repro, checks and touches it had")
    if "title" in given:
        given["title"] = given["title"].strip()
        if not given["title"]:
            raise Rejected("set: --title is empty")
    if {"repro", "repro_reason", "severity"} & set(named) and it.get("kind") != "bug":
        raise Rejected(f"set refuses {', '.join(sorted({'repro', 'repro_reason', 'severity'} & set(named)))} on "
                       f"{bl.label(iid)}: only a bug has a repro and a severity")
    if {"repro", "severity"} & set(a.clear):
        raise Rejected("set refuses --clear repro or severity: a bug needs both")
    if "parent" in given and given["parent"] not in bl.items:
        raise Rejected(f"set refuses parent {given['parent']} for {bl.label(iid)}: no such item")
    if "repro" in given:  # as new bug: a command that fails now, for the defect, not for its own error
        try:
            given["repro"] = {"run": parse_cmd(given["repro"])}
        except ValueError as e:
            raise Rejected(f"set: --repro is not a command line ({e})") from e
        ok, code, out = run_check(bl.root, given["repro"])
        if ok:
            raise Refused(f"--repro passes now (exit {code}): it must fail until the bug is fixed")
        why = own_failure(given["repro"]["run"], code, out, bl.root)
        if why:
            raise Refused(f"--repro fails for its own error, not the defect: {why}")
    if "repro_reason" in given:
        given["repro_reason"] = given["repro_reason"].strip()
    if {"repro", "repro_reason"} & set(named):
        run = (given.get("repro") or it.get("repro") or {}).get("run") or []
        reason = "" if "repro_reason" in a.clear else given.get("repro_reason", it.get("repro_reason", ""))
        why = text_only_repro(run) if run else None
        if why and not reason:
            raise Rejected(f"--repro only matches text in a file ({why}): run the behaviour (a test, a command on a "
                           "planted input), or state why it cannot with --repro-reason TEXT")
    if a.sprint is not None and bl.items.get(a.sprint, {}).get("status") == "active" and it.get("status") == "draft":
        raise Rejected(f"set refuses sprint {a.sprint} for {bl.label(iid)}: the sprint is active and the item is "
                       "draft, so it would never be ready")
    if "checks" in given:
        try:
            given["checks"] = [{"run": parse_cmd(c)} for c in given["checks"]]
        except ValueError as e:
            raise Rejected(f"set: --check is not a command line ({e})") from e

    def edit(new):
        for f, v in given.items():
            if f in SET_LISTS and a.add:
                new[f] = appended(new.get(f, []) if isinstance(new.get(f, []), list) else [], v)
            elif f == "notes" and a.add:
                old = new.get("notes", "")
                new[f] = old if v in old else f"{old} {v}".strip()
            else:
                new[f] = v
        for f in a.clear:
            new.pop(f, None)
        if "touches" in given or "touches" in a.clear:  # new touches may put a gate in a stricter class: store it
            for g in new.get("gates", []) or []:
                reclass_gate(new, g)
        if "parent" in given and not new.get("sprint") and new.get("status") in ("draft", "todo"):
            # as move does: the sprint the new parent puts it in gives its status, todo in an active sprint and draft
            # in a planned one; with no sprint above it the status stays (BG-k4myfom6)
            state = bl.items.get(bl.sprint_of(given["parent"]) or "", {}).get("status")
            if state in ("active", "planned"):
                new["status"] = "todo" if state == "active" else "draft"

    if changed_item(bl, iid, edit):
        say(f"set {bl.label(iid)}: {', '.join(named)}")
    else:
        say(f"set {bl.label(iid)}: unchanged")
    return 0


def cmd_move(bl, a):
    """move: a story's or bug's sprint, with the status that sprint's state gives it and its tasks."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    label = bl.label(iid)
    target = None if a.sprint == "none" else a.sprint
    if it.get("kind") not in IN_SPRINT:
        raise Rejected(f"move refuses {label}: only a story or a bug names a sprint; its tasks and subtasks follow it, "
                       "so move the story or bug above it")
    if it.get("review"):
        raise Rejected(f"move refuses {label}: a sprint needs exactly one review story, and this is its own")
    st = it.get("status")
    if st == "done":
        raise Rejected(f"move refuses {label}: it is done; reopen it first (backlog.py reopen ID --why TEXT)")
    if st == "dropped":
        raise Rejected(f"move refuses {label}: it is dropped, and a dropped item has no sprint to change")
    kids = bl.descendants(iid)
    claimed = [i for i in [iid] + kids if bl.items[i].get("status") == "doing"]
    if claimed:
        raise Rejected(f"move refuses {label}: {', '.join(bl.label(i) for i in claimed[:5])} is doing (claimed); "
                       "release it first, since a claimed item is in the middle of work")
    if target is not None:
        sp = bl.items.get(target)
        if sp is None:
            raise Rejected(f"move refuses sprint {target} for {label}: sprint {target} does not exist")
        if sp.get("kind") != "sprint":
            raise Rejected(f"move refuses {target} for {label}: it is not a sprint")
    state = "todo" if target is not None and bl.items[target].get("status") == "active" else "draft"
    if state == "todo" and not has_scope(bl, iid):
        raise Rejected(f"move refuses sprint {target} for {label}: the sprint is active and the item has no touches "
                       "(and no tasks that all have them), which start requires of every work item")

    def edit_story(new):
        if target is None:
            new.pop("sprint", None)
        else:
            new["sprint"] = target
        new["status"] = state

    def edit_child(new):
        new["status"] = state

    edits = {iid: edit_story}
    edits.update({c: edit_child for c in kids if bl.items[c].get("status") in ("draft", "todo")})
    if changed_items(bl, edits):
        say(f"moved {label} to {bl.label(target) if target else 'no sprint'}: status {state}"
            + (f", {len(edits) - 1} task(s) and subtask(s) follow" if len(edits) > 1 else ""))
    else:
        say(f"move {label}: unchanged")
    return 0


def cmd_reopen(bl, a):
    """reopen: a done item back to work, its evidence and claim cleared; the reason is printed, never stored."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    label = bl.label(iid)
    if not a.why.strip():
        raise Rejected("reopen: --why TEXT must not be empty")
    if it.get("kind") == "sprint":
        raise Rejected(f"reopen refuses {label}: a sprint has no done status")
    if it.get("status") != "done":
        raise Rejected(f"reopen refuses {label}: it is {it.get('status')}; reopen takes only a done item back to work "
                       "(a draft, todo or doing item is open already, and a dropped one is not reopened: file a new item)")
    sp = bl.sprint_of(iid)
    state = "draft" if sp in bl.items and bl.items[sp].get("status") == "planned" else "todo"

    def edit(new):
        new["status"] = state
        new.pop("evidence", None)
        new.pop("claimed_by", None)

    # a done item's gone touches are no finding while it is done: reopening reveals them, and set --touch repoints them
    changed_items(bl, {iid: edit}, reveal=(iid,))
    say(f"reopened {label}: status {state}, evidence and claim cleared. Why: {a.why.strip()}")
    gone = [s for s in stale_touches(bl) if s.startswith(gone_touch_prefix(bl, iid))]
    if gone:
        say("  " + "\n  ".join(gone) + f"\n  repoint them: backlog.py set {iid} --touch PATH ...")
    return 0


GATE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
CAPPED_FILE_RE = re.compile(r"\b(?:AGENTS|README)\.md\b")
SIZE_WORD_RE = re.compile(r"\b(?:cap|capped|bytes|size|limit)\b", re.I)
MEASURED_SIZE_RE = re.compile(r"\b\d[\d,]*\s*bytes\b", re.I)


def cmd_gate(bl, a):
    """gate add: a gate with its question, options and recommendation."""
    iid = need(bl, a.id)
    it = bl.items[iid]
    if it.get("status") in ("done", "dropped"):
        raise Rejected(f"gate add refuses {bl.label(iid)}: it is {it['status']}, so a gate would wait on nothing")
    options = [o.strip() for o in a.option]
    if len(options) < 2 or len(set(options)) != len(options) or not all(options):
        raise Rejected("gate add: --option twice or more, each different and not empty")
    if a.recommendation.strip() not in options:
        raise Rejected("gate add: --recommendation must be one of the --option values")
    about = " ".join([a.question, *options])
    if CAPPED_FILE_RE.search(about) and SIZE_WORD_RE.search(about):
        bare = [o for o in options if not MEASURED_SIZE_RE.search(o)]
        if bare:  # a size cap: the operator is asked once, on each option's measured result
            raise Rejected("gate add: the gate is about a capped file (AGENTS.md, README.md), so each --option states "
                           f"the file's measured size after it (`wc -c`, as 'N bytes'); without one: {', '.join(bare)}")
    gates = it.get("gates", [])
    gid = a.gate_id or next(f"g{n}" for n in range(1, len(gates) + 2) if f"g{n}" not in {g.get("id") for g in gates})
    if not GATE_ID_RE.fullmatch(gid) or gid == START_GATE:
        raise Rejected(f"gate add: the gate id {gid!r} must be lowercase letters, digits and hyphens (at most 40), "
                       f"and not {START_GATE!r}, the sprint's own")
    gate = {"id": gid, "kind": a.kind, "question": a.question.strip(), "options": options,
            "recommendation": a.recommendation.strip()}
    gate["class"] = bl_authority.derived_class(it, gate)
    if gate["class"] in bl_authority.OPERATOR_CLASSES and gate["kind"] != "blocking":
        gate["kind"] = "blocking"
        say(f"gate {gid} of {bl.label(iid)} is class {gate['class']}: made blocking, only the operator answers it")
    if a.do:
        gate["do"] = {}
        for d in a.do:
            opt, sep, how = d.partition("=")
            opt, how = opt.strip(), how.strip()
            if not sep or opt not in options or not how:
                raise Rejected("gate add: --do OPTION=COMMAND, OPTION one of the --option values")
            gate["do"][opt] = how if how in bl.items else parse_cmd(how)
            if not gate["do"][opt]:
                raise Rejected("gate add: --do needs a command or an item id after the =")
    if a.host_check:
        gate["host_check"] = {"run": parse_cmd(a.host_check)}
        if not gate["host_check"]["run"]:
            raise Rejected("gate add: --host-check needs a command")
    same = [g for g in gates if g.get("question") == gate["question"] or g.get("id") == gid]
    if same:
        known = same[0]
        if len(same) > 1 or any(known.get(k) != v for k, v in gate.items() if k not in ("id", "class")) \
                or (a.gate_id and known.get("id") != gid):  # an answer it already has does not make it different
            raise Rejected(f"gate add refuses a different gate with the question or id of gate {known.get('id')} "
                           f"of {bl.label(iid)}: it already has one (its answer is not overwritten)")
        say(f"gate {known.get('id')} of {bl.label(iid)}: unchanged")
        return 0

    def edit(new):
        new["gates"] = list(new.get("gates", [])) + [gate]

    changed_item(bl, iid, edit)
    say(f"gate {gid} ({gate['kind']}) added to {bl.label(iid)}: {gate['question']}")
    return 0


def cmd_host_check(bl, a):
    """host-check: run, on this host, the check of each answered gate that names a host setup; record the result."""
    sid = need(bl, a.sprint)
    if bl.items[sid].get("kind") != "sprint":
        raise Refused(f"{bl.label(sid)} is not a sprint")
    rows = host_gates(bl, sid)
    if not rows:
        say(f"{bl.label(sid)}: no answered gate names a host setup")
        return 0
    results, failed = {}, []
    for iid, g in rows:
        ok, code, out = run_check(bl.root, g["host_check"])
        results[(iid, g["id"])] = {"ok": ok, "exit": code}
        say(f"{'ok' if ok else 'FAILED'} {bl.label(iid)} gate {g['id']} ({g['answer']}): "
            f"{shlex.join(g['host_check']['run'])} exited {code}")
        if not ok:
            failed.append(f"{bl.label(iid)} gate {g['id']}: {g['question']}\n    " + "\n    ".join(out.strip().splitlines()[-5:]))

    def edits(iid):
        def edit(new):
            for g in new["gates"]:
                if (iid, g["id"]) in results:
                    g["host_checked"] = results[(iid, g["id"])]
        return edit

    changed_items(bl, {i: edits(i) for i in {i for i, _ in results}})
    if failed:
        say("host setup does not hold on this host:\n  " + "\n  ".join(failed))
        return 1
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


def cmd_drop(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    live = [c for c in bl.descendants(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if live:
        raise Refused(f"{bl.label(iid)} has open children: " + ", ".join(bl.label(c) for c in live[:5]))
    users = [i for i, x in bl.items.items() if iid in x.get("depends_on", []) and x.get("status") != "dropped"]
    if users:
        raise Refused(f"{bl.label(iid)} is a dependency of " + ", ".join(bl.label(u) for u in users[:5]))
    gone = {iid} if bl.sprint_of(iid) else {iid, *bl.descendants(iid)}  # a drop outside a sprint deletes the descendants too
    inner = gone - {iid}
    users = [i for i, x in bl.items.items() if i not in gone and inner & set(x.get("depends_on", [])) and x.get("status") != "dropped"]
    if users:
        raise Refused(f"{bl.label(iid)} would delete items that " + ", ".join(bl.label(u) for u in users[:5]) + " depend on")
    # a dropped item that depended on this one keeps no link to it: check reports a dependency on a dropped item
    for i, x in bl.items.items():
        if x.get("status") == "dropped" and gone & set(x.get("depends_on", [])):
            left = [d for d in x["depends_on"] if d not in gone]
            if left:
                x["depends_on"] = left
            else:
                x.pop("depends_on")
            bl.save(x)
    if not bl.sprint_of(iid):
        label = bl.label(iid)
        for i, x in sorted(bl.items.items()):  # no remaining item keeps a link to a deleted one (BG-3aqoagow)
            if i in gone or not set(x.get("relates_to") or []) & gone:
                continue
            cut = sorted(gone & set(x["relates_to"]))
            left = [r for r in x["relates_to"] if r not in gone]
            if left:
                x["relates_to"] = left
            else:
                x.pop("relates_to")
            bl.save(x)
            say(f"dropped relates_to {', '.join(cut)} from {bl.label(i)}")
        for i, gate, opt, target in cleanup_gate_do(bl, gone):  # a gate's do names an item by id too
            say(f"dropped gate {gate} do {opt!r} (item {target}) from {bl.label(i)}")
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


def referrer_patterns(term, files):
    """The patterns that name term: a tracked file by its path and its file name, word-bounded (a .py file's name is
    <stem>.py, and it is also named by an import line that holds its module name: `import stem`, `from stem import`),
    any other term as a symbol, word-bounded. The bare module name alone is no reference: prose and items say the
    word (`backlog`) without naming the file."""
    if term in files:
        name = Path(term).name
        pats = [re.compile(re.escape(term)), re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])")]
        if term.endswith(".py"):
            pats.append(re.compile(r"^\s*(?:from|import)\s.*\b" + re.escape(Path(term).stem) + r"\b"))
        return pats
    return [re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])")]


def referrers_of(root, term, files):
    """(path, first line number, matching line count) of each tracked text file other than term itself that names it.
    Backlog item files are left out: an item naming the path in its touches is check's stale-touches error once the
    file moves, and an item's prose only says the word."""
    pats = referrer_patterns(term, files)
    out = []
    for f in files:
        path = Path(root) / f
        if f == term or item_file(f) or not path.is_file() or path.stat().st_size > 4_000_000:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        hit = [n for n, ln in enumerate(lines, 1) if any(p.search(ln) for p in pats)]
        if hit:
            out.append((f, hit[0], len(hit)))
    return out


def cmd_referrers(bl, a):
    """Every tracked file that names a file or symbol a task will move or delete: one line per file with its first
    line and its count of lines, read-only. --item ID marks each file outside the item's scope (its touches and its
    descendants') and exits 1 when there is one, so the touches hold them before the work starts."""
    files = tracked_files(bl.root)
    globs = scope(bl, need(bl, a.item)) if a.item else None
    stray = 0
    for term in a.terms:
        rows = referrers_of(bl.root, term, files)
        for f, first, n in rows:
            out = bool(globs is not None and not in_scope(f, globs))
            stray += out
            say(f"{term}  {f}:{first}  {n} line{'s' * (n != 1)}" + ("  outside touches" if out else ""))
        if not rows:
            say(f"{term}  no tracked file names it")
    return 1 if stray else 0


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
    above = [(x, g) for x in bl.ancestors(iid) for g in bl.items[x].get("gates", []) or [] if g.get("answer")]
    if above:  # a brief built from the goal must not contradict an answer given above the item
        say("answered gates above it, which its work keeps to:")
        for x, g in above:
            by = g.get("by") or "?"
            say(f"  {bl.label(x)} {g['id']}: {g.get('question', '')} -> {g['answer']} (by {by}"
                + (", provisional" if g.get("kind") == "provisional" and g.get("by") == "agent" else "") + ")")
    return 0


def args_new(p):
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
    p.add_argument("--repro-reason", help="why a repro that only matches text in a file cannot run the behaviour")


def args_claim(p):
    p.add_argument("id")
    p.add_argument("--by", required=True)


def args_release(p):
    p.add_argument("id")


def args_answer(p):
    p.add_argument("id")
    p.add_argument("gate")
    p.add_argument("--answer")
    p.add_argument("--by", metavar="operator|agent|delegate:NAME",
                   help="who answers; delegate:NAME only confirms, under the operator's grant on the sprint")
    p.add_argument("--provisional", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--record", action="store_true", help="with --answer TEXT --by operator: keep the answer as an active decision, committed with the item file")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own after KB-Work in the --record commit (repeatable)")


def args_set(p):
    p.add_argument("id")
    p.add_argument("--notes")
    p.add_argument("--link", dest="links", action="append")
    p.add_argument("--touch", dest="touches", action="append")
    p.add_argument("--check", dest="checks", action="append")
    p.add_argument("--depends", dest="depends_on", action="append")
    p.add_argument("--relates", dest="relates_to", action="append")
    p.add_argument("--priority")
    p.add_argument("--rank", type=int)
    p.add_argument("--sprint")
    p.add_argument("--title", help="the item's title")
    p.add_argument("--goal", help="the goal, replaced whole (refused on a done item)")
    p.add_argument("--repro", help="a bug's repro command, which must fail now as new bug's does (refused on a done item)")
    p.add_argument("--repro-reason", dest="repro_reason", help="why a bug's repro can only match text in a file")
    p.add_argument("--severity", choices=SEVERITIES, help="a bug's severity")
    p.add_argument("--parent", help="the item's parent, by the same kind rules check applies")
    p.add_argument("--delegate", action="append", metavar="NAME",
                   help="on a sprint, with --by operator: grant NAME the confirming of its provisional answers")
    p.add_argument("--by", dest="set_by", metavar="operator", help="who writes a --delegate grant: the operator only")
    p.add_argument("--add", action="store_true", help="append to a list (or to the notes) instead of replacing it")
    p.add_argument("--clear", action="append", default=[], metavar="FIELD", help="remove a field (repeatable)")
    for f in SET_REFUSED:  # accepted only to be refused with the rule that applies
        p.add_argument("--" + f.replace("_", "-"), dest="no_" + f, help=argparse.SUPPRESS)


def args_move(p):
    p.add_argument("id")
    p.add_argument("--sprint", required=True, metavar="SP|none")


def args_reopen(p):
    p.add_argument("id")
    p.add_argument("--why", required=True)


def args_gate(p):
    gsub = p.add_subparsers(dest="verb", required=True)
    p = gsub.add_parser("add")
    p.add_argument("id")
    p.add_argument("--question", required=True)
    p.add_argument("--option", action="append", required=True, help="an answer the operator may give (repeatable)")
    p.add_argument("--recommendation", required=True, help="the option the agent recommends")
    p.add_argument("--kind", default="blocking", help="blocking (default) or provisional")
    p.add_argument("--id", dest="gate_id", help="the gate's id (default g1, g2, ...)")
    p.add_argument("--do", action="append", metavar="OPTION=CMD|ID",
                   help="the command that carries OPTION out, or the id of the item whose work adds it (repeatable)")
    p.add_argument("--host-check", help="a command that exits 0 when the host setup the answer names holds here")


def args_fire(p):
    p.add_argument("id")


def args_drop(p):
    p.add_argument("id")
    p.add_argument("--why", required=True)


def args_host_check(p):
    p.add_argument("sprint")


def args_goal(p):
    p.add_argument("id")


def args_referrers(p):
    p.add_argument("terms", nargs="+", help="a tracked file path or a symbol a task will move or delete")
    p.add_argument("--item", help="mark the files outside this item's scope (touches and its descendants')")


bl_cli.register("new", cmd_new, args_new)
bl_cli.register("fmt", cmd_fmt)
bl_cli.register("claim", cmd_claim, args_claim)
bl_cli.register("release", cmd_release, args_release)
bl_cli.register("answer", cmd_answer, args_answer)
bl_cli.register("set", cmd_set, args_set)
bl_cli.register("move", cmd_move, args_move)
bl_cli.register("reopen", cmd_reopen, args_reopen)
bl_cli.register("gate", cmd_gate, args_gate)
bl_cli.register("fire", cmd_fire, args_fire)
bl_cli.register("drop", cmd_drop, args_drop)
bl_cli.register("host-check", cmd_host_check, args_host_check)
bl_cli.register("goal", cmd_goal, args_goal)
bl_cli.register("referrers", cmd_referrers, args_referrers)
