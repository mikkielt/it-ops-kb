#!/usr/bin/env python3
"""The kb's own backlog: epics, stories, tasks, subtasks, bugs and sprints, one JSON file per item in
kb/_self/backlog/ (kb/_self/backlog.md is the runbook). Standard library only; no model, and no network except `red-pipeline` and `intake --network`.

  backlog.py new KIND --title T [--parent ID] [--sprint ID] [--priority P1|P2|P3] [--rank N] [--goal TEXT]
                 [--severity S1..S4] [--check CMD]... [--touch GLOB]... [--depends ID]... [--repro CMD]
                 [--repro-reason TEXT]
                                          a new item (KIND: epic, story, task, subtask, bug, sprint); prints its id
                                          and title. A bug's --repro must fail now, and for the defect: one that
                                          cannot start, dies of a SyntaxError in its own code, gets a usage error
                                          (argparse exit 2) or runs no tests (pytest exit 5) is refused with the
                                          cause; one that only matches text in a file (grep, a python -c that
                                          reads a file) is refused (exit 2, nothing written) without
                                          --repro-reason, kept as repro_reason; a warning names a check or repro that runs no test or tool code,
                                          a repro whose output says it did nothing here, and a bug whose repro
                                          runs a tool with no check that runs tests; a sprint gets its start gate and its review story. A new item that
                                          is a near-duplicate of an open one (similar, below) gets a warning naming
                                          it; the item is still written and the exit code is unchanged
  backlog.py similar TITLE [--goal G]     open items ranked by word overlap of TITLE (and G) with their title and
                                          goal: the share of the query's words found (stop words left out), the
                                          shared count, `near` from 0.60 and 2 words; the first 10; exit 0
  backlog.py check                        validate every item (fields, links, cycles, canonical form, a planned
                                          sprint's items still draft but a claimed research item, and the kb
                                          references of its `knowledge`: a missing one is an error, a fact key no
                                          longer found is reported as stale knowledge; no item may hold a piece of
                                          this host's computer or user name, read from the environment and never
                                          printed); warns of an open bug whose repro only matches text in a
                                          file (a grep of _tools/ source among them) with no repro_reason; exit 1
                                          on errors
  backlog.py fmt                          rewrite every item in canonical form
  backlog.py selectors                    one line per `tests.py -k` selector in the checks of open items: how many
                                          tests pytest --collect-only finds for it now (NONE marks zero, error a
                                          collection that failed), the item's id and title; exit 0 whatever the
                                          counts (a selector often names a test its item has yet to write), 1
                                          without pytest
  backlog.py list [--kind K] [--status S] [--sprint ID]   one line per item: id, kind, status, priority, title
  backlog.py tree [ID] [--sprint ID] [--open]  the hierarchy under an item, a sprint or everything (--open: no done or
                                          dropped item)
  backlog.py find WORD...                 the open items whose title or goal holds every word (case-insensitive), each
                                          with its parent chain; no match prints one line and exits 1
  backlog.py show ID                      one item, its parent chain, children, the knowledge state of each ask and
                                          ref of its `knowledge` and what it waits on
  backlog.py next [--sprint ID] [--any] [--all]   the ready item to work on first (--all: every ready item in
                                          order; --any: items outside an active sprint too, for single-item work),
                                          with the knowledge state of each of its asks and refs
  backlog.py held [--overlaps ID] [--ref REF]   the paths other sessions hold: one line per touches glob of each
                                          claimed (doing) item, with the item, its claimer and its sprint; --ref
                                          reads the item files as REF has them (origin/main after git fetch, where
                                          every claim sync lands; exit 2 for a ref git cannot read). --overlaps ID:
                                          only the claimed items outside ID's chain whose touches overlap ID's own or
                                          its descendants' (a glob read as a path matches the other, or a tracked file
                                          matches both), each naming the glob it meets; exit 1 when there is one
  backlog.py claim ID --by NAME          status doing, claimed by NAME;  backlog.py release ID  back to todo
                                          (a research item of a planned sprint, one whose touches are all inside kb
                                          roots: claimed from draft, released to draft; check accepts it doing or
                                          done, and done proves it before the sprint starts)
  backlog.py answer ID GATE (--answer TEXT --by operator|agent [--record] | --provisional | --confirm)
                                          record a gate's answer: --provisional takes the recommendation as the
                                          agent's answer (provisional gates only); --confirm makes an agent's answer
                                          the operator's; --record (with --by operator) also writes it as an active
                                          decision of kb/_self through kbdecide.py, its context the item (exit 2 with
                                          --provisional, --confirm or a --by other than operator)
  backlog.py set ID [--notes TEXT] [--link T]... [--touch GLOB]... [--check CMD]... [--depends ID]...
                 [--relates ID]... [--priority P1|P2|P3] [--rank N] [--sprint ID] [--add] [--clear FIELD]...
                                          change an item after new: each list option replaces its list (--add:
                                          appends what is missing, so a second run changes nothing; for --notes,
                                          appends the text unless the notes hold it), --clear FIELD removes one.
                                          The result is validated as check does and written only when it adds no
                                          error; status, claimed_by, evidence, id, kind, parent, title and the
                                          fields set does not name are refused, a sprint takes notes and links
                                          only, and a done item keeps its checks and touches (its evidence proves
                                          them); exit 2 for each refusal, the item file unchanged
  backlog.py move ID --sprint SP|none     set a story's or bug's sprint (none: no sprint) and write the status that
                                          sprint's state gives: todo in an active sprint, draft in a planned one or
                                          in none; its draft and todo tasks and subtasks follow. Refused (exit 2, the
                                          file unchanged): a task, subtask or review story, a doing, done or dropped
                                          item or one with a doing task, a missing sprint, an item without touches
                                          into an active sprint; a second run changes nothing
  backlog.py reopen ID --why TEXT         a done item back to work: evidence and claimed_by cleared, status todo (draft
                                          while its sprint is planned); any other status is refused (exit 2). The
                                          reason is printed, never written to the item
  backlog.py gate add ID --question Q --option O... --recommendation R [--kind blocking|provisional] [--id GATE]
                                          add a gate (kind blocking unless given; two or more options, the
                                          recommendation one of them; a gate about a capped file (AGENTS.md,
                                          README.md) needs each option to state the file's measured size, as
                                          'N bytes'; the id defaults to g1, g2, ...), validated as
                                          check does; the same gate again changes nothing, a different gate with an
                                          existing question or id is refused, as is one on a done or dropped item
                                          (exit 2); `answer` answers it
                                          --do OPTION=CMD|ID: the argv that carries the option out, or the id of the
                                          item whose work adds that command (repeatable); check warns of an
                                          unanswered blocking gate with none
                                          --host-check CMD: the command that proves the setup the gate's answer names
                                          holds on this host (exit 0), kept on the gate; `host-check` runs it
  backlog.py host-check SPRINT            run the host check of each answered gate of the sprint's open items, on this
                                          host, before the start gate is asked, and record each result on the gate
                                          (host_checked: ok, exit); exit 1, naming each gate and the command's output
                                          tail, when one fails; `start` refuses a sprint with an answered gate whose
                                          host check has no passing record
  backlog.py fire ID                      mark an item's external trigger as fired
  backlog.py done ID [--dry-run]          run the item's checks at a clean HEAD, check its commits' scope, record the
                                          evidence and set status done; exit 1 with the reasons otherwise, among
                                          them a check or repro that passed doing nothing here (its output a
                                          no-op marker, such as no public remote, or all tests skipped) with no
                                          other passing check that runs tests and no operator accept on gate
                                          host-bound; warns of each such check and of one that runs no code
  backlog.py land ID [--branch B] [--trailer 'KEY: VALUE']...
                                          land a finished item's branch (default work/ID) from a clean tree: fetch
                                          and rebase it on the integration main, then a content item: done --commit,
                                          stress_test.py, rag.py eval and the lint when the landing changes _tools/,
                                          kbgit.py sync --push; an item with a code-lane commit not on that main:
                                          those checks and sync --push (the code/<id> merge request), and a re-run
                                          once it has merged ends as a content item does. A re-run before the merge
                                          says it waits, and when the request is open, mergeable, set to auto-merge
                                          and its pipeline was skipped (GitLab, glab signed in; else nothing more),
                                          names the glab mr merge command that merges it. A finished worker's clean
                                          worktree that Claude Code left locked is removed, unless a process still
                                          runs in it (refused, naming each pid; a host that cannot list them: a note,
                                          and it is removed). Stops at the first failing
                                          step, naming it (exit 1); a failed rebase is aborted
  backlog.py drop ID --why TEXT          status dropped (an item outside any sprint is deleted: git keeps it)
  backlog.py start SPRINT                 activate a sprint whose start gate the operator answered; drafts become todo;
                                          a warning (exit 0) for each open P1 item whose `recurs` names 2 or more
                                          sprint ids and that is not in the sprint
  backlog.py close SPRINT [--summary]     delete a finished sprint, its items and the epics they finished
                                          (--summary: only list each of them with its status and the commit done
                                          recorded, the close commit's body, and change nothing; with --commit
                                          refused)
  backlog.py horizon [--sprint ID] [--hook]   how far each active sprint can go without the operator: reachable
                                          items, what waits on which gate or trigger, the critical path, the
                                          knowledge state of the next item's asks and refs (--hook runs no pack)
  backlog.py goal ID                      a /goal condition for the item: its end state, checks and scope
  backlog.py cost ID [--runs] [--rework] [--format text|json]
                                          the tokens the query log's work sidecars (kb/_querylog/work/) hold for the
                                          item and its descendants (for a sprint, its items too; a sprint's own line
                                          counts for a sprint only), per model: requests, in, cr, out and cw apart,
                                          direct (the item lines' main) and attributed (their routed subagents'
                                          sub). Shared lines, the session total and overhead are not printed yet.
                                          For a sprint, research items' lines (kb content only) are printed
                                          apart, and the overhead lines of the sidecar runs inside the sprint's
                                          window (its start commit to its close commit) as a total of their own,
                                          in no item or sprint figure; unresolved in a shallow clone.
                                          --rework adds the item work's split into work and rework (the counts
                                          from an item's first refused done; json: `rework_split`).
                                          --runs lists each run's line apart; json gives the same numbers. No
                                          sidecar: zeros, exit 0; an unknown id: exit 2. An item whose file is gone
                                          (deleted at sprint close, a closed sprint included) is read from its last
                                          version in git history; an id with none is named on stderr, left out
  backlog.py cost --research [--format text|json]
                                          every item with `research` true or a link naming a query-log gap finding:
                                          its tokens (in + cw + cr + out of its own direct + attributed lines), the
                                          gap findings closed by commits with its KB-Work trailer (a _gaps.md entry
                                          that gains a Resolved or Superseded note), and tokens per closed gap
                                          (integer division; n/a when none closed; unresolved in a shallow clone)
  backlog.py red-pipeline [--status [--job J]|--hook]   the newest pipeline of origin's main in which a job ran
                                          (--job: in which job J succeeded or failed on its own account, never
                                          canceled, manual or skipped; the newest finished one when none did; glab
                                          api, gh on GitHub; a note when neither is signed in), on GitLab read by its
                                          jobs: red when a job someone started failed (its script, a timeout, stuck),
                                          unverified when the job list is unreadable or a job
                                          in ql_deliver.GATE_JOBS (none) did not succeed. When red and no automatic revert covers it, one bug (S1 when
                                          the kb-tests job failed, else S2) unless an item already names that
                                          pipeline; a failure fingerprint (the first failed job and its first failing
                                          test or error line) in the bug's links, and a pipeline failing the same way
                                          joins that open bug's links instead. --status: exit 0 green, 1 red,
                                          unverified (naming any gate jobs) or unreadable; a bug's repro is --status
                                          --job <its first failed job> when its script ran, else --status. --hook:
                                          the async SessionStart form, silent
  backlog.py intake [--file [--hook] | --status FINGERPRINT] [--network]
                                          the candidates of every detector in bl_intake.DETECTORS (deterministic: the
                                          repository's files, no network, no model; --network adds the `ci` detector,
                                          which reads main's newest pipeline as red-pipeline does and files the same
                                          bug: its `pipeline <id>` and `fingerprint` links, its red-pipeline repro),
                                          one block each: detector, kind,
                                          fingerprint (12 hex), title, then goal, repro (a bug's: intake --status
                                          FINGERPRINT) and links (`fingerprint <12 hex>` first, `detector <name>` last).
                                          Writes nothing; a
                                          candidate whose fingerprint an open item's links already carry is marked
                                          skipped. --file writes each new one as a draft item outside any sprint, so a
                                          second run files nothing. --status FP: exit 1 while a detector still reports
                                          that fingerprint (or one cannot run), 0 once none does; the repro of every bug
                                          intake files. Exit 1 also when a detector failed, 2 for a bad fingerprint
                                          or --status with --file. --hook (the async SessionStart form, run as
                                          --file --hook, offline): silent, exit 0 always, runs drift after the other
                                          detectors, stops waiting for them after
                                          INTAKE_HOOK_BUDGET_S and files what the finished ones found, as uncommitted
                                          drafts, never commits or pushes

claim, done, new, start and close take --commit [--trailer 'KEY: VALUE']...: after the command succeeds, commit the
item files it wrote or deleted and nothing else (`git commit --only`: what was staged before stays staged), subject
`chore(backlog): claim|done|file|start|close ID "title"`, and a last paragraph of trailers: KB-Work: <ids> (the item;
a new sprint and its review story), then each --trailer (the session's own, e.g. Co-Authored-By; a KB-* key is
refused). close's commit body is its --summary list.

--root DIR (before the command) runs against another clone. Exit: 0 ok, 1 a refused command or check errors,
2 bad arguments, an unknown id, or a refused `set` or `gate add`.

Knowledge state (show, next, horizon): one line `knowledge <state> ask|ref: <text>` per ask and per ref of an item's
`knowledge`, each run through kbfacts.pack (no network, no model) and reported as one of sufficient (coverage good, no
`check:` line), partial (weak, or good with a `check:` line), unknown (none, or a ref the kb does not hold), stale (a
fact key no longer in its file, or a source with `superseded_by` set that the ref is or cites) or conflicting (an open
`_conflicts.md` entry on its article); stale, then conflicting, override the coverage. Derived on every call, never
stored, and no part of readiness. An item without `knowledge` costs nothing: the pack is not loaded.

Every line that names an item prints its id and its title together, except a title check found holding a piece of
this host's computer or user name, which is withheld.
"""
import argparse, copy, hashlib, json, os, re, shlex, shutil, subprocess, sys, threading
from pathlib import Path

import bl_cli
import bl_intake
from bl_base import (
    APPROVALS, Backlog, CHECK_TIMEOUT_S, COMMITS, FIELDS, GATE_KINDS, ID_RE, IN_SPRINT, KINDS, NEEDS_CHECKS,
    NEEDS_TOUCHES, OPEN, OUTPUT_ROOT, PARENTS, PREFIX_KIND, PRIORITIES, RECURRING_MIN, REL_DIR,
    RESEARCH_KINDS, REVIEW_CHECKS, ROOT, Refused, Rejected, SEVERITIES, SIMILAR_MIN, SIMILAR_SHOWN, SIMILAR_WORDS,
    SPRINT_ID_RE, SPRINT_STATUSES, STARTS, START_GATE, STATUSES, STOP_WORDS, TEXT_MAX, WORKED, canonical,
    commit_written, git, glob_re, host_user_pieces, in_scope, item_file, items_holding_names, need,
    new_id, research_in_planned, research_touches, run, say, scope, trailer_problem, withhold,
    withhold_names,
)


def start_approved(sp):
    """True when the operator answered the sprint's start gate with an approval."""
    g = next((g for g in sp.get("gates", []) if g.get("id") == START_GATE), {})
    return g.get("by") == "operator" and str(g.get("answer", "")).strip().lower() in APPROVALS


# ------------------------------------------------------------------ validation

def _text_ok(v):
    return isinstance(v, str) and v.strip() and len(v) <= TEXT_MAX


def _check_ok(c):
    return (isinstance(c, dict) and isinstance(c.get("run"), list) and c["run"]
            and all(isinstance(x, str) for x in c["run"]) and set(c) <= {"run", "exit", "match"}
            and isinstance(c.get("exit", 0), int) and isinstance(c.get("match", ""), str))


# ------------------------------------------------------------------ knowledge

KNOWLEDGE_KEYS = ("ask", "refs")
ANSWER_REF = re.compile(r"(?:([a-z0-9][a-z0-9-]*):)?(QK-[a-z0-9]+(?:-[a-z0-9]+)*)")  # `QK-<slug>`, `<root>:QK-<slug>`
FACT_KEY = re.compile(r"[0-9a-f]{12}")


