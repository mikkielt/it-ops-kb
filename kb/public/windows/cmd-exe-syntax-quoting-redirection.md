---
topic: windows/cmd-exe-syntax-quoting-redirection
priority: P3
applies_to: "cmd.exe, the Windows command interpreter: invocation switches, special characters and quoting, command operators, redirection and the command-line string limits, as documented on Microsoft Learn (Windows Commands reference; read 2026-10-15)"
retrieved_utc: 2026-10-15
sources: [S-yna7gijv, S-ikuzvclu, S-gp367igh, S-gydqaolr, S-jbeh3qg6, S-5h7fuwx3, S-5b57ykp4, S-akgat5ss, S-e4zz24dq, S-6bobcclf, S-dabwnzz5, S-hrrqkjbi]
status: partial
---

# cmd.exe: command syntax, quoting, operators, redirection and length limits

## Summary
`cmd.exe` takes one command string (`cmd /c <string>` or a line typed at its prompt) and applies its own
parsing before the program sees anything: it strips quotes by a fixed rule, treats `& | < > ^ ( )` as
operators or escapes, expands `%variables%`, and caps the string at 8191 characters. Microsoft documents the
rules in pieces: the `cmd` page holds the switches, the special characters and the length facts; `echo` and
`set` give the escaping examples; redirection is described on a Windows XP-era TechNet page that Learn still
links from the Windows Commands index. Variable expansion, `%~` modifiers, errorlevel and the built-in
commands are in `windows/cmd-exe-variables-expansion-errorlevel.md`. The documents leave some points
unstated (escape order of `2>&1`, how `%` is handled at parse time, which commands are internal); they are
listed as open items, not guessed.

## Facts
### Invoking cmd and the switches
- The Windows command interpreter starts as `cmd [/c|/k] [/s] [/q] [/d] [/a|/u] [/t:...] [/e:on|off] [/f:on|off] [/v:on|off] [<string>]`: `/c` carries out `<string>` and ends the interpreter, `/k` carries it out and keeps the interpreter running, `/q` turns echo off, `/d` skips AutoRun commands, `/a` and `/u` format output as ANSI or Unicode. [DOC S-yna7gijv]
- Without parameters `cmd` shows the Windows version and copyright text. Microsoft's note on the page points users who want more capable scripting to PowerShell. [DOC S-yna7gijv]
- With `/c` or `/k`, the quotation marks around `<string>` are kept only when all five conditions hold: no `/s`; exactly one pair of quotes; no special characters (`& < > ( ) @ ^ |`) inside them; at least one white-space character inside them; and the quoted text is the name of an executable file. [DOC S-yna7gijv]
- When those conditions are not all met, `cmd` looks at the first character of `<string>`: if it is an opening quote, it is removed together with the closing quote, and text after the closing quote is kept. `/s` forces this stripping of the first and last quote and leaves the rest unchanged. [DOC S-yna7gijv]
- Unless `/d` is given, `cmd` first runs the AutoRun commands from these Windows registry values: `HKLM\Software\Microsoft\Command Processor\AutoRun` (`REG_SZ`) and `HKCU\Software\Microsoft\Command Processor\AutoRun` (`REG_EXPAND_SZ`) when either exists, before anything else. [DOC S-yna7gijv]
- Command extensions of the Windows shell are on by default and are switched with `/e:on|off` per process, or with `REG_DWORD` `EnableExtensions` (`0x1` on, `0x0` off) under `HKLM` or `HKCU` `Software\Microsoft\Command Processor`; a user setting beats a computer setting and a command-line switch beats the registry. [DOC S-yna7gijv]
- The commands whose behaviour extensions change are `assoc`, `call`, `chdir`/`cd`, `color`, `del`/`erase`, `endlocal`, `for`, `ftype`, `goto`, `if`, `mkdir`/`md`, `popd`, `prompt`, `pushd`, `set`, `setlocal`, `shift` and `start` (which also changes how it starts external processes). [DOC S-yna7gijv]
- File and directory name completion in the Windows command shell is off by default; `/f:on` enables it for one process (`Ctrl-D` directories only, `Ctrl-F` files and directories), and the `CompletionChar` and `PathCompletionChar` `REG_DWORD` values set the keys for a computer or user (`0x9` is Tab, `0x20` disables a key). [DOC S-yna7gijv, S-ikuzvclu]
- The Windows Commands index says the Command shell can run only Windows commands, not PowerShell cmdlets, and recommends PowerShell over Windows Commands and Windows Script Host for new automation. [DOC S-ikuzvclu]

