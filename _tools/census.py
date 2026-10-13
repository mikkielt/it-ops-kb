#!/usr/bin/env python3
"""Census: confirm that every source in _sources.csv is still current (stdlib only). /kb-census drives it.

  census.py check [--date D] [--out PATH] [--jobs N] [--source ID ...] [--factdiff LOG]   phases 0-1: one verdict per source
  census.py repin LOG [--date D] [--dry-run] [--commit]   phase 1: a pinned file whose facts are word for word at the newer commit is re-pinned
  census.py record LOG --from RESULTS.json | --id ID --outcome O [--note T]   phase 2: what reading decided
  census.py confirm LOG [--date D] [--dry-run]     phase 3: dates and evidence for the confirmed sources and articles
  census.py sample LOG [--changed 0.10] [--judged 0.10] [--ok 0.05] [--seed N] [--brief [--max-age DAYS]]   phase 4: the sources an independent check re-reads
  census.py summary LOG [--factdiff FLOG]          counts per bucket and outcome, the blocked, dns and connect hosts, and the size of phase 2's reading queue
  census.py baselines [--list]                     the live unpinned sources with no detection baseline, counted by host (exit 1 when any)
  census.py judge LOG [--factdiff FLOG] [--model M] [--batch-size N] [--dry-run]   phase 2: review items judged in batches by a no-tool model call
  census.py groups LOG [--factdiff FLOG]           phase 2: the rows to read split into owner groups, as JSON
  census.py brief LOG --group G [--part N] [--factdiff FLOG]   phase 2: a group's brief, filled in
  census.py dispatch LOG --group G [--part N] [--model M] [--max-turns N] [--max-budget-usd X] [--dry-run]   phase 2: a group's brief
                                                   part as a capped headless session, its result written for apply
  census.py apply LOG --group G --from RESULTS.json [--dry-run]   phase 2: a group's result, validated, then its bookkeeping
  census.py score LOG --from RESULTS.json ...      phase 2: results against the outcomes a census recorded in LOG, source by source
  census.py run [--date D] [--resume] [--dry-run]  phases 0-1 as one command: factdiff detect and apply, check, the index, the phase-1 commit, summary
  census.py finish LOG [--date D] [--dry-run]      phase 3 as one command: confirm, kbdecide sweep, the index, the confirmed-dates commit

census.py --root NAME <command> works on that root of this repository's kb/ (default public): its _sources.csv,
_fetch_state.csv, articles and _census/ log. The clone cache (_cache/census/repos) is shared: a repository at a
commit is the same for every root, and source ids never collide across roots (each root has its own prefix).

check (no judgment, network read-only) writes the verdict log LOG, by default _census/<D>.csv, one row per source:
  id,url,kind,repo,pin,path,retrieved_utc,http_status,bucket,evidence,proof,note,used_in,outcome,outcome_note
kind: raw-pin / raw-ref (a raw file at a commit / at a branch or tag), gh-pin / gh-ref (github.com blob or tree), release,
  gh-page, api-* (api.github.com), learn (learn.microsoft.com), live (anything else).
bucket:
  OK            nothing changed since retrieval: the pinned file is byte-identical at the branch tip (content compared,
                so a shallow clone's boundary commit is no change); a recorded release is still the newest of its own
                series (same tag shape, created later); a Learn page's source file in its public MicrosoftDocs repo
                (LEARN_MAP) has no commit since retrieval, or, without one, the page's `updated_at` meta is not after it; a live page's sitemap lastmod or page date is not after it
  CHANGED       the file or page changed since retrieval (evidence: commits or date)
  GONE          404/410, the file was deleted, the commit or tag vanished, or the repository of a pinned source answers
                404 (provider.repository_state: one request per repository; a private one answers alike)
  NEWER-VERSION a newer release of the pinned one exists and the cited file differs there
  NEEDS-READING nothing mechanical decides it: no date on the page, an HTTP error, the host is denied here
                (note `blocked`), the host did not resolve or accept a connection (note `dns` or `connect`: a fetch that
                fails with a name-resolution or connection error is tried once more after RETRY_PAUSE seconds, in the
                same run, and the note is set only when the second try fails too), or MicrosoftDocs/memdocs (archived:
                re-source to the live Learn page)
Git work uses bare blobless clones in _cache/census/repos/ (git over https). A pinned source's repository is asked first,
once, by the forge's own route (provider.repository): on GitHub the raw file of a pinned path, which is not the REST API,
and the API (at most GH_API_MAX requests a run) for a url with no file or to tell a missing ref from a missing repository;
on gitlab.com the projects API. One that answers 404 is GONE and is not cloned.
A github.com page that is a file of a repository (provider.github_page) is decided by its provider's signal, with the one
GET of the page that names a 404, a redirect (the repository moved) and the archived banner: a wiki page by the commits
of its file in the wiki's own repository (`<repo>.wiki`), a repository home by its README blob at the default branch, its
licence blob, a version-like release tag after retrieval and the archived banner, an issue or a discussion by the latest
timestamp of its timeline; a wiki's own git url by its newest commit. The page's About text, topics and counters are no
part of the signal. api.github.com urls and a page no signal fits (a releases list, a pull request) go to reading.
--factdiff LOG takes the verdicts of the census's first stage (factdiff.py detect, _census/factdiff-<date>.csv) for the
sources it covers: unchanged, or every fact found word for word, against a text no newer than retrieved_utc -> OK; gone or soft 404 with nothing moved -> GONE;
facts to review -> CHANGED, the evidence naming `factdiff.py review`. Pinned and errored sources are checked here, but a
pinned source whose repository answers 404 (verdict gone, signal `repository`) is GONE from the log.

repin (no judgment, no network beyond the clone's own fetch) takes each row of kind raw-pin or raw-ref (and release, whose
url names no file and so stays) in bucket CHANGED or NEWER-VERSION that has no outcome, and reads the file at the newer
commit (the one the verdict's evidence names) or release (note `newer=`) from the census clone, `git cat-file blob`. Each
fact citing the source is looked up by its anchor (`_anchors.csv`, the passage's hash): found word for word in that file,
or not. A fact that names the pinned tag (or a tag of the pinned commit) is about that version and counts as not found.
When every fact is found, `repin` adds the new row (`kbid.add_source`: the file at the newer tag, or at the newer commit's
sha; a url already there is kept), sets `superseded_by` on the old row, re-points the facts (`factdiff.repoint`, their
anchors and doc2query expansions follow, and the old id leaves the article's `sources:` when nothing else names it) and
records outcome `superseded` whose note holds the proof: old and new commit, the facts matched. --dry-run prints every
write and changes nothing; --commit commits it with a `KB-Verified` trailer, as `factdiff.py apply --commit` does. A
source with a fact not found stays in phase 2, and `summary`, `groups` and `brief` give its review items only the facts
not found (old passage from the clone at the old commit, new one at the newer); one with no located anchor stays
unchanged. A second run writes the same bytes: a row with an outcome is no candidate.

record fills outcome/outcome_note after phase 2 read a source in full:
  confirmed (the facts still hold), updated (facts rewritten, same source), superseded (a new row replaced it; the note
  names the new id), gone (facts marked [UNK], logged in _gaps.md), unconfirmed (could not be read; left as it was).
RESULTS.json: [{"id": "S123", "outcome": "confirmed", "note": "..."}, ...].

confirm (phase 3) treats as confirmed: bucket OK with no outcome, and outcome confirmed or updated. For each it sets
_sources.csv retrieved_utc to D and ends version_or_date with `confirmed D: <proof>` (replacing an earlier such suffix),
and sets checked_utc in _fetch_state.csv (fetch columns untouched: the census compared, it did not snapshot). Then
every article (front matter with sources:) whose listed sources were all confirmed, or added by the census (rows not
in LOG with retrieved_utc D), gets retrieved_utc D.
Superseded, gone, unconfirmed and unread sources keep their dates: a date is only moved by real confirmation.
Each confirmed unpinned source whose _fetch_state.csv row holds no detection baseline (ETag, Last-Modified, version id or
text hash: what factdiff.py detect compares its next fetch with) gets one from the document factdiff fetched and kept in
_cache/factdiff, when it is a 200 with text for the source's url and was fetched from the log's date to D: a text
fetched before the census or after its confirmation was compared with nothing, so it is no baseline. Nothing is fetched
here. The next `check --factdiff` then takes detect's `unchanged` verdict (a baseline no later than the source's
retrieved_utc) for a live page with no last-updated date, instead of bucket NEEDS-READING.

baselines prints how many live (not superseded) unpinned sources hold no detection baseline, and the count by host (the
QUEUE_HOSTS with most; --list: every host, each with its ids and urls); no network, no model; exit 1 when any, 0 when none.

sample (phase 4) prints a CSV of ids for the independent re-check: a fraction of the sources whose facts phase 2
changed (updated/superseded/gone, group `changed`), of the sources `judge` confirmed with no agent (outcome confirmed,
a note starting `N fact(s) judged supported by`, group `judged`, --judged, default the changed group's 0.10: a false
confirm of the judge is a stale fact dated current, so these are drawn at the rate of the changed ones) and of the
other confirmed ones (bucket OK or outcome confirmed, group `ok`), seeded, at least one each.
--brief prints instead the checker's brief for the same rows: for each sampled source its citing facts (a superseded
source: those of the row that replaced it), each with the passage its anchor names in the source's current text, from
the document cache of _cache/factdiff (--max-age days, default 7) or else a fetch, which it caches. A source whose every
fact has its anchor's passage word for word in that text (the proof `factdiff.py apply` dates a source on) is listed
under "Agreed by tool" with that proof (the facts, the url, the document's fetch time) and the checker never sees it; a
source with a fact whose passage is not there, a source whose page could not be read and a source no fact cites go under
"For the checker" with each fact, its passage (the anchor's, else the best window, marked) and the command that reads the
source. The counts `checked`, `agreed by tool` and `for the checker` head the lists, also for each group (the line
`by group`: the report states the `judged` group's agreement apart from `ok`, each source's group is in its head); the
checker's own agree and disagree counts complete the report. The checker is a context that did not do phase 2, and
changes nothing.

summary prints the hosts of the rows noted `blocked`, `dns` and `connect` apart, and the count of HTTP errors
(NEEDS-READING rows with a numeric status other than 200). It also prints the queue phase 2 must read, with no network and no model: the rows whose bucket is not OK, whose
note is not `blocked` and that have no outcome yet, the lines of the kb naming them (`rag.py src --cited`), and what a
model would read, in characters and in tokens (characters / 4, kb/_self/usage.md), by host: the fact diff review items'
passages (fact, old and new passage) of a row the fact diff log holds items for (FLOG; else the log its evidence names,
else _census/factdiff-<date>.csv beside LOG), and else the whole document held in _cache/factdiff, counted `not cached`
when the cache holds none (a linked worktree reads the clone's main worktree's cache).

judge (phase 2, before groups) sends the fact diff review items of the queue's rows, each a fact with its old and new
passage, in batches to one model call each: `claude -p --output-format json --json-schema` with no tools and
`--max-budget-usd` (STEP_MODELS['judge'] by default, factdiff.JUDGE_BATCH items or JUDGE_BATCH_CHARS characters a
call). A call gives supported, contradicted or not enough information per fact with the sentence of the new passage
that decides it; a `supported` whose sentence is not in the new passage is not believed. The verdicts are written to
_census/judge-<D>.csv beside LOG (one row per fact: source_id, fact, path, verdict, sentence, model, note; a fact
already there is not asked again, so a second run asks only for what a failed call left). A source whose every review
item is supported is recorded `confirmed` with no agent; `summary`, `groups` and `brief` then leave the supported items
out, so the rest go to phase 2's readers with only their undecided facts. Items with no new passage, and the rows of
a pinned file (`repin`'s items), are never sent. --dry-run prints the batch count and the estimated input and output
tokens and USD (queue block's passages, factdiff.JUDGE_PRICE) and asks nothing. The ops row `census.phase` (phase
`judge`) holds the verdict counts, `calls`, `failed`, the tokens of each kind and `cost-usd-micro`, the calls'
total_cost_usd summed in millionths of a dollar. Exit 1 when a call failed (its items stay unjudged), 2 for bad
arguments.

compare measures a model against a judging step's model on a labelled set built from the log's recorded outcomes, with
no model call until --half is given: the items are the lines the commits --from..--to rewrote whose old claim cites a
source recorded `updated` (label changed) and the facts of sources recorded `confirmed` whose claim stands word for word
in the file at --from and at HEAD (label unchanged), each with its passage in the source's current text from the fact diff
cache, split by the sha256 of the source id into `tune` and `held` before any prompt is read against it. --step judge
sends the items to the batch judge's prompt and schema (factdiff.judge_prompt, JUDGE_SCHEMA); --step check sends each
source with its facts to the phase-4 checker's passage judgments (CHECK_TASK, the same schema): no tools, `--effort
medium` for every model, the full model name pinned. A `supported` verdict is the prediction unchanged; the counts are
the agreement with the labels, the false confirms (a changed unit judged supported) and the false rejects. --dry-run
prints the set's counts and the estimated tokens and USD (factdiff.JUDGE_PRICE, else bench_core.PRICE); each call's cap is
--max-budget-usd; the result of a run (verdicts, tokens, total_cost_usd, seconds, the model `modelUsage` names) is written
to _cache/census/compare/ and a held-out half is judged once per model (--again overrides). --decide reads the two held-out
results of the step's baseline model (BASELINE_MODELS) and --model and says whether the model becomes the step's default
(STEP_MODELS): its false confirms no more than the baseline's and its agreement within COMPARE_POINTS points of it, else
which bar failed. Exit 2 for bad arguments, a missing result or a held-out half judged already, 1 when a call failed.

groups prints, as JSON, the queue's rows (the same rows) split by owner group, with no network and no model: a row goes
to the domain (first directory under the root) of the files naming it in the tree (`rag.py src --cited`; the lines of a
ledger or root-level file count for no domain; a row no line names falls back to the files of the log's `used_in`, else
the group `_uncited`), the domain with most of its citing lines when two cite it, the first by name on a tie, its other
files listed as foreign. Each group has `files` (its domain's files that name its rows), `foreign` (file, domain, row
ids), `queue` (rows, facts, items, chars, tokens as `summary` counts them), `parts` and `rows` (id, url, bucket,
evidence, used_in, mode, facts, items, chars). The output depends only on the log, the fact diff log and the tree.
brief prints one group's phase-2 brief as the kb-census skill words it, filled in: the files to edit and the foreign
ones, each row (id, url, bucket, evidence, used_in), the lines of the kb that cite it (`path:line` and text, as
`rag.py src --cited` finds them), its fact diff review items inline (fact, old and new passage: the queue's own
passages) or, for the other rows, the command that reads it (`git show` and `git diff` in the census clone for a pinned
file, the fetch route of the provider for a page), the outcomes and the result JSON shape. A brief is at most
BRIEF_CHARS characters: a group over it is split by whole rows, in id order, into numbered parts (`--part N`, the first
line says `part N of M`), each with the files citing its rows; a row alone over it is a part of its own. Both exit 2 for
a missing log, an unknown group or a part out of range.

apply takes one group's phase-2 result and does the bookkeeping the orchestrator did by hand. RESULTS.json is valid
against _tools/census_result.schema.json (the file the phase-2 brief names, which `claude -p --json-schema` takes):
the six sections of the brief's result and `edited_files`, the files of the group's own list that it edited.
Refused first (exit 2, every problem named, nothing written): a result that breaks the schema (an outcome outside the
five, a missing or unexpected key); a source id the census log or _sources.csv does not know, or that belongs to another
group (groups as `groups` gives them, owners read from the tree at HEAD, so a worker's own edits move no row); a
`superseded` outcome and a `superseded` entry without each other, or an old row already superseded by another id; a new
row that kbid.add_source (what `kbid.py add` writes) refuses, tried on a scratch copy of _sources.csv; an edited file
outside the files the group owns; a gap or conflict topic that is no article. Then, in order: each new row through
kbid.add_source (never a CSV writer; a url already there is kept), superseded_by on the old rows, each gap and
conflict bullet under its `## <topic>` heading of _gaps.md and _conflicts.md (a new heading at the end; a bullet
already there is skipped), the outcomes as `record` writes them, `factdiff.py anchor --file` for the edited files,
build_index.py and `doc2query.py stale` (exit 1, stale keys, is no failure), each a step of its own as run and finish
have them; the foreign edits are printed, never applied. --dry-run prints every write and step and changes nothing;
a second apply of the same result writes the same bytes.

dispatch runs one brief part of a group as a headless session in place of an Agent-tool subagent, which keeps the
orchestrator's model: `claude -p --model M` (DISPATCH_MODEL by default) with the part's brief on stdin behind a few lines
that name the repository root and what the run may do, `--output-format json` and `--json-schema` of
_tools/census_result.schema.json, `--max-turns` (DISPATCH_TURNS) and `--max-budget-usd` (DISPATCH_BUDGET_USD), no hooks,
user settings or MCP server but the Microsoft Learn one, and `--permission-mode dontAsk` with rules that allow Read and
Edit of the group's owned files alone (absolute paths; the working directory is a scratch directory of its own, removed
after the run), `git show` and `git diff` in the census clones the part's rows read, each page's own `curl` line and
`kbid.py url`. The child's environment is passed explicitly and `claude` is taken from PATH, never from the current
directory. The `structured_output` of the reply, when it is valid against the schema, is written to
_cache/census/dispatch/<D>/<group>/RESULTS.json (RESULTS-<N>.json for part N of a group of several) and the command
that applies it is printed; a run that hits a cap, errors, times out or returns no valid result writes none (an earlier
one is removed), prints `UNAPPLIED` with the reason and exits 1. The raw reply is kept beside it. The ops row
`census.phase` (phase `dispatch`) holds `runs`, `ok` or `failed`, `turns`, the tokens of each kind and `cost-usd-micro`;
its `ms` is the command's wall time. --dry-run starts nothing and prints the caps, the rules and the argv, and an estimate
of the run (turns, tokens, USD at list price, and the --max-budget-usd to pass: factdiff.call_cap of the USD).

score takes a census log that holds the outcomes a census recorded and the results of a model's runs (each a RESULTS.json
`dispatch` wrote) and prints, per source a result names, the recorded outcome beside the result's, then the counts:
sources, agreement, false confirms (`confirmed` where the census changed a fact: updated, superseded or gone, the error
that dates a stale fact) of the changed sources, unconfirmed. It reads, writes nothing and asks no model.

check, record, confirm, repin, judge and dispatch (not their --dry-run) each append one ops row `census.phase` to the query log (phase,
date, ms, exit and the rows per bucket or outcome; kb/_self/querylog.md): factdiff.py detect, apply and review write the same.

run and finish chain the phases no model decides, each step a command of its own (its argv is printed first, its ops
row is its own), with no agent turn between them:
  run:    factdiff.py detect --sitemaps (exit 1, facts to review, is no failure), factdiff.py apply --commit (its
          KB-Verified commit), check --factdiff, repin --commit (its KB-Verified commit), build_index.py, the commit of the
          census log (and of what the steps changed in the root), then summary with the queue block and the blocked hosts. --resume skips detect when
          _census/factdiff-<D>.csv exists, apply when its commit is in the history, check when _census/<D>.csv exists;
          without --resume a log that holds phase-2 outcomes is never overwritten (exit 2).
  finish: confirm, kbdecide.py sweep, build_index.py, the commit `docs(kb): census <D>: confirmed dates` with a
          KB-Verified trailer; it prints the sweep's invalidation and relink lines for the report. Every step writes the
          same bytes a second time, so a stopped finish is run again whole.
A failing step stops the run with its exit code and names the step and the command that resumes it. Tracked changes
outside the root under census (and, for finish, the decision ledgers) refuse the run before its first step and its
commit (exit 2); nothing is ever pushed. --dry-run prints each step's argv and runs nothing.

Exit: 0 ok; 1 check could not write, confirm/record found an unknown id, or repin could not re-point a fact; 2 bad
arguments, a missing log, or run/finish/apply refused;
run, finish and apply: the exit code of the step that failed.
"""
import argparse, concurrent.futures as cf, csv, datetime, functools, hashlib, io, json, os, random, re, shlex, shutil, ssl, subprocess, sys
import socket, tempfile, threading, time, types
import urllib.error, urllib.request
from collections import Counter, defaultdict
from urllib.parse import quote, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index, factdiff, kbcommon, kbfacts, kbid, kbusage, provider, ql_capture  # noqa: E402

KB = kbcommon.PUBLIC  # the root under census (--root; public by default); the cache stays in the repository

REPOS = os.path.join(kbcommon.HOME, "_cache", "census", "repos")
JUDGE_COLS = ["source_id", "fact", "path", "verdict", "sentence", "model", "note"]  # _census/judge-<date>.csv
HAIKU_MODEL = "claude-haiku-5-5"  # pinned: the `haiku` alias moves over time (claude/ci-and-headless.md)
BASELINE_MODELS = {"judge": "claude-sonnet-5-5", "check": "claude-opus-5-5"}  # step: the model it ran on before its comparison
# (the checker's was the orchestrator's, the model the census sessions run on)
STEP_MODELS = {"judge": HAIKU_MODEL, "check": HAIKU_MODEL}  # step: the model it runs on now: Haiku 5.5 where it held both
# bars on the held-out half (kb/_self/reports/fact-diff.md, "Haiku 5.5 on the census's judging steps")
COLS = ["id", "url", "kind", "repo", "pin", "path", "retrieved_utc", "http_status", "bucket", "evidence", "proof", "note",
        "used_in", "outcome", "outcome_note"]
BUCKETS = ("OK", "CHANGED", "GONE", "NEWER-VERSION", "NEEDS-READING")
OUTCOMES = ("confirmed", "updated", "superseded", "gone", "unconfirmed")
SHA = re.compile(r"[0-9a-f]{40}")
BLOCKED = "blocked"
HINTED = "lookup hint"  # a source a lookup revalidated within its provider's pacing: no request, no verdict, not dated
UNREAD = (BLOCKED, HINTED)  # notes of the rows phase 2 does not read
DNS, CONNECT = "dns", "connect"  # a fetch that failed to resolve the host, or to connect to it: retried once, then a note
RETRY_PAUSE = 2  # seconds before that one retry
UA ="it-ops-kb-census/1.0 (read-only link check)"
# Learn url path (after /en-us/) -> (public source repo, path prefix): the page is <prefix><rest>.md or <rest>/index.md
LEARN_MAP = [
    ("entra/", "MicrosoftDocs/entra-docs", "docs/"),
    ("windows-server/", "MicrosoftDocs/windowsserverdocs", "WindowsServerDocs/"),
    ("sql/", "MicrosoftDocs/sql-docs", "docs/"),
    ("powershell/dsc/", "MicrosoftDocs/PowerShell-Docs-DSC", "dsc/docs-conceptual/"),
    ("graph/api/", "microsoftgraph/microsoft-graph-docs-contrib", "api-reference/v1.0/api/"),
]
SHALLOW = ("sql-docs", "entra-docs", "windowsserverdocs")  # large doc repos: history since SHALLOW_SINCE is enough
SHALLOW_SINCE = "2026-01-01"


def today():
    return datetime.date.today().isoformat()


def run(args, cwd=None, timeout=300):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return 124, "", str(e)


def g(d, *args, timeout=300):
    return run(["git", *args], cwd=d, timeout=timeout)


def verdict(bucket, evidence, proof="", note=""):
    return {"bucket": bucket, "evidence": evidence, "proof": proof, "note": note}


# ---------------------------------------------------------------- phase 0: classify

