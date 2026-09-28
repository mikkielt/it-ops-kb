# Query log: a self-improving lookup pipeline

Every kb lookup leaves a redacted, judged record in the repository, in `kb/_querylog/`. `learn` turns the records into findings, and `apply` turns accepted findings into eval rows, aliases, expansions and `_gaps.md` entries, pushed straight to `main` once the local gate passes. The aim is better knowledge handling by agents, not an approval workflow for people: no merge requests unless a conflict needs one.

- **Stages:** capture (hooks and tools, a local spool) -> distill (stdlib rules, then Haiku in batches) -> learn (deterministic findings) -> apply (the local gate, then a direct push).
- **Code:** `_tools/querylog.py` (the stages) and `_tools/redact.py` (redaction, tested in `_tools/test_redact.py`). `querylog.py capture` is built (Capture, below; tested in `_tools/test_querylog.py`); distill, learn and apply exit 2 until the Query log items of `kb/_self/work-left.md` build them in order, and this doc is the design they follow. Standard library only, plus the `claude` CLI for Haiku; macOS, Linux and Windows.
- **Why it can be built from hooks:** `UserPromptSubmit` gives the prompt with `session_id` and `prompt_id`, and `Stop` gives `last_assistant_message` for the same session (`claude/hooks.md`, DER S743; the answer `QK-self-improving-lookup-pipeline-query-logging` in `kb/public/_answers.md`).

## Rules

- **One owner per truth.** The store owns logged lookups; findings, the digest and every change `apply` makes derive from the store and the kb.
- **Run metadata once per run file**, in its header line, never per entry.
- **Derived state converges.** A second run on unchanged inputs changes nothing; a test checks it for `learn`, `apply` and the digest.
- **Stages stay separate.** Miss, candidate gap, gap, candidate fact and claim are distinct states, and each promotion is recorded on the finding.
- **`learn` writes findings; `apply` turns accepted findings into changes.** Nothing else writes kb files.
- **Deterministic code first.** Haiku only extracts questions, replaces names, summarises, and judges among candidate articles that code listed. It never picks an article code did not offer, never writes a fact, and never decides a gate.
- **Every gate's failure path is tested**, with a planted failure that makes it fail.
- **Done is a command's output**, never a model's say-so: each build item names its end state, the command that proves it and what must not change (`agents/agent-planning-and-done.md`, DER).

## Surfaces

Every row has `id` (a fresh UUID), `ts` (UTC, milliseconds) and `surface`; a hook row also has `session_id` and `prompt_id`. Fields that would be empty are left out.

| surface | written by | row keeps |
|---|---|---|
| `prompt`: every prompt | an async `UserPromptSubmit` hook | `prompt` as typed, and `kb_intent`: `lookup` (`kb:`, `kb+:`), `skill` (a `/kb-...` command) or `change` (the change router names a skill), so distill can extract the question and see a kb change |
| `kb_hook`: `kb:` and `kb+:` prompts | `_tools/kb_hook.py`, from inside, after its answer | `question`, `forward` (`kb+:`), `verdict`, `articles` the pack cited, `answered` (the hook answered without the model) |
| `mcp`: kb MCP tool calls | an async `PostToolUse` and `PostToolUseFailure` hook, matchers `mcp__kb__.*` and `mcp__plugin_it-ops-kb_kb__.*` | `tool` (`kb_pack`, ...), `args` (question, questions, path, prefix, query and the other lookup arguments, each clipped), `verdict` (the worst of several), `verdicts` when several, `articles` from the result; `outcome: error` for a failed call |
| `kb_ask`: `kb_ask.py` runs | `_tools/kb_ask.py`, from inside | `question`, `route` (`tool`, `good`, `weak`, `plan` for `--route`), `verdict`, `parts`, `model`, `escalated` |
| `stop`: the answer's outcome | an async `Stop` hook | `answer` (`last_assistant_message`), only for a prompt that used the kb |
| `fetch`: web and docs-server fetches | the same async `PostToolUse` and `PostToolUseFailure` hook on `WebFetch`, the three docs servers (under a clone's and the docs plugin's names), and `Bash` and `PowerShell` for `curl` and `wget` only | `tool`, `fetcher` (`curl`, `wget`), `host` and `path` (no user, port, query or fragment; none for a docs-server call without a url), `outcome`; never command text or results |
| `tool_fetch`: `fetch.py` and `census.py` requests | `_tools/fetch.py` and `_tools/census.py` (and `factdiff.py` through `fetch.py`), from inside | `tool` (the running script), `host`, `path`, `outcome`, one row per request |

