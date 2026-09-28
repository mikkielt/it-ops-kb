# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Roots

- **Design a skill that ingests a team's repositories into its roots.** Sources are repository files at a pinned commit (`CODE` tags) and the repositories' own docs, so the kb answers questions across a team's services. Two modes:
  - **From a host project:** the kb is installed as a plugin in another code repository, and an agent working there turns that repository's knowledge into facts of a root. The plugin copy is read-only, so the design has to say where the facts land (the team's fork, a clone, a root under `KB_ROOTS`) and how they get committed.
  - **From this clone:** "source `<repo>` and put it here", run inside this repository.
  - Both modes need the agent to reason and guide the user rather than follow a fixed script: which root the knowledge belongs to or whether to create one (`/kb-add-root`), its visibility, which parts of the repository are worth facts, how to split them into topics, and what to leave out (secrets, generated code, vendored copies).

## Content

- **Sources with `reuse` `unknown`** (treated as paraphrase): their `licence` says what was tried; the terms pages are blocked from the maintainer's network (cyber.gov.au) or refuse scripted reads (iso.org). Read them in a browser (Claude in Chrome during `/kb-refresh`, or a person) and set the class.

## Watch

Triggers, not tasks: act when one fires.

- **`claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them. The block format is in `agents/hybrid-retrieval.md`.
