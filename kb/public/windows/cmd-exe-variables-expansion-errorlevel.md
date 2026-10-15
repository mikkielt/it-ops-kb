---
topic: windows/cmd-exe-variables-expansion-errorlevel
priority: P3
applies_to: "cmd.exe and batch files: environment variables, %var% and delayed (!var!) expansion, batch parameters and %~ modifiers, for variables, errorlevel and exit codes, call/goto, and which commands are built in, as documented on Microsoft Learn (Windows Commands reference; read 2026-10-15)"
retrieved_utc: 2026-10-15
sources: [S-yna7gijv, S-33ugnqz2, S-7varc2ty, S-jbeh3qg6, S-z3njred5, S-5h7fuwx3, S-akgat5ss, S-5b57ykp4, S-ikuzvclu, S-hrrqkjbi, S-dabwnzz5]
status: partial
---

# cmd.exe and batch files: variables, expansion, errorlevel and built-in commands

## Summary
In a batch file `%name%` is replaced by the variable's value, and `%1` to `%9` and `%*` by the script's
arguments; `!name!` is a run-time substitution that exists only when delayed expansion is on (`cmd /v:on` or `setlocal enabledelayedexpansion`). A program's exit code reaches a batch file
as ERRORLEVEL: `if errorlevel N` is true for N and above, `%errorlevel%` holds the number, and `exit /b N` ends a
script with it. `setlocal` and `endlocal` bound variable changes to the batch file. The Learn pages say which
commands extensions change, but do not mark which commands are internal to `cmd.exe`. Quoting, operators,
redirection and the 8191-character limit are in `windows/cmd-exe-syntax-quoting-redirection.md`.

## Facts
### Environment variables and %var% expansion
- In `cmd`, `set` with no parameters lists the environment; `set <name>` shows the variables whose names begin with it (extensions on); `set <name>=<value>` sets one; `set <name>=` with nothing after the equal sign removes it. [DOC S-jbeh3qg6]
- Environment variable names are not case-sensitive in `cmd`, and `set` shows a name exactly as it was typed. [DOC S-yna7gijv]
- `%name%` is replaced by the variable's value; the substitution is not recursive, `cmd` looks a variable up once. [DOC S-yna7gijv]
- Each `cmd` instance inherits its parent's environment, and changes made in the child do not reach the parent. [DOC S-yna7gijv]
- `set /p <name>=<prompt>` reads a line of input into the variable; `set /a <name>=<expression>` evaluates a numeric expression. [DOC S-jbeh3qg6]
- `set /a` operators, highest precedence first, as the page lists them: `( )`, unary `! ~ -`, `* / %`, `+ -`, `<< >>`, `&`, `^`, the assignment operators (`= *= /= %= += -= &= ^= <<= >>=`) and the separator `,`. Numbers are decimal unless prefixed `0x` (hex) or `0` (octal); a name that is not defined counts as zero; an expression with `&&`, `||` or `%` is put in quotes. [DOC S-jbeh3qg6]
- Run from the command line outside a script, `set /a` displays the final value of the expression. [DOC S-jbeh3qg6]
- Types of variable in descending order of precedence: built-in system variables, system variables in `HKLM`, local variables in `HKCU`, variables in `Autoexec.bat`, variables from a logon script, then variables set interactively in a script or batch file. [DOC S-yna7gijv]

### Delayed expansion and setlocal
- Delayed environment variable expansion in `cmd` is off by default. `cmd /v:on` turns it on for the instance, and `!name!` then substitutes the value at run time. [DOC S-yna7gijv, S-jbeh3qg6]
- `setlocal [enableextensions|disableextensions] [enabledelayedexpansion|disabledelayedexpansion]` starts a local scope in a batch file; the chosen settings last until the matching `endlocal` or the end of the file, whatever they were before. [DOC S-33ugnqz2]
- Environment changes made after `setlocal` are local to the batch file; `cmd` restores the previous settings at `endlocal` or at the end of the file. `setlocal` can be nested, and outside a script it has no effect. [DOC S-33ugnqz2]
- `setlocal` sets ERRORLEVEL to 0 when an extensions or delayed-expansion argument was passed and to 1 otherwise; the page's test for extension support is `verify other 2>nul`, `setlocal enableextensions`, `if errorlevel 1 echo Unable to enable extensions`. [DOC S-33ugnqz2]
- `cmd` does not set ERRORLEVEL while command extensions are disabled, which is why that test first runs `verify` with an invalid argument to start ERRORLEVEL at a non-zero value. [DOC S-33ugnqz2]
- The pages do not show a worked loop that needs `!var!` to see a value changed inside a `( ... )` block or `for` body. [UNK: see `_gaps.md`]

