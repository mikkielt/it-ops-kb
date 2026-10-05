"""The kb's deterministic lookup (`python3 _tools/tests.py` runs them with every other test module).

TestLookup (deterministic retrieval): kbfacts.py parses tag variants and ledger topic markers one way; `rag.py eval` passes
every question of kb/public/_retrieval/lookup_eval.csv (expected article in the pack, right coverage verdict); the kb: hook blocks
a covered question, forwards an uncovered one with the pack, and leaves other prompts alone.
TestFingerprint: the index fingerprint of the kb's files is the per-file stat value, and changes with a file's time or a new file.
TestKbHookRoute, TestRawReadNudge: the kb: hook's routes on planted packs, and the hint on a whole-file read of an article.
test_freshness_note_for_latest_or_unnamed_versions: the `freshness:` line of a pack.
LIVE_DATA_TESTS: the tests that read the repository's live kb or backlog, each with why it holds at any size.
"""
import ast, csv, json, os, re, subprocess, sys
from pathlib import Path

import kb_hook, kbcommon, kbfacts, kbid
from conftest import KB, P, TOOLS, copy_kb, querylog_env, run, text, timeout_s

# the benchmark's false good (agent_bench s8): the pack matched Copilot Studio's "data-loss-prevention (DLP)" words
FALSE_GOOD = "How do I integrate ServiceNow with Intune?"  # ServiceNow is held by a Copilot connector line only
SPREAD_GOOD = "Which Graph API migrates mailboxes, calendars and contacts between tenants?"


