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

## Versions

- **A module declares what it takes.** `KBEXT_REQUIRES` is a string of comma-separated bounds on `MAJOR.MINOR`, such as `>=0.1,<2.0`, with the operators `>=`, `>`, `<=`, `<` and `==`. `API_VERSION`'s `MAJOR.MINOR` must meet every bound. A module with none, or one that is no such string, is refused: an extender that does not say which API it was written for is not loaded.
- **A refusal is one line.** A missing module, a missing attribute, an import that raises, a version outside `KBEXT_REQUIRES`, a malformed bound and a bad setting exit 2 with one line on stderr that starts `kbext: point POINT: module MODULE, layer LAYER (FILE)`, the layer being `clone`, `group`, `root`, `user` or `entry point`, and FILE the settings file relative to the workspace or, for an entry point, the distribution.

## Commands

- **`kbext.py resolve POINT --root WS [--kb-root NAME]`** imports the module, checks its version and prints `POINT module:attr (layer LAYER, file FILE)`, or `POINT module:attr (entry point of distribution NAME)`; exit 0, or 2 for a refusal above.
- **`kbext.py call POINT --root WS [--kb-root NAME] --json ARGS`** resolves the extender and calls it with the JSON list `ARGS` as its positional arguments (`[]` with no `--json`), then prints its answer as one JSON line. An extender that is no callable, that raises, or whose answer is not JSON exits 2 with the same one-line form. The commands never exit 1.