def classify(url):
    u = urlparse(url)
    host, parts = u.netloc.lower(), [unquote(p) for p in u.path.split("/")]
    d = {"kind": "live", "host": host, "repo": "", "pin": "", "path": "", "refparts": []}
    if host == "raw.githubusercontent.com" and len(parts) > 4:
        d.update(repo=f"github.com/{parts[1]}/{parts[2]}", pin=parts[3], path="/".join(parts[4:]), refparts=parts[3:])
        d["kind"] = "raw-pin" if SHA.fullmatch(parts[3]) else "raw-ref"
    elif host == "gitlab.com" and "/-/raw/" in u.path:
        pre, _, rest = u.path.partition("/-/raw/")
        ref, _, path = rest.partition("/")
        d.update(repo="gitlab.com" + pre, pin=ref, path=unquote(path), refparts=unquote(rest).split("/"),
                 kind="raw-pin" if SHA.fullmatch(ref) else "raw-ref")
    elif host == "github.com" and len(parts) >= 3:
        d["repo"] = f"github.com/{parts[1]}/{parts[2]}"
        sub = parts[3:]
        if sub[:2] in (["releases", "download"], ["releases", "tag"]) and len(sub) > 2:
            d.update(kind="release", pin=sub[2])
        elif sub[:1] in (["blob"], ["tree"]) and len(sub) > 1:
            d.update(kind="gh-pin" if SHA.fullmatch(sub[1]) else "gh-ref", pin=sub[1], path="/".join(sub[2:]), refparts=sub[1:])
        else:
            d.update(kind="gh-page", repo="")  # repository home, issues, wiki: github.com pages, not a checkout
    elif host == "api.github.com" and len(parts) > 3 and parts[1] == "repos":
        d["repo"] = f"github.com/{parts[2]}/{parts[3]}"
        rest = [p for p in parts[4:] if p]
        if rest[:1] == ["releases"]:
            d["kind"] = "api-releases"
        elif rest[:3] == ["git", "refs", "tags"] and len(rest) > 3:
            d.update(kind="api-tagref", pin=rest[3])
        elif rest[:1] == ["contents"]:
            ref = re.search(r"[?&]ref=([^&]+)", url)
            d.update(kind="api-contents", pin=ref.group(1) if ref else "", path="/".join(rest[1:]))
        elif rest[:1] == ["commits"]:
            p = re.search(r"[?&]path=([^&]+)", url)
            d.update(kind="api-commits", path=unquote(p.group(1)) if p else "")
        elif not rest:
            d["kind"] = "api-repo"
        else:
            d.update(kind="api-other", repo="")
    elif host == "learn.microsoft.com":
        d["kind"] = "learn"
        repo, path = learn_source(url)
        if repo:
            d.update(repo=repo, path=path)
    return d


def learn_source(url):
    """(repo, path) of the public docs repository (LEARN_MAP) and the file path, without its `.md` or `/index.md`, that a
    learn.microsoft.com page is built from; ("", "") for a page that maps to none. census.py's classify and factdiff.py
    detect both read the map through it."""
    u = urlparse(url)
    if u.netloc.lower() != "learn.microsoft.com":
        return "", ""
    rest = "/".join(unquote(p) for p in u.path.split("/")[2:])
    for pre, repo, rpre in LEARN_MAP:
        if rest.startswith(pre):
            return "github.com/" + repo, rpre + rest[len(pre):].rstrip("/")
    return "", ""


# ---------------------------------------------------------------- git checks

_clone_locks = defaultdict(threading.Lock)
_ready = {}


def clone_name(repo):
    """The directory name (without `.git`) of the bare clone of https://<repo> under REPOS."""
    return re.sub(r"[^\w.-]+", "__", repo.strip("/"))


def repo_dir(repo, base=None):
    """(bare blobless clone of https://<repo>, error). `repo` may also be a local path (tests)."""
    base = base or REPOS
    local = os.path.isdir(repo)
    # a local path's clone is named by its last part and a hash: its whole path in the name, under a long base, would
    # pass Windows' 260-character path limit inside the clone
    name = (f"{os.path.basename(os.path.normpath(repo))}-{hashlib.sha1(repo.encode()).hexdigest()[:8]}" if local
            else clone_name(repo))
    d = os.path.join(base, name + ".git")
    with _clone_locks[d]:
        if d in _ready:
            return _ready[d]
        if not os.path.isdir(d):
            os.makedirs(base, exist_ok=True)
            since = [f"--shallow-since={SHALLOW_SINCE}"] if repo.endswith(SHALLOW) else []
            code, _, err = run(["git", "clone", "-q", "--bare", "--filter=blob:none", *since,
                                repo if local else f"https://{repo}", d], timeout=1800)
            if code:
                _ready[d] = (None, f"clone failed: {err.splitlines()[-1][:120] if err else code}")
                return _ready[d]
        g(d, "fetch", "-q", "--tags", "--force", "origin", "+refs/heads/*:refs/heads/*", timeout=900)
        _ready[d] = (d, "")
    return _ready[d]


def have_commit(d, sha):
    if g(d, "cat-file", "-e", sha + "^{commit}")[0] == 0:
        return True
    g(d, "fetch", "-q", "--filter=blob:none", "origin", sha, timeout=900)
    return g(d, "cat-file", "-e", sha + "^{commit}")[0] == 0


def head(d):
    return g(d, "rev-parse", "HEAD")[1]


def tip_for(d, pin):
    """(tip, name): HEAD when the pin is on the default branch, else the newest branch tip containing it."""
    h = head(d)
    if g(d, "merge-base", "--is-ancestor", pin, h)[0] == 0:
        return h, "HEAD"
    out = g(d, "for-each-ref", "--contains", pin, "--sort=-committerdate", "--format=%(refname:short) %(objectname)", "refs/heads")[1]
    if out:
        name, sha = out.splitlines()[0].split()
        return sha, name
    return h, "HEAD"


def check_pin(d, pin, path):
    """A file at a commit: compared by content with the branch tip."""
    if not have_commit(d, pin):
        return verdict("GONE", f"pin {pin[:12]} can no longer be fetched")
    tip, branch = tip_for(d, pin)
    ev = f"{branch}@{tip[:12]}"
    out = g(d, "log", "--format=%H %cs", f"{pin}..{tip}", "--", path)[1]
    commits = [ln.split() for ln in out.splitlines() if ln.strip()]
    if g(d, "cat-file", "-e", f"{tip}:{path}")[0] == 0:
        if g(d, "diff", "--quiet", pin, tip, "--", path, timeout=900)[0] == 0:
            return verdict("OK", f"file identical at the pin and at {ev}", ev)
        latest = commits[0] if commits else [tip, "?"]
        return verdict("CHANGED", f"file differs at {ev}; latest change {latest[0][:12]} {latest[1]}", ev, f"latest={latest[0]}")
    out = g(d, "diff", "-M", "--diff-filter=R", "--name-status", pin, tip, timeout=900)[1]  # whole tree: renames need both paths
    for ln in out.splitlines():
        f = ln.split("\t")
        if f[0].startswith("R") and len(f) == 3 and f[1] == path:
            return verdict("CHANGED", f"renamed to {f[2]} at {ev}", ev, f"renamed={f[2]}")
    return verdict("GONE", f"file deleted upstream (not at {ev})", ev)


VER = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?([-.+]?.*)?$")


def ver_key(s):
    m = VER.match(s)
    return (tuple(int(x or 0) for x in m.groups()[:4]), (m.group(5) or "").strip("-.+")) if m else None


def is_pre(suffix):
    return bool(re.search(r"(?i)alpha|beta|rc|preview|pre|dev", suffix or ""))


def split_tag(tag):
    m = re.match(r"^(.*?)(v?\d.*)$", tag)
    return (m.group(1), m.group(2)) if m else (None, None)


def newer_tags(tag, tags, when):
    """Tags in `tags` that are newer releases than `tag`: same prefix (monorepo families), same shape for a stable
    tag (no fork suffixes, date tags or 4-part numbers), created no earlier; a stable tag ignores pre-releases."""
    prefix, rest = split_tag(tag)
    k = ver_key(rest) if rest else None
    if not k:
        return None
    shape = lambda s: re.sub(r"\d+", "9", s)  # noqa: E731
    out = []
    for t in tags:
        p, r = split_tag(t)
        if t == tag or p != prefix or not r:
            continue
        kt = ver_key(r)
        if not kt or (is_pre(kt[1]) and not is_pre(k[1])) or (not is_pre(k[1]) and shape(r) != shape(rest)):
            continue
        if when.get(t, "") < when.get(tag, ""):
            continue
        if kt[0] > k[0] or (kt[0] == k[0] and is_pre(k[1]) and (not is_pre(kt[1]) or kt[1] > k[1])):
            out.append((kt, t))
    return [t for _, t in sorted(out)]


@functools.lru_cache(maxsize=None)
def repo_tags(d):
    """([tag], {tag: creator date}) of a repository clone; read once per run (the clones do not change during one)."""
    out = g(d, "for-each-ref", "--format=%(refname:short) %(creatordate:iso-strict)", "refs/tags")[1]
    when = dict(ln.split(" ", 1) for ln in out.splitlines() if " " in ln)
    return list(when), when


def split_ref(d, parts):
    """(ref, path) from `ref/with/slashes/path/to/file`: the longest prefix naming a branch or tag here."""
    for n in range(len(parts), 0, -1):
        ref = "/".join(parts[:n])
        if any(g(d, "rev-parse", "-q", "--verify", f"refs/{k}/{ref}")[0] == 0 for k in ("heads", "tags")):
            return ref, "/".join(parts[n:])
    return parts[0], "/".join(parts[1:])


def check_ref(d, ref, path, since):
    """A file (or the whole tree) at a branch or tag name."""
    if g(d, "rev-parse", "-q", "--verify", f"refs/tags/{ref}")[0] == 0:
        tags, when = repo_tags(d)
        newer = newer_tags(ref, tags, when) or []
        if not newer:
            return verdict("OK", f"tag {ref} is the newest release of its series", f"tag {ref} newest")
        if path and g(d, "diff", "--quiet", ref, newer[-1], "--", path, timeout=900)[0] == 0:
            return verdict("OK", f"newer release {newer[-1]}; the file is identical there", f"identical in {newer[-1]}")
        return verdict("NEWER-VERSION", f"newer release {newer[-1]}; the file differs from {ref}", "", f"newer={newer[-1]}")
    branch = head(d) if ref == "HEAD" else g(d, "rev-parse", "-q", "--verify", f"refs/heads/{ref}")[1]
    if not branch:
        return verdict("GONE", f"no branch or tag {ref!r}")
    if path and g(d, "cat-file", "-e", f"{branch}:{path}")[0] != 0:
        return verdict("GONE", f"{path} is not on {ref}")
    out = g(d, "log", "--format=%H %cs", f"--since={since}T00:00:00Z", branch, "--", path or ".")[1]
    commits = [ln.split() for ln in out.splitlines() if ln.strip()]
    ev = f"{ref}@{branch[:12]}"
    if not commits:
        return verdict("OK", f"no commit on {ref} touches it since {since}; {ev}", ev)
    return verdict("CHANGED", f"{len(commits)} commit(s) on {ref} since {since}, latest {commits[0][0][:12]} {commits[0][1]}", ev)


def check_release(d, tag):
    if g(d, "rev-parse", "-q", "--verify", f"refs/tags/{tag}")[0] != 0:
        return verdict("GONE", f"tag {tag} no longer exists")
    tags, when = repo_tags(d)
    newer = newer_tags(tag, tags, when)
    if newer is None:
        return verdict("NEEDS-READING", f"cannot compare release tag {tag}")
    if newer:
        return verdict("NEWER-VERSION", f"newer release(s): {', '.join(newer[-3:])}", "", f"newer={newer[-1]}")
    return verdict("OK", f"{tag} is still the newest release of its series", f"release {tag} newest")


RECORDED = re.compile(r"(?<![\w.])(v?\d+\.\d+(?:\.\d+)*(?:[-.][0-9A-Za-z.]+)?)")


def check_api_release(d, kind, rec, since):
    m = RECORDED.search(rec)
    if m and g(d, "rev-parse", "-q", "--verify", f"refs/tags/{m.group(1)}")[0] == 0:
        tags, when = repo_tags(d)
        newer = newer_tags(m.group(1), tags, when) or []
        if not newer:
            return verdict("OK", f"recorded release {m.group(1)} is still the newest of its series", f"release {m.group(1)} newest")
        return verdict("NEWER-VERSION", f"newer than the recorded {m.group(1)}: {', '.join(newer[-3:])}", "", f"newer={newer[-1]}")
    if kind == "api-repo":
        return verdict("NEEDS-READING", "repository metadata; no recorded release to compare (api.github.com is not called)")
    out = g(d, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short) %(creatordate:short)", "refs/tags")[1]
    after = [ln.split()[0] for ln in out.splitlines() if len(ln.split()) == 2 and ln.split()[1] > since
             and re.fullmatch(r"v?\d+\.\d+(\.\d+)?([-.][0-9A-Za-z.]+)?", ln.split()[0])]
    if not after:
        return verdict("OK", f"no release tagged after retrieval {since}", f"no release after {since}")
    return verdict("NEWER-VERSION", f"release(s) tagged after retrieval {since}: {', '.join(after[:3])}", "", f"newer={after[0]}")


def check_learn(d, path, since):
    cands = (path + ".md", path + "/index.md", path + ".yml", path + "/index.yml")
    have = set(g(d, "ls-tree", "-z", "--name-only", "HEAD", "--", *cands)[1].split("\0"))  # one call for the four probes
    for cand in cands:
        if cand in have:
            out = g(d, "log", "--format=%H %cs", f"--since={since}T00:00:00Z", "HEAD", "--", cand)[1]
            commits = [ln.split() for ln in out.splitlines() if ln.strip()]
            h = head(d)
            if not commits:
                return verdict("OK", f"source file {cand} has no commit since {since} (HEAD {h[:12]})", f"git_commit_id {h[:12]}")
            return verdict("CHANGED", f"source file {cand}: {len(commits)} commit(s) since {since}, latest "
                                      f"{commits[0][0][:12]} {commits[0][1]}", f"git_commit_id {commits[0][0][:12]}")
    return None


def learn_repos(urls):
    """The repositories (LEARN_MAP) that the learn.microsoft.com `urls` map to, each cloned or fetched once, in parallel,
    into the shared clone cache (factdiff.py detect warms them before its per-host jobs)."""
    repos = sorted({repo for repo, _ in map(learn_source, urls) if repo})
    with cf.ThreadPoolExecutor(max(1, len(repos))) as ex:
        list(ex.map(repo_dir, repos))
    return repos


def learn_git_verdict(url, since):
    """check_learn's verdict (OK, or CHANGED with its commits) of a learn.microsoft.com page from the commits of its source
    file since `since` (a day) in the shared clone, with no request to Learn; None for a page that maps to no repository,
    whose repository cannot be cloned or whose file is not at its HEAD (the caller asks Learn instead)."""
    repo, path = learn_source(url)
    if not repo:
        return None
    d, _ = repo_dir(repo)
    return check_learn(d, path, since) if d else None


# ---------------------------------------------------------------- http checks

_host_sem = defaultdict(lambda: threading.Semaphore(2))
_sitemaps, _sitemap_lock = {}, threading.Lock()
_ctx = None


def ssl_ctx():
    global _ctx
    if _ctx is None:
        cafile = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
        _ctx = ssl.create_default_context(cafile=cafile)
    return _ctx


NO_HOST = re.compile(r"(?i)nodename nor servname|name or service not known|temporary failure in name resolution|"
                     r"getaddrinfo failed|no address associated")
NO_CONNECTION = re.compile(r"(?i)timed out|unreachable|no route to host")


def net_failure(e):
    """DNS for a name-resolution error, CONNECT for a connection error (refused, reset, timed out, unreachable), else ''."""
    reason = getattr(e, "reason", e)
    if isinstance(reason, socket.gaierror) or NO_HOST.search(str(reason)):
        return DNS
    if isinstance(reason, (ConnectionError, TimeoutError, socket.timeout)) or NO_CONNECTION.search(str(reason)):
        return CONNECT
    return ""


def net_note(st):
    """`dns` or `connect` for the status of a fetch that failed on the network (`fetch` writes `dns: ...`), else ''."""
    kind = st.partition(":")[0] if isinstance(st, str) else ""
    return kind if kind in (DNS, CONNECT) else ""


def fetch(url, timeout=25, limit=1_000_000):
    """(status or 'blocked' or 'dns: ...' or 'connect: ...' or 'error: ...', text, final url). A name-resolution or
    connection error is tried once more after RETRY_PAUSE seconds: the status that stays is the second try's."""
    got = fetch_once(url, timeout, limit)
    if net_note(got[0]):
        time.sleep(RETRY_PAUSE)
        got = fetch_once(url, timeout, limit)
    return got


def fetch_once(url, timeout, limit):
    with _host_sem[urlparse(url).netloc]:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx()) as resp:
                body = resp.read(limit)
                ql_capture.record_request(url, ql_capture.request_outcome(resp.status, None, len(body), url, resp.geturl(),
                                                                      limit), body)
                return resp.status, body.decode("utf-8", "replace"), resp.geturl()
        except urllib.error.HTTPError as e:
            ql_capture.record_request(url, f"http-{e.code}")
            return e.code, "", url
        except (urllib.error.URLError, OSError) as e:
            ql_capture.record_request(url, "error")
            msg = str(getattr(e, "reason", e))
            if re.search(r"(?i)tunnel|403 forbidden", msg):
                return BLOCKED, "", url
            return f"{net_failure(e) or 'error'}: {msg[:60]}", "", url
        except Exception as e:  # noqa: BLE001 - a link check must never stop the census
            ql_capture.record_request(url, "error")
            return f"error: {type(e).__name__}", "", url


def unreached(st):
    """The NEEDS-READING verdict of a fetch status that no page answered (the note says why: `blocked` by this
    environment's network policy, `dns` or `connect` after the retry), else None."""
    if st == BLOCKED:
        return verdict("NEEDS-READING", "host denied by this environment's network policy", "", BLOCKED)
    note = net_note(st)
    if note:
        return verdict("NEEDS-READING", f"{st} (tried twice)", "", note)
    return None


def sitemap_lastmod(url):
    u = urlparse(url)
    with _sitemap_lock:
        if u.netloc not in _sitemaps:
            m = {}
            for sm in ("/docs/sitemap.xml", "/sitemap.xml"):
                st, body, _ = fetch(f"{u.scheme}://{u.netloc}{sm}", limit=30_000_000)
                if st == 200:
                    m.update({loc.rstrip("/"): lm for loc, lm in
                              re.findall(r"<loc>\s*([^<]+?)\s*</loc>\s*<lastmod>\s*([^<]+?)\s*</lastmod>", body)})
            _sitemaps[u.netloc] = m
    base = url.split("#")[0].rstrip("/")
    return _sitemaps[u.netloc].get(base) or _sitemaps[u.netloc].get(base[:-3] if base.endswith(".md") else "")


DATE_PATTERNS = [
    r'property="article:modified_time"\s+content="([^"]+)"', r'"dateModified"\s*:\s*"([^"]+)"',
    r'name="(?:last-modified|updated_at|ms\.date|revised)"\s+content="([^"]+)"',
    r'itemprop="dateModified"\s+(?:content|datetime)="([^"]+)"',
    r"(?i)last (?:updated|modified|revised)(?: on)?[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})",
]