- **Rows join on `prompt_id`**, a common hook input field (`claude/hooks.md`, DOC S743). A tool that writes from inside (`kb_ask.py`, `fetch.py`, `census.py`) sees no `prompt_id`: its row goes to the tools file, and distill attaches it to the prompt of the same clone whose `UserPromptSubmit`-to-`Stop` window holds the row's time; a row in no window is an entry of its own (a run outside Claude Code).
- **Fetches and answers count only beside the kb**, decided at capture: a `fetch` or `stop` row is written only when the prompt already used the kb (a `kb_hook` or `mcp` row, a prompt with a `kb_intent`, or a tool row since the prompt began). A fetch made before the prompt's first kb call is not logged, and an async kb row that lands after the `Stop` hook ran loses that answer; both are accepted.
- **Failures count.** `PostToolUse` fires only after a successful call, so the same hook runs on `PostToolUseFailure`, which gives the `error` text (`claude/hooks.md`, DOC S743).
- **Shell commands are parsed only for `curl` and `wget`**, in `Bash` and in `PowerShell` (which takes shell commands on Windows, `claude/hooks.md`, DOC S743): the first http(s) url after the command word gives host and path. Command-text parsing undercounts (a script, an alias, a variable), which is why `fetch.py` and `census.py` log from inside; the undercount of other commands is accepted.
- **The MCP server does not log**: it never sees `session_id` or `prompt_id`, so its rows could not join.
- **Logging hooks are async.** An async hook cannot block or add context, which a logging hook never needs, and it does not delay the prompt (`claude/hooks.md`, DOC S743). The `kb:` hook stays synchronous because it answers; its row is one local append after the answer is printed (`_tools/test_stress.py` holds it to the latency with capture off).
- **Fetch outcomes classify facts only:** `http-<status>` (a status the tool or the error text gives), `empty`, `redirect-cross-host` (WebFetch returns such a redirect as text instead of following it, `claude/hooks.md`, DOC S-3yod3u7q; `fetch.py` and `census.py` compare the final url's host), `truncated` (`census.py`'s read limit reached), `error`; everything else is `unknown`: "a bot page", "the summary lacked it", and a shell fetch's exit code 0. Source signals (a host that needs staging, a route misused) are report-only findings.
- **A tool response is read, never kept:** `tool_response` for an MCP call is undocumented (a gap entry under `claude/hooks.md`), so its text is taken from a string, a content-block list or an object holding one.

## Capture (`querylog.py capture`)

- **One command for every hook event.** `sh "<root>/_tools/kbpy" _tools/querylog.py capture`, async, on `UserPromptSubmit`, `PostToolUse`, `PostToolUseFailure` and `Stop` in `.claude/settings.json` and the plugin (`_tools/test_querylog.py` checks both, and `_tools/test_portability.py` the launcher form). It reads the event on stdin, appends at most one row, prints nothing and exits 0 on any input.
- **Tools** call `querylog.record(surface, session_id, **fields)`, or `record_request(url, outcome)` per HTTP request; `record` never raises. `kb_hook.py` loads `querylog.py` only for a `kb:` prompt.
- **Size:** a row longer than `SPOOL_ROW_MAX_CHARS` has its longest text field cut, ending ` [...]`.
- **Pruning:** every `UserPromptSubmit` capture deletes spool files untouched for `SPOOL_MAX_AGE_DAYS`, so rows never distilled do not outlive the horizon.
- **`querylog.py where`** prints the mode, the config file, the directory and whether capture writes.
- **Tests never write the clone's spool:** they run tools with `conftest.querylog_env`, which points capture at a temporary plugin data directory.

## Spool

