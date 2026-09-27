---
topic: dsc/mcp-server
priority: P0
applies_to: "Microsoft DSC 3.2.0, 3.3.0 (release/v3.3 @ ea572fa), 3.4.0-preview.1"
retrieved_utc: 2026-09-26
sources: [S100, S108, S109, S113, S116, S117, S118, S134, S136, S141, S-fs2ec5ax, S-mv4k22q6, S-catcwj3d, S-liojjbc4, S-awsbvym2, S-ezl54xgl, S-eu4akijw, S-pr75qw5k, S-vnizihrz, S-5xcgjq4m, S-kb73mn6y, S-wwzbgp6q, S-mc3u4cy5, S-4vi7fb6a, S-tgdrpywm, S-nchhrpes, S114, S115, S132, S133]
status: complete
---

# `dsc server` / `dsc mcp`: the MCP tool list per version

## Summary
- 3.0.x and 3.1.x have no MCP server. 3.2.0 adds `dsc mcp` with 5 tools. 3.3.0 renames the command to `dsc server` (alias `mcp`) and has 8 tools. 3.4.0-preview.1 has the same 8 tools and adds a `what_if` parameter to the two invoke tools.
- Transport is stdio only (rmcp `transport::stdio`). There is no authentication and no per-tool allow-list inside dsc.
- In 3.3.0, `invoke_dsc_config` and `invoke_dsc_resource` have **no** `what_if` field. A `what_if: true` argument is ignored and the set runs for real, although the 3.3.0 release notes list "Add --what-if in MCP server tools" (PR #1697).

## Facts
- No `mcp`/`server` subcommand exists in `args.rs` at v3.0.0 or v3.1.0. [CODE S132: dsc/src/args.rs#SubCommand; CODE S133: dsc/src/args.rs#SubCommand]
- v3.2.0 defines `mcp` ("mcpAbout") with tools in `dsc/src/mcp/`: invoke_dsc_config, invoke_dsc_resource, list_dsc_functions, list_dsc_resources, show_dsc_resource. [CODE S134: dsc/src/args.rs#SubCommand.Mcp]
- 3.3.0 defines `#[clap(name = "server", alias = "mcp")]`, help text "Use DSC as a server over JSON-RPC (useful as MCP server)". Tools are in `dsc/src/server/`. [CODE S100: dsc/src/args.rs#SubCommand.Server; CODE S108: dsc/src/server/invoke_dsc_config.rs#invoke_dsc_config]
- The server runs `server.serve(stdio())` and returns the instruction string "This server provides tools that work with DSC (DesiredStateConfiguration) which enables users to manage and configure their systems declaratively." [CODE S141: dsc/locales/en-us.toml#instructions; CODE S-fs2ec5ax: dsc/src/server/mod.rs#start_server_async; CODE S-mv4k22q6: dsc/src/server/mcp_server.rs#McpServer.get_info]
- 3.3.0 `InvokeDscConfigRequest` fields: `operation` (get|set|test|export), `configuration` (YAML string), `parameters` (optional YAML string). There is no `what_if`. Set runs as `configurator.invoke_set(false)`. [CODE S108: dsc/src/server/invoke_dsc_config.rs#InvokeDscConfigRequest]
- 3.3.0 `InvokeDscResourceRequest` fields: `operation` (get|set|test|export|delete), `resource_type`, `properties_json`. There is no `what_if`. [CODE S-catcwj3d: dsc/src/server/invoke_dsc_resource.rs#InvokeDscResourceRequest]
- The request structs have no `deny_unknown_fields`, so an unknown `what_if` key is dropped during deserialization and the operation runs normally. [DER S108, S-catcwj3d: neither request struct sets deny_unknown_fields, and serde ignores unknown fields by default]
- 3.4.0-preview.1 `invoke_dsc_config` adds `what_if: Option<bool>` ("Only valid with the 'set' operation"; otherwise `invalid_params` "whatIfOnlySet"). It sets `execution_type = WhatIf`, so results carry `metadata.Microsoft.DSC.executionType = whatIf`. [CODE S109: dsc/src/server/invoke_dsc_config.rs#InvokeDscConfigRequest.what_if]
- 3.4.0-preview.1 `invoke_dsc_resource` adds `what_if` for set/delete: "Resources without native what-if support return a synthetic result derived from 'test'". [CODE S-liojjbc4: dsc/src/server/invoke_dsc_resource.rs#InvokeDscResourceRequest.what_if]
- The strings `whatIfOnlySet` and "simulate the change" appear in the 3.4.0-preview.1 dsc.exe and not in the 3.3.0 dsc.exe (Windows x64 zips). [DER S114,S115: `strings` count 0 vs 1/2]
- Tool annotations are the same in 3.3.0 and 3.4.0-preview.1: invoke_dsc_config and invoke_dsc_resource have readOnly=false, destructive=true, idempotent=true, openWorld=true. invoke_dsc_expression and invoke_dsc_function have readOnly=false, destructive=false. list_dsc_functions, list_dsc_resources, show_dsc_resource and show_dsc_schema have readOnly=true. [CODE S108: dsc/src/server/invoke_dsc_config.rs#invoke_dsc_config; CODE S109: dsc/src/server/invoke_dsc_config.rs#invoke_dsc_config; CODE S-catcwj3d: dsc/src/server/invoke_dsc_resource.rs#invoke_dsc_resource; CODE S-liojjbc4: dsc/src/server/invoke_dsc_resource.rs#invoke_dsc_resource; CODE S-awsbvym2: dsc/src/server/invoke_dsc_expression.rs#invoke_dsc_expression; CODE S-ezl54xgl: dsc/src/server/invoke_dsc_expression.rs#invoke_dsc_expression; CODE S-eu4akijw: dsc/src/server/invoke_dsc_function.rs#invoke_dsc_function; CODE S-pr75qw5k: dsc/src/server/invoke_dsc_function.rs#invoke_dsc_function; CODE S-vnizihrz: dsc/src/server/list_dsc_functions.rs#list_dsc_functions; CODE S-5xcgjq4m: dsc/src/server/list_dsc_functions.rs#list_dsc_functions; CODE S-kb73mn6y: dsc/src/server/list_dsc_resources.rs#list_dsc_resources; CODE S-wwzbgp6q: dsc/src/server/list_dsc_resources.rs#list_dsc_resources; CODE S-mc3u4cy5: dsc/src/server/show_dsc_resource.rs#show_dsc_resource; CODE S-4vi7fb6a: dsc/src/server/show_dsc_resource.rs#show_dsc_resource; CODE S-tgdrpywm: dsc/src/server/show_dsc_schema.rs#show_dsc_schema; CODE S-nchhrpes: dsc/src/server/show_dsc_schema.rs#show_dsc_schema]
- The repo doc page for this command is still titled `dsc mcp` (ms.date 06/17/2026) and documents only `-h`. [DOC S136]

## Reference
| Tool | 3.2.0 | 3.3.0 | 3.4.0-preview.1 | Parameters (3.3.0) | readOnlyHint |
|---|---|---|---|---|---|
| invoke_dsc_config | yes | yes | yes (+`what_if`) | operation, configuration, parameters | false (destructive) |
| invoke_dsc_resource | yes | yes | yes (+`what_if`) | operation, resource_type, properties_json | false (destructive) |
| invoke_dsc_expression | no | yes | yes | expression | false |
| invoke_dsc_function | no | yes | yes | function, parameters (JSON array) | false |
| list_dsc_functions | yes | yes | yes | function_filter, category_filter, description_filter | true |
| list_dsc_resources | yes | yes | yes | adapter | true |
| show_dsc_resource | yes | yes | yes | type | true |
| show_dsc_schema | no | yes | yes | type (schema type) | true |

## Examples
- SNIPPET: Claude Code project `.mcp.json` entry (stdio). Every invoke tool can change the machine it runs on, and on 3.3.0 no argument makes it a dry run; context: dsc 3.3.0 (`server` subcommand, alias `mcp`); checked: syntax [DER S116, S134: 3.3.0 renames `mcp` to `server` with a `mcp` alias]
```json
{ "mcpServers": { "dsc": { "command": "dsc", "args": ["server"] } } }
```
