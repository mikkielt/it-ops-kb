"""provider.py tests, no network (`python3 _tools/tests.py -k provider`).

The shared registry is well-formed (every column, one `*` row, known signals, a probe date); a root's _providers.csv
replaces or adds rows; for_url picks the longest prefix; raw forms, version keys and the document text; probe on
canned responses (304s, raw forms, soft 404) decides the measured columns.
"""
import os

import pytest

import kbcommon, provider


def test_registry_well_formed():
    rows = provider.providers(kbcommon.public())
    names = [r["provider"] for r in rows]
    assert len(names) == len(set(names))
    assert sum(1 for r in rows if r["match"].split() == ["*"]) == 1, "exactly one fallback row"
    for r in rows:
        assert set(provider.COLS) <= set(r), r["provider"]
        sig = [s for s in r["signals"].split(";") if s]
        assert sig and all(s in provider.SIGNALS for s in sig), (r["provider"], sig)
        assert r["probed_utc"], f"{r['provider']}: never probed (/kb-probe)"


def test_for_url_longest_prefix_and_fallback():
    rows = [{"provider": "a", "match": "docs.example.com/"}, {"provider": "b", "match": "docs.example.com/deep/ other.example.com/"},
            {"provider": "g", "match": "*"}]
    assert provider.for_url("https://docs.example.com/x", rows)["provider"] == "a"
    assert provider.for_url("https://docs.example.com/deep/x", rows)["provider"] == "b"
    assert provider.for_url("https://other.example.com/", rows)["provider"] == "b"
    assert provider.for_url("https://elsewhere.example.org/", rows)["provider"] == "g"
    assert provider.for_url("https://learn.microsoft.com/en-us/entra/x")["provider"] == "learn"


def test_root_rows_merge(tmp_path, monkeypatch):
    shared = tmp_path / "providers.csv"
    kbcommon.write_csv(str(shared), provider.COLS, [{"provider": "wiki", "match": "wiki.example.com/", "signals": "hash"},
                                                    {"provider": "generic", "match": "*", "signals": "hash"}])
    root = tmp_path / "team"
    root.mkdir()
    kbcommon.write_csv(str(root / provider.ROOT_FILE), provider.COLS,
                       [{"provider": "wiki", "match": "wiki.corp.example.com/", "signals": "etag;hash"}])
    monkeypatch.setattr(provider, "SHARED", str(shared))
    r = kbcommon.Root("team", str(root), "T", "internal", "")
    rows = provider.providers(r)
    wiki = [x for x in rows if x["provider"] == "wiki"]
    assert len(wiki) == 1 and wiki[0]["match"] == "wiki.corp.example.com/" and wiki[0]["_root"] == "team"


def test_signals_pin_only_for_pinned_urls():
    row = {"signals": "pin;etag;hash"}
    sha = "a" * 40
    assert provider.signals(row, f"https://raw.githubusercontent.com/o/r/{sha}/x.md") == ["pin", "etag", "hash"]
    assert provider.signals(row, "https://raw.githubusercontent.com/o/r/main/x.md") == ["etag", "hash"]
    assert provider.signals({"signals": "hash;etag"}, "https://x.example.com/") == ["etag", "hash"], "hash is always last"


def test_raw_url_forms():
    u = "https://learn.microsoft.com/en-us/entra/x#section"
    assert provider.raw_url(u, {"raw_form": "query:accept=text/markdown"}) == ("https://learn.microsoft.com/en-us/entra/x?accept=text/markdown", {})
    assert provider.raw_url("https://code.claude.com/docs/en/hooks", {"raw_form": "suffix:.md"})[0].endswith("/hooks.md")
    assert provider.raw_url("https://code.claude.com/docs/en/hooks.md", {"raw_form": "suffix:.md"})[0].endswith("/hooks.md")
    assert provider.raw_url(u, {"raw_form": "header:text/markdown"})[1] == {"Accept": "text/markdown"}
    assert provider.raw_url("https://github.com/o/r/blob/v1/a/b.md", {"raw_form": "blob-to-raw"})[0] == \
        "https://raw.githubusercontent.com/o/r/v1/a/b.md"
    assert provider.raw_url("https://gitlab.com/g/p/-/blob/v1/a.md", {"raw_form": "blob-to-raw"})[0] == "https://gitlab.com/g/p/-/raw/v1/a.md"


def test_version_and_document_text():
    md = "---\ntitle: T\ngit_commit_id: abc123\nupdated_at: 2026-08-31T17:37:00Z\n---\n# Title\n\nSee [the page](https://x.example.com) ![img](a.png)<!-- note -->.\n"
    assert provider.version_of(md, ["git_commit_id", "updated_at", "document_id"]) == {"git_commit_id": "abc123", "updated_at": "2026-08-31T17:37:00Z"}
    assert provider.doc_text(md.encode(), "text/markdown") == "# Title\n\nSee the page .\n"
    html = b'<html><head><meta name="updated_at" content="2026-01-02"></head><body><nav>Menu</nav><main><h2>Part</h2><p>Body text.</p></main></body></html>'
    assert provider.version_of(html.decode(), ["updated_at"]) == {"updated_at": "2026-01-02"}
    assert provider.doc_text(html, "text/html") == "## Part\nBody text.\n"
    assert provider.doc_text(b"\x00\x01zip", "application/zip") is None


