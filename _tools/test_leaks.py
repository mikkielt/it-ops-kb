"""The leak scan: tracked files hold no secret, authored files hold placeholders only, and the scan the push guards
run (kbpublic.file_hits) reports each kind of planted leak. The planted values are assembled at run time, so this
file holds none of them whole. The patterns are the production ones (kbcommon); none is kept here."""
import csv, functools, json, os, re, subprocess, sys

import kbcommon
import kbpublic
from conftest import TOOLS, text, tracked

def planted():
    """One leak of each kind, built from parts."""
    return {
        "secret": "gh" + "p_" + "a" * 36,
        "home": "/".join(("", "Users", "realperson", "docs")),
        "ip": ".".join(("10", "77", "88", "99")),
        "email": "@".join(("real.person", "corp-mail.net")),
        "guid": "-".join(("1a2b3c4d", "5e6f", "7a8b", "9c0d", "1e2f3a4b5c6d")),
    }


def secret_plants():
    """One string for each kbcommon.SECRETS pattern, in its order, built from parts. The `(?i)` shape's plant is in
    capitals, which only a screen that casefolds the text and the pattern together finds."""
    return [
        "-----BEGIN " + "RSA PRIVATE KEY-----",
        "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "gh" + "p_" + "a" * 36,
        "github" + "_pat_" + "a" * 22,
        "glp" + "at-" + "a" * 20,
        "glr" + "t-" + "a" * 20,
        "xo" + "xb-" + "1234567890",
        "sk-" + "ant-" + "a" * 20,
        "sk-" + "proj-" + "a" * 32,
        "Account" + "Key=" + "A" * 40,
        "?si" + "g=" + "a" * 30,
        "ey" + "J" + "a" * 10 + ".ey" + "J" + "a" * 10 + "." + "a" * 10,
        "PASS" + "WORD" + ' = "' + "hunter22xx" + '"',
    ]


def allowlist():
    return kbpublic.parse_allowlist(text(kbpublic.ALLOWLIST_PATH) or "")


def pinned():
    out = set()
    for r in kbcommon.roots():
        with open(os.path.join(r.path, kbcommon.ARTIFACTS), encoding="utf-8-sig", newline="") as f:
            out |= {kbcommon.repo_rel(x["path"], r.path) for x in csv.DictReader(f)}
    return out


@functools.lru_cache(maxsize=None)
def screens():
    """(secret searches, the `(?i)` secrets' search or None, placeholder searches): each matches wherever a production
    shape (kbcommon.SECRETS and the placeholders-only shapes) matches, and is cheaper. A `\\b` makes the regex engine
    try every character, so a screen drops it, and the shapes written `(?i)` are searched together in the casefolded
    text. A screen only chooses the files the production patterns (kbcommon.leak_hits, kbpublic.file_hits) judge."""
    drop = lambda rx: re.compile(rx.replace("\\b", ""))  # noqa: E731
    folded = [f"(?:{p[4:]})" for p in kbcommon.SECRETS if p.startswith("(?i)")]
    return ([drop(p) for p in kbcommon.SECRETS if not p.startswith("(?i)")], drop("|".join(folded)) if folded else None,
            [drop(x) for x in (kbcommon.LEAK_HOME, kbcommon.LEAK_IPV4, kbcommon.LEAK_EMAIL, kbcommon.LEAK_GUID)]
            + [rx for _, rx in kbcommon._private_patterns()])


def candidate(t, vendored):
    """The text the leak scan's own verdict (kbcommon.leak_hits) reads to decide whether a file may hold a hit, or None
    when no screen matches it: a text a secret screen matches whole, and for an authored file one a placeholder screen
    matches only its matching lines (each placeholder shape lies within one line, so the lines hold every hit)."""
    secrets, folded, placeholders = screens()
    if any(rx.search(t) for rx in secrets) or (folded and folded.search(t.casefold())):
        return t
    if vendored:
        return None
    spans = set()
    for rx in placeholders:
        for m in rx.finditer(t):
            end = t.find("\n", m.end())
            spans.add((t.rfind("\n", 0, m.start()) + 1, len(t) if end < 0 else end))
    return "\n".join(t[a:b] for a, b in sorted(spans)) or None


