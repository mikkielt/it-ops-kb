#!/usr/bin/env python3
"""Who is operating this session (stdlib only): a pseudonymous operator id and the session's role.

  kbwho.py [--json] [--show-email]   print the operator id, where it came from and the role

The id, in this order:
  1. inherited   KB_OPERATOR, set by the session that started this one (a dispatched worker, a headless run);
  2. auth-status the `email` key of `claude auth status` when it has one (the key is not documented, so a missing
                 key, a logged-out login, no `claude` on PATH or a slow answer falls through);
  3. git         `git config user.email` of this repository;
  4. none        no id (null in --json); nothing is guessed.
The role is KB_ROLE, `interactive` when unset.

An email is never the id: it is mapped to an alias in `_private/operators.json` (uncommitted, gitignored; in the main
worktree of the clone, so its linked worktrees share it), a JSON object of lowercase email to alias. The first use of an email writes `op-` and 8 random hex digits; the operator may
edit the alias, and a tool takes whatever the file holds. A plain hash of an address could be reversed by guessing
it, a random alias cannot. The email itself appears only in `_private/operators.json` and in the output of
`--show-email`; `operator()` and the default output carry the alias only.

`operator()` gives other tools the same answer as a dict `{"id", "source", "role"}`; it never raises (an alias file
that cannot be written leaves `id` None). `otel_attributes()` (and `--otel-attributes`, one JSON object) gives the resource
kbmon's OpenTelemetry export carries: the operator id as `kb.operator.id`, never an email. Exit 0 whatever the source; 2 for a bad argument.

Answers: who the operator of this session is and which role the session has
Use: python3 _tools/kbwho.py [--json]
"""
import argparse, json, os, re, secrets, subprocess, sys, urllib.parse

import kbcommon
import ql_base

SOURCES = ("inherited", "auth-status", "git", "none")
ID_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
EMAIL_RX = re.compile(r"[^\s@]+@[^\s@]+")
AUTH_TIMEOUT = 5  # seconds for `claude auth status` (0.12 s measured)


def aliases_path():
    """The clone's main worktree keeps the file, so every linked worktree gives one email the same alias."""
    return ql_base.clone_home() / "_private" / "operators.json"


def _read_aliases(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def alias_of(email, path=None):
    """The alias of EMAIL in the operators file, written as op- and 8 random hex digits on first use."""
    path = path or aliases_path()
    key = email.strip().lower()
    got = _read_aliases(path).get(key)
    if got:
        return got
    path.parent.mkdir(parents=True, exist_ok=True)
    table = _read_aliases(path)  # read again: another process may have written meanwhile
    if not table.get(key):
        table[key] = "op-" + secrets.token_hex(4)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    return table[key]


def _auth_email():
    try:
        r = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                           timeout=AUTH_TIMEOUT, stdin=subprocess.DEVNULL)
        data = json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    email = data.get("email") if isinstance(data, dict) else None
    return email.strip() if isinstance(email, str) else ""


def _git_email():
    try:
        r = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True, encoding="utf-8",
                           cwd=kbcommon.HOME, timeout=AUTH_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def resolve():
    """(id, source, role, email): email is "" unless the id came from one."""
    role = os.environ.get("KB_ROLE", "").strip() or "interactive"
    inherited = os.environ.get("KB_OPERATOR", "").strip()
    if inherited:
        if ID_RX.fullmatch(inherited):
            return inherited, "inherited", role, ""
        print("kbwho: KB_OPERATOR is not an id (letters, digits, . _ -, at most 64): ignored", file=sys.stderr)
    for source, email in (("auth-status", _auth_email()), ("git", _git_email())):
        if email:
            try:
                return alias_of(email), source, role, email
            except OSError as e:
                print(f"kbwho: cannot write {aliases_path()}: {e}", file=sys.stderr)
                return None, source, role, email
    return None, "none", role, ""


def operator():
    """What other tools record for the operator: {"id", "source", "role"}; the email is not in it."""
    oid, source, role, _ = resolve()
    return {"id": oid, "source": source, "role": role}


def otel_attributes():
    """kbmon's OpenTelemetry resource as a dict: service.name (OTEL_SERVICE_NAME, else the entry of
    OTEL_RESOURCE_ATTRIBUTES, else kbmon), kb.operator.id with the operator id (left out when there is none) and every
    other OTEL_RESOURCE_ATTRIBUTES entry except user.email and one whose value holds an email address."""
    attrs = {}
    for pair in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "").split(","):
        key, sep, value = pair.partition("=")
        key, value = key.strip(), urllib.parse.unquote(value.strip())
        if sep and key and key.lower() != "user.email" and not EMAIL_RX.search(value):
            attrs[key] = value
    attrs["service.name"] = os.environ.get("OTEL_SERVICE_NAME", "").strip() or attrs.get("service.name") or "kbmon"
    oid = operator()["id"]
    if oid:
        attrs["kb.operator.id"] = oid
    return attrs


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kbwho.py", description="Print the pseudonymous operator id, its source and the role.")
    ap.add_argument("--json", action="store_true", help="one JSON object: id, source, role")
    ap.add_argument("--show-email", action="store_true", help="also print the email the id was read from")
    ap.add_argument("--otel-attributes", action="store_true", help="one JSON object: kbmon's OpenTelemetry resource attributes")
    args = ap.parse_args(argv)
    if args.otel_attributes:
        print(json.dumps(otel_attributes()))
        return 0
    oid, source, role, email = resolve()
    out = {"id": oid, "source": source, "role": role}
    if args.show_email:
        out["email"] = email or None
    if args.json:
        print(json.dumps(out))
    else:
        print(f"operator: {oid or 'none'}")
        print(f"source: {source}")
        print(f"role: {role}")
        if args.show_email:
            print(f"email: {email or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
