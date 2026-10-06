---
name: kb-ingest
description: Use when the user asks to ingest, import or source a team's repository into it-ops-kb ("source <repo> and put it here"), or, in a project where the kb is an installed plugin, to turn that project's code and docs into kb facts: picks the root, surveys the repository at a pinned commit with kbingest.py, leaves out secrets, generated and vendored files, proposes topics, writes CODE and DOC facts.
argument-hint: "<repository path or url> [root name] [what the facts should answer]"
---

# Ingest a team's repository into a root

Request: $ARGUMENTS. The facts come from one repository at one pinned commit: its code as `CODE`, its own docs (README, `docs/`, ADRs, runbooks) as `DOC`, so the kb answers questions across a team's services beside `kb/public`. This is a conversation, not a script: at each **Ask** below, propose what you would do and why, and wait for the user.

Read the conduct rules first (`selfdoc.py section` prints one section with its line numbers):

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes"
```

Every other rule of `kb/_self/` is asked for, not read up front. When a step below is reached, run its set: `python3 _tools/rag.py pack --root _self --set <name>` prints that step's tested rule questions, the line that answers each (`path:line`) and the decisions tied to them. The sets of this skill:
- `kb-ingest:where`: before step 1, where the facts land (and step 2, which root)
- `kb-ingest:survey`: before step 3, the survey at a pinned commit
- `kb-ingest:write`: before step 6, writing
- `kb-ingest:commit`: before step 8, commit and report

Any other rule: `python3 _tools/rag.py pack --root _self "<question>"` (`-q` for several parts, `--budget 400`). `coverage: good` names a tested question: follow its line. `weak` or `none`: `python3 _tools/kb_ask.py --root _self "<question>"` has a reader quote the answering lines from the sections, or read the section it names with `python3 _tools/selfdoc.py section DOC HEADING`. A rule you needed and no set or question gave you is a miss: say so in your report, with the question as you asked it.

Facts on the signals used below: `agents/repository-ingestion.md`; on the mapping tools (ctags JSON, language servers, each language's own read-only commands, toolchain pins) `agents/codebase-mapping.md`; on reading PowerShell without running it (`#Requires`, manifests, the AST) `windows/powershell-static-analysis.md`. Run each command on its own (no `;`, `&&`, pipes or loops).

## 1. Where am I, and where do the facts land

Rules of this step (and of step 2): `python3 _tools/rag.py pack --root _self --set kb-ingest:where`.

- **In a clone of it-ops-kb** (the working directory has `_tools/kbroot.py`): "source `<repo>` and put it here" means a root in this clone's `kb/`. `<repo>` is a local clone; for a url, clone it into the scratchpad first (`git clone <url> <dir>`). `KB` below is `.`.
- **In a host project** (the kb is an installed plugin): the plugin copy is read-only by design. Never write into it (`~/.claude/plugins/cache/...` is replaced on every update and deleted 14 days later) nor into `${CLAUDE_PLUGIN_DATA}` (no git history, deleted on uninstall): `claude/plugins.md` in the kb. `<repo>` is usually the host project itself. **Ask** where the facts go, in this order of preference:
  1. **A writable clone of the team's fork of it-ops-kb**, as `kb/<root>/` (the default). It has the gate, KB-* trailers, union-merged ledgers and `kbgit.py sync`, and the fork is the team's marketplace, so every installed copy gets the facts at its next update. A plugin installed from a directory marketplace on that clone loads from the clone itself (`kb/_self/reports/host-plugin-roots.md`), so `/reload-plugins` shows the new facts at once.
  2. **A `KB_ROOTS` directory**: a root kept in another git repository of the team (never the upstream kb). The read tools and `check.py` serve it with `KB_ROOTS=<dir>` set; `kbgit.py`, census and fetch do not, so commits there carry no KB-* trailers and the ledgers have no union merge unless that repository copies the kb's `.gitattributes` lines. The plugin's `kb` server sees it only when a server registration sets `KB_ROOTS` (`kb/_self/plugin.md` section 6).
  
  No clone yet: offer `git clone <fork url> <dir>`, then `/kb-setup` there. Then work on it from the host session: `claude --add-dir <clone>` lets the session edit the clone and loads its skills, this one included (`claude/ci-and-headless.md`). `KB` below is the clone's path: run every tool as `python3 <KB>/_tools/<tool>` (they resolve the kb from their own location, not the working directory) and git as `git -C <KB>`.
- **Remote check, both modes:** `git -C <KB> remote -v`. A clone whose remotes are the upstream kb (`gitlab.com/mikkielt/it-ops-kb`, or its GitHub mirror) takes only a `public` root with placeholders; an `internal` root there is never pushed. Say so before writing anything.

