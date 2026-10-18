---
topic: python/stdlib-argparse-json
priority: P3
applies_to: [python, argparse, json]
retrieved_utc: 2026-10-18
sources: [S-w47ijsvq, S-zzvrhdyd, S-glgntdsx, S-reb2jhbs, S-6gpxsapp, S-uj2rumru, S-36yy3wcx, S-lyf4dv2j, S-lcvgoknn, S-rs27i36t, S-hqcmecwc, S-5x4j2vvx, S-j5cbrmig, S-kli6pbvd, S-cddhnbl6]
status: complete
---

# stdlib argparse subcommands and json output (what this kb's command-line tools rely on)

## Summary
`_tools/` scripts are stdlib-only Python 3.11+ command-line programs that grow subcommands
(`set`, `add`, `show`) and read and write JSON. `argparse` gives one parser per subcommand, a way to
call the chosen handler, mutually exclusive option groups, and a fixed exit status 2 for a usage
error; `json.dumps` keeps dict order unless told to sort, escapes non-ASCII unless told not to, and
picks its separators from `indent`. Pages read at CPython 3.14.7.

## Facts
- `ArgumentParser.add_subparsers(*, title, description, prog, dest, required, help, metavar)` adds
  subcommands; `required` defaults to `False` (parameter added in 3.7), so without `required=True` a
  command line with no subcommand parses without error and the attribute is `None`. [DOC S-w47ijsvq]
- `dest='subparser_name'` on `add_subparsers` stores the chosen subcommand's name under that
  attribute (default: no value stored); `parser.parse_args(['2', 'frobble'])` then gives
  `Namespace(subparser_name='2', y='frobble')`. [DOC S-w47ijsvq]
- The documented way to run the chosen handler: `parser_foo.set_defaults(func=foo)` on each
  subparser, then call `args.func(args)` after `parse_args`; the docs call this "typically the
  easiest way to handle the different actions for each of your subparsers". [DOC S-w47ijsvq]
- `add_mutually_exclusive_group(required=False)` makes argparse check that at most one of its
  arguments is on the command line; giving two prints `PROG: error: argument --bar: not allowed with
  argument --foo`. With `required=True` at least one is needed, else `PROG: error: one of the
  arguments --foo --bar is required`. [DOC S-w47ijsvq]
- A mutually exclusive group takes no `title` or `description`, but can be added to an argument group
  that has them; calling `add_argument_group` or `add_mutually_exclusive_group` on a mutually exclusive
  group was deprecated in 3.11 and raises an exception from 3.14, the docs saying the nesting was never supported. [DOC S-w47ijsvq]
- `ArgumentParser.error(message)` prints the usage and the message to `sys.stderr` and terminates with
  status 2; this covers a missing required argument or subcommand and a mutually exclusive violation.
  `ArgumentParser.exit(status=0, message=None)` prints an optional message to `sys.stderr` and
  exits with `status`; a subclass may override it. [DOC S-w47ijsvq]
- An invalid argument list passed to `parse_args` prints a message to `sys.stderr` and exits with
  status 2; `exit_on_error=False` (added in 3.9) lets the caller catch `argparse.ArgumentError`
  instead. [DOC S-w47ijsvq]
- `default` is ignored for required arguments (positionals whose `nargs` is not `?` or `*`, and
  options with `required=True`). [DOC S-w47ijsvq]
- `json.dumps` and `json.dump` default to `sort_keys=False`, `ensure_ascii=True`, `indent=None` and
  `separators=None`; the module's encoder and decoder "preserve input and output order by default",
  so a dict serialises in its insertion order and order is lost only where the container is
  unordered. [DOC S-zzvrhdyd]
- `sort_keys=True` outputs dictionaries sorted by key; the docs give the use "regression tests to
  ensure that JSON serializations can be compared on a day-to-day basis". [DOC S-zzvrhdyd]
