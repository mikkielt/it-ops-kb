"""The leak scan over tracked files (`python3 _tools/tests.py` runs them with every other test module).

TestLeaks (tracked files): secrets in any file; in authored files (not those of `visibility: internal` roots) also home-directory paths, private IPv4 addresses,
non-placeholder e-mail addresses and GUIDs outside the reviewed allowlist (_tools/tests_allowlist.txt); files that
must never be committed; oversized files.
"""
import os, re

import kbcommon
from conftest import KB, URL_RX, allowlist, authored, fmt, hits, text, tracked

MAX_BYTES = 10 * 1024 * 1024


class TestLeaks:
    # the shapes live in kbcommon: kbingest.py's survey flags the same secrets, redact.py drops what this scan flags

    def test_no_secrets(self):
        allow = allowlist().get("secret", set())
        files = [f for f in tracked() if text(f) is not None]
        found = [h for h in hits(kbcommon.secrets_rx(), files) if h[2].lower() not in allow]  # one pass per file
        assert not found, "possible secrets:\n" + fmt(found)

    def test_no_home_paths(self):
        found = [h for h in hits(kbcommon.LEAK_HOME, authored())
                 if re.split(r"[/\\]+", h[2])[-1].lower() not in kbcommon.HOME_GENERIC]
        assert not found, "machine-specific home paths:\n" + fmt(found)

    def test_no_private_ipv4(self):
        allow = allowlist().get("ip", set())
        found = [h for h in hits(kbcommon.LEAK_IPV4, authored(), strip_urls=True) if h[2] not in allow
                 and all(int(x) < 256 for x in h[2].split("."))]
        assert not found, "private IPv4 addresses (use 192.0.2.x/198.51.100.x/203.0.113.x, or allowlist):\n" + fmt(found)

    def test_no_real_email_addresses(self):
        allow = allowlist().get("email", set())
        found = [h for h in hits(kbcommon.LEAK_EMAIL, authored(), strip_urls=True) if not kbcommon.EMAIL_OK.search(h[2])
                 and h[2].lower() not in allow]
        assert not found, "e-mail addresses outside example.com/noreply (placeholders only):\n" + fmt(found)

    def test_git_remotes_are_urls_not_email(self):
        assert URL_RX.sub("", "clone git@gitlab.com:group/kb.git here").split() == ["clone", "here"]
        assert URL_RX.sub("", "ssh://git@gitlab.com/group/kb.git") == ""
        assert URL_RX.sub("", "run `ssh -T git@gitlab.com` once") == "run `` once"
        for mail in ("jan.git@corp.example.com", "git@corp.example.com wrote", "mail git@corp.example.com: hi"):
            assert re.search(r"@corp\.example\.com", URL_RX.sub("", mail)), mail

    def test_no_unexpected_guids_in_prose(self):
        allow = allowlist().get("guid", set())
        md = [f for f in authored() if f.endswith(".md")]
        found = [h for h in hits(kbcommon.LEAK_GUID, md, strip_urls=True)
                 if not kbcommon.GUID_OK.fullmatch(h[2].lower()) and h[2].lower() not in allow]
        assert not found, "GUIDs in prose that are neither placeholders nor reviewed public ids " \
                                "(tenant/object ids leak; add public ones to _tools/tests_allowlist.txt with a reason):\n" + fmt(found)

    def test_no_forbidden_files_tracked(self):
        rx = re.compile(r"(^|/)(_cache|_private|__pycache__)/|(^|/)\.env(\.|$)|\.(pem|key|pfx|p12|kdbx|tmp)$|(^|/)id_(rsa|ed25519)|(^|/)\.DS_Store$")
        bad = [f for f in tracked() if rx.search(f)]
        assert not bad, "files that must not be committed:\n  " + "\n  ".join(bad)

    def test_no_oversized_files(self):
        big = [(f, os.path.getsize(os.path.join(KB, f))) for f in tracked() if os.path.getsize(os.path.join(KB, f)) > MAX_BYTES]
        assert not big, f"files over {MAX_BYTES // 2**20} MB:\n" + "\n".join(f"  {f}: {s} bytes" for f, s in big)