## 2. Which root

- `python3 <KB>/_tools/kbroot.py list`. Reuse a root whose description covers the team or estate: one root per team, not per repository; each repository becomes domains or topics inside it.
- None fits: run `/kb-add-root` (it asks the name, prefix and visibility), then come back here.
- **Visibility:** at least as closed as the repository. A private or internal repository gives an `internal` root (real hostnames, service accounts, tenants and people are allowed there); a `public` root only for a public repository, and then with the placeholders rule (`AGENTS.md`, "Agent conduct"), which the leak tests enforce. Never put facts from a private repository into `kb/public`.

## 3. Survey at a pinned commit

Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-ingest:survey`.

- `python3 <KB>/_tools/kbingest.py survey <repo> [--rev <tag or sha>]`: the remote, the commit, the pinned url form, the attributes, per area the kept files by kind and the files left out; `--files` lists every file with its pinned url. It reads the commit (`git ls-tree`, `check-attr --source`, `cat-file`), never the working tree.
- **Pick the commit:** a release tag or the default branch's head, and it must be on the remote (`on a remote branch: yes`): a pinned url others cannot open is no evidence. **Ask** the user to push, or pick a pushed commit.
- **`pin: none`** (a forge other than github.com or a GitLab host, e.g. Azure DevOps, Bitbucket, GitHub Enterprise): the CODE lint accepts only those pinned urls or a pinned artifact (`artifact_sha256`). Stop and **ask**; never invent a url form.
- **`worktree: differs`**: read every file with `git -C <repo> show <sha>:<path>`, so the facts match the pinned url.
- **What it leaves out, and why:** secret files (keys, `.env`, credential stores, `*.tfstate`); vendored code (submodules, `vendor/`, `third_party/`, `node_modules/`, `linguist-vendored`): someone else's code, which the kb covers from that project's own sources if at all; generated code (lock files, minified files, protobuf output, `linguist-generated`, `gitlab-generated`, a generated-code header): a tool's output, whose source is the generator's input; binaries and oversized files. An `unset` attribute (`-linguist-generated`) keeps a file. A skip is a default, not a verdict: when the team wrote a file the survey skipped, read it deliberately and say so in the plan.
- **Map (opt-in, after the survey):** when the toolchain of a language the survey kept is installed and the topic plan needs the interfaces, dependencies or entry points of a large or unfamiliar codebase, run `python3 <KB>/_tools/kbingest.py map <repo> --rev <sha>` (`--lang` narrows it; `--help` lists the rest). Skip it for a small repository or a language with no installed toolchain: reading the kept files does the same job.
  - **What it runs:** it checks the commit out into a scratch git worktree (no hook runs, no LFS filter fetches), then per language the toolchain's own read-only commands, each as an argument list with a timeout, in a network-off environment (`kb/public/agents/codebase-mapping.md`, and its cookbook `codebase-mapping.csv`, give the forms): Python through `python -I -B -m ast` per file, Go, Cargo, .NET, npm and TypeScript through their manifest, dependency and file-list queries.
  - **What it never runs:** a build, a restore or install, a lifecycle script, an MSBuild target (.NET is only evaluated: `dotnet msbuild -noAutoResponse` with `-getProperty` and `-getItem`, never `dotnet package list`), `npx`, or a program found inside the worktree (the repository's own `node_modules/.bin` entry is refused, PATH keeps only absolute entries outside it and outside the source clone: entries inside either are dropped); a missing toolchain is never installed. .NET is skipped under a global.json that sets `sdk.paths`, Cargo under a root toolchain file that sets a path and under a root `.cargo/config.toml` (or `.cargo/config`) that names a program (`rustc`, a wrapper, `rustdoc`, a target `runner` or `linker`, `rustflags`, a registry `credential-provider`, `doc.browser`, `include`, any `[env]` or `[host]` key), since the kb does not settle whether `cargo metadata --no-deps` starts one; the network-off environment is an allow-list: only PATH, a home, the temporary folders, the locale and the Windows system and profile variables pass (and the toolchain homes `CARGO_HOME`, `RUSTUP_HOME`, `DOTNET_ROOT`, `GOROOT`, `GOPATH`, `GOMODCACHE`, `GOCACHE` as an absolute path outside the clone), so no credential, proxy or toolchain hook (`CARGO_BUILD_*`, `RUSTFLAGS`, `GOFLAGS`, `NODE_OPTIONS`, `JAVA_TOOL_OPTIONS`, `GIT_*` and the rest) reaches a command; a kept variable that names a path inside the worktree or the source clone, or a relative one with a folder part, is dropped too; the NuGet SDK resolver is switched off; the map is leak-scanned and hits redacted with a note. Some of the repository still runs: MSBuild evaluation reads its imports and runs their property functions. Do not add a command by hand; a language the mapper lacks is read from its files.
  - **Its output:** one JSON map under `_cache/ingest/` (`--out` may move it only elsewhere than `kb/`, which it refuses): the commit, `tools`, `packages`, `imports` per file, `entry_points` and `notes`. It is never committed and never cited. A missing toolchain, a timeout, a non-zero exit or a file that does not parse is a note, not a failure; read the notes and say in the plan which areas the map did not cover.
  - **Into the plan:** `packages` and `entry_points` name candidate topics and the interfaces to read first (step 4, item 2), `imports` show which modules depend on which; each is a lead to a file, and the fact is written from that file read at the pinned commit (step 6), not from the map.
- **Pins:** add `--pins` to list the toolchain pins the repository declares at the commit (`survey <repo> --rev <sha> --pins`): `pin<TAB>file<TAB>name<TAB>value` lines (language and runtime versions, target frameworks, pinned packages, `#Requires`), then a `note: pins:` line per pin file it could not read. It reads the pin files as text at the commit and runs no toolchain. The pins describe the repository at that commit: they go into the topic plan (step 5) and onto source rows and topics (step 6), never into a fact. A pin file with a `note:` gives no pin: say so in the plan, do not fill it in from memory.
- **`secret-flagged`:** a kept file whose text has a secret shape. Read it only for its structure (key names, which service reads them); never copy a value into a fact, a quote, a commit message or your reply. If the value looks real, tell the user to have the owner rotate it, naming the file, not the value.