def norm_date(s):
    s = (s or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def check_pypi(url, rec):
    m = re.match(r"https://pypi\.org/(?:pypi|project)/([^/?#]+)", url)
    st, body, _ = fetch(f"https://pypi.org/pypi/{m.group(1)}/json")
    if st != 200:
        return st, None
    try:
        ver = json.loads(body)["info"]["version"]
    except (ValueError, KeyError, TypeError):
        return st, None
    if re.search(rf"(?<![\w.]){re.escape(ver)}(?![\w.])", rec):
        return st, verdict("OK", f"PyPI latest {ver} matches the recorded version", f"PyPI {ver}")
    if not RECORDED.search(rec):
        return st, verdict("NEEDS-READING", f"PyPI latest {ver}; no version recorded to compare")
    return st, verdict("NEWER-VERSION", f"PyPI latest {ver}; recorded: {rec[:60]}", "", f"newer={ver}")


LEARN_UPDATED = re.compile(r'<meta name="updated_at" content="([^"]+)"')
LEARN_COMMIT = re.compile(r'<meta name="git_commit_id" content="([0-9a-f]{12})')


def check_learn_page(url, since):
    """A Learn page without a readable source repo: its `updated_at` meta (the build's last content update, not
    `ms.date`, the author's review date, which lags) against retrieval."""
    st, body, final = fetch(url)
    if res := unreached(st):
        return st, res
    if st in (404, 410):
        return st, verdict("GONE", f"HTTP {st}")
    m = LEARN_UPDATED.search(body) if st == 200 else None
    date = norm_date(m.group(1)) if m else None
    if not date:
        return st, verdict("NEEDS-READING", f"HTTP {st}, no updated_at; read it (microsoft_docs_fetch)", "", "learn")
    c = LEARN_COMMIT.search(body)
    proof = f"updated_at {date}" + (f", git_commit_id {c.group(1)}" if c else "")
    moved = f"; redirected to {final}" if final.rstrip("/") != url.rstrip("/") else ""
    if date > since:
        return st, verdict("CHANGED", f"Learn updated_at {date} is after retrieval {since}{moved}", proof)
    return st, verdict("OK", f"Learn updated_at {date}, not after retrieval {since}{moved}", proof)


def check_live(url, since, rec):
    if url.startswith(("https://pypi.org/pypi/", "https://pypi.org/project/")):
        st, res = check_pypi(url, rec)
        if res:
            return st, res
    st, body, final = fetch(url)
    if res := unreached(st):
        return st, res
    if st in (404, 410):
        return st, verdict("GONE", f"HTTP {st}")
    if st != 200:
        return st, verdict("NEEDS-READING", f"HTTP {st}")
    date, how = norm_date(sitemap_lastmod(url)), "sitemap lastmod"
    if not date:
        for pat in DATE_PATTERNS:
            m = re.search(pat, body)
            if m and norm_date(m.group(1)):
                date, how = norm_date(m.group(1)), "page date"
                break
    moved = f"; redirected to {final}" if final.rstrip("/") != url.rstrip("/") else ""
    if not date:
        return st, verdict("NEEDS-READING", f"HTTP 200, no last-updated date{moved}")
    if date > since:
        return st, verdict("CHANGED", f"{how} {date} is after retrieval {since}{moved}", f"{how} {date}")
    return st, verdict("OK", f"{how} {date}, not after retrieval {since}{moved}", f"{how} {date}")


# ---------------------------------------------------------------- github.com pages

README_FILE = re.compile(r"(?i)readme(\.[a-z]+)?")
LICENCE_FILE = re.compile(r"(?i)(licen[sc]e|copying)(\.[a-z]+)?")
ARCHIVED = re.compile(r"archived by the owner(?: on ([A-Z][a-z]{2} \d{1,2}, \d{4}))?")
RELEASE_TAG = re.compile(r"\d+\.\d+")


def tree_files(d, directory=""):
    """{path: blob id} of the files directly in `directory` of the default branch (the clone holds trees: no blob is fetched)."""
    out = g(d, "ls-tree", "-z", "HEAD", *([directory + "/"] if directory else []))[1]
    files = {}
    for ent in out.split("\0"):
        meta, _, path = ent.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            files[path] = parts[2]
    return files


def named_file(d, rx, directories=("",)):
    """(path, blob id) of the first file whose name `rx` matches in the first of `directories` that has one (a Markdown file
    before the others), else ("", "")."""
    for sub in directories:
        files = tree_files(d, sub)
        found = sorted((p for p in files if rx.fullmatch(p.rpartition("/")[2])), key=lambda p: (not p.lower().endswith(".md"), p))
        if found:
            return found[0], files[found[0]]
    return "", ""


def wiki_file(d, title):
    """(path, blob id) of the wiki page `title` (`Some-Page`; the file has an extension) in the wiki's repository, else ("", "")."""
    out = g(d, "ls-tree", "-r", "-z", "HEAD")[1]
    want = unquote(title).lower().replace(" ", "-")
    for ent in out.split("\0"):
        meta, _, path = ent.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob" and os.path.splitext(path)[0].lower().replace(" ", "-") == want:
            return path, parts[2]
    return "", ""


def release_tags(d, since=""):
    """The version-like tag names of the clone (those created on or after `since`, when given), sorted."""
    out = g(d, "for-each-ref", "--format=%(refname:short) %(creatordate:short)", "refs/tags")[1]
    return sorted(t for t, _, day in (ln.partition(" ") for ln in out.splitlines())
                  if RELEASE_TAG.search(t) and (not since or day >= since))


def gh_page_id(url, text=""):
    """The version id of a github.com page that is a file of a git repository, from the bare clone cache, or '' when its
    kind has none or the repository cannot be cloned (factdiff.py detect's `git` signal): a wiki page's blob id in the
    wiki's repository; a repository home's README blob at the default branch with its licence blob, its version-like
    tags and whether `text` (the page) carries the archived banner."""
    kind, repo, name = provider.github_page(url)
    if kind not in ("home", "wiki"):
        return ""
    d, _ = repo_dir(repo)
    if not d:
        return ""
    if kind == "wiki":
        return wiki_file(d, name)[1][:16]
    readme = named_file(d, README_FILE, (".github", "", "docs"))
    licence = named_file(d, LICENCE_FILE)
    if not readme[1]:
        return ""
    parts = ["readme " + readme[1], "licence " + licence[1], "tags " + " ".join(release_tags(d)),
             "archived " + ("yes" if ARCHIVED.search(text or "") else "no")]
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()[:16]


def gh_page_quiet_since(url, text, since):
    """Whether the repository of a github.com wiki page or repository home holds no commit for it, no release tag and no
    archiving on or after `since` (a day): the same finding as check_gh_page's, for a page whose text was compared
    with a baseline taken on that day (factdiff.py detect)."""
    kind, repo, name = provider.github_page(url)
    if kind not in ("home", "wiki"):
        return False
    d, _ = repo_dir(repo)
    return bool(d) and check_gh_git(d, kind, name, text, since)["bucket"] == "OK"


def commits_since(d, since, *paths):
    """[(sha, date)] of the commits on the default branch from `since` (a day) on that touch `paths`, newest first."""
    out = g(d, "log", "--format=%H %cs", f"--since={since}T00:00:00Z", "HEAD", "--", *paths)[1]
    return [tuple(ln.split()) for ln in out.splitlines() if ln.strip()]


def check_gh_git(d, kind, name, body, since):
    """The verdict of a repository home or a wiki page from the clone `d` of its repository (the page body: `body`)."""
    h = head(d)[:12]
    if kind == "wiki":
        path, blob = wiki_file(d, name)
        if not blob:
            return verdict("NEEDS-READING", f"page {name} is not a file of the wiki's repository (HEAD {h})")
        commits = commits_since(d, since, path)
        if commits:
            return verdict("CHANGED", f"wiki file {path}: {len(commits)} commit(s) since {since}, latest {commits[0][0][:12]} "
                           f"{commits[0][1]}", f"wiki {h} {path}")
        return verdict("OK", f"wiki file {path} has no commit since {since}; HEAD {h}", f"wiki {h} {path}")
    m = ARCHIVED.search(body)
    if m:
        try:
            day = datetime.datetime.strptime(m.group(1) or "", "%b %d, %Y").date().isoformat()
        except ValueError:
            return verdict("NEEDS-READING", "the page carries the archived banner with no date")
        if day >= since:
            return verdict("CHANGED", f"archived by the owner on {day}, on or after retrieval {since}", f"archived {day}")
    readme, licence = named_file(d, README_FILE, (".github", "", "docs")), named_file(d, LICENCE_FILE)
    if not readme[0]:
        return verdict("NEEDS-READING", f"no README in the default branch (HEAD {h})")
    for label, path in (("README", readme[0]), ("licence", licence[0])):
        commits = commits_since(d, since, path) if path else []
        if commits:
            return verdict("CHANGED", f"{label} {path}: {len(commits)} commit(s) since {since}, latest {commits[0][0][:12]} "
                           f"{commits[0][1]}", f"README {readme[1][:12]}")
    tags = release_tags(d, since)
    if tags:
        return verdict("CHANGED", f"release tag(s) created on or after retrieval {since}: {', '.join(tags[-3:])}", f"HEAD {h}")
    return verdict("OK", f"README {readme[0]} and the licence have no commit since {since}, no release tag after it, not "
                   f"archived since; HEAD {h}", f"README {readme[1][:12]} HEAD {h}")


def check_gh_page(url, kind, repo, name, since):
    """(http status, verdict) of a github.com page the provider registry gives a signal (provider.github_page)."""
    if kind == "wiki-repo":
        d, err = repo_dir(repo)
        if not d:
            return "", verdict("NEEDS-READING", err)
        commits = commits_since(d, since)
        h = head(d)[:12]
        if commits:
            return "", verdict("CHANGED", f"{len(commits)} commit(s) on the wiki's repository since {since}, latest "
                               f"{commits[0][0][:12]} {commits[0][1]}", f"wiki {h}")
        return "", verdict("OK", f"no commit on the wiki's repository since {since}; HEAD {h}", f"wiki {h}")
    st, body, final = fetch(url)
    if res := unreached(st):
        return st, res
    if st in (404, 410):
        return st, verdict("GONE", f"HTTP {st}")
    if st != 200:
        return st, verdict("NEEDS-READING", f"HTTP {st}")
    if unquote(urlparse(final).path).rstrip("/").lower() != unquote(urlparse(url).path).rstrip("/").lower():
        return st, verdict("CHANGED", f"redirected to {final}", f"redirect {final}")
    if kind in ("issue", "discussion"):
        stamp = provider.version_of(body, [provider.TIMELINE]).get(provider.TIMELINE, "")
        if not stamp:
            return st, verdict("NEEDS-READING", "HTTP 200, no timestamp in the page's markup")
        if stamp[:10] > since:
            return st, verdict("CHANGED", f"the timeline's latest event {stamp} is after retrieval {since}", f"timeline {stamp}")
        return st, verdict("OK", f"the timeline's latest event {stamp} is not after retrieval {since}", f"timeline {stamp}")
    d, err = repo_dir(repo)
    if not d:
        return st, verdict("NEEDS-READING", err)
    return st, check_gh_git(d, kind, name, body, since)


# ---------------------------------------------------------------- check (phases 0-1)

def hinted_verdict(evidence):
    """The verdict row of a source a lookup's stored revalidation spared (factdiff.lookup_hints): NEEDS-READING with the
    note HINTED, which no phase reads and `confirm` never dates (only a bucket OK or an outcome does)."""
    return verdict("NEEDS-READING", evidence, "", HINTED)


def factdiff_verdicts(path, retrieved=None):
    """{source id: (http status, verdict)} from a fact diff log (factdiff.py detect, the census's first stage): a source
    that did not change, or whose every fact was found word for word, is OK when the text compared is no newer than
    its retrieved_utc (by the detection baseline or the page's content date; else it is checked here); a gone one
    GONE; one with facts to review CHANGED; one detect spared on a lookup's hint HINTED. Pinned sources are left to
    the git checks here."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by = defaultdict(list)
    for r in rows:
        by[r["source_id"]].append(r)
    out = {}
    for sid, rs in by.items():
        head, facts = rs[0], [r for r in rs if r["fact"]]
        v = head["verdict"]
        if v in ("pinned", "error"):
            continue
        if v == "hinted":  # spared by a lookup's stored result: not asked, so not confirmed either
            out[sid] = ("", hinted_verdict(head["evidence"]))
            continue
        todo = [r for r in facts if r["outcome"] not in ("verbatim", "moved")]
        rd = ((retrieved or {}).get(sid) or "")[:10]
        proven = bool(rd) and any(d and d[:10] <= rd for d in (head.get("baseline_utc", ""), head.get("content_date", "")))
        if v in ("unchanged", "changed", "new", "moved") and not todo and not proven:
            continue  # compared with a text newer than the last confirmation: checked here instead
        if v == "unchanged":
            res = verdict("OK", f"fact diff: unchanged ({head['signal']}: {head['evidence']})", f"fact diff {head['signal']}")
        elif v in ("gone", "soft-404") and not [r for r in facts if r["outcome"] == "moved"]:
            res = verdict("GONE", f"fact diff: {v} ({head['evidence']})")
        elif not todo:
            res = verdict("OK", f"fact diff: {v}, {len(facts)} fact(s) found word for word", "fact diff anchors verbatim")
        else:
            kinds = Counter(r["outcome"] for r in todo)
            res = verdict("CHANGED", f"fact diff: {v}; review " + ", ".join(f"{k}={n}" for k, n in sorted(kinds.items()))
                          + f" (factdiff.py review {os.path.basename(path)} --source {sid})")
        out[sid] = ("", res)
    return out


def check_one(r, c):
    since = (r.get("retrieved_utc") or today())[:10]
    kind = c["kind"]
    if kind == "gh-page":
        page, repo, name = provider.github_page(r["url"])
        if page:
            return check_gh_page(r["url"], page, repo, name, since)
    if kind == "gh-page" or kind == "api-other":
        return "", verdict("NEEDS-READING", "a github.com page (issues, wiki, home) or API call; read it", "", "github page")
    if c["repo"]:
        if provider.is_pinned(r["url"]):  # a clone cache outlives its repository: ask the repository first
            state, ev = provider.repository_state(r["url"])
            if state == "gone":
                return "", verdict("GONE", f"repository: {ev}")
        d, err = repo_dir(c["repo"])
        if not d:
            if kind == "learn":
                return check_learn_page(r["url"], since)
            return "", verdict("NEEDS-READING", err)
        if kind in ("raw-pin", "gh-pin"):
            res = check_pin(d, c["pin"], c["path"])
            if "MicrosoftDocs/memdocs" in c["repo"]:
                res = verdict("NEEDS-READING", res["evidence"] + "; MicrosoftDocs/memdocs is archived: re-source to the live "
                              "Learn page", "", "memdocs")
        elif kind in ("raw-ref", "gh-ref"):
            res = check_ref(d, *split_ref(d, c["refparts"]), since)
        elif kind == "release":
            res = check_release(d, c["pin"])
        elif kind in ("api-releases", "api-repo"):
            res = check_api_release(d, kind, r.get("version_or_date", ""), since)
        elif kind == "api-tagref":
            sha = g(d, "rev-parse", "-q", "--verify", f"refs/tags/{c['pin']}^{{commit}}")[1]
            obj = g(d, "rev-parse", "-q", "--verify", f"refs/tags/{c['pin']}")[1]
            rec = r.get("version_or_date", "")
            res = (verdict("OK", f"tag {c['pin']} still points to {sha[:12]}", f"tag {c['pin']}={sha[:12]}")
                   if sha and (sha[:12] in rec or obj[:12] in rec) else
                   verdict("CHANGED" if sha else "GONE", f"tag {c['pin']} -> {sha[:12] or 'missing'}; recorded {rec[:40]}"))
        elif kind == "api-contents":
            res = check_ref(d, c["pin"] or "HEAD", c["path"], since)
        elif kind == "api-commits":
            res = check_ref(d, "HEAD", c["path"], since)
        else:  # learn with a mapped source repo; a page whose file moved falls back to the page's updated_at
            res = check_learn(d, c["path"], since)
            if not res:
                return check_learn_page(r["url"], since)
        st = fetch(r["url"])[0] if kind in ("raw-pin", "raw-ref") else ""
        return st, res
    if kind == "learn":
        return check_learn_page(r["url"], since)
    return check_live(r["url"], since, r.get("version_or_date", ""))


def read_sources():
    """The rows of the root's _sources.csv, in file order."""
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def article_files():
    """The root's domain .md files (directories not named `_*` or `.*`), relative to the root, sorted."""
    out = []
    for d, dirs, files in os.walk(KB):
        dirs[:] = sorted(x for x in dirs if not x.startswith(("_", ".")) and x != "__pycache__")
        if d != KB:
            out += [os.path.relpath(os.path.join(d, f), KB).replace(os.sep, "/") for f in files if f.endswith(".md")]
    return sorted(out)


def cmd_check(a, tally):
    date = a.date or today()
    out = a.out or os.path.join(KB, "_census", f"{date}.csv")
    rows = [r for r in read_sources() if not a.source or r["id"] in a.source]
    if not rows:
        print("no source selected")
        return 2
    fd = factdiff_verdicts(a.factdiff, {r["id"]: r.get("retrieved_utc", "") for r in rows}) if a.factdiff else {}
    rest = {r["id"]: r for r in rows if r["id"] not in fd}
    hints = factdiff.lookup_hints(list(rest), rest, provider.providers(factdiff.ROOT))
    fd.update({sid: ("", hinted_verdict(factdiff.hinted_result(h)[2])) for sid, h in hints.items()})
    work = [(r, classify(r["url"])) for r in rows]
    print(f"phase 0: {len(work)} sources; " + ", ".join(f"{k}={n}" for k, n in sorted(Counter(c["kind"] for _, c in work).items())), flush=True)
    if hints:
        print(f"  {len(hints)} source(s) a lookup revalidated within its provider's pacing are not asked", flush=True)
    pinned = [(r, c) for r, c in work if c["repo"] and r["id"] not in fd and provider.is_pinned(r["url"])]
    with cf.ThreadPoolExecutor(8) as ex:  # one request per repository (provider.repository_state); a gone one is not cloned
        states = list(ex.map(provider.repository_state, [r["url"] for r, _ in pinned]))
    gone = {c["repo"] for (_, c), (state, _) in zip(pinned, states) if state == "gone"}
    if gone:
        print(f"  {len(gone)} repositor{'y' if len(gone) == 1 else 'ies'} of pinned sources answer 404: not cloned", flush=True)
    repos = sorted({c["repo"] for r, c in work if c["repo"] and r["id"] not in hints} - gone)
    with cf.ThreadPoolExecutor(8) as ex:
        for repo, (d, err) in zip(repos, ex.map(repo_dir, repos)):
            if not d:
                print(f"  {repo}: {err}", flush=True)

    def one(item):
        r, c = item
        if r["id"] in fd:
            return r, c, fd[r["id"]][0], fd[r["id"]][1]
        try:
            st, res = check_one(r, c)
        except Exception as e:  # noqa: BLE001
            st, res = "", verdict("NEEDS-READING", f"census error: {type(e).__name__}: {e}")
        return r, c, st, res

    results = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for n, item in enumerate(ex.map(one, work), 1):
            results.append(item)
            if n % 200 == 0:
                print(f"  {n}/{len(work)}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, lineterminator="\n")
        w.writeheader()
        for r, c, st, res in results:
            w.writerow({"id": r["id"], "url": r["url"], "kind": c["kind"], "repo": c["repo"], "pin": c["pin"], "path": c["path"],
                        "retrieved_utc": r["retrieved_utc"], "http_status": st, **res, "used_in": r.get("used_in", ""),
                        "outcome": "", "outcome_note": ""})
    counts = Counter(res["bucket"] for _, _, _, res in results)
    tally.update(counts)
    print("phase 1: " + ", ".join(f"{b}={counts[b]}" for b in BUCKETS) + f"; wrote {os.path.relpath(out, kbcommon.HOME)}")
    return 0


# ---------------------------------------------------------------- record, confirm, sample, summary

def read_log(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_log(path, rows):
    kbcommon.write_csv(path, COLS, rows, atomic=True)


def set_outcomes(rows, items, tally):
    """Set outcome and outcome_note on the rows of the log for each {id, outcome, note} of `items`; the number of items
    skipped (an unknown id or an outcome outside OUTCOMES, each printed)."""
    by_id = {r["id"]: r for r in rows}
    bad = 0
    for it in items:
        if it.get("id") not in by_id or it.get("outcome") not in OUTCOMES:
            print(f"skipped {it!r}: unknown id or outcome (outcomes: {', '.join(OUTCOMES)})")
            bad += 1
            tally["skipped"] += 1
            continue
        by_id[it["id"]]["outcome"] = it["outcome"]
        tally[it["outcome"]] += 1
        by_id[it["id"]]["outcome_note"] = (it.get("note") or "").replace("\n", " ")[:300]
    return bad


def cmd_record(a, tally):
    rows = read_log(a.log)
    if a.from_json:
        with open(a.from_json, encoding="utf-8") as f:
            items = json.load(f)
    else:
        items = [{"id": a.id, "outcome": a.outcome, "note": a.note or ""}]
    bad = set_outcomes(rows, items, tally)
    write_log(a.log, rows)
    print(f"recorded {len(items) - bad} outcome(s)" + (f", skipped {bad}" if bad else ""))
    return 1 if bad else 0


def confirmed(r):
    return (r["bucket"] == "OK" and not r["outcome"]) or r["outcome"] in ("confirmed", "updated")


SUFFIX = re.compile(r"(?:;\s*)?confirmed \d{4}-\d{2}-\d{2}: [^;]*$")


def cmd_confirm(a, tally):
    date = a.date or today()
    log = {r["id"]: r for r in read_log(a.log)}
    srcs_text = kbcommon.read(os.path.join(KB, "_sources.csv"), newline="", strict=True)
    reader = csv.DictReader(io.StringIO(srcs_text))
    header, rows = reader.fieldnames, list(reader)
    known = {r["id"] for r in rows}
    unknown = sorted(set(log) - known)
    if unknown:
        print(f"log ids not in _sources.csv: {', '.join(unknown[:10])}")
        return 1
    n_src = 0
    for r in rows:
        lr = log.get(r["id"])
        if not lr or not confirmed(lr):
            continue
        proof = (lr["proof"] or lr["outcome_note"] or lr["evidence"]).replace(";", ",")[:120]
        vod = SUFFIX.sub("", r["version_or_date"]).rstrip("; ")
        r["version_or_date"] = (vod + "; " if vod else "") + f"confirmed {date}: {proof}"
        r["retrieved_utc"] = date
        n_src += 1
    # confirmed by this census, or a row it added (phase 2 read those in full); a row merely retrieved on the same
    # day by other work, or left unconfirmed, does not count
    fresh = {sid for sid, lr in log.items() if confirmed(lr)} | {r["id"] for r in rows if r["id"] not in log and r["retrieved_utc"][:10] == date}
    articles = []
    for rel in article_files():
        path = os.path.join(KB, rel)
        text = kbcommon.read(path, newline="", strict=True)
        fm = build_index.front_matter(text)
        if not fm or not fm.get("sources") or "retrieved_utc" not in fm:
            continue
        ids = kbid.SOURCE_ID.findall(str(fm["sources"]))
        if ids and all(i in fresh for i in ids) and str(fm["retrieved_utc"])[:10] != date:
            new = re.sub(r"(?m)^retrieved_utc:.*$", f"retrieved_utc: {date}", text, count=1)
            articles.append((path, new))
    state_path = os.path.join(KB, "_fetch_state.csv")
    state_cols = kbcommon.STATE_COLS
    state = {}
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8", newline="") as f:
            state = {r["id"]: r for r in csv.DictReader(f)}
    stamp = f"{date}T00:00:00Z"
    urls = {r["id"]: r["url"] for r in rows}
    since, prov, n_base = ql_capture.phase_date(path=a.log), provider.providers(factdiff.ROOT), 0
    for sid, lr in log.items():
        if confirmed(lr):
            row = {**state.get(sid, {"id": sid}), "id": sid, "url": urls[sid], "checked_utc": stamp, "error": ""}
            if not factdiff.has_baseline(row) and not provider.is_pinned(urls[sid]):
                got = factdiff.census_baseline(sid, urls[sid], since, date, prov)
                n_base += bool(got)
                row.update(got)
            state[sid] = row
    tally.update(confirmed=n_src, added=len(fresh) - n_src, articles=len(articles), baselines=n_base)
    print(f"confirm {date}: {n_src} source(s) confirmed, {len(fresh) - n_src} row(s) added by the census, {len(articles)} article(s) re-dated, "
          f"{n_base} detection baseline(s) written")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    kbcommon.write_csv(os.path.join(KB, "_sources.csv"), header, rows, atomic=True)
    for path, new in articles:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
    kbcommon.write_csv(state_path, state_cols, sorted(state.values(), key=lambda r: kbid.sort_key(r["id"])), atomic=True)
    return 0


def cmd_baselines(a, tally):
    """The live unpinned sources whose _fetch_state.csv row holds no detection baseline, counted by host (the QUEUE_HOSTS
    with most, unless --list): no network and no model; exit 1 when any, so the gap shows before a census starts. A page
    with no date and no baseline is a row for a reader."""
    srcs = factdiff.sources()
    gap = factdiff.baseline_gap(srcs, factdiff.read_state())
    by_host = defaultdict(list)
    for sid in gap:
        by_host[urlparse(srcs[sid]["url"]).netloc.lower()].append(sid)
    hosts = sorted(by_host, key=lambda h: (-len(by_host[h]), h))
    shown = hosts if a.list else hosts[:QUEUE_HOSTS]
    print(f"baselines: {len(gap)} of {len(factdiff.live_unpinned(srcs))} live unpinned source(s) hold no detection baseline "
          "(no ETag, Last-Modified, version id or text hash in _fetch_state.csv)")
    for h in shown:
        print(f"  {h}: {len(by_host[h])}")
        if a.list:
            for sid in by_host[h]:
                print(f"    {sid} {srcs[sid]['url']}")
    rest = hosts[len(shown):]
    if rest:
        print(f"  {len(rest)} other host(s): {sum(len(by_host[h]) for h in rest)}")
    return 1 if gap else 0


JUDGED_NOTE = "fact(s) judged supported by"  # the note `judge` gives a source it confirmed with no agent; `sampled` reads it
SAMPLE_GROUPS = ("changed", "judged", "ok")  # the phase-4 sample's groups, in the order the sample and its brief list them


def sampled(rows, a):
    """[(group, row)] of the phase-4 sample, in the order the CSV lists them: `changed` (outcome updated, superseded or
    gone), `judged` (outcome confirmed by a model call of `judge`, its note holding `JUDGED_NOTE`: a false confirm
    there is a stale fact the sample must catch, so its rate is the changed group's) and `ok` (bucket OK with no
    outcome, or any other confirmed), each a seeded fraction of at least one row, by id."""
    rnd = random.Random(a.seed)
    changed = [r for r in rows if r["outcome"] in ("updated", "superseded", "gone")]
    judged = [r for r in rows if r["outcome"] == "confirmed" and JUDGED_NOTE in r["outcome_note"]]
    ok = [r for r in rows if (r["bucket"] == "OK" and not r["outcome"]) or (r["outcome"] == "confirmed" and JUDGED_NOTE not in r["outcome_note"])]
    pick = lambda xs, rate: rnd.sample(xs, min(len(xs), max(1, round(len(xs) * rate)))) if xs else []  # noqa: E731
    out = []
    for group, xs in (("changed", pick(changed, a.changed)), ("judged", pick(judged, a.judged)), ("ok", pick(ok, a.ok))):
        out += [(group, r) for r in sorted(xs, key=lambda r: r["id"])]
    return out


WORD = "word for word"  # the anchor's passage is in the source's current text: the proof factdiff apply dates a source on
PLACED = "anchor placed in phase 2"  # the same, by an anchor written after the phase-1 commit: no proof, the checker judges it
SAMPLE_RULES = """\
You are the independent check of the census of {date}: a context that did not do phase 2. Change nothing: edit, record and \
commit nothing.
A source under "Agreed by tool" has every fact that cites it found word for word in its current text: it is not yours.
For each source under "For the checker": judge each of its facts from the passage printed under it, supported or not. Open \
the page (its `read:` line) only when a passage does not settle a fact: no passage, or one that does not say what the fact \
says. A source no fact cites: judge its outcome (gone: the page is gone; superseded: its facts cite the successor). A passage \
marked "anchor placed in phase 2" is the one an anchor written after phase 1 names, for a fact phase 2 may have rewritten: \
judge whether it says what the fact says.
Answer `agree` for a source whose every fact is supported, else `disagree` with the fact (`path:line`) and why.
One line per source of "For the checker": its id, `agree` or `disagree`, and the reason."""


def successor(sid, srcs):
    """The id a chain of `superseded_by` from `sid` ends at: the row whose facts replaced it (`sid` when none did)."""
    seen = {sid}
    while True:
        nxt = ((srcs.get(sid) or {}).get("superseded_by") or "").strip()
        if not nxt or nxt in seen or nxt not in srcs:
            return sid
        seen.add(nxt)
        sid = nxt


def phase1_commit(date):
    """The commit `census.py run` made for the census of `date` (`docs(kb): census DATE phase 1 verdicts`); '' when the
    history holds none."""
    return g(kbcommon.HOME, "log", "-1", "--format=%H", "--fixed-strings", f"--grep=census {date} phase 1 verdicts")[1]


def phase1_keys(commit, rel, cache):
    """The fact keys (`kbfacts.fact_key`) of the facts the file `rel` (root-relative) held at `commit`; None when
    there is no commit or the file was not in it. `cache` ({rel: keys}) keeps what it read."""
    if rel not in cache:
        code, text, _ = g(kbcommon.HOME, "cat-file", "blob", f"{commit}:{kbcommon.repo_rel(rel)}") if commit else (1, "", "")
        units = (kbfacts.md_units if rel.endswith(".md") else kbfacts.csv_units)(rel, text) if code == 0 else []
        cache[rel] = {kbfacts.fact_key(u["text"]) for u in units} if code == 0 else None
    return cache[rel]


def placed_before_phase2(anchor, key, rel, date, commit, cache):
    """True when an anchor can be trusted as a tool's proof in phase 4: its `verified_utc` is a day before the census
    `date` (a census runs in one day, so a same-day anchor is phase 1's or phase 2's), or the fact line is the one the
    phase-1 `commit` held (`phase1_keys`: a reader's rewrite has another key, and no anchor of it predates its edit)."""
    verified = (anchor.get("verified_utc") or "")[:10]
    return bool(verified) and verified < date or key in (phase1_keys(commit, rel, cache) or ())


def current_passage(doc, anchor, claim, cites=1, placed_before=True):
    """(passage, how) of a fact in the source's current text `doc` (`factdiff.Doc`): the anchor's own passage when it is
    there word for word (`WORD`; `PLACED` when `placed_before` is False: the anchor was written after the census's
    phase-1 commit, so possibly by the reader who rewrote the fact, and proves nothing), else the best window
    `Doc.locate` (given the fact's `cites`, the sources it cites) or `Doc.score` gives (`best match`); (None, '') when
    the page holds none."""
    if doc is None:
        return None, ""
    if anchor and anchor.get("status") == "located" and anchor.get("sha") in doc.shas:
        return doc.window(*doc.shas[anchor["sha"]]), WORD if placed_before else PLACED
    win = doc.locate(claim, cites)[0] or doc.score(claim)[0]
    return (doc.window(*win), "best match") if win else (None, "")


def sample_brief(picked, log, a):
    """The phase-4 brief of the sample `picked` ([(group, row)]): per source its citing facts, each with the passage of
    the source's current text (the factdiff document cache, or a fetch) its anchor names; a source whose every fact is
    found word for word by an anchor placed before phase 2's edits (`placed_before_phase2`) is agreed by tool, with that
    proof, and the rest go to the checker with the fact, the passage and the command that reads the source. Returns
    (text, counts)."""
    srcs, facts, anchors = {r["id"]: r for r in read_sources()}, factdiff.cited_facts(), factdiff.read_anchors()
    plan = {r["id"]: successor(r["id"], srcs) for _, r in picked}
    need = sorted({t for t in plan.values() if facts.get(t) and t in srcs})
    docs = factdiff.fetch_all(need, srcs, a.max_age) if need else {}
    cites = factdiff.cite_counts(facts)
    ctx, tool, check = {"providers": provider.providers(factdiff.ROOT)}, [], []
    by_group = {g: Counter() for g in SAMPLE_GROUPS}
    date, phase1 = ql_capture.phase_date(path=log), {}
    commit = phase1_commit(date)
    for group, r in picked:
        tid = plan[r["id"]]
        d = docs.get(tid)
        doc = factdiff.Doc(d["text"]) if d and d.get("status") == 200 and d.get("text") else None
        got = []
        for key, rel, line, text in facts.get(tid, []):
            claim = factdiff.fact_text(text)
            anchor = anchors.get((key, rel, tid))
            before = doc is None or not anchor or anchor.get("status") != "located" \
                or placed_before_phase2(anchor, key, rel, date, commit, phase1)
            passage, how = current_passage(doc, anchor, claim, cites.get((key, rel), 1), before)
            got.append({"at": f"{kbcommon.repo_rel(rel)}:{line}", "claim": claim, "passage": passage, "how": how,
                        "anchor": "located" if anchor and anchor.get("status") == "located" else "not located"})
        head = f"{r['id']}  {group}, outcome {r['outcome'] or '-'}, bucket {r['bucket']}"
        by_group[group]["checked"] += 1
        if got and doc is not None and all(g["how"] == WORD for g in got):
            by_group[group]["agreed by tool"] += 1
            tool.append(f"- {head}: {len(got)} fact(s) found word for word in the current text of "
                        f"{srcs[tid]['url']} (document {tid}, fetched {(d.get('fetched_utc') or '-')[:19]}): "
                        + ", ".join(g["at"] for g in got))
            continue
        out = [f"### {head}", f"- url: {r['url']}"]
        if tid != r["id"]:
            out.append(f"- superseded by {tid}: the facts citing it are checked against {srcs[tid]['url']}")
        if not got:
            out.append(f"- cited by: no fact (outcome {r['outcome'] or 'none'})")
        elif doc is None:
            out.append(f"- current text: not read ({'HTTP ' + str(d['status']) if d and d.get('status') else 'no document'})")
        for n, g in enumerate(got, 1):
            out += [f"  {n}. {g['at']} ({g['anchor']} anchor)", f"     fact: {g['claim']}",
                    f"     passage ({g['how'] or 'none found'}): {g['passage'] or '-'}"]
        out += ["- read:"] + [f"  {c}" for c in read_commands(r, ctx)]
        by_group[group]["for the checker"] += 1
        check.append("\n".join(out))
    n = len(picked)
    groups = "; ".join(f"{g} checked={c['checked']} agreed by tool={c['agreed by tool']} for the checker={c['for the checker']}"
                       for g, c in by_group.items())
    text = "\n\n".join([SAMPLE_RULES.format(date=date),
                         f"checked={n} agreed by tool={len(tool)} for the checker={len(check)}; the checker's passage judgments "
                         f"run on {STEP_MODELS['check']}\nby group, each stated apart in the report: {groups}",
                         "## Agreed by tool\n" + ("\n".join(tool) or "none"),
                         "## For the checker\n\n" + ("\n\n".join(check) or "none")])
    return text, {"checked": n, "agreed by tool": len(tool), "for the checker": len(check)}


def cmd_sample(a, tally):
    if not os.path.isfile(a.log):
        print(f"no census log {a.log}")
        return 2
    picked = sampled(read_log(a.log), a)
    if a.brief:
        text, counts = sample_brief(picked, a.log, a)
        print(text)
        tally.update(counts)
        return 0
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["group", "id", "url", "bucket", "outcome", "evidence", "outcome_note", "used_in"])
    for group, r in picked:
        w.writerow([group, r["id"], r["url"], r["bucket"], r["outcome"], r["evidence"], r["outcome_note"], r["used_in"]])
    return 0


QUEUE_HOSTS = 15  # the hosts the summary's queue block names, most characters first; the rest are one line
FACTDIFF_REVIEW = re.compile(r"factdiff\.py review (factdiff-[\w.-]+\.csv)")


def factdiff_log_rows(rows, log, given=None):
    """The rows of the fact diff log the census used: `given`, else the logs the evidence of `rows` names
    (`factdiff.py review NAME`) beside `log`, else _census/factdiff-<date of log>.csv beside it; [] when none exists."""
    here = os.path.dirname(os.path.abspath(log))
    paths = ([given] if given else [os.path.join(here, n) for n in sorted({m for r in rows for m in FACTDIFF_REVIEW.findall(r["evidence"])})]
             or [os.path.join(here, f"factdiff-{ql_capture.phase_date(path=log)}.csv")])
    return [r for p in paths if os.path.isfile(p) for r in factdiff.read_log(p)]


def phase2_rows(rows):
    """The rows phase 2 reads: bucket not OK, note neither `blocked` nor `lookup hint`, no outcome yet."""
    return [r for r in rows if r["bucket"] != "OK" and r["note"] not in UNREAD and not r["outcome"]]


def review_by_source(ids, fd_rows):
    """{source id: [review item]}: the fact diff items of `fd_rows` for `ids`, each with its old and new passage, read
    with no network (`factdiff.review_items`, offline)."""
    items = defaultdict(list)
    for it in factdiff.review_items(fd_rows, factdiff.sources(), ids, offline=True):
        items[it["source_id"]].append(it)
    return items


def judge_path(log):
    """The judge verdicts' file beside the census log: _census/judge-<date of LOG>.csv."""
    return os.path.join(os.path.dirname(os.path.abspath(log)), f"judge-{ql_capture.phase_date(path=log)}.csv")


def read_judged(log):
    """{(source id, fact key, path): row} of the judge file of `log` (`census.py judge`); {} when there is none."""
    path = judge_path(log)
    if not os.path.isfile(path):
        return {}
    return {(r["source_id"], r["fact"], r["path"]): r for r in kbcommon.load_csv(path, JUDGE_COLS)[1]}


def unsupported(items, judged):
    """`items` (`review_by_source`) without the facts a model call judged supported, a source with none left omitted:
    what phase 2's readers still read. Items of the same facts are the same keys `judge` wrote."""
    out = {}
    for sid, its in items.items():
        keep = [i for i in its if (judged.get((sid, i["key"], i["path"])) or {}).get("verdict") != "supported"]
        if keep:
            out[sid] = keep
    return out


def with_repin_items(items, todo):
    """`items` (`review_by_source`) with the review items `repin_items` gives for the pinned files of `todo` that the fact
    diff holds none for."""
    return {**repin_items(todo, have=items), **items}


def reading_queue(rows, fd_rows, items=None, cited=None):
    """What phase 2 must read, measured with no network and no model: one record per row whose bucket is not OK, whose
    note is not `blocked` and that has no outcome yet: id, host, `facts` (the kb lines naming it, `rag.py src --cited`),
    `mode` (`review`: the fact diff items of `fd_rows` with their passages; `document`: the whole document of
    _cache/factdiff), `chars` read, `items` and `partial` (review items with no old or no new passage), `cached`.
    `items` (`review_by_source`) and `cited` (`kbfacts.cited_lines`) are the lookups a caller already made."""
    todo = phase2_rows(rows)
    if not todo:
        return []
    ids = {r["id"] for r in todo}
    cited = kbfacts.cited_lines(ids) if cited is None else cited
    items = with_repin_items(review_by_source(ids, fd_rows), todo) if items is None else items
    out = []
    for r in todo:
        got, rec = items.get(r["id"]), {"id": r["id"], "host": urlparse(r["url"]).netloc.lower() or "-",
                                         "facts": len(cited.get(r["id"], [])), "items": 0, "partial": 0, "cached": True}
        if got:
            rec.update(mode="review", items=len(got), partial=sum(1 for i in got if i["old"] is None or i["new"] is None),
                       chars=sum(len(factdiff.fact_text(i["fact"])) + len(i["old"] or "") + len(i["new"] or "") for i in got))
        else:
            text = (factdiff.load_json(factdiff.cache_path(r["id"], shared=True)) or {}).get("text") or ""
            rec.update(mode="document", chars=len(text), cached=bool(text))
        out.append(rec)
    return out


def queue_lines(queue):
    """The summary's queue block: totals, then one line per host (most characters first)."""
    tok = lambda n: n // kbusage.CHARS_PER_TOKEN  # noqa: E731
    by = defaultdict(lambda: Counter())
    for q in queue:
        c = by[q["host"]]
        c.update(rows=1, facts=q["facts"], chars=q["chars"], missing=0 if q["cached"] else 1)
    total = sum(q["chars"] for q in queue)
    rev = [q for q in queue if q["mode"] == "review"]
    doc = [q for q in queue if q["mode"] == "document"]
    out = [f"queue (phase 2 reads; no network, no model): rows={len(queue)} facts={sum(q['facts'] for q in queue)} "
           f"chars={total} tokens={tok(total)}",
           f"  review passages: rows={len(rev)} items={sum(q['items'] for q in rev)} "
           f"without a passage={sum(q['partial'] for q in rev)} chars={sum(q['chars'] for q in rev)}",
           f"  whole documents: rows={len(doc)} not cached={sum(1 for q in doc if not q['cached'])} "
           f"chars={sum(q['chars'] for q in doc)}"]
    hosts = sorted(by, key=lambda h: (-by[h]["chars"], h))
    rest = Counter()
    for host in hosts[QUEUE_HOSTS:]:
        rest.update(by[host])
    for host in hosts[:QUEUE_HOSTS]:
        c = by[host]
        out.append(f"  {host}: rows={c['rows']} facts={c['facts']} chars={c['chars']} tokens={tok(c['chars'])} "
                   f"not cached={c['missing']}")
    if rest:
        out.append(f"  {len(hosts) - QUEUE_HOSTS} more hosts: rows={rest['rows']} facts={rest['facts']} chars={rest['chars']} "
                   f"tokens={tok(rest['chars'])} not cached={rest['missing']}")
    return out


def cmd_summary(a, tally):
    rows = read_log(a.log)
    if a.factdiff and not os.path.isfile(a.factdiff):
        print(f"no fact diff log {a.factdiff}")
        return 2
    b = Counter(r["bucket"] for r in rows)
    o = Counter(r["outcome"] or "-" for r in rows)
    nr = Counter(r["note"] or "-" for r in rows if r["bucket"] == "NEEDS-READING")
    print(f"sources={len(rows)} " + " ".join(f"{k}={b[k]}" for k in BUCKETS))
    print("outcomes: " + " ".join(f"{k}={v}" for k, v in sorted(o.items())))
    print("needs-reading by note: " + " ".join(f"{k}={v}" for k, v in sorted(nr.items())))
    hosts = lambda note: Counter(urlparse(r["url"]).netloc.lower() or "-" for r in rows if r["note"] == note)  # noqa: E731
    named = lambda c: " ".join(f"{h}={n}" for h, n in sorted(c.items())) or "none"  # noqa: E731
    print("blocked hosts (denied by this environment's network policy, their sources stay unconfirmed): "
          + named(hosts(BLOCKED)))
    print("dns hosts (name resolution failed twice, a pause apart): " + named(hosts(DNS)))
    print("connect hosts (connection failed twice, a pause apart): " + named(hosts(CONNECT)))
    print("HTTP errors (a status other than 200 that left the source to read): "
          + str(sum(1 for r in rows if r["bucket"] == "NEEDS-READING" and r["http_status"].isdigit() and r["http_status"] != "200")))
    print(f"confirmed (phase 3 would date): {sum(1 for r in rows if confirmed(r))}")
    print("spared by a lookup hint (revalidated by a lookup within its provider's pacing: not asked, not dated): "
          f"{sum(1 for r in rows if r['note'] == HINTED)}")
    todo = phase2_rows(rows)
    items = None
    if todo:
        ids = {r["id"] for r in todo}
        items = with_repin_items(unsupported(review_by_source(ids, factdiff_log_rows(rows, a.log, a.factdiff)), read_judged(a.log)), todo)
    print("\n".join(queue_lines(reading_queue(rows, [], items))))
    return 0


# ---------------------------------------------------------------- judge: review items in batches, one model call each

def judge_queue(rows, log, flog=None):
    """(sources, items) of what `judge` may send: the phase-2 rows that are no pinned file (those go to `repin` and
    a reader) with their fact diff review items, {id: row} and [item] in id order. No network, no model."""
    todo = [r for r in phase2_rows(rows) if r["kind"] not in REPIN_KINDS]
    by = review_by_source({r["id"] for r in todo}, factdiff_log_rows(rows, log, flog) if todo else [])
    srcs = {r["id"]: r for r in sorted(todo, key=lambda r: r["id"]) if by.get(r["id"])}
    return srcs, [it for sid in srcs for it in by[sid]]


def cmd_judge(a, tally):
    rows, err = phase2_args(a)
    if err:
        print(err)
        return 2
    srcs, items = judge_queue(rows, a.log, a.factdiff)
    judged, size = read_judged(a.log), a.batch_size or factdiff.JUDGE_BATCH
    if size < 1 or a.max_budget_usd is not None and a.max_budget_usd <= 0:
        print("--batch-size and --max-budget-usd must be positive")
        return 2
    todo = [it for it in items if (it["source_id"], it["key"], it["path"]) not in judged]
    ask = [todo[i] for i in factdiff.judge_candidates(todo)]
    est = factdiff.judge_estimate(factdiff.judge_batches(ask, size), a.model)
    if a.dry_run:
        print("\n".join(factdiff.estimate_lines(est, a.model, f"{len(srcs)} source(s), {len(items)} review item(s), "
                                                f"{len(items) - len(todo)} judged, {len(todo) - len(ask)} with no new passage")))
        return 0
    if ask and a.max_budget_usd is None and est["cap_usd"] is None:
        print(f"no price for {a.model} (factdiff.JUDGE_PRICE): pass --max-budget-usd")
        return 2
    verdicts, calls = factdiff.judge_items(ask, a.model, size, a.jobs, a.max_budget_usd)
    factdiff.judge_tally(tally, verdicts, calls)
    new = {(ask[i]["source_id"], ask[i]["key"], ask[i]["path"]): {"source_id": ask[i]["source_id"], "fact": ask[i]["key"],
                                                                   "path": ask[i]["path"], "verdict": v["verdict"],
                                                                   "sentence": v["sentence"], "model": a.model, "note": v["note"]}
           for i, v in verdicts.items()}
    judged = {**judged, **new}
    if new:
        kbcommon.write_csv(judge_path(a.log), JUDGE_COLS, sorted(judged.values(), key=lambda r: (kbid.sort_key(r["source_id"]), r["path"], r["fact"])),
                           atomic=True)
    confirmed_ids = []
    for sid, r in srcs.items():
        its = [i for i in items if i["source_id"] == sid]
        if all((judged.get((sid, i["key"], i["path"])) or {}).get("verdict") == "supported" for i in its):
            confirmed_ids.append({"id": sid, "outcome": "confirmed",
                                  "note": f"{len(its)} {JUDGED_NOTE} {a.model} ({os.path.basename(judge_path(a.log))})"})
    if confirmed_ids:
        log_rows = read_log(a.log)
        set_outcomes(log_rows, confirmed_ids, tally)
        write_log(a.log, log_rows)
    counts = Counter(v["verdict"] for v in judged.values() if (v["source_id"], v["fact"], v["path"]) in
                     {(i["source_id"], i["key"], i["path"]) for i in items})
    print(f"judge: {len(srcs)} source(s), {len(items)} review item(s): " + ", ".join(f"{k}={counts[k]}" for k in factdiff.JUDGE_VERDICTS)
          + f", unjudged={len(items) - sum(counts.values())}; {len(confirmed_ids)} source(s) confirmed with no agent")
    print("\n".join(factdiff.judge_lines(calls)))
    return 1 if any(c["error"] for c in calls) else 0


# ---------------------------------------------------------------- compare: a model against a judging step's current one

COMPARE_EFFORT = "medium"  # held equal across models: the Claude Code default of Haiku 5.5, Sonnet 5.5 and Opus 5.5
COMPARE_POINTS = 5  # percentage points of agreement a candidate may lose against the current model
COMPARE_UNCHANGED = 1  # unchanged items of each kind (word for word, best match) drawn for each changed item
COMPARE_FACTS = 4  # facts of one source in a `check` unit
COMPARE_COVER = 0.30  # least cover of a best-match passage an item holds: the lowest band of factdiff's labelled anchor sample
COMPARE_DIR = os.path.join(kbcommon.HOME, "_cache", "census", "compare")  # one result file per step, model and half
CHECK_TASK = """\
You are the independent check of a census of knowledge-base facts: a context that did not rewrite them. Each numbered \
source gives its facts, each with the passage of the source's current text that best matches it. Judge from these \
passages only; you have no page and no tool.
- supported: every fact of the source is stated by its passage: the same claim, wording may differ.
- contradicted: a passage states something that conflicts with a fact.
- not enough information: a passage neither states nor contradicts a fact, or you cannot settle it from it. When in \
doubt choose this: a wrong `supported` is the one error that costs.
`sentence` is the one sentence of a passage that decides the source, copied exactly. Return JSON only: \
{"verdicts": [{"n": 1, "verdict": "supported", "sentence": "..."}]}, one entry per source."""


def rewritten_pairs(base, end):
    """[(path, old line, new line)] of the Markdown and CSV lines the commits `base`..`end` replaced by a line (a hunk of
    as many removed as added lines, paired in order), paths relative to the root under census (a layout with the root
    at the repository's top is read too); ledgers, README.md and dot files left out. Raises ValueError on a bad revision."""
    code, out, err = g(kbcommon.HOME, "diff", "-U0", "--no-color", "--no-renames", base, end, "--", "*.md", "*.csv")
    if code:
        raise ValueError(err or f"git diff {base} {end} failed")
    prefix = kbcommon.repo_rel(KB).rstrip("/") + "/"
    pairs, path, minus, plus = [], None, [], []

    def close():
        if path and minus and len(minus) == len(plus):
            pairs.extend((path, a, b) for a, b in zip(minus, plus))

    for line in out.splitlines():
        if line.startswith("+++ "):
            close()
            minus, plus = [], []
            path = line[6:] if line.startswith("+++ b/") else None
            path = path[len(prefix):] if path and path.startswith(prefix) else path
            if path and (path == "README.md" or any(p.startswith(("_", ".")) for p in path.split("/"))):
                path = None
        elif line.startswith("@@"):
            close()
            minus, plus = [], []
        elif line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:])
        elif line.startswith("+"):
            plus.append(line[1:])
    close()
    return pairs


