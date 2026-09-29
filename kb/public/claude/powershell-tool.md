---
topic: claude/powershell-tool
priority: P3
applies_to: "Claude Code docs as of 2026-09-29 (permissions, tools reference, skills, hooks pages): the PowerShell tool on Windows, its permission rules, and how skills and hooks choose between Bash and PowerShell; the tool is documented as a preview"
retrieved_utc: 2026-09-29
sources: [S742, S-3yod3u7q, S-dfhq4kbv, S743, S-h5sble4p]
status: partial
---

# Claude Code's PowerShell tool: availability, permission rules, skills and hooks

## Summary
On Windows without Git Bash the PowerShell tool is the only shell tool and the Bash tool is not registered; with Git Bash both exist and the PowerShell tool is on by default for claude.ai and Console accounts. Permission rules for it are written `PowerShell(<pattern>)` with the same shape as Bash rules (`*` anywhere, `:*` as a trailing ` *`, case-insensitive, aliases canonicalised, compound commands split and every part must match). A `Bash(...)` rule names a different tool, so every allowed command needs its own `PowerShell(...)` rule for the PowerShell tool. Skills choose the shell for their injected `` !`command` `` blocks through the `shell` frontmatter key.

## Facts
### Availability and defaults
- Windows without Git Bash: the PowerShell tool is enabled automatically and Claude Code does not register the Bash tool at all. [DOC S-3yod3u7q, S743]
- Windows with Git Bash: the tool is on by default for claude.ai and Console accounts; `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` enables it in Amazon Bedrock, Google Cloud Agent Platform and Microsoft Foundry sessions and `0` turns it off. Linux, macOS and WSL: opt-in, and it needs PowerShell 7 or later (`pwsh` on `PATH`). [DOC S-3yod3u7q]
- On Windows Claude Code detects `pwsh.exe` (PowerShell 7+) and falls back to `powershell.exe` (5.1); with the tool enabled Claude treats PowerShell as the primary shell, and the Bash tool stays available for POSIX scripts when Git Bash is installed. [DOC S-3yod3u7q]
- It starts PowerShell with `-ExecutionPolicy Bypass` at process scope only, which does not override Group Policy `MachinePolicy` or `UserPolicy`; `CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY=1` makes it respect the effective policy instead. [DOC S-3yod3u7q]
- PowerShell profiles are not loaded, and sandboxing is not supported on Windows; both are listed as preview limitations. [DOC S-3yod3u7q]
- From v2.1.214 on Windows: `>` and `>>` write UTF-8 on PowerShell 5.1, text piped to a native command's stdin is UTF-8, and a child that waits on stdin gets end-of-file instead of hanging; before it, `>` wrote UTF-16LE and Python could raise `UnicodeEncodeError` printing non-ASCII. [DOC S-3yod3u7q]
- Exit code 1 from `grep`, `rg`, `egrep`, `fgrep`, `findstr` and `git grep` (v2.1.196+) means no match, and from `git diff` means differences, and neither is reported as a failure; `where.exe` exit 1 means no match and `fc.exe` or `diff.exe` exit 1 means the files differ (v2.1.214+, when the command printed output). [DOC S-3yod3u7q]

### Permission rules
- Rules take the form `Tool` or `Tool(specifier)`, and parentheses inside the specifier are literal. A bare `PowerShell` or `PowerShell(*)` matches every command; as a deny rule the bare tool name removes the tool from Claude's context. [DOC S742]
- PowerShell rules use the same shape as Bash rules: `*` matches at any position, the `:*` suffix equals a trailing ` *`. Example allow rules from the docs: `PowerShell(Get-ChildItem *)` and `PowerShell(git commit *)`; deny `PowerShell(Remove-Item *)`. [DOC S742]
- For Bash rules a trailing ` *` (space then `*`) also matches the bare command, and the space is part of the rule: `Bash(ls *)` does not match `lsof`, `Bash(ls*)` does. The PowerShell section says its rules "use the same shape as Bash rules" but repeats no trailing-space example. [DOC S742]
- Common aliases are canonicalised before matching, so `PowerShell(Get-ChildItem *)` also matches `gci`, `ls` and `dir`; matching is case-insensitive. [DOC S742]
- Claude Code parses the PowerShell AST and checks each command of a compound command on its own; `|`, `;` and, on PowerShell 7+, `&&` and `||` split subcommands, and a rule must match every subcommand for the whole to be allowed. [DOC S742]
- A rule cannot match the primary content field by name: `Bash(command:rm *)` style rules for `command` on Bash and PowerShell are ignored with a startup warning; use `Bash(rm *)` or the PowerShell equivalent. [DOC S742]
- A command with a network (UNC) path argument prompts, on Bash and PowerShell alike, because reaching it can send Windows credentials to that host. [DOC S742]
- A deny or ask rule whose tool name matches no known tool produces a startup warning. [DOC S742]
- No docs page says that a `Bash(...)` allow rule covers a PowerShell call; the hooks reference states that a single `if` rule matches only one tool's calls, so each tool gets its own handler. A repository that allows `Bash(python3 _tools/rag.py *)` for macOS and Linux therefore needs `PowerShell(python3 _tools/rag.py *)` for a Windows session where the PowerShell tool runs the command. [DER S742, S743: rule format names the tool; the `if` sentence for hooks]
- `allowed-tools` frontmatter grants are documented with Bash and file rules and `${CLAUDE_SKILL_DIR}` substitution in Bash rules; whether an `allowed-tools: PowerShell(...)` entry works the same way is not shown on the skills page. [UNK: only Bash examples on the skills page]