class TestLookup:
    def test_e2e_fixture_questions_keep_their_pack(self):
        """The query log's end-to-end scenarios (test_querylog_e2e.py) route real lookups through the real kb: each
        recorded question's verdict and lead article are pinned in fixtures/querylog/e2e.json (`pack`). A kb content
        change that moves one fails here, in the content lane of `tests.py --changed`, instead of only in the
        expensive e2e run it would otherwise break; re-pin it there once the scenario is checked against the change."""
        import kbfacts
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "querylog", "e2e.json"), encoding="utf-8") as f:
            lookups = json.load(f)["lookups"]
        pinned = {n: lk for n, lk in lookups.items() if "pack" in lk}
        assert len(pinned) == len([lk for lk in lookups.values() if "asked" in lk]), "every recorded question is pinned"
        moved = []
        for name, lk in pinned.items():
            p = kbfacts.pack(lk["asked"])
            got = {"verdict": p["verdict"], "lead": (p["paths"] or [None])[0]}
            if got != lk["pack"]:
                moved.append(f"{name}: {lk['asked']!r} pinned {lk['pack']}, now {got}")
        assert not moved, "\n".join(moved)

    def test_search_finds_the_expected_article(self):
        """rag.py search (kb_search): the article that answers each query is in its top 5. The baseline any change to
        the search engine must keep, including prose and, with --index, the root
        ledgers that the pack index does not hold."""
        import rag
        from conftest import Q
        cases = [("pim activation latency", None, False, "entra/pim-and-governance.md"),
                 ("kerberos constrained delegation", None, False, "auth/delegation-kcd-obo.md"),
                 ("adminservice routes", "mecm", False, "mecm/adminservice-routes.csv"),
                 ("bitlocker recovery keys entra device", None, False, "entra/bitlocker-key-deletion.md"),
                 ("dsc what-if dry-run", None, False, "dsc/what-if.md"),
                 ("presidio deanonymize operator", None, False, "privacy/presidio-operators-deanonymize.md"),
                 ("rc4 aes-only DefaultDomainSupportedEncTypes", None, False, "auth/kerberos.md"),
                 ("gap unconfirmed instruction limit", None, True, "_answers.md")]
        for query, domain, index, want in cases:
            paths = [h["path"].replace(os.sep, "/") for h in rag.search(query, 5, domain, index, [])]
            assert Q(want) in paths, f"search {query!r}: {paths}"

    def test_persisted_index_gives_identical_packs(self):
        """The sqlite index, the in-memory postings and a domain subset give the same pack and search, byte for byte;
        the root index files never change a pack (the pack's view equals a store without them); a new fingerprint
        names a new index file."""
        import tempfile, kbfacts
        qs = ["When does NTLMv1 become disabled by default?", "SCCM AdminService Kerberos",
              "what-if US_NPI approximateLastSignInDateTime", "zanzibarquux flibbertigibbet"]
        us = kbfacts.corpus()
        assert any(u.get("root") for u in us) and not any(u.get("root") for u in us[:kbfacts.MemStore(
            "x", us).n_main]), "root index units come last"
        mem = kbfacts.MemStore(kbfacts.fingerprint(), us)
        bare = kbfacts.MemStore(kbfacts.fingerprint(), [u for u in us if not u.get("root")])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kbindex-test.sqlite")
            mem.save(path)
            sql = kbfacts.SqlStore(path)
            saved = kbfacts._STORE[0]
            try:
                out = {}
                for name, st in (("mem", mem), ("sql", sql), ("bare", bare)):
                    kbfacts._STORE[0] = st
                    out[name] = [kbfacts.pack(q)["text"] for q in qs] + [kbfacts.pack("kerberos spn", domain="auth")["text"]]
                    if name != "bare":
                        out[name + "-search"] = [kbfacts.search(q, 8, None, ix) for q in qs for ix in (False, True)]
            finally:
                kbfacts._STORE[0] = saved
                sql.con.close()
        assert out["mem"] == out["sql"]
        assert out["mem"] == out["bare"]
        assert out["mem-search"] == out["sql-search"]
        assert kbfacts.index_path("a" * 40) != kbfacts.index_path("b" * 40)

    def test_tag_grammar_variants_parse_one_way(self):
        import kbfacts
        cases = {
            "[DOC S1208, COMMUNITY S1209]": [("DOC", ["S1208"]), ("COMMUNITY", ["S1209"])],
            "[DER S328,S329: different property; Type has no table]": [("DER", ["S328", "S329"])],
            "[DOC\n  S1347, S1354]": [("DOC", ["S1347", "S1354"])],
            "[DER from S1971, S1970]": [("DER", ["S1971", "S1970"])],
            "[UNK — fetch failed]": [("UNK", [])],
            "[DOC S2126; DOC S-k3f7q2zd; UNK]": [("DOC", ["S2126"]), ("DOC", ["S-k3f7q2zd"]), ("UNK", [])],
        }
        for tag, want in cases.items():
            assert [(p["kind"], p["ids"]) for p in kbfacts.parse_tag(tag)] == want, tag
        assert kbfacts.parse_tag("[DER S100: how; why]")[0]["note"] == "how; why"

    def test_decision_tag_parses_one_way(self):
        """`[DECISION D-<8 base32>]` and `[DECISION D-<8 base32>: note]` are tags of their own kind: the id is the
        part's `decision`, never one of its source `ids`; a tag with no valid id parses with an empty one."""
        import kbfacts
        assert "DECISION" in kbfacts.KINDS
        part = kbfacts.parse_tag("[DECISION D-k3f7q2zd]")[0]
        assert (part["kind"], part["ids"], part["decision"], part["note"]) == ("DECISION", [], "D-k3f7q2zd", "")
        part = kbfacts.parse_tag("[DECISION D-k3f7q2zd: chosen for the pilot; revisit in 2027]")[0]
        assert (part["decision"], part["note"]) == ("D-k3f7q2zd", "chosen for the pilot; revisit in 2027")
        parts = kbfacts.parse_tag("[DOC S1208; DECISION D-k3f7q2zd, DECISION D-aaaaaaab: later]")
        assert [(p["kind"], p["ids"], p.get("decision")) for p in parts] == [
            ("DOC", ["S1208"], None), ("DECISION", [], "D-k3f7q2zd"), ("DECISION", [], "D-aaaaaaab")]
        assert kbfacts.parse_tag("[DECISION\n  D-k3f7q2zd]")[0]["decision"] == "D-k3f7q2zd"
        for bad in ("[DECISION]", "[DECISION D-AAAA]", "[DECISION S1208]", "[DECISION D-k3f7q2zd9]"):  # planted
            assert kbfacts.parse_tag(bad)[0]["decision"] == "", bad
        unit = kbfacts.md_units("public/x/y.md", "- Keep jobs 14 days. [DECISION D-k3f7q2zd]\n")[0]
        assert kbfacts.kinds_of(unit["tags"]) == ["DECISION"]

    def test_decision_tag_is_resolved_by_check(self, tmp_path):
        """check.py resolves each `[DECISION <id>]` to a row of its own root's _decisions.csv: a known id passes; an
        unknown id, a malformed id, no id and another root's id each give one error that names the rule."""
        from test_kb_root import DEC, SID, decision, did, make_root, run as run_tool
        root, other = tmp_path / "team-kb", tmp_path / "other-kb"
        make_root(str(root))
        make_root(str(other), prefix="OTH")
        meta = other / "_root.md"
        meta.write_text(meta.read_text(encoding="utf-8").replace("root: fixture", "root: other"), encoding="utf-8", newline="\n")
        for r in (root, other):  # check.py wants the artifacts ledger
            (r / "_artifacts.csv").write_text("path,source_id,sha256\n", encoding="utf-8", newline="\n")
        kbcommon.write_csv(str(root / DEC), kbcommon.DECISION_COLS, [decision(0)])
        kbcommon.write_csv(str(other / DEC), kbcommon.DECISION_COLS, [decision(1)])
        art = root / "print" / "queues.md"
        base = art.read_text(encoding="utf-8")

        def errors(*tags):
            art.write_text(base + "".join(f"- A decided fact. {t}\n" for t in tags), encoding="utf-8", newline="\n")
            code, out = run_tool("check.py", "--root", "fixture", roots=os.pathsep.join([str(root), str(other)]))
            assert "Traceback" not in out, out[-800:]
            return code, [ln for ln in out.splitlines() if ln.startswith("ERROR")]

        assert errors(f"[DECISION {did(0)}]", f"[DECISION {did(0)}: why]", f"[DOC {SID}; DECISION {did(0)}]") == (0, [])
        for tag, rule in ((f"[DECISION {did(5)}]", f"cites unknown decision {did(5)}"),
                          (f"[DECISION {did(1)}]", f"cites decision {did(1)} of root other; a root cites only its own"),
                          ("[DECISION D-AAAA]", "naming 'D-AAAA', not a decision id"),
                          ("[DECISION]", "has a DECISION tag with no decision id"),
                          (f"[DOC {SID}; DECISION {did(7)}]", f"cites unknown decision {did(7)}")):
            code, found = errors(tag)
            assert code == 1 and len(found) == 1 and rule in found[0] and "fixture/print/queues.md" in found[0], (tag, found)

    def test_code_pointer_extensionless_script(self):
        import kbfacts
        ptr = lambda tag: kbfacts.code_pointer(kbfacts.parse_tag(tag)[0])  # noqa: E731
        assert ptr("[CODE S1: src/adr-new#newid]") == ("src/adr-new", "newid")
        assert ptr("[CODE S1: bin/tools/deploy#L10-L20]") == ("bin/tools/deploy", "L10-L20")
        assert ptr("[CODE S1: src/x.py#f]") == ("src/x.py", "f")
        for tag in ("[CODE S1: adr-new#newid]",  # a plain word, no directory and no extension
                    "[CODE S1: src/#newid]",  # a directory
                    "[CODE S1: https://example.com/docs/page#frag]",  # a url
                    "[CODE S1: see the script]"):
            assert ptr(tag) is None, tag

    def test_code_pointer_rejects_prose_and_hosts(self):
        import kbfacts
        ptr = lambda tag: kbfacts.code_pointer(kbfacts.parse_tag(tag)[0])  # noqa: E731
        for tag in ("[CODE S1: and/or#x]", "[CODE S1: either/or#x]", "[CODE S1: his/her#x]",  # prose pairs
                    "[CODE S1: github.com/o/r/blob/main/x#y]", "[CODE S1: www.example.com/-/b#y]"):  # a url, no scheme
            assert ptr(tag) is None, tag
        # the first acceptable pointer of the note wins, past a rejected one
        assert ptr("[CODE S1: and/or#x, then src/foo.py#sym]") == ("src/foo.py", "sym")
        # real pointers: an extensionless script, a dotted directory, a code file whose name ends like a tld
        for tag, want in (("[CODE S1: src/adr-new#newid]", ("src/adr-new", "newid")),
                          ("[CODE S1: .github/workflows/kb.yml#job]", (".github/workflows/kb.yml", "job")),
                          ("[CODE S1: src/Foo.Bar/x.cs#y]", ("src/Foo.Bar/x.cs", "y")),
                          ("[CODE S1: a/b/c.cs#Sym]", ("a/b/c.cs", "Sym")),
                          ("[CODE S1: docs/guide/setup.md#step]", ("docs/guide/setup.md", "step")),
                          ("[CODE S1: app.py#main]", ("app.py", "main")),
                          ("[CODE S1: tools/run.sh#go]", ("tools/run.sh", "go")),
                          ("[CODE S1: lib/x.pl#f]", ("lib/x.pl", "f")),
                          ("[CODE S1: src/and/or.py#f]", ("src/and/or.py", "f"))):
            assert ptr(tag) == want, tag

    def test_code_kind_pointer_and_pinned_sources(self):
        import kbfacts
        part = kbfacts.parse_tag("[CODE S-abcdefgh: crates/ruff_linter/src/settings/mod.rs#DEFAULT_SELECTORS]")[0]
        assert (part["kind"], part["ids"]) == ("CODE", ["S-abcdefgh"])
        assert kbfacts.code_pointer(part) == ("crates/ruff_linter/src/settings/mod.rs", "DEFAULT_SELECTORS")
        assert kbfacts.code_pointer(kbfacts.parse_tag("[CODE S100: src/x.py#L10-L20]")[0]) == ("src/x.py", "L10-L20")
        assert kbfacts.code_pointer(kbfacts.parse_tag("[CODE S100]")[0]) is None
        assert kbfacts.parse_tag("[DOC S1, CODE S2: a.py#f]")[1]["kind"] == "CODE"
        pinned = kbfacts.pinned_source
        assert pinned({"url": "https://raw.githubusercontent.com/astral-sh/ruff/0.16.9/crates/x.rs"})
        assert pinned({"url": "https://raw.githubusercontent.com/python/peps/ff16962a22fdc5e2095e0cbc5c243ea76e34fb52/peps/pep-0596.rst"})
        assert pinned({"url": "https://github.com/o/r/blob/v3.8.0/src/a.py"})
        assert pinned({"url": "https://gitlab.com/g/p/-/raw/v1.2/a.py"})
        assert pinned({"url": "https://gitlab.corp.example.com/ops/deploy/-/raw/" + "ab12" * 10 + "/src/a.py"})  # self-managed
        assert not pinned({"url": "https://gitlab.corp.example.com/ops/deploy/-/raw/main/src/a.py"})
        assert not pinned({"url": "https://git.corp.example.com/ops/deploy/raw/" + "ab12" * 10 + "/src/a.py"})  # no /-/
        assert pinned({"url": "https://example.com/tool.zip", "artifact_sha256": "ab" * 32})
        assert not pinned({"url": "https://raw.githubusercontent.com/o/r/main/a.py"})
        assert not pinned({"url": "https://raw.githubusercontent.com/o/r/refs/heads/release/a.py"})
        assert not pinned({"url": "https://github.com/o/r/blob/master/a.py"})
        assert not pinned({"url": "https://learn.microsoft.com/en-us/powershell/module/x"})

    def test_contract_sources_are_not_code_candidates(self):
        import kbfacts
        contract = kbfacts.contract_source
        for url in ("https://raw.githubusercontent.com/PowerShell/DSC/abc/schemas/v3/bundled/config/document.json",
                    "https://raw.githubusercontent.com/microsoftgraph/msgraph-metadata/abc/clean_v10_metadata/cleanMetadata.xml",
                    "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/abc/schema/2026-07-28/schema.ts",
                    "https://api.msrc.microsoft.com/cvrf/v3.0/swagger/v3/swagger.json",
                    "https://raw.githubusercontent.com/a2aproject/A2A/abc/specification/a2a.proto",
                    "https://raw.githubusercontent.com/open-telemetry/c/v0.161.0/receiver/filelogreceiver/metadata.yaml"):
            assert contract({"url": url}), url
        for url in ("https://raw.githubusercontent.com/PowerShell/DSC/abc/schemas/schemas.config.yaml",
                    "https://raw.githubusercontent.com/PowerShell/DSC/abc/lib/dsc-lib/src/configure/mod.rs",
                    "https://raw.githubusercontent.com/o/r/abc/presidio_analyzer/conf/example_recognizers.yaml",
                    "https://raw.githubusercontent.com/o/r/abc/src/schema_utils.py",
                    "https://gitlab.com/g/p/-/raw/abc/shells/abstract.go"):
            assert not contract({"url": url}), url

    def test_lint_checks_code_and_snippets(self, tmp_path):
        d = copy_kb(str(tmp_path / "kb"))
        with open(os.path.join(d, P("_sources.csv")), "a", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows([
                ["S-zzzzzzz2", "https://raw.githubusercontent.com/o/r/main/a.py", "x", "x", "MIT", "2026-09-27", "", "", "", ""],
                ["S-zzzzzzz3", "https://raw.githubusercontent.com/o/r/v1.0/a.py", "x", "x", "MIT", "2026-09-27", "", "", "", ""]])
        body = ("\n- Unpinned. [CODE S-zzzzzzz2: a.py#f]\n- No pointer. [CODE S-zzzzzzz3]\n- Pinned. [CODE S-zzzzzzz3: a.py#f]\n"
                "- SNIPPET: list things; context: PowerShell 7.4; checked: no [DER S-zzzzzzz3: from a.py]\n\n```powershell\nGet-Thing\n```\n"
                "- SNIPPET: no block or context; checked: no [DOC S-zzzzzzz3]\n"
                "- SNIPPET: bad json; context: any; checked: syntax [DOC S-zzzzzzz3]\n```json\n{\"a\": }\n```\n"
                "- SNIPPET: unbacked; context: any; checked: maybe [UNK]\n```json\n{}\n```\n")
        with open(os.path.join(d, P("auth/kerberos.md")), "a", encoding="utf-8", newline="\n") as f:
            f.write(body)
        p = subprocess.run([sys.executable, os.path.join(d, ".claude", "skills", "kb-verify", "lint.py"), "auth/kerberos"],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        out = p.stdout
        assert "CODE cites S-zzzzzzz2, which is not pinned" in out and "S-zzzzzzz3, which is not pinned" not in out, out
        assert out.count("CODE tag without a path#symbol pointer") == 1, out
        assert "SNIPPET without `context:`: 'SNIPPET: no block or context" in out
        assert "SNIPPET not followed by a fenced code block: 'SNIPPET: no block or context" in out
        assert "its json block does not parse" in out
        assert "SNIPPET without `checked: no|syntax|run`: 'SNIPPET: unbacked" in out
        assert "SNIPPET without an evidence tag (DOC, CODE, DER or COMMUNITY): 'SNIPPET: unbacked" in out
        assert "list things" not in out, "a well-formed snippet has no findings"
        c = subprocess.run([sys.executable, os.path.join(d, ".claude", "skills", "kb-verify", "lint.py"), "--candidates",
                            "auth/kerberos"], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert c.returncode == 0 and "code_candidates=" in c.stdout, c.stdout + c.stderr
        assert "Unpinned." not in c.stdout, "a CODE fact is no longer a candidate"

    def test_lint_observed_run_rule(self, tmp_path):
        """A DER fact resting on a run or probe names the version that ran (kb/_self/content-rules.md, Facts and tags)."""
        d = copy_kb(str(tmp_path / "kb"))
        path = os.path.join(d, P("auth/kerberos.md"))
        text = open(path, encoding="utf-8").read()
        assert "\n## Facts\n" in text
        body = ("- Probe A: observed on PL-LT-00123 in a headless session, the hook was in no job. [DER S-zzzzzzz3: the run]\n"
                "- Probe B: observed on Claude Code 2.1.285 on PL-LT-00123, headless, the hook was in no job. [DER S-zzzzzzz3: the run]\n"
                "- Probe C: in the headless runs of version 3 the child outlived the parent. [DER S-zzzzzzz3: the run]\n"
                "- Probe D: a run without an observed failure needs no new mechanism. [DER S-zzzzzzz3: policy]\n"
                "- Probe E: a `-c` probe tells the runtime from an alias. [DER S-zzzzzzz3: command names]\n")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text.replace("\n## Facts\n", "\n## Facts\n" + body, 1))
        p = subprocess.run([sys.executable, os.path.join(d, ".claude", "skills", "kb-verify", "lint.py"), "auth/kerberos"],
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout_s(120))
        hits = [ln for ln in p.stdout.splitlines() if "rests on a run or probe but names no version" in ln]
        assert len(hits) == 1 and hits[0].startswith("WARN") and "Probe A" in hits[0], p.stdout

    def test_lint_observed_run_needs_a_real_version_and_a_real_run(self):
        """A measurement (2.5 s, TLS 1.2) is no version, and 'in the long run' or 'in a pipeline run' is no run of ours."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "kb_verify_lint", os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py"))
        lint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lint)
        der = {"DER"}
        warns = [
            "- Observed on PL-LT-00123: the wait took 2.5 s. [DER S1]",
            "- Observed on PL-LT-00123: TLS 1.2 was negotiated. [DER S1]",
            "- Observed on PL-LT-00123 over TLS version 1.2, the wait took about 2.5. [DER S1]",
            "- Measured with 120 devices: the sync took 3.2 % longer. [DER S1]",
            "- In the headless runs the child outlived the parent. [DER S1]",
            "- In two runs the child outlived the parent. [DER S1]"]
        quiet = [
            "- In the long run the cache wins. [DER S1]",
            "- In a pipeline run the job reads the variable. [DER S1]",
            "- Observed on Claude Code 2.1.285 the wait took 2.5 s. [DER S1]",
            "- Observed on PowerShell 7.4: the call failed. [DER S1]",
            "- Measured with git 2.43 and TLS 1.2: 2.5 s. [DER S1]",
            "- Observed on version 3: the call failed. [DER S1]",
            "- In the headless runs of v3.3 the child outlived the parent. [DER S1]"]
        for item in warns:
            assert lint.unversioned_run(item, der), item
        for item in quiet:
            assert not lint.unversioned_run(item, der), item
        assert not lint.unversioned_run("- Observed on PL-LT-00123: the wait took 2.5 s. [DOC S1]", {"DOC"}), "DER facts only"

    def test_ledger_topic_markers_link_entries(self):
        import kbfacts
        from conftest import Q
        e = kbfacts.link_entries([{"file": Q("_gaps.md"), "line": 1, "end": 1, "section": "x", "text": "a gap (topic: auth/kerberos)"}])[0]
        assert e["explicit"] == [Q("auth/kerberos")], "a ledger's topic marker names a topic of its own root"
        rows = {r["topic"]: r for r in kbfacts.audit("agents/shared-ner-service")}
        assert rows[Q("agents/shared-ner-service")]["gaps"], "shared-ner-service's named gap entries are not linked"

    def test_alias_and_signal_tables(self):
        import kbfacts
        for name, cols in (("aliases.csv", ["term", "canonical"]), ("signals.csv", ["signal", "topic"])):
            with open(kbcommon.data_path(name, shared=name == "aliases.csv"), encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            assert rows[0] == cols, name
            keys = [r[0].lower() for r in rows[1:]]
            assert len(keys) == len(set(keys)), f"{name}: duplicate {cols[0]}"
            for r in rows[1:]:
                assert len(r) == 2, f"{name}: {r}"
                assert r[0].strip() and r[1].strip(), f"{name}: {r}"
        topics = set(kbfacts.topic_files())
        bad = [r["signal"] for root, r in kbfacts.data_rows("signals.csv") if kbcommon.qualify(root, r["topic"]) not in topics]
        assert not bad, f"signals.csv names topics that do not exist in its root: {bad}"
        for r in csv.DictReader(open(kbcommon.data_path("aliases.csv", shared=True), encoding="utf-8")):
            assert r["term"] == r["term"].lower().strip(), "aliases.csv terms are lowercase"
        assert {"last", "sign", "npi"} <= set(kbfacts.terms("approximateLastSignInDateTime US_NPI")), \
                        "compound identifiers are also indexed as their parts"
        assert "npi" not in kbfacts.key_terms("US_NPI"), "parts never count as key words"
        us = kbfacts.corpus()
        assert any(u.get("code") for u in us), "fenced code blocks are searchable"
        assert any(not u["tags"] and u["path"].endswith(".csv") for u in us), "untagged data rows are searchable"
        assert len(kbfacts.units("ad/ldap-paging-filters")) == len([u for u in kbfacts.units("ad/ldap-paging-filters") if u["tags"]]), \
                         "fact counts (units) never include untagged content"
        clipped = kbfacts.clip("x " * 300 + "[DOC S100]", 420)
        assert clipped.endswith("[DOC S100]"), "a cut fact keeps its tag visible"
        extra, variants = kbfacts.expand("SCCM AdminService")
        assert "configmgr" in extra
        assert "configmgr" not in kbfacts.key_terms("SCCM AdminService"), "an expansion is never a key word"
        assert ("mecm",) in variants["sccm"]

    def test_doc2query_expansions(self):
        """expansions.csv is well-formed, and its words only rank facts: KB_DOC2QUERY=0 turns them off."""
        import kbfacts
        path = kbcommon.data_path("doc2query/expansions.csv")
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["key", "question"]
        assert all(len(r) == 2 and re.fullmatch(r"[0-9a-f]{12}", r[0]) and r[1].strip() for r in rows[1:])
        assert kbfacts.fact_key("a  b\n c") == kbfacts.fact_key("a b c"), "keys ignore whitespace"
        code = ("import os, sys; os.environ['KB_DOC2QUERY'] = '0'; sys.path.insert(0, {!r}); import kbfacts; "
                "sys.exit(len(kbfacts.expansions()))").format(TOOLS)
        assert subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0

    def test_lookup_eval_ids_unique(self):
        """Eval ids are EV-<slug> of the question (kbid.eval_id), so parallel writers converge instead of colliding.
        Two different questions with one slug: lengthen the newer id by hand (EV-<slug>-2)."""
        with open(kbcommon.data_path("lookup_eval.csv"), encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        ids = [r["id"] for r in rows]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        assert not dup, f"duplicate lookup_eval.csv ids: {dup}"
        for r in rows:
            assert re.search(kbid.EV_ID.pattern + r"$", r["id"])
            assert r["id"] == kbid.eval_id(r["question"]) or re.fullmatch(re.escape(kbid.eval_id(r["question"])) + r"-\d+", r["id"]), \
                            f"{r['id']}: not the slug of its question ({kbid.eval_id(r['question'])})"

    def test_doc2query_no_stale_keys(self):
        code, out = run(os.path.join(TOOLS, "doc2query.py"), "stale")
        assert code == 0, "expansion keys of reworded or removed facts; run python3 _tools/doc2query.py prune\n" + out[-1500:]

    def test_lookup_eval_passes(self):
        code, out = run(os.path.join(TOOLS, "rag.py"), "eval")
        assert code == 0, out[-3000:]

    def test_kb_ask_routes(self, tmp_path):
        def ask(q, *flags):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_ask.py"), *flags, q], capture_output=True,
                               text=True, encoding="utf-8", cwd=KB, timeout=timeout_s(60), env=querylog_env(tmp_path))
            return p.returncode, p.stdout, p.stderr
        bitlocker = "Does deleting an Entra device also delete its BitLocker recovery keys?"
        code, out, err = ask(bitlocker, "--route")
        assert code == 0 and out.startswith("kind=good verdict=good parts=1 model=haiku"), out + err
        code, out, _ = ask("What is the maximum email attachment size?", "--route")  # weak (lookup eval)
        assert out.startswith("kind=split") and "model=sonnet" in out and "route: split" in out, out
        code, out, _ = ask("What is the Intel Wi-Fi Roaming Aggressiveness setting?", "--route")  # none
        assert out.startswith("kind=web") and "model=sonnet" in out and "route: web" in out, out
        assert "model=opus" in ask("Intel Wi-Fi roaming", "--route", "--model", "opus")[1]
        assert "entra/bitlocker-key-deletion.md:" in ask(bitlocker, "--no-model")[1], "a good pack without a model"
        # counts and 'who cites' go to the audit and source tools, never to a model
        assert ask("How many intune articles are partial?", "--route")[1].startswith("kind=tool")
        # 'complete', not 'partial': the audit must list rows however many intune articles are still partial
        out = ask("How many intune articles in the kb have status complete?")[1]
        assert out.startswith("| path | status |") and "intune/" in out and "articles=" in out, out
        assert "auth/kerberos.md:" in ask("Which files cite S1216?")[1]
        assert ask("Which articles cover BitLocker recovery key escrow?", "--route")[1].startswith("kind=good")
        # several parts: one pack each
        out = ask("(1) default Windows LAPS password length; (2) the Delivery Optimization peer-to-peer port", "--route")[1]
        assert "parts=2" in out and "part 2: the Delivery Optimization peer-to-peer port" in out, out
        assert "parts=2" in ask("What is the LAPS password length? Which port does Delivery Optimization use?",
                                "--route")[1]
        out = ask("What is the default Windows LAPS password length? Answer from the kb with citation.", "--route")[1]
        assert out.startswith("kind=good") and "parts=1" in out, "an instruction sentence is not a part: " + out

    def test_kb_ask_without_claude_prints_the_evidence(self, tmp_path):
        env = querylog_env(tmp_path, base={"PATH": os.path.dirname(sys.executable)})
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_ask.py"), "What is the default Windows LAPS password length?"],
                           capture_output=True, text=True, encoding="utf-8", cwd=KB, timeout=timeout_s(60), env=env)
        assert p.returncode == 2 and p.stdout.startswith("coverage: good") and "windows/laps.md:" in p.stdout, p.stdout + p.stderr

    def test_kb_hook(self, tmp_path):
        def hook(prompt):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps({"prompt": prompt}),
                               capture_output=True, text=True, encoding="utf-8", cwd=KB, timeout=timeout_s(60),
                               env=querylog_env(tmp_path))
            assert p.returncode == 0, p.stderr
            return json.loads(p.stdout) if p.stdout.strip() else None
        assert hook("fix the build please") is None
        covered = hook("kb: Does deleting an Entra device also delete its BitLocker recovery keys?")
        assert covered["decision"] == "block"
        assert "entra/bitlocker-key-deletion.md:" in covered["reason"]
        assert covered["reason"].startswith("coverage: good")
        missing = hook("kb: What is the Intel Wi-Fi Roaming Aggressiveness setting?")
        assert "decision" not in missing
        line = missing["hookSpecificOutput"]["additionalContext"]
        assert "route: web" in line and "kb lacks: " in line and "Roaming" in line, line
        assert "live docs, not in the kb" in line and "\n## " not in line, "coverage none: the differential, no fact lines"
        p = subprocess.run([sys.executable, "-c", "import sys, kb_hook; kb_hook.answer('fix the build'); "
                            "sys.exit('kbfacts' in sys.modules)"], cwd=TOOLS, capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert p.returncode == 0, "a prompt without kb: must return before kbfacts is loaded"
        forward = hook("kb+: Does deleting an Entra device also delete its BitLocker recovery keys?")
        assert forward["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        # a good pack whose lead article never names the product asked about (a false good) goes to the model
        flagged = hook("kb: " + FALSE_GOOD)
        assert "decision" not in flagged, "a good pack with a check: line must not be answered without the model"
        ctx = flagged["hookSpecificOutput"]["additionalContext"]
        assert "coverage: good" in ctx and "\ncheck: " in ctx and "ServiceNow" in ctx, ctx[:400]

    def test_spread_key_words_get_a_check_line(self):
        # no product named: a tenant fact and a mailbox fact make a `good`, but no fact holds half the key words
        res = kbfacts.pack(SPREAD_GOOD)
        assert res["verdict"] == "good" and res["spread"] and not res["unmatched"], (res["verdict"], res["spread"])
        assert res["text"].splitlines()[1].startswith("check: no single fact holds half the key words"), res["text"][:300]
        flagged = kb_hook.answer("kb: " + SPREAD_GOOD)
        assert "decision" not in flagged and "\ncheck: " in flagged["hookSpecificOutput"]["additionalContext"]
        # no true `good` of the eval set gets it
        for row in csv.DictReader(open(kbcommon.data_path("lookup_eval.csv"), encoding="utf-8")):
            if row["expect_verdict"] == "good":
                assert not kbfacts.pack(row["question"])["spread"], row["id"]

    def test_false_good_gets_a_check_line(self):
        res = kbfacts.pack(FALSE_GOOD)
        assert res["verdict"] == "good" and res["unmatched"] == ["servicenow"], (res["verdict"], res["unmatched"])
        assert res["text"].splitlines()[1].startswith("check: ") and "never mentions ServiceNow" in res["text"]
        # the names an article holds only in its title or applies_to (SQL Server for sp_getapplock) count as held,
        # and two-letter names (AV, PC) are never flagged
        for q in ("What does sp_getapplock do in SQL Server and what lock modes does it take?",
                  "Does deleting an Entra device also delete its BitLocker recovery keys?"):
            res = kbfacts.pack(q)
            assert res["verdict"] == "good" and not res["unmatched"] and "\ncheck: " not in res["text"], (q, res["unmatched"])

    def test_common_words_need_one_fact_that_holds_them_all(self):
        # every word common, none naming anything: key words spread over unrelated facts are no answer
        for q in ("email attachment size", "remote desktop gateway ports", "mailbox size limit",
                  "How do I migrate user mailboxes between tenants?", "What is the maximum email attachment size?"):
            assert kbfacts.pack(q)["verdict"] == "weak", q
        # one fact holding every key word stays good (Battery health in endpoint analytics)
        assert kbfacts.pack("battery health report")["verdict"] == "good"
        # a specific word lets the key words spread: the article a word is about (ruff), the kb's brand spelling of a
        # lowercase word (cmpivot -> CMPivot, bitlocker -> BitLocker), an identifier (list/get), a product alias (dsc)
        for q in ("ruff default rules", "cmpivot query timeout", "bitlocker recovery key escrow", "prompts list/get",
                  "Where does dsc look for its policy settings file on Windows?"):
            assert kbfacts.pack(q)["verdict"] == "good", q

    def test_pack_number_with_unit_suffix_is_good(self):
        # a number joined to a unit by a hyphen (1.5-second, 30-day) is also indexed as the number, so a question
        # that writes it apart (1.5 seconds) matches the fact; its dot parts (1, 5) alone never did
        assert "1.5" in kbfacts.terms("a 1.5-second budget") and "30" in kbfacts.terms("a 30-day window")
        assert "1.5" not in kbfacts.key_terms("a 1.5-second budget"), "parts never count as key words"
        res = kbfacts.pack("SessionEnd hook input fields reason budget 1.5 seconds")
        assert res["verdict"] == "good" and "1.5" not in res["lacks"], (res["verdict"], res["lacks"])
        assert "public/claude/hooks.md:64 " in res["text"], res["text"]

    def test_off_domain_product_is_none(self):
        # a rare name no printable line holds: the subject is another product the kb only mentions in passing
        for q in ("How do I configure VMware Horizon instant clones?", "How do I deploy SAP GUI to Windows clients?",
                  "Purview endpoint DLP onboarding requirements for Windows devices",
                  "What ports does VMware Horizon Connection Server use?", "What ServiceNow roles can approve change requests?"):
            res = kbfacts.pack(q)
            assert res["verdict"] == "none" and res["text"].splitlines()[1].startswith("The kb does not cover"), q
        # a longer unknown name among well-matched words is the subject too (the AV/PC exemption is for abbreviations)
        assert kbfacts.pack("What does the NinjaOne agent collect from Windows devices?")["verdict"] == "none"
        # a common name missing from the answer lines (API, in the Presidio REST facts) is not a subject
        assert kbfacts.pack("Does the Presidio analyzer REST API require authentication?")["verdict"] == "good"


FINGERPRINT_CHECK = r"""
import hashlib, json, os, sys, time
import kbcommon, kbfacts

def reference():
    # the fingerprint as it was computed before kb_entries: os.walk, then one os.stat per file
    h = hashlib.sha1(f"{kbfacts.INDEX_VERSION}|{os.environ.get('KB_DOC2QUERY', '')}".encode())
    rels = []
    for r in kbcommon.roots():
        for root, dirs, files in os.walk(r.path):
            dirs[:] = sorted(d for d in dirs if d not in kbfacts.SKIP_DIRS and not d.startswith("."))
            if root == r.path:
                continue
            rels += [kbcommon.qualify(r, os.path.relpath(os.path.join(root, f), r.path)) for f in sorted(files)
                     if f.endswith((".md", ".csv"))]
    extra = [*kbfacts.root_files((kbcommon.SOURCES,)), *kbfacts.index_files(), *kbfacts.alias_files(),
             *kbfacts.data_files("signals.csv"), *kbfacts.data_files("doc2query/expansions.csv"),
             os.path.join(kbfacts.TOOLS, "kbfacts.py"), os.path.join(kbfacts.TOOLS, "kbid.py"),
             os.pathsep.join(r.path for r in kbcommon.roots())]
    for rel in rels + extra:
        try:
            st = os.stat(kbcommon.path_of(rel))
            h.update(f"{rel}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
        except OSError:
            h.update(f"{rel}\0-\n".encode())
    return h.hexdigest()

def now():
    kbfacts._FP[:] = [0.0, None]
    return kbfacts.fingerprint()

root = os.environ["KB_ROOTS"]
art = os.path.join(root, "print", "queues.md")
out = {"files": list(kbfacts.kb_files()), "first": (now(), reference())}
st = os.stat(art)
os.utime(art, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))  # the time alone: the size is the same
out["touched"] = (now(), reference())
os.makedirs(os.path.join(root, "print", "deep"))
with open(os.path.join(root, "print", "deep", "b.csv"), "w", encoding="utf-8", newline="\n") as f:
    f.write("a,b\n1,2\n")
out["added"] = (now(), reference())
print(json.dumps(out))
"""


class TestFingerprint:
    def test_the_listing_gives_the_per_file_stat_value(self, tmp_path):
        """fingerprint() reads the domain files' times and sizes from the directory listing (kb_entries), yet gives
        the value one os.stat per file gave; a change of a file's time alone, and a new file in a new directory, give
        a new value (planted: a fingerprint that missed either would equal the one before)."""
        from test_kb_root import make_root
        root = str(tmp_path / "team-kb")
        make_root(root)
        env = {**os.environ, "KB_ROOTS": root, "KB_INDEX": "0"}
        env.pop("KB_DOC2QUERY", None)
        p = subprocess.run([sys.executable, "-c", FINGERPRINT_CHECK], cwd=TOOLS, capture_output=True, text=True,
                           encoding="utf-8", env=env, timeout=120)
        assert p.returncode == 0, p.stderr
        out = json.loads(p.stdout)
        assert "fixture/print/queues.md" in out["files"] and any(f.startswith("public/") for f in out["files"])
        assert not any(f.startswith("fixture/_") for f in out["files"]), "a root's own files are ledgers"
        for step in ("first", "touched", "added"):
            got, want = out[step]
            assert got == want, step
        assert len({out[s][0] for s in ("first", "touched", "added")}) == 3, out


class TestKbHookRoute:
    """kb_hook.respond on planted packs: a route hands the model the differential; a clean good pack does not."""
    INSTRUCTION = "live docs, not in the kb"
    FACTS = ["", "## public/x/a.md  A  [complete, retrieved 2026-09-27]"] + [
        f"- public/x/a.md:{i} fact number {i} with words to fill a line. [DOC S1]" for i in range(1, 400)]

    def planted(self, monkeypatch, verdict, route, head, facts=True, **extra):
        text = "\n".join(head + (self.FACTS if facts else []))
        res = {"verdict": verdict, "route": route, "has": ["a"], "lacks": ["b"], "missing": [], "unmatched": [],
               "spread": None, "paths": ["public/x/a.md"], "text": text}
        monkeypatch.setattr(kbfacts, "pack", lambda question: dict(res, **extra))
        return res

    def test_web_has_the_instruction_and_no_fact_lines(self, monkeypatch):
        head = ["coverage: none; not in the kb: b", kbfacts.NONE_SENTENCE, "route: web", "kb has: a", "kb lacks: b"]
        self.planted(monkeypatch, "none", "web", head)
        out, row = kb_hook.respond("kb: a b")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "decision" not in out and row["answered"] is False
        assert self.INSTRUCTION in ctx and "never fill it from memory" in ctx and "State what it has and lacks" in ctx
        assert "route: web\nkb has: a\nkb lacks: b" in ctx and "fact number" not in ctx and "\n## " not in ctx
        assert kbfacts.NONE_SENTENCE not in ctx and len(ctx) < 10000, len(ctx)

    def test_split_holds_the_pack_within_the_limit(self, monkeypatch):
        head = ["coverage: weak (best article matches 1 of 2 key words: a)", "route: split", "kb has: a", "kb lacks: b"]
        res = self.planted(monkeypatch, "weak", "split", head)
        assert len(res["text"]) > 10000, "the planted pack must be too long for the limit"
        for prefix in ("kb:", "kb+:"):
            ctx = kb_hook.respond(f"{prefix} a b")[0]["hookSpecificOutput"]["additionalContext"]
            assert self.INSTRUCTION in ctx and "Answer what it has from the pack below with path:line" in ctx, prefix
            assert "route: split\nkb has: a\nkb lacks: b\n" in ctx and "fact number 1 " in ctx, prefix
            assert "check: line" not in ctx and len(ctx) < 10000, (prefix, len(ctx))

    def test_flagged_good_is_split_and_says_what_a_failed_check_means(self, monkeypatch):
        head = ["coverage: good", "check: public/x/a.md never mentions B; the facts may be about something related.",
                "route: split", "kb has: a", "kb lacks: -"]
        self.planted(monkeypatch, "good", "split", head, facts=False, unmatched=["b"])
        out, row = kb_hook.respond("kb: a b")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "decision" not in out and row["answered"] is False
        assert self.INSTRUCTION in ctx and "treat the whole question as what the kb lacks" in ctx and "\ncheck: " in ctx

    def test_good_split_by_a_word_nowhere_in_the_kb_is_let_through(self, monkeypatch):
        head = ["coverage: good (best article matches 2 of 2 key words: a, b); not in the kb: zzq", "route: split",
                "kb has: a, b", "kb lacks: zzq"]
        self.planted(monkeypatch, "good", "split", head, facts=False, missing=["zzq"], lacks=["zzq"])
        out, row = kb_hook.respond("kb: a b zzq")
        assert "decision" not in out and row["answered"] is False, out
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert self.INSTRUCTION in ctx and "route: split\nkb has: a, b\nkb lacks: zzq" in ctx
        assert "treat the whole question as what the kb lacks" not in ctx

    def test_clean_good_is_blocked_and_kb_plus_keeps_its_context(self, monkeypatch):
        self.planted(monkeypatch, "good", None, ["coverage: good"], facts=False)
        out, row = kb_hook.respond("kb: a b")
        assert out["decision"] == "block" and out["reason"].startswith("coverage: good") and row["answered"] is True
        assert self.INSTRUCTION not in json.dumps(out)
        ctx = kb_hook.respond("kb+: a b")[0]["hookSpecificOutput"]["additionalContext"]
        assert ctx.startswith("The kb: hook ran the kb evidence pack for this question (coverage: good). Answer from it")
        assert self.INSTRUCTION not in ctx and ctx.endswith("coverage: good")


class TestBacklogPrompt:
    """kb_hook on `backlog:` and `backlog+:` prompts: backlog.py's output is the answer, or the model's context."""
    FAKE = ("import pathlib, sys\n"
            "if (pathlib.Path(__file__).parent / 'fail').exists():\n"
            "    sys.exit('planted failure')\n"
            "print('FAKE ' + ' '.join(sys.argv[1:]))\n"
            "for i in range(int(pathlib.Path(__file__).with_name('long').read_text())):\n"
            "    print(f'line {i} ' + 'x' * 100)\n")

    def fake(self, tmp_path, monkeypatch, long=0, fail=False):
        script = tmp_path / "_tools" / "backlog.py"
        script.parent.mkdir()
        script.write_text(self.FAKE, encoding="utf-8", newline="\n")
        (script.parent / "long").write_text(str(long), encoding="utf-8")
        if fail:
            (script.parent / "fail").write_text("", encoding="utf-8")
        monkeypatch.setattr(kb_hook, "BACKLOG_PY", str(script))

    def test_backlog_prompt_is_answered_and_blocked(self, tmp_path, monkeypatch):
        self.fake(tmp_path, monkeypatch)
        for prompt in ("backlog: what is next?", "  Backlog:", "backlog:what is blocked"):
            out, row = kb_hook.respond(prompt)
            assert row is None and set(out) == {"decision", "reason"} and out["decision"] == "block", (prompt, out)
            assert out["reason"].startswith("$ backlog.py horizon\nFAKE horizon\n\n$ backlog.py next --all --any\n"
                                            "FAKE next --all --any"), out["reason"]
            assert "without the model" in out["reason"] and "`backlog+:`" in out["reason"]

    def test_backlog_prompt_plus_passes_the_same_output_to_the_model(self, tmp_path, monkeypatch):
        self.fake(tmp_path, monkeypatch)
        out, row = kb_hook.respond("backlog+: what is next?")
        assert row is None and "decision" not in out
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "Answer from their output" in ctx and ctx.endswith("$ backlog.py horizon\nFAKE horizon\n\n"
                                                                   "$ backlog.py next --all --any\nFAKE next --all --any")
        assert kb_hook.respond("backlog: x")[0]["reason"].startswith(ctx.split("\n\n", 1)[1])

    def test_backlog_prompt_plus_context_is_cut_to_the_limit(self, tmp_path, monkeypatch):
        self.fake(tmp_path, monkeypatch, long=300)
        ctx = kb_hook.respond("backlog+: x")[0]["hookSpecificOutput"]["additionalContext"]
        assert len(ctx) <= kb_hook.LIMIT and "FAKE horizon" in ctx and "line 0 " in ctx and "line 299 " not in ctx
        assert len(kb_hook.respond("backlog: x")[0]["reason"]) > 10000, "the block reason is shown to the user whole"

    @staticmethod
    def every_part_problems(ctx):
        """What a backlog+ context lacks: each command's line, a note of its left-out lines, the limit."""
        problems = [] if len(ctx) <= kb_hook.LIMIT else [f"{len(ctx)} characters, over LIMIT"]
        for args in kb_hook.BACKLOG_COMMANDS:
            shown = "backlog.py " + " ".join(args)
            if f"$ {shown}\nFAKE {' '.join(args)}\nline 0 " not in ctx:
                problems.append(f"no output of {shown}")
            if f"more line(s): run `{shown}` for all of them" not in ctx:
                problems.append(f"no note of the lines of {shown} left out")
        return problems

    def test_backlog_hook_keeps_every_part(self, tmp_path, monkeypatch):
        # each command alone fills the limit (as horizon did once seven sprints were active): both keep a share
        self.fake(tmp_path, monkeypatch, long=200)
        ctx = kb_hook.respond("backlog+: x")[0]["hookSpecificOutput"]["additionalContext"]
        assert self.every_part_problems(ctx) == [], ctx[-400:]
        # a short part leaves its unused share to the long one, uncut
        assert kb_hook.fit_blocks([("a", "$ a\nshort"), ("b", "$ b\n" + "y\n" * 50)], 80).startswith("$ a\nshort\n\n$ b\n")

    def test_backlog_hook_keeps_every_part_planted_failure(self, tmp_path, monkeypatch):
        def cut_from_the_end(blocks, budget):  # the old cut: lines popped from the end of the joined output
            lines = "\n\n".join(text for _, text in blocks).splitlines()
            while lines and len("\n".join(lines)) > budget:
                lines.pop()
            return "\n".join(lines)
        self.fake(tmp_path, monkeypatch, long=200)
        monkeypatch.setattr(kb_hook, "fit_blocks", cut_from_the_end)
        ctx = kb_hook.respond("backlog+: x")[0]["hookSpecificOutput"]["additionalContext"]
        assert "no output of backlog.py next --all --any" in self.every_part_problems(ctx)

    def test_backlog_prompt_command_that_fails_never_blocks_the_prompt(self, tmp_path, monkeypatch):
        self.fake(tmp_path, monkeypatch, fail=True)
        for prompt in ("backlog: x", "backlog+: x"):
            out, row = kb_hook.respond(prompt)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            assert row is None and "decision" not in out, (prompt, out)
            assert "`backlog.py horizon` exited 1: planted failure" in ctx, ctx
        monkeypatch.setattr(kb_hook, "BACKLOG_PY", str(tmp_path / "missing" / "backlog.py"))
        assert "decision" not in kb_hook.respond("backlog: x")[0]
        monkeypatch.setattr(kb_hook, "BACKLOG_TIMEOUT", 0.001)
        monkeypatch.setattr(kb_hook, "BACKLOG_PY", str(tmp_path / "_tools" / "backlog.py"))
        assert "TimeoutExpired" in kb_hook.respond("backlog: x")[0]["hookSpecificOutput"]["additionalContext"]

    def test_backlog_prompt_only_a_leading_prefix_counts(self):
        for prompt in ("my backlog: x", "backlogs: x", "backlog x", "backlog", "fix the backlog: it is slow", ""):
            assert kb_hook.BACKLOG_PREFIX.match(prompt) is None, prompt
            assert kb_hook.answer(prompt) is None, prompt

    def test_backlog_prompt_end_to_end_without_loading_the_kb(self, tmp_path):
        def hook(prompt):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps({"prompt": prompt}),
                               capture_output=True, text=True, encoding="utf-8", cwd=KB, timeout=timeout_s(60),
                               env=querylog_env(tmp_path))
            assert p.returncode == 0, p.stderr
            return json.loads(p.stdout)
        out = hook("backlog: what is next?")
        assert out["decision"] == "block" and out["reason"].startswith("$ backlog.py horizon\n"), out["reason"][:200]
        assert "\n\n$ backlog.py next --all --any\n" in out["reason"]
        ctx = hook("backlog+: what is next?")["hookSpecificOutput"]["additionalContext"]
        assert "$ backlog.py horizon\n" in ctx and "$ backlog.py next --all --any\n" in ctx
        p = subprocess.run([sys.executable, "-c", "import sys, kb_hook; kb_hook.answer('backlog: x'); "
                            "sys.exit('kbfacts' in sys.modules)"], cwd=TOOLS, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout_s(60))
        assert p.returncode == 0, "a backlog: prompt must not load kbfacts"
        assert not list((tmp_path / "querylog" / "spool").rglob("*.jsonl")), "a backlog: prompt writes no query log row"


    def test_backlog_prompt_live_data_size_independent(self, tmp_path, monkeypatch):
        """The end-to-end test above runs over the live backlog; what it asserts holds at any size of it. Planted: each
        command's output grown far past the hook's limit (as seven active sprints grew horizon, BG-o3cjsgmm): the
        block reason still starts with horizon and holds next whole, and the backlog+ context keeps both commands."""
        self.fake(tmp_path, monkeypatch, long=3000)
        reason = kb_hook.respond("backlog: what is next?")[0]["reason"]
        assert reason.startswith("$ backlog.py horizon\n") and "\n\n$ backlog.py next --all --any\n" in reason
        ctx = kb_hook.respond("backlog+: what is next?")[0]["hookSpecificOutput"]["additionalContext"]
        assert "$ backlog.py horizon\n" in ctx and "$ backlog.py next --all --any\n" in ctx
        assert self.every_part_problems(ctx) == [], ctx[-400:]


# The tests that read the repository's own live data (its kb, its backlog), each with why what it asserts holds at
# any size of that data: another session growing the kb or the backlog must not turn main red (ST-2zl2od7q). Every
# test that runs a tool with cwd=KB is listed (test_live_data_size_independent_list); test_backlog.py builds its own
# repository for every test and reads no live data.
LIVE_DATA_TESTS = {
    "test_e2e_fixture_questions_keep_their_pack": "pins named questions' verdict and lead article, re-pinned on a "
                                                  "content change; no count",
    "test_search_finds_the_expected_article": "a named article in a top-5 ranking: the search baseline, no count",
    "test_persisted_index_gives_identical_packs": "two stores of the same corpus agree, whatever its size",
    "test_ledger_topic_markers_link_entries": "one named article's ledger link",
    "test_alias_and_signal_tables": "each row well formed and each named topic present, at any row count",
    "test_doc2query_expansions": "each row well formed, at any row count",
    "test_lookup_eval_ids_unique": "ids unique and slug-shaped, at any row count",
    "test_doc2query_no_stale_keys": "the tool's exit code",
    "test_lookup_eval_passes": "the eval's exit code over its own rows",
    "test_kb_ask_routes": "named questions' routes; the audit row lists rows by a status, never a count",
    "test_kb_ask_without_claude_prints_the_evidence": "one named question's evidence",
    "test_kb_hook": "named questions' verdicts and routes",
    "test_spread_key_words_get_a_check_line": "named questions, and a property of every good eval row",
    "test_false_good_gets_a_check_line": "named questions' verdicts",
    "test_common_words_need_one_fact_that_holds_them_all": "named questions' verdicts",
    "test_pack_number_with_unit_suffix_is_good": "one named question's verdict and fact line",
    "test_off_domain_product_is_none": "named questions' verdicts",
    "test_backlog_prompt_end_to_end_without_loading_the_kb": "headers and block shape, which the hook keeps at any "
                                                             "backlog size (test_backlog_prompt_live_data_size_independent)",
    "test_raw_read_nudge_end_to_end_prints_json_only_for_a_read": "a hint for a command; the kb's files are not read",
    "test_raw_read_nudge_survives_odd_input": "the hook's exit on odd input; the kb's files are not read",
    "test_raw_read_nudge_recognises_powershell_reads": "a hint for a command; the kb's files are not read",
    "test_raw_read_nudge_is_silent_for_other_powershell_commands": "no output for a command; the kb's files are not read",
}


def live_runs(source):
    """The test functions in SOURCE whose body, or a helper method of their class they call, runs a tool with cwd=KB."""
    tree = ast.parse(source)
    out = set()
    for cls in [n for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.Module))]:
        funcs = [n for n in cls.body if isinstance(n, ast.FunctionDef)]
        helpers = {f.name for f in funcs if not f.name.startswith("test_") and "cwd=KB" in ast.get_source_segment(source, f)}
        for f in funcs:
            seg = ast.get_source_segment(source, f)
            if f.name.startswith("test_") and ("cwd=KB" in seg or any(f"self.{h}(" in seg for h in helpers)):
                out.add(f.name)
    return out


