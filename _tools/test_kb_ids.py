"""kbid.py source ids (`python3 _tools/tests.py` runs them with every other test module).

TestIds: kbid.py hash source ids are deterministic and normalization-stable; bad ids and answer-id clashes are caught.
TestAddSource: `kbid.py add` writes a converging, id-ordered _sources.csv row that check.py accepts, and refuses
a conflicting row, a bad field and a hash-id collision.
"""
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

import kbcommon
import kbid
from conftest import TOOLS, P, text


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


class TestAddSource:
    """`kbid.py add`: a row written through a CSV writer, converging, refusing a conflict; in a temporary root, never
    this repository's."""
    URL = "https://docs.example.com/print/queues"
    HEADER = "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
    FIELDS = {"--title": 'Queues, "retention"', "--publisher": "corp.example.com", "--licence": "internal",
              "--reuse": "quote"}

    def make_root(self, tmp_path):
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "_root.md").write_text("---\nroot: fixture\nid_prefix: FXT\nvisibility: internal\ndescription: fx\n---\n",
                                       encoding="utf-8", newline="\n")
        for name in ("_answers.md", "_gaps.md", "_conflicts.md"):
            (root / name).write_text("# x\n", encoding="utf-8", newline="\n")
        (root / "_sources.csv").write_text(self.HEADER, encoding="utf-8", newline="\n")
        (root / "_artifacts.csv").write_text("path,source_id,sha256,zip_member\n", encoding="utf-8", newline="\n")
        return root

    def add(self, root, url, *extra, **override):
        """(exit code, stdout, stderr) of `kbid.py add URL` with the standard fields, `override` replacing some
        (keys without the dashes), `extra` flags appended."""
        fields = {**self.FIELDS, **{"--" + k: v for k, v in override.items()}}
        args = [x for kv in fields.items() for x in kv]
        return self.tool(root, "kbid.py", "add", url, *args, *extra, "--root", "fixture")

    def tool(self, root, script, *args):
        env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX")}
        env["KB_ROOTS"] = str(root)
        p = subprocess.run([sys.executable, str(Path(TOOLS) / script), *args], capture_output=True, text=True,
                           encoding="utf-8", env=env, timeout=120)
        return p.returncode, p.stdout, p.stderr

    def rows(self, root):
        with open(root / "_sources.csv", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_add_source_writes_a_row_that_passes_check(self, tmp_path):
        root = self.make_root(tmp_path)
        code, out, err = self.add(root, self.URL + "/", "--version", "v1")
        assert code == 0, err
        sid = kbid.source_id(self.URL, "FXT")
        assert out == sid + "\n"
        rows = self.rows(root)
        assert len(rows) == 1 and rows[0]["id"] == sid and rows[0]["url"] == self.URL + "/"
        assert rows[0]["title"] == 'Queues, "retention"' and rows[0]["reuse"] == "quote" and rows[0]["version_or_date"] == "v1"
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", rows[0]["retrieved_utc"]) and rows[0]["used_in"] == ""
        assert '"Queues, ""retention"""' in (root / "_sources.csv").read_text(encoding="utf-8"), "csv-quoted"
        code, out, err = self.tool(root, "check.py", "--root", "fixture")
        assert code == 0, out + err

    def test_add_source_check_fails_on_a_planted_bad_row(self, tmp_path):
        """The row `add` writes is the one check.py reads: a row whose licence was blanked afterwards fails it."""
        root = self.make_root(tmp_path)
        assert self.add(root, self.URL)[0] == 0
        path = root / "_sources.csv"
        path.write_text(path.read_text(encoding="utf-8").replace(",internal,", ",,"), encoding="utf-8", newline="\n")
        code, out, err = self.tool(root, "check.py", "--root", "fixture")
        assert code == 1 and "has no licence" in out + err

    def test_add_source_converges_and_keeps_id_order(self, tmp_path):
        urls = [f"https://docs.example.com/page/{n}" for n in range(6)]
        root = self.make_root(tmp_path)
        for u in urls:
            assert self.add(root, u)[0] == 0
        assert [r["id"] for r in self.rows(root)] == sorted(kbid.source_id(u, "FXT") for u in urls), \
            "inserted in id order, as kbgit.py fix keeps"
        before = (root / "_sources.csv").read_bytes()
        code, out, err = self.add(root, urls[2] + "#frag")
        assert code == 0 and out == kbid.source_id(urls[2], "FXT") + "\n" and "unchanged" in err
        assert (root / "_sources.csv").read_bytes() == before, "the same row again changes nothing"

    def test_add_source_refuses_a_conflicting_row(self, tmp_path):
        root = self.make_root(tmp_path)
        assert self.add(root, self.URL)[0] == 0
        before = (root / "_sources.csv").read_bytes()
        code, out, err = self.add(root, self.URL, licence="public domain")
        assert code == 2 and out == "" and "refused" in err and "licence" in err, err
        code, out, err = self.add(root, self.URL, "--sha256", "a" * 64)
        assert code == 2 and "artifact_sha256" in err, "a hash the row lacks conflicts when given"
        assert (root / "_sources.csv").read_bytes() == before

    def test_add_source_refuses_bad_fields_and_a_hash_collision(self, tmp_path):
        root = self.make_root(tmp_path)
        before = (root / "_sources.csv").read_bytes()
        for override, msg in [({"reuse": "steal"}, "invalid choice"), ({"licence": "  "}, "--licence is empty"),
                              ({"title": ""}, "--title is empty"), ({"publisher": ""}, "--publisher is empty")]:
            code, out, err = self.add(root, self.URL, **override)
            assert code == 2 and msg in err, (override, err)
        code, out, err = self.add(root, self.URL, "--sha256", "xyz")
        assert code == 2 and "64 hexadecimal" in err
        code, out, err = self.add(root, "ftp://docs.example.com/x")
        assert code == 2 and "not an http(s) url" in err
        assert (root / "_sources.csv").read_bytes() == before
        a, b = "https://example.com/c/266794", "https://example.com/c/514424"  # a real 40-bit collision
        assert self.add(root, a)[0] == 0
        mid = (root / "_sources.csv").read_bytes()
        code, out, err = self.add(root, b)
        assert code == 2 and "hash id" in err and (root / "_sources.csv").read_bytes() == mid

    def test_add_source_reuses_a_legacy_id(self, tmp_path):
        """A url that a row holds under a legacy id gives that id and writes nothing (a copy of a real public row)."""
        real = next(r for r in kbid.read_rows(kbcommon.public()) if re.fullmatch(r"S\d+", r["id"]))
        root = tmp_path / "public"
        root.mkdir()
        (root / "_sources.csv").write_text(kbcommon.csv_text(list(real), [real]), encoding="utf-8", newline="\n")
        fake = kbcommon.Root("public", str(root), "S", "public", "")
        got = kbid.add_source(fake, real["url"], real["title"], real["publisher"], real["licence"], real["reuse"])
        assert got == (real["id"], False)
        assert (root / "_sources.csv").read_text(encoding="utf-8") == kbcommon.csv_text(list(real), [real])