- `ensure_ascii=True` escapes all non-ASCII and non-printable characters; `False` outputs every
  character as is except quotation mark, reverse solidus and U+0000 to U+001F. [DOC S-zzvrhdyd]
- `indent` given as a positive integer indents that many spaces per level, a string (such as `"\t"`)
  is used per level, `0`, a negative number or `""` inserts only newlines, and `None` gives the most
  compact output. Strings for `indent` were added in 3.2. [DOC S-zzvrhdyd]
- `separators=None` means `(', ', ': ')` when `indent` is `None` and `(',', ': ')` otherwise (the
  no-trailing-space item separator since 3.4), so an indented dump has no trailing whitespace on
  lines; `separators=(',', ':')` gives the most compact form. [DOC S-zzvrhdyd]
- `json.dumps` does not write a trailing newline and `json.dump` writes to a text file object; the
  docs' examples do not add one, so a tool that writes a file and wants a final newline adds it
  itself. [DER S-zzvrhdyd: neither signature documents a newline parameter]
- A POSIX shell gives a command that is not found the exit status 127, and one that is found but is not
  an executable utility 126; when the search for a utility fails the shell "shall write an error
  message", whose wording the standard does not fix. [DOC S-glgntdsx]
- In a POSIX AND list (`a && b`) the second command runs only when the first exits 0, in an OR list
  (`a || b`) only when it exits non-zero, the list's status is that of the last command executed, and in
  a pipeline (`a | b`) each command's standard output feeds the next one's standard input. [DOC S-glgntdsx]
- Bash: "If a command is not found, the child process created to execute it returns a status of 127";
  a command found but not executable returns 126, and one ended by fatal signal N returns 128+N.
  [DOC S-reb2jhbs]
- So a `sh -c` or `bash -c` string that chains commands with `&&`, `||`, `;` or `|` can exit 127 for any
  of its own command words, not only the first, and the not-found message names the missing word in a
  shell-specific wording; a check that reads exit 127 as "cannot start" must read every command word of
  the string as the command's own. [DER S-glgntdsx, S-reb2jhbs: the 127 rule applies per command, and the
  list operators run the later commands]
