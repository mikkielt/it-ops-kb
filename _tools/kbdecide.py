#!/usr/bin/env python3
"""The operator's decisions of a root or of kb/_self (stdlib only): agents propose them, the operator confirms them.

  kbdecide.py propose --root R TEXT --source S --context C [--review-by DATE] [--links TEXT] [--date DATE]
                                         add a decision with status `proposed` and print its id
  kbdecide.py confirm ID --root R --by operator [--maker M] [--name NAME] [--date DATE]
                                         make a proposed decision `active`; refused without `--by operator`
  kbdecide.py record --root R TEXT --source S --context C --by operator [--maker M] [--name NAME] [--review-by DATE]
                     [--links TEXT] [--date DATE]
                                         propose and confirm in one write: an `active` decision, with the maker as
                                         `confirm` records it; refused without `--by operator`, except `--by autopilot`
                                         (maker `autopilot`, `--review-by` required: the operator ratifies or
                                         supersedes it)
  kbdecide.py supersede OLD NEW --root R --by operator
                                         the active decision NEW takes the place of the active decision OLD; refused
                                         without `--by operator`
  kbdecide.py invalidate ID --root R --reason TEXT [--date DATE]
                                         withdraw a proposed or an active decision; its row stays. Open to agents:
                                         it names no maker, so it rejects a proposal as well
  kbdecide.py restore ID --root R --by operator
                                         bring an invalidated decision back, `active` when a maker confirmed it,
                                         else (a rejected proposal) `proposed`; its row stays and `links` keeps what
                                         was invalidated; refused without `--by operator`
  kbdecide.py relink ID --root R --fact PATH:LINE [--old KEY] [--date DATE]
                                         repoint a proposed or active decision's `fact:` reference whose fact is gone to
                                         the fact at PATH:LINE (refused when no fact starts there); its row stays and
                                         `links` keeps the old key. Open to agents, like the sweep that flags it
  kbdecide.py makers R [--policy P --by operator]
                                         show how root R saves its decision makers, or (the operator's) set the policy:
                                         role-only, role-and-name or central-register
  kbdecide.py ratify ID [--root R] --by operator [--date DATE]
                                         the operator takes an autopilot decision as their own: its maker becomes the
                                         operator, its `review_by` falls away; `--root` defaults to `_self`; refused
                                         without `--by operator`
  kbdecide.py revert ID [--root R] --by operator --why TEXT [--date DATE]
                                         the operator withdraws an autopilot decision: it is invalidated (its row stays)
                                         and a story to undo what it changed is filed with `backlog.py new story`;
                                         refused without `--by operator`
  kbdecide.py digest [--out PATH]        write kb/_self/reports/autopilot-digest.md: the autopilot's decisions not yet
                                         ratified, the restricted classes (secrets, push, querylog, agents-rule, delete)
                                         first, each group oldest first, with item, gate, answer and `review_by`
  kbdecide.py sweep [--root R] [--dry-run] [--date DATE]
                                         invalidate every proposed or active decision whose context is broken (rules
                                         below), naming the context in the reason; open to agents
  kbdecide.py list [--root R] [--status S] [--context REF]
                                         the decisions of one root, or of every root and kb/_self, one per line:
                                         root, id, status, date, by, context, text (tab-separated)

R is a root's name (`python3 _tools/kbroot.py list`) or `_self` for kb/_self; there is no default, so a decision never
lands in a root by omission. The rows go to the root's `_decisions.csv`; its format and rules are in kbcommon
(DECISION_COLS, DECISION_STATUS, CONTEXT_KINDS) and `kb/_self/content-rules.md`, Decisions.

The row store is shared: a `Ledger` names the file, columns, id form and check of one kind of rows, and `Store(name,
ledger)`, `load`, `save`, `find`, `need`, `mark_invalidated` and `sweep` work over any of them. DECISIONS is this
tool's; LOGS (`_logs.csv`, `kb/_self/content-rules.md`, Logs) is kblog.py's, which has its own commands and no copy of
the store.

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
  - What an agent may do and what is the operator's: `propose`, `invalidate`, `relink` and `sweep` are open to agents
    (the sweep invalidates a decision whose subject is gone, and a proposal nobody should confirm is rejected the same
    way, with no maker named); `confirm`, `record`, `supersede`, `restore` and `makers --policy` need `--by operator`, which an agent passes
    only after the operator said so, because each makes or brings back a decision that holds.
  - A root saves its decision makers by a policy (kbcommon.POLICIES), one reserved row of its decision-makers.csv.
    There is no default: `propose` in a root with none is refused with the question and the options until the
    operator runs `makers R --policy P --by operator`. role-and-name is refused where kbcommon.maker_names_allowed
    says no names may be kept (a root that is not internal); kb/_self is the central register, holds roles only and
    has no policy to set.
  - `sweep` covers every root and kb/_self, or the one `--root`, and invalidates a proposed or an active decision
    when one of its context references no longer holds: (1) an `item:` is dropped, as its file says or, when sprint
    close or `backlog.py drop` outside a sprint deleted the file, as its last version in git history says (not done:
    dropped; an item that is done, or was deleted done, does not invalidate; one with no history says nothing); (2) a `source:` has a `superseded_by` in its
    _sources.csv; (3) an `article:` or a `domain:` is gone, a root's removal included; (4) its `review_by` is before
    the date. The reason names the reference (`item:TK-x dropped`), several joined by `; `. A `fact:` whose key no
    fact has any more (the fact was reworded or removed) invalidates nothing: the decision is flagged with a line
    `ID<TAB>relink<TAB>root<TAB>fact:KEY<TAB>PATH:LINE<TAB>text` naming the current fact likeliest to be it (`-` when
    none is likely enough) and no row changes; `relink` repoints it. `--dry-run` prints what it would invalidate and
    writes nothing; `--date` is the day taken as today (default: today). No row is deleted.
  - The likeliest fact (`suggest`): a key is a hash, so the old text is read back from the git history of the files the
    fact was in (its `_anchors.csv` rows, the context's articles), and the facts of those files (else of the root;
    kb/_self: of every root) are scored by difflib's ratio of the two texts' terms, at least MIN_SIMILAR; with no
    history, by the share of the key terms the anchors kept, the questions doc2query generated for the fact, or the
    decision's own text that a fact holds. A root points only at its own facts.
  - `relink` replaces the one gone `fact:` of a proposed or active decision with the key of the fact at PATH:LINE
    (`--old KEY` when several are gone), refused when no fact starts at that line, the fact is another root's, or
    none of the context's facts is gone; the row stays and `links` records the old key, the new fact and the day.
    It is open to agents: a decision's text and maker do not change, the pointer is what it is about, and the sweep
    that flags it may invalidate a decision as well.
  - Every row written passes `check.py`: after each write the files are checked, and a change that would add an
    error is undone and refused. Refusals before a root's first decision go through `policy_refusal`.

Exit: 0 done, 2 refused (a rule above, an unknown root or id, or a file that cannot be read) or bad arguments.
"""
import argparse, base64, datetime, difflib, hashlib, json, re, subprocess, sys
from pathlib import Path