def test_live_data_size_independent_list():
    """Every test of this file and test_backlog.py that runs a tool over the live repository is in LIVE_DATA_TESTS
    with its reason, and every name there is a test of this file. Planted: an unlisted live test is found."""
    names = {n.name for n in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}
    assert set(LIVE_DATA_TESTS) <= names, sorted(set(LIVE_DATA_TESTS) - names)
    for f in (Path(__file__), Path(TOOLS) / "test_backlog.py"):
        unlisted = live_runs(f.read_text(encoding="utf-8")) - set(LIVE_DATA_TESTS)
        assert not unlisted, f"{f.name}: tests over live data not in LIVE_DATA_TESTS: {sorted(unlisted)}"
    live = "cwd=" + "KB"  # split, so this test's own source is not a live run
    planted = (f"class TestX:\n    def go(self):\n        return run(x, {live})\n\n"
               "    def test_counts(self):\n        assert self.go() == 3\n\n"
               f"def test_direct():\n    run(y, {live})\n\ndef test_fixture(tmp_path):\n    run(y, cwd=tmp_path)\n")
    assert live_runs(planted) == {"test_counts", "test_direct"}


class TestRawReadNudge:
    """kb_hook on a PreToolUse Bash or PowerShell event: a whole-file read of a kb article gets a hint and runs; all else is silent."""
    READS = ["cat kb/public/claude/hooks.md", "cat ./kb/public/claude/hooks.md kb/public/ad/gpo.md",
             "sed -n 1,40p kb/public/claude/hooks.md", "sed -n '20,30p' kb/public/x/y.md", "head -n 40 kb/public/x/y.md",
             "tail -20 kb/public/x/y.md", "grep -n LAPS kb/public/windows/laps.md", "grep -in laps kb/public/windows/laps.md",
             "cat kb/public/_gaps.md", "cat kb/acme/_gaps.md", "cat kb/acme/net/vpn.md",
             "cd /work/it-ops-kb && cat /work/it-ops-kb/kb/public/x/y.md | head -5", "FOO=1 cat kb/public/x/y.md",
             "git status\ncat kb/public/x/y.md", "sed -ne 20,30p kb/public/x/y.md", "sed --quiet 5p kb/public/x/y.md",
             "sed -E -n '/i/p' kb/public/x/y.md", "sed -n -e 1p kb/public/x/y.md", "sed -e i -n kb/public/x/y.md"]
    SILENT = ["ls kb/public/claude", "cat README.md", "cat _tools/kb_hook.py", "cat kb/_self/backlog.md",
              "cat kb/public/_sources.csv", "grep -rn LAPS kb/public", "grep LAPS kb/public/windows/laps.md",
              "sed -i s/a/b/ kb/public/x/y.md", "sed s/a/b/ kb/public/x/y.md", "cat notes > kb/public/x/y.md",
              "cat notes >> kb/public/x/y.md", "python3 _tools/rag.py show kb/public/claude/hooks.md:23 -n 30",
              "python3 _tools/rag.py search \"laps\" --index", "git add kb/public/x/y.md", "wc -l kb/public/x/y.md",
              "echo cat kb/public/x/y.md", "cat \"kb/public/x/y.md", "", "   ",
             "sed -in s/a/b/p kb/public/x/y.md", "sed -i -n 's/a/b/p' kb/public/x.md", "sed -n -i s/a/b/p kb/public/x/y.md",
             "sed -ni s/a/b/p kb/public/x/y.md", "sed -n -i.bak s/a/b/p kb/public/x/y.md",
             "sed -n --in-place s/a/b/p kb/public/x/y.md", "sed --in-place=.bak -n s/a/b/p kb/public/x/y.md",
             "sed --quiet --in-place s/a/b/p kb/public/x/y.md", "sed -n -I '' s/a/b/p kb/public/x/y.md",
             "sed -Eni s/a/b/p kb/public/x/y.md"]

    @staticmethod
    def event(command, **extra):
        return dict({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}, **extra)

    def run_hook(self, stdin):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=stdin, capture_output=True,
                           text=True, encoding="utf-8", cwd=KB, timeout=60)
        assert p.returncode == 0, p.stderr
        return p.stdout

    def test_raw_read_nudge_names_the_rag_tools_and_decides_nothing(self):
        for command in self.READS:
            out = kb_hook.raw_read_nudge(self.event(command))
            assert out is not None, f"no hint for: {command!r}"
            spec = out["hookSpecificOutput"]
            assert spec["hookEventName"] == "PreToolUse" and set(spec) == {"hookEventName", "additionalContext"}, spec
            ctx = spec["additionalContext"]  # no permissionDecision: the command runs as it would without the hook
            for name in ("rag.py show", "rag.py facts", "rag.py audit", "search", "--index"):
                assert name in ctx, (command, name)

    def test_raw_read_nudge_is_silent_for_other_commands(self):
        for command in self.SILENT:
            assert kb_hook.raw_read_nudge(self.event(command)) is None, f"hint for: {command!r}"
        assert kb_hook.raw_read_nudge(self.event("cat kb/public/x/y.md", tool_name="Read")) is None

    def test_raw_read_nudge_survives_odd_input(self):
        for odd in [{}, {"tool_input": None}, {"tool_input": []}, {"tool_input": {}}, {"tool_input": {"command": None}},
                    {"tool_input": {"command": ["cat", "kb/public/x.md"]}}, {"tool_input": {"command": 7}}, {"tool_name": 3}]:
            assert kb_hook.raw_read_nudge(odd) is None, odd
        for stdin in ["", "not json", "[]", "null", "\"cat kb/public/x/y.md\"", "{\"tool_input\": 5}"]:
            assert self.run_hook(stdin) == "", stdin

    def test_raw_read_nudge_end_to_end_prints_json_only_for_a_read(self):
        out = self.run_hook(json.dumps(self.event("sed -n 1,20p kb/public/claude/hooks.md")))
        assert json.loads(out)["hookSpecificOutput"]["additionalContext"] == kb_hook.RAW_NUDGE
        assert self.run_hook(json.dumps(self.event("python3 _tools/rag.py show kb/public/claude/hooks.md:23"))) == ""
        assert self.run_hook(json.dumps(self.event("cat kb/_self/maintaining.md"))) == ""
        # a UserPromptSubmit event is untouched
        assert self.run_hook(json.dumps({"prompt": "cat kb/public/claude/hooks.md"})) == ""

    def test_raw_read_nudge_returns_before_shlex_for_a_command_without_a_kb_path(self):
        p = subprocess.run([sys.executable, "-c", "import sys, kb_hook; kb_hook.raw_read_nudge({'tool_input': "
                            "{'command': 'ls -la'}}); sys.exit('shlex' in sys.modules)"], cwd=TOOLS, capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        assert p.returncode == 0, "an ordinary command must not load shlex"

    PS_READS = ["Get-Content kb/public/claude/hooks.md", "Get-Content .\\kb\\public\\claude\\hooks.md -TotalCount 40",
                "gc 'kb\\public\\x\\y.md' -Raw", "GET-CONTENT -Path kb/public/x/y.md",
                "get-content -LiteralPath \"kb\\public\\x\\y.md\"", "cat kb\\public\\x\\y.md", "type kb\\public\\x\\y.md",
                "Select-String -Path kb\\public\\windows\\laps.md -Pattern LAPS", "sls LAPS kb/public/windows/laps.md",
                "Select-String -Pattern LAPS -Path kb\\public\\a.md,kb\\public\\b.md",
                "Get-Content C:\\work\\it-ops-kb\\kb\\public\\x\\y.md | Select-Object -First 5",
                "Get-Content kb\\acme\\_gaps.md", "Microsoft.PowerShell.Management\\Get-Content kb\\public\\x\\y.md",
                "& cat kb\\public\\x\\y.md", "Get-ChildItem kb\\public; Get-Content kb\\public\\x\\y.md",
                "Get-Location\nGet-Content kb\\public\\x\\y.md"]
    # a read whose result is assigned, and a parameter written as -Name:value (BG-rgvfn5aa)
    PS_READS_ASSIGNED = ["$t = Get-Content kb\\public\\x.md", "Get-Content -Path:kb\\public\\x.md",
                         "$t = gc -LiteralPath:'kb\\public\\x.md'", "$t=gc -LiteralPath:'kb\\public\\x.md'",
                         "[string]$t = Get-Content kb\\public\\x.md -Raw", "[string[]]$lines=Get-Content kb/public/x.md",
                         "$t += Get-Content kb\\public\\x.md", "$env:T =Get-Content kb\\public\\x.md",
                         "$t = Select-String -Path:\"kb\\public\\a.md\",kb\\public\\b.md -Pattern LAPS",
                         "Get-ChildItem kb; $t = Get-Content -Path:kb\\public\\x.md -TotalCount:40"]
    PS_SILENT_ASSIGNED = ["$t = Set-Content kb\\public\\x.md -Value notes", "$p = 'kb\\public\\x.md'",
                          "$p = \"kb\\public\\x.md\"; Remove-Item $p", "$t = Get-Content notes.txt > kb\\public\\x.md",
                          "Set-Content -Path:kb\\public\\x.md -Value:notes", "Out-File -FilePath:kb\\public\\x.md",
                          "$t = Get-Content -Path:kb\\_self\\tools.md", "$t -eq 'Get-Content kb\\public\\x.md'",
                          "git commit -m \"type kb/public/x.md\"", "$m = git commit -m \"type kb/public/x.md\"",
                          "$t == Get-Content kb\\public\\x.md"]

    def test_raw_read_nudge_recognises_assigned_and_colon_parameter_powershell_reads(self):
        for command in self.PS_READS_ASSIGNED:
            assert kb_hook.is_raw_read(command, powershell=True), f"no hint for: {command!r}"
            assert kb_hook.raw_read_nudge(self.event(command, tool_name="PowerShell")) is not None, command
        for command in self.PS_SILENT_ASSIGNED:
            assert not kb_hook.is_raw_read(command, powershell=True), f"hint for: {command!r}"
        # Bash has no `$t = cmd` assignment; its mode is unchanged
        assert not kb_hook.is_raw_read("$t = cat kb/public/x.md")
    PS_SILENT = ["Get-ChildItem kb\\public\\claude", "Get-Content README.md", "Get-Content kb\\_self\\maintaining.md",
                 "Get-Content kb\\public\\_sources.csv", "Get-Content _tools\\kb_hook.py",
                 "Select-String -Path _tools\\*.py -Pattern kb", "Set-Content kb\\public\\x\\y.md -Value notes",
                 "Add-Content kb/public/x/y.md -Value notes", "Get-Content notes.txt | Set-Content kb\\public\\x\\y.md",
                 "Get-Content notes.txt > kb\\public\\x\\y.md", "Get-Content notes.txt >> kb\\public\\x\\y.md",
                 "Remove-Item kb\\public\\x\\y.md", "python3 _tools/rag.py show kb\\public\\claude\\hooks.md:23 -n 30",
                 "git add kb\\public\\x\\y.md", "Write-Output 'cat kb/public/x/y.md'", "Get-Content 'kb\\public\\x\\y.md",
                 "Get-Item kb\\public\\x\\y.md", "", "   "]

    def test_raw_read_nudge_recognises_powershell_reads(self):
        for command in self.PS_READS:
            out = kb_hook.raw_read_nudge(self.event(command, tool_name="PowerShell"))
            assert out is not None, f"no hint for: {command!r}"
            assert set(out) == {"hookSpecificOutput"} and out["hookSpecificOutput"]["additionalContext"] == kb_hook.RAW_NUDGE
        # the PowerShell tool sends the command as tool_input.command, like Bash (public/claude/hooks.md)
        out = self.run_hook(json.dumps(self.event(self.PS_READS[0], tool_name="PowerShell")))
        assert json.loads(out)["hookSpecificOutput"]["additionalContext"] == kb_hook.RAW_NUDGE

    def test_raw_read_nudge_is_silent_for_other_powershell_commands(self):
        for command in self.PS_SILENT:
            assert kb_hook.raw_read_nudge(self.event(command, tool_name="PowerShell")) is None, f"hint for: {command!r}"
        assert self.run_hook(json.dumps(self.event("Get-Content kb\\_self\\tools.md", tool_name="PowerShell"))) == ""
        # the PowerShell verbs are not Bash's, and Bash's `sed -n` is not a PowerShell command
        assert kb_hook.raw_read_nudge(self.event("Get-Content kb/public/x/y.md")) is None
        assert kb_hook.raw_read_nudge(self.event("sed -n 1,40p kb/public/x/y.md", tool_name="PowerShell")) is None
        assert kb_hook.raw_read_nudge(self.event("Get-Content kb/public/x/y.md", tool_name="Read")) is None

    def test_raw_read_nudge_hook_is_registered_on_bash_and_powershell(self):
        # one entry per tool: Bash through sh, PowerShell through `shell: powershell` (no sh without Git Bash);
        # test_portability.py gates the launcher forms and that each call fires the hint once
        groups = json.loads(text(".claude/settings.json"))["hooks"]["PreToolUse"]
        entries = [e for e in groups if e["matcher"] in ("Bash", "PowerShell")]
        assert [e["matcher"] for e in entries] == ["Bash", "PowerShell"], entries
        # kb_hook.py answers only Bash and PowerShell: an entry on another tool would run it for nothing
        idle = [e["matcher"] for e in groups if e not in entries
                and any("kb_hook.py" in h.get("command", "") for h in e["hooks"])]
        assert idle == [], idle
        hooks = [h for e in entries for h in e["hooks"]]
        assert hooks[0]["command"] == 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/kb_hook.py', hooks
        assert hooks[1]["shell"] == "powershell" and "/_tools/kb_hook.py" in hooks[1]["command"], hooks
        assert len(hooks) == 2, hooks


def test_freshness_note_for_latest_or_unnamed_versions():
    """A question about the latest release, or naming a version the kb never mentions, gets a `freshness:` line
    (the kb's facts are as of the lead article's retrieval: check the source live); other questions get none."""
    latest = kbfacts.pack("What is the latest presidio-analyzer release?")["text"]
    assert re.search(r"^freshness: these facts are as of \d{4}-\d{2}-\d{2}\. A newer release", latest, re.M), latest[:400]
    unnamed = kbfacts.pack("Does presidio-analyzer 2.2.999 include the UuidRecognizer?")["text"]
    assert "; the kb never names 2.2.999. " in unnamed, unnamed[:400]
    assert "freshness:" not in kbfacts.pack("What is the default Windows LAPS password length?")["text"]
    assert kbfacts.freshness("q v1.2 25H2 CMPivot", ["25h2", "v1.2", "cmpivot"], {}) == (
        "freshness: the kb never names v1.2. A newer release may exist: check the cited source live and "
        "say which version your answer is for.")


# ---------------------------------------------------------------- decisions beside the facts (decision_lookup)

DECISION_QUESTION = "Who approves an early purge of the print queues?"  # the fixture article says nothing of approval
DECISION_TEXT = "Print owner approves an early purge of print queues."
DECISION_PATTERN_QUESTION = "What pattern do print queue names follow?"  # answered by the article's own fact
DECISION_CONTEXT = "article:print/queues"


def decision_lookup_root(tmp_path, rows=None, article_extra=""):
    """A fixture root (test_kb_root.make_root) with its decisions (decision_lookup_set) and `article_extra` appended
    to its article. The tests rewrite its decision file between calls: it is not in the pack index, so one index
    (decision_lookup_run keeps it beside the root) serves a whole test."""
    from test_kb_root import make_root
    root = tmp_path / "team-kb"
    make_root(str(root))
    if article_extra:
        art = root / "print" / "queues.md"
        art.write_text(art.read_text(encoding="utf-8") + article_extra, encoding="utf-8", newline="\n")
    decision_lookup_set(str(root), rows)
    return str(root)


def decision_lookup_set(root, rows):
    """The root's _decisions.csv holds these rows (None: no file; []: a header only)."""
    from test_kb_root import DEC
    path = Path(root) / DEC
    if rows is None:
        path.unlink(missing_ok=True)
    else:
        kbcommon.write_csv(str(path), kbcommon.DECISION_COLS, rows)


def decision_lookup_run(root, *args):
    from test_kb_root import run as run_tool
    code, out = run_tool("rag.py", *args, roots=root, data=str(Path(root).parent / "index"))
    assert code == 0 and "Traceback" not in out, out[-600:]
    return out


def decision_lookup_pack(root, question, *extra, rows=...):
    """The pack of `question` in the fixture root, after `rows` are written when given (decision_lookup_set)."""
    if rows is not ...:
        decision_lookup_set(root, rows)
    return decision_lookup_run(root, "pack", question, "--root", "fixture", *extra)


def decision_lookup_rows():
    from test_kb_root import decision
    return [decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT),
            decision(1, text="Print queue names move to the pattern PQ-site-floor-room.", context=DECISION_CONTEXT,
                     status="proposed", by="", by_ref=""),
            decision(2, text="Finished print jobs stay for 30 days.", context=DECISION_CONTEXT, status="invalidated",
                     invalidated_reason="article:print/queues is gone", invalidated_date="2026-10-02"),
            decision(3, text="Print queues are purged every hour.", context=DECISION_CONTEXT, status="superseded")]


