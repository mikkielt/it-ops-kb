---
topic: python/stdlib-archive-read-errors
priority: P3
applies_to: "Python stdlib zipfile and tarfile reading an archive that is corrupt, truncated, encrypted or compressed in an unsupported way (docs at CPython v3.13.2; probes on Python 3.13.2, macOS, 2026-10-22)"
retrieved_utc: 2026-10-22
sources: [S-vpqnb7i6, S-bzzofa6p]
status: partial
---

# stdlib zipfile and tarfile: which exception a bad archive raises

## Summary
A tool that reads archives it did not make (a downloaded zip, a `.tar.gz` of a release) needs one `except` that
covers every way the read can fail, or a failure leaves as a traceback and an exit status that other code reads as
"nothing found". The docs name `BadZipFile` for a bad zip and `ReadError` for a tar archive that cannot be handled, but
the probes below show five exception types that do not share a base: `zipfile.BadZipFile`, `RuntimeError` (with its subclass
`NotImplementedError`), `zlib.error`, `EOFError` and `tarfile.TarError`. A `tar.gz` cut short raises `EOFError`, which the
`tarfile` page does not mention.

## Facts
### What the docs say
- `zipfile.BadZipFile` is "the error raised for bad ZIP files"; `BadZipfile` is its deprecated alias. [DOC S-vpqnb7i6]
- The zipfile page lists the reasons an extraction can fail "from the file itself": an incorrect password, CRC checksum, ZIP format, or an unsupported compression method or decryption. [DOC S-vpqnb7i6]
- `ZipFile.read` of a member whose compression method is none of `ZIP_STORED`, `ZIP_DEFLATED`, `ZIP_BZIP2` and `ZIP_LZMA` raises `NotImplementedError`; the page adds that an error is also raised when the matching compression module (`zlib`, `bz2`, `lzma`) is not available. [DOC S-vpqnb7i6]
- `tarfile.TarError` is the base class of the module's exceptions; `ReadError` is raised "when a tar archive is opened, that either cannot be handled by the tarfile module or is somehow invalid". [DOC S-bzzofa6p]
- `tarfile.open` raises `ReadError` when the mode does not suit a compressed file for reading (mode `'r'` avoids it) and `CompressionError` when a compression method is not supported. [DOC S-bzzofa6p]
- A text search of `tarfile.rst` at v3.13.2 finds no `EOFError`, so the page does not say what a truncated compressed stream raises. [DER S-bzzofa6p: the search came back empty on 2026-10-22]

### What a run showed
- On Python 3.13.2, macOS, 2026-10-22, with archives built in memory: bytes that are not a zip, and a zip with its last ten bytes cut off, both raised `zipfile.BadZipFile` ("File is not a zip file") on open; a stored member whose data byte was flipped raised `BadZipFile` ("Bad CRC-32") on `read`; `BadZipFile` derives from `Exception` directly, not from `OSError`. [DER S-vpqnb7i6: the documented class; the results of one run]
- On the same run, a member with its encrypted flag set (and no password) raised a plain `RuntimeError` ("is encrypted, password required"), and a member with compression method 99 raised `NotImplementedError`, which is a subclass of `RuntimeError`: one `except RuntimeError` takes both. [DER S-vpqnb7i6: the documented `NotImplementedError`; the results of one run]
- A deflated member whose compressed bytes were damaged raised `zlib.error` ("invalid code lengths set"), which is neither a `BadZipFile` nor an `OSError`; a deflated member whose declared compressed size was cut to ten bytes raised `BadZipFile` ("Bad CRC-32"). [DER S-vpqnb7i6: the documented causes; the results of one run]
- A `tar.gz` cut at half its length, opened with mode `'r:gz'` and read member by member, raised `EOFError` ("Compressed file ended before the end-of-stream marker was reached"), not a `TarError`; input that was not gzip at all, and a gzip stream with a damaged byte, both raised `ReadError` ("not a gzip file", "zlib error"), a `TarError`. [DER S-bzzofa6p: the documented `ReadError`; the results of one run]
- So a reader of untrusted archives catches `zipfile.BadZipFile`, `RuntimeError`, `zlib.error`, `EOFError`, `tarfile.TarError` and `OSError` together and treats each as "unreadable archive", never as "no match". [DER S-vpqnb7i6, S-bzzofa6p: the classes above and the probes]
- Open: `bz2` and `lzma` members and `.tar.xz` archives were not run, nor a zip with a damaged ZIP64 record; whether the exception types change in a later Python was not read. [UNK: see `_gaps.md`]

## Reference
- `python/stdlib-urllib-errors.md`: the same question for a network read (which exception a cut or failed response raises).
- `python/stdlib-argparse-json.md`: exit codes a command-line tool chooses for a failed read.

## Examples
- SNIPPET: read the member names of an archive and map every read failure to one error; context: Python 3.13, standard library only; checked: run (a good zip and a good `tar.gz` gave their names; a zip with an encrypted member, a cut `tar.gz` and a file that is no archive each gave `unreadable`) [DER S-vpqnb7i6, S-bzzofa6p: the exception classes above]
```python
import tarfile
import zipfile
import zlib


def names(path: str) -> list[str]:
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                z.testzip()
                return z.namelist()
        with tarfile.open(path, "r") as t:
            return t.getnames()
    except (zipfile.BadZipFile, RuntimeError, zlib.error, EOFError,
            tarfile.TarError, OSError) as err:
        raise ValueError(f"unreadable: {type(err).__name__}") from err
```