import check, kbcommon, kbfacts

SELF_ROOT = "_self"  # the name that stands for kb/_self, which is no root
AUTOPILOT = "autopilot"  # the maker `record --by autopilot` names: a decision the operator ratifies or supersedes
OPERATOR = "operator"  # what `confirm --by` must be, and the maker of an internal root's decision that names none


class Refused(Exception):
    """A request the tool will not carry out; the message says why."""


class Ledger:
    """One kind of row file the store keeps in a root or in kb/_self: its `noun` (as a refusal says it), `file`, `cols`,
    `id_form` (a compiled regex) with the `prefix` of its ids, its `status` values, the `check` that judges it (check.py's, run over a
    root as check.check_decisions is), the `text_max` of one free-text cell (None: no limit), and `fact_gone`: what a
    context `fact:` that no fact has any more does to a row, `flag` (a relink line, the row stays) or `invalidate`."""

    def __init__(self, noun, file, cols, id_form, prefix, status, check, text_max=None, fact_gone="flag"):
        self.noun, self.file, self.cols, self.id_form, self.prefix, self.status = noun, file, cols, id_form, prefix, status
        self.check, self.text_max, self.fact_gone = check, text_max, fact_gone


DECISIONS = Ledger("decision", kbcommon.DECISIONS, kbcommon.DECISION_COLS, kbcommon.DECISION_ID, kbcommon.DECISION_PREFIX,
                   kbcommon.DECISION_STATUS, check.check_decisions)
LOGS = Ledger("log row", check.LOGS, check.LOG_COLS, check.LOG_ID, check.LOG_PREFIX, check.LOG_STATUS, check.check_logs,
              text_max=check.LOG_TEXT_MAX, fact_gone="invalidate")


class Store:
    """Where one root's (or kb/_self's) rows of one ledger (default: decisions) are kept: `root` is a kbcommon.Root,
    None for kb/_self."""

    def __init__(self, name, ledger=DECISIONS):
        self.ledger = ledger
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
        return self.base / self.ledger.file

    @property
    def label(self):
        return "kb/_self/" + self.ledger.file if self.root is None else kbcommon.qualify(self.root, self.ledger.file)


def stores(name=None, ledger=DECISIONS):
    """The Store of `name`, or every root's and kb/_self's when `name` is None."""
    if name is not None:
        return [Store(name, ledger)]
    try:
        return [Store(r.name, ledger) for r in kbcommon.roots()] + [Store(SELF_ROOT, ledger)]
    except kbcommon.RootError as e:
        raise Refused(str(e))


def load(store):
    """The rows of the store's file ([] when it has none): Refused when it cannot be read or its header is not the
    ledger's columns."""
    if not store.path.is_file():
        return []
    try:
        header, rows = kbcommon.load_csv(str(store.path))
    except kbcommon.CsvError as e:
        raise Refused(str(e))
    if header != store.ledger.cols:
        raise Refused(f"{store.label}: header is {','.join(header or [])!r}, not {','.join(store.ledger.cols)!r}")
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
    """The errors check.py finds in the store's files (the ledger's check) as they are on disk now."""
    owner = {r.id_prefix: r for r in kbcommon.roots()}
    check.errors.clear()
    store.ledger.check(store.root, owner, known_sources())
    found = list(check.errors)
    check.errors.clear()
    return found


def save(store, rows, path=None, cols=None):
    """Write the rows (of the store's file, or of `path` with the columns `cols`), then check the files: a change that
    adds an error to what check.py found before is undone and refused, so no row kbdecide writes fails check.py. The
    file is replaced whole, never half written."""
    path, cols = path or store.path, cols or store.ledger.cols
    before = problems(store)
    old = path.read_bytes() if path.is_file() else None
    kbcommon.write_csv(str(path), cols, rows, atomic=True)
    new = [e for e in problems(store) if e not in before]
    if new:
        if old is None:
            path.unlink()
        else:
            path.write_bytes(old)
        raise Refused("the change would fail check.py: " + "; ".join(new))