### Batch parameters and for variables
- The batch argument references are `%0`, `%1`, ... and `%*` is all the arguments; batch parameters passed on with `call` can hold options, file names, other parameters and variables such as `%baud%`. [DOC S-5h7fuwx3]
- `%~1` removes surrounding quotation marks; further letters after the tilde select a part of `%1` taken as a file name: `f` fully qualified path, `d` drive, `p` path, `n` name, `x` extension, `s` short names, `a` attributes, `t` date and time, `z` size, and `$PATH:` searches `PATH` (empty string when the variable or file is missing). [DOC S-5h7fuwx3]
- Modifiers combine (`%~dp1`, `%~nx1`, `%~dp$PATH:1`, `%~ftza1`); the `%~` syntax ends at a valid argument number, and the modifiers cannot be used with `%*`. [DOC S-5h7fuwx3]
- The `for` variable takes the same modifiers (`%~dpI`, `%~nxI`, ...); uppercase variable names avoid confusion with the modifier letters, which are not case-sensitive. [DOC S-5b57ykp4]
- A `for` variable is written `%f` at the prompt and `%%f` in a batch file; variable names are case sensitive and global, at most 52 can be active at once, and a digit is not usable as a name because it would clash with `%0` to `%9`. [DOC S-5b57ykp4]
- `for /f` splits each line of a file, a literal string or a command's output into tokens (`eol`, `skip`, `delims`, `tokens`, `usebackq`); the default is the first token, delimited by space and tab, and blank lines are skipped. A command in backquotes is run by a child `cmd.exe` and its output parsed as a file. [DOC S-5b57ykp4]
- `for /l %N in (start,step,end)` counts, for example `(1,2,9)` gives 1 3 5 7 9; `for /d` walks directories and `for /r` walks a tree. [DOC S-5b57ykp4]

### Control flow: call, goto, if
- `call <file>` runs another batch program and returns to the caller; the file must have a `.bat` or `.cmd` extension. `call :<label> <args>` runs a label as a subroutine in a new batch context: the first end of the file returns to the statement after `call`, the second end exits the script. [DOC S-5h7fuwx3]
- `goto :EOF` (extensions on) ends the current batch file without a label; `goto <label>` for a missing label stops the batch program with "Label not found". [DOC S-akgat5ss]
- `if` forms: `if [not] errorlevel <n>`, `if [not] <s1>==<s2>`, `if [not] exist <file>`, and with extensions `if [/i] <s1> EQU|NEQ|LSS|LEQ|GTR|GEQ <s2>`, `if defined <var>` and `if cmdextversion <n>`; `/i` ignores case, and a comparison of two all-digit strings is numeric. [DOC S-7varc2ty]
- `else` must be on the same line as the command after `if`; the parenthesised form `if exist F (del F) else (echo missing)` is the page's one-line example. [DOC S-7varc2ty]

### Errorlevel and exit codes
- `if errorlevel <n>` is true when the previous program's exit code is equal to or greater than `n`; `if not errorlevel 1` is therefore the success test, and `if %errorlevel% LEQ 1` compares the number. [DOC S-7varc2ty]
- Under `if defined`, the page adds `%errorlevel%`, `%cmdcmdline%` and `%cmdextversion%`: each expands to the current value only if no environment variable of that name already exists, and an existing variable wins. [DOC S-7varc2ty]
- `exit /b [<code>]` leaves the current batch script and sets ERRORLEVEL to the code; run outside a batch script it exits `cmd.exe`. `exit [<code>]` without `/b` ends the command interpreter and its process exit code is the number. [DOC S-z3njred5]
- Puppet's Windows `exec` page says Puppet, which uses `GetExitCodeProcess`, reports a large positive exit code where `cmd.exe` shows a negative one (the negative number subtracted from 4294967296), and passes on Microsoft's advice to avoid negative or very large exit codes. [DOC S-hrrqkjbi]
- The `cmd` page does not say how the exit code of a `cmd /c "<program>"` process relates to the program's: whether `cmd /c` returns the last command's code is not stated. [UNK: see `_gaps.md`]

