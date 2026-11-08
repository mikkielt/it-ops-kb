# Extension API changelog

One entry per `kbext.API_VERSION`, newest first: a heading `## MAJOR.MINOR.PATCH` and what changed for a group's extenders (an entry added, deprecated or removed, a signature changed). `python3 _tools/kbext.py lint` fails when the `API_VERSION` of the working tree differs from the one at the newest `ext-v` tag and has no heading here (`kb/_self/extending.md`, Compatibility).

## 0.1.0

The first version of the public extension API, with no compatibility promised before 1.0. The points `lane`, `forge`, `ranker`, `mcp_tools`, `ingest_mappers`, `leak_scan` and `backlog_commands` and the settings keys `extensions`, `extension_paths`, `backlog`, `gate_checks`, `group`, `leak` and `locked` (`python3 _tools/kbext.py surface` prints them with their signatures).
