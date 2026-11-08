# Extending: how a group's extenders are found and loaded

A group extends the kb from its own repository with Python functions at named extension points. `_tools/kbext.py` finds one for a point, checks it against the extension API version and, for `call`, runs it. It uses the standard library only, and a shipped tool reads an extender through `kbext.load`, never by its own search.

Everything not in `kbext.SURFACE` is internal: only the extension points and settings keys in the two tables below are the public API, and a group may rely on nothing else. The tables hold the code's registry, entry for entry: `python3 _tools/kbext.py surface` prints `API_VERSION` and the registry (`--json` for a tool), and `python3 _tools/selfdoc.py check` fails when a row is missing, differs from the code or names an entry the code does not have.

## Extension points

`SURFACE` is a literal (`ast.literal_eval` reads it) of dicts with `name`, `signature` and `added`, the `API_VERSION` that introduced the entry; a deprecated entry also has `deprecated` and, once it stops working, `removed`. The extender of a point is the `module:attr` that `extensions.<point>` names.

| name | signature | added | deprecated | removed |
| --- | --- | --- | --- | --- |
| `lane` | `module with path_lane(path) -> str and commit_paths(repo, sha) -> list` | 0.1.0 | | |
| `forge` | `Adapter(target, run, cwd=None) with request, pipelines, pipeline, jobs, trace, set_description, merge` | 0.1.0 | | |
| `ranker` | `rank(question, candidates) -> list of candidate paths` | 0.1.0 | | |
| `mcp_tools` | `list of dicts with name, description, inputSchema and call(arguments) -> str` | 0.1.0 | | |
| `ingest_mappers` | `module with SUFFIXES and mapper(repo_dir, rev, files) -> dict` | 0.1.0 | | |
| `leak_scan` | `file_hits(path, text, allow, pinned=()) -> list` | 0.1.0 | | |
| `backlog_commands` | `list of modules adding or replacing a command through bl_cli.register(name, handler, add_arguments=None, help=None) or bl_cli.extend(name, wrap, add_arguments)` | 0.1.0 | | |

## The forge point