### Command operators
- In a Windows command line, `<command1> | <command2>` sends command1's output to command2's input; `<command1> || <command2>` runs command2 only if command1 fails; `<command1> && <command2>` runs command2 only if command1 succeeded; `<command1> & <command2>` is documented as the way to group commands on one line. [DOC S-yna7gijv]
- A command that completes its operation successfully returns exit code zero "or no exit code"; in `a && b && c` each command runs only if the one before succeeded, and a failure stops the rest. [DOC S-yna7gijv]
- In a Windows pipe both commands start at once; the second waits for its input. A filter chain such as `dir /b | find "LOG" > loglist.txt` combines a pipe with a redirection. [DOC S-gp367igh]
- `call` must not be used with pipes or redirection symbols (`|`, `<`, `>`); the `call` page names no workaround. [DOC S-5h7fuwx3]

### Special characters, quoting and escaping
- In Windows batch files and at the prompt, `&`, `|` and parentheses are special: when passed as arguments they must be preceded by the escape character `^` or be inside quotation marks. [DOC S-yna7gijv]
- Quotation marks are required around text that holds any of ``& < > [ ] | { } ^ = ; ! ' + , ` ~`` or white space; a path with spaces is written `"Test 2"`. [DOC S-yna7gijv]
- In `set`, everything after the equal sign is the value. The characters `< > | & ^` need `^` or quotes, and when quotes are used they become part of the value: `set V=New^&Name` stores `New&Name`, `set V="New&Name"` stores the quotes too. [DOC S-yna7gijv, S-jbeh3qg6]
- A caret before an ordinary character is dropped: `set testVar=TEST^1` gives `TEST1`; `set testVar=TEST^^1` gives `TEST^1`. [DOC S-jbeh3qg6]
- Typing `set V=New&Name` with no caret or quotes can fail with "'Name' is not recognized as an internal or external command, operable program or batch file."; the page shows this as the symptom of an unescaped `&`. [DOC S-yna7gijv]
- To print `| & < >` with `echo`, put `^` right before the character; `^^` prints a caret. Inside a block closed with `)` both parentheses of the text need `^`, as in `This is ^(now^) correct`. [DOC S-gydqaolr]
- An exclamation mark in batch output is written `"Hello World^!"` (inside quotes, caret before the mark) or `Hello World^^!` without quotes. [DOC S-gydqaolr]
- `echo` with an empty variable prints `ECHO is off`; `echo:%var%` prints a blank line instead. `echo.` must have no space before the period. [DOC S-gydqaolr]
- `@` before a command suppresses its echo; `@echo off` on the first line suppresses all of a batch file's echo, and `echo off` inside a batch file does not change the setting at the prompt. [DOC S-gydqaolr]
- A `for /f` literal string in double quotes is parsed with command symbols (`\ & | > < ^`) as ordinary characters, which is how a text with operators is fed to the loop. [DOC S-5b57ykp4]
- A line in a batch file that begins with a colon is a label and any commands on that line are ignored; a label name may contain spaces but not `;` or `=`. [DOC S-akgat5ss]

### Redirection
- The Windows redirection operators are `>` (write output to a file or device), `<` (read input from a file), `>>` (append), `>&` and `<&` (duplicate one handle onto another) and `|`. [DOC S-gp367igh]
- The handles `cmd` redirects on Windows are 0 `STDIN`, 1 `STDOUT`, 2 `STDERR`, and 3 to 9 are defined by each application; the default handle is 0 for `<` and 1 for `>`. A number written before the operator picks the handle. [DOC S-gp367igh]
- `dir>c:\file.txt 2>&1` sends standard output and standard error to one file; `ipconfig.exe>>output.log 2>&1` does the same by appending. [DOC S-gp367igh]
- `>` creates the file or replaces its content, and opens it write-only; `<` opens the file read-only, so `<&2` leaves handle 0 unreadable because handle 2 is write-only; a duplicated handle keeps the access of the original. [DOC S-gp367igh]
- The page documenting these operators is a Windows XP-era TechNet article under `previous-versions`; the Windows Commands index links to it as the reference for redirection operators. [DOC S-ikuzvclu, S-gp367igh]