def policy_question(store):
    """The question a root with no policy is asked, with the options it may take."""
    options = [f"{p} ({what})" for p, what in kbcommon.POLICIES.items()
               if p != "role-and-name" or kbcommon.maker_names_allowed(store.root, p)]
    return (f"{store.name} has no storage policy for decision makers. How is a decision maker saved there? Options: "
            + "; ".join(options) + f". The operator sets it: python3 _tools/kbdecide.py makers {store.name} "
            f"--policy <option> --by {OPERATOR}")


def policy_refusal(store, rows):
    """Why `store` may not take a decision yet, or None. The one place a root's rule for how a decision maker is saved
    is enforced before its first decision; `propose` asks it with the rows the file holds. A root with no policy is
    refused with the question and its options; kb/_self, the central register, has a fixed one (roles only)."""
    if store.root is None or kbcommon.root_policy(store.root):
        return None
    return policy_question(store)


def maker_fields(store, maker, name):
    """(by, by_ref) to record when the operator confirms a decision, as the store keeps decision makers: the role of
    the maker `maker` names (a row of the store's decision-makers.csv or of the central register) or `name` when the
    store may hold names (kbcommon.maker_names_allowed); a store that may not requires `maker`."""
    names_ok = kbcommon.maker_names_allowed(store.root)
    if name and not names_ok:
        raise Refused(f"{store.name} keeps no names (it is not an internal root or its policy keeps none): leave out "
                      f"--name and name a role with --maker")
    if not maker:
        if not names_ok:
            raise Refused(f"{store.name} keeps decision makers by reference: pass --maker with the id of a row of its "
                          f"{kbcommon.DECISION_MAKERS} or of the central register kb/_self/{kbcommon.DECISION_MAKERS}")
        return name or OPERATOR, ""
    central = kbcommon.root_policy(store.root) == "central-register"
    roles = {**read_makers(Path(kbcommon.SELF)), **({} if central else read_makers(store.base))}
    if maker not in roles:
        where = "the central register" if central else f"{store.name}/{kbcommon.DECISION_MAKERS} or the central register"
        raise Refused(f"no decision maker {maker!r} in {where}")
    return name or roles[maker], maker


def read_makers(base):
    """{id: role} of the decision-makers.csv in the directory `base` ({} when it has none or cannot be read)."""
    try:
        rows = kbcommon.load_csv(str(base / kbcommon.DECISION_MAKERS))[1]
    except kbcommon.CsvError:
        return {}
    return {(r.get("id") or "").strip(): (r.get("role") or "").strip() for r in rows
            if (r.get("id") or "").strip() != kbcommon.POLICY_ROW}


def row_id(ledger, *parts):
    """The ledger's prefix, `-` and the first 8 base32 characters of the sha256 of the parts joined by line breaks, as a
    source id is made from its url (kbid.source_id)."""
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).digest()
    return f"{ledger.prefix}-" + base64.b32encode(digest).decode("ascii").lower()[:8]


def decision_id(text, context):
    """`D-` and the first 8 base32 characters of the sha256 of the decision's text and context."""
    return row_id(DECISIONS, text, context)


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
    """The row `did`; Refused when the id is malformed or the file has no such row."""
    noun = store.ledger.noun
    if not store.ledger.id_form.fullmatch(did or ""):
        raise Refused(f"{did!r} is not a {noun} id ({store.ledger.prefix}-<8 base32>)")
    for r in rows:
        if (r.get("id") or "").strip() == did:
            return r
    raise Refused(f"no {noun} {did} in {store.label}")


def field(row, key):
    return (row.get(key) or "").strip()


def need(row, status, did, what, noun="decision"):
    """Refused unless the row's status is one of `status` (a tuple): `what` is what was asked of it."""
    if field(row, "status") not in status:
        raise Refused(f"{did} is {field(row, 'status') or 'without a status'}: only {' or '.join(status)} {noun}s can be {what}")


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


def need_operator(a, what):
    """Refused unless `--by` is the operator: `what` is what only the operator does."""
    if a.by != OPERATOR:
        raise Refused(f"only the operator {what}: run it with --by {OPERATOR} once the operator has said so")


def cmd_confirm(a):
    need_operator(a, "confirms a decision")
    store = Store(a.root)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("proposed",), a.id, "confirmed")
    by, by_ref = maker_fields(store, a.maker, a.name)
    row.update(status="active", by=by, by_ref=by_ref, date=day(a.date))
    save(store, rows)
    print(f"{a.id}\tactive\t{store.name}")
    return 0


def cmd_record(a):
    """Write an operator's decision as `active` in one step (propose and confirm in one write, so a refusal leaves no
    proposed row behind)."""
    if a.by == AUTOPILOT:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", (a.review_by or "").strip()):
            raise Refused("an autopilot decision needs --review-by YYYY-MM-DD: the operator ratifies or supersedes it by then")
        if a.maker not in (None, AUTOPILOT) or a.name:
            raise Refused(f"an autopilot decision's maker is {AUTOPILOT!r}: leave out --name and --maker")
        a.maker = AUTOPILOT
    else:
        need_operator(a, "records a decision")
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
        raise Refused(f"{did} is already in {store.label}: the same text and context")
    by, by_ref = maker_fields(store, a.maker, a.name)
    row = dict.fromkeys(kbcommon.DECISION_COLS, "")
    row.update(id=did, text=text, by=by, by_ref=by_ref, source=source, date=day(a.date), context=context,
               status="active", review_by=(a.review_by or "").strip(), links=" ".join((a.links or "").split()))
    save(store, rows + [row])
    print(f"{did}\tactive\t{store.name}")
    return 0