`extensions.forge` names a class, `Adapter(target, run, cwd=None)`, that `bl_forge.arm(root)` builds in place of the `Glab` or `Gh` arm the `forge` setting picks: `target` is the `bl_forge.Target` (`forge`, `host`, `project`) of the project, `run` the command runner (`run(argv, cwd=None) -> (code, out, err)`) and `cwd` the workspace root. With no `extensions.forge` and no entry point of group `it_ops_kb.forge`, `arm` returns the arm the `forge` setting picks, as before; a named adapter that cannot be loaded exits 2 with kbext's one line and never falls back. An empty `forge` setting still raises `NoForge` before the adapter is built. `bl_forge.read_request`, `set_description` and `merge_own` and the reads of stalled and land all go through `arm(root)`, so the adapter answers each of them; `url_arm`, which has a remote's url and no root (`red-pipeline`, the intake `ci` detector and the query log's delivery), keeps reading that url's own forge. The adapter answers in GitLab's words, `opened`, `merged` and `closed` for a request and `success`, `failed`, `canceled`, `skipped`, `manual`, `running` and `pending` for a pipeline or job.

| method | returns |
| --- | --- |
| `request(branch=None, title_prefix=None)` | the request of the source branch, or of the title starting with the prefix, an open one before a merged one before a closed one, or None for none; an object with attributes `state`, `iid`, `title`, `branch`, `url`, `pipeline` (its head pipeline's status or None), `merge_status`, `mergeable`, `auto_merge`, `merged_at` and `description` (`""` for none), as `bl_forge.Request` has; raises `bl_forge.ForgeError` when the forge cannot be read |
| `pipelines(ref=None, sha=None, limit=1)` | a list of at most `limit` pipelines of the ref or commit, newest first, each with attributes `id`, `sha`, `status`, `url` and `ref`, as `bl_forge.Pipeline` has |
| `pipeline(ref)` | the newest pipeline of the ref, or None for none |
| `jobs(pipeline_id)` | the pipeline's jobs as a list of dicts in GitLab's job words (`id`, `name`, `status`, `failure_reason` and `started_at`, the keys the readers use), a retried job's attempts all in it, or None when the list cannot be read; an adapter that counts its list reads keeps `job_calls`, which the `ci.pipeline` ops row reports |
| `trace(job_id)` | the job's log as text, `""` when it cannot be read |
| `set_description(request, text)` | `(ok, output)`: whether the request's description became the text, and the forge's answer or error line |
| `merge(request)` | `(merged, output)`: whether the request merged at once, and the forge's output; an adapter that refuses to merge sets a `merge_refusal` text, which `merge_own` raises as `Rejected` before any call |

## Settings keys

The keys of a settings file (`kb/_self/coordination.md`, Coordination settings) that the extension API reads.

| name | signature | added | deprecated | removed |
| --- | --- | --- | --- | --- |
| `extensions` | `object: point name -> module:attr` | 0.1.0 | | |
| `extension_paths` | `list of directories put on sys.path` | 0.1.0 | | |
| `backlog` | `object overriding backlog.json key by key` | 0.1.0 | | |
| `gate_checks` | `list of argument lists run after the shipped gate` | 0.1.0 | | |
| `group` | `string: the group's name` | 0.1.0 | | |
| `leak` | `object with shapes: list of kind and regular expression` | 0.1.0 | | |
| `locked` | `list of key names a later layer may not set` | 0.1.0 | | |

## Finding an extender

- **`API_VERSION` is the extension API's version.** `kbext.API_VERSION` is a `MAJOR.MINOR.PATCH` string of its own, apart from the content and the plugin. Below 1.0 no compatibility is promised; an extender that declares `>=0.1` stays valid when 1.0 comes.
- **A setting names the extender first.** `load(point, root, kb_root=None)` reads `extensions.<point>` through `kbsettings.layered`: the group, clone, kb root and user files, later over earlier, a group file able to lock the key (`kb/_self/coordination.md`, Coordination settings). The value is `module:attr`, where `attr` may be dotted, or a module name alone, which makes the module the extender.
- **An entry point is the second source.** With no `extensions.<point>` in any layer, the one entry point of group `it_ops_kb.<point>` that `importlib.metadata.entry_points` lists is the extender (its value is `module:attr` as well). Two entry points for one point exit 2 naming both distributions; no setting and no entry point exit 2 naming the point.
- **`extension_paths` puts a directory on `sys.path`.** Each settings layer may list directories under `extension_paths`; each one is read relative to the directory of the file that names it (an absolute path stays) and put on `sys.path` before the import, a later layer's first. A group's `ext/` directory in its overlay repository is found this way, with no install step.

- **`lane` is read by `bl_base.lane(root)`.** `extensions.lane` (or an entry point) names the lane module, which has `path_lane(path)` answering `code` for a code path and `commit_paths(repo, sha)`; it wins over `backlog.json`'s `lane_module`, a key that stays supported in API 1 for the kb's own `kblane`. With neither there is no code lane. A named lane module that cannot be loaded is a refusal, never a fall back to `lane_module`.
- **`gate_checks` is read by `kg_sync.group_gate(root)`.** Each argument list of the `gate_checks` lists of the settings layers (group, clone, kb root, user, in that order) runs without a shell from the repository root, with a timeout of its own (`KB_GATE_CHECK_TIMEOUT_S`, default 600 s). `kbgit.py sync --push` runs them after its shipped checks and `backlog.py done` after the item's checks; a failure refuses (exit 1 for sync) naming the argv, the layer that lists it and the exit code (`timed out` or `not started` for the others), and with none set both run as before. The list is read from each layer's file, since `kbsettings.layered` takes only an object.

## Point `mcp_tools`: a group's own tools on the kb MCP server

- **The team's own `kb_mcp.py` serves them.** `extensions.mcp_tools` is one `module:attr` or a list of them (or an entry point of group `it_ops_kb.mcp_tools`); each attribute is a tool dict, or a list of them, with `name`, `description`, `inputSchema` and `call`. The server reads the settings of `CLAUDE_PROJECT_DIR`, else the working directory, once per process, and lists each tool as `<group>_<name>` beside the shipped tools, the group being the settings' `group` string; the description starts with the group name, followed by `: `. A server limited to named roots (`--roots`), `kb_http.py` and the `kbtools.py` catalog do not serve them.
- **`kbext.load_all(point, root, kb_root=None)` loads them.** It returns the extenders of a point in the order its setting names them, the setting being one `module:attr` or a list of them (an entry point gives one), each loaded and version-checked as `load` does with the same refusals; `kbext.configured` tells first whether the group names any, so a group with no `mcp_tools` costs a server no stderr line.
- **A call runs `call(arguments)` and answers its text.** An exception in `call`, or an answer that is no string, is an `isError` result (`error: ...`), never a server failure.
- **A refusal is one stderr line and the shipped tools stay as before.** A tool whose prefixed name is a shipped tool's is left out, the line naming it. No `group` name, or any load failure (a missing module, a version outside `KBEXT_REQUIRES`, a malformed tool dict, a bad setting), leaves all of the group's tools out, the line starting `kb_mcp: point mcp_tools`.

- **`backlog_commands` is read by `bl_cli.load_group_commands(root)`.** `backlog.py` calls it after the shipped modules are imported and before it builds the parser, and it loads the list through `kbext.load_all`. `extensions.backlog_commands` is a list of module names (a point whose setting may be a list, not only `module:attr`); a module adds or replaces commands as it is imported, through `bl_cli.register(name, handler, add_arguments=None, help=None)` or `bl_cli.extend(name, wrap, add_arguments)`. A handler that takes one parameter is called with the arguments alone, any other with `(bl, args)`. A `register` or `extend` of a shipped command's name, or of another group module's, replaces it, and each run of the replaced command prints one stderr line `backlog.py: command NAME is the group's: module MODULE replaces or extends it (layer LAYER)`; `backlog.py -h` ends the help of each command a group added or replaced with `[group NAME]`, the `group` setting. A module `kbext` refuses (it cannot be imported, declares no API version this one meets or raises) is named on stderr (`backlog.py: group commands not loaded: point backlog_commands: module MODULE, layer LAYER (FILE): ...`) and the commands the group's modules registered are all taken back, so the shipped commands run as before.

## Versions

- **A module declares what it takes.** `KBEXT_REQUIRES` is a string of comma-separated bounds on `MAJOR.MINOR`, such as `>=0.1,<2.0`, with the operators `>=`, `>`, `<=`, `<` and `==`. `API_VERSION`'s `MAJOR.MINOR` must meet every bound. A module with none, or one that is no such string, is refused: an extender that does not say which API it was written for is not loaded.
- **A refusal is one line.** A missing module, a missing attribute, an import that raises, a version outside `KBEXT_REQUIRES`, a malformed bound and a bad setting exit 2 with one line on stderr that starts `kbext: point POINT: module MODULE, layer LAYER (FILE)`, the layer being `clone`, `group`, `root`, `user` or `entry point`, and FILE the settings file relative to the workspace or, for an entry point, the distribution.

## The ranker point

- **`rank(question, candidates)` adds one ranked list to the pack.** `kf_index.pack` calls the extender of `ranker` with the question and the qualified paths (`public/intune/x.md`) of the candidate articles, best first, and `kbfacts.rrf` fuses the list it returns with the pack's own order as one more expert, so an article it puts first ranks no lower than without it. A path it returns that is no candidate is dropped; a candidate it leaves out keeps only its own rank. The verdict, the route and the `check:` lines are decided before and do not change; only which articles print, and in what order, can.
- **A failing ranker leaves the pack as it was.** An exception, an answer that is no list, an extender that is no callable and a refusal of `kbext` print one line on stderr that starts `kbext:` and names point `ranker`; the pack then ranks as without one. With no ranker set nothing is read and every pack is byte for byte as before. The extender is resolved once per process and settings file.

## Commands

- **`kbext.py resolve POINT --root WS [--kb-root NAME]`** imports the module, checks its version and prints `POINT module:attr (layer LAYER, file FILE)`, or `POINT module:attr (entry point of distribution NAME)`; exit 0, or 2 for a refusal above.
- **`kbext.py call POINT --root WS [--kb-root NAME] --json ARGS`** resolves the extender and calls it with the JSON list `ARGS` as its positional arguments (`[]` with no `--json`), then prints its answer as one JSON line. An extender that is no callable, that raises, or whose answer is not JSON exits 2 with the same one-line form. The commands never exit 1.