def test_decision_lookup_labels_and_the_invalidated_flag(tmp_path):
    """A pack prints the active decision as `decided`, the proposed one as `proposed (not confirmed)`, each with its
    id and the row's path:line (which `rag.py show` prints); an invalidated one only with --invalidated, as
    `invalidated because <reason>`; a superseded one never."""
    from test_kb_root import did
    root = decision_lookup_root(tmp_path, decision_lookup_rows())
    out = decision_lookup_pack(root, DECISION_QUESTION)
    assert f"\n## decisions\n- fixture/_decisions.csv:2 decided by operator on 2026-10-01: {DECISION_TEXT} [DECISION {did(0)}]" in out, out
    out = decision_lookup_pack(root, DECISION_PATTERN_QUESTION)
    assert (f"- fixture/_decisions.csv:3 proposed (not confirmed): Print queue names move to the pattern "
            f"PQ-site-floor-room. [DECISION {did(1)}]") in out, out
    assert "decided by" not in out and "30 days" not in out and "every hour" not in out, out
    shown = decision_lookup_pack(root, DECISION_PATTERN_QUESTION, "--invalidated")
    assert (f"- fixture/_decisions.csv:4 invalidated because article:print/queues is gone: Finished print jobs stay for "
            f"30 days. [DECISION {did(2)}]") in shown and "every hour" not in shown, shown
    row = decision_lookup_run(root, "show", "fixture/_decisions.csv:3", "-n", "1")
    assert did(1) in row and "PQ-site-floor-room" in row, row
    # planted: the same two rows both active print as decided, so the labels come from the status
    rows = [{**r, "status": "active", "invalidated_reason": "", "invalidated_date": ""} for r in decision_lookup_rows()[:2]]
    out = decision_lookup_pack(root, DECISION_PATTERN_QUESTION, rows=rows)
    assert "proposed" not in out and "decided on 2026-10-01: Print queue names move" in out, out


