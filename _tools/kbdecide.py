#!/usr/bin/env python3
"""The operator's decisions of a root or of kb/_self (stdlib only): agents propose them, the operator confirms them.

  kbdecide.py propose --root R TEXT --source S --context C [--review-by DATE] [--links TEXT] [--date DATE]
                                         add a decision with status `proposed` and print its id
  kbdecide.py confirm ID --root R --by operator [--maker M] [--name NAME] [--date DATE]
                                         make a proposed decision `active`; refused without `--by operator`
  kbdecide.py supersede OLD NEW --root R   the active decision NEW takes the place of the active decision OLD
  kbdecide.py invalidate ID --root R --reason TEXT [--date DATE]
                                         withdraw an active decision; its row stays
  kbdecide.py restore ID --root R          bring an invalidated decision back, `active` when a maker confirmed it,
                                         else `proposed`; its row stays and `links` keeps what was invalidated
  kbdecide.py list [--root R] [--status S] [--context REF]
                                         the decisions of one root, or of every root and kb/_self, one per line:
                                         root, id, status, date, by, context, text (tab-separated)

R is a root's name (`python3 _tools/kbroot.py list`) or `_self` for kb/_self; there is no default, so a decision never
lands in a root by omission. The rows go to the root's `_decisions.csv`; its format and rules are in kbcommon
(DECISION_COLS, DECISION_STATUS, CONTEXT_KINDS) and `kb/_self/content-rules.md`, Decisions.

  - A decision's id is `D-` and 8 base32 characters of the sha256 of its text and context, so the same decision
    proposed twice is one id and the second is refused.
  - `source` is where the decision was made, and it is required; a source id in it must be one the root may cite.
    `context` is one or more `kind:value` references (item, fact, source, article, domain) of what it is about.
  - `confirm` is the operator's: it needs `--by operator`, which an agent passes only after the operator said so.
    The decision's date becomes the day it was confirmed. The maker is recorded as the root stores a decision maker
    (`maker_fields`): `--maker M` names a row of the root's decision-makers.csv or of the central register
    kb/_self/decision-makers.csv; a root that keeps names (an internal one) may leave it out and may take `--name`.
  - Nothing is ever deleted: `invalidate` sets the status and the reason, `supersede` marks the old decision
    `superseded` and lists it in the new one's `supersedes`.
  - Every row written passes `check.py`: after each write the files are checked, and a change that would add an
    error is undone and refused. Refusals before a root's first decision go through `policy_refusal`.

Exit: 0 done, 2 refused (a rule above, an unknown root or id, or a file that cannot be read) or bad arguments.
"""
import argparse, base64, datetime, hashlib, re, sys
from pathlib import Path

import check, kbcommon

SELF_ROOT = "_self"  # the name that stands for kb/_self, which is no root
OPERATOR = "operator"  # what `confirm --by` must be, and the maker of an internal root's decision that names none


class Refused(Exception):
    """A request the tool will not carry out; the message says why."""


class Store:
    """Where one root's (or kb/_self's) decisions are kept: `root` is a kbcommon.Root, None for kb/_self."""

    def __init__(self, name):
        if name == SELF_ROOT:
            self.name, self.root, self.base = SELF_ROOT, None, Path(kbcommon.SELF)
            return
        try:
            self.root = kbcommon.root(name)
        except KeyError:
            raise Refused(f"no root {name!r} (python3 _tools/kbroot.py list; kb/_self is {SELF_ROOT})")
        except kbcommon.RootError as e:
            raise Refused(str(e))
        self.name, self.base = name, Path(self.root.path)

    @property
    def path(self):
        return self.base / kbcommon.DECISIONS

    @property
    def label(self):
        return "kb/_self/" + kbcommon.DECISIONS if self.root is None else kbcommon.qualify(self.root, kbcommon.DECISIONS)


def stores(name=None):
    """The Store of `name`, or every root's and kb/_self's when `name` is None."""
    if name is not None:
        return [Store(name)]
    try:
        return [Store(r.name) for r in kbcommon.roots()] + [Store(SELF_ROOT)]
    except kbcommon.RootError as e:
        raise Refused(str(e))


def load(store):
    """The rows of the store's _decisions.csv ([] when it has none): Refused when it cannot be read or its header is
    not kbcommon.DECISION_COLS."""
    if not store.path.is_file():
        return []
    try:
        header, rows = kbcommon.load_csv(str(store.path))
    except kbcommon.CsvError as e:
        raise Refused(str(e))
    if header != kbcommon.DECISION_COLS:
        raise Refused(f"{store.label}: header is {','.join(header or [])!r}, not {','.join(kbcommon.DECISION_COLS)!r}")
    return rows