## 4. What is worth a fact

The test for every candidate: a teammate or an agent would ask a question that this fact answers, and the answer is not obvious from opening one file. Reason from the repository's purpose, in this order:
1. **Its own docs** (README, `docs/`, ADRs, runbooks): `DOC`, cited at the pinned url of the doc file. Check each claim against the code it describes; a doc the code contradicts goes to the root's `_conflicts.md` with both citations.
2. **Interfaces:** API routes, CLI commands and flags, message and file formats, config keys with their defaults, the environment variables it reads (names, never values). A published contract (OpenAPI, JSON Schema, `.proto`) is `DOC`; the rest is `CODE` with `path#symbol`.
3. **Operations:** pipeline stages and what triggers them, deploy targets, schedules, required CI variables (names), service accounts and permission scopes, ports, the other services and vendor products it depends on. Where it uses a vendor product the kb covers (Graph scopes, Intune, ConfigMgr), cite the team fact in this root and point to the public topic in Reference; do not restate public facts.
4. **Behaviour that surprises:** defaults, limits, retries, timeouts, error handling, feature flags, anything a comment warns about.

Where the leads for items 2 to 4 come from in a large or unfamiliar codebase, cheapest first:
- the pins (`survey --pins`): the runtime and framework an interface targets;
- the `map` output, when step 3 made one: `packages` and `entry_points` name the interfaces, `imports` say which file depends on which;
- Universal Ctags JSON (`--output-format=json`) or a language server, when the user or the session already has one, for the symbols of a file the map does not cover;
- PowerShell: `#Requires`, manifests and the AST (`Parser.ParseFile`), which parse without running the script (`windows/powershell-static-analysis.md`).

Each is a lead to a file, never a citation: the fact is written from that file read at the pinned commit. Where a tool gave no lead (no toolchain, a note in the map), the files are read and the plan says so.

Write a `CODE` fact only for a claim that matters outside source browsing: an interface, a contract, an entry point, generated output, security or persistence behaviour. Never one per symbol, import or map row: the map lists what a reader can open, the fact says what it means for a teammate's question. Each `CODE` fact cites the file and `path#symbol` and names the map relation it rests on (step 6). The pins go on the source row and in `applies_to`, never in a fact.

Leave out: what the code says line by line (the repository stays the source; the kb holds what answers questions across services), formatting and lint settings, tests except as evidence for behaviour (cite them as `CODE`), commit history and authors, and personal data. A command a teammate runs (deploy, run locally) can be a `SNIPPET:` with `checked: no|syntax|run`.

## 5. Topics

- **Domains:** the team's services or concerns (`deploy/`, `inventory-api/`), or the public domain names when the repository is about a vendor product (`intune/`, `mecm/`), so a pack across roots puts the team's facts beside the vendor's. `python3 <KB>/_tools/rag.py topics` shows the names in use.
- **One topic per subject a question targets:** a service's interface, its configuration, its deployment, its runbook. Never one topic per file or per directory. A topic that already covers the subject is extended (the rules in `/kb-research` step 2).
- **Ask:** present the plan before writing: root, commit, the pins from `survey --pins`, domains, each topic with the files it reads, what is left out and why, and anything the user must decide. Large repositories go in passes, one area per pass.