### Built-in commands
- The Windows Commands index says all supported Windows and Windows Server versions have a set of Win32 console commands built in; its A-Z reference lists commands, and does not mark which of them are internal to `cmd.exe` and which are separate `.exe` files. [DOC S-ikuzvclu]
- The `cmd` page lists the commands that command extensions change (the list is in `windows/cmd-exe-syntax-quoting-redirection.md`); it does not call that list "the built-in commands". [DOC S-yna7gijv]
- Some of these commands act differently at the prompt than in a batch file: `call` and `setlocal` have no effect outside a script or batch file, `exit /b` outside a batch script exits `cmd.exe`, and `for` takes `%f` at the prompt and `%%f` in a batch file. [DOC S-5h7fuwx3, S-33ugnqz2, S-z3njred5, S-5b57ykp4]
- Puppet's page says Puppet has no shell provider for `exec` on Windows, so a shell built-in such as `echo` needs a full `cmd.exe /c ...` command. [DOC S-hrrqkjbi]
- The `subprocess` documentation says that on Windows `shell=True` is needed only when the command is built into the shell, such as `dir` or `copy`, and not to run a batch file or a console executable. [DOC S-dabwnzz5]

### How it fits
- A batch file that hands a result to a caller ends each branch with `exit /b <code>` and uses small non-negative codes: `if errorlevel 1` is a "1 or greater" test, so a code that `cmd.exe` shows as negative is below 1 and is missed by it, and other tools show the same code as a large positive number. The failure test that does not depend on sign is `if not %errorlevel%==0`. [DER S-z3njred5, S-7varc2ty, S-hrrqkjbi: `exit /b` sets ERRORLEVEL; `if errorlevel` is a greater-or-equal test; `cmd.exe` shows negative codes that other APIs report as positive]
- A batch file that takes a path argument uses `%~1` to drop the caller's quotes and puts its own quotes back (`"%~1"`), so a path with spaces stays one argument and the special characters are quoted. [DER S-5h7fuwx3, S-yna7gijv: `%~1` removes quotes; spaces and special characters need double quotes]
- Variables that are meant to be read after `endlocal`, or by a caller, are not safe in a `setlocal` scope: changes there are restored at `endlocal`. [DER S-33ugnqz2: the scope rule above]

### Open
- When `cmd` expands `%var%` for a block versus a single line, and the exact interaction with `!var!`, is not in the Learn pages read (help text `set /?` is not on Learn). [UNK: see `_gaps.md`]
- The set of commands internal to `cmd.exe` is not given by the Learn reference. [UNK: see `_gaps.md`]

## Reference
- Related: `windows/cmd-exe-syntax-quoting-redirection.md` (invocation, quoting, operators, redirection, length limits), `python/stdlib-windows-portability.md` (8191 limit, `%COMSPEC%` with `shell=True`), `arch/puppet-windows-nodes.md` (`cmd.exe /c`, negative exit codes), `mecm/osd-task-sequences.md` (`%varname%` task sequence variables inside `cmd.exe /c` steps).
- Microsoft pages: `cmd`, `set`, `setlocal`, `if`, `for`, `call`, `goto`, `exit`, `echo` and "Windows Commands" on Microsoft Learn.

## Examples
- `deploy.cmd` on `PL-SRV-0042`: `@echo off`, `setlocal enableextensions`, `call :step "%~1"`, `if errorlevel 1 exit /b 1`, `exit /b 0`, with `:step` doing the work and ending in `goto :EOF`.
- `for /f "usebackq tokens=1,2 delims=," %%a in ("%~1") do echo %%a %%b` in a batch file reads the comma-delimited file named by its first argument (`usebackq` allows the quoted file name) and prints its first two fields.