class KbAtHead:
    """The kb roots of a clone (kb/<name>/ with a _root.md), read on demand for the references of an item's
    `knowledge`. Source ids, QK answer ids, topics and fact keys are resolved with the kb's own readers (kbid,
    kbfacts), so a fact key is the one _anchors.csv and doc2query use. Files are read from the checkout, which is
    HEAD once the work is committed."""

    def __init__(self, root):
        import kbcommon
        self.roots, self._sources, self._facts = {}, None, {}
        kb = Path(root) / "kb"
        for p in sorted(kb.iterdir()) if kb.is_dir() else []:
            if (p / kbcommon.ROOT_FILE).is_file():
                try:
                    self.roots[kbcommon.load_root(str(p)).name] = p
                except kbcommon.RootError:
                    continue  # check.py reports a malformed root

    @staticmethod
    def text(path):
        try:
            return Path(path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return None

    def split(self, qpath):
        """(root name, path inside the root) of `<root>/<path>`; a path whose first part names no root is public's."""
        head, _, rest = qpath.partition("/")
        return (head, rest) if head in self.roots else ("public", qpath)

    def source_rows(self):
        """{id: row} of every root's _sources.csv."""
        import csv, io, kbcommon
        if self._sources is None:
            self._sources = {}
            for p in self.roots.values():
                text = self.text(p / kbcommon.SOURCES)
                if text:
                    for r in csv.DictReader(io.StringIO(text, newline="")):
                        self._sources.setdefault(r.get("id", ""), r)
        return self._sources

    def source_ids(self):
        """Every root's ids of its _sources.csv."""
        return set(self.source_rows())

    def answer_ids(self, root):
        """The answer ids (`## <id>. ` headings) of a root's _answers.md."""
        import kbcommon, kbid
        p = self.roots.get(root)
        return set(kbid.answer_ids(self.text(p / kbcommon.ANSWERS) or "")) if p else set()

    def is_topic(self, qpath):
        """Whether `<root>/<domain>/<slug>` (public's without the root) is an article of a root."""
        import kbfacts
        root, rel = self.split(qpath)
        p = self.roots.get(root)
        ok = p and rel and ".." not in rel.split("/") and not rel.startswith(("_", "."))
        text = self.text(p / f"{rel}.md") if ok else None
        return text is not None and kbfacts.is_article(text)

    def fact_units(self, qpath):
        """{fact key (kbfacts.fact_key): its unit} for the tagged facts of one article or data file `<root>/<path>`;
        None when there is no such file."""
        import kbfacts
        if qpath not in self._facts:
            root, rel = self.split(qpath)
            p = self.roots.get(root)
            ok = p and rel.endswith((".md", ".csv")) and ".." not in rel.split("/")
            text = self.text(p / rel) if ok else None
            if text is None:
                units = None
            elif rel.endswith(".md"):
                units = kbfacts.md_units(rel, text) if kbfacts.is_article(text) else []
            else:
                units = kbfacts.csv_units(rel, text)
            self._facts[qpath] = None if units is None else {kbfacts.fact_key(u["text"]): u for u in units
                                                             if u["tags"]}
        return self._facts[qpath]

    def fact_keys(self, qpath):
        """The fact keys (kbfacts.fact_key) of the tagged facts of one article or data file `<root>/<path>`; None
        when there is no such file."""
        units = self.fact_units(qpath)
        return None if units is None else set(units)

    def answer_question(self, root, aid):
        """The question in the heading `## <aid>. <question>` of a root's _answers.md, or None."""
        import kbcommon
        p = self.roots.get(root)
        m = re.search(rf"(?m)^## {re.escape(aid)}\.\s+(.+?)\s*$", (self.text(p / kbcommon.ANSWERS) or "") if p else "")
        return m.group(1) if m else None


def knowledge_check(bl, iid):
    """([errors], [stale]) for the `knowledge` {ask: [questions], refs: [references]} of one item. A reference is a
    topic id (`intune/win32-apps`, `<root>/<domain>/<slug>` outside public), a QK answer id (`QK-<slug>`,
    `<root>:QK-<slug>`), a source id (`S2150`, `S-o3v6ozch`) or `<root>/<path>#<fact key>` (12 hex). One absent
    from the kb is an error. A fact key no longer found in a file that exists (the fact was reworded or removed) is
    stale: a finding `check` prints and does not count as an error, since a refresh of the kb rewords facts."""
    know = bl.items[iid].get("knowledge")
    if know is None:
        return [], []
    errs, stale = [], []
    e = lambda msg: errs.append(f"{bl.label(iid)}: knowledge {msg}")  # noqa: E731
    if not isinstance(know, dict) or set(know) - set(KNOWLEDGE_KEYS):
        e("must be {ask: [questions], refs: [references]}")
        return errs, stale
    for f in KNOWLEDGE_KEYS:
        if f in know and not (isinstance(know[f], list) and all(_text_ok(x) for x in know[f])):
            e(f"{f} must be a list of non-empty texts")
    if errs:
        return errs, stale
    import kbid
    if not hasattr(bl, "kb"):
        bl.kb = KbAtHead(bl.root)
    kb = bl.kb
    for ref in (r.strip() for r in know.get("refs", [])):
        answer = ANSWER_REF.fullmatch(ref)
        if "#" in ref:
            path, _, key = ref.rpartition("#")
            if not FACT_KEY.fullmatch(key):
                e(f"ref {ref!r}: not <root>/<path>#<fact key> (12 lowercase hex characters)")
            elif kb.fact_keys(path) is None:
                e(f"ref {ref!r}: no article or data file {path!r} in the kb")
            elif key not in kb.fact_keys(path):
                stale.append(f"{bl.label(iid)}: stale knowledge: fact {key} is no longer in {path} "
                             f"(reworded or removed)")
        elif answer:
            root = answer.group(1) or "public"
            if root not in kb.roots:
                e(f"ref {ref!r}: no kb root {root!r}")
            elif answer.group(2) not in kb.answer_ids(root):
                e(f"ref {ref!r}: no such answer in root {root!r}")
        elif kbid.id_prefix(ref):
            if ref not in kb.source_ids():
                e(f"ref {ref!r}: no such source id in any root's _sources.csv")
        elif "/" in ref:
            if not kb.is_topic(ref):
                e(f"ref {ref!r}: no such topic (an article of a kb root)")
        else:
            e(f"ref {ref!r}: not a topic id, QK answer id, source id or <root>/<path>#<fact key>")
    return errs, stale


def stale_knowledge(bl):
    """The stale-knowledge findings of every item (knowledge_check)."""
    return [x for iid in bl.items for x in knowledge_check(bl, iid)[1]]


# ------------------------------------------------------------------ code and its docs

CODE_DIRS = ("_tools/", ".claude/", ".claude-plugin/")  # with CODE_FILES: the paths whose change needs /kb-self
CODE_FILES = (".gitlab-ci.yml",)
EVERY_TOOL = "_tools/*.py"  # a map pattern that matches this glob, read as a path, covers every tool: a standard doc
OPEN_STATUSES = ("draft", "todo", "doing")


def is_code(path):
    return path in CODE_FILES or path.startswith(CODE_DIRS)


def tracked_files(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    return r.stdout.splitlines() if r.returncode == 0 else []


def dependents(bl, iid):
    """The items that depend on iid, directly or through another item (later work)."""
    out, todo = set(), [iid]
    while todo:
        cur = todo.pop()
        for i, it in bl.items.items():
            if cur in it.get("depends_on", []) and i not in out and i != iid:
                out.add(i)
                todo.append(i)
    return out


def stale_touches(bl):
    """An error for each open item whose touches names a path without glob characters that the working tree lacks and
    that has a commit in git log: a file a move or a deletion stranded, so the item's scope (and `done`'s
    outside-touches refusal) names nothing. A path no commit ever had is a file the item is yet to create: no error."""
    history = {}
    out = []
    for iid, it in bl.items.items():
        if it.get("kind") == "sprint" or it.get("status") not in OPEN_STATUSES:
            continue
        for t in it.get("touches", []) or []:
            if not isinstance(t, str) or not t or re.search(r"[*?\[]", t) or (bl.root / t).exists():
                continue
            if t not in history:
                try:
                    r = subprocess.run(["git", "-C", str(bl.root), "log", "-1", "--format=%H", "HEAD", "--", t],
                                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                    history[t] = r.returncode == 0 and bool(r.stdout.strip())
                except (OSError, subprocess.SubprocessError):
                    history[t] = False
            if history[t]:
                out.append(f"{bl.label(iid)}: touches names {t}, which git history has and the working tree lacks "
                           f"(moved or deleted: name its new path, or drop it from touches)")
    return out


def selector_of(argv):
    """(display text, targets, -k expression, -m expression) for a check argv that runs tests.py with -k (other
    pass-through flags are ignored), else None. The default -m is tests.py's own, `not stress`; a `--changed` run
    selects by the change, not by name, so it is no selector."""
    if not isinstance(argv, list) or "--changed" in argv:
        return None
    at = next((n for n, x in enumerate(argv) if isinstance(x, str) and re.split(r"[\\/]", x)[-1] == "tests.py"), None)
    if at is None:
        return None
    k = m = None
    targets = []
    rest = [x for x in argv[at + 1:] if isinstance(x, str)]
    n = 0
    while n < len(rest):
        if rest[n] in ("-k", "-m") and n + 1 < len(rest):
            if rest[n] == "-k":
                k = rest[n + 1]
            else:
                m = rest[n + 1]
            n += 2
            continue
        if not rest[n].startswith("-"):
            targets.append(rest[n])
        n += 1
    if k is None:
        return None
    return shlex.join(targets + ["-k", k] + (["-m", m] if m else [])), targets, k, m or "not stress"


def collected(root, cmd, targets, k, m):
    """How many tests pytest --collect-only selects under -m M -k K in TARGETS (default _tools), run from root: (count,
    None), or (None, why) when the collection itself failed. Exit 5 (everything deselected) is a count of 0."""
    argv = cmd + ["--collect-only", "-q", "--color=no", "-p", "no:cacheprovider", "-m", m, "-k", k] + (targets or ["_tools"])
    try:
        r = subprocess.run(argv, cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        return None, type(e).__name__
    if r.returncode not in (0, 5):
        return None, f"pytest exit {r.returncode}"
    return sum(1 for ln in r.stdout.splitlines() if re.match(r"[^\s:]+\.py::", ln)), None


def selector_rows(bl, cmd):
    """[(count or None, why, selector text, item id)] for every tests.py -k selector in the checks of the open items,
    each distinct selector collected once, fewest tests first (collection errors, then zeros)."""
    seen, rows = {}, []
    for iid, it in bl.items.items():
        if it.get("kind") == "sprint" or it.get("status") not in OPEN_STATUSES:
            continue
        for c in it.get("checks", []) or []:
            sel = selector_of(c.get("run") if isinstance(c, dict) else None)
            if sel is None:
                continue
            text, targets, k, m = sel
            if text not in seen:
                seen[text] = collected(bl.root, cmd, targets, k, m)
            rows.append((*seen[text], text, iid))
    return sorted(rows, key=lambda r: (-1 if r[0] is None else r[0], r[2], r[3]))


def touch_paths(item, files, literal):
    """The paths an item's touches name: each path as written, each glob expanded over FILES (tracked paths) and
    LITERAL (the paths a doc map names, which may not exist yet)."""
    paths = set()
    for t in item.get("touches", []) or []:
        if not isinstance(t, str) or not t:
            continue
        if not re.search(r"[*?]", t):
            paths.add(t)
            continue
        rx = glob_re(t)
        paths |= {p for p in list(files) + literal if rx.match(p)}
    return paths


def dependencies(bl, iid):
    """The items iid depends on, directly or through another item (earlier work)."""
    out, todo = set(), [iid]
    while todo:
        for d in bl.items.get(todo.pop(), {}).get("depends_on", []) or []:
            if d in bl.items and d not in out and d != iid:
                out.add(d)
                todo.append(d)
    return out


def docs_after_code(bl, ids):
    """One refusal for each open task or bug among IDS whose touches are only kb/_self docs that kb/_self/map.csv maps
    to the code another item touches, which it depends on: the sync gate's `selfdoc stale` reads the code and its docs
    in one range, and a task that waits for the code lands them apart. A standard doc (a map pattern that covers every
    _tools/*.py) describes no one change and is left out; a missing or unreadable map gives none."""
    import selfdoc
    try:
        docmap = selfdoc.load_map(str(bl.root))
    except selfdoc.SelfdocError:
        return []
    docmap = {d: pats for d, pats in docmap.items() if not any(selfdoc.matches(p, EVERY_TOOL) for p in pats)}
    literal = [p for pats in docmap.values() for p in pats if not re.search(r"[*?]", p)]
    files, out = None, []
    for iid in sorted(ids):
        it = bl.items[iid]
        touches = it.get("touches", []) or []
        if it.get("status") not in OPEN_STATUSES or it.get("kind") == "sprint" or not touches or \
                not all(isinstance(t, str) and t.startswith("kb/_self/") for t in touches):
            continue
        if files is None:
            files = tracked_files(bl.root)
        docs = touch_paths(it, files, literal)
        for dep in sorted(dependencies(bl, iid)):
            if bl.items[dep].get("status") not in OPEN_STATUSES:
                continue
            code = sorted(p for p in touch_paths(bl.items[dep], files, literal) if is_code(p))
            held = sorted(d for d in selfdoc.describing(docmap, code) if d in docs)
            if held:
                out.append(f"{bl.label(iid)}: touches only docs of code that {bl.label(dep)}, which it depends on, "
                           f"touches: {', '.join(held)} (put them in {bl.label(dep)}'s touches: the sync gate's "
                           "selfdoc stale needs code and its docs in one range)")
    return out


def docs_warnings(bl, only=None):
    """An open item whose own touches name code (CODE_DIRS, CODE_FILES) whose kb/_self/map.csv docs are in no open
    item's touches, or only in the touches of items that depend on it (a later task): kb/_self/git.md asks for a code
    change's doc lines in the same commit, and sync's selfdoc stale gate refuses the push without them. The item's own
    scope (its touches and its descendants') covers a doc; a missing or unreadable map gives no warning. A standard
    doc, one with a map pattern that covers every _tools/*.py (EVERY_TOOL), describes no one change: selfdoc stale
    still lists it, and a Self-Reviewed trailer clears it there, so it is no item's to carry. ONLY limits the items
    reported to those ids; the holders of a doc are still every open item."""
    import selfdoc
    try:
        docmap = selfdoc.load_map(str(bl.root))
    except selfdoc.SelfdocError:
        return []
    docmap = {d: pats for d, pats in docmap.items() if not any(selfdoc.matches(p, EVERY_TOOL) for p in pats)}
    files = None
    literal = [p for pats in docmap.values() for p in pats if not re.search(r"[*?]", p)]
    open_ids = [i for i, it in bl.items.items() if it.get("kind") != "sprint" and it.get("status") in OPEN_STATUSES]
    out = []
    for iid in open_ids:
        if only is not None and iid not in only:
            continue
        if files is None and any(re.search(r"[*?]", t) for t in bl.items[iid].get("touches", []) or []
                                 if isinstance(t, str)):
            files = tracked_files(bl.root)
        paths = touch_paths(bl.items[iid], files or [], literal)
        code = sorted(p for p in paths if is_code(p))
        if not code:
            continue
        own = scope(bl, iid)
        later = dependents(bl, iid)
        missing, deferred = [], {}
        for doc in sorted(selfdoc.describing(docmap, code)):
            if in_scope(doc, own):
                continue
            holders = [i for i in open_ids if i != iid and in_scope(doc, bl.items[i].get("touches", []) or [])]
            if not holders:
                missing.append(doc)
            elif all(h in later for h in holders):
                for h in holders:
                    deferred.setdefault(h, []).append(doc)
        if missing:
            out.append(f"{bl.label(iid)}: touches code whose kb/_self/map.csv docs are in no item's touches: "
                       f"{', '.join(missing)} (add them to this item's touches: kb/_self/git.md, code and its docs "
                       f"land in one commit)")
        for h, docs in sorted(deferred.items()):
            out.append(f"{bl.label(iid)}: the docs of its code are only in a later task's touches, "
                       f"{bl.label(h)} (it depends on this one): {', '.join(docs)} (move them to this item's touches)")
    return out


# ------------------------------------------------------------------ knowledge state

STATES = ("sufficient", "partial", "unknown", "stale", "conflicting")
SETTLED_NOTE = re.compile(r"(?:^|\s)- (?:(?:Resolved|Superseded) \d{4}-\d{2}-\d{2}\b"
                          r"|Reviewed \d{4}-\d{2}-\d{2}, not a source disagreement\b)")  # the notes that close an entry


class KnowledgeState:
    """The state of each ask and each ref of an item's `knowledge`, derived from the kb on every call and never
    stored: the pack (kbfacts.pack: no network, no model) of the ask, or of the text a ref stands for (a topic's
    title, a QK answer's question, a source's title, a fact's own text), then, in this order:
      unknown      the ref is not in the kb, or the pack's coverage is `none` (or the pack could not run);
      stale        a fact key no longer found in its file, or a source that the ref is, that the fact cites or that
                   the pack cites has `superseded_by` set in _sources.csv;
      conflicting  the ref's article (a source ref: any entry naming it), or the pack's lead article, has an open
                   entry in _conflicts.md: an entry with no `- Resolved <date>`, `- Superseded <date>` or
                   `- Reviewed <date>, not a source disagreement` note (`Reviewed <date>, still open` keeps it open);
      partial      coverage `weak`, or `good` with a `check:` line (a possible false good);
      sufficient   coverage `good` with no `check:` line.
    A pack whose coverage is `none` shows no article or source, so only what the ref itself is (its own fact, source
    or article) can make it stale or conflicting. The pack is the one `rag.py pack "<text>"` prints, in this process."""

    def __init__(self, bl):
        import kbcommon, kbfacts
        if not hasattr(bl, "kb"):
            bl.kb = KbAtHead(bl.root)
        self.kb, self.kf, self.kc, self._packs, self._open = bl.kb, kbfacts, kbcommon, {}, None

    def pack(self, question):
        if question not in self._packs:
            self._packs[question] = self.kf.pack(question)
        return self._packs[question]

    def open_conflicts(self):
        """([(entry, linked topics)]) of the entries of every root's _conflicts.md that no Resolved, Superseded or
        "Reviewed <date>, not a source disagreement" note closes."""
        if self._open is None:
            kf = self.kf
            entries = kf.link_entries(kf.ledger_entries(self.kc.CONFLICTS))
            self._open = [e for e in entries if not SETTLED_NOTE.search(e["text"])]
        return self._open

    def topic_of(self, qpath):
        """The qualified topic of an article or of a data file that an article lists, or None."""
        kf = self.kf
        meta = kf.articles().get(qpath)
        if meta:
            return meta["topic"]
        return next((t for t, files in kf.topic_files().items() if qpath in files), None)

    def conflict_of(self, qpaths, source_id=None):
        """The `file:line` of an open conflict entry that names one of the articles' topics (or the source id)."""
        topics = {t for t in map(self.topic_of, qpaths) if t}
        if not topics and not source_id:
            return None
        for e in self.open_conflicts():
            if topics & set(e["explicit"]) or (source_id and source_id in e["ids"]):
                return f"{e['file']}:{e['line']}"
        return None

    def superseded(self, ids):
        rows = self.kb.source_rows()
        return [(i, (rows[i].get("superseded_by") or "").strip()) for i in dict.fromkeys(ids)
                if i in rows and (rows[i].get("superseded_by") or "").strip()]

    def judge(self, question, articles=(), ids=(), source=None):
        """(state, why) for a question; `articles` the qualified paths and `ids` the source ids the ref itself is or
        cites; `source` the source id a source ref is."""
        try:
            res = self.pack(question)
        except Exception as ex:  # a kb the pack cannot read: no evidence, so no better than unknown
            return "unknown", f"the pack could not run: {type(ex).__name__}: {ex}"
        covered = res["verdict"] != "none"
        old = self.superseded(list(ids) + (res["sources"] if covered else []))
        if old:
            return "stale", "; ".join(f"source {i} is superseded by {new}" for i, new in old)
        clash = self.conflict_of(list(articles) + (res["paths"][:1] if covered else []), source)
        if clash:
            return "conflicting", f"open entry at {clash}"
        if not covered:
            return "unknown", "the kb does not cover it: coverage none"
        if res["verdict"] == "weak":
            return "partial", "coverage weak"
        if res["unmatched"] or res["spread"]:
            return "partial", "coverage good, but the pack's check: line flags a possible false good"
        return "sufficient", ""

    def of_ask(self, question):
        return self.judge(question)

    def of_ref(self, ref):
        """(state, why) for one reference, resolved as knowledge_check resolves it."""
        kb, ref = self.kb, ref.strip()
        answer = ANSWER_REF.fullmatch(ref)
        if "#" in ref:
            path, _, key = ref.rpartition("#")
            units = kb.fact_units(path) if FACT_KEY.fullmatch(key) else None
            if units is None:
                return "unknown", "no such article or data file, or not a fact key"
            if key not in units:
                return "stale", f"fact {key} is no longer in {path}, reworded or removed"
            u = units[key]
            root, rel = kb.split(path)
            text = self.kf.TAG.sub("", u["text"]).strip(" |")
            return self.judge(text, [f"{root}/{rel}"], [i for t in u["tags"] for i in t["ids"]])
        if answer:
            root = answer.group(1) or "public"
            question = kb.answer_question(root, answer.group(2)) if root in kb.roots else None
            return self.judge(question, ()) if question else ("unknown", "no such answer")
        import kbid
        if kbid.id_prefix(ref):
            row = kb.source_rows().get(ref)
            return self.judge(row.get("title") or row.get("url") or ref, (), [ref], ref) if row else (
                "unknown", "no such source id")
        if "/" in ref and kb.is_topic(ref):
            root, rel = kb.split(ref)
            title = self.kf.front_matter(kb.text(kb.roots[root] / f"{rel}.md") or "")["title"]
            return self.judge(title or rel, [f"{root}/{rel}.md"])
        return "unknown", "no such topic"


def knowledge_lines(bl, iid, indent="  "):
    """One line per ask and per ref of an item's `knowledge`: `knowledge <state> ask|ref: <text>` and, for any state
    but sufficient, why. [] for an item with no asks or refs, without loading the pack (a malformed field is
    `check`'s to report)."""
    know = bl.items[iid].get("knowledge")
    if not isinstance(know, dict):
        return []
    todo = [(k, x) for k, f in (("ask", "ask"), ("ref", "refs")) for x in (know.get(f) if isinstance(know.get(f), list) else [])
            if isinstance(x, str) and x.strip()]
    if not todo:
        return []
    if not hasattr(bl, "state"):
        bl.state = KnowledgeState(bl)
    out = []
    for kind, text in todo:
        state, why = bl.state.of_ask(text) if kind == "ask" else bl.state.of_ref(text)
        out.append(f"{indent}knowledge {state:<11} {kind}: {text.strip()}" + (f" ({why})" if why else ""))
    return out


def validate(bl, pieces=None):
    errs = list(bl.load_errors)
    named = items_holding_names(bl, pieces)
    bl.withheld |= set(named)
    for iid, hits in named.items():
        for path, kind in hits:
            errs.append(f"{bl.label(iid)}: field {path} holds a piece of this host's "
                        f"{'computer' if kind == 'host' else 'user'} name (read from the environment, not printed); "
                        f"write a placeholder instead")
    for iid, it in bl.items.items():
        e = lambda msg, iid=iid: errs.append(f"{bl.label(iid)}: {msg}")  # noqa: E731
        if it.get("id") != iid:
            e(f"id {it.get('id')!r} does not match its file name")
        if not ID_RE.fullmatch(iid):
            e("id is not <EP|ST|TK|SB|BG|SP>-<8 base32 characters>")
        kind = it.get("kind")
        if kind not in KINDS:
            e(f"kind {kind!r} is not one of {', '.join(KINDS)}")
            continue
        if ID_RE.fullmatch(iid) and PREFIX_KIND[iid[:2]] != kind:
            e(f"id prefix {iid[:2]} does not match kind {kind}")
        unknown = set(it) - FIELDS
        if unknown:
            e(f"unknown fields {sorted(unknown)}")
        if not _text_ok(it.get("title")):
            e("title missing or longer than TEXT_MAX")
        for f in ("goal", "notes"):
            if f in it and not _text_ok(it[f]):
                e(f"{f} empty or longer than TEXT_MAX")
        if "links" in it and not (isinstance(it["links"], list) and all(_text_ok(x) for x in it["links"])):
            e("links must be a list of texts (each non-empty, at most TEXT_MAX)")
        if bl.raw.get(iid) != canonical(it):
            e("not in canonical form (python3 _tools/backlog.py fmt)")
        if kind == "sprint":
            if it.get("status") not in SPRINT_STATUSES:
                e(f"sprint status must be one of {SPRINT_STATUSES}")
            if not _text_ok(it.get("goal")):
                e("a sprint needs a goal")
            if not any(g.get("id") == START_GATE for g in it.get("gates", []) if isinstance(g, dict)):
                e("a sprint needs its start gate")
            reviews = [i for i in bl.sprint_items(iid) if bl.items[i].get("review")]
            if len(reviews) != 1:
                e(f"a sprint needs exactly one review story (has {len(reviews)})")
        else:
            if it.get("status") not in STATUSES:
                e(f"status must be one of {STATUSES}")
            if it.get("priority") not in PRIORITIES:
                e(f"priority must be one of {PRIORITIES}")
            if not isinstance(it.get("rank", 0), int):
                e("rank must be an integer")
            if kind != "subtask" and kind != "epic" and not _text_ok(it.get("goal")):
                e("goal (the end state) missing")
        par = it.get("parent")
        if par:
            if par not in bl.items:
                e(f"parent {par} does not exist")
            elif bl.items[par].get("kind") not in PARENTS[kind]:
                e(f"a {kind} cannot sit under a {bl.items[par].get('kind')}")
        elif kind in ("task", "subtask"):
            e(f"a {kind} needs a parent ({' or '.join(PARENTS[kind])})")
        if "sprint" in it:
            s = it["sprint"]
            if kind not in IN_SPRINT:
                e("only stories and bugs name a sprint; tasks and subtasks follow theirs")
            elif s not in bl.items or bl.items[s].get("kind") != "sprint":
                e(f"sprint {s} does not exist")
        if it.get("review") and (kind != "story" or not it.get("sprint")):
            e("a review item is a story in a sprint")
        if kind == "bug":
            if it.get("severity") not in SEVERITIES:
                e(f"a bug needs a severity {SEVERITIES}")
            if not _check_ok(it.get("repro")):
                e("a bug needs a repro check (a command that fails until it is fixed)")
            if "repro_reason" in it and not _text_ok(it["repro_reason"]):
                e("repro_reason must be text: why the repro can only match text in a file")
        elif "severity" in it or "repro" in it or "repro_reason" in it:
            e("severity and repro are for bugs only")
        checks = it.get("checks", [])
        if not isinstance(checks, list) or not all(_check_ok(c) for c in checks):
            e("checks must be a list of {run: [argv...], exit?: int, match?: regex}")
        elif kind in NEEDS_CHECKS and not checks and not (kind == "bug" and it.get("repro")):
            e("checks missing: the commands that prove the end state")
        for c in checks if isinstance(checks, list) else []:
            if isinstance(c, dict) and c.get("match"):
                try:
                    re.compile(c["match"])
                except re.error as x:
                    e(f"check match is not a regex: {x}")
        touches = it.get("touches", [])
        if not isinstance(touches, list) or not all(isinstance(t, str) and t for t in touches):
            e("touches must be a list of path globs")
        elif kind in NEEDS_TOUCHES and not touches:
            e("touches missing: the path globs this item may change")
        for f in ("depends_on", "relates_to"):
            for d in it.get(f, []):
                if d not in bl.items:
                    e(f"{f} names {d}, which does not exist")
                elif d == iid:
                    e(f"{f} names the item itself")
                elif f == "depends_on" and bl.items[d].get("status") == "dropped":
                    e(f"depends on dropped {bl.label(d)}")
        gate_ids = set()
        for g in it.get("gates", []):
            if not isinstance(g, dict) or not _text_ok(g.get("question", "")) or g.get("kind") not in GATE_KINDS:
                e("a gate needs id, kind (blocking|provisional) and question")
                continue
            if g.get("id") in gate_ids or not g.get("id"):
                e(f"gate id {g.get('id')!r} missing or repeated")
            gate_ids.add(g.get("id"))
            if g["kind"] == "provisional" and not g.get("recommendation"):
                e(f"provisional gate {g['id']} needs a recommendation")
            if "answer" in g and g.get("by") not in ("operator", "agent"):
                e(f"gate {g['id']}: an answer needs by: operator|agent")
            if g["kind"] == "blocking" and g.get("by") == "agent":
                e(f"gate {g['id']} is blocking: only the operator answers it")
            hc = g.get("host_check")
            if "host_check" in g and not (isinstance(hc, dict) and isinstance(hc.get("run"), list) and hc["run"]
                                          and all(isinstance(w, str) and w for w in hc["run"])):
                e(f"gate {g['id']}: host_check needs run: a command as a list of words")
            for opt, how in (g.get("do") or {}).items() if isinstance(g.get("do", {}), dict) else ():
                if opt not in g.get("options", []):
                    e(f"gate {g['id']}: do names {opt!r}, which is not one of its options")
                elif not (isinstance(how, list) and how and all(isinstance(w, str) and w for w in how)
                          or isinstance(how, str) and how in bl.items):
                    e(f"gate {g['id']}: do for {opt!r} needs an argv (a list of words) or the id of an item")
            if "do" in g and not isinstance(g["do"], dict):
                e(f"gate {g['id']}: do maps an option to its command")
            if "host_checked" in g and not (isinstance(g["host_checked"], dict)
                                            and isinstance(g["host_checked"].get("ok"), bool)):
                e(f"gate {g['id']}: host_checked needs ok: true or false")
        if "recurs" in it:
            rc = it["recurs"]
            if not isinstance(rc, list) or not all(isinstance(r, str) and SPRINT_ID_RE.fullmatch(r) for r in rc):
                e("recurs must be a list of sprint ids (SP-...): the sprints the work came back in")
            elif len(set(rc)) != len(rc):
                e("recurs names a sprint twice")
        trig = it.get("trigger")
        if trig is not None and not (isinstance(trig, dict) and _text_ok(trig.get("when", ""))
                                     and isinstance(trig.get("fired", False), bool)):
            e("trigger must be {when: text, fired: bool}")
        errs.extend(knowledge_check(bl, iid)[0])
        st = it.get("status")
        if st == "doing" and not it.get("claimed_by"):
            e("status doing needs claimed_by")
        sp = bl.sprint_of(iid) if kind != "sprint" else None
        if st in WORKED and sp in bl.items and bl.items[sp].get("status") == "planned" \
                and not (st in ("doing", "done") and research_in_planned(bl, iid)):
            e(f"status {st} while its sprint {bl.label(sp)} is planned: not in a started sprint "
              f"(a planned sprint's items stay draft until backlog.py start)")
        if st == "done" and kind in NEEDS_CHECKS + ("bug",) and not it.get("evidence"):
            e("status done without evidence (set only by backlog.py done)")
    # cycles over depends_on and parent
    state = {}

    def visit(i, path):
        state[i] = 1
        for d in bl.items[i].get("depends_on", []) + ([bl.items[i]["parent"]] if bl.items[i].get("parent") else []):
            if d not in bl.items:
                continue
            if state.get(d) == 1:
                errs.append(f"cycle: {' -> '.join(bl.label(x) for x in path + [d])}")
            elif not state.get(d):
                visit(d, path + [d])
        state[i] = 2

    for i in bl.items:
        if not state.get(i):
            visit(i, [i])
    return errs


# ------------------------------------------------------------------ readiness

def open_gates(it, kinds=("blocking",)):
    return [g for g in it.get("gates", []) if g.get("kind") in kinds and "answer" not in g]


def waits(bl, iid, any_sprint=False, by=None):
    """Why an item cannot be worked on now ([] = ready): its status, sprint, dependencies, gates, trigger, children.
    With `by`, a dependency that is `doing` and claimed by that session does not wait (`claim --by`: one session works
    both items in order)."""
    it = bl.items[iid]
    out = []
    if it.get("kind") in ("sprint", "epic"):
        return ["not a work item"]
    if it.get("status") not in ("todo", "doing"):
        out.append(f"status {it.get('status')}")
    sp = bl.sprint_of(iid)
    if not any_sprint and (not sp or bl.items.get(sp, {}).get("status") != "active"):
        out.append("not in an active sprint")
    for i in [iid] + bl.ancestors(iid):  # an ancestor's gates, trigger and dependencies hold its descendants too
        a = bl.items[i]
        for g in open_gates(a):
            out.append(f"gate {i}/{g['id']}: {g['question']}")
        t = a.get("trigger")
        if t and not t.get("fired"):
            out.append(f"trigger on {bl.label(i)}: {t['when']}")
        for d in a.get("depends_on", []):
            dep = bl.items.get(d, {})
            if dep.get("status") == "doing" and by is not None and dep.get("claimed_by") == by:
                continue
            if dep.get("status") != "done":
                out.append(f"depends on {bl.label(d)}" + (f" (through {bl.label(i)})" if i != iid else ""))
    if it.get("review"):
        for s in bl.sprint_items(sp):
            if s != iid and bl.items[s].get("kind") in IN_SPRINT and bl.items[s].get("status") not in ("done", "dropped"):
                out.append(f"review waits on {bl.label(s)}")
    open_children = [c for c in bl.children(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if open_children:
        out.append(f"{len(open_children)} open child item(s)")
    return out


def ready(bl, sprint=None, any_sprint=False):
    ids = [i for i in bl.items if not waits(bl, i, any_sprint)
           and (sprint is None or bl.sprint_of(i) == sprint)]
    return sorted(ids, key=bl.order_key)


# ------------------------------------------------------------------ near-duplicates and recurring work

def words(text):
    """The words similar compares: lowercased runs of letters and digits, stop words and single characters left out."""
    return {w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if len(w) > 1 and w not in STOP_WORDS}


def similar(bl, text, exclude=()):
    """Open items ranked by word overlap with text: (score, shared count, id) for each item that shares a word, the
    score the share of text's words found in the item's title and goal; highest first, then most shared, then id."""
    q = words(text)
    out = []
    for iid, it in bl.items.items():
        if iid in exclude or it.get("kind") == "sprint" or it.get("status") not in OPEN:
            continue
        shared = q & words(f"{it.get('title', '')} {it.get('goal', '')}")
        if shared:
            out.append((round(len(shared) / len(q), 2), len(shared), iid))
    return sorted(out, key=lambda r: (-r[0], -r[1], r[2]))


def is_near(row):
    return row[0] >= SIMILAR_MIN and row[1] >= SIMILAR_WORDS


def recurring_left_out(bl, sid):
    """Open P1 items whose recurs list names RECURRING_MIN sprints or more and that are not in sprint sid."""
    return sorted((i for i, it in bl.items.items()
                   if it.get("kind") != "sprint" and it.get("status") in OPEN and it.get("priority") == "P1"
                   and isinstance(it.get("recurs"), list) and len(set(it["recurs"])) >= RECURRING_MIN
                   and bl.sprint_of(i) != sid), key=bl.order_key)


# ------------------------------------------------------------------ git and checks

def item_commits(root, ids):
    """{commit: [paths]} of the commits on HEAD whose KB-Work trailer names any of the ids, oldest first. Only work
    counts: a commit that changes nothing but item files (a claim, a gate, a sprint's plan) is not the item's work."""
    log = git(root, "log", "HEAD", "--reverse", "--no-merges",
              "--format=%H%x00%(trailers:key=KB-Work,valueonly,separator=%x2C)%x1e")
    out = {}
    for rec in log.split("\x1e"):
        sha, _, vals = rec.strip().partition("\x00")
        if sha and set(ID_RE.findall(vals)) & set(ids):
            paths = [p for p in git(root, "show", "--name-only", "--format=", sha).splitlines() if p]
            if any(not item_file(p) for p in paths):
                out[sha] = paths
    return out


def unlanded_code(root, ids):
    """(short hashes, remote, owners) of the code-lane KB-Work commits on HEAD naming any of the ids that are not
    ancestors of refs/remotes/<integration>/main as last fetched; the hashes are [] when all are, and ["(no such ref)"]
    when the ref is missing and there is a code-lane commit. The owners are the ids the late commits name, first seen
    first, for the code/<id> branches sync opened. Content-lane commits never count."""
    import kblane, kbpublic
    remote = kbpublic.integration_remote(root)
    code = [sha for sha, paths in item_commits(root, ids).items()
            if kblane.paths_lane(paths)[0] == kblane.CODE]
    if not code:
        return [], remote, []
    ref = f"refs/remotes/{remote}/main"
    if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode:
        return ["(no such ref)"], remote, []
    late = [sha for sha in code
            if subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=root,
                              capture_output=True).returncode]
    owners = []
    for sha in late:
        named = ID_RE.findall(git(root, "log", "-1", "--format=%(trailers:key=KB-Work,valueonly,separator=%x2C)", sha))
        owners += [i for i in named if i in ids and i not in owners][:1]
    return [sha[:10] for sha in late], remote, owners


def blob_id(root, rev, path):
    p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{rev}:{path}"], cwd=root, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout.strip() if p.returncode == 0 else None


def out_of_scope(root, commits, globs):
    """[(commit, path)] of the paths outside the globs that the item's commits changed and HEAD still has changed:
    a later commit that restored a file (a revert) clears it."""
    first = {}
    for sha, paths in commits.items():
        for p in paths:
            if not in_scope(p, globs):
                first.setdefault(p, sha)
    return [(sha, p) for p, sha in first.items() if blob_id(root, f"{sha}^", p) != blob_id(root, "HEAD", p)]


ANSI_RE = bl_intake.ANSI_RE


def colourless_env():
    """The environment with colour off: FORCE_COLOR (3 in a Claude Code background session) makes Python 3.13+
    colour its tracebacks and 3.14 argparse its usage errors, which would hide a repro's own error from own_failure
    and a check's output from its match."""
    env = {k: v for k, v in os.environ.items() if k not in ("FORCE_COLOR", "PYTHON_COLORS", "CLICOLOR_FORCE")}
    env["NO_COLOR"] = "1"
    return env


def run_check(root, c):
    """Run one check, or a bug's repro, without a shell and with colour off; its output comes back with any colour
    codes taken out. A check that names python3 or python runs with the interpreter running this tool: on a host
    whose python3 is the Windows Store alias, or none on PATH, it still proves the item."""
    argv = list(c["run"])
    if argv and argv[0] in ("python3", "python"):
        argv[0] = sys.executable
    try:
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=CHECK_TIMEOUT_S, env=colourless_env())
        code, out = p.returncode, ANSI_RE.sub("", (p.stdout or "") + (p.stderr or ""))
    except OSError as e:
        code, out = None, f"cannot start: {e}"
    except subprocess.TimeoutExpired as e:
        code, out = None, str(e)
    ok = code == c.get("exit", 0) and (not c.get("match") or re.search(c["match"], out, re.M) is not None)
    return ok, code, out


SYNTAX_ERROR = re.compile(r"(SyntaxError|IndentationError|TabError)\b")
FRAME = re.compile(r'File "([^"]*)", line \d+')
NOT_FOUND = re.compile(r"is not recognized as an internal or external command"
                       r"|^\S+: (line \d+: )?\S+: command not found$", re.M)


def own_code(argv, path):
    """True when a frame's file is the repro's own code: the -c string, or the script python runs (argv[1])."""
    if path == "<string>":
        return True
    script = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else None
    if not script:
        return False
    p, s = (os.path.normcase(os.path.normpath(x)) for x in (path, script))
    return p == s or p.endswith(os.sep + s)


def own_failure(argv, code, out):
    """Why a failing repro failed for its own error rather than the defect, or None when its failure may be the
    defect's: it cannot start (not found; exit 127 or 9009, or a shell's or python -m's lone not-found message);
    Python cannot compile its own code (a
    SyntaxError in the -c string or the script it names, before anything is tested); the tool it runs rejects its
    arguments (argparse's exit 2 with usage: and error:); or a pytest run selected no tests (exit 5, or no tests ran).
    A failed assertion, a traceback from the code under test or a finding with exit 1 is a failure it accepts."""
    lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    last = lines[-1][:200] if lines else ""
    alone = len(lines) <= 3  # a shell's or interpreter's one message, not a tool's output that mentions one
    if ((code is None and out.startswith("cannot start")) or code in (127, 9009)
            or (alone and NOT_FOUND.search(out)) or (alone and argv[1:2] == ["-m"] and "No module named " in out)):
        msg = next((ln[:200] for ln in lines if NOT_FOUND.search(ln) or "No module named " in ln), last)
        return f"the command cannot start ({msg or f'exit {code}'})"
    if code is None:
        return None
    for i, ln in enumerate(lines):
        if not SYNTAX_ERROR.match(ln):
            continue
        frame = next((m for m in map(FRAME.search, reversed(lines[:i])) if m), None)  # the frame it points at
        if frame and own_code(argv, frame.group(1)):
            return (f"Python cannot compile the repro's own code ({ln[:200]}): it fails before it tests anything, "
                    "whatever the defect does (a backslash in a Python string, or newlines lost in --repro's "
                    "split: use / in paths and ; between statements, or put the code in a script)")
    if code == 2 and re.search(r"^usage: ", out, re.M) and re.search(r"^\S+: error: ", out, re.M):
        err = next((ln for ln in lines if re.match(r"\S+: error: ", ln)), last)[:200]
        return (f"the tool rejects the repro's arguments ({err}): a usage error tests nothing (when the rejection is "
                "the defect, write a repro that runs the tool and exits 1 on it)")
    if re.search(r"\bno tests ran\b", out) or (code == 5 and re.search(r"\bdeselected\b", out)):
        return f"the test run selected no tests (exit {code}: {last}): a -k or path that matches nothing reproduces nothing"
    return None


# What a tool prints when it ran but did nothing in this clone (a missing remote, an empty selection): a check or repro
# whose output says so proves nothing, whatever its exit code (BG-uqmjlqfl's repro, publish --dry-run, printed the
# first two in a clone with no public remote and passed).
NOOP_MARKERS = (re.compile(r"\bno public remote\b", re.I),
                re.compile(r"\bnothing (?:published|to publish|to push|to land|to do|to check|to run)\b", re.I),
                re.compile(r"\bno test can be affected\b", re.I))
TEST_SUMMARY = re.compile(r"^=*\s*(\d+ [a-z]+(?:, \d+ [a-z]+)*) in \d+(?:\.\d+)?s\b", re.M)
RAN_TESTS = {"passed", "failed", "error", "errors", "xfailed", "xpassed"}
TRIVIAL_CMDS = {"true", ":", "echo", "printf", "rem"}
TRIVIAL_CODE = re.compile(r"(?:pass|None|True|0|\.\.\.|(?:sys\.)?exit\(\s*0?\s*\)|quit\(\s*\)|import sys"
                          r"|print\([^()]*\)|true|:|exit(?: 0)?|echo\b.*)?")
SHELLS = {"sh", "bash", "zsh", "cmd", "pwsh", "powershell"}
HOST_BOUND_GATE = "host-bound"  # the gate whose operator answer accepts a proof that does nothing in this clone
HOST_BOUND_ACCEPTS = APPROVALS + ("accept", "accepted")


def noop_output(out):
    """Why a check's or repro's output says it did nothing in this clone, or None: a known no-op marker
    (NOOP_MARKERS), or a pytest summary where every selected test was skipped."""
    for rx in NOOP_MARKERS:
        m = rx.search(out)
        if m:
            return f"its output says it did nothing here ({m.group(0)!r})"
    for m in TEST_SUMMARY.finditer(out):
        kinds = {w.split()[1] for w in m.group(1).split(", ")}
        if "skipped" in kinds and not kinds & RAN_TESTS:
            return f"every test it selected was skipped ({m.group(1)})"
    return None


def trivial_command(argv):
    """Why a check's command runs no test or tool code, or None: a shell builtin (true, echo), or a python -c or
    shell -c string of statements that only pass, print or exit 0. It passes whatever the code does."""
    if not argv:
        return None
    base, code = _command_code(argv)
    if base in TRIVIAL_CMDS:
        return f"it runs {base}, no test or tool"
    if code is not None and (base.startswith("python") or base in SHELLS):
        if all(TRIVIAL_CODE.fullmatch(s.strip()) for s in re.split(r"[;\n]", code)):
            return f"its code ({code.strip()[:60]!r}) only passes, prints or exits 0"
    return None


# A repro that only matches text in a file proves the text, not the behaviour: BG-qtphqxt2's rejected the literal
# '>&2', which the fix met by writing '>& 2'; BG-g6qpxe5x's was a regex over a test's text; BG-rrht7uts's grepped
# _tools/ for 'worktrees' and passed on a fix that did not work. `new` refuses one without a stated reason
# (--repro-reason, kept as the item's repro_reason) and `check` warns of an open bug's.
GREP_CMDS = {"grep", "egrep", "fgrep", "rg", "ag", "findstr", "select-string", "sls"}
READS_FILE = re.compile(r"\bopen\(|\.read_text\(|\.read_bytes\(")
TEXT_MODULES = {"sys", "re", "json", "csv", "pathlib", "os", "io", "fnmatch", "glob", "ast", "tomllib", "itertools",
                "functools", "collections", "string"}
IMPORTS = re.compile(r"(?:^|[;\n])\s*(?:from\s+([\w.]+)\s+import\b|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))")
RUNS_CODE = re.compile(r"\b(?:subprocess|runpy|importlib|exec|eval|compile|__import__|system|popen|spawn\w*"
                       r"|sys\.path)\b")
TOOL_SOURCE = re.compile(r"_tools/[\w./-]+\.py\b")


def _command_code(argv):
    """(base command name, the -c / /c / -Command string or None) of a check's argv."""
    base = re.sub(r"\.exe$", "", Path(argv[0]).name.lower()) if argv else ""
    code = argv[2] if len(argv) > 2 and argv[1].lower() in ("-c", "/c", "-command") else None
    return base, code


def _is_grep(words):
    """True when a command's words (a leading ! dropped) run a grep: GREP_CMDS or git grep."""
    words = words[1:] if words[:1] == ["!"] else words
    base = re.sub(r"\.exe$", "", Path(words[0]).name.lower()) if words else ""
    return base in GREP_CMDS or (base == "git" and words[1:2] == ["grep"])


def text_only_repro(argv):
    """Why a repro only matches text in a file and runs no behaviour, or None: grep (git grep, rg, findstr,
    Select-String), a shell -c of nothing but greps, or a python -c that reads a file and imports only text modules
    (TEXT_MODULES), running no other code. It names a _tools/ source file it reads. A script repro is not judged."""
    if not argv:
        return None
    base, code = _command_code(argv)
    if _is_grep(argv[:2]):
        what = "it greps a file"
    elif code is not None and base in SHELLS:
        segs = [s.split() for s in re.split(r"&&|\|\||[;|\n]", code)]
        segs = [w for w in segs if w and w[0] not in ("set", "exit")]
        what = "its shell code only greps files" if segs and all(map(_is_grep, segs)) else None
    elif code is not None and base.startswith("python"):
        mods = {m.split(".")[0].strip() for pair in IMPORTS.findall(code) for g in pair if g for m in g.split(",")}
        ok = READS_FILE.search(code) and mods <= TEXT_MODULES and not RUNS_CODE.search(code)
        what = "its python code only reads a file and tests its text" if ok else None
    else:
        what = None
    if not what:
        return None
    src = sorted(set(TOOL_SOURCE.findall(" ".join(argv))))
    return f"{what}{', reading source of ' + ', '.join(src) + ' for a string' if src else ''}"


def repro_text_warnings(bl):
    """check's warnings: an open bug whose repro only matches text in a file (text_only_repro) with no repro_reason."""
    out = []
    for iid, it in sorted(bl.items.items()):
        rp = it.get("repro")
        if it.get("kind") != "bug" or it.get("status") not in OPEN_STATUSES or it.get("repro_reason") \
                or not _check_ok(rp):
            continue
        why = text_only_repro(rp["run"])
        if why:
            out.append(f"{bl.label(iid)}: the repro only matches text in a file ({why}), so it can pass on a fix that "
                       "does not work or fail on one that does: run the behaviour (a test, a command on a planted "
                       "input), or state why it cannot in repro_reason")
    return out


STATE_READER = re.compile(r"\bitems?'?s?\s+(?:status|presence)\b|\b(?:status|presence) of (?:an?|each|every|the)? ?items?\b"
                          r"|\bbacklog state\b|\breads? (?:the )?backlog\b", re.I)
STATE_PATHS = (("done", r"(?<![a-z])done(?![a-z])"),
               ("drop inside a sprint", r"drop\w*[\s_-]*(?:in|inside)[\s_-]*(?:a[\s_-]*)?sprint"),
               ("drop outside a sprint", r"drop\w*[\s_-]*(?:out|outside)"),
               ("close", r"(?<![a-z])close(?![a-z])"), ("release", r"(?<![a-z])release(?![a-z])"))


def state_path_warnings(bl):
    """check's warnings: an open story, task or bug whose goal says its code reads an item's status or presence
    (STATE_READER) and whose checks name fewer than every way that state changes (STATE_PATHS: done, a drop inside and
    outside a sprint, close, release), each way found by its words in the checks' commands (a -k selector names a
    test by them). It answers SP-jtfo4ael, where a sweep passed checks that never dropped an item outside a sprint."""
    out = []
    for iid, it in sorted(bl.items.items()):
        if it.get("kind") not in ("story", "task", "bug") or it.get("status") not in OPEN_STATUSES \
                or not isinstance(it.get("goal"), str) or not STATE_READER.search(it["goal"]):
            continue
        text = " ".join(" ".join(c["run"]) for c in it.get("checks", []) if _check_ok(c)).lower()
        absent = [name for name, rx in STATE_PATHS if not re.search(rx, text)]
        if absent:
            out.append(f"{bl.label(iid)}: its goal reads an item's status or presence, and its checks name no test "
                       f"for these ways the state changes: {', '.join(absent)} (a check per path, "
                       "`-k` selectors naming them: kb/_self/backlog.md, planning)")
    return out


def gate_do_warnings(bl):
    """check's warnings: an unanswered blocking gate of an open item whose options carry no `do` (the argv that
    carries an option out, or the id of the item whose work adds that command), so an answer would wait on a command
    nobody planned."""
    out = []
    for iid, it in sorted(bl.items.items()):
        if it.get("status") not in OPEN_STATUSES:
            continue
        for g in it.get("gates", []):
            if isinstance(g, dict) and g.get("kind") == "blocking" and "answer" not in g and g.get("id") != START_GATE \
                    and not g.get("do"):
                out.append(f"{bl.label(iid)}: blocking gate {g.get('id')} has no `do` for its options, the command "
                           "that carries each out or the item that adds it (gate add --do OPTION=CMD|ID)")
    return out


def is_test_run(argv):
    """True when a check runs tests: tests.py or pytest, so it exercises the code it proves."""
    return any(Path(x).name == "tests.py" for x in argv[1:3]) or "pytest" in argv[:3]


def noop_warnings(it, repro_out=""):
    """new's warnings of a proof that may do nothing in this clone: a check or repro that runs no test or tool code,
    a bug's failing repro whose output says it did nothing here, and a bug whose repro runs a tool against this
    clone's state with no check that runs tests (done refuses such a repro that passes doing nothing)."""
    out = []
    for c in it.get("checks", []) + ([it["repro"]] if it.get("repro") else []):
        why = trivial_command(c["run"])
        if why:
            out.append(f"{shlex.join(c['run'])} proves nothing: {why}, so it passes whatever the code does")
    if it.get("repro"):
        run, tests = it["repro"]["run"], any(is_test_run(c["run"]) for c in it.get("checks", []))
        why = noop_output(repro_out)
        if why:
            out.append(f"the repro failed while doing nothing in this clone ({why}): its failure may not be the "
                       "defect's, and it can pass here the same way")
        if not tests and not is_test_run(run) and len(run) > 1 and run[1].endswith(".py"):
            out.append(f"the repro runs {run[1]} against this clone's state and no --check runs tests: should it pass "
                       "here doing nothing, done refuses it; add --check 'python3 _tools/tests.py -k <the test that "
                       "plants the defect>'")
    return out


def host_bound_accepted(it):
    g = next((g for g in it.get("gates", []) if g.get("id") == HOST_BOUND_GATE), {})
    return g.get("by") == "operator" and str(g.get("answer", "")).strip().lower() in HOST_BOUND_ACCEPTS


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
        say(f"new sprint {bl.label(it['id'])}, review story {bl.label(rv['id'])}")
        commit_written(bl, a, "file", it["id"], [it["id"], rv["id"]])
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
        why = own_failure(it["repro"]["run"], code, out)
        if why:
            raise Refused(f"--repro fails for its own error, not the defect: {why}")
        why = text_only_repro(it["repro"]["run"])
        if why and not (a.repro_reason or "").strip():
            raise Rejected(f"--repro only matches text in a file ({why}): it proves the text, not the behaviour, and "
                           "can pass on a fix that does not work; run the behaviour (a test, a command on a planted "
                           "input), or state why it cannot with --repro-reason TEXT")
        if (a.repro_reason or "").strip():
            it["repro_reason"] = a.repro_reason.strip()
    elif a.repro_reason:
        raise Rejected("--repro-reason is for a bug's --repro")
    if a.check:
        it["checks"] = [{"run": parse_cmd(c)} for c in a.check]
    warns = noop_warnings(it, out if kind == "bug" else "")
    if a.touch:
        it["touches"] = a.touch
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


def cmd_similar(bl, a):
    text = f"{a.title} {a.goal or ''}"
    if not words(text):
        raise Refused("similar: the title holds no word to compare")
    rows = similar(bl, text)
    for row in rows[:SIMILAR_SHOWN]:
        say(f"{row[0]:.2f}  {row[1]:>2}  {'near' if is_near(row) else '    '}  {bl.label(row[2])}")
    say(f"similar: {len(rows)} open item(s) share a word, {sum(map(is_near, rows))} near-duplicate(s)")
    return 0


def cmd_check(bl, a):
    pieces = host_user_pieces()
    planned = [i for sid, sp in bl.items.items() if sp.get("kind") == "sprint" and sp.get("status") == "planned"
               for i in bl.sprint_items(sid)]
    errs = validate(bl, pieces) + stale_touches(bl) + docs_after_code(bl, planned)
    stale = stale_knowledge(bl)
    warns = docs_warnings(bl) + repro_text_warnings(bl) + state_path_warnings(bl) \
        + gate_do_warnings(bl)
    for x in errs + stale + warns:
        say(withhold_names(x, pieces))  # an error that quotes an item's text never prints a name either
    say(f"backlog check: items={len(bl.items)} errors={len(errs)} stale={len(stale)} warnings={len(warns)}")
    return 1 if errs else 0


def cmd_selectors(bl, a):
    import tests
    cmd = tests.pytest_cmd()
    if cmd is None:
        raise Refused("pytest is needed to count the tests a selector collects: install uv (https://docs.astral.sh/uv/) "
                      "and rerun, or `pip install pytest pytest-xdist`")
    rows = selector_rows(bl, cmd)
    for count, why, text, iid in rows:
        flag = "error" if count is None else "NONE" if count == 0 else ""
        say(f"{'?' if count is None else count:>5}  {flag:<5}  {text}  {bl.label(iid)}" + (f"  ({why})" if why else ""))
    say(f"backlog selectors: checks={len(rows)} selectors={len({r[2] for r in rows})} "
        f"none={sum(1 for r in rows if r[0] == 0)} errors={sum(1 for r in rows if r[0] is None)}")
    return 0


def cmd_fmt(bl, a):
    n = 0
    for iid, it in bl.items.items():
        if bl.raw.get(iid) != canonical(it):
            bl.save(it)
            n += 1
    say(f"fmt: rewrote {n}")
    return 0


def line(bl, iid):
    it = bl.items[iid]
    extra = f" {it['severity']}" if it.get("severity") else ""
    return f"{iid}  {it['kind']:<7} {it.get('status', ''):<7} {it.get('priority', ''):<2}{extra}  {it.get('title', '')}"


def cmd_list(bl, a):
    for iid in sorted(bl.items, key=lambda i: (bl.items[i].get("kind") != "sprint", bl.order_key(i)
                                               if bl.items[i].get("kind") != "sprint" else i)):
        it = bl.items[iid]
        if (a.kind and it.get("kind") != a.kind) or (a.status and it.get("status") != a.status) \
                or (a.sprint and bl.sprint_of(iid) != a.sprint and iid != a.sprint):
            continue
        say(line(bl, iid))
    return 0


def cmd_find(bl, a):
    want = [w.lower() for w in a.words if w.strip()]
    if not want:
        raise Refused("find: give at least one word")
    hits = sorted((i for i, it in bl.items.items() if it.get("kind") != "sprint" and it.get("status") in OPEN
                   and all(w in f"{it.get('title', '')} {it.get('goal', '')}".lower() for w in want)),
                  key=bl.order_key)
    if not hits:
        say(f"find: no open item holds {' '.join(want)}")
        return 1
    for i in hits:
        say(line(bl, i))
        for p in bl.ancestors(i):
            say(f"  parent: {bl.label(p)}")
    return 0


def cmd_tree(bl, a):
    def shown(i):
        return not a.open or bl.items[i].get("status") not in ("done", "dropped")

    def walk(i, depth):
        say("  " * depth + line(bl, i))
        for c in sorted(bl.children(i), key=bl.order_key):
            if shown(c):
                walk(c, depth + 1)

    if a.id:
        walk(need(bl, a.id), 0)
        return 0
    if a.sprint:
        need(bl, a.sprint)
        say(line(bl, a.sprint))
        for i in sorted((i for i in bl.sprint_items(a.sprint) if bl.items[i].get("sprint") and shown(i)),
                        key=bl.order_key):
            walk(i, 1)
        return 0
    for i in sorted((i for i, it in bl.items.items() if not it.get("parent") and it.get("kind") != "sprint"
                     and shown(i)), key=bl.order_key):
        walk(i, 0)
    return 0


def cmd_show(bl, a):
    iid = need(bl, a.id)
    say(canonical(bl.items[iid]).rstrip())
    for p in bl.ancestors(iid):
        say(f"parent: {bl.label(p)}")
    sp = bl.sprint_of(iid)
    if sp:
        say(f"sprint: {bl.label(sp)}")
    for c in bl.children(iid):
        say(f"child: {line(bl, c)}")
    for x in knowledge_lines(bl, iid, indent=""):
        say(x)
    w = waits(bl, iid)
    say("ready" if not w else "waits on:\n  " + "\n  ".join(w))
    return 0


def cmd_next(bl, a):
    ids = ready(bl, a.sprint, a.any)
    if not ids:
        say("nothing ready" + (f" in {bl.label(a.sprint)}" if a.sprint else "") + ": python3 _tools/backlog.py horizon")
        return 1
    for i in ids if a.all else ids[:1]:
        say(line(bl, i))
        for x in knowledge_lines(bl, i):
            say(x)
    return 0


def items_at(root, ref):
    """{id: item} of the item files as git REF has them (a fetched origin/main holds every pushed claim); a file
    that is not a JSON object is left out. Exit 2 (Rejected) for a ref git cannot read."""
    try:
        names = [n for n in git(root, "ls-tree", "--name-only", f"{ref}:{REL_DIR}").splitlines() if n.endswith(".json")]
    except Refused as e:
        raise Rejected(f"held --ref {ref}: {e}") from e
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True,
                       input="".join(f"{ref}:{REL_DIR}/{n}\n" for n in names).encode("utf-8"))
    data, out, at = p.stdout, {}, 0
    for n in names:
        nl = data.find(b"\n", at)
        if nl < 0:
            break
        head = data[at:nl].split()
        if len(head) != 3 or head[1] != b"blob":  # `<name> missing`: nothing follows the header
            at = nl + 1
            continue
        size = int(head[2])
        body, at = data[nl + 1:nl + 1 + size], nl + 2 + size
        try:
            item = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            out[n[:-len(".json")]] = item
    return out


def touches_overlap(a, b, files):
    """True when two touches globs can name one path: either, read as a path, matches the other (`_tools/**` and
    `_tools/x.py`), or a tracked file matches both (`_tools/*.py` and `_tools/back*`)."""
    ra, rb = glob_re(a), glob_re(b)
    return bool(ra.match(b) or rb.match(a) or any(ra.match(f) and rb.match(f) for f in files))


def held_line(bl, iid, glob):
    it = bl.items[iid]
    sp = bl.sprint_of(iid)
    return f"{glob}  {bl.label(iid)}  by {it.get('claimed_by')}  {bl.label(sp) if sp else 'no sprint'}"


def cmd_held(bl, a):
    """The touches of every claimed (doing) item, one line per glob: the glob, the item, its claimer and its sprint.
    --overlaps ID: only the claimed items outside ID's own chain whose touches overlap ID's scope (its touches and
    its descendants'), each line naming the glob of ID's it meets; exit 1 when there is one."""
    mine = bl
    if a.ref:
        bl = Backlog(bl.root)
        bl.items, bl.raw = items_at(bl.root, a.ref), {}
    doing = sorted(i for i, it in bl.items.items() if it.get("status") == "doing" and it.get("claimed_by")
                   and it.get("kind") != "sprint")
    if not a.overlaps:
        rows = sorted((t, i) for i in doing for t in bl.items[i].get("touches", []) or [] if isinstance(t, str) and t)
        for t, i in rows:
            say(held_line(bl, i, t))
        if not rows:
            say("held: no claimed item holds a path")
        return 0
    src = mine if a.overlaps in mine.items else bl
    iid = need(src, a.overlaps)
    chain = {iid, *src.ancestors(iid), *src.descendants(iid)}
    own = [t for t in scope(src, iid) if isinstance(t, str) and t]
    files = tracked_files(bl.root)
    hits = []
    for i in doing:
        if i in chain:
            continue
        for t in bl.items[i].get("touches", []) or []:
            met = [m for m in own if isinstance(t, str) and t and touches_overlap(m, t, files)]
            if met:
                hits.append(f"{held_line(bl, i, t)}  meets {', '.join(met)}")
    for x in sorted(hits):
        say(x)
    if not hits:
        say(f"held: no claimed item's touches overlap {src.label(iid)}")
    return 1 if hits else 0


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
    it.update(status="doing", claimed_by=a.by)
    bl.save(it)
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


def record_decision(bl, iid, gate, text):
    """Keep the operator's answer to a gate as an active decision of kb/_self (`kbdecide.py record`, so check.py guards
    the write): its source names the item and the gate, its context is the item. Refused with kbdecide's reason."""
    tool = Path(bl.root) / "_tools" / "kbdecide.py"
    argv = [sys.executable, str(tool), "record", "--root", "_self", "--source", f"backlog item {iid} gate {gate}",
            "--context", f"item:{iid}", "--by", "operator", "--maker", "operator", "--", text]
    p = subprocess.run(argv, cwd=str(bl.root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    if p.returncode:
        raise Refused(f"--record: {(p.stdout + p.stderr).strip()}")
    say(p.stdout.strip())


def cmd_answer(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    g = next((g for g in it.get("gates", []) if g.get("id") == a.gate), None)
    if g is None:
        raise Refused(f"{bl.label(iid)} has no gate {a.gate}")
    if a.record and (a.provisional or a.confirm or a.by != "operator" or not a.answer):
        raise Rejected("--record keeps the operator's answer as a decision: --answer TEXT --by operator, "
                       "never --provisional or --confirm")
    if a.confirm:
        if g.get("by") != "agent":
            raise Refused(f"gate {a.gate} of {bl.label(iid)} has no agent answer to confirm")
        g["by"] = "operator"
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
            record_decision(bl, iid, a.gate, a.answer)
    bl.save(it)
    say(f"gate {a.gate} of {bl.label(iid)}: {g['answer']} (by {g['by']})")
    return 0


def changed_item(bl, iid, edit):
    """Apply `edit` to a copy of the item and write it when the copy differs and validates as `check` does: no error
    that was not there before (this item's, or another's that a dependency cycle or a review story's sprint would
    add). Returns True when it wrote the file, False when the edit leaves the item as it is; raises Rejected with the
    new errors and the item untouched."""
    return changed_items(bl, {iid: edit})


def changed_items(bl, edits):
    """`changed_item` for several items at once ({id: edit}): the copies are validated together, so either every
    changed item is written or none is. Returns True when it wrote any file."""
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
        fresh = [x for x in validate(bl) + stale_touches(bl) if x not in before]
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
SET_FIELDS = ("notes", "priority", "rank", "sprint") + SET_LISTS  # what set changes; the others are refused
SET_REFUSED = {  # a field set refuses, with the rule it states
    "status": "changes only through claim, release, start, close, drop and done",
    "claimed_by": "changes only through claim and release",
    "evidence": "is written only by done",
    "id": "is the item's identity",
    "kind": "is the item's identity",
    "parent": "is the item's identity",
    "title": "is the item's identity",
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
    given.update({f: getattr(a, f) for f in SET_LISTS})
    given = {f: v for f, v in given.items() if v is not None}
    both = sorted(set(given) & set(a.clear))
    if both:
        raise Rejected(f"set: {', '.join(both)} given a value and --clear together")
    if not given and not a.clear:
        raise Rejected("set: nothing to change: name a field (" + ", ".join(SET_FIELDS) + ")")
    named = sorted(set(given) | set(a.clear))
    if it.get("kind") == "sprint" and set(named) - {"notes", "links"}:
        raise Rejected(f"set refuses {', '.join(sorted(set(named) - {'notes', 'links'}))} on a sprint: "
                       "a sprint takes notes and links only")
    if it.get("status") == "done" and {"checks", "touches"} & set(named):
        raise Rejected(f"set refuses checks and touches on {bl.label(iid)}: it is done, and its evidence proves the "
                       "checks and touches it had")
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

    changed_item(bl, iid, edit)
    say(f"reopened {label}: status {state}, evidence and claim cleared. Why: {a.why.strip()}")
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
        if len(same) > 1 or any(known.get(k) != v for k, v in gate.items() if k != "id") \
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


def host_gates(bl, sid, answered=True):
    """(item id, gate) for each gate of the sprint's open items that carries a host check, the answered ones only
    unless `answered` is False."""
    return [(i, g) for i in bl.sprint_items(sid) if bl.items[i].get("status") not in ("done", "dropped")
            for g in bl.items[i].get("gates", []) if "host_check" in g and (not answered or "answer" in g)]


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


def noop_proof(bl, iid, passed):
    """done's rule for checks that passed ([(check, output)]) without doing their work: one that runs no test or tool
    code is warned of; one whose output says it did nothing in this clone (noop_output) is warned of too, and refuses
    done unless another passing check runs tests and did its work, or the operator accepted the host-bound proof
    (gate HOST_BOUND_GATE answered accept or approve)."""
    noops = []
    for c, out in passed:
        why = noop_output(out)
        if why:
            noops.append((c, why))
        why = why or trivial_command(c["run"])
        if why:
            say(f"warning: {shlex.join(c['run'])} passed without doing its work in this clone: {why}")
    proven = [c for c, out in passed if is_test_run(c["run"]) and not noop_output(out)]
    if not noops or proven or host_bound_accepted(bl.items[iid]):
        return
    c, why = noops[0]
    raise Refused(f"{bl.label(iid)} is not done: {shlex.join(c['run'])} passed without doing its work in this clone "
                  f"({why}), and no check that runs tests proves the fix. Name one: backlog.py set {iid} --add "
                  "--check 'python3 _tools/tests.py -k <the test that plants the defect>'; or ask the operator to "
                  f"accept the host-bound proof: backlog.py gate add {iid} --id {HOST_BOUND_GATE} --question "
                  "'Accept a proof that does nothing in this clone?' --option accept --option add-test "
                  f"--recommendation add-test, answered with backlog.py answer {iid} {HOST_BOUND_GATE} --answer "
                  "accept --by operator")


def cmd_done(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    kind = it["kind"]
    if kind == "sprint":
        raise Refused("a sprint is closed with backlog.py close")
    if kind == "epic":
        problems = [f"open child {line(bl, c)}" for c in bl.children(iid)
                    if bl.items[c].get("status") not in ("done", "dropped")]
    else:
        problems = [x for x in waits(bl, iid, any_sprint=True)
                    if not x.startswith(("status doing", "not in an active sprint"))]
    if it.get("status") not in ("todo", "doing", "draft" if kind == "epic" else "todo"):
        problems.append(f"status {it.get('status')}")
    if it.get("review"):
        sp = bl.sprint_of(iid)
        for s in bl.sprint_items(sp) + [sp]:
            for g in bl.items[s].get("gates", []):
                if g.get("by") == "agent":
                    problems.append(f"provisional answer to confirm: {bl.label(s)} gate {g['id']}: {g['answer']}")
    globs = scope(bl, iid)
    if globs:
        dirty = [ln[3:] for ln in git(bl.root, "status", "--porcelain").splitlines()
                 if in_scope(ln[3:].strip('"'), globs) and not in_scope(ln[3:].strip('"'), ())]
        if dirty:
            problems.append("uncommitted changes in scope (checks run on HEAD): " + ", ".join(dirty[:5]))
        family = [iid] + bl.descendants(iid)
        if it.get("touches") and not item_commits(bl.root, [iid] + bl.descendants(iid)):
            problems.append(f"no commit on HEAD carries the trailer KB-Work: {iid} or one of its descendants' ids "
                            "and changes a file other than item files (git reads a trailer only in the message's last "
                            "paragraph, with the others; a claim or planning commit is not the work)")
        late, remote, owners = unlanded_code(bl.root, family)
        if late == ["(no such ref)"]:
            problems.append(f"code commits of the item, and refs/remotes/{remote}/main is not fetched: fetch {remote}, "
                            "then run done again")
        elif late:
            branches = ", ".join("code/" + o for o in owners or [iid])
            problems.append(f"code commit(s) {', '.join(late)} are not on {remote}/main: merge the merge request sync "
                            f"opened for them (branch {branches}), fetch {remote} and run done again")
        for sha, path in out_of_scope(bl.root, item_commits(bl.root, family), globs):
            problems.append(f"commit {sha[:10]} changed {path}, outside touches (revert it, or widen touches)")
    if problems:
        raise Refused(f"{bl.label(iid)} is not done:\n  " + "\n  ".join(problems))
    checks = list(it.get("checks", [])) + ([it["repro"]] if it.get("repro") else [])
    results, failed, passed = [], [], []
    for c in checks:
        ok, code, out = run_check(bl.root, c)
        results.append({"run": c["run"], "exit": code, "sha256": hashlib.sha256(out.encode()).hexdigest()[:16]})
        say(f"{'ok  ' if ok else 'FAIL'} exit={code} {shlex.join(c['run'])}")
        if not ok:
            failed.append((c, code, out))
        else:
            passed.append((c, out))
    if failed:
        for c, code, out in failed:
            tail = "\n".join(out.strip().splitlines()[-8:])
            say(f"--- {shlex.join(c['run'])} (want exit {c.get('exit', 0)}"
                + (f", output matching {c['match']!r}" if c.get("match") else "") + f"):\n{tail}")
        raise Refused(f"{bl.label(iid)} is not done: {len(failed)} check(s) failed")
    noop_proof(bl, iid, passed)
    if a.dry_run:
        say(f"{bl.label(iid)} would be done")
        return 0
    head = git(bl.root, "rev-parse", "HEAD").strip()
    it.update(status="done", evidence={"commit": head, "checks": results})
    it.pop("claimed_by", None)
    bl.save(it)
    say(f"done {bl.label(iid)} at {head[:10]}" + ("" if a.commit else f"; commit this with the trailer KB-Work: {iid}"))
    commit_written(bl, a, "done", iid)
    return 0


# land: the steps after a worker's branch comes back, each a command run from the clone's root with this interpreter
LAND_HEAVY = (("stress_test.py", ["_tools/stress_test.py"]),  # run once, when the landing changes _tools/
              ("rag.py eval", ["_tools/rag.py", "eval"]),
              ("lint", [".claude/skills/kb-verify/lint.py"]))
LAND_SYNC = ("kbgit.py sync --push", ["_tools/kbgit.py", "sync", "--push"])
LAND_TAIL = 30  # output lines shown of a step that passed (sync's report is shown whole)


def land_stop(step, why):
    return Refused(f"land stopped at step {step}: {why}")


def land_run(root, step, argv, whole=False):
    """Run one landing step; its output (the tail of it, unless WHOLE or it failed) goes through say()."""
    say(f"land: {step}")
    try:
        p = subprocess.run([sys.executable, *argv], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=colourless_env())
        code, out = p.returncode, ANSI_RE.sub("", (p.stdout or "") + (p.stderr or "")).rstrip()
    except OSError as e:
        code, out = None, f"cannot start: {e}"
    lines = out.splitlines()
    shown = lines if whole or code else lines[-LAND_TAIL:]
    if shown:
        say("\n".join(shown))
    if code != 0:
        raise land_stop(step, f"python3 {shlex.join(argv)} exited {code}")


def land_git(root, step, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise land_stop(step, f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def has_ref(root, ref):
    return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root, capture_output=True).returncode == 0


def checked_out_elsewhere(root, branch):
    """(path, lock reason or None) of another worktree that has BRANCH checked out, or None (git rebase cannot check
    it out here). A locked worktree with no reason has the reason ""."""
    here = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    for block in git(root, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("worktree ") or f"branch refs/heads/{branch}" not in lines:
            continue
        path = Path(lines[0][len("worktree "):]).resolve()
        if path != here:
            lock = next((ln[len("locked "):] for ln in lines if ln == "locked" or ln.startswith("locked ")), None)
            return path, lock
    return None


# the lock Claude Code puts on a subagent's worktree, which outlives the agent when it left background work running
WORKER_LOCK = "claude agent"
WORKER_DIR = (".claude", "worktrees")  # under the clone's main checkout


def live_processes(path):
    """([(pid, command)], None) of the processes whose working directory is PATH or under it, or (None, why) when this
    host gives no way to tell: Linux reads /proc/<pid>/cwd, other POSIX hosts (macOS) ask `lsof -d cwd` for every
    process's working directory; Windows exposes no process's working directory to the standard library, so it is
    never checked there. Never signals a process."""
    target = os.path.realpath(path)

    def inside(cwd):
        return cwd == target or cwd.startswith(target.rstrip(os.sep) + os.sep)

    if os.name == "nt":
        return None, "Windows does not expose a process's working directory"
    proc = Path("/proc")
    if (proc / "self" / "cwd").exists():
        out = []
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            try:
                cwd = os.readlink(d / "cwd")
                comm = (d / "comm").read_text(encoding="utf-8", errors="replace").strip()
            except OSError:  # gone, or another user's
                continue
            if inside(cwd):
                out.append((int(d.name), comm))
        return sorted(out), None
    lsof = shutil.which("lsof")
    if not lsof:
        return None, "no /proc and no lsof on this host"
    try:
        p = subprocess.run([lsof, "-n", "-P", "-w", "-d", "cwd", "-Fpcn"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"lsof failed: {e}"
    out, pid, comm, seen = [], None, "", False
    for ln in p.stdout.splitlines():
        if ln.startswith("p") and ln[1:].isdigit():
            pid, comm, seen = int(ln[1:]), "", True
        elif ln.startswith("c"):
            comm = ln[1:]
        elif ln.startswith("n") and pid is not None and inside(ln[1:]):
            out.append((pid, comm))
    if not seen:  # lsof lists at least itself: nothing read means it could not look
        return None, f"lsof listed no process (exit {p.returncode})"
    return sorted(set(out)), None


def release_worker_worktree(root, path, lock):
    """Remove the finished worker's worktree PATH that holds the branch land needs: unlocked, then `git worktree
    remove` (never --force). Only a worktree under the clone's .claude/worktrees/ whose lock reason starts with
    WORKER_LOCK and that has no uncommitted changes. Returns None once it is removed, else why it was left as it was
    (a remove that fails puts the lock back)."""
    def run_git(*args, cwd=root):
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout if not p.returncode else (p.stderr or p.stdout)).strip()

    if lock is None:
        return "it is not locked"
    if not lock.startswith(WORKER_LOCK):
        return f"it is locked ({lock or 'no reason given'}), not by a Claude Code agent"
    common = (Path(root) / git(root, "rev-parse", "--git-common-dir").strip()).resolve()
    if path.parent != common.parent.joinpath(*WORKER_DIR).resolve():
        return f"it is locked ({lock}) but not under {'/'.join(WORKER_DIR)}/ of the clone"
    code, out = run_git("status", "--porcelain", cwd=path)
    if code or out:
        return (f"it is locked ({lock}) and has uncommitted changes: commit or discard them there, then "
                f"git worktree unlock and git worktree remove it")
    procs, unchecked = live_processes(path)
    if procs:  # the worker left background work running there: removing the worktree would pull it from under it
        named = ", ".join(f"pid {pid} ({comm or '?'})" for pid, comm in procs)
        return (f"it is locked ({lock}) and a process still runs there: {named}; end it (the worker ends every "
                f"background command and monitor it started), then run land again")
    if unchecked:
        say(f"land: could not check {path} for live processes ({unchecked}); removing it as a clean worker's")
    code, out = run_git("worktree", "unlock", str(path))
    if code:
        return f"git worktree unlock: {out}"
    code, out = run_git("worktree", "remove", str(path))
    if code:
        run_git("worktree", "lock", "--reason", lock, str(path))
        return f"git worktree remove: {out}"
    say(f"land: removed the finished worker's worktree {path} (unlocked; its lock was: {lock})")
    return None


# head pipeline states after which GitLab's auto-merge ("merge when the pipeline succeeds") never fires
STUCK_PIPELINES = ("skipped",)


def mr_stuck(mr):
    """True for a GitLab merge request, as the single-request API (`projects/:id/merge_requests/:iid`) answers it,
    that is open, mergeable (`detailed_merge_status` mergeable; `merge_status` can_be_merged on a GitLab without the
    detailed field), set to auto-merge, and whose head pipeline ended in a state in STUCK_PIPELINES: auto-merge waits
    for a pipeline to succeed, which a skipped one never does, so the request sits until someone merges it."""
    if not isinstance(mr, dict):
        return False
    pipe = mr.get("head_pipeline") if isinstance(mr.get("head_pipeline"), dict) else {}
    detailed = mr.get("detailed_merge_status")
    mergeable = detailed == "mergeable" if detailed is not None else mr.get("merge_status") == "can_be_merged"
    return (mr.get("state") == "opened" and mr.get("merge_when_pipeline_succeeds") is True and mergeable
            and pipe.get("status") in STUCK_PIPELINES)


def stuck_merge_request(root, remote, branch):
    """The line land adds while it waits for the merge request of BRANCH: when an open request of BRANCH into main on
    REMOTE's GitLab is stuck (`mr_stuck`), it names the request and the command that merges it. None when no request
    is stuck, and also, saying nothing, when it cannot tell: a remote that is a local path, a forge that is not GitLab,
    glab not signed in, a failed or unreadable call."""
    import urllib.parse
    from ql_deliver import forge_list, origin_forge
    code, url, _ = run(["git", "remote", "get-url", remote], cwd=root)
    url = (url or "").strip()
    if code or not url or url.lower().startswith("file:") or Path(url).exists():
        return None  # a local remote names no forge
    forge, host, project = origin_forge(url)
    if forge != "gitlab":
        return None
    quoted = urllib.parse.quote(project, safe="")
    listed, _, _ = forge_list(url, run, None, lambda p: (
        f"projects/{p}/merge_requests?state=opened&source_branch={urllib.parse.quote(branch, safe='')}"
        f"&target_branch=main&per_page=20"))
    for summary in listed or []:
        iid = summary.get("iid") if isinstance(summary, dict) else None
        if not isinstance(iid, int):
            continue
        code, out, _ = run(["glab", "api", "--hostname", host, f"projects/{quoted}/merge_requests/{iid}"])
        try:
            mr = json.loads(out) if code == 0 else None
        except ValueError:
            mr = None
        if mr_stuck(mr):
            status = mr["head_pipeline"].get("status")
            return (f"land: merge request !{iid} ({mr.get('web_url') or branch}) is mergeable and set to auto-merge, "
                    f"but its pipeline was {status}, so auto-merge will not fire: merge it with "
                    f"glab mr merge {iid} --auto-merge=false --yes -R https://{host}/{project}")
    return None


def cmd_land(bl, a):
    """Land a finished item's branch: rebase it on the integration main, then by lane. Content: done --commit, the
    heavy checks when _tools/ changed, sync --push. Code not yet on the integration main: the heavy checks, sync
    --push (a code/<id> merge request; main does not move), and a re-run once it has merged finishes it as content
    does. Stops at the first failing step, naming it. Every run and every stop ends on the branch (or the detached
    commit) it started on: the rebase switches to the landed branch, and a claim --commit made after land must not
    ride on it into its merge request."""
    import kbpublic
    iid = need(bl, a.id)
    root = bl.root
    remote = kbpublic.integration_remote(root)
    branch = a.branch or f"work/{iid}"
    upstream = f"refs/remotes/{remote}/main"
    if git(root, "status", "--porcelain").strip():
        raise land_stop("clean tree", "uncommitted changes: commit or stash them first (git status --short)")
    if not has_ref(root, f"refs/heads/{branch}"):
        raise land_stop("branch", f"no local branch {branch} (--branch names another)")
    other = checked_out_elsewhere(root, branch)
    if other:  # a finished worker's worktree, clean and locked by Claude Code, is removed; any other refuses
        why = release_worker_worktree(root, *other)
        if why:
            raise land_stop("branch", f"{branch} is checked out in the worktree {other[0]} and {why}: land it from "
                                      "there, or remove that worktree first")
    start = git(root, "rev-parse", "HEAD").strip()
    start_ref = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip()
    try:
        say(f"land: fetch {remote} main")
        land_git(root, "fetch", "fetch", "--quiet", remote, f"+refs/heads/main:{upstream}")
        say(f"land: rebase {branch} on {remote}/main")
        p = subprocess.run(["git", "rebase", "--quiet", upstream, branch], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode:
            subprocess.run(["git", "rebase", "--abort"], cwd=root, capture_output=True)
            raise land_stop("rebase", f"{branch} does not rebase cleanly on {remote}/main (rebase aborted, nothing "
                                      f"changed): rebase it by hand, then run land again\n"
                                      f"{(p.stderr or p.stdout).strip()}")
        bl = Backlog(root)  # the item files as the rebased branch has them
        need(bl, iid)
        family = [iid] + bl.descendants(iid)
        late, _, owners = unlanded_code(root, family)
        if late == ["(no such ref)"]:
            raise land_stop("fetch", f"{upstream} does not exist after the fetch")
        if late:
            import kg_lane  # the branch sync --push opens for this range, named by the one helper sync uses
            _, code_branch = kg_lane.lane_plan(str(root), upstream, "HEAD")
            code_branch = code_branch or "code/" + (owners[0] if owners else iid)  # git failed: the item's own id
            tracking = f"refs/remotes/{remote}/{code_branch}"
            fetched = subprocess.run(["git", "fetch", "--quiet", remote, f"+refs/heads/{code_branch}:{tracking}"],
                                     cwd=root, capture_output=True).returncode == 0
            if fetched and git(root, "rev-parse", f"{tracking}^{{tree}}") == git(root, "rev-parse", "HEAD^{tree}"):
                say(f"land: {bl.label(iid)} waits for its merge request (branch {code_branch} on {remote}, already "
                    f"pushed with this content): merge it, then run backlog.py land {iid} again")
                stuck = stuck_merge_request(root, remote, code_branch)
                if stuck:
                    say(stuck)
                return 0
        if not late:
            if bl.items[iid].get("status") == "done":
                say(f"land: done: {bl.label(iid)} is done already")
            else:
                say("land: done --commit")
                try:
                    cmd_done(bl, argparse.Namespace(id=iid, dry_run=False, commit=True, trailer=a.trailer))
                except Refused as e:
                    raise land_stop("done", str(e)) from None
        changed = git(root, "diff", "--name-only", upstream, "HEAD").splitlines()
        if any(p.startswith("_tools/") for p in changed):
            for step, argv in LAND_HEAVY:
                land_run(root, step, argv)
        land_run(root, *LAND_SYNC, whole=True)
        if late:
            say(f"land: {bl.label(iid)} is not done yet: its code goes as the merge request of branch {code_branch}; "
                f"once it has merged, run backlog.py land {iid} again (fetch, rebase, done --commit, sync --push)")
        else:
            say(f"land: {bl.label(iid)} landed")
        return 0
    finally:  # back to where land started, whatever happened after the rebase switched to BRANCH
        back = (["switch", "-q", start_ref[len("refs/heads/"):]] if start_ref.startswith("refs/heads/")
                else ["switch", "-q", "--detach", start])
        p = subprocess.run(["git", *back], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if p.returncode:
            say(f"land: could not return to {start_ref or start[:10]}: {(p.stderr or p.stdout).strip()}")


def cmd_drop(bl, a):
    iid = need(bl, a.id)
    it = bl.items[iid]
    live = [c for c in bl.descendants(iid) if bl.items[c].get("status") not in ("done", "dropped")]
    if live:
        raise Refused(f"{bl.label(iid)} has open children: " + ", ".join(bl.label(c) for c in live[:5]))
    users = [i for i, x in bl.items.items() if iid in x.get("depends_on", []) and x.get("status") != "dropped"]
    if users:
        raise Refused(f"{bl.label(iid)} is a dependency of " + ", ".join(bl.label(u) for u in users[:5]))
    # a dropped item that depended on this one keeps no link to it: check reports a dependency on a dropped item
    for i, x in bl.items.items():
        if x.get("status") == "dropped" and iid in x.get("depends_on", []):
            left = [d for d in x["depends_on"] if d != iid]
            if left:
                x["depends_on"] = left
            else:
                x.pop("depends_on")
            bl.save(x)
    if not bl.sprint_of(iid):
        label = bl.label(iid)
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


def has_scope(bl, iid):
    """An item's work has a scope: it is dropped, has touches of its own, or has tasks or subtasks that are not
    dropped and every one of which has a scope (a story broken down into tasks is covered by them)."""
    it = bl.items[iid]
    if it.get("status") == "dropped" or it.get("touches"):
        return True
    kids = [c for c in bl.children(iid) if bl.items[c].get("status") != "dropped"]
    return bool(kids) and all(has_scope(bl, c) for c in kids)


def cmd_start(bl, a):
    sid = need(bl, a.sprint)
    sp = bl.items[sid]
    if sp.get("kind") != "sprint":
        raise Refused(f"{bl.label(sid)} is not a sprint")
    g = next(g for g in sp["gates"] if g["id"] == START_GATE)
    if not start_approved(sp):
        raise Refused(f"{bl.label(sid)}: the operator has not approved it (gate {START_GATE}: {g.get('answer', 'open')})")
    items = bl.sprint_items(sid)
    if len(items) < 2:
        raise Refused(f"{bl.label(sid)} commits to no item besides its review")
    unchecked = [f"{bl.label(i)} gate {g['id']}" for i, g in host_gates(bl, sid)
                 if not g.get("host_checked", {}).get("ok")]
    if unchecked:
        raise Refused(f"{bl.label(sid)} has an answered gate whose host setup is not checked on this host "
                      "(`backlog.py host-check`, which must pass):\n  " + "\n  ".join(unchecked))
    bare = [i for i in items if not bl.items[i].get("review") and not has_scope(bl, i)]
    if bare:
        raise Refused(f"{bl.label(sid)} has work items without touches (give each its own touches, or tasks that "
                      "all have them):\n  " + "\n  ".join(bl.label(i) for i in bare))
    later = docs_after_code(bl, items)
    if later:
        raise Refused(f"{bl.label(sid)} has a task whose docs wait for the code they describe:\n  " + "\n  ".join(later))
    for i in items:
        if bl.items[i].get("status") == "draft":
            bl.items[i]["status"] = "todo"
            bl.save(bl.items[i])
    sp["status"] = "active"
    bl.save(sp)
    say(f"started {bl.label(sid)}: {sp['goal']}")
    for w in docs_warnings(bl, set(items)):
        say(f"  warning: {w}")
    for i, d, where in outside_deps(bl, sid):
        say(f"  warning: {bl.label(i)} depends on {bl.label(d)}, outside this sprint ({where})")
    for i in recurring_left_out(bl, sid):
        say(f"  warning: recurring P1 item {bl.label(i)} (recurs in {len(set(bl.items[i]['recurs']))} sprints) "
            "is not in this sprint")
    commit_written(bl, a, "start", sid)
    return 0


def summary_key(bl, iid):
    """Tree order: each item under its parent, the tops (epics, then the sprint's stories and bugs) in work order."""
    return [bl.order_key(x) for x in reversed([iid] + bl.ancestors(iid))]


def summary_line(bl, iid, gone):
    """One commit-body line for an item close deletes: its id, title, kind, status and the commit done recorded."""
    it = bl.items[iid]
    depth = sum(1 for p in bl.ancestors(iid) if p in gone)
    ev = (it.get("evidence") or {}).get("commit") if isinstance(it.get("evidence"), dict) else None
    at = f" at {ev[:10]}" if ev else ", no evidence commit"
    return f"{'  ' * depth}- {bl.label(iid)} ({it.get('kind', '')}): {it.get('status', '')}{at}"


def cmd_close(bl, a):
    if a.summary and a.commit:
        raise Refused("close --summary only prints and commits nothing: run close --commit without --summary")
    sid = need(bl, a.sprint)
    items = bl.sprint_items(sid)
    left = [i for i in items if bl.items[i].get("status") not in ("done", "dropped")]
    if left:
        raise Refused(f"{bl.label(sid)} is not finished:\n  " + "\n  ".join(line(bl, i) for i in left))
    gone = set(items)
    epics = {p for i in items for p in bl.ancestors(i) if bl.items[p].get("kind") == "epic"}
    for e in epics:
        rest = [c for c in bl.descendants(e) if c not in gone]
        if bl.items[e].get("status") == "done" and not rest:
            gone.add(e)
    summary = [f"delivered by {bl.label(sid)}:"] + [summary_line(bl, i, gone)
                                                  for i in sorted(gone, key=lambda i: summary_key(bl, i))]
    if a.summary:  # the runbook prints the list, writes the retrospective, then closes: --summary changes nothing
        for x in summary:
            say(x)
        return 0
    title = bl.items[sid].get("title", "")
    for i in gone:
        say(f"deleted {line(bl, i)}")
    # a remaining item's relates_to is information only, and a depends_on on a deleted item that is not dropped is
    # satisfied (close refuses while anything is open): drop those ids, or check fails on dangling links and horizon
    # counts the item as waiting outside its sprint. A dependency on a dropped item stays for check to report.
    dead = gone | {sid}
    for i, it in sorted(bl.items.items()):
        if i in dead:
            continue
        cut = []
        for f in ("relates_to", "depends_on"):
            ids = it.get(f)
            if not isinstance(ids, list):
                continue
            off = [r for r in ids if r in dead and (f == "relates_to" or bl.items[r].get("status") != "dropped")]
            if not off:
                continue
            keep = [r for r in ids if r not in off]
            if keep:
                it[f] = keep
            else:
                it.pop(f)
            cut.append(f"{f} {', '.join(off)}")
        if cut:
            bl.save(it)
            say(f"dropped {'; '.join(cut)} from {bl.label(i)}")
    for i in gone:
        bl.delete(i)
    label = bl.label(sid)
    bl.delete(sid)
    say(f"closed {label}; its items stay in git history (git log --grep 'KB-Work: <id>')")
    # the body is the summary: the retrospective's findings, written by hand, go in with git commit --amend
    commit_written(bl, a, "close", sid, body="\n".join(summary), title=title)
    return 0


def where_outside(bl, d):
    """Where a dependency outside a sprint stands: in no sprint, or in a sprint (started or not)."""
    sp = bl.sprint_of(d)
    if not sp or sp not in bl.items:
        return "in no sprint"
    return f"in sprint {bl.label(sp)}" + ("" if bl.items[sp].get("status") == "active" else ", not started")


def outside_deps(bl, sid):
    """[(item id, dependency id, where)] for each undone depends_on, own or an ancestor's, of an open item of sprint
    sid that points outside it, into no sprint or a sprint not started."""
    items = set(bl.sprint_items(sid))
    out = []
    for i in sorted(items):
        if bl.items[i].get("status") in ("done", "dropped"):
            continue
        for d in dict.fromkeys(d for x in [i] + bl.ancestors(i) for d in bl.items[x].get("depends_on", [])):
            sp = bl.sprint_of(d) if d in bl.items else None
            if d in items or d not in bl.items or bl.items[d].get("status") == "done" or (
                    sp and bl.items[sp].get("status") == "active"):
                continue
            out.append((i, d, where_outside(bl, d)))
    return out


def horizon(bl, sid):
    """(reachable open ids, {cause: [stuck ids]}, critical path [ids], level widths) for a sprint."""
    items = [i for i in bl.sprint_items(sid) if bl.items[i].get("status") not in ("done", "dropped")]
    cause = {}
    if bl.items[sid].get("status") != "active":
        g = next((g for g in bl.items[sid].get("gates", []) if g.get("id") == START_GATE), {})
        why = (STARTS + sid if start_approved(bl.items[sid])
               else f"the sprint's start gate: {g.get('question', 'not started')}")
        cause = {i: why for i in items}
    for i in items:
        outside = []
        for x in [i] + bl.ancestors(i):
            it = bl.items[x]
            for g in open_gates(it):
                cause[i] = f"gate {x}/{g['id']} ({bl.items[x]['title']}): {g['question']}" + (
                    f" [recommended: {g['recommendation']}]" if g.get("recommendation") else "")
            if it.get("trigger") and not it["trigger"].get("fired"):
                cause[i] = f"trigger on {bl.label(x)}: {it['trigger']['when']}"
            for d in it.get("depends_on", []):
                if d not in items and bl.items.get(d, {}).get("status") != "done" and d not in outside:
                    outside.append(d)
        if outside:
            cause[i] = "outside this sprint: " + ", ".join(
                f"{bl.label(d)} ({where_outside(bl, d) if d in bl.items else 'not found'})" for d in outside)
    # propagate: an item waits on what its own and its ancestors' dependencies, its children
    # and (for the review) the sprint wait on
    edges = {i: list(dict.fromkeys(d for x in [i] + bl.ancestors(i) for d in bl.items[x].get("depends_on", [])
                                   if d in items))
             + [c for c in bl.children(i) if c in items] for i in items}
    for i in items:
        if bl.items[i].get("review"):
            edges[i] += [s for s in items if s != i and bl.items[s].get("kind") in IN_SPRINT]
    changed = True
    while changed:
        changed = False
        for i in items:
            if i not in cause:
                src = next((cause[d] for d in edges[i] if d in cause), None)
                if src:
                    cause[i], changed = src, True
    reach = [i for i in items if i not in cause]
    depth = {}

    def d(i, seen=()):
        if i not in depth:
            depth[i] = 1 + max((d(x, seen + (i,)) for x in edges[i] if x in reach and x not in seen), default=0)
        return depth[i]

    for i in reach:
        d(i)
    path = []
    if reach:
        cur = max(reach, key=lambda i: (depth[i], i))
        while cur:
            path.append(cur)
            nxt = [x for x in edges[cur] if x in reach and depth.get(x) == depth[cur] - 1]
            cur = min(nxt) if nxt else None
    widths = [sum(1 for i in reach if depth[i] == k) for k in range(1, (max(depth.values()) if depth else 0) + 1)]
    by_cause = {}
    for i, c in cause.items():
        by_cause.setdefault(c, []).append(i)
    return reach, by_cause, list(reversed(path)), widths


def cmd_horizon(bl, a):
    sprints = [a.sprint] if a.sprint else sorted(i for i, it in bl.items.items()
                                                  if it.get("kind") == "sprint" and it.get("status") == "active")
    lines = []
    if not sprints:
        planned = [i for i, it in bl.items.items() if it.get("kind") == "sprint"]
        n = sum(1 for it in bl.items.values() if it.get("kind") != "sprint" and it.get("status") not in ("done", "dropped"))
        lines.append(f"backlog: no active sprint; {n} open item(s)"
                     + (", planned: " + ", ".join(bl.label(s) + (" (approved, not started)" if start_approved(bl.items[s])
                                                                 else "") for s in planned) if planned else "")
                     + " (python3 _tools/backlog.py tree)")
    for sid in sprints:
        need(bl, sid)
        items = bl.sprint_items(sid)
        done = sum(1 for i in items if bl.items[i].get("status") in ("done", "dropped"))
        reach, stuck, path, widths = horizon(bl, sid)
        starts = len(stuck.get(STARTS + sid, []))  # approved: they wait on backlog.py start, not on the operator
        waiting = sum(map(len, stuck.values())) - starts
        if a.hook:  # every session reads it: id and title, counts and the next id; horizon without --hook has the rest
            nxt = ready(bl, sid)
            lines.append(f"sprint {sid} “{clip(bl.items[sid].get('title', ''), HOOK_TITLE)}”: "
                         f"{done}/{len(items)} done, {len(reach)} reachable"
                         + (f", {starts} wait on backlog.py start" if starts else "")
                         + (f", {waiting} wait on the operator or a trigger" if waiting else "")
                         + (f", next {nxt[0]}" if nxt else ""))
            for c, ids in stuck.items():
                lines.append(f"  waiting on {clip(c, HOOK_CAUSE)}: " + ", ".join(ids[:5]))
            continue
        lines.append(f"sprint {bl.label(sid)} [{bl.items[sid].get('status')}]: goal {bl.items[sid].get('goal')}")
        lines.append(f"  {done}/{len(items)} done; {len(reach)} more reachable without the operator; "
                     + (f"{starts} wait on backlog.py start {sid}; " if starts else "")
                     + f"{waiting} wait on the operator or a trigger")
        nxt = ready(bl, sid)
        if nxt:
            lines.append(f"  next: {bl.label(nxt[0])}")
            if not a.hook:  # the SessionStart hook runs no pack
                lines += knowledge_lines(bl, nxt[0], indent="    ")
        if path:
            lines.append(f"  critical path ({len(path)} steps, parallel width per step {widths}): "
                         + " -> ".join(bl.label(i) for i in path))
        for c, ids in stuck.items():
            lines.append(f"  waiting on {c}")
            for i in ids[:5 if a.hook else 50]:
                lines.append(f"    {bl.label(i)}")
    text = withhold("\n".join(lines))
    if a.hook:
        print(hook_json(text))
    else:
        say(text)
    return 0


HOOK_MAX = 1000  # characters of the hook's whole stdout (its newline included), which every session in a clone reads
HOOK_TITLE = 48  # characters of a sprint title on a hook line
HOOK_CAUSE = 100  # characters of a waiting cause (a gate's question, a trigger) on a hook line


def clip(s, n):
    """s cut to n characters, its last one an ellipsis when cut."""
    return s if len(s) <= n else s[:n - 1] + "…"


def hook_json(text):
    """The SessionStart hook's JSON for text, under HOOK_MAX: its last lines give way, newest first, to one line
    naming how many were left out and the command that prints them, whatever the number of sprints."""
    def dump(t):
        return json.dumps({"systemMessage": t, "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": t + "\nGoals and critical paths: python3 _tools/backlog.py horizon. "
                                     "The backlog runbook is kb/_self/backlog.md."}}, ensure_ascii=False)
    lines, cut, out = text.split("\n"), 0, dump(text)
    while len(out) + 1 >= HOOK_MAX and lines:
        lines.pop()
        cut += 1
        out = dump("\n".join(lines + [f"(+{cut} more line(s): python3 _tools/backlog.py horizon)"]))
    return out


# The pipeline reader, the failure fingerprint and the red-main bug are the CI detector's (bl_intake.py); this
# facade passes its own `run`, which a test replaces, and keeps the names its callers use.
GITLAB_FINISHED = bl_intake.GITLAB_FINISHED
S1_JOBS = bl_intake.S1_JOBS
STATUS_REPRO = list(bl_intake.PIPELINE_REPRO)  # a red-main bug adds --job <its job>
MAIN_PIPELINES = bl_intake.MAIN_PIPELINES
LOG_PREFIX_RE = bl_intake.LOG_PREFIX_RE
failure_fingerprint = bl_intake.failure_fingerprint
names_pipeline = bl_intake.names_pipeline


def normalise_error_line(line):
    """`bl_intake.normalise_error_line` with this module's LOG_PREFIX_RE."""
    return bl_intake.normalise_error_line(line, LOG_PREFIX_RE)


def first_failure(log):
    """`bl_intake.first_failure` with this module's LOG_PREFIX_RE."""
    return bl_intake.first_failure(log, LOG_PREFIX_RE)


def bug_with_fingerprint(bl, fp):
    """The id of an open bug (not done or dropped) whose links carry `fingerprint <fp>`, or None."""
    for iid, it in sorted(bl.items.items()):
        if (it.get("kind") == "bug" and it.get("status") not in ("done", "dropped")
                and f"fingerprint {fp}" in it.get("links", [])):
            return iid
    return None


def add_pipeline(bl, iid, pid):
    """Add `pipeline <pid>` to the links of item `iid` (a bug that already carries its fingerprint) and save it."""
    it = bl.items[iid]
    marker = f"pipeline {pid}"
    if marker not in it.get("links", []):
        it["links"] = list(it.get("links", [])) + [marker]
        bl.save(it)


def latest_pipeline(root, job=None):
    """(pipeline, note): `bl_intake.latest_pipeline` read through this module's `run`."""
    return bl_intake.latest_pipeline(root, job, run)


def covered_by_revert(root, sha):
    """`bl_intake.covered_by_revert` read through this module's `run`."""
    return bl_intake.covered_by_revert(root, sha, run)


def red_bug(pid, sha, sev, jobs=(), url=None, extra="", fingerprint=None, job=None):
    """A red-main bug item (not saved): `bl_intake.pipeline_candidate` written as the item red-pipeline files."""
    return bl_intake.item_of(bl_intake.pipeline_candidate(pid, sha, sev, jobs, url, extra, fingerprint, job),
                             new_id("bug"))


def cmd_red_pipeline(bl, a):
    if not a.status:
        import kbpublic
        run(["git", "fetch", "-q", kbpublic.integration_remote(bl.root), "main"], cwd=bl.root)
    p, note = latest_pipeline(bl.root, getattr(a, "job", None))
    if p is None:
        say(f"red-pipeline: not checked: {note}")
        return 1 if a.status else 0
    unpassed = p.get("unverified") or []
    state = "red" if p["red"] else "unverified" if unpassed else "green"
    why = f": a gate job did not pass: {', '.join(unpassed)}" if state == "unverified" else ""
    if a.status:
        say(f"red-pipeline: {p['how']} pipeline {p['id']} of main is {state}{why} ({note})")
        return 0 if state == "green" else 1
    if not p["red"]:
        say(f"red-pipeline: {p['how']} pipeline {p['id']} of main is {state}{why}: nothing to file")
        return 0
    marker = f"pipeline {p['id']}"
    for iid, it in bl.items.items():
        if names_pipeline(it, marker):
            say(f"red-pipeline: {marker} already filed as {bl.label(iid)}")
            return 0
    if covered_by_revert(bl.root, p["sha"]) is not False:
        say(f"red-pipeline: {marker} is covered by an automatic revert (or its history is unreadable): nothing to file")
        return 0
    cand = bl_intake.pipeline_finding(p)  # the CI detector's candidate
    sev = cand.severity
    active = [i for i, it in bl.items.items() if it.get("kind") == "sprint" and it.get("status") == "active"]
    fp = p.get("fingerprint")
    it = bl_intake.item_of(cand, new_id("bug"))
    if sev == "S1" and len(active) == 1:
        it.update(sprint=active[0], status="todo")
    ok, code, _ = run_check(bl.root, it["repro"])
    if ok:
        say(f"red-pipeline: {marker} is green on a second read (repro exit {code}): nothing to file")
        return 0
    dup = bug_with_fingerprint(bl, fp) if fp else None
    if dup:
        add_pipeline(bl, dup, p["id"])
        say(f"red-pipeline: {marker} fails the same way (fingerprint {fp}): added to {bl.label(dup)}")
        return 0
    bl.save(it)
    say(f"red-pipeline: new bug {bl.label(it['id'])}")
    return 0


def cmd_intake(bl, a):
    if a.status is not None and not bl_intake.FP_RE.fullmatch(a.status):
        print(f"intake: {a.status!r} is not a fingerprint (12 hex characters)", file=sys.stderr)
        return 2
    if a.status is not None and a.file:
        print("intake: --status and --file do not go together", file=sys.stderr)
        return 2
    found, failures = bl_intake.collect(bl.root, network=a.network)
    for why in failures:
        print(withhold(f"intake: detector failed: {why}"), file=sys.stderr)
    if a.status is not None:
        hit = next((c for c in found if c.fp == a.status), None)
        if hit:
            say(f"intake: {a.status} is still reported by {hit.detector}: {bl_intake.one(hit.title)}")
            return 1
        if failures:
            say(f"intake: {a.status} is not reported, but a detector failed to run")
            return 1
        say(f"intake: {a.status} is no longer reported")
        return 0
    new = skipped = 0
    for c in found:
        dup = bl_intake.open_with_fingerprint(bl.items, c.fp) or bl_intake.named_by(bl.items, c)
        for ln in bl_intake.lines(c, bl.label(dup) if dup else None):
            say(ln)
        if dup:
            skipped += 1
            continue
        new += 1
        if a.file:
            it = bl_intake.item_of(c, new_id(c.kind))
            bl.save(it)
            say(f"  filed {bl.label(it['id'])}")
    say(f"intake: {len(found)} candidate(s), {new} new{' filed' if a.file else ''}, {skipped} skipped" if found
        else "intake: no candidates")
    return 1 if failures else 0


INTAKE_HOOK_BUDGET_S = 50  # intake --hook stops waiting for the detectors after this; the hook's own timeout is 60
INTAKE_HOOK_SLOW = {"drift"}  # intake --hook runs these after the other offline detectors: drift runs item checks


def hook_intake(bl, a, budget=None):
    """`intake --file --hook`, the async SessionStart form: runs the fast offline detectors first, then the slow ones
    (INTAKE_HOOK_SLOW, on what is left of the budget), then the network ones (only with `--network`), and stops
    waiting after `budget` seconds (default INTAKE_HOOK_BUDGET_S); what the detectors that finished by then found is
    filed, so a slow one costs only its own findings. It writes each new candidate as an uncommitted draft item as
    `--file` does, prints nothing, never commits or pushes, and returns 0 whatever happens."""
    budget = INTAKE_HOOK_BUDGET_S if budget is None else budget
    names = sorted(bl_intake.DETECTORS, key=lambda n: (n in bl_intake.NETWORK_DETECTORS, n in INTAKE_HOOK_SLOW, n))
    found = []  # candidates of the detectors that finished, in order

    def read():
        for name in names:
            if name in bl_intake.NETWORK_DETECTORS and not a.network:
                continue
            try:
                found.extend(bl_intake.collect(bl.root, only=name)[0])
            except Exception:  # noqa: BLE001 - a session starts whatever the detectors do
                pass

    t = threading.Thread(target=read, daemon=True)
    t.start()
    t.join(budget)
    if a.file:
        seen = set()
        for c in list(found):
            if c.fp in seen or bl_intake.open_with_fingerprint(bl.items, c.fp) or bl_intake.named_by(bl.items, c):
                continue
            seen.add(c.fp)
            bl.save(bl_intake.item_of(c, new_id(c.kind)))
    return 0


# `cost ID`: what the query log's work sidecars (kb/_querylog/work/<yyyy-mm>/<run-id>.jsonl, written by distill) hold
# for an item and its descendants: tokens per model, the counts of its own prompts (direct, the `main` of its lines)
# apart from those of the subagents routed to it (attributed, the `sub`), cache writes (cw) as a figure of their own.
# A sprint line (`item: SP-...`) is the sprint's, and a shared line (`items`: the ids its session claimed) is its
# session's, not an item's: its counts, `main` and `sub` together, are the `shared` figure of a report, counted once
# for every line that names any id in the report's scope, never once per item it names, and the session total is
# direct + attributed + shared (`cost_report`). Reads no command text, session or prompt id: the sidecar has none. An id with a line and no item file (deleted at sprint close)
# is resolved from the last version of its file in git history (`history_items`), so the totals of its ancestors and
# of its sprint, open or closed, include its lines.
COST_KEYS = ("requests", "in", "cw", "cw1h", "cr", "out")
# one entry per figure group a cost report prints: (report key, sidecar field, label); a later total adds an entry
COST_GROUPS = (("direct", "main", "direct (main)"), ("attributed", "sub", "attributed (sub)"))
COST_SHARED, COST_TOTAL = "shared", "session_total"  # the report's figures beside COST_GROUPS, never an item's own


def cost_add(total, models):
    """Add {model: counts} into `total`: all six counts, a missing one as 0."""
    for m, c in models.items():
        t = total.setdefault(m, dict.fromkeys(COST_KEYS, 0))
        for k in COST_KEYS:
            t[k] += c.get(k, 0)


def cost_models(w, field):
    """{model: counts} of a work line's `main`, or its `sub` summed over the agent groups."""
    maps = [w.get(field) or {}] if field == "main" else list((w.get(field) or {}).values())
    out = {}
    for models in maps:
        cost_add(out, models)
    return out


def cost_lines(root, ids, rework=False):
    """([line], [skipped run id]): the lines of the work sidecars under root/kb/_querylog that name one of `ids`
    (every line when `ids` is None), oldest run first: an item line {run, item, prompts, <report key>: {model:
    counts}}, and a shared line {run, items, prompts, shared: {model: counts}} (its `main` and `sub` together) that
    names one of `ids` among its `items`; a sidecar that breaks the store's work gates (`ql_store.work_line_problems`) is skipped whole and named, so a bad
    file never skews a sum. With `rework`, an item line that has a `rework` block also has `rework`: {prompts,
    <report key>: {model: counts}}, a part of the line's own figures; without it no line has the key."""
    import ql_store
    out, skipped = [], []
    for p in ql_store.work_files(Path(root) / "kb" / "_querylog"):
        try:
            objs = ql_store.load_run(p)
        except (OSError, ValueError):
            objs = []
        lines = [w for _, w in objs[1:]]
        if not objs or any(ql_store.work_line_problems(w, p.stem) for w in lines):
            skipped.append(p.stem)
            continue
        for w in lines:
            if "item" in w and (ids is None or w["item"] in ids):  # a shared line has `items`, no `item`
                row = {"run": p.stem, "item": w["item"], "prompts": w["prompts"],
                       **{key: cost_models(w, field) for key, field, _ in COST_GROUPS}}
                if rework and "rework" in w:
                    row["rework"] = {"prompts": w["rework"]["prompts"],
                                     **{key: cost_models(w["rework"], field) for key, field, _ in COST_GROUPS}}
                out.append(row)
            elif "items" in w and (ids is None or ids.intersection(w["items"])):
                both = {}
                for _, field, _ in COST_GROUPS:
                    cost_add(both, cost_models(w, field))
                out.append({"run": p.stem, "items": w["items"], "prompts": w["prompts"], COST_SHARED: both})
    return out, skipped


def cost_scope(bl, iid):
    """The ids whose lines an item's cost sums: it and its descendants, and for a sprint also the items in it."""
    ids = {iid, *bl.descendants(iid)}
    if bl.items[iid].get("kind") == "sprint":
        ids |= set(bl.sprint_items(iid))
    return ids


HISTORY_CHUNK = 100  # item files named in one `git log`, so the command line stays short on every OS
HISTORY_TIMEOUT_S = 60


def history_parse(text):
    """{id: item JSON} from the patch text of `git log -p --diff-filter=D` over item files, newest deletion first: the
    removed lines of each deleted file, the first (newest) deletion of an id kept; a version that is not a JSON
    object is left out."""
    body, cur, hunk = {}, None, False
    for ln in text.splitlines():
        if ln.startswith("diff --git "):
            m = re.search(r"/([^/ ]+)\.json$", ln)
            cur = m.group(1) if m and m.group(1) not in body else None
            hunk = False
            if cur:
                body[cur] = []
        elif cur and ln.startswith("@@"):
            hunk = True
        elif cur and hunk and ln.startswith("-"):
            body[cur].append(ln[1:])
    out = {}
    for iid, rows in body.items():
        try:
            it = json.loads("\n".join(rows))
        except ValueError:
            continue
        if isinstance(it, dict):
            out[iid] = it
    return out


def history_items(root, ids):
    """{id: the last version of its item file} for the ids whose file git history shows deleted: one `git log --all`
    per `HISTORY_CHUNK` ids, run in `root` (a worktree shares its history). An id with no deletion in the history
    this clone holds (never committed, or a shallow clone cut it) is absent; git missing, failing or timing out
    leaves the chunk's ids absent, never an error."""
    found = {}
    ids = sorted({i for i in ids if ID_RE.fullmatch(i)})
    for n in range(0, len(ids), HISTORY_CHUNK):
        paths = [f"{REL_DIR}/{i}.json" for i in ids[n:n + HISTORY_CHUNK]]
        argv = ["git", "--literal-pathspecs", "-C", str(root), "log", "--all", "--diff-filter=D", "--no-renames",
                "--no-ext-diff", "--no-textconv", "--format=", "-p", "--", *paths]
        try:
            p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=HISTORY_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode == 0:
            found.update(history_parse(p.stdout))
    return found


def cost_view(bl, ids):
    """(view, {id: item} restored from history, [id asked of history and not found]): a copy of `bl` whose items also
    hold each of `ids` that has no item file (and, in turn, the parent of each such item that has none), so the
    parent chain and the sprint of an item deleted at sprint close resolve. An id is asked of git once per run."""
    view = copy.copy(bl)
    view.items = dict(bl.items)
    restored, asked = {}, set()
    want = {i for i in ids if i not in view.items}
    while want:
        asked |= want
        got = history_items(bl.root, want)
        restored.update(got)
        view.items.update(got)
        want = {it["parent"] for it in got.values() if isinstance(it.get("parent"), str)} - asked - set(view.items)
    return view, restored, sorted(asked - set(restored))


def cost_is_research(view, iid):
    """True for a research item (backlog.md, Sprints): a story, task or subtask whose touches, its descendants' too,
    are all kb content (`research_touches`)."""
    return view.items[iid].get("kind") in RESEARCH_KINDS and research_touches(scope(view, iid))


def cost_sum(lines):
    """{runs, prompts, <report key>: {model: counts}, by_item, items} of item lines."""
    out = {"runs": len({w["run"] for w in lines}), "prompts": sum(w["prompts"] for w in lines),
           **{key: {} for key, _, _ in COST_GROUPS}, "by_item": {}}
    for w in lines:
        one = out["by_item"].setdefault(w["item"], {"prompts": 0, **{key: {} for key, _, _ in COST_GROUPS}})
        one["prompts"] += w["prompts"]
        for key, _, _ in COST_GROUPS:
            cost_add(out[key], w[key])
            cost_add(one[key], w[key])
    out["items"] = sorted(out["by_item"])
    return out


def cost_take(total, models):
    """Subtract {model: counts} from `total` (the counterpart of cost_add): a part of what `total` holds."""
    for m, c in models.items():
        t = total.setdefault(m, dict.fromkeys(COST_KEYS, 0))
        for k in COST_KEYS:
            t[k] -= c.get(k, 0)
        if not any(t.values()):  # a model all of whose counts were the part's has no row left
            del total[m]


def cost_part():
    """An empty figure set of the work/rework split: prompts and each report key's {model: counts}."""
    return {"prompts": 0, **{key: {} for key, _, _ in COST_GROUPS}}


def cost_part_add(into, part, sign=1):
    """Add (or, with sign -1, take) `part`'s prompts and figures into `into`."""
    into["prompts"] += sign * part["prompts"]
    for key, _, _ in COST_GROUPS:
        (cost_add if sign > 0 else cost_take)(into[key], part[key])


def cost_split(lines):
    """The work/rework split of item lines (cost_lines with `rework`): {items, work, rework, by_item}. `rework` sums the
    lines' rework blocks and `work` is what is left of their figures (the prompts and counts before an item's first
    refused done, and all of an item with none), each {prompts, <report key>: {model: counts}}; `items` are the ids
    with a rework block, sorted, and `by_item` holds, for those only, the item's `work` and `rework` the same way."""
    whole, rw, per, has = cost_part(), cost_part(), {}, set()
    for w in lines:
        cost_part_add(whole, {"prompts": w["prompts"], **{key: w[key] for key, _, _ in COST_GROUPS}})
        one = per.setdefault(w["item"], {"all": cost_part(), "rework": cost_part()})
        cost_part_add(one["all"], {"prompts": w["prompts"], **{key: w[key] for key, _, _ in COST_GROUPS}})
        if "rework" in w:
            has.add(w["item"])
            cost_part_add(rw, w["rework"])
            cost_part_add(one["rework"], w["rework"])
    work = cost_part()
    cost_part_add(work, whole)
    cost_part_add(work, rw, -1)
    out = {"items": sorted(has), "work": work, "rework": rw, "by_item": {}}
    for i in out["items"]:
        part = cost_part()
        cost_part_add(part, per[i]["all"])
        cost_part_add(part, per[i]["rework"], -1)
        out["by_item"][i] = {"work": part, "rework": per[i]["rework"]}
    return out


def cost_report(bl, iid, rework=False):
    """The report of `cost ID`: {id, items, runs, prompts, <report key>: {model: counts}, shared, session_total,
    shared_prompts, by_item, run_lines, shared_lines, skipped, restored, unresolved, view}. `shared` sums the shared
    lines that name any id in the scope, each line once however many of its items are in it (and so once for an
    epic or a sprint), and `session_total` is direct + attributed + shared; `by_item` and `run_lines` hold item
    lines only, so a shared line is in no item's own row. `restored` are the ids in the sum whose item file is gone, read from git history;
    `unresolved` the ids with a line (or the parents of those) that have no file and no history, left out of every
    sum; `view` the backlog with the restored items, for labels. Raises KeyError for an id with neither a file nor
    a history. A sprint's report also has `research` (the lines of its research items, `cost_is_research`: {items,
    runs, prompts, direct, attributed, total, by_item}), kept out of `items`, `runs`, `prompts`, `direct`,
    `attributed` and `session_total`, which are the item work, and `overhead` (`cost_overhead`), in no figure of
    either; `run_lines` keeps every item line. With `rework`, the report also has `rework_split` (cost_split) of the
    item work lines, research left out as in the figures above; without it, no line and no key of the report
    differs from a report that never heard of rework."""
    all_lines, skipped = cost_lines(bl.root, None, rework=True) if rework else cost_lines(bl.root, None)
    named = {i for w in all_lines for i in (w["items"] if "items" in w else [w["item"]])}
    view, restored, unresolved = cost_view(bl, named | {iid})
    if iid not in view.items:
        raise KeyError(iid)
    keep = cost_scope(view, iid)
    lines = [w for w in all_lines if w.get("item") in keep]
    shared = [w for w in all_lines if keep.intersection(w.get("items", ()))]  # each line once, however many items
    sprint = view.items[iid].get("kind") == "sprint"
    research = {w["item"] for w in lines if sprint and cost_is_research(view, w["item"])}
    work = cost_sum([w for w in lines if w["item"] not in research])
    rep = {"id": iid, "runs": work["runs"], "prompts": work["prompts"],
           **{key: work[key] for key, _, _ in COST_GROUPS}, COST_SHARED: {}, COST_TOTAL: {},
           "shared_prompts": sum(w["prompts"] for w in shared), "by_item": work["by_item"], "run_lines": lines,
           "shared_lines": shared, "skipped": skipped, "unresolved": unresolved, "view": view}
    for w in shared:
        cost_add(rep[COST_SHARED], w[COST_SHARED])
    for key in (*(g[0] for g in COST_GROUPS), COST_SHARED):
        cost_add(rep[COST_TOTAL], rep[key])
    rep["items"] = work["items"]
    if rework:
        rep["rework_split"] = cost_split([w for w in lines if w["item"] not in research])
    rep["restored"] = sorted(({w["item"] for w in lines} | {iid}) & set(restored))
    if sprint:
        res = cost_sum([w for w in lines if w["item"] in research])
        res["total"] = {}
        for key, _, _ in COST_GROUPS:
            cost_add(res["total"], res[key])
        rep["research"] = res
        rep["overhead"] = cost_overhead(bl.root, iid)
    return rep


# `cost SP`, overhead: the `overhead` lines of the work sidecars (usage.md) are the kb's own background runs, in
# no item's or sprint's figure. A sprint's window runs from its start commit to its close commit: the oldest commit
# that adds `"status": "active"` to the sprint's item file (`start`), to the newest commit that deletes the file
# (`close`; none while the file exists: the window is open, with no upper bound). A run belongs to it when the time
# in its run id (UTC) is at or after the start and at or before the close. Git decides, as in `history_items`: a
# shallow clone, no git or no start commit leaves the overhead unresolved, never guessed.
GIT_TIMEOUT_S = 30


def git_times(root, *args):
    """[epoch seconds] of the commits `git log --all` lists for `args` (`%ct` of each), or None when git fails."""
    argv = ["git", "--literal-pathspecs", "-C", str(root), "log", "--all", "--format=%ct", *args]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    return [int(x) for x in p.stdout.split()] if p.returncode == 0 else None


def sprint_window(root, sid):
    """(start, end, reason): the sprint's window in epoch seconds (`end` None while the sprint is open), or
    (None, None, why) when git history cannot say."""
    try:
        shallow = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None, None, "git is unavailable"
    if shallow.returncode != 0:
        return None, None, "git history is unavailable"
    if shallow.stdout.strip() == "true":
        return None, None, "shallow clone: the sprint's start commit may be cut from history"
    path = f"{REL_DIR}/{sid}.json"
    starts = git_times(root, "--diff-filter=AM", "-S", '"status": "active"', "--", path)
    if not starts:
        return None, None, "no commit in history sets the sprint active"
    if (Path(root) / path).is_file():
        return min(starts), None, None
    closes = git_times(root, "--diff-filter=D", "--", path)
    if not closes:
        return None, None, "the sprint's file is gone and no commit in history deletes it"
    return min(starts), max(closes), None


def cost_overhead(root, sid):
    """The overhead of sprint `sid`: {resolved, reason, start, end, runs, calls, kinds: {kind: {calls, main}}, total}
    (`start` and `end` UTC `YYYY-MM-DDThh:mm:ssZ`, `end` None while open): the overhead lines of the work sidecars of the runs
    inside the sprint's window, summed apart from every item. Unresolved (`resolved` False, a `reason`, no figures)
    when the window is unknown (`sprint_window`). A sidecar that breaks the store's work gates is left out, as
    `cost_lines` does."""
    import datetime
    import ql_store
    start, end, reason = sprint_window(root, sid)
    def iso(t):
        return None if t is None else datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = {"resolved": reason is None, "reason": reason, "start": iso(start), "end": iso(end)}
    if reason:
        return out
    out.update(runs=0, calls=0, kinds={}, total={})
    for p in ql_store.work_files(Path(root) / "kb" / "_querylog"):
        if not ql_store.RUN_ID.fullmatch(p.stem):
            continue
        when = datetime.datetime.strptime(p.stem[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)
        if when.timestamp() < start or (end is not None and when.timestamp() > end):
            continue
        try:
            objs = ql_store.load_run(p)
        except (OSError, ValueError):
            continue
        lines = [w for _, w in objs[1:]]
        if not objs or any(ql_store.work_line_problems(w, p.stem) for w in lines):
            continue
        mine = [w for w in lines if "overhead" in w]
        out["runs"] += bool(mine)
        for w in mine:
            one = out["kinds"].setdefault(w["overhead"], {"calls": 0, "main": {}})
            one["calls"] += w["calls"]
            out["calls"] += w["calls"]
            cost_add(one["main"], w["main"])
            cost_add(out["total"], w["main"])
    return out


# `cost --research`: the items that did research against the query log's gap findings, each with its tokens and the gap
# findings closed by commits that carry its `KB-Work` trailer. An item is listed when its `research` field is true (a
# field only a later item adds; until then none is) or one of its `links` names a gap finding of the committed store
# (`F-<12 hex>` with kind `gap` in `kb/_querylog/findings`). Its tokens are its own lines' direct + attributed counts
# (`cost_lines`, no descendant, no shared line), the sum of `in`, `cw`, `cr` and `out` over the models (`TOKEN_KEYS`:
# `requests` is a count of calls, no tokens). A gap finding is closed by a commit when the commit's version of a
# root's `_gaps.md` has a settling note (`ql_research.SETTLED`: Resolved or Superseded, dated) under the entry that
# names the finding and its first parent's version has none (or has no entry or no file): the commit that settles the
# entry, the one `/kb-research` writes, never the query log's own record, which has no `KB-Work` trailer. Tokens per
# closed gap is the item's tokens divided by the count of its closed gaps, integer division (floor); `n/a` when it
# closed none, and unresolved, no figure, when git cannot say (a shallow clone, no git, a failing git).
TOKEN_KEYS = ("in", "cw", "cr", "out")
GAP_ID_RE = re.compile(r"\bF-[0-9a-f]{12}\b")
GAPS_PATHSPEC = ":(glob)kb/*/_gaps.md"
WORK_TRAILER = "KB-Work"


def cost_tokens(models):
    """The tokens of {model: counts}: `in` + `cw` + `cr` + `out` summed over the models."""
    return sum(c.get(k, 0) for c in models.values() for k in TOKEN_KEYS)


def gap_links(it, kinds):
    """The gap findings (id in `kinds` with kind `gap`) an item's `links` name, sorted."""
    ids = {m for x in it.get("links", []) if isinstance(x, str) for m in GAP_ID_RE.findall(x)}
    return sorted(i for i in ids if kinds.get(i) == "gap")


def gaps_settled(text):
    """The ids of the finding named by the _gaps.md entries (top-level bullets, with their indented lines) of `text`
    that carry a settling dated note, the rule of `ql_research.settled`: an id on the bullet's own lines, never one
    a note line mentions."""
    import ql_research
    lines, out, i = text.split("\n"), set(), 0
    while i < len(lines):
        if not lines[i].startswith("- "):
            i += 1
            continue
        end = i + 1
        while end < len(lines) and lines[end][:1] in (" ", "\t") and lines[end].strip():
            end += 1
        notes = [ql_research.NOTE.match(ln) for ln in lines[i + 1:end]]
        if any(m and m.group(1) in ql_research.SETTLED for m in notes):
            out.update(m for ln, n in zip(lines[i:end], [None, *notes]) if not n for m in GAP_ID_RE.findall(ln))
        i = end
    return out


def git_text(root, *args, timeout=GIT_TIMEOUT_S):
    """The stdout of `git -C root ARGS`, or None when git is missing, times out or fails."""
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def closed_gaps_by_item(root, wanted):
    """({item id: {gap finding id closed by a commit whose KB-Work trailer names it}}, reason): `reason` is None when
    git answered, else why it could not (a shallow clone, git missing or failing) and the map is None, never a guess.
    One `git log --all --no-merges` over the `_gaps.md` ledgers lists the commits that touch one with their
    trailers; each commit that names one of `wanted` is read at itself and at its first parent."""
    shallow = git_text(root, "rev-parse", "--is-shallow-repository")
    if shallow is None:
        return None, "git history is unavailable"
    if shallow.strip() == "true":
        return None, "shallow clone: the commits that closed a gap may be cut from history"
    log = git_text(root, "log", "--all", "--no-merges", "--no-renames", "--diff-filter=AM", "--name-only",
                   f"--format=%x1e%H%x1f%P%x1f%(trailers:key={WORK_TRAILER},valueonly)%x1f", "--", GAPS_PATHSPEC,
                   timeout=HISTORY_TIMEOUT_S)
    if log is None:
        return None, "git log failed"
    out = {i: set() for i in wanted}
    for rec in log.split("\x1e")[1:]:
        sha, parents, trailer, names = rec.split("\x1f", 3)
        ids = wanted.intersection(re.split(r"[,\s]+", trailer.strip()))
        if not ids:
            continue
        for path in sorted({n for n in names.split("\n") if n.strip()}):
            after = git_text(root, "show", f"{sha}:{path}")
            first = parents.split()[0] if parents.split() else None
            held = git_text(root, "ls-tree", "--name-only", first, "--", path) if first else ""  # "" when absent
            before = git_text(root, "show", f"{first}:{path}") if held and held.strip() else ""
            if after is None or before is None or held is None:
                return None, "git could not read a commit's ledger"
            closed = gaps_settled(after) - gaps_settled(before)
            for i in ids:
                out[i] |= closed
    return out, None


def cost_research(bl):
    """The report of `cost --research`: {items: [{id, title, selected_by, runs, prompts, direct, attributed, tokens,
    direct_tokens, attributed_tokens, closed_gaps, gap_status, tokens_per_gap}], git: {resolved, reason}, skipped,
    unresolved, view}, the items by tokens descending then id. `selected_by` holds `research` and `links`; `gap_status`
    is `closed` (`closed_gaps` sorted, `tokens_per_gap` their floor division), `none` (none closed: no ratio) or
    `unresolved` (git cannot say: `closed_gaps` and `tokens_per_gap` are None). An item with no work line has 0
    tokens. Items restored from git history (deleted at sprint close) count when a work line names them."""
    import ql_store
    all_lines, skipped = cost_lines(bl.root, None)
    named = {w["item"] for w in all_lines if "item" in w}
    view, _, unresolved = cost_view(bl, named)
    kinds = {i: r.get("kind") for i, r in ql_store.finding_states(Path(bl.root) / "kb" / "_querylog").items()}
    chosen = {}
    for iid, it in view.items.items():
        why = (["research"] if it.get("research") is True else []) + (["links"] if gap_links(it, kinds) else [])
        if why:
            chosen[iid] = why
    closed, reason = closed_gaps_by_item(bl.root, set(chosen)) if chosen else ({}, None)
    rows = []
    for iid, why in chosen.items():
        mine = [w for w in all_lines if w.get("item") == iid]
        parts = {key: {} for key, _, _ in COST_GROUPS}
        for w in mine:
            for key in parts:
                cost_add(parts[key], w[key])
        gaps = None if closed is None else sorted(closed[iid])
        tokens = sum(cost_tokens(m) for m in parts.values())
        rows.append({"id": iid, "title": view.items[iid].get("title"), "selected_by": why,
                     "runs": len({w["run"] for w in mine}), "prompts": sum(w["prompts"] for w in mine), **parts,
                     "tokens": tokens, "direct_tokens": cost_tokens(parts["direct"]),
                     "attributed_tokens": cost_tokens(parts["attributed"]), "closed_gaps": gaps,
                     "gap_status": "unresolved" if gaps is None else "closed" if gaps else "none",
                     "tokens_per_gap": tokens // len(gaps) if gaps else None})
    rows.sort(key=lambda r: (-r["tokens"], r["id"]))
    return {"items": rows, "git": {"resolved": reason is None, "reason": reason}, "skipped": skipped,
            "unresolved": unresolved, "view": view}


def cmd_cost_research(bl, a):
    rep = cost_research(bl)
    if rep["skipped"]:
        print(f"cost: skipped sidecars that break the store's gates: {', '.join(rep['skipped'])}", file=sys.stderr)
    if rep["unresolved"]:
        print(f"cost: no item file and no git history for {', '.join(rep['unresolved'])}: left out", file=sys.stderr)
    if a.format == "json":
        say(json.dumps({"research_items": rep["items"], "git": rep["git"], "skipped": rep["skipped"],
                        "unresolved": rep["unresolved"], "token_keys": list(TOKEN_KEYS)}, sort_keys=True, indent=2))
        return 0
    git = rep["git"]
    say(f"cost --research: {len(rep['items'])} item(s) with research true or a link to a gap finding; tokens = "
        f"{' + '.join(TOKEN_KEYS)} of direct + attributed (the item's own lines)")
    say("closed gaps: " + ("resolved" if git["resolved"] else f"unresolved ({git['reason']})"))
    for r in rep["items"]:
        gaps, per = r["closed_gaps"], r["tokens_per_gap"]
        shown = ("unresolved" if gaps is None else f"{len(gaps)} closed gap(s): {', '.join(gaps)}" if gaps
                 else "no closed gap")
        say(f"  {rep['view'].label(r['id'])}: {r['tokens']} tokens (direct {r['direct_tokens']}, attributed "
            f"{r['attributed_tokens']}), {shown}; tokens per closed gap: "
            + ("unresolved" if gaps is None else "n/a" if per is None else str(per)))
    return 0


def cost_row(name, c):
    return f"{name}  requests {c['requests']}  in {c['in']}  cr {c['cr']}  out {c['out']} | cw {c['cw']}"


def cost_figures(models, indent):
    """The rows of one figure group: a row per model, then the sum of the models (zeros when there are none)."""
    allm = {k: sum(c[k] for c in models.values()) for k in COST_KEYS}
    return [indent + cost_row(m, models[m]) for m in sorted(models)] + [indent + cost_row("all models", allm)]


def cost_block(part, indent):
    """The figure groups of `part`; a report (it has COST_SHARED) also prints shared and the session total."""
    out = []
    groups = [(key, label) for key, _, label in COST_GROUPS]
    if COST_SHARED in part:
        groups += [(COST_SHARED, f"shared (outside any window, {part['shared_prompts']} prompt(s))"),
                   (COST_TOTAL, "session total (direct + attributed + shared)")]
    for key, label in groups:
        out.append(f"{indent}{label}:")
        out += cost_figures(part[key], indent + "  ")
    return out


def cost_apart(rep, view):
    """The lines of a sprint's research and overhead, apart from the item work above them (none for any other id)."""
    out = []
    if "research" in rep:
        res = rep["research"]
        out.append(f"research ({len(res['items'])} item(s), {res['prompts']} prompt(s); in none of the figures above"
                   + (": " + ", ".join(view.label(i) for i in res["items"]) if res["items"] else "") + "):")
        for key, _, label in COST_GROUPS:
            out.append(f"  {label}:")
            out += cost_figures(res[key], "    ")
        out.append("  total (direct + attributed):")
        out += cost_figures(res["total"], "    ")
    if "overhead" in rep:
        ov = rep["overhead"]
        if not ov["resolved"]:
            out.append(f"system overhead: unresolved ({ov['reason']})")
        else:
            out.append(f"system overhead ({ov['start']} to {ov['end'] or 'now'}, {ov['runs']} run(s), "
                       f"{ov['calls']} call(s); in no item or sprint figure):")
            for kind in sorted(ov["kinds"]):
                out.append(f"  {kind} ({ov['kinds'][kind]['calls']} call(s)):")
                out += cost_figures(ov["kinds"][kind]["main"], "    ")
            out.append("  all kinds:")
            out += cost_figures(ov["total"], "    ")
    return out


def cost_part_tokens(part):
    """The tokens of a work/rework part: `in` + `cw` + `cr` + `out` of its direct and attributed figures."""
    return sum(cost_tokens(part[key]) for key, _, _ in COST_GROUPS)


def cost_split_json(split):
    """The `rework_split` of the json report: the split's parts, each with its `tokens` besides its prompts and
    figures, and `token_keys`."""
    def part(p):
        return {**p, "tokens": cost_part_tokens(p)}
    return {"items": split["items"], "work": part(split["work"]), "rework": part(split["rework"]),
            "by_item": {i: {"work": part(one["work"]), "rework": part(one["rework"])}
                        for i, one in split["by_item"].items()}, "token_keys": list(TOKEN_KEYS)}


def cost_split_text(split, view):
    """The lines of `cost --rework`: the work and rework figures of the report's item work, then the items that
    have rework with their tokens of each (none, when no item has)."""
    out = [f"work and rework (the counts before an item's first refused done and from it; {len(split['items'])} "
           f"item(s) with rework; tokens = {' + '.join(TOKEN_KEYS)}):"]
    for name, key in (("work", "work"), ("rework", "rework")):
        part = split[key]
        out.append(f"  {name} ({part['prompts']} prompt(s), {cost_part_tokens(part)} tokens):")
        for gkey, _, label in COST_GROUPS:
            out.append(f"    {label}:")
            out += cost_figures(part[gkey], "      ")
    if not split["items"]:
        out.append("  no item has rework")
    for i in split["items"]:
        one = split["by_item"][i]
        out.append(f"  {view.label(i)}: work {one['work']['prompts']} prompt(s), {cost_part_tokens(one['work'])} tokens; "
                   f"rework {one['rework']['prompts']} prompt(s), {cost_part_tokens(one['rework'])} tokens")
    return out


def cmd_cost(bl, a):
    if a.research:
        if a.id or a.runs or a.rework:
            raise Rejected("cost --research lists every research item: it takes no ID, no --runs and no --rework")
        return cmd_cost_research(bl, a)
    if not a.id:
        raise Rejected("cost needs an ID, or --research")
    rep = cost_report(bl, a.id, rework=True) if a.rework else cost_report(bl, a.id)
    iid, view = rep["id"], rep["view"]
    if rep["skipped"]:
        print(f"cost: skipped sidecars that break the store's gates: {', '.join(rep['skipped'])}", file=sys.stderr)
    if rep["unresolved"]:
        print(f"cost: no item file and no git history for {', '.join(rep['unresolved'])}: left out of every sum",
              file=sys.stderr)
    if a.format == "json":
        out = {k: rep[k] for k in ("id", "items", "runs", "prompts", "shared_prompts", "by_item", "skipped", "restored",
                                   "unresolved", COST_SHARED, COST_TOTAL, *(g[0] for g in COST_GROUPS))}
        out.update({k: rep[k] for k in ("research", "overhead") if k in rep})  # a sprint's report only
        if a.rework:
            out["rework_split"] = cost_split_json(rep["rework_split"])
        if a.runs:
            out["run_lines"] = rep["run_lines"]
            out["shared_lines"] = rep["shared_lines"]
        say(json.dumps(out, sort_keys=True, indent=2))
        return 0
    n = len(rep["items"])
    say(f"cost {view.label(iid)}: {rep['runs']} run(s), {n} item(s) with work lines, {rep['prompts']} prompt(s)"
        " (the item and its descendants)")
    if rep["restored"]:
        say("from git history (item file deleted): " + ", ".join(view.label(i) for i in rep["restored"]))
    for x in cost_block(rep, ""):
        say(x)
    for x in cost_apart(rep, view):
        say(x)
    if a.rework:
        for x in cost_split_text(rep["rework_split"], view):
            say(x)
    if rep["items"] not in ([], [iid]):
        say("by item:")
        for i in rep["items"]:
            say(f"  {view.label(i)}: {rep['by_item'][i]['prompts']} prompt(s)")
            for x in cost_block(rep["by_item"][i], "    "):
                say(x)
    if a.runs:
        say("shared lines (one per session):")
        for w in rep["shared_lines"]:
            say(f"  {w['run']}  {', '.join(view.label(i) for i in w['items'])}: {w['prompts']} prompt(s)")
            for x in cost_figures(w[COST_SHARED], "    "):
                say(x)
        say("runs:")
        for w in rep["run_lines"]:
            say(f"  {w['run']}  {view.label(w['item'])}: {w['prompts']} prompt(s)")
            for x in cost_block(w, "    "):
                say(x)
    return 0


def referrer_patterns(term, files):
    """The patterns that name term: a tracked file by its path (a .py also by its module name, word-bounded), any
    other term as a symbol, word-bounded."""
    if term in files:
        pats = [re.compile(re.escape(term))]
        if term.endswith(".py"):
            pats.append(re.compile(r"\b" + re.escape(Path(term).stem) + r"\b"))
        return pats
    return [re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])")]


def referrers_of(root, term, files):
    """(path, first line number, matching line count) of each tracked text file other than term itself that names it."""
    pats = referrer_patterns(term, files)
    out = []
    for f in files:
        path = Path(root) / f
        if f == term or not path.is_file() or path.stat().st_size > 4_000_000:
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


def args_similar(p):
    p.add_argument("title")
    p.add_argument("--goal")


def args_list(p):
    p.add_argument("--kind", choices=list(KINDS))
    p.add_argument("--status")
    p.add_argument("--sprint")


def args_tree(p):
    p.add_argument("id", nargs="?")
    p.add_argument("--sprint")
    p.add_argument("--open", action="store_true")


def args_find(p):
    p.add_argument("words", nargs="+")


def args_show(p):
    p.add_argument("id")


def args_next(p):
    p.add_argument("--sprint")
    p.add_argument("--any", action="store_true")
    p.add_argument("--all", action="store_true")


def args_held(p):
    p.add_argument("--overlaps", metavar="ID", help="only the claimed items whose touches overlap this item's")
    p.add_argument("--ref", help="read the claims from this git ref (origin/main after git fetch) instead of the files")


def args_claim(p):
    p.add_argument("id")
    p.add_argument("--by", required=True)


def args_release(p):
    p.add_argument("id")


def args_answer(p):
    p.add_argument("id")
    p.add_argument("gate")
    p.add_argument("--answer")
    p.add_argument("--by", choices=("operator", "agent"))
    p.add_argument("--provisional", action="store_true")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--record", action="store_true", help="with --answer TEXT --by operator: keep the answer as an active decision")


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


def args_done(p):
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")


def args_land(p):
    p.add_argument("id")
    p.add_argument("--branch", help="the local branch to land (default work/ID)")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own for the done --commit commit (repeatable)")


def args_drop(p):
    p.add_argument("id")
    p.add_argument("--why", required=True)


def args_start(p):
    p.add_argument("sprint")


def args_host_check(p):
    p.add_argument("sprint")


def args_close(p):
    p.add_argument("sprint")
    p.add_argument("--summary", action="store_true",
                   help="only print each item close would delete with its status and evidence commit (the close "
                        "commit's body); changes nothing")


def args_horizon(p):
    p.add_argument("--sprint")
    p.add_argument("--hook", action="store_true")


def args_goal(p):
    p.add_argument("id")


def args_referrers(p):
    p.add_argument("terms", nargs="+", help="a tracked file path or a symbol a task will move or delete")
    p.add_argument("--item", help="mark the files outside this item's scope (touches and its descendants')")


def args_cost(p):
    p.add_argument("id", nargs="?")
    p.add_argument("--runs", action="store_true", help="also list each run's line apart")
    p.add_argument("--rework", action="store_true",
                   help="also split the work from the rework after an item's first refused done")
    p.add_argument("--research", action="store_true",
                   help="instead of an ID: every research item's tokens against the gap findings its commits closed")
    p.add_argument("--format", choices=("text", "json"), default="text")


def args_red_pipeline(p):
    p.add_argument("--status", action="store_true")
    p.add_argument("--job", help="read the newest pipeline of main in which this job succeeded or failed on its own account (a red-main bug's repro)")
    p.add_argument("--hook", action="store_true")


def args_intake(p):
    p.add_argument("--file", action="store_true", help="write each new candidate as a draft item outside any sprint")
    p.add_argument("--status", metavar="FINGERPRINT",
                   help="exit 1 while a detector still reports this fingerprint (a filed bug's repro)")
    p.add_argument("--network", action="store_true",
                   help="also run the detectors that call the network (ci: the newest pipeline of main, as red-pipeline reads it)")
    p.add_argument("--hook", action="store_true",
                   help="the async SessionStart form: silent, bounded, exit 0 always; with --file it writes the drafts uncommitted")


bl_cli.register("new", cmd_new, args_new)
bl_cli.register("similar", cmd_similar, args_similar)
bl_cli.register("check", cmd_check)
bl_cli.register("fmt", cmd_fmt)
bl_cli.register("selectors", cmd_selectors)
bl_cli.register("list", cmd_list, args_list)
bl_cli.register("tree", cmd_tree, args_tree)
bl_cli.register("find", cmd_find, args_find)
bl_cli.register("show", cmd_show, args_show)
bl_cli.register("next", cmd_next, args_next)
bl_cli.register("held", cmd_held, args_held)
bl_cli.register("claim", cmd_claim, args_claim)
bl_cli.register("release", cmd_release, args_release)
bl_cli.register("answer", cmd_answer, args_answer)
bl_cli.register("set", cmd_set, args_set)
bl_cli.register("move", cmd_move, args_move)
bl_cli.register("reopen", cmd_reopen, args_reopen)
bl_cli.register("gate", cmd_gate, args_gate)
bl_cli.register("fire", cmd_fire, args_fire)
bl_cli.register("done", cmd_done, args_done)
bl_cli.register("land", cmd_land, args_land)
bl_cli.register("drop", cmd_drop, args_drop)
bl_cli.register("start", cmd_start, args_start)
bl_cli.register("host-check", cmd_host_check, args_host_check)
bl_cli.register("close", cmd_close, args_close)
bl_cli.register("horizon", cmd_horizon, args_horizon)
bl_cli.register("goal", cmd_goal, args_goal)
bl_cli.register("referrers", cmd_referrers, args_referrers)
bl_cli.register("cost", cmd_cost, args_cost)
bl_cli.register("red-pipeline", cmd_red_pipeline, args_red_pipeline)
bl_cli.register("intake", cmd_intake, args_intake)


def main(argv=None):
    ap = bl_cli.build_parser(__doc__.split("\n\n")[0], str(ROOT))
    a = ap.parse_args(argv)
    OUTPUT_ROOT[0] = a.root
    for s in (sys.stdout, sys.stderr):  # refusals go to stderr; on Windows a pipe defaults to the ANSI code page
        s.reconfigure(encoding="utf-8")
    if a.cmd == "red-pipeline" and a.hook:  # async SessionStart: files a bug at most, prints nothing, never fails
        try:
            cmd_red_pipeline(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            pass
        return 0
    if a.cmd == "intake" and a.hook:  # async SessionStart: uncommitted drafts at most, prints nothing, never fails
        try:
            return hook_intake(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            return 0
    if a.cmd == "horizon" and a.hook:  # the SessionStart event on stdin carries nothing the horizon needs
        try:
            return cmd_horizon(Backlog(a.root), a)
        except Exception:  # noqa: BLE001 - a session starts whatever happens here
            return 0
    bl = Backlog(a.root)
    try:
        if a.cmd in COMMITS + ("land",):  # before the command writes anything
            if a.trailer and not getattr(a, "commit", True):
                raise Refused("--trailer goes with --commit")
            why = next(filter(None, map(trailer_problem, a.trailer)), None)
            if why:
                raise Refused(why)
        return bl_cli.handler_of(a.cmd)(bl, a)
    except KeyError as e:
        print(withhold(f"no item {e.args[0]}"), file=sys.stderr)
        return 2
    except Rejected as e:
        print(withhold(str(e)), file=sys.stderr)
        return 2
    except Refused as e:
        print(withhold(str(e)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
