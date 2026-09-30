"""The query log's redactor (`python3 _tools/tests.py -k redact`): _tools/redact.py against a positive and a negative
corpus (kb/_self/querylog.md, Redaction).

  positive   every identifier shape comes out as kb placeholders only, person and organisation names through the
             Haiku stub, and the leak scan (kbcommon.leak_hits, the shapes of test_kb_leaks.py's TestLeaks) finds nothing in
             the output (planted: the raw corpus fails the scan, and so does `redact.py --scan`)
  negative   well-known SIDs, ids and hosts the public root contains, documentation values and the placeholders
             come out unchanged
  idempotent redact(redact(x)) == redact(x) over both corpora and their concatenation
  Haiku      the `claude -p` argument list; a flagged entry, a malformed reply and a leak the rules miss each drop

The corpus is built at run time: a `~` breaks every identifier in this file's source, so the leak scan of tracked
files passes over it, and c() removes the marks.
"""
import json, os, subprocess, sys

import pytest

import kbcommon, redact

TOOLS = os.path.dirname(os.path.abspath(__file__))


def c(s):
    return s.replace("~", "")


# one entry per shape; each value must be gone from the output
POSITIVE = {
    "guid": ("Why does policy 3f2b8c1~e-5d4a-4b7c-9e1f-aa3b4c5d6e7f fail on the tenant?", ["3f2b8c1e"]),
    "guid upper": ("Object {9A8B7C6~D-1E2F-4A3B-8C9D-0E1F2A3B4C5D} is missing", ["9A8B7C6D"]),
    "guid bare": ("the app id 3f2b8c1~e5d4a4b7c9e1faa3b4c5d6e7f is not consented", ["3f2b8c1e5d4a"]),
    "ipv4 private": ("the DP at 10.~1.20.33 and 172.~16.5.4 and 192.~168.10.7 times out", ["10.~1.20.33", "172.~16.5.4", "192.~168.10.7"]),
    "ipv4 public": ("our proxy 8~1.2.113.44 blocks it", ["81.2.113.44"]),
    "ipv6": ("the client fe80::1c2b:3aff:fe4d:5e6f and 2a01:4f8:c0c:1234::1 cannot reach it", ["fe80::1c2b", "2a01:4f8"]),
    "sid domain": ("owner S-1-5-21-3623811015-3361044348-30300820-1013 lost rights", ["3623811015"]),
    "sid domain admins": ("S-1-5-21-1004336348-1177238915-682003330-512 has too many members", ["1004336348"]),
    "upn": ("sign-in fails for anna.nowak~@acme-corp.pl since Monday", ["anna.nowak", "acme-corp"]),
    "email": ("mail from it-helpdesk~@acme.com.pl bounces", ["it-helpdesk", "acme.com"]),
    "upn netbios suffix": ("UPN jsmith~@ACME has no suffix", ["jsmith", "ACME"]),
    "down-level": ("ACME\\anowak cannot run the task", ["ACME", "anowak"]),
    "down-level lower": ("whoami says acme-pl\\j.smith", ["acme-pl", "j.smith"]),
    "fqdn": ("fs01.acme.local and dc01.ad.acme-corp.pl resolve wrongly", ["acme", "fs01", "dc01"]),
    "fqdn tenant": ("files on acmecorp.sharepoint.com are blocked", ["acmecorp"]),
    "unc": ("copy from \\\\fs01\\Finance$\\Budget2025\\q3.xlsx fails", ["fs01", "Budget2025"]),
    "unc ip": ("\\\\10.~1.2.3\\deploy\\acmetools", ["10.~1.2.3", "acmetools"]),
    "home windows": ("C:\\Us~ers\\anowak\\AppData\\Local\\Temp\\acmecorp_setup.log is huge", ["anowak", "acmecorp"]),
    "home json": ("\"C:\\\\Us~ers\\\\pwisniewski\\\\Desktop\\\\x.ps1\"", ["pwisniewski"]),
    "home macos": ("/Us~ers/anowak/projects/acmeportal", ["anowak", "acmeportal"]),
    "home linux": ("/ho~me/jsmith/.ssh/config", ["jsmith"]),
    "drive path": ("D:\\Clients\\Kowalczyk Holding\\umowa.xlsx", ["Kowalczyk", "umowa"]),
    "jwt": ("token ey~JhbGciOiJIUzI1NiJ9.ey~JzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            ["eyJ", "dozjg"]),
    "gitlab token": ("export TOKEN=gl~pat-a1B2c3D4e5F6g7H8i9J0kLmN", ["a1B2c3D4"]),
    "github token": ("gh~p_" + "Ab1" * 12 + " was revoked", ["Ab1Ab1"]),
    "password": ("pass~word = \"Zaq12wsxCde3\" in the script", ["Zaq12wsx"]),
    "account key": ("Account~Key=" + "Q2xhdWRlQ29kZVRva2VuMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=" + ";", ["Q2xhdWRl"]),
    "sas": ("https://x.blob.core.windows.net/c/f?sv=2022&s~ig=" + "abcDEF123ghiJKL456mnoPQR789stuVWX0yz" + " fails",
            ["abcDEF123"]),
    "high entropy": ("the key Zk9xR2tWb3BqM3NlY3JldDEyMzQ1Ng does not work", ["Zk9xR2tW"]),
    "hex digest": ("hash a3f9c2e8d1b04f7e9a6c5d2b1e0f3a4c5b6d7e8f9a0b1c2d mismatches", ["a3f9c2e8"]),
    "computer default": ("DESKTOP-7H2K9QP is not compliant", ["7H2K9QP"]),
    "computer site": ("WAW-SRV-017 and LT-PL-4411 and KRK-WS0042 miss updates", ["WAW-SRV", "LT-PL-4411", "KRK-WS0042"]),
    "crlf": ("line one fs01.acme.local\r\nline two ACME\\anowak\r\n", ["acme", "anowak"]),
    "names": ("Anna Nowak from Acme Polska asked Piotr Wiśniewski about ACME\\pwisniewski", ["Anna", "Nowak", "Acme",
                                                                                       "Piotr", "Wiśniewski"]),
}

NEGATIVE = [
    "How do I deploy a Win32 app with Intune to devices in a dynamic group?",
    "Well-known SIDs: S-1-5-18 S-1-5-32-544 S-1-1-0 S-1-5-80-0 and capability "
    "S-1-15-3-1024-1065365936-1281604716-3511738428-1654721687-432734479-3232135806-4053264122-3456934681",
    "Graph appId 00000003-0000-0000-c000-000000000000 and ASR rule d4f940ab-401b-4efc-aadc-ad5f3c50688a",
    "hosts learn.microsoft.com, graph.microsoft.com, login.microsoftonline.com and gitlab.com",
    "https://learn.microsoft.com/en-us/mem/intune/apps/apps-win32-app-management",
    "PL-LT-00123 PL-SRV-0042 corp.example.com 00000000-0000-0000-0000-000000000000 jan.kowalski",
    "jan.kowalski@corp.example.com CORP\\jan.kowalski \\\\PL-SRV-0042\\share S-1-5-21-0-0-0-512 192.0.2.10 "
    "2001:db8::10 <secret> PL-PATH",
    "NT AUTHORITY\\SYSTEM, NT AUTHORITY\\NETWORK SERVICE, BUILTIN\\Administrators and HKLM\\SOFTWARE\\Policies",
    "C:\\Windows\\CCM\\Logs\\AppEnforce.log and C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "127.0.0.1, ::1, 255.255.255.0 and 192.0.2.44 are fine",
    "settings.json, kb_hook.py, web.config and System.IO.Path.Combine",
    "CVE-2024-21412, KB5034441, Win32LobAppPowerShellScript and DeviceManagementConfigurationPolicy",
    "line one\r\nline two\r\n",
]

NAMES = {"Anna Nowak": "jan.kowalski", "Piotr Wiśniewski": "jan.kowalski", "Acme Polska": "CORP"}


def haiku_stub(texts):
    """What Haiku does in stage 2, for known names: each person as jan.kowalski, each organisation as CORP."""
    out = []
    for t in texts:
        for name, placeholder in NAMES.items():
            t = t.replace(name, placeholder)
        out.append((t, False))
    return out


@pytest.fixture(scope="module")
def k():
    return redact.known()


def positive(k):
    raw = [c(t) for t, _ in POSITIVE.values()]
    return raw, redact.redact_batch(raw, haiku_stub, k)


def test_known_holds_the_kb_ids_the_negative_corpus_uses(k):
    assert {"00000003" "00000000c000000000000000", "d4f940ab401b4efcaadcad5f3c50688a"} <= k.guids  # Graph, an ASR rule
    assert {"learn.microsoft.com", "graph.microsoft.com", "login.microsoftonline.com", "gitlab.com"} <= k.hosts


def test_positive_corpus_gives_placeholders_only(k):
    raw, out = positive(k)
    assert None not in out, [r for r, o in zip(raw, out) if o is None]
    for (name, (_, gone)), o in zip(POSITIVE.items(), out):
        for g in map(c, gone):
            assert g not in o, f"{name}: {g!r} left in {o!r}"
        assert o != c(POSITIVE[name][0]), name
    assert "\r\n" in out[list(POSITIVE).index("crlf")], "line ends are kept"


def test_leak_scan_over_the_corpus_output(k):
    raw, out = positive(k)
    planted = kbcommon.leak_hits("\n".join(raw))
    assert {kind for kind, _ in planted} == {"secret", "home", "ip", "email", "guid"}, planted  # the scan bites
    assert kbcommon.leak_hits("\n".join(out)) == []
    neg = [redact.redact(t, k) for t in NEGATIVE]
    assert redact.scan("\n".join(neg), k) == []


def test_negative_corpus_is_unchanged(k):
    for t in NEGATIVE:
        assert redact.redact(t, k) == t


def test_placeholders_pass_through(k):
    for v in redact.PLACEHOLDERS.values():
        assert redact.redact(v, k) == v, v


def test_idempotent(k):
    raw, out = positive(k)
    texts = raw + NEGATIVE + ["\n".join(raw + NEGATIVE), " ".join(raw)]
    for t in texts:
        once = redact.redact(t, k)
        assert redact.redact(once, k) == once, t
    for o in out:
        assert redact.redact(o, k) == o


def test_shapes_from_a_fixture_kb_stay():
    """An id a public root contains stays: the allowlist is derived from the root's text, not kept by hand."""
    guid = "3f2b8c1e-5d4a-4b7c-9e1f-aa3b4c5d6e7f"
    fixture = redact.scan_known([f"The CSP node uses {guid} and fs01.acme.local."])
    assert redact.redact(f"why {guid} on fs01.acme.local?", fixture) == f"why {guid} on fs01.acme.local?"
    empty = redact.scan_known([])
    assert redact.redact(f"why {guid} on fs01.acme.local?", empty) == \
        f"why {redact.PLACEHOLDERS['guid']} on {redact.PLACEHOLDERS['host']}?"


def test_names_argv():
    argv = redact.names_argv("haiku")
    assert argv[1:4] == ["-p", "--model", "haiku"]
    assert argv[argv.index("--tools") + 1] == ""
    assert json.loads(argv[argv.index("--settings") + 1]) == {"disableAllHooks": True}
    assert "--strict-mcp-config" in argv and all(isinstance(a, str) for a in argv)


def test_names_prompt_and_reply_round_trip():
    texts = ["a \"quoted\" Wiśniewski", "b"]
    prompt = redact.names_prompt(texts)
    sent = json.loads(prompt.rsplit("\n\n", 1)[1])
    assert [e["text"] for e in sent] == texts
    reply = "Here:\n" + json.dumps([{"i": 0, "text": "x", "identifying": False}, {"i": 1, "text": "y", "identifying": True}])
    assert redact.parse_names(reply, 2) == [("x", False), ("y", True)]
    for bad in ("no json", "[]", json.dumps([{"i": 1, "text": "x", "identifying": False}]),
                json.dumps([{"i": 0, "text": "x", "identifying": "no"}])):
        with pytest.raises(ValueError):
            redact.parse_names(bad, 1)


def test_doubt_drops(k, monkeypatch):
    texts = ["how do I fix fs01.acme.local", "Anna Nowak again"]
    flagged = lambda ts: [(ts[0], False), (ts[1], True)]  # noqa: E731
    assert redact.redact_batch(texts, flagged, k) == ["how do I fix corp.example.com", None]

    def malformed(ts):
        return redact.parse_names("not json", len(ts))
    assert redact.redact_batch(texts, malformed, k) == [None, None]
    echo = lambda ts: [(t + " reach me at anna~@acme.pl".replace("~", ""), False) for t in ts]  # noqa: E731
    assert all("acme" not in o for o in redact.redact_batch(texts, echo, k))  # the second rules pass catches it
    # planted: with the rules switched off, only the leak scan stands between Haiku's output and the store
    monkeypatch.setattr(redact, "redact", lambda text, k=None: text)
    assert redact.finish(c("reach me at anna~@acme.pl"), k) is None
    assert redact.finish("a clean question", k) == "a clean question"


def test_cli_keeps_line_ends_and_scans(tmp_path, k):
    """Two runs (each reads the public root once): the rules pass over a file, the planted scan over stdin."""
    raw = c("fs01.acme.local\r\nACME\\anowak at 10.~1.2.3\n").encode("utf-8")
    run = lambda *a: subprocess.run([sys.executable, os.path.join(TOOLS, "redact.py"), *a],  # noqa: E731
                                    input=raw, capture_output=True)
    f = tmp_path / "in.txt"
    f.write_bytes(raw)
    p = run(str(f))
    assert p.returncode == 0, p.stderr
    assert p.stdout == b"corp.example.com\r\nCORP\\jan.kowalski at 192.0.2.10\n"
    assert redact.scan(p.stdout.decode("utf-8"), k) == []
    planted = run("--scan")
    assert planted.returncode == 1 and b"ip\t10.1.2.3" in planted.stdout.replace(b"\r\n", b"\n")
    assert run("--bogus").returncode == 2