- **Where:** `_cache/querylog/spool/<session_id>.jsonl` in a clone on every OS (short UUID names keep Windows paths short), and `${CLAUDE_PLUGIN_DATA}/querylog/spool/` in a plugin host: the hook runs the plugin's copy, so `CLAUDE_PLUGIN_ROOT` names this code and `CLAUDE_PLUGIN_DATA` is set (`claude/hooks.md`, `claude/plugins.md`, DOC). Rows without a session, or with a session id that is not a safe file name, go to `tools-<yyyy-mm-dd>.jsonl` (UTC) beside them. The `DISABLED` marker is `_cache/querylog/DISABLED` in a clone and `${CLAUDE_PLUGIN_DATA}/querylog/DISABLED` in a host.
- **Never committed** (`_cache/` is ignored). A spool file is deleted once its distilled entry is pushed (in mode `local`: committed) or dropped; rows never distilled are deleted after `SPOOL_MAX_AGE_DAYS`, the same horizon as Claude Code's own local transcripts (`claude/data-retention.md`, DOC S747).
- **Raw text stays here.** The spool holds prompts and answers as typed, which is why it is local and short-lived; nothing raw leaves it except rule-redacted text sent to Haiku.
- **The pipeline never logs itself:** every `claude -p` it starts (`kb_ask.py`'s reader and researcher, the Haiku stage in `redact.names_argv`) runs with `--settings '{"disableAllHooks": true}'` (`querylog.NO_HOOKS`), which turns hooks off for that run over project and local settings (`claude/hooks.md`, DOC S743); a test fails on an argument list without it. `_tools/agent_bench.py` keeps hooks on, since it measures what a session loads.

## Distill

- **Trigger.** The `SessionEnd` hook only starts a detached distill and returns. `SessionEnd` hooks share a 1.5-second budget, and a plugin hook's `timeout` does not raise it, so a batch job with a network push fits only as a launcher (`claude/hooks.md`, DOC and DER S743; the answer `QK-kb-need-know-build-query-log`). `SessionStart` also starts one, for sessions that closed without it.
- **Closed sessions only.** A spool file is ready when its session ended, or when it has been idle for `SESSION_IDLE_CLOSED_S` (a crash or a kill fires no `SessionEnd`).
- **One distill per machine**, under the lock (Portability); a second one exits at once.
- **Its own worktree.** Distill commits in a git worktree under `_cache/querylog/`, checked out from `origin/main`, never in the person's checkout, so a background commit never meets their uncommitted work. A plugin host uses a managed clone under `${CLAUDE_PLUGIN_DATA}` instead.
- **Steps:** join the rows on `prompt_id`; keep the prompts that used the kb (and their fetches); redact (below); write one run file; commit it with `KB-Auto: querylog`; then `learn` and `apply` in mode `auto`.
- **Caps.** At most `HAIKU_BATCH_ENTRIES` entries per `claude -p` call, `HAIKU_BATCHES_PER_RUN` calls per run and `HAIKU_DAILY_CALLS` calls per machine per day. Over a cap, entries wait in the spool for the next run.

## Redaction (`_tools/redact.py`)

1. **Rules** (stdlib `re`, `redact()`): key and token shapes (`kbcommon.SECRETS`), JWTs, UNC paths, home and drive paths, UPNs and emails, down-level `DOMAIN\name`, domain SIDs, GUIDs (hyphenated and bare), IPv6, IPv4, FQDNs, computer-name patterns, high-entropy strings, in that order. Each becomes the placeholder for its kind (table below).
2. **Haiku** on the rule-redacted text only: extracts the question, replaces person and organisation names, summarises the outcome, and judges among the candidate articles code listed. Names rest on Haiku, with no NER layer; the test corpus includes names, which a stub replaces. `redact.py` holds the name step's interface (`names_argv`, `names_prompt`, `parse_names`); `querylog.py` supplies the model, the caps, the timeout and the call.
3. **Rules and the leak scan again** on Haiku's output (`finish()`): the scan is `kbcommon.leak_hits`, the same shapes the tracked-file leak test (`_tools/test_kb.py`, TestLeaks) flags, so nothing the scan would catch reaches the store.

| kind | placeholder |
|---|---|
| hyphenated / bare GUID | `00000000-0000-0000-0000-000000000000` / 32 zeros |
| IPv4 / IPv6 | `192.0.2.10` / `2001:db8::10` (the documentation ranges) |
| domain SID | `S-1-5-21-0-0-0-<RID>`: the domain identifier goes, the RID stays |
| UPN or email / down-level logon | `jan.kowalski@corp.example.com` / `CORP\jan.kowalski` |
| FQDN | `corp.example.com` |
| computer name | `PL-SRV-0042` when it reads as a server (SRV, SQL, DC1, ...), else `PL-LT-00123` |
| UNC host / home-directory user / other path segment | `\\PL-SRV-0042` / `jan.kowalski` / `PL-PATH` |
| key, token, JWT, high-entropy string | `<secret>` (angle brackets: the secret shapes never match a placeholder) |
| person / organisation name (Haiku) | `jan.kowalski` / `CORP` |

- **What stays:** well-known SIDs (`S-1-5-18`, `S-1-5-32-*` built-in groups, capability `S-1-15-3-*` and the other constant ones) identify no one, while an `S-1-5-21-*` domain SID names the organisation's domain; a user is matched both as a UPN and as `DOMAIN\name`, with no suffix allowlist, since an explicit UPN's suffix need not be the DNS domain (`reuse/pseudonymization-tokenization.md`, DOC and DER S-h2cmbqvf, S-dcjdn73r). Windows authorities (`NT AUTHORITY\`, `BUILTIN\`) and registry roots (`HKLM\`) are not logons. Loopback, multicast, netmasks, the documentation ranges and names (`example.com`, `.test`) stay.
- **The allowlist is the public root, read at run time.** `known()` runs the same shapes over every text file of `kb/public` (never an internal root, which names real tenants) once per process, and any GUID, public IP, host, email, logon, computer name or token found there stays: Graph app ids, CSP and ASR GUIDs, vendor hosts. So the vendor allowlist is the hosts the root names, matched exactly (a tenant's `name.sharepoint.com` is not kept because `sharepoint.com` is). One owner, nothing generated to go stale: an id an article adds is kept from the next run. A private address the kb shows is an example there, so private IPs are never kept this way.
- **Paths:** a segment made only of words the public root uses stays (`C:\Windows\CCM\Logs`), any other becomes `PL-PATH`; the user of `C:\Users\<name>`, `/Users/<name>` and `/home/<name>` always becomes `jan.kowalski` (`Public`, `Default` stay).
- **High entropy:** a token of `ENTROPY_MIN_LEN` or more letters, digits, `+` and `_` (trailing `=` allowed), with a letter and a digit, at `ENTROPY_MIN_BITS` or more. Per-character entropy alone does not separate identifiers from keys (`DeviceManagementConfiguration` scores 3.8 bits), so a token made only of words the public root uses, split at case and digit changes with each word 3 letters or more (`Win32LobAppPowerShellScript`), stays.
- **Doubt drops.** An entry Haiku flags as still identifying, or one the second leak scan catches, is dropped; only its counts go to the run header. A reply that is not the expected JSON drops its batch.
- **Haiku runs batched at distill:** `claude -p --model haiku --tools "" --settings '{"disableAllHooks": true}'` with no user plugins or MCP servers (`--setting-sources project,local --strict-mcp-config`), the batch on stdin. Its output is stored once per entry id and never regenerated, so a second distill cannot change a committed entry.
- **Idempotent:** `redact(redact(x)) == redact(x)`, and the placeholders pass through unchanged.
- **What the API sees:** rule-redacted text goes to the Claude API, under the organisation's retention (30 days standard for commercial use, `claude/data-retention.md`, DOC S747); `/kb-setup` says so.

## Store (`kb/_querylog/`)

- **Files:** `kb/_querylog/<yyyy-mm>/<run-id>.jsonl` (a header line, then entries) and `kb/_querylog/findings/<yyyy-mm>/<run-id>.jsonl`. One file per run, so parallel pushes from different machines never touch the same file and no `merge=union` driver is needed; a finding's state is its last record across findings files, so no file is edited after its run.
- **Header:** run id, pipeline version, retrieval version, kb commit, counts (entries, dropped, waiting). Entries carry none of these.
- **Entry:** id, surface, redacted question, verdict, cited articles, outcome summary, Haiku's judgement; a fetch entry keeps host, path and outcome class.
- **Never committed:** the raw prompt or answer, `session_id`, `prompt_id`, `transcript_path`, the user, the host name.
- **Not a root:** `pack` and `search` skip it, and the leak scan in `_tools/tests.py` covers it.
- **Gates**, each with a planted failure: a duplicate id across run files (`kbgit.py fix --check`); a missing header or provenance field; an identifier in a run file; a fetch entry with a query string, a non-public host or command text.
- **Why commit machine-written data at all:** the store is the one input `learn` and the digest read, so every clone computes the same findings and numbers from git alone (`agents/docs-maintenance-agents.md`).

## Learn and apply

- **`learn`** reads the store and the kb at `HEAD` and writes findings only. Every judged miss is re-run with `pack` on `HEAD` first; one that now passes is `fixed-since`. Kinds: eval (the kb has the answer, the pack missed it), alias, expansion, gap candidate, and source findings (report-only). A host's staging level comes from its provider-registry row (`_tools/providers.csv`, or a root's `_providers.csv`) when it has one, else from the routes table in `kb/_self/web-sources.md`; a test keeps the two in agreement.
- **`apply`** turns accepted findings into changes: an eval row only with the fix that makes it pass; aliases and expansions only when `rag.py eval` passes, off-kb `good` does not rise and the mean pack does not grow (`kb/_self/doc2query.md`); a reproduced gap candidate in a kb domain becomes a `_gaps.md` entry under its topic; a finding with no accepted fix stays a gap candidate. Source findings are never applied.
- **Research is opt-in per user**, capped by the user's own daily count: add-only, a candidate fact is accepted only when its quote of `QUOTE_MAX_WORDS` words or fewer is on the page (`querylog.py quotecheck`), and a disagreement goes to `_conflicts.md`. The gate and the quote check are its review.

## Delivery

- **Straight to `main` on `origin`**, the repository the clone came from: run files, findings, eval rows, aliases, expansions, gap entries and opt-in research, once the local gate passes and a rebase on `origin/main` is clean (`querylog.py apply --push`, through `kbgit.py sync`).
- **Trailer:** each commit carries `KB-Auto: querylog|eval|alias|expansion|gap|research|revert` beside its KB-* trailers.
- **`origin` only.** Mirroring to other remotes (`claude` on GitHub) stays a person's job.
- **No hard-coded host.** Every GitLab host name comes from `origin`'s url, with GitLab.com as the fallback.
- **A conflict `kbgit.py sync` cannot resolve** pushes a `querylog/<run-id>` branch with `-o merge_request.create -o merge_request.target=main` and leaves the findings pending, for a person or `/kb-git-sync`. The push options open the MR without a token (`gitlab/automated-merge-requests.md`, DOC S-2d2dlaeq). No auto-merge: a failed pipeline does not end auto-merge, so a retried job would merge a red MR (the answer `QK-kb-need-know-build-query-log`).
- **CI before any new push.** Distill reads the CI status of the last automatic commit (`glab api` on GitLab, `gh` on GitHub; skipped with a note when neither is signed in). Red: it pushes a revert commit (`KB-Auto: revert`) and records `apply failed` on the finding, which is never retried. Pending: nothing is pushed this run.
- **No CI job writes to the repository.** The project leaves job-token pushes off, and `.gitlab-ci.yml` runs branch and tag pipelines only.
- **Plugin hosts** distill in the managed clone and push to its `origin`; the first push refused for want of rights writes a `DISABLED` marker and deletes the spool, which turns logging off for good, while a network error or a red gate does not. **Cloud sessions** distill in the container and push to their own `origin`.

## Configuration

- **No environment variables.** Program defaults are the constants in the table below.
- **Per-user choices** live in one uncommitted file, written by `/kb-setup`: `_private/querylog.json` in a clone, `${CLAUDE_PLUGIN_DATA}/querylog/config.json` in a host. Keys: `mode` (`auto`, `local`, `off`), `research` (true or false), `research_daily` (runs per day).
- **Modes:** `auto` distills, commits and pushes; `local` distills and commits in the worktree, and never pushes; `off` writes nothing, not even the spool. A config file that cannot be read, or names no known mode, counts as `off` (fail closed); no file means `DEFAULT_MODE`.
- **What `/kb-setup` says:** colleagues' redacted questions are recorded in the repository, and rule-redacted text is sent to the API for Haiku; research is off.

## Program defaults

| constant | value | why |
|---|---|---|
| `DEFAULT_MODE` | `local` | nothing is pushed until the pipeline's end-to-end test passes; switching it to `auto` is the last Query log item in `kb/_self/work-left.md` |
| `DEFAULT_RESEARCH` | off | research writes facts, so each person opts in |
| `DEFAULT_RESEARCH_DAILY` | 3 runs per user per day | used when research is on and the file names no cap; a few quote-checked additions a day stay reviewable in the log |
| `HAIKU_MODEL` | `haiku` | the cheapest model for extraction, name replacement and summaries; the alias follows the current Haiku |
| `HAIKU_BATCH_ENTRIES` | 25 entries per call | one call's fixed prompt is shared by many entries, and a malformed reply loses one small batch only |
| `HAIKU_BATCHES_PER_RUN` | 4 calls | bounds one distill's run time, which bounds `LOCK_STALE_S` |
| `HAIKU_DAILY_CALLS` | 20 calls per machine per day | bounds API spend on a busy machine; entries over it wait |
| `HAIKU_TIMEOUT_S` | 180 s per call | a batch reply takes well under it; a hung CLI must not hold the lock |
| `LAUNCH_BUDGET_S` | 0.5 s | the `SessionEnd` launcher returns in a third of the shared 1.5-second budget, leaving the rest to other `SessionEnd` hooks (`claude/hooks.md`, DOC S743) |
| `LOCK_STALE_S` | 3600 s | a lock older than this is stale: longer than the longest run (`HAIKU_BATCHES_PER_RUN` x `HAIKU_TIMEOUT_S`, plus the gate and a push); an age rule because a PID probe with `os.kill(pid, 0)` terminates the holder on Windows (`python/stdlib-windows-portability.md`, DER S-ew7mucsg) |
| `SESSION_IDLE_CLOSED_S` | 86400 s | a session with no `SessionEnd` counts as closed after a day idle; a live session is rarely idle that long |
| `SPOOL_MAX_AGE_DAYS` | 30 days | raw text stays local no longer than Claude Code keeps its own transcripts by default (`claude/data-retention.md`, DOC S747) |
| `SPOOL_ROW_MAX_CHARS` | 4000 characters | a pasted log cannot fill the spool; distill needs the question, not the paste |
| `QUESTION_MAX_CHARS` | 500 characters | a committed question is a question, not a document |
| `SUMMARY_MAX_CHARS` | 300 characters | an outcome summary says what happened, not the answer |
| `ENTROPY_MIN_LEN` (`_tools/redact.py`) | 20 characters | shorter random-looking strings are mostly words and ids the kb names |
| `ENTROPY_MIN_BITS` (`_tools/redact.py`) | 3.5 bits per character | keys and tokens sit above it; long CamelCase names can too, which the kb-word rule (Redaction) keeps |
| `QUOTE_MAX_WORDS` | 25 words | a short quote is checkable on the page and stays within the kb's quoting rules (`kb/_self/content-rules.md`) |
| `FAILED_RETRIES` | 0 | a finding whose change turned CI red is never retried; a person or a later finding decides |
| `CONFLICT_BRANCH_PREFIX` | `querylog/` | conflict branches are recognisable, and `status` lists their open MRs |
| `FALLBACK_GITLAB_HOST` | `gitlab.com` | used only when `origin`'s url names no host |
| `DIGEST_PERIOD` | one ISO week | the digest shows once, at the first `SessionStart` of the week |

## Portability

- **One Python entry point.** Every hook calls `sh _tools/kbpy <script>`, which finds `python3`, `python` or `py -3` and checks that the one it found runs. Hooks without `args` run in `sh -c` on macOS and Linux and in Git Bash on Windows, and on Windows `python3` is only an alias (`claude/hooks.md`, DOC S743; `python/stdlib-windows-portability.md`, DOC S-sjuwcuhk). Without Git Bash, Windows hooks run in PowerShell, the launcher cannot start, and nothing is logged there.
- **The lock uses no `fcntl`**, which is Unix only: an `O_EXCL` file (or an `os.mkdir` directory) holding the owner's PID and start time, stale after `LOCK_STALE_S`, never checked by signalling the PID (`python/stdlib-windows-portability.md`, DOC S-oavxfpsn, S-ew7mucsg).
- **The `SessionEnd` launcher detaches** with `start_new_session=True` on POSIX and `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` on Windows, with stdin, stdout and stderr redirected (`python/stdlib-windows-portability.md`, DOC S-dabwnzz5). Whether Claude Code's hook process on Windows sits in a job object that ends the child is undocumented; the launcher's Windows test decides.
- **Files and processes:** every file is opened with `encoding="utf-8"` (and `newline="\n"` when writing), paths go through `pathlib`, and subprocesses take argument lists, never `shell=True`.
- **Tested on Linux and Windows in CI**, macOS on the maintainer's machine. The Windows job runs only when the tools, hooks, plugin, CI file or lock change, since its minutes count against the Free quota (`gitlab/hosted-runners-windows.md`, DOC S-lfuz2ssn; `kb/_self/git.md`).

## Reporting

- **Digest:** `querylog.py digest` computes the week's numbers (lookups, verdicts, misses fixed, findings by kind and state, drops) from the committed store, identically in any clone.
- **Status:** `querylog.py status` lists open source findings ranked by result characters, open conflict MRs, and reverted automatic commits.
- **Audit trail:** `git log --format='%h %(trailers:key=KB-Auto,valueonly)'`.
