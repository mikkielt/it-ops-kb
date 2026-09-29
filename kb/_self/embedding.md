# Embedding: the kb inside a host MCP server

A host MCP server is another team's server that answers its own clients (a Copilot Studio agent, a chat front end) and adds the kb's lookups to its tools: it runs `_tools/kb_mcp.py` as a stdio child from a clone of this repository and re-exposes some of its tools. This file is the contract such a host relies on: how it starts the child, which roots it serves, which tools it re-exposes and under what names, what it copies into its own descriptions, when it restarts, and the test that pins all of this. What the server does for a Claude Code session is in `kb/_self/plugin.md`; its flags are in `kb/_self/tools.md`.

The other path needs no host: `_tools/kb_http.py` serves the same tools and instructions over Streamable HTTP to a client that connects to the kb directly, and serves only `kb/public` unless its `--roots` names more (its docstring); `kb/_self/hosting.md` deploys it.

## 1. Start the child

- **Command:** `python3 <clone>/_tools/kb_mcp.py --roots public`, spawned as a child process with stdin and stdout as pipes: newline-delimited JSON-RPC 2.0, UTF-8, only JSON-RPC on stdout, logs on stderr; the server exits when stdin closes. Python 3.11+ standard library only, nothing to install (`kb/_self/plugin.md`, section 3).
- **Working directory:** any. The server finds the kb from its own file's location, never from the working directory; the contract test starts it with the filesystem root as its working directory.
- **`KB_INDEX`:** the directory for the pack index. Without it the index goes to `CLAUDE_PLUGIN_DATA`, else `_cache/` in the clone, else a temp directory; `KB_INDEX=0` keeps it in memory only. Point it at a writable directory the host owns when the clone is read-only. A server limited by `--roots` names its index file after that root set (`kbindex-r<hash>-...`), so servers with different root sets can share the directory. The first lookup after a start builds the index when no file for the current kb exists; the server starts that build at once, while the host is still connecting.
- **`KB_ROOTS`:** directories of roots kept outside the clone (`kb/_self/plugin.md`, section 6). A host leaves it unset unless those roots are meant for its audience, and still names what it serves with `--roots`.
- **Check before serving:** `python3 <clone>/_tools/kb_mcp.py --roots public --status` prints the copy's commit, census tag and the roots served, and exits. An unknown root name stops either form with exit 2 and the error on stderr.

## 2. Roots: one instance per audience

`python3 _tools/kb_mcp.py` without `--roots` serves every root in the clone (`kb/public`, each `kb/<name>/`, the `KB_ROOTS` directories). For an audience outside the team that owns an internal root, the host passes `--roots public`. A root is a filter on what the tools read, not access control: the `root` argument of `kb_pack` and `kb_search` only narrows within the served roots, and nothing in a request can widen them. A host with two audiences runs two children, each with its own `--roots`, and routes each client to one of them. Under any `--roots`, `kb_show` still reads the kb's own docs (`kb/_self/`) and the repository's `README.md`, and never `_private/` or `_cache/`.

## 3. Handshake and the re-exposed tools

- **Handshake:** a legacy `initialize` (the server answers the protocol version asked for when it knows it, else 2025-11-25) then `notifications/initialized`, or a 2026-07-28 `server/discover`; then `tools/list` and `tools/call`. The module docstring of `_tools/kb_mcp.py` is the full reference.
- **Tools:** the host re-exposes `kb_pack`, `kb_search` and `kb_show`, under its own names with a `kb_` prefix (`kb_pack` as is, or `kb_docs_pack`), so a model tells them apart from the host's live tools. It passes the arguments through unchanged, as the input schemas from `tools/list` describe them, and returns the text block as it came. The other tools (`kb_facts`, `kb_audit`, `kb_source`, `kb_status`, `kb_topics_for`) are not in the contract and may change at any version.
- **Descriptions:** every kb tool description starts "Documentation facts from it-ops-kb (not live device or directory data)"; the host keeps that opening in its own descriptions.

## 4. Copy the instructions into the host's descriptions

The kb's lookup rules travel in the server's `instructions` (the `initialize` result) and in `AGENTS.md`, neither of which reaches a host's clients: a client sees only the host's server name and description and the tool descriptions the host writes. Copilot Studio's orchestrator decides whether to call a server from its name and description and takes each tool's name, description and inputs from the server (`kb/public/agents/copilot-studio-mcp-client.md`, "Client behaviour"). So the host:

- puts the kb's `instructions` text into its `kb_pack` description (or its server description), leaving out only sentences that name tools it does not re-expose;
- puts the none rule into the description of every tool it re-exposes: when a pack says `coverage: none`, say the kb does not cover it and add nothing from memory;
- keeps the rest of the coverage rules with the none rule: `good` answers from the pack, and under a `check:` line only if a cited line answers the question itself; `weak` gets one reworded `kb_pack` or one `kb_show`; `UNK` and `COMMUNITY` facts are leads, not answers; answers cite `path:line` and the source url.

## 5. Updates: restart on a census tag

- **What to run:** a clone checked out at a census tag, `census-YYYY-MM-DD`, a commit whose sources were all confirmed current on that date (`kb/_self/git.md`; `kb/_self/plugin.md`, section 4). To move, the host checks out the newer tag and restarts the child.
- **Why restart:** the kb's files are re-read while the server runs (the pack index is rebuilt when a kb file changes), but the server's code, `instructions`, tool list and input schemas load once, at start. After a restart the host compares `serverInfo.version` with the version it copied its descriptions from, and on a change reads `instructions` and `tools/list` again and updates its own descriptions.
- **`kb copy:` line:** when the clone's commit is behind the branch it follows (its upstream, else `origin/HEAD` or `origin/main`, from local refs only), every `kb_pack` result opens with a `kb copy: N commits behind ...` line. A server started with `--roots` (as a host does) gives only that staleness line, with no path, upstream or command, and its `kb_status` leaves out `update` and `kb_dir`; an unlimited server names the update command, which for a clone at a census tag is checking out the newest `census-*` tag. A host pinned to a tag that fetches newer commits gets the line in every pack.

## 6. The contract test

`_tools/fixtures/kb_mcp_contract.json` pins what a host relies on: the server's `VERSION`, a sha256 of its `instructions`, and the names and input schemas of `kb_pack`, `kb_search` and `kb_show`. The `test_embed_contract_*` tests in `_tools/test_kb_mcp.py` start `_tools/kb_mcp.py` as a host does (a stdio child, working directory at the filesystem root, `KB_ROOTS` and `CLAUDE_PLUGIN_DATA` unset), compare the live contract with the fixture, call each of the three tools once (a text block, `isError` false, and a `coverage:` line from `kb_pack`), and check that a planted schema or instructions change is caught. A change to any pinned part at the same `VERSION` fails; a change with `VERSION` moved passes once the fixture is regenerated with `uv run --frozen python _tools/test_kb_mcp.py --write-contract`. Descriptions, titles and the tools outside the three are not pinned. The `test_embed_roots_*` tests hold `--roots` to section 2. Run them with `python3 _tools/tests.py -k embed`.