def test_decision_lookup_coverage_counts_only_active_decisions(tmp_path):
    """The fixture article does not answer who approves an early purge, so the pack is `none`. An active decision whose
    text holds the question's words lifts it to `good` (no route lines, its words not reported missing); a proposed,
    an invalidated (with --invalidated) or a superseded one leaves the verdict as it was, and so does an active one
    that holds too few of the words or lacks a name the question uses."""
    from test_kb_root import decision
    root = decision_lookup_root(tmp_path)
    base = decision_lookup_pack(root, DECISION_QUESTION)
    assert base.startswith("coverage: none"), base
    lifted = decision_lookup_pack(root, DECISION_QUESTION, rows=[decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT)])
    assert lifted.startswith("coverage: good (an active decision answers it;"), lifted
    assert "route:" not in lifted and "not in the kb" not in lifted and "decided by operator" in lifted, lifted
    # tied to no article, the words alone answer
    item = [decision(0, text=DECISION_TEXT, context="item:TK-abcd2345")]
    assert decision_lookup_pack(root, DECISION_QUESTION, rows=item).startswith("coverage: good (an active decision answers it;")
    proposed = dict(status="proposed", by="", by_ref="")
    invalid = dict(status="invalidated", invalidated_reason="item:TK-abcd2345 dropped", invalidated_date="2026-10-02")
    for name, row, extra in (("proposed", decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, **proposed), ()),
                             ("invalid", decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, **invalid), ("--invalidated",)),
                             ("super", decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, status="superseded"), ("--invalidated",)),
                             ("few", decision(0, text="Print queues are purged nightly.", context=DECISION_CONTEXT), ())):
        out = decision_lookup_pack(root, DECISION_QUESTION, *extra, rows=[row])
        assert out.splitlines()[0] == base.splitlines()[0], (name, out[:300])
    out = decision_lookup_pack(root, DECISION_QUESTION, rows=[decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, **proposed)])
    assert "proposed (not confirmed)" in out, out
    out = decision_lookup_pack(root, DECISION_QUESTION, "--invalidated",
                               rows=[decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, **invalid)])
    assert "invalidated because item:TK-abcd2345 dropped" in out, out
    # a name the decision does not hold (the question is about another product) keeps it from answering
    other = decision_lookup_pack(root, "Who approves an early purge of the Contoso print queues?", rows=item)
    assert "an active decision answers it" not in other, other[:300]


