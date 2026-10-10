---
topic: python/stdlib-urllib-errors
priority: P3
applies_to: "Python stdlib urllib.request, urllib.error, socket and http.client exceptions (docs and source at CPython v3.13.2; probes on Python 3.13.2, macOS, 2026-10-10)"
retrieved_utc: 2026-10-10
sources: [S-mktiemgc, S-ia6oszzb, S-dh7elejp, S-kudz6dke]
status: partial
---

# stdlib urllib: how a name-resolution, connection, timeout or HTTP failure surfaces

## Summary
A tool that retries a request needs to tell a failure of the network from an answer of the server.
`urllib.request.urlopen` raises two kinds of exception. Failures while it connects and sends the request
come out as `URLError` whose `reason` is the original `OSError`: a `socket.gaierror` for a name that did not
resolve, a `ConnectionError` subclass for a refused connection. An answer with an error status comes out as
`HTTPError`, a subclass of `URLError` with a `code`; a `304` to a conditional request is one of them.
Failures after the request is sent (a read timeout, a closed connection) are not wrapped: they are raised as
they are. One `except OSError` therefore catches all of them, and the order of the `except` clauses and the
type of `reason` tell them apart.

## Facts
### What the docs and the source say
- `URLError` is raised by the handlers "when they run into a problem", is a subclass of `OSError`, and has a
  `reason` attribute that is a message string or another exception instance. [DOC S-mktiemgc]
- `HTTPError` is a subclass of `URLError` that carries the HTTP status code (`code`), a `reason` that is
  usually a string, the response `headers` and a file-like `fp` for the error body; it can also be used as the
  file-like return value of `urlopen`. [DOC S-mktiemgc]
- `socket.gaierror` is a subclass of `OSError` raised for address-related errors by `getaddrinfo` and
  `getnameinfo`; its value is a pair `(error, string)`, and the numeric `error` matches one of the `EAI_*`
  constants of the `socket` module. [DOC S-ia6oszzb]
- `socket.timeout` is a deprecated alias of `TimeoutError` (since 3.10), a subclass of `OSError`, raised when
  a socket that has a timeout set times out, with the value "timed out". [DOC S-ia6oszzb]
- In `AbstractHTTPHandler.do_open`, the call that connects and sends the request (`h.request(...)`) is in a
  `try` whose `except OSError as err` raises `URLError(err)`; the next statement, `h.getresponse()`, is
  outside that `except`, so an `OSError` raised while the response is read is not wrapped. [CODE S-dh7elejp: Lib/urllib/request.py#AbstractHTTPHandler.do_open]
- `http.client.HTTPException` derives from `Exception`, not from `OSError`; `IncompleteRead` and
  `BadStatusLine` are subclasses of it, and `RemoteDisconnected` is a subclass of both `ConnectionResetError`
  and `BadStatusLine`. [DOC S-kudz6dke]

### What a run showed
- On Python 3.13.2, macOS (Darwin 25.5.0), 2026-10-10, `urlopen("http://nonexistent.invalid/")` raised
  `URLError` whose `reason` was `gaierror(8, 'nodename nor servname provided, or not known')`: `reason` is a
  `socket.gaierror`, not a `ConnectionError`, and `reason.errno == socket.EAI_NONAME` (8 on this host;
  `EAI_AGAIN` was 2). Compare with the `socket` constants, never literal numbers: the docs say only that the
  value matches an `EAI_*` constant. [DER S-ia6oszzb, S-mktiemgc: the `EAI_*` match; the value observed in one run]
- On the same run (Python 3.13.2, macOS), a connection to a closed local port raised `URLError` whose `reason` was
  `ConnectionRefusedError(61, 'Connection refused')`, an instance of `ConnectionError` and not of
  `socket.gaierror`. [DER S-mktiemgc: the `reason` attribute; the value observed in one run]
- On Python 3.13.2, macOS, a local server's `404` and `304` both raised `HTTPError` (an instance of `URLError`, with `code` 404 or 304
  and `reason` `'Not Found'` or `'Not Modified'`): with urllib, a conditional `GET` that finds the resource
  unchanged surfaces as an exception, not as a response. [DER S-mktiemgc: `HTTPError` is a `URLError` with a `code`; the codes observed in one run]
- With `timeout=0.5` against a local server that accepted the connection and then waited, `urlopen` raised a
  bare `TimeoutError('timed out')`, not a `URLError`; against one that closed the connection without a
  response it raised `http.client.RemoteDisconnected`, also not a `URLError`. Both agree with the `do_open`
  structure above. [DER S-dh7elejp, S-kudz6dke, S-ia6oszzb: where `do_open` wraps; the exceptions observed in one run]
- So a retry can tell a name-resolution failure (`URLError` with `reason` a `socket.gaierror`, its `errno`
  one of the `EAI_*` constants), a connection failure (`URLError` with `reason` a `ConnectionError`), a
  timeout (`TimeoutError`, bare or as `reason`) and an HTTP answer (`HTTPError`, by its `code`) apart by type; a bare `except URLError` would take an `HTTPError` for a network failure, because
  `HTTPError` is its subclass, and would miss the unwrapped failures. [DER S-mktiemgc, S-ia6oszzb, S-dh7elejp, S-kudz6dke: the classes and where they are raised]
- Open: the `socket.EAI_*` values and the exact `reason` of a refused or unreachable connection on Windows and
  Linux were not run, and whether a proxy changes where the failure is raised was not read. [UNK: see `_gaps.md`]

## Reference
- `python/stdlib-windows-portability.md`: other stdlib behaviour that differs by platform.
- `agents/doc-change-detection.md`: GitHub and Learn conditional requests, whose `304` urllib raises as `HTTPError`.

## Examples
- SNIPPET: sort one `urlopen` call's failure into name resolution, connection, timeout, HTTP status or other network error; context: Python 3.13, standard library only, no proxy configured; checked: run (a name that does not resolve gave `dns`, a closed local port `connect`) [DER S-mktiemgc, S-ia6oszzb, S-dh7elejp, S-kudz6dke: the exception classes and where they are raised]
```python
import http.client
import socket
import urllib.error
import urllib.request


def classify(url: str, timeout: float = 10.0) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            resp.read()
        return "ok"
    except urllib.error.HTTPError as err:  # first: it is also a URLError
        return f"http:{err.code}"
    except urllib.error.URLError as err:  # raised while connecting
        reason = err.reason
        if isinstance(reason, socket.gaierror):
            return "dns"
        if isinstance(reason, TimeoutError):
            return "timeout"
        if isinstance(reason, ConnectionError):
            return "connect"
        return "network"
    except TimeoutError:  # raised while the response is read
        return "timeout"
    except (OSError, http.client.HTTPException):  # reset, dropped, incomplete read
        return "network"
```