def half_of(sid):
    """`tune` or `held` for a source id: the parity of the first byte of its sha256, so a source's facts stay in one half
    and the split exists before any prompt is read against it."""
    return "held" if hashlib.sha256(sid.encode("utf-8")).digest()[0] & 1 else "tune"


def labelled_set(rows, base, end, seed=1):
    """The labelled items, from recorded census outcomes only, each `{source_id, key, path, fact, old, new, how, label,
    half}` shaped as a fact diff review item (`fact`, `old`, `new`):
    - changed: a line the commits `base`..`end` rewrote, whose old claim cites a source the census log records `updated`
      (the old claim, the passage of that source's current text it best matches, at COMPARE_COVER at least);
    - unchanged: a fact of a source recorded `confirmed` whose claim stands word for word in its file at `base`, as it
      does at HEAD: its anchor's passage found word for word in the source's current text, or the best match (as
      `current_passage`); for each changed item COMPARE_UNCHANGED of each kind, drawn by a seeded hash.
    The documents are the fact diff cache's: no network, no model."""
    upd = {r["id"] for r in rows if r["outcome"] == "updated"}
    conf = {r["id"] for r in rows if r["outcome"] == "confirmed"}
    docs = {}

    def doc(sid):
        if sid not in docs:
            d = factdiff.load_json(factdiff.cache_path(sid, shared=True)) or {}
            docs[sid] = factdiff.Doc(d["text"]) if d.get("status") == 200 and d.get("text") else None
        return docs[sid]

    def passage_of(sid, anchor, claim, cites=1):
        """(passage, how) as `current_passage`, with a best match below COMPARE_COVER given up."""
        got, how = current_passage(doc(sid), anchor, claim, cites)
        return (None, "") if got and how != WORD and doc(sid).score(claim)[1] < COMPARE_COVER else (got, how)

    changed, seen = [], set()
    for path, old, new in rewritten_pairs(base, end):
        claim = factdiff.fact_text(old)
        if len(claim.split()) < 6 or claim == factdiff.fact_text(new):
            continue
        cited = set(kbid.SOURCE_ID.findall(old))
        for sid in sorted(cited & upd):
            passage, how = passage_of(sid, None, claim, len(cited))
            key = kbfacts.fact_key(old)
            if passage and (sid, path, key) not in seen:
                seen.add((sid, path, key))
                changed.append({"source_id": sid, "key": key, "path": path, "fact": claim, "old": None, "new": passage,
                                "how": how, "label": "changed"})
                break
    prefix = kbcommon.repo_rel(KB).rstrip("/") + "/"
    at_base = {}

    def text_at_base(path):
        if path not in at_base:
            got = next((o for c, o, _ in (g(kbcommon.HOME, "show", f"{base}:{p}") for p in (prefix + path, path)) if c == 0), "")
            at_base[path] = " ".join(kbfacts.TAG.sub(" ", got).split())
        return at_base[path]

    facts, anchors, pool = factdiff.cited_facts(), factdiff.read_anchors(), []
    cites = factdiff.cite_counts(facts)
    for sid in sorted(conf):
        for key, rel, _line, text in facts.get(sid, []):
            claim = factdiff.fact_text(text)
            if len(claim.split()) < 6 or " ".join(claim.split()) not in text_at_base(rel):
                continue
            passage, how = passage_of(sid, anchors.get((key, rel, sid)), claim, cites.get((key, rel), 1))
            if passage:
                pool.append({"source_id": sid, "key": key, "path": rel, "fact": claim, "old": None, "new": passage,
                             "how": how, "label": "unchanged"})
    pool.sort(key=lambda it: hashlib.sha256(f"{seed}:{it['source_id']}:{it['key']}".encode("utf-8")).hexdigest())
    n = COMPARE_UNCHANGED * len(changed)
    out = changed + [it for how in (WORD, "best match") for it in [p for p in pool if p["how"] == how][:n]]
    for it in out:
        it["half"] = half_of(it["source_id"])
    return sorted(out, key=lambda it: (it["label"], kbid.sort_key(it["source_id"]), it["path"], it["key"]))


def check_units(items):
    """One unit per source of `items` for the `check` step: its first COMPARE_FACTS facts (by key) with their passages,
    shaped as a review item whose `fact` and `new` hold them; the source's label and half are its items'."""
    by = defaultdict(list)
    for it in items:
        by[it["source_id"]].append(it)
    out = []
    for sid, its in sorted(by.items(), key=lambda kv: kbid.sort_key(kv[0])):
        its = sorted(its, key=lambda i: i["key"])[:COMPARE_FACTS]
        out.append({"source_id": sid, "key": sid, "path": its[0]["path"], "label": its[0]["label"], "half": its[0]["half"],
                    "facts": [(i["fact"], i["new"]) for i in its], "fact": " ".join(i["fact"] for i in its), "old": None,
                    "new": "\n".join(i["new"] for i in its)})
    return out