## 6. Write

Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-ingest:write`.

Follow the contract of `/kb-add-topic` steps 3 to 5 (source rows first, one tag per fact, four sections, `build_index.py`), in `<KB>/kb/<root>/`:
- **Source rows** in the root's `_sources.csv`, one per file cited: url from `python3 <KB>/_tools/kbingest.py url <repo> <path> --rev <sha>`, the row written with `python3 <KB>/_tools/kbid.py add <URL> --root <root> --title T --publisher P --licence L --reuse R --version V`, which prints the id (never a CSV writer). `--title` `<repo> <path> at <short sha>`; `--publisher` the team; `--version` `<tag or branch> @<short sha> (<commit date>)`, and on the row of a pin file the pins it declares (`; python-version 3.14`); `--licence` the repository's licence (SPDX id, `--reuse copy`) or `internal: <team> repository, no licence file` (`--reuse quote`: paraphrase, quotes of 25 words or fewer).
- **Facts:** `[CODE <P>-xxxxxxxx: path#symbol]` (or `path#L10-L20`), `[DOC <P>-xxxxxxxx]` for the team's docs, `[DER ...: how]` for what combines them. In your own words. The map relation a `CODE` fact rests on goes after the pointer in the same tag (`[CODE <P>-xxxxxxxx: src/app.py#run, imported by src/cli.py]`; the lint takes the first `path#symbol` of the note as the pointer and accepts the text after it), else in the sentence; a fact that rests on no relation needs none. `applies_to` names the repository, the commit and the pins that bear on the topic (the runtime or framework its code targets).
- **Retrieval data** in the root's `_retrieval/signals.csv`: the repository's distinctive names (service and module names, API routes, CLI names), so `kb_topics_for` maps code, the host project's included, to these topics. One `_retrieval/lookup_eval.csv` row per topic (`python3 <KB>/_tools/kbid.py eval "<question>"`) keeps it findable.
- What the repository does not say (a production value, an owner) goes to the root's `_gaps.md`, ending `(topic: <domain>/<slug>)`.

## 7. Check

With `KB_ROOTS=<dir>` in front of each command for a root kept outside the clone:
- `python3 <KB>/_tools/build_index.py`, then `python3 <KB>/_tools/check.py` -> `errors=0`.
- `python3 <KB>/.claude/skills/kb-verify/lint.py <root>/<domain>` -> no errors (CODE pointers, pinned sources).
- `python3 <KB>/_tools/rag.py pack "<a question a teammate would ask>" --root <root>` for two or three questions: `good`, citing the new topics; `python3 <KB>/_tools/rag.py eval`.
- `python3 <KB>/_tools/tests.py` in a clone (stage new files first): the leak scan covers every tracked file, secrets in any root included.

## 8. Commit and report

Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-ingest:commit`.

- **Clone of the fork:** `/kb-verify`, then commit in the clone, `feat(kb): ingest <repo> into <root>`, the body naming the repository, the commit and what was left out and why; push with `python3 <KB>/_tools/kbgit.py sync --push` only to the remote the user confirmed (the fork's), never to the upstream kb with an internal root.
- **`KB_ROOTS` directory:** commit in that repository with its own git (`git -C <dir>`), same message; `kbgit.py` does not work there.
- **Later commits of the repository:** first `python3 <KB>/_tools/kbingest.py drift <repo> --rev <new sha> --root <root>` (`--prefix` narrows it; `--remote HOST/PROJECT` when the clone has no origin). It is read-only and rewrites no fact, source row or date; exit 1 means findings. Report each `finding KIND KBPATH:LINE SOURCE-ID PATH#SYMBOL DETAIL` line to the user with its fact and kind (`file-missing`, `moved`, `symbol-missing`, `changed`; `unverifiable` means the commit or file is not in the clone: fetch and run again). The user decides which facts to revisit. `git -C <repo> diff --stat <old sha> <new sha>` names the topics whose files changed, which covers the DOC facts drift does not compare. Re-source what the user chose at the new commit (a new row per file, `superseded_by` on the old one) with `/kb-refresh <root>/<domain>/<slug>`.
- Report: root and where it lives, the commit, topics written with facts by tag, source rows, signal and eval rows, what was left out (counts per reason, and any file read despite a skip), secret-flagged files (names only), drift findings on a later commit, and what the user must decide.