- POSIX reserved words are `!`, `{`, `}`, `case`, `do`, `done`, `elif`, `else`, `esac`, `fi`, `for`, `if`, `in`, `then`, `until` and `while`, recognized only unquoted and as the first word of a command or the first word after a reserved word other than `case`, `for` or `in`; so after `if`, `then`, `do` or `!` the next word is a command word. [DOC S-glgntdsx]
- The reserved word `!` before a pipeline makes its exit status the logical NOT of the pipeline's status. [DOC S-glgntdsx]
- `env [-i] [name=value]... [utility [argument...]]` runs the utility named after its assignments with the modified environment, so in `env A=1 python3 x.py` the command word is `python3`, not `env`. [DOC S-6gpxsapp]
- So a reader of a shell string's command words takes the word after `if`, `then`, `elif`, `else`, `do`, `!`, `&&`, `||`, `;`, `|` and a newline, skips leading `name=value` assignments and an `env` prefix with its options and assignments, and reads a nested `sh -c` or `bash -c` string the same way. [DER S-glgntdsx, S-6gpxsapp]
- A `socketserver` (and so `http.server`) server's `handle_request()` processes one request, and when none arrives within the server's `timeout` seconds it calls `handle_timeout()` and returns; `shutdown()` stops a `serve_forever()` loop and must be called from another thread, or it deadlocks. [DOC S-uj2rumru]
- So a local receiver that must exit after an idle period loops on `handle_request()` with `timeout` set and checks the time since its last request after each return, and a test of that exit plants an idle bound of a second or less. [DER S-uj2rumru]
- `http.server.ThreadingHTTPServer(server_address, RequestHandlerClass)` is `HTTPServer` that handles each request in its own thread through `ThreadingMixIn`; the docs give browsers pre-opening sockets, on which `HTTPServer` "would wait indefinitely", as the reason. The module's page warns that `http.server` "is not recommended for production" and implements only basic security checks. [DOC S-rs27i36t]
- A `ThreadingMixIn` server's `daemon_threads` defaults to `False`, so the interpreter does not exit until every request thread has finished; setting it to `True` makes the threads daemonic and the server stops waiting for them. [DOC S-uj2rumru]
- The `socketserver` threaded-server example binds `("localhost", 0)` under the comment "Port 0 means to select an arbitrary unused port" and reads the chosen address back from `server.server_address` (an `(address, port)` tuple); `http.server`'s `server_port` is "obtained from" it. [DOC S-uj2rumru, S-rs27i36t]
- So a long-lived request on a `ThreadingHTTPServer` (a wait that holds its connection open) occupies one thread for as long as it lasts, and a server that must stop at once sets `daemon_threads = True` and calls `shutdown()` from a thread other than the one in `serve_forever()`. The pages read give no long-poll recipe and no worker limit for `ThreadingHTTPServer`; the module's own limits are for the forking mixin only. [DER S-rs27i36t, S-uj2rumru: thread-per-request class, the `daemon_threads` text and the shutdown rule read together]
- In `BaseHTTPRequestHandler` the docs describe `rfile` as an input stream "ready to read from the start of the optional input data": the handler parses the request line and the headers (`http.client.parse_headers` on `rfile`) and then calls the `do_<METHOD>` method, so the body is still in `rfile` when `do_POST` starts. [DOC S-rs27i36t]
- `parse_request` reads the headers up to the blank line, answers `431` on an over-long header line or too many headers, and then looks at `Connection` and `Expect`; `handle_one_request` calls `do_<METHOD>` straight after it. In `BaseHTTPRequestHandler` the only reads of `rfile` are the request line (`readline(65537)`) and the header parse; the first code in the file that reads `Content-Length` and the body is `CGIHTTPRequestHandler`'s CGI path, which a `do_POST` of your own subclass does not use. [CODE S-hqcmecwc: Lib/http/server.py#BaseHTTPRequestHandler.parse_request, handle_one_request; CGIHTTPRequestHandler.run_cgi]
- For `Expect: 100-continue` on an HTTP/1.1 request to an HTTP/1.1 server, `handle_expect_100` sends `100 Continue` by default before the body is awaited; its docstring says an override may "reject unauthorized requests" by sending an error response and returning `False`, which ends the request before any body is read. [CODE S-hqcmecwc: Lib/http/server.py#BaseHTTPRequestHandler.handle_expect_100]
- `handle` loops `handle_one_request` while `close_connection` is false; `parse_request` starts it `True` and turns it `False` only for a request of version 1.1 or higher to a handler whose `protocol_version` is `HTTP/1.1` (a `Connection: keep-alive` header does the same on such a handler), and `Connection: close` in the request or `send_header("Connection", "close")` sets it `True` again. `StreamRequestHandler.finish` flushes and closes `wfile` and `rfile`; it does not drain `rfile`. [CODE S-hqcmecwc: Lib/http/server.py#parse_request, handle, send_header; S-5x4j2vvx: Lib/socketserver.py#StreamRequestHandler.finish]
- One probe (Python 3.13.2, macOS, 2026-10-18, `ThreadingHTTPServer` with `protocol_version = "HTTP/1.1"`): a `do_POST` that answered `413` with `Content-Length: 0` without touching `rfile` received a `POST` whose body was the text of a second request (`GET /smuggled`); the server then ran `do_GET` for `/smuggled` on the same connection and sent a second response. The default `protocol_version` is `HTTP/1.0`, so a handler that does not set it closes the connection after each response and has no such second request. [DER S-hqcmecwc, S-5x4j2vvx: probe read against the code above]
- So a handler can refuse from the headers alone (a `Content-Length` over its limit, a missing token) and send its `4xx` without reading `rfile`; on a keep-alive connection it must also close it (`Connection: close` header, or `self.close_connection = True`) or read and discard the body, since the unread bytes would otherwise be parsed as the next request line. Whether a client that is still sending sees the early response or a reset depends on the TCP stack and is not stated in the pages read. [DER S-hqcmecwc, S-rs27i36t: body unread by the framework; keep-alive loop; the probe above]
- `socket.settimeout(value)` takes "a nonnegative real number expressing seconds, or `None`": a non-zero value makes later operations raise a `timeout` exception when it elapses, `0` puts the socket in non-blocking mode and `None` in blocking mode; `setblocking(True)` is `settimeout(None)` and `setblocking(False)` is `settimeout(0.0)`. `socket.timeout` is a deprecated alias of `TimeoutError` since 3.10. The page states no upper bound and no error for a value out of range. [DOC S-j5cbrmig]
- In the C code `settimeout` and `setdefaulttimeout` share `socket_parse_timeout`: `None` is accepted; any other value is converted to integer nanoseconds (`_PyTime_FromSecondsObject`, an `OverflowError` when it does not fit); a result below zero raises `ValueError("Timeout value out of range")`; on Windows a value that does not fit a `timeval`, and on a build without `poll` one over `INT_MAX` milliseconds, raises `OverflowError("timeout doesn't fit into C timeval")`. [CODE S-kli6pbvd: Modules/socketmodule.c#socket_parse_timeout, sock_settimeout]
- The conversion in `pytime.c` multiplies a `float` by 1e9 and raises `OverflowError("timestamp out of range for C PyTime_t")` when the result is outside the signed 64-bit range, so the largest accepted number of seconds is about 9.22e9; an `int` is read with `PyLong_AsLongLong` and the same `OverflowError` follows when it or its product by 1e9 does not fit; a `float` NaN raises `ValueError("Invalid value NaN (not a number)")`. [CODE S-cddhnbl6: Python/pytime.c#pytime_from_object, pytime_from_double]
- One probe (Python 3.13.2, macOS, 2026-10-18): `settimeout` accepted `None`, `0`, `-0.0`, `True` (as 1.0) and `9223372036.0`; it raised `ValueError: Timeout value out of range` for `-1`, `ValueError: Invalid value NaN (not a number)` for NaN, `TypeError` for the string `"1"`, and `OverflowError` for `1e10`, `9223372036.9`, `1e300`, `inf` and `2**63` (the message was `timestamp out of range for platform time_t` for a float and `timestamp too large to convert to C PyTime_t` for the `int`, wording that differs from the 3.14.7 source above). A value that large is a bug in the caller, not a timeout, so a tool that takes `--timeout` from its user checks the range itself or catches `OverflowError` and `ValueError` beside `TypeError`. [DER S-j5cbrmig, S-kli6pbvd, S-cddhnbl6: probe read against the source; the wording differs between versions]
- `textwrap.shorten(text, width, *, fix_sentence_endings=False, break_long_words=True, break_on_hyphens=True, placeholder=' [...]')` (added in 3.4) first collapses whitespace, replacing all of it with single spaces; if the result fits in `width` it is returned, else enough words are dropped from the end so the remaining words plus the placeholder fit. The docs' examples: `shorten("Hello  world!", width=12)` gives `'Hello world!'`, `width=11` gives `'Hello [...]'`, and `shorten("Hello world", width=10, placeholder="...")` gives `'Hello...'`. [DOC S-36yy3wcx]
- Because `shorten` collapses whitespace before it calls `TextWrapper`, the docs say changing `tabsize`, `expand_tabs`, `drop_whitespace` and `replace_whitespace` has no effect on it; its other keyword arguments are the `TextWrapper` attributes of the same names. The page does not say what `shorten` does when the placeholder alone is wider than `width`. [DOC S-36yy3wcx]
- `shorten` cuts at word boundaries: it drops whole words from the end, so a result is never a window cut inside a word, and text with no whitespace to drop at is left to `break_long_words`. [DER S-36yy3wcx: the dropped-words rule and the `break_long_words` text]
- `TextWrapper.width` (default 70) is "the maximum length of wrapped lines": the docs guarantee no output line longer than `width` characters when no single word in the input is longer than `width`, and `wrap(text)` returns lines each "at most width characters long". The page counts in characters, not bytes. [DOC S-36yy3wcx]
- `TextWrapper.max_lines` (default `None`, added in 3.4): if not `None`, the output has at most `max_lines` lines, with `placeholder` appearing at the end of the output; `placeholder` (default `' [...]'`, added in 3.4) is the string that appears at the end of the output text if it has been truncated. [DOC S-36yy3wcx]
- `TextWrapper.break_long_words` (default `True`): if true, words longer than `width` are broken so no line is longer than `width`; if false they are not broken, they go on a line by themselves, and some lines may be longer than `width`. [DOC S-36yy3wcx]
- So `TextWrapper(width=W, max_lines=1, placeholder=P).fill(s)` is the documented way to cut one long sentence to one line that ends in `P`, and a line over `W` is possible only through a word longer than `W` with `break_long_words=False`. [DER S-36yy3wcx: `max_lines`, `placeholder` and `break_long_words` texts]
- `str.encode(encoding='utf-8', errors='strict')` returns the string encoded to bytes; `encoding` defaults to `'utf-8'`, and with `'strict'` (the default) an encoding error raises a `UnicodeError`; `'Python'.encode()` gives `b'Python'` of type `bytes`. [DOC S-lyf4dv2j]
- UTF-8 represents a code point below 128 as the one byte of that value and any code point of 128 or more as a sequence of two, three or four bytes, each between 128 and 255; a string of ASCII text is also valid UTF-8. [DOC S-lcvgoknn]
- So the UTF-8 size of a `str` is `len(s.encode())`, which differs from `len(s)` for every character at or above U+0080; the tools measure printed bytes this way, not by character count. [DER S-lyf4dv2j, S-lcvgoknn: default encoding and the byte-count rule]
- U+2026 HORIZONTAL ELLIPSIS is above U+07FF and so takes three bytes in UTF-8 (`E2 80 A6`), where three ASCII dots take three bytes too; the Python pages read state only that a UTF-8 code point takes two to four bytes, so the three is derived from the UTF-8 encoding table, not stated there. [DER S-lcvgoknn: the two-to-four-byte rule; the length ranges are the standard UTF-8 table]

## Reference
- SNIPPET: subcommands with a handler, one exclusive group and stable JSON output; context: Python
  3.11+ stdlib; checked: syntax [DOC S-w47ijsvq: `add_subparsers(required=True)`, `set_defaults(func=...)`,
  `add_mutually_exclusive_group`; DOC S-zzvrhdyd: `sort_keys`, `indent`, `ensure_ascii`]
```python
import argparse
import json


def cmd_set(args):
    print(json.dumps({"id": args.id, "field": args.field}, sort_keys=True, indent=2, ensure_ascii=False))


parser = argparse.ArgumentParser(prog="tool")
sub = parser.add_subparsers(dest="cmd", required=True)
p_set = sub.add_parser("set")
p_set.add_argument("id")
group = p_set.add_mutually_exclusive_group(required=True)
group.add_argument("--field")
group.add_argument("--clear", action="store_true")
p_set.set_defaults(func=cmd_set)

args = parser.parse_args()  # usage errors exit with status 2
args.func(args)
```

## Examples
- A CLI whose new subcommand must fail with a message, not a traceback, on bad input calls
  `parser.error("...")` (status 2, usage on stderr) for argument-combination errors found after
  parsing, and `sys.exit(1)` or a custom status for runtime failures, keeping 2 for usage errors.
  [DER S-w47ijsvq: `error()` exits with 2; the split is our convention]
- A tool that rewrites a JSON file and must produce a small diff loads it (insertion order kept),
  changes one key and dumps with the same `indent` and `ensure_ascii` it was written with; adding
  `sort_keys=True` reorders keys of the whole file once. [DER S-zzvrhdyd]