def test_decision_lookup_no_decision_rows_leave_the_pack_unchanged(tmp_path):
    """A kb with no decision row packs byte for byte as before: no file, a header only, and only rows nothing prints
    (superseded; invalidated without --invalidated) give the same text, whichever format."""
    from test_kb_root import QUESTION, decision
    sup = [decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, status="superseded")]
    inv = [decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT, status="invalidated",
                    invalidated_reason="item:TK-abcd2345 dropped", invalidated_date="2026-10-02")]
    root = decision_lookup_root(tmp_path)
    questions = (QUESTION, DECISION_QUESTION, DECISION_PATTERN_QUESTION, "What is the default Windows LAPS password length?")
    for q in questions:
        for fmt in ("detailed", "concise"):
            texts = {name: decision_lookup_pack(root, q, "--format", fmt, rows=rows)
                     for name, rows in (("none", None), ("header", []), ("superseded", sup), ("invalidated", inv))}
            assert len(set(texts.values())) == 1 and "## decisions" not in texts["none"], (q, texts)
    for q in ("What is the default Windows LAPS password length?", "When does NTLMv1 become disabled by default?"):
        res = kbfacts.pack(q)  # the real kb: the invariant, whatever rows it holds
        assert ("## decisions" in res["text"]) == bool(res["decisions"]), q
    # planted: a printable row does change the pack, so the equality above can fail
    planted = decision_lookup_pack(root, DECISION_QUESTION, rows=[decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT)])
    assert planted != decision_lookup_pack(root, DECISION_QUESTION, rows=None)


def test_decision_lookup_lines_count_inside_the_budget(tmp_path):
    """The decision lines are paid from the pack's budget: at most MAX_DECISIONS lines and a third of the budget,
    and the facts printed with them are never more than without them (a large budget keeps them all)."""
    from test_kb_root import decision
    long_text = "Spooler notes say that quokka reports go to the print owner every week. " * 4
    rows = [decision(i, text=f"{long_text}Rule {i}.", context=DECISION_CONTEXT) for i in range(6)]
    extra = "".join(f"- Spooler note {n}: the quokka report of the finished print jobs is filed on Friday. [DOC FXT-3iumfjqd]\n"
                    for n in range(1, 6))  # the words the question uses are not common: few of many facts hold them
    extra += "".join(f"- Filler fact {n} about xylophone calibration. [DOC FXT-3iumfjqd]\n" for n in range(40))
    root = decision_lookup_root(tmp_path, None, extra)
    question = "What do the spooler notes say about quokka?"

    def lines(out, decisions):
        return [ln for ln in out.splitlines() if ln.startswith("- ") and ("_decisions.csv" in ln) == decisions]

    for budget in (200, 400, 6000):
        without = decision_lookup_pack(root, question, "--budget", str(budget), rows=None)
        with_ = decision_lookup_pack(root, question, "--budget", str(budget), rows=rows)
        decided = lines(with_, True)
        assert 1 <= len(decided) <= kbfacts.MAX_DECISIONS, (budget, with_)
        assert set(lines(with_, False)) <= set(lines(without, False)), budget
        if len(decided) > 1:
            assert sum(map(len, decided[:-1])) <= int(budget * 3.5) // kbfacts.DECISION_BUDGET_SHARE, (budget, decided)
        if budget == 6000:
            assert lines(with_, False) == lines(without, False), "a large budget keeps every fact line"
        if budget == 200:
            assert len(lines(with_, False)) < len(lines(without, False)), "the facts gave way to the decisions"


def test_decision_lookup_cited_and_named_facts_bring_their_decision(tmp_path):
    """A fact that cites `[DECISION id]`, or that a decision names (`fact:`), brings the decision beside it in a pack
    and in `show` whatever words it holds; the short tag of `facts` prints the id, not a bare DECISION."""
    from test_kb_root import ARTICLE, SID, decision, did
    cited = f"- The nightly purge runs at 02:00 on the spooler. [DOC {SID}; DECISION {did(0)}]\n"
    named = f"- Spooler logs are kept for 3 days. [DOC {SID}]\n"
    key = kbfacts.fact_key(f"Spooler logs are kept for 3 days. [DOC {SID}]")
    rows = [decision(0, text="Retention is the team's choice, not the vendor's.", context="item:TK-abcd2345"),
            decision(1, text="Logs follow the audit schedule.", context=f"fact:{key}")]
    root = decision_lookup_root(tmp_path, rows, cited + named)
    out = decision_lookup_pack(root, "When does the nightly purge run on the spooler?")
    assert f"decided by operator on 2026-10-01: Retention is the team's choice, not the vendor's. [DECISION {did(0)}]" in out, out
    assert "Logs follow the audit schedule" not in out, out
    out = decision_lookup_pack(root, "How many days are spooler logs kept?")
    assert f"Logs follow the audit schedule. [DECISION {did(1)}]" in out, out
    first = next(n for n, ln in enumerate((ARTICLE + cited).splitlines(), start=1) if "nightly purge runs" in ln)
    shown = decision_lookup_run(root, "show", f"fixture/print/queues.md:{first}", "-n", "1")
    assert f"DECISION {did(0)}]\ndecisions:\n- fixture/_decisions.csv:2 decided" in shown and did(1) not in shown, shown
    shown = decision_lookup_run(root, "show", f"fixture/print/queues.md:{first + 1}", "-n", "1")
    assert did(1) in shown and did(0) not in shown, shown  # the fact the second decision names
    assert "decisions:" not in decision_lookup_run(root, "show", "fixture/print/queues.md:16", "-n", "1")
    facts = decision_lookup_run(root, "facts", "fixture", "--tag", "DECISION")
    assert f"[DOC {SID}; DECISION {did(0)}]" in facts, facts
    import rag
    part = kbfacts.parse_tag(f"[DOC S1208; DECISION {did(0)}, DECISION {did(1)}]")
    assert rag.short_tag(part) == f"DOC S1208; DECISION {did(0)},{did(1)}"
    assert rag.short_tag(kbfacts.parse_tag("[DECISION]")) == "DECISION"  # a tag naming none stays bare (check.py reports it)