### Command-line length and environment limits
- The longest string the Windows `cmd.exe` handles is 8191 characters. The limit covers the command line, individual environment variables inherited by other processes (such as `PATH`) and every environment variable expansion; it also applies to commands in a batch file run from Command Prompt, counted after parameters are expanded. [DOC S-e4zz24dq]
- On Windows `cmd` ignores an inherited environment variable that is longer than 8191 characters although the Win32 limit is 32,767. Microsoft's workarounds are a parameter file named on the command line, and shorter or fewer entries in `PATH`. [DOC S-e4zz24dq]
- The `cmd` page states the Windows environment limits in bytes: an individual variable at most 8,192 bytes and all variables of a process (names, values and equal signs) at most 65,536 characters. [DOC S-yna7gijv]
- The Microsoft article on the 8191 limit says it applies to Windows Server 2012 R2, Windows Server 2008 R2 SP1 and Windows 7 SP1 and gives no figure for later releases. [DOC S-e4zz24dq]
- The Win32 layer below `cmd` takes a command line of 32,767 characters including the terminating null (`CreateProcessW`). [DOC S-6bobcclf]

### How it fits
- A tool that builds `cmd /c <program path> <args>` keeps its quotes only when exactly one pair is present and nothing special is inside it; a quoted program path plus any quoted argument already means two pairs, so the safe form wraps the whole string in one more pair of quotes and adds `/s`, which strips just that outer pair. [DER S-yna7gijv: the five keep-quotes conditions and the `/s` rule]
- A script that passes a value through `cmd` escapes each `& | < > ^` with `^` (or quotes it) before the interpreter sees the line. Microsoft documents this `cmd` stage; how the started program then splits its own command line is a separate step, which this article does not cover (Python's side is in `python/stdlib-windows-portability.md`). [DER S-yna7gijv, S-jbeh3qg6, S-gydqaolr: the escape rules above; S-dabwnzz5: `subprocess` converts an argument list to one string with the MS C runtime quoting rules, a step apart from `cmd`'s own]
- A launcher that must run a shell built-in (`dir`, `copy`, `echo`) needs `cmd.exe /c`; executables and batch files can be started directly. The same launcher counts 8191 characters for the `cmd` line and 32,767 for a direct `CreateProcess`. [DER S-dabwnzz5, S-hrrqkjbi, S-e4zz24dq, S-6bobcclf: built-ins need the shell; the two limits]
- Output of a build or deploy step is captured with `> file 2>&1` (one file, both streams) or `> out.log 2> err.log` (two files); a `call` step cannot carry redirection, so redirect the called batch file's own commands instead. [DER S-gp367igh, S-5h7fuwx3: the handle rules and the `call` restriction]

### Open
- Whether `2>&1` placed before `>` redirects stderr to the console or to the file is not stated on the redirection page; its examples put `> file` first. [UNK: needs a probe on a host; see `_gaps.md`]
- The Learn pages say what `%var%` and `!var!` do but not at which stage of parsing `cmd` expands `%` or how `^` and quotes interact with it in a batch file versus the prompt. [UNK: see `_gaps.md`]
- The 8191-character article names Windows 7 and Server 2008 R2 / 2012 R2 only; a statement for Windows 10, Windows 11 and current Windows Server was not found. [UNK: see `_gaps.md`]

## Reference
- Related: `windows/cmd-exe-variables-expansion-errorlevel.md` (variables, delayed expansion, batch parameters, errorlevel, built-ins), `python/stdlib-windows-portability.md` (8191 and 32,767 limits seen from Python, `shell=True` and `%COMSPEC%`), `arch/puppet-windows-nodes.md` (`cmd.exe /c` for built-ins, exit-code display), `windows/process-parent-and-command-line.md` (reading a running process's command line).
- Microsoft pages: `cmd`, `echo`, `set`, `call`, `goto`, `for`, "Windows Commands" and "Command prompt (Cmd.exe) command-line string limitation" on Microsoft Learn; "Using command redirection operators" under `previous-versions` (Windows XP, TechNet).

## Examples
- On `PL-LT-00123` a wrapper that must start a tool under a path with spaces writes `cmd /s /c ""C:\Program Files\Tool\tool.exe" --name "Test 2""`: with `/s` the outer pair of quotes is stripped and the rest, `"C:\Program Files\Tool\tool.exe" --name "Test 2"`, is run unchanged.
- `dir C:\Scripts\*.cmd > C:\Temp\list.txt 2>&1 && echo done` lists the scripts into one file and prints `done` only if `dir` returned zero.
