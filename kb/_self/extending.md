# Extending: how a group's extenders are found and loaded

A group extends the kb from its own repository with Python functions at named extension points. `_tools/kbext.py` finds one for a point, checks it against the extension API version and, for `call`, runs it. It uses the standard library only, and a shipped tool reads an extender through `kbext.load`, never by its own search.

## Finding an extender

- **`API_VERSION` is the extension API's version.** `kbext.API_VERSION` is a `MAJOR.MINOR.PATCH` string of its own, apart from the content and the plugin. Below 1.0 no compatibility is promised; an extender that declares `>=0.1` stays valid when 1.0 comes.
- **A setting names the extender first.** `load(point, root, kb_root=None)` reads `extensions.<point>` through `kbsettings.layered`: the group, clone, kb root and user files, later over earlier, a group file able to lock the key (`kb/_self/coordination.md`, Coordination settings). The value is `module:attr`, where `attr` may be dotted, or a module name alone, which makes the module the extender.
- **An entry point is the second source.** With no `extensions.<point>` in any layer, the one entry point of group `it_ops_kb.<point>` that `importlib.metadata.entry_points` lists is the extender (its value is `module:attr` as well). Two entry points for one point exit 2 naming both distributions; no setting and no entry point exit 2 naming the point.
- **`extension_paths` puts a directory on `sys.path`.** Each settings layer may list directories under `extension_paths`; each one is read relative to the directory of the file that names it (an absolute path stays) and put on `sys.path` before the import, a later layer's first. A group's `ext/` directory in its overlay repository is found this way, with no install step.

## Versions

- **A module declares what it takes.** `KBEXT_REQUIRES` is a string of comma-separated bounds on `MAJOR.MINOR`, such as `>=0.1,<2.0`, with the operators `>=`, `>`, `<=`, `<` and `==`. `API_VERSION`'s `MAJOR.MINOR` must meet every bound. A module with none, or one that is no such string, is refused: an extender that does not say which API it was written for is not loaded.
- **A refusal is one line.** A missing module, a missing attribute, an import that raises, a version outside `KBEXT_REQUIRES`, a malformed bound and a bad setting exit 2 with one line on stderr that starts `kbext: point POINT: module MODULE, layer LAYER (FILE)`, the layer being `clone`, `group`, `root`, `user` or `entry point`, and FILE the settings file relative to the workspace or, for an entry point, the distribution.

## Commands

- **`kbext.py resolve POINT --root WS [--kb-root NAME]`** imports the module, checks its version and prints `POINT module:attr (layer LAYER, file FILE)`, or `POINT module:attr (entry point of distribution NAME)`; exit 0, or 2 for a refusal above.
- **`kbext.py call POINT --root WS [--kb-root NAME] --json ARGS`** resolves the extender and calls it with the JSON list `ARGS` as its positional arguments (`[]` with no `--json`), then prints its answer as one JSON line. An extender that is no callable, that raises, or whose answer is not JSON exits 2 with the same one-line form. The commands never exit 1.