def test_decision_lookup_audit_lists_shared_contexts_without_blocking(tmp_path):
    """audit lists the active decisions that share a context reference as a possible contradiction, once per
    reference; a proposed, an invalidated or a lone decision is not listed, and check.py still passes."""
    from test_kb_root import checked_root, decision, did
    rows = [decision(0, text="Keep jobs 14 days.", context="article:print/queues; item:TK-abcd2345"),
            decision(1, text="Keep jobs 30 days.", context="domain:print; article:print/queues"),
            decision(2, text="Keep jobs 7 days.", context="article:print/queues", status="proposed", by="", by_ref=""),
            decision(3, text="Purge nightly.", context="item:TK-wxyz2345")]
    root = decision_lookup_root(tmp_path, rows)
    out = decision_lookup_run(root, "audit", "--root", "fixture")
    assert out.count("possible contradiction") == 1, out
    block = out[out.index("possible contradiction"):]
    assert block.startswith("possible contradiction: 2 active decisions share article:fixture/print/queues (read them; "
                            "nothing is blocked)\n"), block
    assert f"  {did(0)} fixture/_decisions.csv:2 Keep jobs 14 days." in block and did(1) in block, block
    assert did(2) not in block and did(3) not in block, block
    assert decision_lookup_run(root, "audit", "fixture/print").count("possible contradiction") == 1
    assert "possible contradiction" not in decision_lookup_run(root, "audit", "--root", "public"), "narrowed away"
    # planted: the sharing decision only proposed (or alone) lists nothing
    decision_lookup_set(root, rows[:1] + rows[2:])
    assert "possible contradiction" not in decision_lookup_run(root, "audit", "--root", "fixture")
    # nothing is blocked: check.py reports no decision error for the sharing rows
    code, found, text = checked_root(tmp_path / "chk", rows[:2] + [rows[3]])
    assert found == {}, text[-800:]


# ---- LOG rows and the LOG tag, and the DECISION tag in data rows (check.py: LOG_COLS, LEDGER_TAGS)

def log_row(i=0, **over):
    """A valid LOG row of the fixture root, with the fields in `over` replaced."""
    row = {"id": "L-aaaaaaa" + "abcdefgh"[i], "observation": "Median 12 pack calls a day over 9 days, 3 of them weak.",
           "source_run_ids": "20260929T101500Z-0000abcd; 20260930T101500Z-0000abce", "observed_from": "2026-09-21",
           "observed_to": "2026-09-30", "context": "article:print/queues; domain:print", "status": "active",
           "invalidated_reason": "", "links": ""}
    row.update(over)
    return row


def log_check(tmp_path, rows=None, *, other=None, visibility="internal", article="", data="", prefix="FXT"):
    """check.py over a fixture root (and a second root `other` with its own log rows) that keeps these LOG rows
    (dicts; None: no _logs.csv), `article` appended to its article and `data` as a row of a data file:
    (exit code, the ERROR lines)."""
    from test_kb_root import make_root, run as run_tool
    root, second = tmp_path / "team-kb", tmp_path / "other-kb"
    make_root(str(root), prefix=prefix)
    make_root(str(second), prefix="OTH")
    meta = second / "_root.md"
    meta.write_text(meta.read_text(encoding="utf-8").replace("root: fixture", "root: other"), encoding="utf-8", newline="\n")
    meta = root / "_root.md"
    meta.write_text(meta.read_text(encoding="utf-8").replace("visibility: internal", f"visibility: {visibility}"),
                    encoding="utf-8", newline="\n")
    for r in (root, second):  # check.py wants the artifacts ledger
        (r / "_artifacts.csv").write_text("path,source_id,sha256\n", encoding="utf-8", newline="\n")
    if rows is not None:
        kbcommon.write_csv(str(root / "_logs.csv"), ["id", "observation", "source_run_ids", "observed_from", "observed_to",
                                                     "context", "status", "invalidated_reason", "links"], rows)
    if other is not None:
        kbcommon.write_csv(str(second / "_logs.csv"), ["id", "observation", "source_run_ids", "observed_from", "observed_to",
                                                       "context", "status", "invalidated_reason", "links"], other)
    art = root / "print" / "queues.md"
    art.write_text(art.read_text(encoding="utf-8") + article, encoding="utf-8", newline="\n")
    if data:
        sig = root / "_retrieval" / "signals.csv"
        sig.write_text(sig.read_text(encoding="utf-8") + data, encoding="utf-8", newline="\n")
    code, out = run_tool("check.py", "--root", "fixture", roots=os.pathsep.join([str(root), str(second)]))
    assert "Traceback" not in out, out[-800:]
    return code, [ln for ln in out.splitlines() if ln.startswith("ERROR")]


def test_log_row_contract(tmp_path):
    """A `_logs.csv` has the header id, observation, source_run_ids, observed_from, observed_to, context, status,
    invalidated_reason, links, and each row is a derived aggregate with the runs it came from: a valid row passes;
    each defect (planted) gives one error that names the rule, and a row carrying raw event text is refused."""
    assert log_check(tmp_path / "ok", [log_row(0), log_row(1, status="proposed"),
                                       log_row(2, status="invalidated", invalidated_reason="the article was rewritten")]) == (0, [])
    assert log_check(tmp_path / "none") == (0, [])  # the file is optional
    planted = {
        "id": ("id 'L-AAAA' is not L-<8 base32>", {"id": "L-AAAA"}),
        "no observation": ("no observation", {"observation": ""}),
        "no number": ("holds no number", {"observation": "Users often ask about print queues"}),
        "long": ("is longer than", {"observation": "Median 12 calls. " + "words " * 60}),
        "json": ("holds a JSON object", {"observation": 'Median 12 calls {"event": "pack", "n": 3}'}),
        "timestamp": ("holds a timestamp with a time of day", {"observation": "Median 12 calls at 2026-09-30T10:15:00Z"}),
        "compact timestamp": ("holds a timestamp with a time of day", {"links": "20260930T101500Z"}),
        "line break": ("holds a line break", {"observation": "Median 12 calls\nsecond line"}),
        "leak": ("has a leak-scan hit (ip)", {"observation": "Median 12 calls from 10.20.30.40"}),
        "no runs": ("no source_run_ids", {"source_run_ids": ""}),
        "bad run": ("is not a run id", {"source_run_ids": "r-12"}),
        "run twice": ("a run id twice", {"source_run_ids": "20260929T101500Z-0000abcd;20260929T101500Z-0000abcd"}),
        "bad date": ("are not both YYYY-MM-DD", {"observed_from": "2026-9-21"}),
        "dates reversed": ("is after observed_to", {"observed_from": "2026-10-01"}),
        "status": ("is not one of proposed|active|invalidated", {"status": "superseded"}),
        "no context": ("no context", {"context": ""}),
        "bad context": ("is not <kind>:<value>", {"context": "print queues"}),
        "unknown article": ("names no article print/gone", {"context": "article:print/gone"}),
        "reason without invalidation": ("invalidated_reason exactly when", {"invalidated_reason": "why"}),
        "invalidated without reason": ("invalidated_reason exactly when", {"status": "invalidated"}),
    }
    for n, (name, (rule, over)) in enumerate(planted.items()):
        code, found = log_check(tmp_path / f"p{n}", [log_row(0, **over)])
        assert code == 1 and len(found) == 1 and rule in found[0] and "fixture/_logs.csv:2" in found[0], (name, found)
    code, found = log_check(tmp_path / "dup", [log_row(0), log_row(0)])
    assert code == 1 and len(found) == 2 and all("duplicate log row id" in e for e in found), found
    assert log_check(tmp_path / "inv", [log_row(0, status="invalidated", invalidated_reason="gone", context="article:print/gone")]) == (0, [])
    code, found = log_check(tmp_path / "pre", [log_row(0)], prefix="L")  # a root prefix L would read as a log row's id
    assert code == 1 and any("id_prefix 'L' is reserved for log row ids" in e for e in found), found


def test_log_header_is_exact(tmp_path):
    """A `_logs.csv` whose header is not LOG_COLS is one error on the file."""
    from test_kb_root import make_root, run as run_tool
    root = tmp_path / "team-kb"
    make_root(str(root))
    (root / "_artifacts.csv").write_text("path,source_id,sha256\n", encoding="utf-8", newline="\n")
    (root / "_logs.csv").write_text("id,observation,context\nL-aaaaaaaa,Median 12,article:print/queues\n", encoding="utf-8", newline="\n")
    code, out = run_tool("check.py", "--root", "fixture", roots=str(root))
    assert code == 1 and "fixture/_logs.csv: header is 'id,observation,context', not 'id,observation," in out, out[-600:]


def test_log_tag_is_resolved_by_check(tmp_path):
    """An internal root's `[LOG <id>]` names a row of its own root's _logs.csv, in an article or in a data row: a known
    id passes (alone or beside a source); an unknown, a malformed, a missing and another root's id each give one error."""
    from test_kb_root import SID
    own, other = log_row(0), log_row(1)
    ok = f"- A fact with a signal. [LOG {own['id']}]\n- Another. [DOC {SID}; LOG {own['id']}]\n- Wrapped. [LOG\n  {own['id']}]\n"
    assert log_check(tmp_path / "ok", [own], other=[other], article=ok, data=f"spooler,\"print/queues [LOG {own['id']}]\"\n") == (0, [])
    for n, (tag, rule) in enumerate(((f"[LOG {log_row(5)['id']}]", f"cites unknown log row {log_row(5)['id']}"),
                                     (f"[LOG {other['id']}]", f"cites log row {other['id']} of root other; a root cites only its own log rows"),
                                     ("[LOG L-AAAA]", "naming 'L-AAAA', not a log row id"),
                                     ("[LOG]", "has a LOG tag with no log row id"),
                                     (f"[DOC {SID}; LOG {log_row(6)['id']}]", f"cites unknown log row {log_row(6)['id']}"))):
        code, found = log_check(tmp_path / f"a{n}", [own], other=[other], article=f"- A signal. {tag}\n")
        assert code == 1 and len(found) == 1 and rule in found[0] and "fixture/print/queues.md" in found[0], (tag, found)
        code, found = log_check(tmp_path / f"d{n}", [own], other=[other], data=f"spooler,\"{tag}\"\n")
        assert code == 1 and len(found) == 1 and rule in found[0] and "fixture/_retrieval/signals.csv:3" in found[0], (tag, found)
    code, found = log_check(tmp_path / "ccm", [own], article="- A CCM line is `<![LOG[text]LOG]!><time=\"1\">`. [DOC " + SID + "]\n")
    assert (code, found) == (0, []), found  # the log line of a CCM client is no tag


def test_log_tag_refused_in_public_root(tmp_path):
    """A `[LOG <id>]` in an article or a data row of a public root is refused, even when the root holds the row (observed
    signals stay beside internal facts); the same tag in an internal root passes."""
    own = log_row(0)
    tag = f"[LOG {own['id']}]"
    assert log_check(tmp_path / "internal", [own], article=f"- Fact. {tag}\n") == (0, [])
    for n, kw in enumerate(({"article": f"- Fact. {tag}\n"}, {"data": f"spooler,\"{tag}\"\n"}, {"article": "- Fact. [LOG L-AAAA]\n"})):
        code, found = log_check(tmp_path / f"pub{n}", [own], visibility="public", **kw)
        assert code == 1 and len(found) == 1 and "has a LOG tag, and root fixture is public" in found[0], (kw, found)
    assert log_check(tmp_path / "pubfile", [own], visibility="public") == (0, [])  # the file itself may sit there: the projection keeps it off


def test_decision_tag_in_csv_data_row_is_resolved(tmp_path):
    """check.py resolves a `[DECISION <id>]` in a data row of a root's CSV as it does in Markdown: a known id passes; an
    unknown id, a malformed one, no id and another root's id each give one error on the row."""
    from test_kb_root import DEC, decision, did, make_root, run as run_tool
    root, other = tmp_path / "team-kb", tmp_path / "other-kb"
    make_root(str(root))
    make_root(str(other), prefix="OTH")
    meta = other / "_root.md"
    meta.write_text(meta.read_text(encoding="utf-8").replace("root: fixture", "root: other"), encoding="utf-8", newline="\n")
    for r in (root, other):
        (r / "_artifacts.csv").write_text("path,source_id,sha256\n", encoding="utf-8", newline="\n")
    kbcommon.write_csv(str(root / DEC), kbcommon.DECISION_COLS, [decision(0)])
    kbcommon.write_csv(str(other / DEC), kbcommon.DECISION_COLS, [decision(1)])
    sig = root / "_retrieval" / "signals.csv"
    base = sig.read_text(encoding="utf-8")

    def errors(tag):
        sig.write_text(base + f"spooler,\"print/queues {tag}\"\n", encoding="utf-8", newline="\n")
        code, out = run_tool("check.py", "--root", "fixture", roots=os.pathsep.join([str(root), str(other)]))
        assert "Traceback" not in out, out[-800:]
        return code, [ln for ln in out.splitlines() if ln.startswith("ERROR")]

    assert errors(f"[DECISION {did(0)}]") == (0, [])
    for tag, rule in ((f"[DECISION {did(5)}]", f"cites unknown decision {did(5)}"),
                      (f"[DECISION {did(1)}]", f"cites decision {did(1)} of root other; a root cites only its own"),
                      ("[DECISION D-AAAA]", "naming 'D-AAAA', not a decision id"),
                      ("[DECISION]", "has a DECISION tag with no decision id")):
        code, found = errors(tag)
        assert code == 1 and len(found) == 1 and rule in found[0] and "fixture/_retrieval/signals.csv:3" in found[0], (tag, found)


