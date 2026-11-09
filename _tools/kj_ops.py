"""The closed table of the operations a job may run (stdlib only; kb/_self/coordination.md, section "Operation jobs").

`OPS` is the authority rule of the job queue: an operation not in it (`publish`, `answer`, any operator-only command) is
no job, and an executor runs only the argument list `argv` builds from a table row, so the CLI's own gates and refusals
apply to a job as they do to a person. Each row names whether it takes a backlog id as its subject and the options it
takes, each with the kind of value it holds:

  land        SUBJECT  wait_merge (seconds), trailer (repeatable)         backlog.py land ID
  done        SUBJECT  commit (flag), trailer (repeatable)                backlog.py done ID
  stage-back  SUBJECT  check (flag), self_reviewed (a doc path, repeatable), trailer (repeatable)
                                                                          backlog.py stage-back ID
  sync-push   no subject, no option                                       kbgit.py sync --push
  check       no subject, name (one of CHECKS, required)                  backlog.py check, tests.py, tests.py --changed
  bench       SUBJECT a scenario (a slug), budget (USD, required)         benchmarks.py run SCENARIO --max-usd USD

An operation that spends model calls (`PAID`: bench, dispatch, begin) takes the option `budget`, the most it may spend in USD
(`kbjob.py submit --budget USD`), and `check_job` refuses one without it; `OverCap`, a `Refusal` of its own, is a budget that
would take its group past the cap of its placement decision, which `kbjob.py` prints with exit 1.

`check_job` validates an operation, its subject's shape, its options and `by` and returns the options as the job record
keeps them (a number as an int, a flag as true, a repeatable one as a list); a refusal is a `Refusal`, which names what is
allowed and which `kbjob.py` prints with exit 2. `argv` is the argument list of a row, a path relative to the clone's top.
"""
import re

import kj_place

BY = re.compile(r"claude-[0-9a-f]{8}")
ITEM = re.compile(r"[A-Z]{2}-[a-z2-7]{8}")
TRAILER = re.compile(r"[A-Za-z][A-Za-z0-9-]*: [^\r\n]{1,200}")
DOC = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,119}")
SCENARIO = re.compile(r"[a-z][a-z0-9-]{0,39}")
USD = re.compile(r"[0-9]{1,6}(\.[0-9]{1,2})?")
WAIT_MAX = 86400
FLAGS = ("true", "false", "1", "0")
CHECKS = {"backlog-check": ["_tools/backlog.py", "check"],
          "tests-full": ["_tools/tests.py"],
          "tests-changed": ["_tools/tests.py", "--changed", "origin/main"]}

OPS = {
    "land": {"subject": True, "options": {"wait_merge": "seconds", "trailer": "trailer"}},
    "done": {"subject": True, "options": {"commit": "flag", "trailer": "trailer"}},
    "stage-back": {"subject": True, "options": {"check": "flag", "self_reviewed": "doc", "trailer": "trailer"}},
    "sync-push": {"subject": False, "options": {}},
    "check": {"subject": False, "options": {"name": "check"}},
    "bench": {"subject": True, "scenario": True, "options": {"budget": "usd"}},
}
PAID = kj_place.PAID_OPS  # the operations that spend model calls: each needs a budget
REPEATABLE = ("trailer", "self_reviewed")  # an option that may be given more than once: the record holds a list


class Refusal(ValueError):
    """A submit's input the table does not allow: the message names what is allowed (exit 2)."""


class OverCap(Refusal):
    """A paid job whose budget would take its group's day past the cap of the placement decision: nothing is queued (exit 1)."""


def item_subject(op):
    """True when the subject of OP is the id of an item of the clone's backlog (not a scenario, not none)."""
    row = OPS[op]
    return bool(row["subject"]) and not row.get("scenario")


def allowed(op):
    row = OPS[op]
    names = ", ".join(row["options"]) or "none"
    subject = "a scenario as its subject" if row.get("scenario") else "a backlog id as its subject" if row["subject"] else "no subject"
    return f"{op} takes {subject} and the options {names}"