def known_sources():
    """What check.check_decisions takes as `known`: {root name: its source ids, "*": every root's}."""
    out = {}
    for r in kbcommon.roots():
        try:
            out[r.name] = {x["id"] for x in kbcommon.load_csv(str(Path(r.path) / kbcommon.SOURCES), ("id",))[1]}
        except kbcommon.CsvError:
            out[r.name] = set()
    out["*"] = set().union(*out.values())
    return out


def problems(store):
    """The errors check.py finds in the store's decision files as they are on disk now."""
    owner = {r.id_prefix: r for r in kbcommon.roots()}
    check.errors.clear()
    check.check_decisions(store.root, owner, known_sources())
    found = list(check.errors)
    check.errors.clear()
    return found


def save(store, rows):
    """Write the rows, then check the files: a change that adds an error to what check.py found before is undone and
    refused, so no row kbdecide writes fails check.py. The file is replaced whole, never half written."""
    before = problems(store)
    old = store.path.read_bytes() if store.path.is_file() else None
    kbcommon.write_csv(str(store.path), kbcommon.DECISION_COLS, rows, atomic=True)
    new = [e for e in problems(store) if e not in before]
    if new:
        if old is None:
            store.path.unlink()
        else:
            store.path.write_bytes(old)
        raise Refused("the change would fail check.py: " + "; ".join(new))


def policy_refusal(store, rows):
    """Why `store` may not take a decision yet, or None. The one place a root's rule for how a decision maker is saved
    is enforced before its first decision; `propose` asks it with the rows the file holds. No rule is enforced yet."""
    return None


def maker_fields(store, maker, name):
    """(by, by_ref) to record when the operator confirms a decision, as the store keeps decision makers: the role of
    the maker `maker` names (a row of the store's decision-makers.csv or of the central register) or `name` when the
    store may hold names (kbcommon.maker_names_allowed); a store that may not requires `maker`."""
    names_ok = kbcommon.maker_names_allowed(store.root)
    if name and not names_ok:
        raise Refused(f"{store.name} keeps no names (it is published or not an internal root): leave out --name and "
                      f"name a role with --maker")
    if not maker:
        if not names_ok:
            raise Refused(f"{store.name} keeps decision makers by reference: pass --maker with the id of a row of its "
                          f"{kbcommon.DECISION_MAKERS} or of the central register kb/_self/{kbcommon.DECISION_MAKERS}")
        return name or OPERATOR, ""
    roles = {**read_makers(Path(kbcommon.SELF)), **read_makers(store.base)}
    if maker not in roles:
        raise Refused(f"no decision maker {maker!r} in {store.name}/{kbcommon.DECISION_MAKERS} or the central register")
    return name or roles[maker], maker


def read_makers(base):
    """{id: role} of the decision-makers.csv in the directory `base` ({} when it has none or cannot be read)."""
    try:
        rows = kbcommon.load_csv(str(base / kbcommon.DECISION_MAKERS))[1]
    except kbcommon.CsvError:
        return {}
    return {(r.get("id") or "").strip(): (r.get("role") or "").strip() for r in rows}


def decision_id(text, context):
    """`D-` and the first 8 base32 characters of the sha256 of the decision's text and context, as a source id is made
    from its url (kbid.source_id)."""
    digest = hashlib.sha256(f"{text}\n{context}".encode("utf-8")).digest()
    return f"{kbcommon.DECISION_PREFIX}-" + base64.b32encode(digest).decode("ascii").lower()[:8]


def day(text):
    """The date `text` (YYYY-MM-DD) names, today when it is None; Refused when it is not a real date."""
    if text is None:
        return datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise Refused(f"date {text!r} is not YYYY-MM-DD")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise Refused(f"date {text!r} is not YYYY-MM-DD")
    return text


def find(rows, did, store):
    """The row of decision `did`; Refused when the id is malformed or the file has no such decision."""
    if not kbcommon.DECISION_ID.fullmatch(did or ""):
        raise Refused(f"{did!r} is not a decision id (D-<8 base32>)")
    for r in rows:
        if (r.get("id") or "").strip() == did:
            return r
    raise Refused(f"no decision {did} in {store.label}")


def field(row, key):
    return (row.get(key) or "").strip()


def need(row, status, did, what):
    """Refused unless the decision's status is one of `status` (a tuple): `what` is what was asked of it."""
    if field(row, "status") not in status:
        raise Refused(f"{did} is {field(row, 'status') or 'without a status'}: only {' or '.join(status)} decisions can be {what}")


def cmd_propose(a):
    store = Store(a.root)
    rows = load(store)
    why = policy_refusal(store, rows)
    if why:
        raise Refused(why)
    text, source = " ".join(a.text.split()), " ".join(a.source.split())
    context = "; ".join(kbcommon.split_list(a.context))
    for what, value in (("text", text), ("--source (where the decision was made)", source), ("--context", context)):
        if not value:
            raise Refused(f"a decision needs {what}")
    did = decision_id(text, context)
    if any(field(r, "id") == did for r in rows):
        raise Refused(f"{did} is already in {store.label}: the same text and context (restore or confirm it)")
    row = dict.fromkeys(kbcommon.DECISION_COLS, "")
    row.update(id=did, text=text, source=source, date=day(a.date), context=context, status="proposed",
               review_by=(a.review_by or "").strip(), links=" ".join((a.links or "").split()))
    save(store, rows + [row])
    print(f"{did}\tproposed\t{store.name}")
    return 0