### Skills and hooks choose a shell
- A skill's `` !`command` `` and fenced `!` blocks run through the Bash tool by default, or through PowerShell when the frontmatter has `shell: powershell` and the PowerShell tool is enabled; when bash is unavailable they run through the PowerShell tool. [DOC S-dfhq4kbv]
- `shell: bash` on a machine without Git Bash fails the invocation before any command runs, with "Skill <name> requires bash (`shell: bash` in frontmatter) but Git Bash was not found". [DOC S-dfhq4kbv]
- Injected commands never prompt: each is checked against permission rules, and outside auto mode any result other than allow, including a rule that would ask, aborts the invocation; `allowed-tools` pre-approves an unmatched command, deny and ask rules still win. [DOC S-dfhq4kbv]
- A failed injected command aborts the whole skill invocation; with the default bash shell any non-zero exit is a failure except exit 1 from recognised search and comparison commands, and the PowerShell shell has a different carve-out set that includes `grep` and `git diff` but not `find` or `diff`. [DOC S-dfhq4kbv]
- The instructions in a skill's body are followed by Claude with whichever shell tool exists, so a command written with a POSIX environment prefix (`VAR=x cmd`), `&&` chains, `$(...)` or bare `curl` behaves differently in PowerShell 5.1: `&&` and `||` exist only on PowerShell 7+, and `curl` there is an alias of `Invoke-WebRequest`. [DER S742, S-3yod3u7q: `&&`/`||` splitting only on 7+; the shell-selection sentences]
- A `PreToolUse` hook that inspects shell commands matches `Bash|PowerShell`; a hook matching only `Bash` never fires on Windows without Git Bash. [DOC S743, S-3yod3u7q]
- A command hook's `shell` field takes `bash` or `powershell` (default `bash`, or `powershell` on Windows without Git Bash); hooks spawn PowerShell directly, so `"shell": "powershell"` does not depend on `CLAUDE_CODE_USE_POWERSHELL_TOOL`. [DOC S743]
- Git for Windows is optional on native Windows; with it Claude Code uses Git Bash for the Bash tool, without it shell commands go through PowerShell. [DOC S-h5sble4p]

## Reference
| Need | Form | Source |
|---|---|---|
| Allow a read-only PowerShell command | `"PowerShell(Get-ChildItem *)"` in `permissions.allow` | S742 |
| Allow every PowerShell call | `PowerShell` or `PowerShell(*)` | S742 |
| Cover both shells in a hook | matcher `Bash\|PowerShell`, separate `if` per tool | S743 |
| Skill block in PowerShell | frontmatter `shell: powershell` | S-dfhq4kbv |
| Turn the tool off / on | `CLAUDE_CODE_USE_POWERSHELL_TOOL=0` / `=1` | S-3yod3u7q |

Related: `claude/hooks.md` (command hooks on Windows, SessionStart), `claude/permissions-mcp.md` (rule syntax for MCP tools), `claude/skills-and-subagents.md`, `python/stdlib-windows-portability.md`.

## Examples
- SNIPPET: an allow list that covers one command in both shell tools; context: Claude Code 2.1.281 settings.json `permissions` key, Windows with the PowerShell tool enabled; checked: syntax [DOC S742: `Tool(specifier)` form, `PowerShell(...)` rules share Bash's shape]
```json
{
  "permissions": {
    "allow": [
      "Bash(python3 _tools/rag.py *)",
      "PowerShell(python3 _tools/rag.py *)"
    ]
  }
}
```
