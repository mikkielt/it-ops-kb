---
name: kb-probe
description: Use when the user asks to probe a documentation provider for it-ops-kb, add or update a provider row (a host such as Microsoft Learn, a team wiki or git host), or when change detection picks a poor signal for a host: measures the provider with live requests and updates its registry row.
argument-hint: "<provider name | new provider name and a sample url> [--root NAME]"
---

# Probe a knowledge provider

Provider: $ARGUMENTS. If empty, run `python3 _tools/provider.py list` and ask which one.

Read `kb/_self/maintaining.md` first, then the `kb/_self/` files this skill relies on: `kb/_self/web-sources.md` (routes and staging), `kb/_self/tools.md` (the commands) and `kb/_self/git.md` (commits and pushes). The registry's columns are in the docstring of `_tools/provider.py`.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops).

## 1. The row
- Public providers live in `_tools/providers.csv`, shared by every root. A team's internal provider (its wiki, its git host) goes in `kb/<root>/_providers.csv` of that team's root, never in the shared file (an `internal` root may name real hosts; `public` files may not).
- A new provider: add its row with a CSV writer (`provider.py` `COLS` order): `provider` (lowercase name), `match` (url prefixes without scheme), and the curated columns from the provider's own documentation: `redirects`, `history`, `search_api` (`{q}` in the template), `mcp_freshness`, `rate_limit`, `reuse`. Leave the measured columns empty.
- Curated values come from documentation or from facts already in the kb (`python3 _tools/rag.py pack "<provider> change detection"`, `agents/doc-change-detection.md`, `agents/doc-lookup-sources.md`); an endpoint the kb relies on and does not yet hold goes in through `/kb-research`.

## 2. Measure
1. `python3 _tools/provider.py probe <name>` (sample: the root's first source the provider serves; `--url URL` for another; `python3 _tools/provider.py --root NAME probe <name>` for a team root). It prints each request and what would change; nothing is written.
2. Check the result against what you expect: a raw form that answers HTML, an ETag that changes per request, a made-up url that answers 200 (soft 404). Probe a second sample url when a result looks accidental.
3. `python3 _tools/provider.py probe <name> --write` stores the measured columns and `probed_utc`. The `*` row (generic) records only the date and a note: one host does not describe the long tail.
4. `python3 _tools/provider.py show <sample url>` shows the form and the signals the fetch tools will use.

## 3. Check and report
- `python3 _tools/check.py` and `python3 _tools/tests.py -k provider`.
- A changed signal changes what the fetch tools trust: say so in the commit body.
- Commit with the probe's evidence lines in the body (`/kb-verify`, then `python3 _tools/kbgit.py sync --push`); commit only when asked.
- Report: the provider, the sample urls, each measured column old -> new, and anything the probe could not decide (put it in the row's `notes`).