def check_prompt(batch):
    """The `check` step's whole input: the task, then each source as `### n` with its facts and passages."""
    parts = [CHECK_TASK]
    for n, u in enumerate(batch, 1):
        parts.append(f"### {n}\n" + "\n".join(f"fact {k}: {f}\npassage {k}: {p}" for k, (f, p) in enumerate(u["facts"], 1)))
    return "\n\n".join(parts)


def compare_rate(model):
    """(USD per MTok in, out) of `model`: factdiff.JUDGE_PRICE, else the benchmark tooling's table (bench_core.PRICE,
    the first tier), else None."""
    if model in factdiff.JUDGE_PRICE:
        return factdiff.JUDGE_PRICE[model]
    try:
        import bench_core
        return tuple(bench_core.PRICE[model][0][1:3])
    except (ImportError, KeyError):
        return None


def compare_estimate(batches, prompt_of, model):
    """`factdiff.judge_estimate`'s record for `batches` of units whose call text is `prompt_of(batch)`, priced by
    `compare_rate`: no network, no model."""
    cpt, rate = kbusage.CHARS_PER_TOKEN, compare_rate(model)
    ins = [len(prompt_of(b)) // cpt + factdiff.JUDGE_CALL_TOKENS for b in batches]
    outs = [len(b) * factdiff.JUDGE_REPLY_TOKENS for b in batches]
    cost = [(i * rate[0] + o * rate[1]) / 1e6 for i, o in zip(ins, outs)] if rate else []
    return {"batches": len(batches), "items": sum(len(b) for b in batches), "input_tokens": sum(ins), "output_tokens": sum(outs),
            "usd": round(sum(cost), 4) if rate else None, "cap_usd": factdiff.call_cap(max(cost)) if cost else None}


def compare_call(prompt, model, cap_usd):
    """`factdiff.judge_call` at COMPARE_EFFORT: the `judge_result` of one tool-less call, with the seconds it took and the
    models its `modelUsage` names (the model actually served, not the one asked for)."""
    t0, models = time.monotonic(), []
    with tempfile.TemporaryDirectory() as cwd:
        try:
            p = subprocess.run([*factdiff.judge_argv(model, cap_usd), "--effort", COMPARE_EFFORT], input=prompt, cwd=cwd,
                               capture_output=True, text=True, encoding="utf-8", timeout=factdiff.JUDGE_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as e:
            return {"verdicts": None, "cost_usd": 0.0, "usage": {}, "error": f"{type(e).__name__}: {e}"[:200],
                    "wall_s": round(time.monotonic() - t0, 1), "models": []}
    got = factdiff.judge_result(p.stdout)
    try:
        use = json.loads(p.stdout).get("modelUsage")
        models = sorted(use) if isinstance(use, dict) else []
    except (ValueError, AttributeError):
        pass
    if got["error"] and not p.stdout.strip():
        got["error"] = (p.stderr.strip().splitlines() or [f"claude -p exited {p.returncode}"])[-1][:200]
    return {**got, "wall_s": round(time.monotonic() - t0, 1), "models": models}


def compare_run(units, prompt_of, model, size, jobs, cap_usd, call=None):
    """(verdicts, calls) of `units` judged in batches of one call each: `verdicts` is {index in `units`: {verdict,
    sentence, note}} (`factdiff.judge_verdicts`, so a `supported` needs its sentence in the passage), `calls` one record per
    batch: {items, cost_usd, usage, error, wall_s, models}. `call` replaces compare_call."""
    call = call or compare_call
    at, batches = 0, []
    for b in factdiff.judge_batches(units, size):
        batches.append((at, b))
        at += len(b)

    def one(job):
        return call(prompt_of(job[1]), model, cap_usd or compare_estimate([job[1]], prompt_of, model)["cap_usd"]
                    or factdiff.JUDGE_CAP_FLOOR_USD)

    with cf.ThreadPoolExecutor(max(1, min(jobs, len(batches) or 1))) as ex:
        replies = list(ex.map(one, batches))
    verdicts, calls = {}, []
    for (start, b), reply in zip(batches, replies):
        got = factdiff.judge_verdicts(b, reply["verdicts"] or [])
        verdicts.update({start + k: v for k, v in got.items()})
        calls.append({"items": len(b), "cost_usd": reply["cost_usd"], "usage": reply["usage"], "wall_s": reply.get("wall_s", 0),
                      "models": reply.get("models", []), "error": reply["error"] or ("" if got or not b else "no entry matched an item")})
    return verdicts, calls


def compare_scores(units, verdicts):
    """The agreement of `verdicts` with the units' labels: a `supported` is the prediction `unchanged`, anything else
    (including no verdict: the unit goes to a reader) `changed`. Counts: units, changed, unchanged, agree, false_confirms
    (a changed unit judged supported, the error that dates a stale fact), false_rejects, unjudged."""
    s = Counter(units=len(units))
    for i, u in enumerate(units):
        v = (verdicts.get(i) or {}).get("verdict")
        predicted = "unchanged" if v == "supported" else "changed"
        s[u["label"]] += 1
        s["agree"] += predicted == u["label"]
        s["false_confirms"] += predicted == "unchanged" and u["label"] == "changed"
        s["false_rejects"] += predicted == "changed" and u["label"] == "unchanged"
        s["unjudged"] += v is None
    return {k: s[k] for k in ("units", "changed", "unchanged", "agree", "false_confirms", "false_rejects", "unjudged")}


def compare_path(step, model, half):
    return os.path.join(COMPARE_DIR, f"{step}-{model}-{half}.json")


def compare_decide(step, model):
    """(lines, default model) of the two held-out results of `step`: the step's current model and `model`. The candidate
    becomes the default only when its false confirms are no more than the current model's and its agreement is within
    COMPARE_POINTS of it; else the line names the bar that failed."""
    cur, res = BASELINE_MODELS[step], {}
    for m in (cur, model):
        try:
            with open(compare_path(step, m, "held"), encoding="utf-8") as f:
                res[m] = json.load(f)
        except (OSError, ValueError):
            return [f"no held-out result of {step} for {m}: run `compare --step {step} --model {m} --half held` first"], None
    c, n = res[cur]["scores"], res[model]["scores"]
    pct = lambda r: 100.0 * r["agree"] / r["units"] if r["units"] else 0.0  # noqa: E731
    fc_ok = n["false_confirms"] <= c["false_confirms"]
    ag_ok = pct(c) - pct(n) <= COMPARE_POINTS
    out = [f"{step}: {m} agreement {r['agree']}/{r['units']} = {pct(r):.1f}%, false confirms {r['false_confirms']}/{r['changed']}, "
           f"usd {sum(x['cost_usd'] for x in res[m]['calls']):.4f}" for m, r in ((cur, c), (model, n))]
    out.append(f"bar false confirms no more than {cur}'s: {'met' if fc_ok else 'FAILED'} ({n['false_confirms']} vs {c['false_confirms']})")
    out.append(f"bar agreement within {COMPARE_POINTS} points of {cur}: {'met' if ag_ok else 'FAILED'} "
               f"({pct(n) - pct(c):+.1f} points)")
    ok = fc_ok and ag_ok
    out.append(f"{step}: default {model}" if ok else f"{step}: keeps {cur}: " + " and ".join(
        b for b, met in (("false confirms above the current model's", fc_ok), (f"agreement more than {COMPARE_POINTS} points below it", ag_ok))
        if not met))
    return out, model if ok else cur


def cmd_compare(a, tally):
    if a.step not in BASELINE_MODELS:
        print(f"--step: one of {', '.join(BASELINE_MODELS)}")
        return 2
    if a.decide:
        lines, default = compare_decide(a.step, a.model)
        print("\n".join(lines))
        return 0 if default else 2
    if not os.path.isfile(a.log):
        print(f"no census log {a.log}")
        return 2
    if not a.half or not a.base or not a.end:
        print("compare needs --half, --from and --to (or --decide)")
        return 2
    size = a.batch_size or factdiff.JUDGE_BATCH
    if size < 1 or a.max_budget_usd is not None and a.max_budget_usd <= 0:
        print("--batch-size and --max-budget-usd must be positive")
        return 2
    try:
        items = labelled_set(read_log(a.log), a.base, a.end, a.seed)
    except ValueError as e:
        print(f"bad revision: {e}")
        return 2
    units = [u for u in (check_units(items) if a.step == "check" else items) if u["half"] == a.half]
    prompt_of = check_prompt if a.step == "check" else factdiff.judge_prompt
    counts = Counter((it["half"], it["label"]) for it in (check_units(items) if a.step == "check" else items))
    print(f"labelled set ({a.step}, seed {a.seed}, {a.base}..{a.end}): " + ", ".join(
        f"{h} {lab}={counts[(h, lab)]}" for h in ("tune", "held") for lab in ("changed", "unchanged")))
    est = compare_estimate(factdiff.judge_batches(units, size), prompt_of, a.model)
    if a.dry_run:
        print("\n".join(factdiff.estimate_lines(est, a.model, f"{a.step} step, {a.half} half, {len(units)} unit(s)")))
        return 0
    if a.max_budget_usd is None and est["cap_usd"] is None:
        print(f"no price for {a.model}: pass --max-budget-usd")
        return 2
    out = compare_path(a.step, a.model, a.half)
    if a.half == "held" and os.path.exists(out) and not a.again:
        print(f"the held-out half was judged once by {a.model} for {a.step} ({kbcommon.repo_rel(out)}): --again judges it again")
        return 2
    t0 = time.monotonic()
    verdicts, calls = compare_run(units, prompt_of, a.model, size, a.jobs, a.max_budget_usd)
    wall = round(time.monotonic() - t0, 1)
    scores = compare_scores(units, verdicts)
    factdiff.judge_tally(tally, verdicts, calls)
    served = sorted({m for c in calls for m in c["models"]})
    record = {"step": a.step, "model": a.model, "served": served, "effort": COMPARE_EFFORT, "half": a.half, "base": a.base,
              "end": a.end, "seed": a.seed, "batch": size, "jobs": a.jobs, "wall_s": wall, "scores": scores, "calls": calls,
              "verdicts": [{"source_id": u["source_id"], "key": u["key"], "label": u["label"],
                            "verdict": (verdicts.get(i) or {}).get("verdict", ""), "note": (verdicts.get(i) or {}).get("note", "")}
                           for i, u in enumerate(units)]}
    os.makedirs(COMPARE_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=1)
    s = scores
    print(f"compare step={a.step} model={a.model} served={','.join(served) or '-'} effort={COMPARE_EFFORT} half={a.half}: "
          f"units={s['units']} changed={s['changed']} unchanged={s['unchanged']} agree={s['agree']}/{s['units']} "
          f"({100.0 * s['agree'] / s['units'] if s['units'] else 0:.1f}%) false-confirms={s['false_confirms']}/{s['changed']} "
          f"false-rejects={s['false_rejects']} unjudged={s['unjudged']} wall={wall}s jobs={a.jobs}")
    print("\n".join(factdiff.judge_lines(calls)))
    return 1 if any(c["error"] for c in calls) else 0


# ---------------------------------------------------------------- groups, brief: phase 2 split by owner

BRIEF_CHARS = 30_000  # characters of one brief part, head and rules included; a source alone over it is a part of its own
UNCITED = "_uncited"  # the group of the rows no domain file names (a domain never starts with `_`)
RESULT_SCHEMA = os.path.join(kbcommon.TOOLS, "census_result.schema.json")  # what a phase-2 group returns; `apply` takes it
SCHEMA_REL = kbcommon.repo_rel(RESULT_SCHEMA)

BRIEF_RULES = """\
For each source with review items below: judge each item as supported, contradicted or not enough information from its old \
and new passage, and read the page only when they do not settle it. For a source gone with no successor (`dead` facts, \
nothing moved), report it: the orchestrator runs `python3 _tools/factdiff.py dead {flog} --source <id>`, which turns the \
facts that cited only it into `[UNK]`, adds the `_gaps.md` entries and marks the row dead with its last Wayback capture.
For each other source: read it in full as it is now with the command under it. Then check every fact in your files that \
cites it (the lines listed under it).
- All facts still hold: outcome `confirmed`.
- A fact changed: rewrite it from the new text (same tag). A live page: keep the id, outcome `updated`. A pinned file or \
release: propose a new row for the new pinned url (the orchestrator writes it with `python3 _tools/kbid.py add`; \
`python3 _tools/kbid.py url <URL>` gives its id), re-point the facts you re-verified, outcome `superseded` with the new \
id in the note.
- Gone or withdrawn: mark the facts `[UNK]`, outcome `gone`, and give a `_gaps.md` bullet (what, where you looked, \
ending `(topic: <domain>/<slug>)`).
- Cannot read it: outcome `unconfirmed` with the reason; change nothing.
- Sources that now disagree with a kb fact you cannot settle: give a `_conflicts.md` bullet ending \
`(topic: <domain>/<slug>)`.
Update each edited article's `sources:` header and `status`. Do not touch `_sources.csv`, `_gaps.md`, `_conflicts.md`, \
the index or any file outside your list, and do not commit. Facts in foreign files that need an edit: describe them.
Rules that hold throughout:
- Read the full page before confirming or changing a fact (`microsoft_docs_fetch` for Learn, the `.mdx` page for Claude \
Code docs, git for pinned files); a review item's old and new passage settle only the item they are printed for.
- Paraphrase Learn text; a quote is 25 words or fewer.
- Placeholders only in every fact you write (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`, tenant \
`00000000-0000-0000-0000-000000000000`): never a real hostname, tenant or object id, address, person or token.
- Never call a docs server's `submit_feedback` tool: it posts outside the repo.
Return JSON only: {{"outcomes": [{{"id", "outcome", "note"}}], "new_rows": [{{all _sources.csv columns}}], \
"superseded": {{"old id": "new id"}}, "gaps": [{{"topic", "text"}}], "conflicts": [{{"topic", "text"}}], \
"foreign_edits": [{{"file", "line", "change"}}], "edited_files": [every file of yours that you edited]}}, valid against \
the JSON Schema `{schema}`; the orchestrator applies it with `python3 _tools/census.py apply {log} --group {group} \
--from <your result>`."""


def domain_of(rel):
    """The domain of a file path relative to the root (its first directory); None for a root-level file (a ledger) or a
    directory named `_*` or `.*`."""
    head, sep, _ = rel.partition("/")
    return head if sep and not head.startswith(("_", ".")) else None


def citing_files(r, cited, root):
    """{file relative to the root: [line]} of the domain files naming the row: the tree's lines (`rag.py src --cited`),
    else, for a row no line names, the files of the log's `used_in` (no lines)."""
    out = defaultdict(set)
    for qpath, n in cited.get(r["id"], []):
        top, _, rel = qpath.partition("/")
        if top == root and domain_of(rel):
            out[rel].add(n)
    if not out:
        for rel in filter(None, r["used_in"].split(";")):
            if domain_of(rel):
                out[rel]
    return {rel: sorted(ns) for rel, ns in sorted(out.items())}


def owner_of(files):
    """The group owning a row: the domain with most of its citing lines (a file with no line counts once), the first
    by name on a tie; UNCITED when no domain file names it."""
    weight = Counter()
    for rel, ns in files.items():
        weight[domain_of(rel)] += len(ns) or 1
    return min(weight, key=lambda d: (-weight[d], d)) if weight else UNCITED


def phase2_context(rows, log, flog=None):
    """What groups and brief share, with no network and no model: the date, the rows phase 2 reads by owner group
    (`members`: group -> [(row, citing files, queue record)]), the fact diff items, the cited lines and the providers."""
    todo = phase2_rows(rows)
    ids = {r["id"] for r in todo}
    fd_rows = factdiff_log_rows(rows, log, flog) if ids else []
    cited = kbfacts.cited_lines(ids) if ids else {}
    judged = read_judged(log) if ids else {}
    items = with_repin_items(unsupported(review_by_source(ids, fd_rows), judged), todo) if ids else {}
    queue = {q["id"]: q for q in reading_queue(rows, fd_rows, items, cited)}
    root, members = os.path.basename(KB), defaultdict(list)
    for r in sorted(todo, key=lambda r: r["id"]):
        files = citing_files(r, cited, root)
        members[owner_of(files)].append((r, files, queue[r["id"]]))
    date = ql_capture.phase_date(path=log)
    flog_rel = os.path.relpath(os.path.abspath(flog), kbcommon.HOME).replace(os.sep, "/") if flog else census_path(f"factdiff-{date}.csv")
    return {"date": date, "root": root, "members": dict(sorted(members.items())), "items": items, "judged": judged, "flog": flog_rel,
            "log": os.path.relpath(os.path.abspath(log), kbcommon.HOME).replace(os.sep, "/"),
            "providers": provider.providers(factdiff.ROOT)}


def foreign_files(group, members):
    """{file: [row id]} of the files outside the group's domain that cite its rows."""
    out = defaultdict(set)
    for r, files, _ in members:
        for rel in files:
            if domain_of(rel) != group:
                out[rel].add(r["id"])
    return {rel: sorted(ids) for rel, ids in sorted(out.items())}


def owned_files(group, members):
    return sorted({rel for _, files, _ in members for rel in files if domain_of(rel) == group})


MEMDOCS_LINE = ("MicrosoftDocs/memdocs is archived: re-source to the live Learn page (microsoft_docs_fetch), "
                "outcome `superseded` with its new row")  # the line of a memdocs pin row that sends the reader to Learn


def read_commands(r, ctx):
    """The lines that read a source in full: git show and git diff of a pinned file in the census clone, else the fetch
    route of its page (Learn: microsoft_docs_fetch; otherwise the provider's raw form of the url)."""
    if r["kind"] in ("raw-pin", "gh-pin") and r["repo"] and r["pin"] and r["path"]:
        clone = kbcommon.repo_rel(os.path.join(REPOS, clone_name(r["repo"]) + ".git"), kbcommon.HOME)
        found = re.search(r"@([0-9a-f]{12})", f"{r['evidence']} {r['proof']}")
        tip = found.group(1) if found else "HEAD"
        moved = r["note"][len("renamed="):] if r["note"].startswith("renamed=") else r["path"]
        out = [f"git -C {clone} show {tip}:{moved}",
               f"git -C {clone} diff {r['pin']}:{r['path']} {tip}:{moved}" if moved != r["path"]
               else f"git -C {clone} diff {r['pin']} {tip} -- {r['path']}"]
        if r["note"] == "memdocs":
            out.append(MEMDOCS_LINE)
        return out
    if r["kind"] == "learn" or urlparse(r["url"]).netloc.lower() == "learn.microsoft.com":
        return [f"microsoft_docs_fetch {r['url']}"]
    url, headers = provider.raw_url(r["url"], provider.for_url(r["url"], ctx["providers"]))
    return [f"fetch {url}" + "".join(f" (header {k}: {v})" for k, v in headers.items())]


def row_block(r, files, q, group, ctx):
    """The brief's text for one source: its row, the lines of the kb that cite it, then its review items or the
    commands that read it."""
    root = ctx["root"]
    out = [f"### {r['id']}  {r['bucket']}", f"- url: {r['url']}", f"- evidence: {r['evidence']}",
           f"- used_in: {r['used_in'] or '-'}"]
    lines = [(rel, n) for rel, ns in files.items() for n in ns]
    if lines:
        out.append(f"- cited by (`python3 _tools/rag.py src {r['id']} --cited`):")
        texts = {}
        for rel, n in lines:
            if rel not in texts:
                texts[rel] = (kbfacts.read(f"{root}/{rel}") or "").splitlines()
            text = texts[rel][n - 1].strip() if n <= len(texts[rel]) else ""
            if text.startswith("sources:"):
                text = "(front matter `sources:`; keep it in step with the facts)"  # a list of ids, not a fact
            out.append(f"  - {kbcommon.repo_rel(rel)}:{n}{' (foreign)' if domain_of(rel) != group else ''} {text}")
    else:
        out.append("- cited by: no domain file names it in the tree"
                   + (f"; the log's used_in lists {r['used_in']}" if r["used_in"] else ""))
    got = ctx["items"].get(r["id"]) if q["mode"] == "review" else None
    if got:
        done = sum(1 for (sid, _, _), j in ctx["judged"].items() if sid == r["id"] and j["verdict"] == "supported")
        out.append("- review items (judge each: supported | contradicted | not enough information)"
                   + (f"; {done} more were judged supported by a model call and are left out" if done else "") + ":")
        for n, it in enumerate(got, 1):
            out += [f"  {n}. {it['outcome']} {kbcommon.repo_rel(it['path'])}:{it['where'].rpartition(':')[2]}"
                    f" ({it['verdict']}; {it['note']})",
                    f"     fact: {factdiff.fact_text(it['fact'])}",
                    f"     old ({it['old_from']}): {it['old'] or '-'}",
                    f"     new ({it['new_from'] or '-'}): {it['new'] or '-'}"]
    else:
        out += ["- read:"] + [f"  {c}" for c in read_commands(r, ctx)]
    return "\n".join(out)


def brief_head(group, part, parts, files, foreign, ctx, n):
    out = [f"You re-verify it-ops-kb sources for the census of {ctx['date']}. Group {group}, part {part} of {parts}: "
           f"{n} source(s), at most {BRIEF_CHARS} characters a part (a source alone over it is a part of its own); the "
           "parts of a group share its files, so run them one after another."]
    out.append("Your files (edit only these): " + (", ".join(kbcommon.repo_rel(f) for f in files) or "none"))
    if foreign:
        out.append("Foreign files (cite your sources, not yours to edit): "
                   + ", ".join(kbcommon.repo_rel(f) for f in foreign))
    out.append("Sources, each with its row (id, url, bucket, evidence, used_in), the lines of the kb that cite it and how "
               "to read it; no lookup call is needed to start:")
    return "\n".join(out)


def brief_packs(group, members, ctx):
    """(packed, rules): the group's `members` packed into parts of at most BRIEF_CHARS (a source alone over it is a part
    of its own), each a list of (member, its block's text) in id order, and the rules text every part ends with."""
    rules = BRIEF_RULES.format(flog=ctx["flog"], schema=SCHEMA_REL, log=ctx["log"], group=group)
    blocks = [(m, row_block(m[0], m[1], m[2], group, ctx)) for m in members]
    fixed = len(brief_head(group, 99, 99, owned_files(group, members), foreign_files(group, members), ctx, 999)) \
        + len(rules) + 4
    packed, cur, size = [], [], fixed
    for b in blocks:
        if cur and size + len(b[1]) + 2 > BRIEF_CHARS:
            packed.append(cur)
            cur, size = [], fixed
        cur.append(b)
        size += len(b[1]) + 2
    packed.append(cur)
    return packed, rules


def part_text(group, packed, rules, ctx, i):
    """The text of part `i` (from 1) of `brief_packs`'s `packed`."""
    part = packed[i - 1]
    mem = [m for m, _ in part]
    return "\n\n".join([brief_head(group, i, len(packed), owned_files(group, mem), foreign_files(group, mem), ctx, len(part)),
                        *(text for _, text in part), rules])


def brief_parts(group, members, ctx):
    """The group's brief as a list of texts, each at most BRIEF_CHARS (a source alone over it is a part of its own):
    the skill's phase-2 brief filled in. A part holds whole sources, in id order; its files are those citing them."""
    packed, rules = brief_packs(group, members, ctx)
    return [part_text(group, packed, rules, ctx, i) for i in range(1, len(packed) + 1)]


def group_records(ctx):
    """The groups of `census.py groups`: per group its rows, owned files, foreign files, queue size and brief parts."""
    out = []
    for group, members in ctx["members"].items():
        qs = [q for _, _, q in members]
        chars = sum(q["chars"] for q in qs)
        out.append({"group": group, "files": owned_files(group, members),
                    "foreign": [{"file": f, "domain": domain_of(f), "rows": ids} for f, ids in foreign_files(group, members).items()],
                    "queue": {"rows": len(members), "facts": sum(q["facts"] for q in qs), "items": sum(q["items"] for q in qs),
                              "chars": chars, "tokens": chars // kbusage.CHARS_PER_TOKEN},
                    "parts": len(brief_parts(group, members, ctx)),
                    "rows": [{"id": r["id"], "url": r["url"], "bucket": r["bucket"], "evidence": r["evidence"],
                              "used_in": [f for f in r["used_in"].split(";") if f], "mode": q["mode"], "facts": q["facts"],
                              "items": q["items"], "chars": q["chars"]} for r, _, q in members]})
    return out


def phase2_args(a):
    """(rows, error): the log's rows, or None and the reason a groups or brief run refuses (exit 2)."""
    if not os.path.isfile(a.log):
        return None, f"no census log {a.log}"
    if a.factdiff and not os.path.isfile(a.factdiff):
        return None, f"no fact diff log {a.factdiff}"
    return read_log(a.log), ""


def cmd_groups(a, tally):
    rows, err = phase2_args(a)
    if err:
        print(err)
        return 2
    ctx = phase2_context(rows, a.log, a.factdiff)
    print(json.dumps({"log": os.path.relpath(os.path.abspath(a.log), kbcommon.HOME).replace(os.sep, "/"),
                      "date": ctx["date"], "root": ctx["root"], "brief_chars": BRIEF_CHARS,
                      "rows": sum(len(m) for m in ctx["members"].values()), "groups": group_records(ctx)}, indent=1))
    return 0


def cmd_brief(a, tally):
    rows, err = phase2_args(a)
    if err:
        print(err)
        return 2
    ctx = phase2_context(rows, a.log, a.factdiff)
    if a.group not in ctx["members"]:
        print(f"no group {a.group!r} in the queue of {a.log}; groups: " + (", ".join(ctx["members"]) or "none"))
        return 2
    parts = brief_parts(a.group, ctx["members"][a.group], ctx)
    if not 1 <= a.part <= len(parts):
        print(f"group {a.group} has {len(parts)} part(s); --part {a.part} is out of range")
        return 2
    print(parts[a.part - 1])
    return 0


# ---------------------------------------------------------------- repin: a pinned file word for word at the newer commit

REPIN_KINDS = ("raw-pin", "raw-ref", "release")  # the kinds whose cited file a newer commit or release can be read for
REPIN_BUCKETS = ("CHANGED", "NEWER-VERSION")


def repin_clone(repo):
    """The census clone of `repo` as it stands, with no fetch (a linked worktree reads the clone's main worktree's), or
    None when there is none."""
    name = clone_name(repo) + ".git"
    for base in (REPOS, os.path.join(kbfacts.clone_home(), "_cache", "census", "repos")):
        if os.path.isdir(os.path.join(base, name)):
            return os.path.join(base, name)
    return None


def rev(d, name):
    """The full commit id that `name` (a tag, a branch or an abbreviated sha) names in the clone, or ''."""
    return g(d, "rev-parse", "-q", "--verify", f"{name}^{{commit}}")[1]


def blob_at(d, commit, path):
    """The bytes of `path` at `commit` in the clone (`cat-file blob`, never `show`: kb/_self/code.md), or None."""
    try:
        p = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"], cwd=d, capture_output=True, timeout=300)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return p.stdout if p.returncode == 0 else None


def retarget(url, ref_parts, new_ref, new_path=None):
    """The raw file url `url` whose ref (`ref_parts` path segments) is `new_ref`, and whose file is `new_path` when the
    file moved."""
    u = urlparse(url)
    segs = u.path.split("/")
    start = 3 if u.netloc.lower() == "raw.githubusercontent.com" else next(
        i + 2 for i in range(len(segs) - 1) if segs[i:i + 2] == ["-", "raw"])
    segs[start:start + ref_parts] = [new_ref]
    if new_path:
        segs[start + 1:] = [quote(p) for p in new_path.split("/")]
    return u._replace(path="/".join(segs)).geturl()


def names_pin(text, names):
    """Whether a fact's text names one of `names` (the pinned tag and the tags of the pinned commit) as a whole word."""
    return any(re.search(rf"(?<![\w.]){re.escape(n)}(?!\w|\.\w)", text) for n in names)


def repin_plan(r, d, facts, anchors):
    """What re-pinning one log row amounts to, read from the census clone `d` with no network and no model, or None for a
    row that is no candidate (a kind outside REPIN_KINDS, a bucket outside REPIN_BUCKETS). A dict with `reason` (why
    nothing can be judged: a release page, no newer commit in the clone, no located anchor), else `matched` and
    `missing`: the facts citing the row (`factdiff.cited_facts` tuples) whose anchor is, or is not, found word for
    word in the file at the newer commit or release (`missing` holds (fact, why)); a fact that names the pinned tag is
    about that version and is `missing` whatever the file says. `ok` is True when nothing is missing."""
    c = classify(r["url"])
    if c["kind"] not in REPIN_KINDS or r["bucket"] not in REPIN_BUCKETS:
        return None
    plan = {"ok": False, "reason": "", "matched": [], "missing": [], "doc": None}
    if not c["path"]:
        plan["reason"] = "the url names a release, not a file of the repository"
        return plan
    if c["kind"] == "raw-pin":
        ref, path, old = c["pin"], c["path"], c["pin"]
    else:
        ref, path = split_ref(d, c["refparts"])
        old = rev(d, f"refs/tags/{ref}")
    npath, new, nref = path, "", ""
    if r["bucket"] == "NEWER-VERSION":
        tag = r["note"][len("newer="):] if r["note"].startswith("newer=") else ""
        new, nref = (rev(d, f"refs/tags/{tag}"), tag) if tag else ("", "")
    else:
        at = re.search(r"@([0-9a-f]{7,40})$", r["proof"] or "")
        new = rev(d, at.group(1)) if at else (tip_for(d, ref)[0] if c["kind"] == "raw-pin" else rev(d, f"refs/heads/{ref}"))
        nref = new
        if r["note"].startswith("renamed="):
            npath = r["note"][len("renamed="):]
    plan.update(path=path, new_path=npath, old=old, new=new, ref=ref, new_ref=nref, parts=len(ref.split("/")))
    if not new or not nref:
        plan["reason"] = "the newer commit or release is not in the clone"
        return plan
    data = blob_at(d, new, npath)
    if data is None:
        plan["reason"] = f"{npath} is not in the clone at {new[:12]}"
        return plan
    plan["url"] = retarget(r["url"], plan["parts"], nref, npath if npath != path else None)
    plan["sha256"] = hashlib.sha256(data).hexdigest()
    text = provider.doc_text(data, "text/plain", plan["url"])
    if text is None:
        plan["reason"] = "the file at the newer commit is not text"
        return plan
    mine = facts.get(r["id"], [])
    known = lambda f: anchors.get((f[0], f[1], r["id"])) or {}  # noqa: E731
    if not any(known(f).get("status") == "located" for f in mine):
        plan["reason"] = "no located anchors"
        return plan
    names = {ref, *(g(d, "tag", "--points-at", old)[1].split() if old else [])}
    names |= {n[1:] for n in names if re.match(r"v\d", n)}
    doc = plan["doc"] = factdiff.Doc(text)
    for f in mine:
        a = known(f)
        if a.get("status") != "located":
            plan["missing"].append((f, "no located anchor"))
        elif names_pin(factdiff.fact_text(f[3]), names):
            plan["missing"].append((f, "the fact names the pinned version"))
        elif a.get("sha") in doc.shas:
            plan["matched"].append(f)
        else:
            plan["missing"].append((f, "not found word for word"))
    plan["ok"] = not plan["missing"]
    return plan


def repin_item(r, plan, f, why, anchors, d, cites=None):
    """The review item (`factdiff.review_items` shape) of one fact of a row that stays in the queue: its old passage
    from the file at the old commit (else the anchor's quote) and its new one from the file at the newer commit.
    `cites` is `factdiff.cite_counts` of the root."""
    key, rel, line, text = f
    a = anchors.get((key, rel, r["id"])) or {}
    old, old_from = None, ""
    if a.get("status") == "located" and plan["old"]:
        data = blob_at(d, plan["old"], plan["path"])
        od = factdiff.Doc(provider.doc_text(data, "text/plain", r["url"]) if data is not None else "")
        if a["sha"] in od.shas:
            old, old_from = od.window(*od.shas[a["sha"]]), f"{plan['old'][:12]}:{plan['path']} in the census clone"
    if old is None and a.get("quote"):
        old, old_from = a["quote"], "anchor quote"
    doc, claim = plan["doc"], factdiff.fact_text(text)
    win = (doc.locate(claim, (cites or {}).get((key, rel), 1))[0] or doc.score(claim)[0]) if doc is not None else None
    new = doc.window(*win) if win else None
    found = len(plan["matched"])
    note = f"{why} at {plan['new'][:12]}; {found} of {found + len(plan['missing'])} fact(s) of the source found word for word"
    outcome = "unanchored" if why == "no located anchor" else "modified" if new is not None else "not-found"
    return {"outcome": outcome, "source_id": r["id"], "url": r["url"], "verdict": "changed", "note": note, "fact": text,
            "where": f"{factdiff.ROOT.name}/{rel}:{line}", "key": key, "path": rel, "old": old, "old_from": old_from,
            "new": new, "new_from": f"{plan['new'][:12]}:{plan['new_path']} in the census clone" if new is not None else ""}


def repin_candidates(rows):
    """The log rows a repin may resolve: a kind in REPIN_KINDS, a bucket in REPIN_BUCKETS, no outcome, not blocked."""
    return [r for r in rows if r["kind"] in REPIN_KINDS and r["bucket"] in REPIN_BUCKETS and not r["outcome"]
            and r["note"] != BLOCKED and r["repo"]]


def repin_items(rows, have=()):
    """{source id: [review item]} for the candidates among `rows` (the ids in `have` excepted) that stay in the queue
    with some facts found word for word at the newer commit or release: only the facts not found, each with its old and
    new passage, read from the census clone with no fetch. A candidate with no clone, no located anchor or nothing
    found has none (the whole document stands); one with every fact found is for `repin` to apply."""
    cand = [r for r in repin_candidates(rows) if r["id"] not in have]
    out, ctx, cites = {}, None, None
    for r in cand:
        d = repin_clone(r["repo"])
        if not d:
            continue
        if ctx is None:
            ctx = (factdiff.cited_facts(), factdiff.read_anchors())
            cites = factdiff.cite_counts(ctx[0])
        plan = repin_plan(r, d, *ctx)
        if plan and not plan["reason"] and plan["missing"] and plan["matched"]:
            out[r["id"]] = [repin_item(r, plan, f, why, ctx[1], d, cites) for f, why in plan["missing"]]
    return out


def fact_key_at(rel, line):
    """The fact key of the unit at `line` of a root file as it stands, or None."""
    for u in kbfacts.units(kbcommon.qualify(factdiff.ROOT, rel)):
        if u["line"] == line and kbfacts.bare(u["path"]) == rel:
            return kbfacts.fact_key(u["text"])
    return None


def unlist_source(rel, sid):
    """Drop `sid` from the inline `sources:` list of a root file's front matter when no other line of the file names it;
    True when the file changed."""
    path = os.path.join(KB, rel)
    text = kbcommon.read(path, newline="")
    lines = (text or "").split("\n")
    end = next((k for k, ln in enumerate(lines[1:40], 1) if ln == "---"), None) if lines[0] == "---" else None
    if end is None:
        return False
    pat = re.compile(rf"(?<![\w-]){re.escape(sid)}(?![\w-])")
    if any(pat.search(ln) for ln in lines[end + 1:]):
        return False
    for k, ln in enumerate(lines[:end]):
        m = re.match(r"^(sources:\s*\[)(.*)(\]\s*)$", ln)
        if m and pat.search(m.group(2)):
            kept = [x.strip() for x in m.group(2).split(",") if x.strip() and x.strip() != sid]
            lines[k] = m.group(1) + ", ".join(kept) + m.group(3)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(lines))
            return True
    return False


def repin_title(title, plan):
    """The title of the new row: the old one with its tag or commit replaced by the new one's, else `<title> at <new>`."""
    label = plan["new_ref"] if not SHA.fullmatch(plan["new_ref"]) else plan["new_ref"][:12]
    for s in (plan["ref"], plan["ref"][:12]):
        if s and s in title:
            return title.replace(s, label)
    return f"{title} at {label}"


def cmd_repin(a, tally):
    """census.py repin LOG: for each pinned file the census marked CHANGED or NEWER-VERSION (raw-pin, raw-ref, release),
    read the newer commit or release from the census clone and, when every fact citing it is found word for word
    there, write the new row (`kbid.add_source`), set `superseded_by` on the old one, re-point the facts and record
    `superseded` with the proof. The rest stays in the phase-2 queue. Exit 0, or 1 when a fact could not be re-pointed,
    2 for a missing log."""
    if not os.path.isfile(a.log):
        print(f"no census log {a.log}")
        return 2
    date, root = a.date or today(), factdiff.ROOT
    rows, srcs = read_log(a.log), {r["id"]: r for r in read_sources()}
    say = lambda msg: print(("would " if a.dry_run else "") + msg, flush=True)  # noqa: E731
    facts, anchors = factdiff.cited_facts(), factdiff.read_anchors()
    by_url = {kbid.normalize_url(s["url"]): s for s in srcs.values()}
    ids_of = {}  # new url -> the id its row has, or will have
    log = {r["id"]: r for r in rows}
    exp_path = kbcommon.data_path("doc2query/expansions.csv")
    exp_head, exp_rows = kbcommon.load_csv(exp_path, ("key", "question")) if os.path.isfile(exp_path) else (None, [])
    exp_before = [dict(r) for r in exp_rows]
    n_sup = n_queued = n_new = n_facts = failed = 0
    files, superseded, added = set(), {}, {}
    for r in sorted(repin_candidates(rows), key=lambda r: kbid.sort_key(r["id"])):
        sid = r["id"]
        if sid not in srcs or (srcs[sid].get("superseded_by") or "").strip():
            continue
        d, err = repo_dir(r["repo"])
        plan = repin_plan(r, d, facts, anchors) if d else {"reason": err, "missing": [], "matched": []}
        if plan is None:
            continue
        if plan["reason"] or plan["missing"]:
            n_queued += 1
            why = plan["reason"] or f"{len(plan['missing'])} of {len(plan['missing']) + len(plan['matched'])} fact(s) not found word for word"
            print(f"repin {sid}: stays in the queue: {why}")
            continue
        url = plan["url"]
        there = by_url.get(kbid.normalize_url(url))
        if there and (there.get("superseded_by") or "").strip():
            n_queued += 1
            print(f"repin {sid}: stays in the queue: {there['id']} ({url}) is itself superseded")
            continue
        new_id = there["id"] if there else ids_of.get(url) or kbid.source_id(url, root.id_prefix)
        old_l, new_l = (plan["old"] or plan["ref"])[:12], plan["new"][:12]
        proof = f"re-pinned to {new_id}: {old_l} -> {new_l}, {len(plan['matched'])} fact(s) found word for word"
        if not there and url not in ids_of:
            row = {"url": url, "title": repin_title(srcs[sid]["title"], plan), "publisher": srcs[sid]["publisher"],
                   "licence": srcs[sid]["licence"], "reuse": srcs[sid]["reuse"],
                   "artifact_sha256": plan["sha256"] if (srcs[sid].get("artifact_sha256") or "").strip() else "",
                   "version_or_date": (f"{plan['new_ref']}; " if not SHA.fullmatch(plan["new_ref"]) else "")
                   + f"commit {plan['new']}; re-pinned {date} from {sid}: {len(plan['matched'])} fact(s) found word for word"}
            say(f"add source {new_id} {url}")
            if not a.dry_run:
                got, why = add_new_row(root, row, date)
                if why:
                    n_queued += 1
                    print(f"repin {sid}: stays in the queue: {why}")
                    continue
                new_id = got
                n_new += 1
            else:
                n_new += 1
        ids_of[url] = new_id
        say(f"re-point {len(plan['matched'])} fact(s) of {sid} to {new_id}: {old_l} -> {new_l}")
        if a.dry_run:
            n_sup += 1
            n_facts += len(plan["matched"])
            continue
        moved, bad = set(), 0
        for key, rel, line, text in plan["matched"]:
            cur = fact_key_at(rel, line) or key  # an earlier source's re-pointing may have reworded this fact
            if not factdiff.repoint(rel, cur, sid, new_id):
                bad += 1
                print(f"repin {sid}: {rel}:{line} could not be re-pointed")
                continue
            nkey = fact_key_at(rel, line)
            for (k, p, s), arow in list(anchors.items()):
                if k == cur and p == rel:
                    del anchors[(k, p, s)]
                    if nkey:
                        moved_row = {**arow, "fact": nkey, "source_id": new_id if s == sid else s}
                        if s == sid:
                            moved_row["verified_utc"] = date
                        anchors[(nkey, p, moved_row["source_id"])] = moved_row
            for e in exp_rows:
                if nkey and e["key"] == cur:
                    e["key"] = nkey
            moved.add(rel)
            n_facts += 1
        for rel in sorted(moved):
            unlist_source(rel, sid)
        files |= moved
        failed += bad
        if not bad:
            superseded[sid] = new_id
            added.setdefault(new_id, set()).update(moved)
            log[sid]["outcome"], log[sid]["outcome_note"] = "superseded", proof[:300]
            n_sup += 1
            print(f"repin {sid}: {proof}")
    tally.update({"superseded": n_sup, "queued": n_queued, "new-rows": n_new, "facts": n_facts})
    print(f"repin {date}: sources superseded={n_sup} left in the queue={n_queued} new source rows={n_new} facts re-pointed={n_facts}"
          + (" (dry run: nothing written)" if a.dry_run else ""))
    if a.dry_run:
        return 0
    if superseded:
        hdr, srows = kbcommon.load_csv(kbcommon.SOURCES, ("id",))
        for s in srows:
            if s["id"] in superseded:
                s["superseded_by"] = superseded[s["id"]]
            if s["id"] in added:
                s["used_in"] = ";".join(sorted({*filter(None, s["used_in"].split(";")), *added[s["id"]]}))
        kbcommon.write_csv(os.path.join(KB, kbcommon.SOURCES), hdr, srows, atomic=True)
        write_log(a.log, rows)
    if files:
        factdiff.write_anchors(anchors)
    if exp_rows != exp_before:
        kbcommon.write_csv(exp_path, exp_head, exp_rows, atomic=True)
    if a.commit and superseded:
        paths = [os.path.join(KB, p) for p in (kbcommon.SOURCES, kbcommon.ANCHORS, kbcommon.data_rel("doc2query/expansions.csv"))]
        paths += [os.path.abspath(a.log)] + [os.path.join(KB, p) for p in sorted(files)]
        if g(kbcommon.HOME, "add", "--", *[p for p in paths if os.path.exists(p)])[0]:
            print("git add failed; nothing committed")
            return 1
        msg = (f"docs(kb): census {date}: re-pin {len(superseded)} source(s)\n\ncensus.py repin on "
               f"{os.path.relpath(os.path.abspath(a.log), kbcommon.HOME)}: {n_facts} fact(s) found word for word at the newer "
               f"commit or release and re-pointed to {len(set(superseded.values()))} source row(s); no model read them.\n")
        if g(kbcommon.HOME, "commit", "-q", "-m", msg, "--trailer", f"KB-Verified: {date}")[0]:
            print("git commit failed (hooks or nothing to commit)")
            return 1
        print("committed with KB-Verified: " + date)
    return 1 if failed else 0


# ---------------------------------------------------------------- run, finish: the phases no model decides

TOOLS_REL =kbcommon.repo_rel(kbcommon.TOOLS, kbcommon.HOME)  # `_tools`: the steps run from the repository's root
LEDGER = re.compile(r"kb/[^/]+/_decisions\.csv")  # what kbdecide.py sweep writes, in every root and in kb/_self


# ---------------------------------------------------------------- apply: a group's phase-2 result, by tool

JSON_TYPES = {"object": dict, "array": list, "string": str, "integer": int}
IGNORED_COLS = ("retrieved_utc", "used_in", "superseded_by")  # new_rows columns `kbid.py add` and `kbgit.py fix` own


def schema_errors(value, schema, where="$"):
    """The errors of `value` against `schema`, one string each naming where (`$.outcomes[2].outcome`). The subset of
    JSON Schema census_result.schema.json uses: type, enum, minLength, minimum, pattern, required, properties,
    additionalProperties (false or a schema) and items."""
    want = schema.get("type")
    if want and (not isinstance(value, JSON_TYPES[want]) or (want == "integer" and isinstance(value, bool))):
        return [f"{where}: want {want}, got {type(value).__name__}"]
    out = []
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{where}: {value!r} is not one of {', '.join(map(str, schema['enum']))}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            out.append(f"{where}: is empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, int) and not isinstance(value, bool) and value < schema.get("minimum", value):
        out.append(f"{where}: {value} is below {schema['minimum']}")
    if isinstance(value, dict):
        props, extra = schema.get("properties", {}), schema.get("additionalProperties", True)
        out += [f"{where}: missing {k}" for k in schema.get("required", []) if k not in value]
        for k, v in value.items():
            if k in props:
                out += schema_errors(v, props[k], f"{where}.{k}")
            elif extra is False:
                out.append(f"{where}: unexpected {k}")
            elif isinstance(extra, dict):
                out += schema_errors(v, extra, f"{where}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            out += schema_errors(v, schema["items"], f"{where}[{i}]")
    return out


def head_cited_lines(ids):
    """`kbfacts.cited_lines` as the files stand at HEAD: {id: [(qualified path, line)]}. A group's rows are the same
    before and after its worker rewrote the facts (a fact re-pointed to a new row no longer names the old id), so the
    owner of a row is read from the tree the worker started from, as `git grep` finds it; the working tree when git
    cannot say."""
    if not ids:
        return {}
    kb = kbcommon.repo_rel(kbcommon.KB_DIR, kbcommon.HOME)
    code, out, _ = g(kbcommon.HOME, "grep", "-n", "-I", "-E", "|".join(sorted(map(re.escape, ids))), "HEAD", "--", kb)
    if code not in (0, 1):
        return kbfacts.cited_lines(ids)
    found = defaultdict(list)
    for ln in out.splitlines():
        path, _, rest = ln.removeprefix("HEAD:").partition(":")
        n, _, text = rest.partition(":")
        if n.isdigit() and path.startswith(kb + "/"):
            for i in set(kbfacts.ID.findall(text)) & set(ids):
                found[i].append((path[len(kb) + 1:], int(n)))
    return found


def group_scope(rows, cited=None):
    """{group: [(row, citing files)]} of every row phase 2 reads, whether or not it has an outcome yet (a second apply
    finds its group again), owners as the tree at HEAD gives them."""
    scope = [r for r in rows if r["bucket"] != "OK" and r["note"] not in UNREAD]
    cited = head_cited_lines({r["id"] for r in scope}) if cited is None else cited
    root, groups = os.path.basename(KB), defaultdict(list)
    for r in sorted(scope, key=lambda r: r["id"]):
        files = citing_files(r, cited, root)
        groups[owner_of(files)].append((r, files))
    return dict(sorted(groups.items()))


def owned_shown(group, scope):
    """{path as the brief prints it (relative to the repository): path relative to the root} of the files `group` owns."""
    return {kbcommon.repo_rel(rel): rel for _, files in scope.get(group, []) for rel in files if domain_of(rel) == group}


def trial_rows(new_rows, root, today=None):
    """([problem], [id]): the rows of `new_rows` added with `kbid.add_source`, what `kbid.py add` writes, to a scratch
    copy of the root's _sources.csv, so what it would refuse is named and nothing is written. `today` as for add_source."""
    out, ids = [], []
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(root.path, kbcommon.SOURCES), tmp)
        scratch = types.SimpleNamespace(path=tmp, name=root.name, id_prefix=root.id_prefix)
        for n, row in enumerate(new_rows):
            sid, why = add_new_row(scratch, row, today)
            ids.append(sid)
            if why:
                out.append(f"new_rows[{n}] {row.get('url')}: {why}")
    return out, ids


def add_new_row(root, row, today=None):
    """(id, '') after adding the row through `kbid.add_source` (the id is the one already there when it is), else
    ('', what kbid refused)."""
    try:
        sid, _ = kbid.add_source(root, row["url"], row["title"], row["publisher"], row["licence"], row["reuse"],
                                 row.get("version_or_date", ""), row.get("artifact_sha256", ""), today)
    except ValueError as e:
        return "", f"refused: {e}"
    if row.get("id") and row["id"] != sid:
        return sid, f"id {row['id']} is not the id kbid.py gives the url ({sid})"
    return sid, ""


def result_problems(res, group, scope, log, sources, root, today=None):
    """([problem], [new row id]) of a result that matches the schema, each problem naming what it found: a source id
    the log or `_sources.csv` does not know or another group's, an outcome without its pair, a new row `kbid.py add`
    refuses, an edited file outside the group's owned files, a gap or conflict topic that is no article. Nothing is
    written."""
    out = []
    mine = {r["id"] for r, _ in scope.get(group, [])}
    owner = {r["id"]: grp for grp, ms in scope.items() for r, _ in ms}
    shown = owned_shown(group, scope)
    new_problems, new_ids = trial_rows(res["new_rows"], root, today)
    out += new_problems
    known = set(sources) | set(new_ids)
    seen = set()
    for i, o in enumerate(res["outcomes"]):
        sid = o["id"]
        if sid not in log:
            out.append(f"outcomes[{i}]: unknown source id {sid} (not in the census log)")
        elif sid not in mine:
            out.append(f"outcomes[{i}]: {sid} is " + (f"a row of group {owner[sid]}, not of {group}" if sid in owner
                                                       else "no phase-2 row of the log (bucket OK or blocked)"))
        if sid in seen:
            out.append(f"outcomes[{i}]: a second outcome for {sid}")
        seen.add(sid)
    for old, new in res["superseded"].items():
        if old not in sources or old not in mine:
            out.append(f"superseded {old}: unknown source id" if old not in sources else f"superseded {old}: not a row of group {group}")
        elif not any(o["id"] == old and o["outcome"] == "superseded" for o in res["outcomes"]):
            out.append(f"superseded {old}: the outcomes hold no `superseded` outcome for it")
        elif sources[old].get("superseded_by") not in ("", None, new):
            out.append(f"superseded {old}: already superseded by {sources[old]['superseded_by']}")
        if new not in known:
            out.append(f"superseded {old}: unknown source id {new} (not in _sources.csv, not a new row)")
    out += [f"outcomes: {o['id']} is `superseded` and `superseded` has no entry for it" for o in res["outcomes"]
            if o["outcome"] == "superseded" and o["id"] not in res["superseded"]]
    for f in res["edited_files"]:
        if f not in shown and f not in shown.values():
            out.append(f"edited_files: {f} is outside the files group {group} owns"
                       + (f" ({', '.join(sorted(shown))})" if shown else " (it owns none)"))
    for kind in ("gaps", "conflicts"):
        for i, e in enumerate(res[kind]):
            if not os.path.isfile(os.path.join(KB, e["topic"] + ".md")):
                out.append(f"{kind}[{i}]: topic {e['topic']} is no article ({e['topic']}.md)")
    return out, new_ids


def edited_rel(res, group, scope):
    """The root-relative paths of the result's `edited_files` (each given as the brief printed it, or relative to the
    root), sorted, once each."""
    shown = owned_shown(group, scope)
    return sorted({shown.get(f, f) for f in res["edited_files"]})


def ledger_with(text, entries):
    """`text` of a ledger (_gaps.md, _conflicts.md) with each (topic, bullet) added under its `## <topic>` heading, after
    the heading's last line, or under a new heading at the end; a bullet already in the file is skipped, so a second run
    writes the same bytes."""
    lines = text.rstrip("\n").split("\n")
    for topic, bullet in entries:
        if bullet in lines:
            continue
        head = f"## {topic}"
        if head in lines:
            at = lines.index(head) + 1
            end = next((i for i in range(at, len(lines)) if lines[i].startswith("## ")), len(lines))
            while end > at and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = ["", bullet] if end == at else [bullet]
        else:
            lines += ["", head, "", bullet]
    return "\n".join(lines) + "\n"


def bullet_of(entry):
    """The ledger bullet of a gap or conflict entry: its text on one line, ending `(topic: <topic>)`."""
    text = " ".join(entry["text"].split()).removeprefix("- ")
    return "- " + (text if f"(topic: {entry['topic']})" in text else f"{text} (topic: {entry['topic']})")


def foreign_lines(res):
    return [f"foreign edit (not applied): {e['file']}:{e['line']} {e['change']}" for e in res["foreign_edits"]]


def plan_apply(root, edited):
    """The steps of `census.py apply` after its writes: the anchors of the edited articles, the index, the stale
    expansion keys (`doc2query.py stale` exits 1 for some: no failure, `prune` removes them)."""
    ra = root_args(root)
    anchor = [step("anchor", "factdiff.py", *ra, "anchor", *[x for f in edited for x in ("--file", f)])] if edited else []
    return [*anchor, step("index", "build_index.py", *ra), step("stale", "doc2query.py", *ra, "stale", ok=(0, 1))]


def cmd_apply(a, tally):
    """census.py apply: validate the result, then write it; the exit code (0, 2 refused, else the failing step's)."""
    fail = lambda msg: print(msg, file=sys.stderr) or 2  # noqa: E731
    if not os.path.isfile(a.log):
        return fail(f"no census log {a.log}")
    try:
        with open(a.from_json, encoding="utf-8") as f:
            res = json.load(f)
        with open(RESULT_SCHEMA, encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, ValueError) as e:
        return fail(f"cannot read {a.from_json} or the schema {SCHEMA_REL}: {e}")
    rows, root = read_log(a.log), factdiff.ROOT
    scope = group_scope(rows)
    if a.group not in scope:
        return fail(f"no group {a.group!r} in {a.log}; groups: " + (", ".join(scope) or "none"))
    problems = schema_errors(res, schema)
    sources = {r["id"]: r for r in read_sources()}
    new_ids = []
    if not problems:
        problems, new_ids = result_problems(res, a.group, scope, {r["id"]: r for r in rows}, sources, root)
    if problems:
        return fail(f"refused: {len(problems)} problem(s) in {a.from_json}, nothing written:\n" + "\n".join(f"  {p}" for p in problems))
    dry, say = a.dry_run, lambda msg: print(("would " if a.dry_run else "") + msg, flush=True)  # noqa: E731
    for row, sid in zip(res["new_rows"], new_ids):
        extra = [c for c in IGNORED_COLS if row.get(c)]
        if sid in sources:
            say(f"keep source {sid} {row['url']}: already in _sources.csv")
            continue
        say(f"add source {sid} {row['url']}" + (f" (not taken from the row: {', '.join(extra)})" if extra else ""))
        if not dry:
            add_new_row(root, row)
    if res["superseded"]:
        for old, new in sorted(res["superseded"].items()):
            say(f"set superseded_by of {old} to {new}")
        if not dry:
            path = os.path.join(KB, kbcommon.SOURCES)
            header, srcs = kbcommon.parse_csv(kbcommon.SOURCES, kbcommon.read(path, newline="", strict=True), ("id",))
            for r in srcs:
                r["superseded_by"] = res["superseded"].get(r["id"], r["superseded_by"])
            kbcommon.write_csv(path, header, srcs, atomic=True)
    for kind, name in (("gaps", kbcommon.GAPS), ("conflicts", kbcommon.CONFLICTS)):
        entries = [(e["topic"], bullet_of(e)) for e in res[kind]]
        for topic, bullet in entries:
            say(f"write under `## {topic}` in {name}: {bullet[:100]}")
        if entries and not dry:
            path = os.path.join(KB, name)
            text = kbcommon.read(path, newline="", strict=True) or ""
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(ledger_with(text, entries))
    counts = Counter(o["outcome"] for o in res["outcomes"])
    say(f"record {len(res['outcomes'])} outcome(s) in {a.log}: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"))
    if not dry and res["outcomes"]:
        set_outcomes(rows, res["outcomes"], tally)
        write_log(a.log, rows)
    print("\n".join(foreign_lines(res)) or "no foreign edits")
    root_name = os.path.basename(KB)
    rerun = shlex.join(["python3", f"{TOOLS_REL}/census.py", *root_args(root_name), "apply", a.log, "--group", a.group, "--from", a.from_json])
    code, _ = drive(plan_apply(root_name, edited_rel(res, a.group, scope)), kbcommon.repo_rel("."), False, dry, rerun)
    return code


# ---------------------------------------------------------------- dispatch: a group's brief part as a capped headless session

DISPATCH_MODEL = "claude-sonnet-5-5"  # pinned; Haiku 5.5 was measured against it on held-out phase-2 groups and met neither
# the agreement bar nor the usable-result bar (kb/_self/reports/fact-diff.md), so a group is read on this, not the orchestrator's
DISPATCH_TURNS = 150  # --max-turns of one brief part's session (print mode: an error at the limit, no limit by default)
DISPATCH_BUDGET_USD = 5.0  # --max-budget-usd of one brief part's session (a hard cap, subagent spend included)
DISPATCH_TIMEOUT_S = 3600  # the session is stopped after this long and its group stays unapplied
DISPATCH_DIR = os.path.join(kbcommon.HOME, "_cache", "census", "dispatch")  # <date>/<group>/: RESULTS.json, the reply, stderr
DISPATCH_ENV_DROP = ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR", "KB_INDEX")  # as bench_core.no_plugin_env
DISPATCH_STOPS = {"error_max_turns": "hit the turn cap (--max-turns)",
                  "error_max_budget_usd": "hit the dollar cap (--max-budget-usd)",
                  "error_max_structured_output_retries": "gave no result that fits the schema"}
DISPATCH_BASE_TOKENS = 15_000  # what a headless session holds before the brief: its system prompt, tool definitions, run context
DISPATCH_PAGE_CHARS = 26_000  # a whole document no cache holds (the 2026-09-26 queue's mean: 9,739,477 characters, 367 rows)
DISPATCH_TURNS_PER_ROW = 4  # a source takes about a fetch, a read of each citing file, an edit and a note
DISPATCH_REPLY_TOKENS = 800  # output of one turn, its thinking included (Haiku 5.5 cannot turn thinking off)
DOCS_MCP = os.path.join(kbcommon.HOME, ".claude-plugin", "it-ops-kb-docs", ".mcp.json")
LEARN_SERVER, LEARN_TOOL = "microsoft-learn", "mcp__microsoft-learn__microsoft_docs_fetch"
FETCHABLE = re.compile(r"[A-Za-z0-9._~:/?#@&+=%,;-]+")  # a url a Bash permission rule holds as written
FETCH_HEADER = re.compile(r"[A-Za-z0-9._/+=;,: -]+")  # a `Name: value` header a rule holds as written
FETCH_LINE = re.compile(r"fetch (\S+)((?: \(header [^:()]+: [^()]*\))*)")  # the line `read_commands` prints for a page
HEADER = re.compile(r"\(header ([^:()]+): ([^()]*)\)")


def claude_exe(path=None):
    """The `claude` on PATH ($PATH, else `path`), never one in the current directory: only absolute entries other than
    the current directory count (a relative or empty entry names a directory of the working tree; Windows tries the
    current directory first). None when none is found."""
    here = os.path.realpath(os.getcwd())
    dirs = [d for d in (os.environ.get("PATH", "") if path is None else path).split(os.pathsep)
            if os.path.isabs(d) and os.path.realpath(d) != here]
    found = shutil.which("claude", path=os.pathsep.join(dirs))
    return found if found and os.path.dirname(os.path.realpath(found)) != here else None


def dispatch_estimate(prompt_chars, queue, model, turns):
    """What one brief part's session reads and costs, with no network and no model: {turns, input_tokens,
    output_tokens, usd, cap_usd}, `usd` and `cap_usd` None for a model with no price (bench_core.PRICE). `queue` is the
    part's records of `reading_queue`: a review row counts its passages, a document row its cached text or, for a
    document no cache holds, DISPATCH_PAGE_CHARS. The pages are written to the cache once and the context is read back
    on every turn at half its final size, so the figure is one run's list price, not a bound: `cap_usd` is
    factdiff.call_cap of it, the --max-budget-usd a run takes."""
    cpt = kbusage.CHARS_PER_TOKEN
    pages = sum((q["chars"] if q["cached"] or q["mode"] == "review" else DISPATCH_PAGE_CHARS) // cpt for q in queue)
    start = DISPATCH_BASE_TOKENS + prompt_chars // cpt
    n = max(1, min(turns, 2 + DISPATCH_TURNS_PER_ROW * len(queue)))
    est = {"turns": n, "input_tokens": start + pages + n * (start + pages // 2), "output_tokens": n * DISPATCH_REPLY_TOKENS,
           "usd": None, "cap_usd": None}
    try:
        import bench_core
        p = bench_core.PRICE[model][bench_core.tier_of(model, start + pages)]
    except (ImportError, KeyError):
        return est
    est["usd"] = round(((start + pages) * bench_core.write_rate(p) + n * (start + pages // 2) * p[4]
                        + est["output_tokens"] * p[2]) / 1e6, 4)
    est["cap_usd"] = factdiff.call_cap(est["usd"])
    return est


def dispatch_env():
    """The child's environment, passed explicitly: this process's without the plugin and project variables."""
    return {k: v for k, v in os.environ.items() if k not in DISPATCH_ENV_DROP}


def docs_mcp_config():
    """The `--mcp-config` JSON of the Microsoft Learn server alone (from the docs plugin's `.mcp.json`), else None."""
    try:
        with open(DOCS_MCP, encoding="utf-8") as f:
            server = json.load(f)["mcpServers"][LEARN_SERVER]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return json.dumps({"mcpServers": {LEARN_SERVER: server}}, separators=(",", ":"))


def dispatch_plan(group, members, ctx):
    """What one brief part's session may touch, from the part's rows: {files: the group's owned files in it (absolute),
    clones: the census clones its `git show` and `git diff` commands read, fetch: {row id: the `curl` argv of its page},
    learn: [row id] read with the Learn tool, skipped: [row id] whose page no permission rule can name exactly}."""
    clones, fetch, learn, skipped = set(), {}, set(), []
    for r, _, _ in members:
        for line in read_commands(r, ctx):
            git, page = re.match(r"git -C (\S+) (?:show|diff) ", line), FETCH_LINE.fullmatch(line)
            if git:
                clones.add(os.path.join(kbcommon.HOME, git.group(1)))
            elif line.startswith("microsoft_docs_fetch ") or line == MEMDOCS_LINE:
                learn.add(r["id"])
            elif page:
                heads = HEADER.findall(page.group(2))
                if FETCHABLE.fullmatch(page.group(1)) and all(FETCH_HEADER.fullmatch(f"{k}: {v}") for k, v in heads):
                    fetch[r["id"]] = ["curl", "-sSL", *[x for k, v in heads for x in ("-H", f"{k}: {v}")], page.group(1)]
                else:
                    skipped.append(r["id"])
    return {"files": [os.path.join(KB, rel) for rel in owned_files(group, members)], "clones": sorted(clones),
            "fetch": fetch, "learn": sorted(learn), "skipped": skipped}


def worktrees_file(files):
    """The first of `files` (absolute paths) whose own path or real path holds `.claude/worktrees`, else None: the claude
    CLI denies under `dontAsk` the Edit rule of a file there (found in a checkout `git worktree add` made under that
    directory), so a session started from such a checkout edits nothing."""
    for path in files:
        for p in (path, os.path.realpath(path)):
            parts = p.replace("\\", "/").split("/")
            if any(a == ".claude" and b == "worktrees" for a, b in zip(parts, parts[1:])):
                return path
    return None


def dispatch_rules(plan, scratch):
    """(allow, tools) of a session: the `--allowedTools` rules and the `--tools` set. Read and Edit rules name each
    owned file as an absolute path (`//` is the filesystem root), so no other repository file is readable or editable
    (the working directory is the empty scratch directory, and `dontAsk` denies the rest); Bash holds only the clone's
    `git show` and `git diff`, each page's own `curl` line and `kbid.py url`."""
    def at(tool, path, tail=""):
        return f"{tool}(//{path.replace(os.sep, '/').lstrip('/')}{tail})"

    allow = []
    for path in plan["files"]:
        allow += [at("Read", path), at("Edit", path)]
    allow += [at(tool, scratch, "/**") for tool in ("Read", "Edit", "Write")]
    for clone in plan["clones"]:
        allow += [f"Bash({shlex.join(['git', '-C', clone, verb])} *)" for verb in ("show", "diff")]
    allow += sorted({f"Bash({shlex.join(argv)})" for argv in plan["fetch"].values()})
    allow.append(f"Bash({shlex.join(['python3', os.path.join(kbcommon.TOOLS, 'kbid.py'), 'url'])} *)")
    if plan["learn"]:
        allow.append(LEARN_TOOL)
    return allow, ["Read", "Edit", "Write", "Grep", "Bash"]


def dispatch_argv(exe, model, turns, usd, schema_text, allow, tools, mcp):
    """The `claude -p` argument list of a part's session: no hooks, user settings or MCP servers but the Learn one,
    nothing saved, `--output-format json` with `--json-schema` (the result as `structured_output`), the turn and
    dollar caps, `dontAsk` (a tool no rule allows is denied: nobody is there to answer) and the rules last, as
    `--allowedTools` takes every argument after it. The brief goes on stdin."""
    return [exe, "-p", "--model", model, *kbcommon.NO_HOOKS, "--setting-sources", "project,local", "--strict-mcp-config",
            *(["--mcp-config", mcp] if mcp else []), "--no-session-persistence", "--output-format", "json",
            "--json-schema", schema_text, "--max-turns", str(turns), "--max-budget-usd", f"{usd:.2f}",
            "--permission-mode", "dontAsk", "--tools", ",".join(tools), "--allowedTools", *allow]


def dispatch_prompt(brief, plan, scratch):
    """The session's stdin: what the run allows (the brief's paths are relative to the repository root, and its
    `fetch` and `git` lines are the commands below), then the brief."""
    out = ["Run context (census.py dispatch; not part of the brief below):",
           f"- The repository root is {kbcommon.HOME}: every path in the brief is relative to it, so give each tool "
           f"the absolute path. Your working directory is {scratch}, an empty scratch directory: write throwaway "
           "files only there.",
           "- You run unattended in permission mode dontAsk: a tool, file or command not named here is denied. Do "
           "not look for another route: record that source as `unconfirmed` with the reason.",
           "- Files you may read and edit: " + (", ".join(plan["files"]) or "none") + ".", "- Commands you may run:"]
    out += [f"  - {shlex.join(['git', '-C', c, 'show'])} <revision>:<path>, and {shlex.join(['git', '-C', c, 'diff'])} "
            "<arguments> (the brief's relative `git -C` lines, with this absolute path)" for c in plan["clones"]]
    out += [f"  - {sid}: {shlex.join(argv)} (what the brief's `fetch` line for it means; write it exactly so)"
            for sid, argv in sorted(plan["fetch"].items())]
    out.append(f"  - {shlex.join(['python3', os.path.join(kbcommon.TOOLS, 'kbid.py'), 'url'])} <URL> (the id of a new row)")
    if plan["learn"]:
        out.append(f"- `microsoft_docs_fetch <url>` in the brief is the tool `{LEARN_TOOL}`.")
    if plan["skipped"]:
        out.append("- No command can read these sources here (a url with characters a permission rule cannot hold, or "
                   "no Learn tool): " + ", ".join(plan["skipped"]) + ". Judge them from their review items; with "
                   "none, `unconfirmed`.")
    return "\n".join(out) + "\n\n" + brief


def dispatch_reply(stdout, schema):
    """{result, cost_usd, usage, models, turns, error} of a `claude -p --output-format json` reply: `result` is the
    `structured_output` (else the JSON object in `result`) when it is valid against `schema`, else None with `error`
    naming why: a cap, an error result, no JSON, or the first problems against the schema."""
    out = {"result": None, "cost_usd": 0.0, "usage": {}, "models": [], "turns": 0, "error": ""}
    try:
        r = json.loads(stdout)
    except ValueError:
        r = None
    if not isinstance(r, dict):
        out["error"] = "stdout is no JSON result"
        return out
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    out["cost_usd"] = float(r["total_cost_usd"]) if num(r.get("total_cost_usd")) else 0.0
    out["turns"] = int(r["num_turns"]) if num(r.get("num_turns")) else 0
    use = r.get("usage") if isinstance(r.get("usage"), dict) else {}
    out["usage"] = {name: use[key] for key, name in factdiff.JUDGE_USAGE
                    if isinstance(use.get(key), int) and not isinstance(use.get(key), bool) and use[key] > 0}
    out["models"] = sorted(r["modelUsage"]) if isinstance(r.get("modelUsage"), dict) else []
    kind = str(r.get("subtype", ""))
    if kind in DISPATCH_STOPS:
        out["error"] = DISPATCH_STOPS[kind]
        return out
    if r.get("is_error") or kind.startswith("error"):
        errs = r.get("errors")
        errs = "; ".join(str(e) for e in errs) if isinstance(errs, list) else errs
        out["error"] = str(errs or r.get("result") or kind or "claude -p failed")[:200]
        return out
    got = r.get("structured_output")
    if got is None and isinstance(r.get("result"), str):
        a, b = r["result"].find("{"), r["result"].rfind("}")
        try:
            got = json.loads(r["result"][a:b + 1]) if 0 <= a < b else None
        except ValueError:
            got = None
    if not isinstance(got, dict):
        out["error"] = "the reply holds no JSON result"
        return out
    problems = schema_errors(got, schema)
    if problems:
        out["error"] = f"the result breaks the schema ({len(problems)} problem(s)): " + "; ".join(problems[:3])
        return out
    out["result"] = got
    return out


def dispatch_call(argv, prompt, cwd, env):
    """(stdout, stderr's last line or the reason there is none, exit code or None) of one session, killed after
    DISPATCH_TIMEOUT_S."""
    try:
        p = subprocess.run(argv, input=prompt, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                           timeout=DISPATCH_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return "", f"timed out after {DISPATCH_TIMEOUT_S}s", None
    except (OSError, subprocess.SubprocessError) as e:
        return "", f"{type(e).__name__}: {e}"[:200], None
    return p.stdout, (p.stderr.strip().splitlines() or [f"claude -p exited {p.returncode}"])[-1][:200], p.returncode


def cmd_dispatch(a, tally):
    """census.py dispatch: one brief part of one group as a headless `claude -p` session; its schema-valid result is
    written to RESULTS.json for `apply`. Exit 0, 1 when the run stopped or returned no valid result (nothing is
    written: the group stays unapplied), 2 refused."""
    rows, err = phase2_args(a)
    if err:
        print(err)
        return 2
    if a.max_turns < 1 or a.max_budget_usd <= 0:
        print("--max-turns and --max-budget-usd must be positive")
        return 2
    ctx = phase2_context(rows, a.log, a.factdiff)
    if a.group not in ctx["members"]:
        print(f"no group {a.group!r} in the queue of {a.log}; groups: " + (", ".join(ctx["members"]) or "none"))
        return 2
    packed, rules = brief_packs(a.group, ctx["members"][a.group], ctx)
    if not 1 <= a.part <= len(packed):
        print(f"group {a.group} has {len(packed)} part(s); --part {a.part} is out of range")
        return 2
    members = [m for m, _ in packed[a.part - 1]]
    brief = part_text(a.group, packed, rules, ctx, a.part)
    exe = claude_exe()
    if exe is None and not a.dry_run:
        print("claude is not on PATH (a relative entry, or the current directory, does not count)")
        return 2
    plan = dispatch_plan(a.group, members, ctx)
    mcp = docs_mcp_config() if plan["learn"] else None
    if plan["learn"] and not mcp:
        plan = {**plan, "skipped": sorted(plan["skipped"] + plan["learn"]), "learn": []}
    under = worktrees_file(plan["files"])
    if under:
        print(f"dispatch refuses to run from here: {under} is under .claude/worktrees, where the claude CLI denies the "
              "Edit rules of the group's files, so the session would edit nothing and return its rewrites as foreign "
              "edits: run it from a checkout outside .claude/worktrees")
        if not a.dry_run:
            return 2
    with open(RESULT_SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    schema_text = json.dumps(schema, separators=(",", ":"))
    out_dir = os.path.join(DISPATCH_DIR, ctx["date"], a.group)
    name = "RESULTS.json" if len(packed) == 1 else f"RESULTS-{a.part}.json"
    results = os.path.join(out_dir, name)
    shown = kbcommon.repo_rel(results)
    label = f"group {a.group} part {a.part} of {len(packed)}"
    apply_cmd = shlex.join(["python3", f"{TOOLS_REL}/census.py", *root_args(ctx["root"]), "apply", a.log, "--group", a.group,
                            "--from", shown])
    if a.dry_run:
        allow, tools = dispatch_rules(plan, "<scratch>")
        argv = dispatch_argv(exe or "claude", a.model, a.max_turns, a.max_budget_usd, "<schema>", allow, tools, mcp and "<mcp-config>")
        prompt = dispatch_prompt(brief, plan, "<scratch>")
        est = dispatch_estimate(len(prompt), [q for _, _, q in members], a.model, a.max_turns)
        print(f"dispatch dry run (nothing started): {label}: model={a.model} max-turns={a.max_turns} "
              f"max-budget-usd={a.max_budget_usd:.2f} rows={len(members)} prompt chars={len(prompt)} "
              f"tokens~{len(prompt) // kbusage.CHARS_PER_TOKEN}")
        print(f"estimate: turns~{est['turns']} input tokens~{est['input_tokens']} output tokens~{est['output_tokens']} "
              + (f"usd~{est['usd']:.4f} cap~{est['cap_usd']:.2f} (--max-budget-usd)" if est["usd"] is not None
                 else f"usd unknown (no price for {a.model} in bench_core.PRICE)"))
        print(f"claude: {exe or 'not on PATH'}; schema: {SCHEMA_REL}; result: {shown}; then: {apply_cmd}")
        print("argv: " + shlex.join(argv))
        return 0
    if os.path.exists(results):
        os.remove(results)  # a result of an earlier run is no result of this one
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="census-dispatch-") as scratch:
        scratch = os.path.realpath(scratch)
        allow, tools = dispatch_rules(plan, scratch)
        argv = dispatch_argv(exe, a.model, a.max_turns, a.max_budget_usd, schema_text, allow, tools, mcp)
        began = time.monotonic()
        stdout, why, code = dispatch_call(argv, dispatch_prompt(brief, plan, scratch), scratch, dispatch_env())
    wall = round(time.monotonic() - began, 1)
    with open(os.path.join(out_dir, f"reply-{a.part}.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(stdout)
    reply = dispatch_reply(stdout, schema)
    if not stdout.strip():
        reply["error"] = why
    elif code and reply["result"] is not None:
        reply["result"], reply["error"] = None, f"claude -p exited {code} with a result: not taken"
    ok = reply["result"] is not None
    tally["runs"] += 1
    tally["ok" if ok else "failed"] += 1
    tally.update(reply["usage"])
    tally["turns"] += reply["turns"]
    tally["cost-usd-micro"] += round(reply["cost_usd"] * 1e6)
    toks = " ".join(f"{n}={reply['usage'].get(n, 0)}" for _, n in factdiff.JUDGE_USAGE)
    print(f"dispatch {label}: model={a.model} served={','.join(reply['models']) or '-'} turns={reply['turns']} "
          f"wall={wall}s {toks} total_cost_usd={reply['cost_usd']:.4f}")
    if not ok:
        print(f"{label} UNAPPLIED: {reply['error']}; no RESULTS.json was written (the reply is "
              f"{kbcommon.repo_rel(os.path.join(out_dir, f'reply-{a.part}.json'))})")
        return 1
    with open(results, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reply["result"], f, indent=1)
        f.write("\n")
    print(f"result: {shown} ({len(reply['result']['outcomes'])} outcome(s)); then: {apply_cmd}")
    return 0


CHANGING = ("updated", "superseded", "gone")  # the outcomes of a source whose facts the census changed


def score_lines(recorded, results):
    """(lines, counts) of `results` (each a phase-2 result's outcomes list) against `recorded` ({source id: outcome} of
    a census log): one line per source a result names that the log holds an outcome for, in id order, and the counts
    `sources`, `agree`, `false_confirms` (confirmed where the census changed a fact), `false_confirms_updated` (of
    them, where it rewrote one: outcome `updated`), `changed` (sources the census changed), `unconfirmed` and `unrecorded` (named by a result, no outcome in the log)."""
    got, n = {}, Counter()
    for outcomes in results:
        for o in outcomes:
            got[o["id"]] = o["outcome"]
    lines = []
    for sid in sorted(got):
        want = recorded.get(sid, "")
        if not want:
            n["unrecorded"] += 1
            continue
        n["sources"] += 1
        n["changed"] += want in CHANGING
        n["agree"] += got[sid] == want
        n["unconfirmed"] += got[sid] == "unconfirmed"
        fc = got[sid] == "confirmed" and want in CHANGING
        n["false_confirms"] += fc
        n["false_confirms_updated"] += fc and want == "updated"
        lines.append(f"{sid}: recorded {want}, result {got[sid]}" + (" FALSE CONFIRM" if fc else "" if got[sid] == want else " differs"))
    return lines, n


def cmd_score(a, tally):
    """census.py score LOG --from RESULTS.json ...: what a model's phase-2 results say, source by source, against the
    outcomes a census recorded in LOG (read-only). Exit 0, 2 refused."""
    try:
        recorded = {r["id"]: r["outcome"] for r in read_log(a.log)}
        results = []
        for path in a.from_json:
            with open(path, encoding="utf-8") as f:
                results.append(json.load(f)["outcomes"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"cannot read the log or a result: {e}", file=sys.stderr)
        return 2
    lines, n = score_lines(recorded, results)
    print("\n".join(lines))
    pct = 100.0 * n["agree"] / n["sources"] if n["sources"] else 0.0
    print(f"score: results={len(results)} sources={n['sources']} agree={n['agree']} ({pct:.1f}%) "
          f"false-confirms={n['false_confirms']}/{n['changed']} (updated {n['false_confirms_updated']}) unconfirmed={n['unconfirmed']} unrecorded={n['unrecorded']}")
    return 0


def step(name, script, *args, ok=(0,), skip="", capture=False):
    """One step of a driver: its argv (printed with `python3`, run with this interpreter), the exit codes that are no
    failure, the reason a resumed run skips it (empty: it runs) and whether its output is kept for the report."""
    return {"name": name, "argv": ["python3", f"{TOOLS_REL}/{script}", *args], "ok": ok, "skip": skip, "capture": capture}


def commit_step(subject, body, add, *trailers):
    """The step that commits: `add` are the files it adds besides the tracked changes of the root (the census logs)."""
    argv = ["git", "commit", "-q", "-m", subject, "-m", body]
    for t in trailers:
        argv += ["--trailer", t]
    return {"name": "commit", "argv": argv, "ok": (0,), "skip": "", "capture": False, "add": add}


def root_args(root):
    return [] if root == "public" else ["--root", root]


def census_path(name):
    return kbcommon.repo_rel(f"{kbcommon.CENSUS_DIR}/{name}")


def output_exists(rel):
    return os.path.exists(os.path.join(kbcommon.HOME, rel))


def apply_committed(flog, date):
    """True when `factdiff.py apply --commit` of this log and date is already in the history (its commit message names
    both: apply writes nothing a rerun could tell it by, and a rerun with nothing to commit fails)."""
    path = os.path.relpath(os.path.join(kbcommon.HOME, flog), kbcommon.HOME)
    return bool(g(kbcommon.HOME, "log", "-1", "--format=%H", "--fixed-strings", "--all-match",
                  f"--grep=fact diff {date}: confirm", f"--grep={path}")[1])


def plan_run(root, date, resume, exists, applied):
    """The steps of `census.py run`: phase 0 (the fact diff and what it settles), phase 1 (the mechanical verdicts), the
    index and the phase-1 commit, then the summary. `exists(path)` and `applied(log, date)` say whether the output of
    a step for this date is there; `resume` skips the steps whose output is."""
    flog, log = census_path(f"factdiff-{date}.csv"), census_path(f"{date}.csv")
    ra = root_args(root)
    return [
        step("detect", "factdiff.py", *ra, "detect", "--date", date, "--sitemaps", ok=(0, 1),
             skip=f"{flog} exists" if resume and exists(flog) else ""),
        step("apply", "factdiff.py", *ra, "apply", flog, "--date", date, "--commit",
             skip="its commit is in the history" if resume and applied(flog, date) else ""),
        step("check", "census.py", *ra, "check", "--date", date, "--factdiff", flog,
             skip=f"{log} exists" if resume and exists(log) else ""),
        step("repin", "census.py", *ra, "repin", log, "--date", date, "--commit"),
        step("index", "build_index.py", *ra),
        commit_step(f"docs(kb): census {date} phase 1 verdicts",
                    "census.py run: the fact diff, the mechanical verdicts and the index; no model read them.", [log, flog]),
        step("summary", "census.py", *ra, "summary", log, "--factdiff", flog),
    ]


def plan_finish(root, log, date):
    """The steps of `census.py finish`: phase 3 (dates), the sweep of the decisions whose context it broke, the index
    and the confirmed-dates commit with its KB-Verified trailer."""
    ra = root_args(root)
    return [
        step("confirm", "census.py", *ra, "confirm", log, "--date", date),
        step("sweep", "kbdecide.py", "sweep", "--date", date, capture=True),
        step("index", "build_index.py", *ra),
        commit_step(f"docs(kb): census {date}: confirmed dates",
                    "census.py finish: sources, articles and fetch state dated by script; decisions swept.", [],
                    f"KB-Verified: {date}"),
    ]


def tracked_dirty():
    """The tracked paths that differ from HEAD or from the index (untracked files do not count, as for `kbgit.py sync`)."""
    out = set()
    for extra in ([], ["--cached"]):
        out.update(p for p in g(kbcommon.HOME, "diff", "--name-only", "-z", *extra)[1].split("\0") if p)
    return sorted(out)


def foreign(paths, root_rel, finish):
    """The paths a driver does not write: outside the root under census and, for `finish`, no decision ledger."""
    return [p for p in paths if not p.startswith(root_rel + "/") and not (finish and LEDGER.fullmatch(p))]


def run_step(s):
    """(exit code, stdout kept for a `capture` step else '') of one step, run from the repository's root."""
    p = subprocess.run([sys.executable, *s["argv"][1:]], cwd=kbcommon.HOME, text=True, encoding="utf-8",
                       stdout=subprocess.PIPE if s["capture"] else None)
    return p.returncode, p.stdout or ""


def run_commit(s, root_rel, finish):
    """(exit code, '') of the commit step: add the census logs and the tracked changes of the root (and, for `finish`,
    of the ledgers), then commit when the index differs from HEAD; a tracked change outside them refuses it (exit 2).
    Never pushes."""
    dirty = tracked_dirty()
    bad = foreign(dirty, root_rel, finish)
    if bad:
        print(f"refused: tracked changes outside {root_rel}/: {', '.join(bad[:5])}", file=sys.stderr)
        return 2, ""
    add = sorted({*dirty, *(p for p in s["add"] if output_exists(p))})
    if add and g(kbcommon.HOME, "add", "--", *add)[0]:
        print("git add failed; nothing committed", file=sys.stderr)
        return 1, ""
    if g(kbcommon.HOME, "diff", "--cached", "--quiet")[0] == 0:
        print("nothing to commit")
        return 0, ""
    code, _, err = g(kbcommon.HOME, *s["argv"][1:])
    if code:
        print(f"git commit failed (hooks or nothing to commit): {err.splitlines()[-1] if err else code}", file=sys.stderr)
        return 1, ""
    print(f"committed: {s['argv'][s['argv'].index('-m') + 1]}")
    return 0, ""


def drive(steps, root_rel, finish, dry_run, rerun):
    """Run `steps` in order, one at a time, with no agent turn between them: (0, kept) when all pass, else (the exit
    code of the step that failed, kept); the failing step's name and `rerun`, the command that resumes it, are
    printed. A dry run prints each step's argv and runs nothing. `kept` is the output of each `capture` step by name."""
    n, kept = len(steps), {}
    for i, s in enumerate(steps, 1):
        head = f"step {i}/{n} {s['name']}"
        if dry_run:
            print(f"{head}: {shlex.join(s['argv'])}" + (f"  (--resume skips it: {s['skip']})" if s["skip"] else ""))
        elif s["skip"]:
            print(f"{head}: skipped, {s['skip']}")
        else:
            print(f"{head}: {shlex.join(s['argv'])}", flush=True)
            code, kept[s["name"]] = run_commit(s, root_rel, finish) if s["name"] == "commit" else run_step(s)
            if code not in s["ok"]:
                if kept[s["name"]]:
                    print(kept[s["name"]].rstrip("\n"), file=sys.stderr)
                print(f"{head} failed with exit {code}; resume from it: {rerun}", file=sys.stderr)
                return code, kept
    return 0, kept


def refusals(root_rel, finish, extra=()):
    """What stops a driver before its first step: `extra`, and tracked changes it does not write."""
    bad = foreign(tracked_dirty(), root_rel, finish)
    scope = f"{root_rel}/" + (" and the decision ledgers" if finish else "")
    return [*extra, *([f"tracked changes outside {scope}: {', '.join(bad[:5])}" + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else "")
                       + "; commit or set them aside, as `kbgit.py sync` requires too"] if bad else [])]


def start(why, dry_run):
    """None to go on, else the exit code: a dry run only notes what would refuse a run, a run is refused (exit 2)."""
    for w in why:
        print(("note: a run would be refused: " if dry_run else "refused: ") + w, file=sys.stdout if dry_run else sys.stderr)
    return 2 if why and not dry_run else None


def cmd_run(a, tally):
    date, root, root_rel = a.date or today(), os.path.basename(KB), kbcommon.repo_rel(".")
    log, extra = census_path(f"{date}.csv"), []
    if not a.resume and output_exists(log):
        n = sum(1 for r in read_log(os.path.join(kbcommon.HOME, log)) if r["outcome"])
        if n:
            extra.append(f"{log} holds {n} phase-2 outcome(s) that check would overwrite; --resume continues from it")
    refused = start(refusals(root_rel, False, extra), a.dry_run)
    if refused:
        return refused
    rerun = shlex.join(["python3", f"{TOOLS_REL}/census.py", *root_args(root), "run", "--date", date, "--resume"])
    code, _ = drive(plan_run(root, date, a.resume, output_exists, apply_committed), root_rel, False, a.dry_run, rerun)
    if code == 0 and not a.dry_run:
        print(f"next: phase 2 reads the queue above; phase 3 is `census.py finish {log} --date {date}`")
    return code


def cmd_finish(a, tally):
    date, root, root_rel = a.date or today(), os.path.basename(KB), kbcommon.repo_rel(".")
    if not os.path.isfile(a.log):
        print(f"no census log {a.log}", file=sys.stderr)
        return 2
    log = os.path.relpath(os.path.abspath(a.log), kbcommon.HOME).replace(os.sep, "/")
    refused = start(refusals(root_rel, True), a.dry_run)
    if refused:
        return refused
    rerun = shlex.join(["python3", f"{TOOLS_REL}/census.py", *root_args(root), "finish", log, "--date", date])
    code, kept = drive(plan_finish(root, log, date), root_rel, True, a.dry_run, rerun)
    if code == 0 and not a.dry_run:
        print("for the report (kbdecide.py sweep: the invalidations and the relink lines, which `kbdecide.py relink` repoints):")
        print(kept.get("sweep", "").rstrip("\n") or "(no output)")
    return code


PHASES = {"check": cmd_check, "record": cmd_record, "confirm": cmd_confirm, "repin": cmd_repin,
          "judge": cmd_judge, "dispatch": cmd_dispatch}  # each writes a census.phase ops row


def main():
    global KB
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", metavar="NAME", default="public", help="the root under census (default public)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="phases 0-1: a mechanical verdict per source, written to the census log")
    c.add_argument("--date", help="census date (default today)")
    c.add_argument("--out", help="log path (default _census/<date>.csv)")
    c.add_argument("--jobs", type=int, default=16, help="parallel checks (default 16)")
    c.add_argument("--source", action="append", default=[], help="only these source ids (repeatable)")
    c.add_argument("--factdiff", metavar="LOG", help="the fact diff log of the census's first stage: its sources take its "
                                                     "verdicts, the rest are checked here")
    r = sub.add_parser("record", help="phase 2: record what reading a source decided")
    r.add_argument("log")
    r.add_argument("--from", dest="from_json", help="JSON list of {id, outcome, note}")
    r.add_argument("--id")
    r.add_argument("--outcome", choices=OUTCOMES)
    r.add_argument("--note")
    f = sub.add_parser("confirm", help="phase 3: date the confirmed sources and the articles whose sources all are")
    f.add_argument("log")
    f.add_argument("--date", help="confirmation date (default today)")
    f.add_argument("--dry-run", action="store_true", help="report, write nothing")
    s = sub.add_parser("sample", help="phase 4: the sources an independent check re-reads, as CSV, or with --brief as its brief")
    s.add_argument("log")
    s.add_argument("--brief", action="store_true", help="the checker's brief: each source's citing facts with their passage in "
                                                        "the current text; a source whose every fact is word for word is agreed by tool")
    s.add_argument("--max-age", type=float, default=7, help="--brief reuses cached documents up to DAYS old, else fetches "
                                                            "(default 7, as factdiff.py anchor)")
    s.add_argument("--changed", type=float, default=0.10, help="fraction of the changed sources (default 0.10)")
    s.add_argument("--judged", type=float, default=0.10, help="fraction of the sources the batch judge confirmed (default 0.10, "
                                                              "the changed group's: the judge's false confirms are stale facts)")
    s.add_argument("--ok", type=float, default=0.05, help="fraction of the other confirmed sources (default 0.05)")
    s.add_argument("--seed", type=int, default=1)
    bs = sub.add_parser("baselines", help="the live unpinned sources with no detection baseline, counted by host (exit 1 when any)")
    bs.add_argument("--list", action="store_true", help="every host, each with its source ids and urls")
    m = sub.add_parser("summary", help="counts per bucket and outcome, and the size of phase 2's reading queue")
    m.add_argument("log")
    m.add_argument("--factdiff", metavar="FLOG", help="the fact diff log whose review items the queue sizes (default: the "
                                                      "log the census's evidence names, else factdiff-<date>.csv beside LOG)")
    jd = sub.add_parser("judge", help="phase 2: review items judged in batches by a no-tool model call; a source with every "
                                      "fact supported is confirmed with no agent")
    jd.add_argument("log")
    jd.add_argument("--factdiff", metavar="FLOG", help="the fact diff log whose review items are judged (default as for summary)")
    jd.add_argument("--model", default=STEP_MODELS["judge"], help=f"the model of each call (default {STEP_MODELS['judge']})")
    jd.add_argument("--batch-size", type=int, metavar="N", help=f"items per call (default {factdiff.JUDGE_BATCH})")
    jd.add_argument("--max-budget-usd", type=float, metavar="USD", help="each call's cap (default: its estimate, tripled)")
    jd.add_argument("--jobs", type=int, default=4, help="parallel calls (default 4)")
    jd.add_argument("--dry-run", action="store_true", help="print the batch count and the estimated tokens and USD, ask nothing")
    cp = sub.add_parser("compare", help="a model against a judging step's current one on a labelled set built from the log's "
                                        "recorded outcomes (paid unless --dry-run or --decide)")
    cp.add_argument("log")
    cp.add_argument("--step", required=True, choices=list(BASELINE_MODELS),
                    help="judge: the batch judge of review items; check: the phase-4 checker's passage judgments")
    cp.add_argument("--model", default=HAIKU_MODEL, help=f"the model asked (default {HAIKU_MODEL}); --decide compares it "
                                                         "with the step's baseline model")
    cp.add_argument("--half", choices=("tune", "held"), help="the half of the split to judge: the held-out half is judged once")
    cp.add_argument("--from", dest="base", metavar="REV", help="the revision before the census's phase-2 edits")
    cp.add_argument("--to", dest="end", metavar="REV", help="the revision after them")
    cp.add_argument("--seed", type=int, default=1, help="the seed of the unchanged items' draw (default 1)")
    cp.add_argument("--batch-size", type=int, metavar="N", help=f"units per call (default {factdiff.JUDGE_BATCH})")
    cp.add_argument("--max-budget-usd", type=float, metavar="USD", help="each call's cap (default: its estimate, tripled)")
    cp.add_argument("--jobs", type=int, default=4, help="parallel calls (default 4)")
    cp.add_argument("--dry-run", action="store_true", help="print the set's counts and the estimated tokens and USD, ask nothing")
    cp.add_argument("--again", action="store_true", help="judge a held-out half a model already judged")
    cp.add_argument("--decide", action="store_true", help="read the two held-out results and print which bar the model meets")
    gp = sub.add_parser("groups", help="phase 2: the rows to read split into owner groups, as JSON")
    gp.add_argument("log")
    gp.add_argument("--factdiff", metavar="FLOG", help="the fact diff log whose review items the queue sizes (default as for "
                                                       "summary)")
    bp = sub.add_parser("brief", help="phase 2: one group's brief, filled in with its rows, cited facts and review items")
    bp.add_argument("log")
    bp.add_argument("--group", required=True, help="a group name `groups` prints")
    bp.add_argument("--part", type=int, default=1, help=f"the part of a group over {BRIEF_CHARS} characters (default 1)")
    bp.add_argument("--factdiff", metavar="FLOG", help="the fact diff log whose review items the brief prints (default as "
                                                       "for summary)")
    ay = sub.add_parser("apply", help="phase 2: validate a group's JSON result and do its bookkeeping")
    ay.add_argument("log")
    ay.add_argument("--group", required=True, help="the group `groups` prints whose result this is")
    ay.add_argument("--from", dest="from_json", required=True, metavar="RESULTS.json",
                    help=f"the group's result, valid against {SCHEMA_REL}")
    ay.add_argument("--dry-run", action="store_true", help="print every write and step, change nothing")
    dp = sub.add_parser("dispatch", help="phase 2: one group's brief part as a capped headless session on a smaller model; "
                                         "writes the result `apply` takes (paid unless --dry-run)")
    dp.add_argument("log")
    dp.add_argument("--group", required=True, help="a group name `groups` prints")
    dp.add_argument("--part", type=int, default=1, help=f"the part of a group over {BRIEF_CHARS} characters (default 1)")
    dp.add_argument("--factdiff", metavar="FLOG", help="the fact diff log whose review items the brief prints (default as "
                                                       "for summary)")
    dp.add_argument("--model", default=DISPATCH_MODEL, help=f"the session's model (default {DISPATCH_MODEL})")
    dp.add_argument("--max-turns", type=int, metavar="N", default=DISPATCH_TURNS, help=f"turn cap (default {DISPATCH_TURNS})")
    dp.add_argument("--max-budget-usd", type=float, metavar="USD", default=DISPATCH_BUDGET_USD,
                    help=f"dollar cap (default {DISPATCH_BUDGET_USD:.2f})")
    dp.add_argument("--dry-run", action="store_true", help="print the model, caps, rules and argv, start nothing")
    sc = sub.add_parser("score", help="phase 2: results of a model, source by source, against the outcomes a census recorded "
                                      "(read-only)")
    sc.add_argument("log", help="the census log that holds the recorded outcomes")
    sc.add_argument("--from", dest="from_json", action="append", required=True, metavar="RESULTS.json",
                    help="a group's result (repeatable: the parts and groups of one model's run)")
    u = sub.add_parser("run", help="phases 0-1 as one command: fact diff, apply, check, index, the phase-1 commit, summary")
    u.add_argument("--date", help="census date (default today)")
    u.add_argument("--resume", action="store_true", help="skip the steps whose output for the date exists")
    u.add_argument("--dry-run", action="store_true", help="print each step's argv, run nothing")
    rp = sub.add_parser("repin", help="phase 1: re-pin the pinned files whose cited facts are word for word at the newer commit")
    rp.add_argument("log")
    rp.add_argument("--date", help="date of the new rows (default today)")
    rp.add_argument("--dry-run", action="store_true", help="print every write, change nothing")
    rp.add_argument("--commit", action="store_true", help="commit the result with a KB-Verified trailer")
    z = sub.add_parser("finish", help="phase 3 as one command: confirm, decision sweep, index, the confirmed-dates commit")
    z.add_argument("log")
    z.add_argument("--date", help="confirmation date (default today)")
    z.add_argument("--dry-run", action="store_true", help="print each step's argv, run nothing")
    a = ap.parse_args()
    kbd = os.path.realpath(kbcommon.KB_DIR)
    try:
        here = [r for r in kbcommon.roots() if os.path.dirname(os.path.realpath(r.path)) == kbd and r.name == a.root]
    except kbcommon.RootError as e:
        sys.exit(str(e))
    if not here:
        ap.error(f"--root {a.root}: no such root in {kbcommon.repo_rel(kbcommon.KB_DIR)}/")
    KB = kbcommon.KB = here[0].path
    factdiff.ROOT = here[0]
    if a.cmd == "record" and not a.from_json and not (a.id and a.outcome):
        ap.error("record needs --from FILE, or --id and --outcome")
    cmds = {**PHASES, "sample": cmd_sample, "baselines": cmd_baselines, "summary": cmd_summary, "groups": cmd_groups, "brief": cmd_brief,
            "compare": cmd_compare, "score": cmd_score,
            "apply": cmd_apply, "run": cmd_run, "finish": cmd_finish}
    run = lambda tally: cmds[a.cmd](a, tally)  # noqa: E731
    if a.cmd in PHASES and not getattr(a, "dry_run", False):
        sys.exit(ql_capture.census_phase(a.cmd, run, ql_capture.phase_date(getattr(a, "date", None), getattr(a, "log", None))))
    sys.exit(run(Counter()))


if __name__ == "__main__":
    main()