def cmd_makers(a):
    store = Store(a.root)
    if store.root is None:
        raise Refused(f"{SELF_ROOT} is the central register: it holds roles only and has no storage policy to set")
    path = store.base / kbcommon.DECISION_MAKERS
    try:
        header, rows = kbcommon.load_csv(str(path)) if path.is_file() else (kbcommon.MAKER_COLS, [])
    except kbcommon.CsvError as e:
        raise Refused(str(e))
    if header != kbcommon.MAKER_COLS:
        raise Refused(f"{kbcommon.qualify(store.root, kbcommon.DECISION_MAKERS)}: header is {','.join(header or [])!r}, "
                      f"not {','.join(kbcommon.MAKER_COLS)!r}")
    if a.policy is None:
        print(f"policy={kbcommon.root_policy(store.root) or 'unset'}\t{store.name}")
        for r in rows:
            if field(r, "id") != kbcommon.POLICY_ROW:
                print("\t".join([field(r, "id"), field(r, "role"), field(r, "name")]))
        return 0
    need_operator(a, "sets how a root saves its decision makers")
    if a.policy not in kbcommon.POLICIES:
        raise Refused(f"policy {a.policy!r} is not one of {'|'.join(kbcommon.POLICIES)}")
    if a.policy == "role-and-name" and not kbcommon.maker_names_allowed(store.root, a.policy):
        raise Refused(f"{store.name} may not keep decision makers by {a.policy}: it is not an internal root, so it keeps "
                      f"no names (choose role-only or central-register)")
    row = dict.fromkeys(kbcommon.MAKER_COLS, "")
    row.update(id=kbcommon.POLICY_ROW, role=a.policy)
    save(store, [row] + [r for r in rows if field(r, "id") != kbcommon.POLICY_ROW], path, kbcommon.MAKER_COLS)
    print(f"policy={a.policy}\t{store.name}")
    return 0


def cmd_supersede(a):
    need_operator(a, "supersedes a decision")
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


def mark_invalidated(store, row, reason, when):
    """Set the row invalidated with its reason, kept in the file. A ledger with an `invalidated_date` column takes the
    day there; another notes it in `links` when the cell has room."""
    row.update(status="invalidated", invalidated_reason=reason)
    if "invalidated_date" in store.ledger.cols:
        row["invalidated_date"] = when
        return
    note = "; ".join(filter(None, [field(row, "links"), f"invalidated {when}"]))
    if store.ledger.text_max is None or len(note) <= store.ledger.text_max:
        row["links"] = note


def invalidate(a, ledger=DECISIONS):
    """Withdraw a proposed or active row of the ledger, keeping it (`--reason` says why)."""
    store = Store(a.root, ledger)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("proposed", "active"), a.id, "invalidated", ledger.noun)  # a rejected proposal names no maker: check.py takes that of an invalidated row
    reason = " ".join(a.reason.split())
    if not reason:
        raise Refused(f"--reason is empty: say why the {ledger.noun} no longer holds")
    mark_invalidated(store, row, reason, day(a.date))
    save(store, rows)
    print(f"{a.id}\tinvalidated\t{store.name}")
    return 0


def cmd_invalidate(a):
    return invalidate(a)


def cmd_restore(a):
    need_operator(a, "restores a decision")
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


ORIGIN = re.compile(r"backlog item (\S+) gate (\S+)")  # the source of a decision `backlog.py answer --record` writes
RESTRICTED = ("secrets", "push", "querylog", "agents-rule", "delete")  # the classes the digest lists first
DIGEST = Path(kbcommon.SELF) / "reports" / "autopilot-digest.md"


def autopilot_row(rows, did, store, what):
    """The active decision `did` the autopilot made: Refused when it is another's or is not active."""
    row = find(rows, did, store)
    need(row, ("active",), did, what)
    if field(row, "by") != AUTOPILOT:
        raise Refused(f"{did} is not an autopilot decision (by {field(row, 'by') or 'no one'}): only the autopilot's can be {what}")
    return row


def origin(row):
    """(item id, gate id) the decision answered, from its source; ('', '') when its source names none."""
    m = ORIGIN.search(field(row, "source"))
    return m.groups() if m else ("", "")