# ---------------------------------------------------------------- LOG lines beside the facts of a lookup (log lookup)

LOG_BLOCK = "observed signal (LOG, not a fact):"
LOG_COLS = ["id", "observation", "source_run_ids", "observed_from", "observed_to", "context", "status", "invalidated_reason",
            "links"]


def log_lookup_set(root, rows):
    """The root's _logs.csv holds these rows (None: no file; []: a header only)."""
    path = Path(root) / "_logs.csv"
    if rows is None:
        path.unlink(missing_ok=True)
    else:
        kbcommon.write_csv(str(path), LOG_COLS, rows)


def log_lookup_rows():
    """Six rows: two active ones tied to the fixture article (by `article:` and by `domain:`), and four that no lookup
    prints (proposed, invalidated, active with an `item:` only, active about another article)."""
    return [log_row(0, observation="Median 12 pack calls a day over 9 days, 3 of them weak.", context=DECISION_CONTEXT,
                    observed_to="2026-09-30"),
            log_row(1, observation="Range 2 to 8 print lookups a day over 5 days.", context="domain:print",
                    observed_from="2026-09-21", observed_to="2026-09-25"),
            log_row(2, observation="Median 7 purge questions a day over 4 days.", context=DECISION_CONTEXT, status="proposed"),
            log_row(3, observation="Median 6 spooler questions a day over 3 days.", context=DECISION_CONTEXT,
                    status="invalidated", invalidated_reason="article:print/queues was rewritten"),
            log_row(4, observation="Median 5 sprint calls a day over 2 days.", context="item:TK-abcd2345"),
            log_row(5, observation="Median 4 other calls a day over 6 days.", context="article:print/other")]


def log_lookup_ids(i):
    return log_row(i)["id"]


def log_lookup_split(text):
    """(the text without the LOG block, the block's lines): the block is the label and the `- ` lines that follow it."""
    found = re.search(r"\n\n?" + re.escape(LOG_BLOCK) + r"((?:\n- [^\n]*)+)", text)
    return (text[:found.start()] + text[found.end():], found.group(1).split("\n")[1:]) if found else (text, [])


LOG_QUESTION = "How long are finished print jobs kept on the spooler?"  # `good` from the fixture article's own facts
QUOKKA = "What do the quokka notes say about Friday or Monday?"


def test_lookup_shows_log_lines_in_pack_show_and_audit(tmp_path):
    """The active LOG rows whose context is a shown article (its `article:`, a `domain:` that holds it) print after the
    facts under `observed signal (LOG, not a fact):` with the dates they cover, in pack, show and audit; a proposed
    row, an invalidated one, one tied to an item only and one about another article never print, and a root with no
    `_logs.csv` (a header only, or only such rows) prints no block anywhere."""
    root = decision_lookup_root(tmp_path)
    cmds = {"pack": ("pack", LOG_QUESTION, "--root", "fixture"), "show": ("show", "fixture/print/queues.md:1", "-n", "40"),
            "audit": ("audit", "--root", "fixture")}
    plain = {name: decision_lookup_run(root, *cmd) for name, cmd in cmds.items()}
    assert all(LOG_BLOCK not in out for out in plain.values()), plain
    log_lookup_set(root, log_lookup_rows())
    want = [f"- fixture/_logs.csv:2 observed 2026-09-21 to 2026-09-30: Median 12 pack calls a day over 9 days, 3 of them weak. "
            f"[LOG {log_lookup_ids(0)}]",
            f"- fixture/_logs.csv:3 observed 2026-09-21 to 2026-09-25: Range 2 to 8 print lookups a day over 5 days. "
            f"[LOG {log_lookup_ids(1)}]"]
    for name, cmd in cmds.items():
        out = decision_lookup_run(root, *cmd)
        rest, block = log_lookup_split(out)
        assert block == want, (name, out)
        assert rest == plain[name], (name, "only the block is added")
        assert all(log_lookup_ids(i) not in out for i in (2, 3, 4, 5)), (name, out)
    row = decision_lookup_run(root, "show", "fixture/_logs.csv:2", "-n", "1")  # the PATH:LINE a line names is the row
    assert log_lookup_ids(0) in row and "Median 12 pack calls" in row, row
    # planted: no file, a header only, or rows nothing prints give the plain output, so the block is the difference
    for rows in (None, [], log_lookup_rows()[2:]):
        log_lookup_set(root, rows)
        for name, cmd in cmds.items():
            assert decision_lookup_run(root, *cmd) == plain[name], (rows, name)


def test_lookup_shows_log_lines_cited_fact_and_budget(tmp_path):
    """A row tied by `fact:` (a printed fact's key) or cited by a printed fact's `[LOG id]` tag prints, one about an
    `item:` alone does not; the block is capped (MAX_LOGS lines, the newest first) and paid from the pack's budget after
    the facts, so a small budget drops it first while the facts print as they do with no log row."""
    from test_kb_root import SID
    pad = " ".join(["the long grey drawer beside the old cabinet in the back room"] * 5)  # facts long enough to fill a small budget
    extra = (f"- Quokka notes are filed on Friday in {pad}. [DOC {SID}; LOG {log_lookup_ids(1)}]\n"
             f"- Quokka notes are archived on Monday in {pad}. [DOC {SID}]\n")
    root = decision_lookup_root(tmp_path, None, extra)
    unit = next(u for u in kbfacts.md_units("fixture/print/queues.md", extra) if "archived on Monday" in u["text"])
    by_fact = log_row(0, observation="Median 3 quokka questions a day over 5 days.", context=f"fact:{kbfacts.fact_key(unit['text'])}")
    by_cite = log_row(1, observation="Median 2 filing questions a day over 4 days.", context="item:TK-abcd2345")
    item_only = log_row(2, observation="Median 9 sprint calls a day over 4 days.", context="item:TK-abcd2345")
    many = [log_row(i, observation=f"Median {i} spooler calls a day over {i} days.", context="domain:print",
                    observed_to=f"2026-10-0{i}") for i in range(3, 7)]
    plain = decision_lookup_pack(root, QUOKKA)
    assert plain.startswith("coverage: good") and "Friday" in plain and "Monday" in plain, plain
    log_lookup_set(root, [by_fact, by_cite, item_only])
    rest, block = log_lookup_split(decision_lookup_pack(root, QUOKKA))
    assert rest == plain and sorted(ln.rsplit("[LOG ", 1)[1] for ln in block) == [f"{log_lookup_ids(0)}]", f"{log_lookup_ids(1)}]"], block
    # capped, newest first
    log_lookup_set(root, [by_fact, by_cite] + many)
    rest, block = log_lookup_split(decision_lookup_pack(root, QUOKKA))
    assert rest == plain and len(block) == kbfacts.MAX_LOGS == 2 and log_lookup_ids(6) in block[0], block
    # the budget: facts as without rows at every budget; the block is there at a large one and gone at a small one
    shown = {}
    for budget in ("200", "250", "300", "400", "1200"):
        log_lookup_set(root, None)
        bare = decision_lookup_pack(root, QUOKKA, "--budget", budget)
        log_lookup_set(root, [by_fact, by_cite] + many)
        rest, block = log_lookup_split(decision_lookup_pack(root, QUOKKA, "--budget", budget))
        assert rest == bare, (budget, rest, bare)
        shown[budget] = len(block)
    assert shown["1200"] == 2 and shown["200"] < shown["1200"], shown
    assert list(shown.values()) == sorted(shown.values()), f"a smaller budget never prints more LOG lines: {shown}"


def test_log_not_counted_in_coverage(tmp_path):
    """An active LOG row whose words would answer a question changes neither the coverage line, the route lines, the
    `check:` lines nor the fact lines, whatever the verdict (good, weak, none); where the verdict is `none` and routes
    to the web the pack prints no block. A decision with the same words does lift the verdict (planted), so the
    comparison can fail."""
    from test_kb_root import decision
    root = decision_lookup_root(tmp_path)
    questions = {"none": DECISION_QUESTION, "good": LOG_QUESTION,
                 "weak": "How long are finished print jobs kept for approval of the queue pattern?"}
    answering = [log_row(0, observation="Print owner approves an early purge of print queues in 3 of 5 cases.",
                         context=DECISION_CONTEXT),
                 log_row(1, observation="Finished print jobs are kept for approval of the queue pattern in 7 of 9 cases.",
                         context="domain:print")]
    seen = set()
    for name, question in questions.items():
        log_lookup_set(root, None)
        base = decision_lookup_pack(root, question)
        log_lookup_set(root, answering)
        got = decision_lookup_pack(root, question)
        seen.add(base.splitlines()[0].split(" ")[1])
        rest, block = log_lookup_split(got)
        assert rest == base, (name, got, base)  # every line of coverage, check:, route, kb has/lacks and the facts
        assert (block != []) == (not base.startswith("coverage: none")), (name, got)
        lines = ("coverage:", "check:", "route:", "kb has:", "kb lacks:")
        assert [ln for ln in got.splitlines() if ln.startswith(lines)] == [ln for ln in base.splitlines() if ln.startswith(lines)]
    assert seen == {"none", "good", "weak"}, f"the three verdicts are covered: {seen}"
    # planted: an active decision with the same words does change the coverage
    log_lookup_set(root, answering)
    decision_lookup_set(root, [decision(0, text=DECISION_TEXT, context=DECISION_CONTEXT)])
    assert decision_lookup_pack(root, DECISION_QUESTION).startswith("coverage: good (an active decision answers it;")


def test_log_not_counted_in_coverage_tag_is_no_evidence(tmp_path):
    """`LOG` is a kind kbfacts parses (the id is the part's `log`, never one of its source `ids`), and a `[LOG id]` tag
    is no evidence: a fact carrying only it has no tag, one that also carries `[DOC id]` counts once as DOC, and
    audit's counts and a pack's verdict are those of the fact without the LOG tag."""
    import check
    assert kbfacts.LOG_ID.pattern == check.LOG_ID.pattern and kbfacts.LOG_FILE == check.LOGS
    assert "LOG" in kbfacts.KINDS and "LOG" not in kbfacts.EVIDENCE_KINDS
    part = kbfacts.parse_tag("[LOG L-aaaaaaaa]")[0]
    assert (part["kind"], part["ids"], part["log"], part["note"]) == ("LOG", [], "L-aaaaaaaa", "")
    parts = kbfacts.parse_tag("[DOC S1208; LOG L-aaaaaaab: seen twice]")
    assert [(p["kind"], p["ids"], p.get("log"), p["note"]) for p in parts] == [
        ("DOC", ["S1208"], None, ""), ("LOG", [], "L-aaaaaaab", "seen twice")]
    for bad in ("[LOG]", "[LOG L-AAAA]", "[LOG S1208]", "[LOG L-aaaaaaaa9]"):
        assert kbfacts.parse_tag(bad)[0]["log"] == "", bad
    only = kbfacts.md_units("fixture/print/queues.md", "- Quokka notes are filed on Friday. [LOG L-aaaaaaaa]\n")[0]
    assert only["tags"] == [] and kbfacts.log_ids_in(only["text"]) == ["L-aaaaaaaa"], only
    both = kbfacts.md_units("fixture/print/queues.md", "- Quokka notes are filed on Friday. [DOC S1208; LOG L-aaaaaaaa]\n")[0]
    assert kbfacts.kinds_of(both["tags"]) == ["DOC"] and kbfacts.log_ids_in(both["text"]) == ["L-aaaaaaaa"], both
    assert [p["kind"] for p in kbfacts.tags_in("[LOG L-aaaaaaaa] [DER S1: how]")] == ["DER"]
    # the pack of a question only a LOG-tagged fact answers is no `good`; the same fact tagged DOC is (planted)
    from test_kb_root import SID
    question = "What do the quokka notes say about Friday?"
    logged = decision_lookup_root(tmp_path / "a", None, f"- Quokka notes are filed on Friday. [LOG {log_lookup_ids(0)}]\n")
    docs = decision_lookup_root(tmp_path / "b", None, f"- Quokka notes are filed on Friday. [DOC {SID}]\n")
    got, want = decision_lookup_pack(logged, question), decision_lookup_pack(docs, question)
    assert want.startswith("coverage: good") and not got.startswith("coverage: good"), (got, want)
    # audit counts: the LOG tag adds no fact and no kind
    both_root = decision_lookup_root(tmp_path / "c", None, f"- Quokka notes are filed on Friday. [DOC {SID}; LOG {log_lookup_ids(0)}]\n")
    plain_root = decision_lookup_root(tmp_path / "d", None, f"- Quokka notes are filed on Friday. [DOC {SID}]\n")
    rows = [decision_lookup_run(r, "audit", "--root", "fixture", "--format", "concise") for r in (both_root, plain_root)]
    assert rows[0] == rows[1] and "LOG" not in rows[0], rows