def value_of(op, name, kind, raw):
    """The record's value of option NAME given as the text RAW, or a Refusal."""
    if kind == "seconds":
        if not re.fullmatch(r"[0-9]{1,6}", str(raw)) or int(raw) > WAIT_MAX:
            raise Refusal(f"option {name} of {op} is a number of seconds, 0 to {WAIT_MAX}, not {str(raw)[:40]!r}")
        return int(raw)
    if kind == "usd":
        if not re.fullmatch(USD, str(raw)) or float(raw) <= 0:
            raise Refusal(f"option {name} of {op} is a number of US dollars above 0 (at most 2 decimals), not {str(raw)[:40]!r}")
        return float(raw) if "." in str(raw) else int(raw)
    if kind == "flag":
        if str(raw).lower() not in FLAGS:
            raise Refusal(f"option {name} of {op} is a flag, one of {', '.join(FLAGS)}, not {str(raw)[:40]!r}")
        return str(raw).lower() in ("true", "1")
    if kind == "trailer":
        if not isinstance(raw, str) or not TRAILER.fullmatch(raw):
            raise Refusal(f"option {name} of {op} is 'Key: value' (the key starts with a letter, one line of at most 200 characters), not {str(raw)[:40]!r}")
        return raw
    if kind == "doc":
        if not isinstance(raw, str) or not DOC.fullmatch(raw) or ".." in raw.split("/"):
            raise Refusal(f"option {name} of {op} is a doc path of letters, digits and _ . / -, not {str(raw)[:40]!r}")
        return raw
    if str(raw) not in CHECKS:
        raise Refusal(f"option {name} of {op} is one of {', '.join(CHECKS)}, not {str(raw)[:40]!r}")
    return str(raw)


def check_job(op, subject, by, options):
    """The options of the job as its record keeps them. A Refusal names what is allowed: the operations of OPS, the
    subject a row takes, the options of its row and the shape of `by`."""
    if op in PAID and "budget" not in (options or {}):
        raise Refusal(f"{op} spends model calls: pass --budget USD, the most it may spend")
    if op not in OPS:
        raise Refusal(f"{str(op)[:40]!r} is no operation of the job queue: one of {', '.join(OPS)}")
    row = OPS[op]
    if by and not BY.fullmatch(by):
        raise Refusal(f"--by is claude- and 8 lowercase hex digits (never a full session id), not {str(by)[:40]!r}")
    if row.get("scenario"):
        if not subject or not SCENARIO.fullmatch(subject):
            raise Refusal(f"{op} takes a scenario name as its subject (lowercase letters, digits and -, at most 40), not {str(subject)[:40]!r}")
    elif row["subject"]:
        if not subject or not ITEM.fullmatch(subject):
            raise Refusal(f"{allowed(op)}, not {str(subject)[:40]!r}")
    elif subject:
        raise Refusal(f"{allowed(op)}, not {str(subject)[:40]!r}")
    given = {}
    for name, raw in (options or {}).items():
        kind = row["options"].get(name)
        if kind is None:
            raise Refusal(f"{name!r} is no option of {op}: {allowed(op)}")
        many = raw if isinstance(raw, list) else [raw]
        if len(many) > 1 and name not in REPEATABLE:
            raise Refusal(f"option {name} of {op} is given once")
        values = [value_of(op, name, kind, one) for one in many]
        given[name] = values if name in REPEATABLE else values[0]
    if op == "check" and "name" not in given:
        raise Refusal(f"check takes --name, one of {', '.join(CHECKS)}")
    return given


def argv(op, subject, options):
    """The argument list the executor runs for a job, relative to the clone's top (a script path first). The options are
    the record's (`check_job` already validated them), so the list holds no text the table did not accept."""
    options = options or {}
    if op == "land":
        out = ["_tools/backlog.py", "land", subject]
        if "wait_merge" in options:
            out += ["--wait-merge", str(options["wait_merge"])]
    elif op == "done":
        out = ["_tools/backlog.py", "done", subject] + (["--commit"] if options.get("commit") else [])
    elif op == "stage-back":
        out = ["_tools/backlog.py", "stage-back", subject] + (["--check"] if options.get("check") else [])
        for doc in options.get("self_reviewed", []):
            out += ["--self-reviewed", doc]
    elif op == "sync-push":
        return ["_tools/kbgit.py", "sync", "--push"]
    elif op == "check":
        return list(CHECKS[options["name"]])
    elif op == "bench":
        return ["_tools/benchmarks.py", "run", subject, "--max-usd", str(options["budget"])]
    else:
        raise Refusal(f"{str(op)[:40]!r} is no operation of the job queue: one of {', '.join(OPS)}")
    for trailer in options.get("trailer", []):
        out += ["--trailer", trailer]
    return out