def read_item(iid):
    """The backlog item file `iid` as a dict, None when there is none or it cannot be read."""
    try:
        item = json.loads((Path(kbcommon.SELF) / "backlog" / f"{iid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return item if isinstance(item, dict) else None


def cmd_ratify(a):
    """The operator takes an autopilot decision as their own: its maker becomes the operator's, its review falls away
    (the sweep invalidates a decision whose `review_by` passed), and `links` keeps who made it and when."""
    need_operator(a, "ratifies an autopilot decision")
    store = Store(a.root or SELF_ROOT)
    rows = load(store)
    row = autopilot_row(rows, a.id, store, "ratified")
    when = day(a.date)
    by, by_ref = maker_fields(store, OPERATOR, None)
    kept = f"ratified {when}; made by the autopilot {field(row, 'date')}"
    row.update(by=by, by_ref=by_ref, date=when, review_by="", links="; ".join(filter(None, [field(row, "links"), kept])))
    save(store, rows)
    print(f"{a.id}\tratified\t{store.name}")
    return 0


def story_goal(did, text, iid, gate, item, why):
    """The goal of the story that undoes decision `did`: what it answered, what the item touched, why the operator reverted it."""
    title = (item or {}).get("title") or "item file gone"
    touches = ", ".join(map(str, (item or {}).get("touches") or [])) or "no file named"
    goal = (f"What autopilot decision {did} changed is undone, or the operator's reason to keep it is recorded: the autopilot "
            f"answered gate {gate} of {iid} ({title}) with: {text}. The operator reverted it because: {why}. "
            f"That item's touches: {touches}.")
    return goal[:2000]


def file_story(did, row, why):
    """File, through backlog.py, the story that undoes the decision's work; its id. Refused with backlog's reason."""
    iid, gate = origin(row)
    item = read_item(iid) if iid else None
    title = f"Undo autopilot decision {did}: {(item or {}).get('title') or field(row, 'text')}"
    argv = [sys.executable, str(Path(kbcommon.TOOLS) / "backlog.py"), "new", "story", "--title", " ".join(title.split())[:200],
            "--goal", story_goal(did, field(row, "text"), iid or "its item", gate or "its gate", item, why)]
    for t in (item or {}).get("touches") or []:
        argv += ["--touch", str(t)]
    p = subprocess.run(argv, cwd=kbcommon.HOME, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    m = re.search(r"new story (\S+)", p.stdout)
    if p.returncode or not m:
        raise Refused(f"the story that undoes {did} was not filed: {(p.stdout + p.stderr).strip()}")
    return m.group(1)


def cmd_revert(a):
    """The operator withdraws an autopilot decision: it is invalidated (its row stays) and a story to undo what it
    changed is filed first, so a refusal files nothing."""
    need_operator(a, "reverts an autopilot decision")
    why = " ".join((a.why or "").split())
    if not why:
        raise Refused("--why is empty: say why the operator reverts the decision")
    store = Store(a.root or SELF_ROOT)
    rows = load(store)
    row = autopilot_row(rows, a.id, store, "reverted")
    when = day(a.date)
    story = file_story(a.id, row, why)
    mark_invalidated(store, row, f"reverted by the operator: {why}", when)
    save(store, rows)
    print(f"{a.id}\tinvalidated\t{store.name}\tstory {story}")
    return 0


def digest_group(cls):
    return 0 if cls in RESTRICTED else 1


def unratified(store):
    """[(class, item id, item title, gate, row)] of the store's active autopilot decisions, the restricted classes first,
    each group oldest first (then by id)."""
    import bl_authority  # only the digest reads a gate's class: a scratch repository without the backlog still has the rest
    out = []
    for row in load(store):
        if field(row, "status") != "active" or field(row, "by") != AUTOPILOT:
            continue
        iid, gate = origin(row)
        item = read_item(iid) if iid else None
        g = next((g for g in (item or {}).get("gates") or [] if isinstance(g, dict) and g.get("id") == gate), None)
        cls = bl_authority.gate_class(item or {}, g or {"id": gate, "question": field(row, "text")})
        out.append((cls, iid, (item or {}).get("title") or "item file gone", gate, row))
    return sorted(out, key=lambda x: (digest_group(x[0]), field(x[4], "date"), field(x[4], "id")))


def digest_text(entries):
    lines = ["# Autopilot digest", "",
             "The autopilot's decisions the operator has not ratified, written by `python3 _tools/kbdecide.py digest`: the "
             "restricted classes first, each group oldest first. Ratify one with `python3 _tools/kbdecide.py ratify ID --by "
             f"{OPERATOR}`, or revert it with `python3 _tools/kbdecide.py revert ID --by {OPERATOR} --why TEXT`.", ""]
    if not entries:
        return "\n".join(lines + ["No unratified autopilot decisions.", ""])
    for heading, group in (("Restricted classes (" + ", ".join(RESTRICTED) + ")", 0), ("Other classes", 1)):
        part = [e for e in entries if digest_group(e[0]) == group]
        if not part:
            continue
        lines += [f"## {heading}", ""]
        for cls, iid, title, gate, row in part:
            lines.append(f"- {field(row, 'id')} ({cls}): item {iid or '-'} \"{title}\", gate {gate or '-'}, answer \"{field(row, 'text')}\", "
                         f"review_by {field(row, 'review_by') or '-'}")
        lines.append("")
    return "\n".join(lines)


def cmd_digest(a):
    entries = unratified(Store(SELF_ROOT))
    path = Path(a.out) if a.out else DIGEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(digest_text(entries), encoding="utf-8", newline="\n")
    print(f"digest\t{len(entries)} unratified\t{path}")
    return 0


def git_out(*args):
    """The output of `git ARGS` run in this repository, '' when it fails (no git, no repository, no such revision)."""
    try:
        p = subprocess.run(["git", *args], cwd=kbcommon.HOME, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    except OSError:
        return ""
    return p.stdout if p.returncode == 0 else ""


class Context:
    """What the context references of decisions are checked against, read once per sweep: backlog items (the file, or
    the last version git history keeps of a deleted one) and the sources' `superseded_by`."""

    def __init__(self):
        self.items, self.sources = {}, None

    def item_status(self, iid):
        """The status of backlog item `iid`: its file's; else, for a file that was deleted (sprint close, or `drop`
        outside a sprint), `done` when its last version in git history was done and `dropped` for any other status;
        else '' (never seen, or no git history to ask)."""
        if iid not in self.items:
            rel = f"kb/_self/backlog/{iid}.json"
            path = Path(kbcommon.HOME) / rel
            here = path.is_file()
            text = path.read_text(encoding="utf-8") if here else self.deleted_version(rel)
            try:
                data = json.loads(text) if text else None
            except ValueError:
                data = None
            status = (data.get("status") or "") if isinstance(data, dict) else ""
            if not here and status not in ("", "done"):
                status = "dropped"  # deleted by sprint close or by `backlog.py drop` outside a sprint, and never done
            self.items[iid] = status
        return self.items[iid]

    @staticmethod
    def deleted_version(rel):
        """The text of `rel` as it was just before the newest commit that deleted it, '' when git holds none."""
        last = git_out("log", "-1", "--diff-filter=D", "--format=%H", "--", rel).strip()
        return git_out("show", f"{last}^:{rel}") if last else ""

    def superseded_by(self, store, sid):
        """What `superseded_by` says of source `sid` in the store's root (kb/_self: in any root), '' when nothing."""
        if self.sources is None:
            self.sources = {}
            for r in kbcommon.roots():
                try:
                    rows = kbcommon.load_csv(str(Path(r.path) / kbcommon.SOURCES), ("id",))[1]
                except kbcommon.CsvError:
                    continue
                self.sources[r.name] = {field(x, "id"): " ".join(field(x, "superseded_by").split()) for x in rows}
        pools = list(self.sources.values()) if store.root is None else [self.sources.get(store.name, {})]
        return next((p[sid] for p in pools if p.get(sid)), "")


def gone(store, kind, value):
    """Whether the article or domain `value` of a context reference no longer exists: in the store's root, or, in
    kb/_self, in the root its `<root>/<path>` names (a root that is gone too)."""
    where, rel = (Path(store.root.path), value) if store.root else (None, value)
    if store.root is None:
        owner, rel = kbcommon.split(value)
        where = Path(owner.path) if owner else None
    if where is None or not rel:
        return True
    return not ((where / f"{rel}.md").is_file() if kind == "article" else (where / rel).is_dir())


def broken(store, row, ctx, today, facts=None):
    """The reasons, `<ref> <what>`, why the context of the row no longer holds; [] when it holds. A ledger whose
    `fact_gone` is `invalidate` (not `flag`) also takes each `fact:` of `facts` (a Facts) that no fact has any more."""
    out = []
    for kind, value in kbcommon.context_refs(row.get("context")):
        if kind == "item" and ctx.item_status(value) == "dropped":
            out.append(f"item:{value} dropped")
        elif kind == "source" and ctx.superseded_by(store, value):
            out.append(f"source:{value} superseded by {ctx.superseded_by(store, value)}")
        elif kind in ("article", "domain") and gone(store, kind, value):
            out.append(f"{kind}:{value} is gone")
    if store.ledger.fact_gone == "invalidate" and facts is not None:
        out += [f"fact:{key} is gone" for key in gone_facts(row, facts)]
    review = field(row, "review_by")
    if review and review < today:  # ISO dates compare as text; a malformed review_by is check.py's to report
        out.append(f"review_by {review} passed")
    return out


MIN_SIMILAR = 0.5  # the least similarity (0 to 1) a current fact needs to be offered for a gone one
HISTORY = 40  # the commits of a file read back for the text of a fact that is gone
CLIP = 200  # characters of a suggested fact's text that sweep prints


class Facts:
    """The facts the kb has now (tagged units of every root), read on first use, so a sweep of decisions that name no
    fact reads none. A fact is known by its key (kbfacts.fact_key) and found by `PATH:LINE`."""

    def __init__(self):
        self._units = self._keys = self._at = None

    def load(self):
        if self._units is None:
            self._units, self._keys, self._at = [u for u in kbfacts.units() if u["tags"]], {}, {}
            for u in self._units:
                u["key"] = kbfacts.fact_key(u["text"])
                self._keys.setdefault(u["key"], u)
                self._at[(u["path"], u["line"])] = u
        return self._units

    def live(self, key):
        self.load()
        return key in self._keys

    def allowed(self, store):
        """The facts a decision of `store` may point at: its root's own (kb/_self: any root's), as a root cites only
        its own sources."""
        return [u for u in self.load() if store.root is None or kbfacts.root_name(u["path"]) == store.name]

    def at(self, store, spec):
        """The fact `spec` (`PATH:LINE`, as rag.py pack prints it: qualified, or inside the root of `store`) names;
        Refused when no fact starts at that line or it is another root's."""
        path, _, line = spec.strip().rpartition(":")
        if not path or not line.isdigit():
            raise Refused(f"--fact {spec!r} is not PATH:LINE (as rag.py pack prints it, such as public/auth/kerberos.md:12)")
        path = path.replace("\\", "/")
        if kbcommon.split(path)[0] is None and store.root is not None:
            path = kbcommon.qualify(store.root, path)
        self.load()
        u = self._at.get((path, int(line)))
        if u is None:
            raise Refused(f"{spec} is no fact: no tagged bullet, table row or data row starts at that line (python3 "
                          f"_tools/rag.py show {spec}); in {SELF_ROOT} a path is written <root>/<path>")
        if store.root is not None and kbfacts.root_name(u["path"]) != store.name:
            raise Refused(f"{spec} is a fact of root {kbfacts.root_name(u['path'])}: {store.name} points only at its own facts")
        return u


def gone_facts(row, facts):
    """The keys of the `fact:` references of decision `row` that no fact has any more, in order."""
    return list(dict.fromkeys(v for k, v in kbcommon.context_refs(row.get("context")) if k == "fact" and not facts.live(v)))


def old_text(key, qpaths):
    """The text fact `key` had: its tagged unit in the newest of the last HISTORY versions git holds of the files
    `qpaths` (qualified) that has it; '' when none does or git has no history to ask."""
    for q in qpaths:
        root, rel = kbcommon.split(q)
        if root is None:
            continue
        repo = kbcommon.repo_rel(str(Path(root.path) / rel))
        for sha in git_out("log", f"-n{HISTORY}", "--format=%H", "--", repo).split():
            text = git_out("show", f"{sha}:{repo}")
            for u in (kbfacts.md_units(q, text) if rel.endswith(".md") else kbfacts.csv_units(q, text)):
                if u.get("tags") and kbfacts.fact_key(u["text"]) == key:
                    return u["text"]
    return ""


def anchor_rows(key):
    """[(Root, row)] of every root's _anchors.csv for fact `key`: where the fact was and its key terms."""
    out = []
    for r in kbcommon.roots():
        try:
            rows = kbcommon.load_csv(str(Path(r.path) / kbcommon.ANCHORS))[1]
        except kbcommon.CsvError:
            continue
        out += [(r, x) for x in rows if field(x, "fact") == key]
    return out


def suggest(store, row, key, facts):
    """The current fact likeliest to be fact `key` reworded, or None. Where it was: the files of its _anchors.csv rows
    and the context's articles; those facts first, then every fact the store may point at.
      - the old text is read back from git history of those files when a version holds it, and a fact scores by
        difflib's ratio of the two texts' terms (kbfacts.terms: stems), in order;
      - else the hint is what the kb kept of it: the key terms of its anchors and the words of the questions doc2query
        generated for it, else the decision's own text, and a fact scores by the share of the hint it holds.
    A fact scores at least MIN_SIMILAR or is not offered; the best wins, the first of equals; another fact the
    decision names is never offered."""
    refs = kbcommon.context_refs(row.get("context"))
    anchors = anchor_rows(key)
    paths = [kbcommon.qualify(r, x["path"]) for r, x in anchors]
    paths += [(v if store.root is None else kbcommon.qualify(store.root, v)) + ".md" for k, v in refs if k == "article"]
    paths = list(dict.fromkeys(paths))
    old = old_text(key, paths)
    if kbfacts.terms(old):
        score = text_scorer(old)
    else:
        hint = {t.strip() for _, x in anchors for t in field(x, "terms").split(";") if t.strip()}
        for q in kbfacts.expansions().get(key, ()):
            hint |= set(kbfacts.terms(q))
        score = hint_scorer(hint or set(kbfacts.terms(field(row, "text"))))
    named = {v for k, v in refs if k == "fact"}
    pool = [u for u in facts.allowed(store) if u["key"] not in named]
    near = [u for u in pool if u["path"] in paths]
    for group in ([near, pool] if near else [pool]):
        if top := closest(group, score):
            return top
    return None


def text_scorer(old):
    """score(text): how like the text `old` another text is, 0 to 1: difflib's ratio of the two terms in order."""
    sm = difflib.SequenceMatcher(autojunk=False)
    sm.set_seq2(kbfacts.terms(old))

    def score(text):
        sm.set_seq1(kbfacts.terms(text))
        if sm.real_quick_ratio() < MIN_SIMILAR or sm.quick_ratio() < MIN_SIMILAR:  # the cheap bounds first
            return 0.0
        return sm.ratio()
    return score


def hint_scorer(hint):
    """score(text): the share of the terms in `hint` (a set) that the text holds, 0 to 1."""
    def score(text):
        return len(hint & set(kbfacts.terms(text))) / len(hint) if hint else 0.0
    return score


def closest(units, score):
    """The unit whose text scores highest, at least MIN_SIMILAR, the first of equals; None when none does."""
    top, top_score = None, MIN_SIMILAR
    for u in units:
        s = score(u["text"])
        if s >= top_score and (top is None or s > top_score):
            top, top_score = u, s
    return top


def relink_line(store, row, key, hit):
    """What sweep prints of a decision whose fact is gone: id, relink, root, the old key, the suggested PATH:LINE (`-`
    when none) and its text."""
    text = " ".join(hit["text"].split()) if hit else "(no current fact is likely enough)"
    if len(text) > CLIP:
        text = text[:CLIP - 3] + "..."
    return "\t".join([field(row, "id"), "relink", store.name, f"fact:{key}", f"{hit['path']}:{hit['line']}" if hit else "-", text])


def clip_reason(store, why):
    """`why` cut to the ledger's free-text limit, so a long list of broken references never makes the file fail."""
    cap = store.ledger.text_max
    return why if cap is None or len(why) <= cap else why[:cap - 3] + "..."


def sweep(a, ledger=DECISIONS):
    """Invalidate every proposed or active row of the ledger, in the root `a.root` or in all, whose context is broken
    (the rules in the docstring); a decision whose only fault is a `fact:` that is gone is flagged for `relink`."""
    today, ctx, facts, refused, n, flagged = day(a.date), Context(), Facts(), [], 0, 0
    for store in stores(a.root, ledger):
        rows, hit, flag = load(store), [], []
        for r in rows:
            if field(r, "status") not in ("proposed", "active"):
                continue
            if why := broken(store, r, ctx, today, facts):
                hit.append((r, "; ".join(why)))
            elif ledger.fact_gone == "flag":  # a context that holds apart from a fact that is gone is flagged, its row left as it is
                flag += [(r, key) for key in gone_facts(r, facts)]
        for r, key in flag:
            print(relink_line(store, r, key, suggest(store, r, key, facts)))
        flagged += len(flag)
        if not hit:
            continue
        for r, why in hit:
            print(f"{field(r, 'id')}\t{'would invalidate' if a.dry_run else 'invalidated'}\t{store.name}\t{why}")
            mark_invalidated(store, r, clip_reason(store, why), today)
        if not a.dry_run:
            try:
                save(store, rows)
            except Refused as e:  # one store's refusal leaves its file as it was; the others are still swept
                refused.append(f"{store.name}: {e}")
                continue
        n += len(hit)
    print(f"{'would_invalidate' if a.dry_run else 'invalidated'}={n}")
    if ledger.fact_gone == "flag":
        print(f"relink={flagged}")
    for why in refused:
        print(f"refused: {why}")
    return 2 if refused else 0


def cmd_sweep(a):
    return sweep(a)


def cmd_relink(a):
    store = Store(a.root)
    rows = load(store)
    row = find(rows, a.id, store)
    need(row, ("proposed", "active"), a.id, "relinked")
    facts, when = Facts(), day(a.date)
    target = facts.at(store, a.fact)
    named = [v for k, v in kbcommon.context_refs(row.get("context")) if k == "fact"]
    gone = gone_facts(row, facts)
    if a.old:
        if a.old not in named:
            raise Refused(f"{a.id} has no context fact:{a.old} (its facts: {', '.join(named) or 'none'})")
        if a.old not in gone:
            raise Refused(f"fact:{a.old} of {a.id} still exists: relink repoints a fact that is gone")
        old = a.old
    elif len(gone) == 1:
        old = gone[0]
    elif not gone:
        raise Refused(f"no fact of the context of {a.id} is gone: nothing to relink")
    else:
        raise Refused(f"{a.id} has several facts that are gone ({', '.join(gone)}): name the one to repoint with --old KEY")
    new = target["key"]
    parts = kbcommon.split_list(row.get("context"))
    parts = [p for p in parts if p != f"fact:{old}"] if f"fact:{new}" in parts else [f"fact:{new}" if p == f"fact:{old}" else p for p in parts]
    row["context"] = "; ".join(parts)
    row["links"] = "; ".join(filter(None, [field(row, "links"), f"relinked fact:{old} to fact:{new} ({target['path']}:{target['line']}) on {when}"]))
    save(store, rows)
    print(f"{a.id}\trelinked\t{store.name}\tfact:{old}\tfact:{new}\t{target['path']}:{target['line']}")
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
    p = add("record", "the operator's decision, written as active in one step")
    p.add_argument("text", help="the decision")
    p.add_argument("--by", help=f"must be {OPERATOR}, or {AUTOPILOT} (with --review-by)")
    p.add_argument("--source", required=True, help="where it was made: a source id of the root, or free text")
    p.add_argument("--context", required=True, help="`;`-separated kind:value references (item, fact, source, article, domain)")
    p.add_argument("--maker", help="the id of a decision maker of the root's decision-makers.csv or the central register")
    p.add_argument("--name", help="the maker's name, in a root that keeps names")
    p.add_argument("--review-by", help="YYYY-MM-DD, when to look at it again")
    p.add_argument("--links", help="free text")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("supersede", "an active decision takes the place of another")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--by", help=f"must be {OPERATOR}")
    p = add("invalidate", "withdraw a proposed or active decision, keeping its row")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("restore", "the operator brings an invalidated decision back")
    p.add_argument("id")
    p.add_argument("--by", help=f"must be {OPERATOR}")
    p = add("ratify", "the operator makes an autopilot decision their own", root_required=False)
    p.add_argument("id")
    p.add_argument("--by", help=f"must be {OPERATOR}")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = add("revert", "the operator withdraws an autopilot decision and a story undoes what it changed", root_required=False)
    p.add_argument("id")
    p.add_argument("--by", help=f"must be {OPERATOR}")
    p.add_argument("--why", help="why the operator reverts it")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p = sub.add_parser("digest", help="write the unratified autopilot decisions to kb/_self/reports/autopilot-digest.md")
    p.add_argument("--out", help="write here instead")
    p = sub.add_parser("makers", help="show or set how a root saves its decision makers")
    p.add_argument("root", help="a root's name")
    p.add_argument("--policy", help=f"{'|'.join(kbcommon.POLICIES)}; the operator's")
    p.add_argument("--by", help=f"must be {OPERATOR} with --policy")
    p = add("relink", "repoint a decision's gone fact reference to the fact at PATH:LINE")
    p.add_argument("id")
    p.add_argument("--fact", required=True, help="PATH:LINE of the fact it is about now, as rag.py pack prints it")
    p.add_argument("--old", help="the key of the gone fact to repoint, when the context has several that are gone")
    p.add_argument("--date", help="YYYY-MM-DD, noted in links (default: today)")
    p = add("sweep", "invalidate the decisions whose context is broken", root_required=False)
    p.add_argument("--dry-run", action="store_true", help="print what would be invalidated and write nothing")
    p.add_argument("--date", help="YYYY-MM-DD, the day taken as today (default: today)")
    p = add("list", "the decisions of one root or of all", root_required=False)
    p.add_argument("--status", choices=DECISIONS.status)
    p.add_argument("--context", help="only the decisions whose context names this kind:value (or bare value)")
    return ap


COMMANDS = {"propose": cmd_propose, "confirm": cmd_confirm, "record": cmd_record, "makers": cmd_makers, "supersede": cmd_supersede, "invalidate": cmd_invalidate,
            "restore": cmd_restore, "ratify": cmd_ratify, "revert": cmd_revert, "digest": cmd_digest, "relink": cmd_relink, "sweep": cmd_sweep, "list": cmd_list}


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        return COMMANDS[a.cmd](a)
    except Refused as e:
        print(f"refused: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
