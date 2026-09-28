# Host plugin lookup across roots

Whether an installed plugin serves a team root beside `kb/public` in a host project, as `kb/_self/plugin.md` section 6 describes. **Setup:** Claude Code 2.1.283 on macOS; Haiku 4.5 for the headless runs; the kb at 266 public topics. Everything stayed on one machine: a scratch clone of this repository with its remote removed (the "fork"), a scratch host project (an empty git repository), and no push.

## Method

1. **Fork with a team root.** `python3 _tools/kbroot.py add team --prefix TM --visibility internal`, then one article, `team/intune/compliance-naming.md` (the team's `CMP-<platform>-<ring>-<purpose>` naming rule for Intune compliance policies and its grace-period practice), citing one source row `TM-unavfdbc` (`https://wiki.corp.example.com/endpoint/intune-compliance-naming`). Placeholders only: `corp.example.com`, `PL-LT-00123`, `PL-SRV-0042`, `jan.kowalski`. The team article leaves out the public fact the question also needs, so a full answer has to come from both roots. In the fork: `check.py` `errors=0`, `build_index.py --check`, `fetch.py --offline` and `tests.py` pass (after the test fix below).
2. **Question**, spanning both roots: "what is our team's naming rule for Intune compliance policies, and can the built-in Mark device noncompliant action be removed?" The first part is only in `team/`, the second only in `public/intune/compliance-policies.md:35`.
3. **Three ways a host gets the kb**, each run headless in the host (`claude -p --output-format stream-json --verbose --model haiku --no-session-persistence`, the kb tools allowed with `--allowedTools`):
   - **Installed plugin:** `claude plugin marketplace add <fork> --scope local` and `claude plugin install it-ops-kb@it-ops-kb --scope local` in the host (both land in the host's `.claude/settings.local.json`, a `directory` marketplace source); `--setting-sources project,local`.
   - **`--plugin-dir <fork>`** with `--setting-sources project` (the local-scope install left out).
   - **`KB_ROOTS`:** the team root copied outside any clone and served by this repository's `_tools/kb_mcp.py` with `KB_ROOTS` set on the server, from an `--mcp-config` file with `--strict-mcp-config` (the same server entry `claude mcp add --scope local kb -e KB_ROOTS=...` writes, without registering it).
4. **The server alone:** the installed copy's `_tools/kb_mcp.py` driven over stdio (initialize, `kb_status`, `kb_pack`), no model.

## Results

| mode | first run | after the fixes | pack carries | answer cites |
|---|---|---|---|---|
| installed plugin | `coverage: none` for both parts in 2 of 2 runs ($0.060 and $0.019); the traced run passed `domain: "Intune"` | good, $0.015, 2 turns | both roots | `team/intune/compliance-naming.md:16, :17, :18` and `public/intune/compliance-policies.md:35` |
| `--plugin-dir` | (run after the fixes) | good, $0.014, 2 turns | both roots | `team/...:16, :18` and `public/...:35` |
| `KB_ROOTS` | (run after the fixes) | good, $0.055, 2 turns, with `domain: "intune"` | both roots | `team/...:16, :18` and `public/...:35` |
| server over stdio | good | good | both roots, one footer with `TM-unavfdbc` and the `S-` urls | (no model) |

The session's init event lists `plugin:it-ops-kb:kb` connected and the eight `mcp__plugin_it-ops-kb_kb__*` tools in the first two modes, and `kb` (source `dynamic`) with the `mcp__kb__*` tools in the third. A plugin from a `directory` marketplace loads from that directory, not from the `plugins/cache/` copy the install also writes.

Raw pack, installed copy's server, the whole question (trimmed to the first lines per article):

```text
coverage: good (best article matches 10 of 11 key words: action, built-in, complianc, intun, mark, naming, noncompliant, policy, rule, team)

## team/intune/compliance-naming.md  Team Intune compliance policy naming  [complete, retrieved 2026-09-28]
- team/intune/compliance-naming.md:16 Team naming rule: every Intune compliance policy is named `CMP-<platform>-<ring>-<purpose>`, ... [DOC TM-unavfdbc]
- team/intune/compliance-naming.md:18 The team sets the schedule of the built-in "Mark device noncompliant" action to 1 day on every `CMP-*-PROD-*` policy, ... [DOC TM-unavfdbc]

## public/intune/compliance-policies.md  Intune compliance policies  [complete, retrieved 2026-09-26]
- public/intune/compliance-policies.md:35 Every compliance policy includes the built-in default action **Mark device noncompliant**, scheduled at **0 days** (immediately); this schedule can be changed to grant a grace period, but the action itself can't be removed. [DOC S-u3qwumeu]

sources:
  -> TM-unavfdbc  https://wiki.corp.example.com/endpoint/intune-compliance-naming
  -> S-u3qwumeu  https://learn.microsoft.com/en-us/intune/intune-service/protect/actions-for-noncompliance
```

`kb_status` of the installed copy: `roots: public (prefix S, public, 266 topics, 2644 sources); team (prefix TM, internal, 1 topics, 1 sources)`.

## What failed, and the fixes

- **A capitalised domain narrowed every pack to nothing.** Haiku called `kb_pack` with `questions` and `domain: "Intune"`; the domain directories are lowercase, so the pack saw no units and printed `coverage: none; not in the kb: complianc, intun, naming, policy, rule`, a false `none` the model reported as "the kb does not cover this". Not specific to roots: the same call on this repository gave `none` for a question it covers. Now `kbfacts.domain_prefix` matches a domain against the kb's paths without regard to case, and `kb_pack`, `kb_search` and `rag.py pack`/`search -d` refuse a domain no path is under, listing the domains, instead of packing nothing (`_tools/test_kb_mcp.py`, `test_domain_is_matched_without_case_and_an_unknown_one_is_refused`).
- **`kb_status` of a copy installed from a local directory marketplace** printed `commit: unknown (not a git clone or an installed plugin copy)` beside `installed_as: plugin ..., version <sha>`: there is no clone under `plugins/marketplaces/` to resolve the version in. The version (the commit) is now the commit (`test_status_of_a_plugin_copy_from_a_directory_marketplace`).
- **The fork's own test run failed** on a root named `team`: `_tools/test_kbroot.py` copied the fork's roots into its kb copy and `_tools/test_kb_root.py` added a `team` root beside them. The first now drops a fork's roots from its copy; the second uses a fixture root (`fixture`, prefix `FXT`) a fork does not take.