def cmd_confirm(a):
    if a.by != OPERATOR:
        raise Refused(f"only the operator confirms a decision: run it with --by {OPERATOR} once the operator has said so")
    store = Store(a.root)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("proposed",), a.id, "confirmed")
    by, by_ref = maker_fields(store, a.maker, a.name)
    row.update(status="active", by=by, by_ref=by_ref, date=day(a.date))
    save(store, rows)
    print(f"{a.id}\tactive\t{store.name}")
    return 0


def cmd_supersede(a):
    store = Store(a.root)
    rows = load(store)
    if a.old == a.new:
        raise Refused("a decision cannot supersede itself")
    old, new = find(rows, a.old, store), find(rows, a.new, store)
    need(old, ("active",), a.old, "superseded")
    need(new, ("active",), a.new, "the one that supersedes (confirm it first)")
    old["status"] = "superseded"
    new["supersedes"] = "; ".join(kbcommon.split_list(new.get("supersedes")) + [a.old])
    save(store, rows)
    print(f"{a.old}\tsuperseded by {a.new}\t{store.name}")
    return 0


def cmd_invalidate(a):
    store = Store(a.root)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("active",), a.id, "invalidated")  # a proposed one names no maker, which check.py asks of an invalidated one
    reason = " ".join(a.reason.split())
    if not reason:
        raise Refused("--reason is empty: say why the decision no longer holds")
    row.update(status="invalidated", invalidated_reason=reason, invalidated_date=day(a.date))
    save(store, rows)
    print(f"{a.id}\tinvalidated\t{store.name}")
    return 0


def cmd_restore(a):
    store = Store(a.root)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("invalidated",), a.id, "restored")
    kept = f"was invalidated {field(row, 'invalidated_date')}: {field(row, 'invalidated_reason')}"
    status = "active" if field(row, "by") or field(row, "by_ref") else "proposed"  # never a confirmation the operator did not give
    row.update(status=status, invalidated_reason="", invalidated_date="", links="; ".join(filter(None, [field(row, "links"), kept])))
    save(store, rows)
    print(f"{a.id}\t{status}\t{store.name}")
    return 0


def cmd_list(a):
    n = 0
    for store in stores(a.root):
        for r in load(store):
            if a.status and field(r, "status") != a.status:
                continue
            if a.context and not matches(r, a.context):
                continue
            n += 1
            print("\t".join([store.name, field(r, "id"), field(r, "status"), field(r, "date"), field(r, "by"),
                             field(r, "context"), field(r, "text")]))
    print(f"decisions={n}")
    return 0


def matches(row, ref):
    """Whether the decision's context names `ref`: a `kind:value` part, or a bare value of any kind."""
    ref = ref.strip()
    return any(ref in (f"{kind}:{value}", value) for kind, value in kbcommon.context_refs(row.get("context")))


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help, root_required=True):
        p = sub.add_parser(name, help=help)
        p.add_argument("--root", required=root_required, help=f"a root's name, or {SELF_ROOT} for kb/_self")
        return p

    p = add("propose", "add a proposed decision")
    p.add_argument("text", help="the decision")
    p.add_argument("--source", required=True, help="where it was made: a source id of the root, or free text")
    p.add_argument("--context", required=True, help="`;`-separated kind:value references (item, fact, source, article, domain)")
    p.add_argument("--review-by", help="YYYY-MM-DD, when to look at it again")
    p.add_argument("--links", help="free text")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("confirm", "the operator confirms a proposed decision")
    p.add_argument("id")
    p.add_argument("--by", help=f"must be {OPERATOR}")
    p.add_argument("--maker", help="the id of a decision maker of the root's decision-makers.csv or the central register")
    p.add_argument("--name", help="the maker's name, in a root that keeps names")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("supersede", "an active decision takes the place of another")
    p.add_argument("old")
    p.add_argument("new")
    p = add("invalidate", "withdraw a decision, keeping its row")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("restore", "bring an invalidated decision back")
    p.add_argument("id")
    p = add("list", "the decisions of one root or of all", root_required=False)
    p.add_argument("--status", choices=kbcommon.DECISION_STATUS)
    p.add_argument("--context", help="only the decisions whose context names this kind:value (or bare value)")
    return ap


COMMANDS = {"propose": cmd_propose, "confirm": cmd_confirm, "supersede": cmd_supersede, "invalidate": cmd_invalidate,
            "restore": cmd_restore, "list": cmd_list}


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        return COMMANDS[a.cmd](a)
    except Refused as e:
        print(f"refused: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