def _resp(status=200, body=b"", ctype="text/html", etag="", lastmod="", final=None):
    h = {"content-type": ctype}
    if etag:
        h["etag"] = etag
    if lastmod:
        h["last-modified"] = lastmod
    return {"status": status, "headers": h, "body": body, "final": final, "hops": [], "error": ""}


def test_probe_decides_measured_columns(monkeypatch):
    page = "https://docs.example.com/a/page"
    md = b"---\ngit_commit_id: abc\nupdated_at: 2026-01-01\n---\n# Page\n" + b"text " * 60

    def fake(url, headers=None, **k):
        headers = headers or {}
        if url.endswith("robots.txt"):
            return _resp(200, b"Sitemap: https://docs.example.com/sitemap.xml\n", "text/plain")
        if "accept=text/markdown" in url:
            if headers.get("If-None-Match") == '"e1"':
                return _resp(304)
            return _resp(200, md, "text/markdown", etag='"e1"', lastmod="Mon, 01 Jun 2026 00:00:00 GMT")
        if url.endswith(".md") or headers.get("Accept") == "text/markdown":
            return _resp(404)
        if url == page:
            return _resp(200, b"<html><title>Page - Docs</title><main><p>x</p></main></html>", etag='"h1"', final=url)
        return _resp(200, b"<html>landing</html>")  # a made-up url answers 200: soft 404

    monkeypatch.setattr(provider, "request", fake)
    found, ev = provider.probe({"provider": "x", "match": "docs.example.com/", "search_api": "-"}, page)
    assert found["raw_form"] == "query:accept=text/markdown"
    assert found["etag"] == "stable" and found["not_found"] == "soft-404"
    assert found["version_meta"].startswith("git_commit_id,updated_at")
    assert found["signals"] == "etag;version;hash", found
    assert found["sitemap"] == "https://docs.example.com/sitemap.xml"
    assert found["lastmod"] == "stable-no-304"


def test_probe_cli_needs_a_known_provider():
    import subprocess, sys
    p = subprocess.run([sys.executable, os.path.join(kbcommon.TOOLS, "provider.py"), "probe", "no-such-provider"],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 2 and "no provider" in p.stderr


@pytest.mark.parametrize("url", ["https://learn.microsoft.com/en-us/intune/x", "https://raw.githubusercontent.com/o/r/" + "b" * 40 + "/f.md",
                                 "https://code.claude.com/docs/en/hooks", "https://modelcontextprotocol.io/docs/x",
                                 "https://docs.gitlab.com/ci/", "https://www.example.org/any"])
def test_every_family_has_a_provider(url):
    assert provider.for_url(url) is not None


TEXT = "<html><body><p>Sigstore information for Python releases</p></body></html>\n".encode("utf-8") * 20


def _deflate(data, wbits):
    import zlib
    c = zlib.compressobj(wbits=wbits)
    return c.compress(data) + c.flush()


@pytest.mark.parametrize("coding,wbits", [("gzip", 31), ("x-gzip", 31), ("deflate", 15), ("deflate", -15)])
def test_decode_body_takes_off_the_content_encoding(coding, wbits):
    assert provider.decode_body(_deflate(TEXT, wbits), coding) == TEXT
    assert provider.decode_body(_deflate(TEXT, wbits), coding.upper()) == TEXT


def test_decode_body_keeps_what_it_cannot_decode():
    assert provider.decode_body(TEXT, "") == TEXT
    assert provider.decode_body(TEXT, "identity") == TEXT
    assert provider.decode_body(b"not gzip at all", "gzip") == b"not gzip at all"  # a lying header: the bytes as sent
    assert provider.decode_body(b"\x28\xb5\x2f\xfd", "zstd") == b"\x28\xb5\x2f\xfd"  # an unknown coding: as sent
    # a list of codings is undone last to first
    assert provider.decode_body(_deflate(_deflate(TEXT, 15), 31), "deflate, gzip") == TEXT
    # the limit caps the decoded size, as it caps a plain body
    assert provider.decode_body(_deflate(TEXT, 31), "gzip", limit=10) == TEXT[:10]


def test_request_decodes_a_gzip_body_sent_unasked(monkeypatch):
    """www.python.org answers gzip without an Accept-Encoding: request() hands callers the text, not the gzip bytes."""
    import http.server, threading
    gz = _deflate(TEXT, 31)

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            code = 200 if self.path == "/ok" else 404
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(gz)))
            self.end_headers()
            self.wfile.write(gz)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(provider, "DELAY", 0)
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        r = provider.request(base + "/ok")
        assert r["status"] == 200 and r["body"] == TEXT and r["body"][:2] != bytes([31, 139])
        assert r["headers"]["content-encoding"] == "gzip"  # the headers stay as the server sent them
        e = provider.request(base + "/missing")  # an HTTP error body is decoded too
        assert e["status"] == 404 and e["body"] == TEXT
    finally:
        srv.shutdown()
        srv.server_close()
