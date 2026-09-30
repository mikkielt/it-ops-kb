"""kbid.py source ids (`python3 _tools/tests.py` runs them with every other test module).

TestIds: kbid.py hash source ids are deterministic and normalization-stable; bad ids and answer-id clashes are caught.
"""
import re

import kbid
from conftest import P, text


class TestIds:
    URL ="https://learn.microsoft.com/en-us/windows/security/example"

    def test_hash_id_is_deterministic_and_well_formed(self):
        sid = kbid.source_id(self.URL)
        assert sid == kbid.source_id(self.URL)
        assert re.search(r"^S-[a-z2-7]{8}$", sid)
        assert kbid.is_source_id(sid) and kbid.is_source_id("S100") and not kbid.is_source_id("S-12")
        assert kbid.source_id("https://example.com/") == "S-" + __import__("base64").b32encode(
            __import__("hashlib").sha256(b"https://example.com/").digest()).decode().lower()[:8]

    def test_normalization_equivalences(self):
        same = ["HTTPS://Learn.Microsoft.COM/en-us/windows/security/example", self.URL + "/", self.URL + "#section",
                "https://learn.microsoft.com:443/en-us/windows/security/example", "  " + self.URL + "  ", self.URL + "?"]
        for u in same:
            assert kbid.normalize_url(u) == self.URL, u
        assert kbid.normalize_url("http://Example.com") == "http://example.com/"
        assert kbid.normalize_url("http://example.com:80/a") == "http://example.com/a"
        differ = [self.URL.replace("windows", "Windows"), self.URL + "?view=1", "http://learn.microsoft.com/en-us/windows/security/example",
                  "https://learn.microsoft.com:8443/en-us/windows/security/example", self.URL + "%2F"]
        for u in differ:
            assert kbid.source_id(u) != kbid.source_id(self.URL), u

    def test_check_sources_catches_hand_typed_and_collisions(self):
        ok = [{"id": kbid.source_id(self.URL), "url": self.URL + "/"}, {"id": "S100", "url": self.URL}]
        assert kbid.check_sources(ok) == []
        typed = kbid.check_sources([{"id": "S-abcdefgh", "url": self.URL}])
        assert typed and "does not match its url" in typed[0]
        a, b = "https://example.com/c/266794", "https://example.com/c/514424"  # a real 40-bit collision
        assert kbid.source_id(a) == kbid.source_id(b)
        assert any("collision" in e for e in kbid.check_sources([{"id": kbid.source_id(a), "url": a}, {"id": "S1", "url": b}]))

    def test_id_regexes_accept_both_forms(self):
        text = "fact [DOC S1289, S-k3f7q2zd] and S3 sleep, HTTPS-only"
        assert kbid.SOURCE_ID.findall(text) == ["S1289", "S-k3f7q2zd"], "a cited id; prose like S3 is not one"
        assert kbid.ANY_ID.findall("S1480,S1483: HTTPS-only, S-BAD") == ["S1480", "S1483", "S-BAD"]
        assert sorted(["S-bbbbbbbb", "S1000", "S-aaaaaaaa", "S999"], key=kbid.sort_key) == \
                         ["S999", "S1000", "S-aaaaaaaa", "S-bbbbbbbb"]
        assert [kbid.canonical_id(x) for x in ("s0100", "s-K3F7Q2ZD", "t-ABCDEFGH")] == ["S0100", "S-k3f7q2zd", "T-abcdefgh"]
        assert "TGT-issuance" not in kbid.ANY_ID.findall("[DOC S1480] TGT-issuance SDK-embedded")

    def test_root_prefixes(self):
        """Each root's ids carry its prefix: a hash id is <prefix>-<hash of the url>; legacy ids are public's."""
        tid = kbid.source_id(self.URL, "T")
        assert tid == "T-" + kbid.source_id(self.URL)[2:] and kbid.id_prefix(tid) == "T" and kbid.id_prefix("S100") == "S"
        assert kbid.check_sources([{"id": tid, "url": self.URL}], "T", "team") == []
        assert "not an id of root team" in kbid.check_sources([{"id": kbid.source_id(self.URL), "url": self.URL}], "T", "team")[0]
        assert "not an id of root team" in kbid.check_sources([{"id": "S100", "url": self.URL}], "T", "team")[0]
        assert "not an id of root public" in kbid.check_sources([{"id": tid, "url": self.URL}])[0]

    def test_answer_ids(self):
        assert kbid.answer_id("How does Dataverse sync with an on-prem SQL Server?") == "QK-dataverse-sync-prem-sql-server"
        assert re.search(kbid.QK_ID.pattern, kbid.answer_id("???"))
        ids = kbid.answer_ids("## Q1. a\n## QK-x-y. b\n## QK-x-y. c\n### Q2. no\n## QG1 (no dot)\n")
        assert ids == ["Q1", "QK-x-y", "QK-x-y"]
        real = kbid.answer_ids(text(P("_answers.md")) or "")
        assert len(real) == len(set(real)), "duplicate answer ids in _answers.md"