@functools.lru_cache(maxsize=None)
def scan():
    """[(file, kind, value)] the tracked files hold, as the push guards read them (kbpublic.file_hits) with the
    reviewed allowlist. Vendor exports, snapshots, pinned artifacts and the query log store are read for secrets only
    and files of internal roots are left out of the placeholders rule. One pass over the text finds the files that
    may hold a hit (candidate: the screens, then the leak scan's own verdict on what they pass); file_hits then gives
    the verdict, so the test and the guards agree."""
    allow, pins = allowlist(), pinned()
    internal = tuple(kbcommon.repo_rel(".", r.path) + "/" for r in kbcommon.roots() if r.visibility != "public")
    internal += tuple(kbcommon.repo_rel(p.path, kbcommon.HOME) for p in kbcommon.pointers() if p.visibility != "public")
    secrets = re.compile(kbcommon.secrets_rx())
    out = []
    for f in tracked():
        t = text(f)
        if t is None:
            continue
        vendored = f in pins or "/artifacts/" in f or f"/{kbcommon.SNAPSHOTS}/" in f or f.startswith("kb/_querylog/")
        probe = candidate(t, vendored)
        if probe is None:
            continue
        if vendored:
            if not secrets.search(probe):
                continue
        elif not kbcommon.leak_hits(probe, allow):
            continue
        out += [(f, k, v) for k, v in kbpublic.file_hits(f, t, allow, pins) if k == "secret" or not f.startswith(internal)]
    return out


def test_tracked_files_hold_no_secret_and_authored_files_hold_placeholders_only():
    found = [h for h in scan() if h[1] == "secret"]
    assert not found, "possible secrets (file only):\n" + "\n".join(f"  {f}" for f, _, _ in found[:20])
    found = [h for h in scan() if h[1] != "secret"]
    assert not found, "real-looking values (placeholders only, or allowlist with a reason):\n" + "\n".join(
        f"  {f}: {k} {v}" for f, k, v in found[:20])


def test_scan_reports_each_planted_leak_and_honours_the_allowlist_and_webfetch_hook_denies_a_routed_host_and_passes_the_rest_and_leak_screens_cover_secrets(
        tmp_path, monkeypatch):
    values = planted()
    for kind, value in values.items():
        assert kind in [k for k, _ in kbpublic.file_hits("notes.md", f"see {value} here", {})], kind
    # each production secret shape has a plant its own pattern matches, and the scan's pre-screen (candidate) keeps
    # the whole text for an authored and a vendored file while file_hits reports a secret
    plants = secret_plants()
    assert len(plants) == len(kbcommon.SECRETS), (len(plants), len(kbcommon.SECRETS))
    for pattern, plant in zip(kbcommon.SECRETS, plants):
        assert re.search(pattern, plant), pattern
        body = f"see {plant} here"
        assert candidate(body, False) == body and candidate(body, True) == body, pattern
        assert "secret" in [k for k, _ in kbpublic.file_hits("notes.md", body, {})], pattern
        assert "secret" in [k for k, _ in kbpublic.file_hits("kb/x/artifacts/a.txt", body, {})], pattern
    # every armor line but the EC and the OpenPGP block ones is a secret on its own; those two are one only with key
    # material after them (no allowlist entry passes them by value), and their label quoted alone in prose, or ahead of
    # its own tail line, is not
    for kind in ("", "RSA ", "EC ", "OPENSSH ", "DSA ", "PGP ", "PGP BLOCK ", "ENCRYPTED "):
        label = kind.replace("BLOCK ", "") + "PRIVATE KEY" + (" BLOCK" if "BLOCK" in kind else "")
        head, tail = "-----BEGIN " + label + "-----", "-----END " + label + "-----"
        for lead in ("\n", "\r\n", "\\n", "\\\\n", "\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES-128-CBC,0123ABCD\n\n",
                     "\nComment: Alice | work\n\n", "\nComment: C:\\new\n\n", " Comment: x ",
                     "\n> ", "\n# ", "\n// ", "\n/// ", "\n//! ", " | ", "\n* ", "\n- ", "\nComment:Alice\n\n", "\n- Comment: a\n- ", "\\t", "\nProc-Type:4,ENCRYPTED\n",
                     "\n> Proc-Type: 4,ENCRYPTED\n> DEK-Info: AES-128-CBC,0123ABCD\n> \n> "):
            assert kbcommon.leak_hits(head + lead + "MIIBVAIBADANBgkqhkiG9w0BAQEFAASC" + "\n" + tail, allowlist()) == \
                [("secret", head)], (kind, lead)
        alone = kbcommon.leak_hits(f"the line `{head}` and `{tail}` name it, as does {head}\n{tail}\n", allowlist())
        assert alone == ([] if kind in ("EC ", "PGP BLOCK ") else [("secret", head)] * 2), kind
        wrapped = head + "\n" + "\n".join(["MIIBVAIBADANBgkq", "hkiG9w0BAQEFAASC", "BKcwggSjAgEAAoIB"]) + "\n" + tail
        assert kbcommon.leak_hits(wrapped, allowlist()) == [("secret", head)], kind
        path = kbcommon.leak_hits(head + "\nkb/public/security/secret-shapes-in-text.md\n", allowlist())
        assert path == ([] if kind in ("EC ", "PGP BLOCK ") else [("secret", head)]), kind
        # a repository path right after the label passes; a single-line body that a `.`, `_` or `-` follows is key material
        for ref in ("kb/public/mecm/sql2022-views.md", "kb/public/Intune/Apps/Win32.md",
                    "kb/public/Intune/ConfigurationProfiles.md", "kb/public/Entra/ConditionalAccessPolicies-and-more.md"):
            assert kbcommon.leak_hits(head + " " + ref + " page", allowlist()) == \
                ([] if kind in ("EC ", "PGP BLOCK ") else [("secret", head)]), (kind, ref)
        # a table row of the label, a `Name: value` cell and an identifier cell holds no key material
        row = kbcommon.leak_hits(f"| {head} | Note: PEM label | PrivateKeyInfoStructureXX |", allowlist())
        assert row == ([] if kind in ("EC ", "PGP BLOCK ") else [("secret", head)]), kind
        for body in ("MIIBVAIBADANBgkqhkiG9w0BAQEFAASC", "MIIBVAIBADANBgkqhkiG9w0BAQEF/AASC+BKcwggSjAgEAAoIB",
                     "CwgQj8C/nbil1bW34cYU", "XGjtEk/DnNfribxUdl7d"):
            for suffix in (".", "_x", "-x", ".pem"):
                assert kbcommon.leak_hits(head + " " + body + suffix, allowlist()) == [("secret", head)], (kind, body, suffix)
    # the placeholders pass, an allowlisted value passes
    ok = "jan.kowalski t@example.com 00000000-0000-0000-0000-000000000000 192.0.2.7"
    assert kbpublic.file_hits("notes.md", ok, {}) == []
    allow = kbpublic.parse_allowlist("\n".join(f"{k} {v}  # reviewed" for k, v in values.items() if k != "home"))
    assert [k for k, _ in kbpublic.file_hits("notes.md", " ".join(values.values()), allow)] == ["home"]
    # a home path passes only when the allowlist names the whole match (lowercased); a sibling path is still flagged
    match = re.match(kbcommon.LEAK_HOME, values["home"]).group(0)
    allow = kbpublic.parse_allowlist(f"home {match.upper()}  # reviewed")
    assert kbpublic.file_hits("notes.md", f"see {values['home']} here", allow) == []
    assert [k for k, _ in kbpublic.file_hits("notes.md", values["home"].replace("realperson", "other"), allow)] == ["home"]
    # the private names of an internal root and its pointer (a registry planted in a temporary directory): a source id with
    # its prefix, a qualified path and the pointer's url host and path are refused, a bare root name is not
    team = tmp_path / "team"
    team.mkdir()
    (team / kbcommon.ROOT_FILE).write_text("---\nroot: team-z\nid_prefix: TZ\nvisibility: internal\n---\n", encoding="utf-8")
    monkeypatch.setenv("KB_ROOTS", str(team))
    monkeypatch.setattr(kbcommon, "_ROOTS", [])
    monkeypatch.setattr(kbcommon, "_MISSING", [])
    monkeypatch.setattr(kbcommon, "_pointer_files", lambda: [str(tmp_path / "team-y.md")])
    (tmp_path / "team-y.md").write_text("---\nroot: team-y\nid_prefix: TY\nvisibility: internal\nurl: https://" + "kb.team-y"
                                        + ".test/team-y/kb.git\naccess: fetch\n---\n", encoding="utf-8")
    private = "TZ-k3f7q2zd TY-k3f7q2zd team-z/mdm/x.md kb.team-y.test team-y/kb"
    got = [v for _, v in kbcommon.leak_hits(private)]
    assert all(any(w in v for v in got) for w in private.split()), got
    assert kbcommon.leak_hits("S-k3f7q2zd on corp.example.com, public/mdm/x.md; team-z owns it") == []
    # vendor exports are read for secrets only
    assert [k for k, _ in kbpublic.file_hits("kb/x/artifacts/a.txt", " ".join(values.values()), {})] == ["secret"]
    # the PreToolUse guard on WebFetch (kb_hook.webfetch_deny): a host the routes table routes away from WebFetch is
    # denied with the row's find and read routes as the reason; another host, a url with no host and an unreadable
    # table pass. Both hook files wire it synchronously (an async hook cannot deny).
    import kb_hook, ql_learn
    ev = lambda url: {"hook_event_name": "PreToolUse", "tool_name": "WebFetch", "tool_input": {"url": url}}
    out = kb_hook.webfetch_deny(ev("https://learn.microsoft.com/en-us/intune/"))["hookSpecificOutput"]
    row = ql_learn.avoided_route("learn.microsoft.com")
    assert out["permissionDecision"] == "deny" and row["find"] in out["permissionDecisionReason"] \
        and row["read"] in out["permissionDecisionReason"], out
    assert kb_hook.webfetch_deny(ev("https://pypi.org/project/x/")) is None
    assert kb_hook.webfetch_deny(ev("not a url")) is None
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps(ev("https://pypi.org/")),
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and p.stdout == "", p.stdout + p.stderr  # a pass prints nothing
    monkeypatch.setattr(ql_learn, "WEB_SOURCES", tmp_path / "missing.md")
    assert kb_hook.webfetch_deny(ev("https://learn.microsoft.com/")) is None
    for path in (".claude/settings.json", ".claude-plugin/plugin.json"):
        pre = json.loads(text(path))["hooks"]["PreToolUse"]
        hooks = [h for m in pre if m.get("matcher") == "WebFetch" for h in m["hooks"]]
        assert [h for h in hooks if "kb_hook.py" in h["command"] and not h.get("async")], path


def test_backlog_check_refuses_leak_in_item_text(tmp_path):
    def backlog(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", str(tmp_path), *args],
                           cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    assert backlog("new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    assert backlog("check")[0] == 0
    (path,) = tmp_path.rglob("EP-*.json")
    item = json.loads(path.read_text(encoding="utf-8"))
    value = planted()["ip"]
    item["goal"] = f"see {value} here"
    path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8", newline="\n")
    code, out = backlog("check")
    assert code == 1 and "field goal has a leak-scan hit (ip" in out and value not in out, out
