"""The kb's own checks: documentation cohesion, deterministic lookup, ids and leak detection (`python3 _tools/tests.py`
runs them with every other test module).

TestToolChecks, TestCohesion: check.py and fetch.py --offline pass; no lint errors beyond the recorded baseline; the
generated index files (_coverage.csv, README coverage table, used_in) are up to date (build_index.py --check); links,
backtick paths and used_in paths resolve; every CLI flag the docs mention exists in that tool; the docs servers' .mcp.json (.claude-plugin/it-ops-kb-docs/), .claude/settings.json and AGENTS.md agree;
skills are well-formed and only /kb-lookup is model-invocable; AGENTS.md stays under 4 KB
(every session and subagent loads it; maintainer rules live in MAINTAINING.md); `ruff check` is clean (pyproject.toml).
TestLookup (deterministic retrieval): kbfacts.py parses tag variants and ledger topic markers one way; `rag.py eval` passes
every question of _tools/lookup_eval.csv (expected article in the pack, right coverage verdict); the kb: hook blocks
a covered question, forwards an uncovered one with the pack, and leaves other prompts alone.
TestIds: kbid.py hash source ids are deterministic and normalization-stable; bad ids and answer-id clashes are caught.
TestLeaks (tracked files): secrets in any file; in authored files also home-directory paths, private IPv4 addresses,
non-placeholder e-mail addresses and GUIDs outside the reviewed allowlist (_tools/tests_allowlist.txt); files that
must never be committed; oversized files.
"""
import csv, functools, glob, json, os, re, subprocess, sys

import pytest

import kbfacts, kbid
from conftest import KB, TOOLS

LINT = os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py")
BASELINE = os.path.join(TOOLS, "lint_baseline.txt")
ALLOWLIST = os.path.join(TOOLS, "tests_allowlist.txt")
MAX_BYTES = 10 * 1024 * 1024
# the benchmark's false good (agent_bench s8): the pack matched Copilot Studio's "data-loss-prevention (DLP)" words
FALSE_GOOD = "Microsoft Purview Data Loss Prevention endpoint DLP onboarding requirements"


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=KB, capture_output=True, text=True, errors="replace")
    return p.returncode, p.stdout + p.stderr


@functools.lru_cache(maxsize=None)
def tracked():
    """Tracked files (git ls-files), or every file outside ignored dirs when git is unavailable (read once per run)."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=KB, capture_output=True, check=True).stdout
        return tuple(sorted(f for f in out.decode().split("\0") if f))
    except (OSError, subprocess.CalledProcessError):
        out = []
        for root, dirs, files in os.walk(KB):
            dirs[:] = [d for d in dirs if d not in {".git", "_cache", "_private", "__pycache__"}]
            out += [os.path.relpath(os.path.join(root, f), KB) for f in files]
        return tuple(sorted(out))


@functools.lru_cache(maxsize=None)
def text(rel):
    try:
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def pinned():
    with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8-sig", newline="") as f:
        return {r["path"] for r in csv.DictReader(f)}


@functools.lru_cache(maxsize=None)
def authored():
    """Tracked text files we wrote ourselves: not pinned artifacts and not vendor exports under */artifacts/."""
    p = pinned()
    return tuple(f for f in tracked() if f not in p and "/artifacts/" not in f and text(f) is not None)


def allowlist():
    out = {}
    if os.path.exists(ALLOWLIST):
        with open(ALLOWLIST, encoding="utf-8") as f:
            lines = f.read().splitlines()
        for ln in lines:
            ln = ln.split("#", 1)[0].strip()
            if ln:
                kind, value = ln.split(None, 1)
                out.setdefault(kind, set()).add(value.strip().lower())
    return out


def lint_errors():
    code, out = run(LINT)
    return {ln.strip() for ln in out.splitlines() if ln.startswith("ERROR")}


# urls, including git remotes: ssh:// and the scp-like `git@host:path` form, and `ssh [-opts] git@host` (a remote or an
# ssh login, not an e-mail address)
URL_RX = re.compile(r"(?:https?|ssh|git)://\S+|(?<![\w.%+-])git@[\w.-]+:[\w./~-]+|\bssh(?:\s+-\w+)*\s+git@[\w.-]+")


def hits(pattern, files, flags=0, strip_urls=False):
    rx = re.compile(pattern, flags)
    found = []
    for f in files:
        t = text(f)
        if t is None:
            continue
        for n, ln in enumerate(t.splitlines(), 1):
            src = URL_RX.sub("", ln) if strip_urls else ln
            for m in rx.finditer(src):
                found.append((f, n, m.group(0)))
    return found


def fmt(found, limit=20):
    return "\n".join(f"  {f}:{n}: {v}" for f, n, v in found[:limit]) + (f"\n  ... +{len(found) - limit}" if len(found) > limit else "")


DOCS = ["README.md", "AGENTS.md", "MAINTAINING.md"] + sorted(os.path.relpath(p, KB) for p in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")))


class TestToolChecks:
    def test_check_py_passes(self):
        code, out = run(os.path.join(TOOLS, "check.py"))
        assert code == 0, out[-3000:]

    def test_pinned_artifacts_match(self):
        code, out = run(os.path.join(TOOLS, "fetch.py"), "--offline")
        assert code == 0, out[-3000:]

    def test_no_new_lint_errors(self):
        known = set()
        if os.path.exists(BASELINE):
            with open(BASELINE, encoding="utf-8") as f:
                known = {ln.strip() for ln in f if ln.strip()}
        now = lint_errors()
        new = sorted(now - known)
        fixed = sorted(known - now)
        if fixed:
            print(f"\nnote: {len(fixed)} baseline lint error(s) are fixed; refresh with tests.py --write-lint-baseline", file=sys.stderr)
        assert not new, "new lint errors (fix them, or accept deliberately with --write-lint-baseline):\n" + "\n".join(new[:30])


class TestCohesion:
    def test_generated_indexes_up_to_date(self):
        """_coverage.csv, the README coverage table and used_in are generated; a hand edit or a missed rebuild fails."""
        code, out = run(os.path.join(TOOLS, "build_index.py"), "--check")
        assert code == 0, "generated index files are out of date; run python3 _tools/build_index.py\n" + out[-3000:]

    def test_markdown_links_resolve(self):
        bad = []
        for f in [x for x in authored() if x.endswith(".md")] + [x for x in DOCS if x not in authored()]:
            t = re.sub(r"```.*?```|`[^`\n]*`", "", text(f) or "", flags=re.S)
            for link in re.findall(r"\]\(([^)\s]+)\)", t):
                if re.match(r"[a-z][a-z0-9+.-]*:", link) or link.startswith("#"):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(KB, os.path.dirname(f), link.split("#")[0]))):
                    bad.append((f, 0, link))
        assert not bad, "broken relative links:\n" + fmt(bad)

    def test_backtick_paths_resolve(self):
        roots = {d for d in os.listdir(KB) if os.path.isdir(os.path.join(KB, d))}
        allow = allowlist().get("path", set())
        bad = []
        for f in [x for x in authored() if x.endswith(".md")] + DOCS:
            for ref in set(re.findall(r"`((?:[\w.-]+/)+[\w.-]+\.(?:md|csv|ya?ml|json|xml|py|ts|proto|txt))`", text(f) or "")):
                top = ref.split("/")[0]
                if top in roots and ref.lower() not in allow and not os.path.exists(os.path.join(KB, ref)) \
                        and not os.path.exists(os.path.join(KB, os.path.dirname(f), ref)):
                    bad.append((f, 0, ref))
        assert not bad, "backtick paths that do not exist:\n" + fmt(bad)

    def test_used_in_paths_exist(self):
        with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
            bad = [(r["id"], 0, u) for r in csv.DictReader(f)
                   for u in filter(None, (x.strip() for x in (r.get("used_in") or "").split(";")))
                   if not os.path.exists(os.path.join(KB, u))]
        assert not bad, "_sources.csv used_in names missing files:\n" + fmt(bad)

    def test_documented_flags_exist(self):
        """Every --flag written next to a tool in the docs must appear in that tool's source."""
        bad = []
        for f in DOCS:
            for n, ln in enumerate((text(f) or "").splitlines(), 1):
                for m in re.finditer(r"((?:_tools|\.claude/skills/[\w-]+)/[\w-]+\.py)([^|`\n]*)", ln):
                    tool = os.path.join(KB, m.group(1))
                    if not os.path.exists(tool):
                        bad.append((f, n, f"{m.group(1)} does not exist"))
                        continue
                    src = text(m.group(1))
                    for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]+", m.group(2)):
                        if f'"{flag}"' not in src and f"'{flag}'" not in src and flag not in src.split('"""')[1]:
                            bad.append((f, n, f"{m.group(1)} {flag}"))
        assert not bad, "documented flags missing from the tool:\n" + fmt(bad)

    def test_mcp_config_consistent(self):
        servers = json.loads(text(".claude-plugin/it-ops-kb-docs/.mcp.json"))["mcpServers"]
        settings = json.loads(text(".claude/settings.json"))
        assert "enabledMcpjsonServers" not in settings, "no root .mcp.json: a clone registers the servers at local scope"
        table = dict(re.findall(r"^\s*\| `([\w-]+)` \| `(https://[^`]+)` \|", text("AGENTS.md"), re.M))
        assert table == {k: v["url"] for k, v in servers.items()}, "AGENTS.md server table != the docs .mcp.json"
        known = set(servers) | {"kb"}  # kb: the clone's local-scope kb server (kb_mcp.py --register-local)
        perms = settings.get("permissions", {})
        for rule in perms.get("allow", []):
            m = re.match(r"mcp__([\w-]+?)(?:__|$)", rule)
            if m:
                assert m.group(1) in known, f"allow rule {rule} names an unknown server"
                assert "__" in rule[5:] or m.group(1) == "kb", f"{rule}: only the read-only kb server is allowed whole"
            assert "submit_feedback" not in rule, "submit_feedback must never be allowed"
            assert not (rule.startswith("mcp__") and rule.endswith("__*") and rule[5:-3] in ("claude-code-docs", "mcp-docs")), \
                             f"{rule} would allow submit_feedback"
        for s in ("claude-code-docs", "mcp-docs"):
            if s in servers:
                assert f"mcp__{s}__submit_feedback" in perms.get("deny", [])
        for s, v in servers.items():
            assert v.get("url", "").startswith("https://"), f"{s}: not an https url"
            assert "headers" not in v, f"{s}: shared config must not carry headers (credentials belong in user scope)"

    def test_skills_well_formed(self):
        skills = sorted(glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")))
        assert skills, "no skills found"
        for p in skills:
            t = text(os.path.relpath(p, KB))
            assert t.startswith("---\n"), f"{p}: no front matter"
            fm = t.split("\n---", 1)[0]
            name = re.search(r"^name:\s*(\S+)", fm, re.M)
            assert name and name.group(1) == os.path.basename(os.path.dirname(p)), f"{p}: name must equal its directory"
            assert re.search(r"(?m)^description:\s*\S.{20,}", fm), f"{p}: description missing or too short"
            assert os.path.basename(os.path.dirname(p)) in text("AGENTS.md"), f"{p}: skill not listed in AGENTS.md"
            if os.path.basename(os.path.dirname(p)) != "kb-lookup":  # its description would load into every session
                assert re.search(r"(?m)^disable-model-invocation: true$", fm), f"{p}: only /kb-lookup is model-invocable"

    def test_python_passes_ruff_when_installed(self):
        """pyflakes rules (pyproject.toml [tool.ruff]): no unused or undefined names; skipped without ruff."""
        try:
            p = subprocess.run([sys.executable, "-m", "ruff", "check", "--output-format", "concise", "."], cwd=KB,
                               capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            pytest.skip("ruff not runnable")
        if "No module named ruff" in p.stderr:
            pytest.skip("ruff is not installed (dev group in pyproject.toml)")
        assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-1000:]

    def test_claude_md_imports_agents_md(self):
        assert "@AGENTS.md" in (text("CLAUDE.md") or "")
        assert "MAINTAINING.md" not in (text("CLAUDE.md") or ""), "MAINTAINING.md is read on demand, never imported"

    def test_agents_md_stays_small(self):
        size = len((text("AGENTS.md") or "").encode())
        assert size <= 4096, f"AGENTS.md is {size} bytes: it loads into every session and subagent; " \
                                         "move maintainer detail to MAINTAINING.md"
        for s in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")):
            if os.path.basename(os.path.dirname(s)) not in ("kb-lookup", "kb-review-workspace"):  # read-only skills
                assert "MAINTAINING.md" in text(os.path.relpath(s, KB)), f"{s}: a skill that changes the kb must point to MAINTAINING.md"


class TestLookup:
    def test_search_finds_the_expected_article(self):
        """rag.py search (kb_search): the article that answers each query is in its top 5. The baseline any change to
        the search engine must keep (plan-tooling-efficiency.md R3), including prose and, with --index, the root
        ledgers that the pack index does not hold."""
        import rag
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
            assert want in paths, f"search {query!r}: {paths}"

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

    def test_ledger_topic_markers_link_entries(self):
        import kbfacts
        e = kbfacts.link_entries([{"file": "_gaps.md", "line": 1, "end": 1, "section": "x", "text": "a gap (topic: auth/kerberos)"}])[0]
        assert e["explicit"] == ["auth/kerberos"]
        rows = {r["topic"]: r for r in kbfacts.audit("agents/shared-ner-service")}
        assert rows["agents/shared-ner-service"]["gaps"], "shared-ner-service's named gap entries are not linked"

    def test_alias_and_signal_tables(self):
        import kbfacts
        for name, cols in (("aliases.csv", ["term", "canonical"]), ("signals.csv", ["signal", "topic"])):
            with open(os.path.join(TOOLS, name), encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            assert rows[0] == cols, name
            keys = [r[0].lower() for r in rows[1:]]
            assert len(keys) == len(set(keys)), f"{name}: duplicate {cols[0]}"
            for r in rows[1:]:
                assert len(r) == 2, f"{name}: {r}"
                assert r[0].strip() and r[1].strip(), f"{name}: {r}"
        topics = set(kbfacts.topic_files())
        bad = [r["signal"] for r in csv.DictReader(open(os.path.join(TOOLS, "signals.csv"), encoding="utf-8")) if r["topic"] not in topics]
        assert not bad, f"signals.csv names topics that do not exist: {bad}"
        for r in csv.DictReader(open(os.path.join(TOOLS, "aliases.csv"), encoding="utf-8")):
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
        path = os.path.join(TOOLS, "doc2query", "expansions.csv")
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
        with open(os.path.join(TOOLS, "lookup_eval.csv"), encoding="utf-8", newline="") as f:
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

    def test_kb_ask_routes(self):
        def ask(q, *flags, env=None):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_ask.py"), *flags, q], capture_output=True,
                               text=True, cwd=KB, timeout=60, env=env)
            return p.returncode, p.stdout, p.stderr
        bitlocker = "Does deleting an Entra device also delete its BitLocker recovery keys?"
        code, out, err = ask(bitlocker, "--route")
        assert code == 0 and out.startswith("kind=good verdict=good parts=1 model=haiku"), out + err
        code, out, _ = ask("What is the Intel Wi-Fi Roaming Aggressiveness setting?", "--route")
        assert out.startswith("kind=weak") and "model=sonnet" in out, out
        assert "model=opus" in ask("Intel Wi-Fi roaming", "--route", "--model", "opus")[1]
        assert "entra/bitlocker-key-deletion.md:" in ask(bitlocker, "--no-model")[1], "a good pack without a model"
        # counts and 'who cites' go to the audit and source tools, never to a model
        assert ask("How many intune articles are partial?", "--route")[1].startswith("kind=tool")
        out = ask("How many intune articles in the kb have status partial?")[1]
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

    def test_kb_ask_without_claude_prints_the_evidence(self):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_ask.py"), "What is the default Windows LAPS password length?"],
                           capture_output=True, text=True, cwd=KB, timeout=60, env={"PATH": os.path.dirname(sys.executable)})
        assert p.returncode == 2 and p.stdout.startswith("coverage: good") and "windows/laps.md:" in p.stdout, p.stdout + p.stderr

    def test_kb_hook(self):
        def hook(prompt):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps({"prompt": prompt}),
                               capture_output=True, text=True, cwd=KB, timeout=60)
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
        assert line.startswith("it-ops-kb has no coverage for: ") and "Roaming" in line, line
        assert "\n" not in line, "coverage none: one line, not the pack"
        p = subprocess.run([sys.executable, "-c", "import sys, kb_hook; kb_hook.answer('fix the build'); "
                            "sys.exit('kbfacts' in sys.modules)"], cwd=TOOLS, capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, "a prompt without kb: must return before kbfacts is loaded"
        forward = hook("kb+: Does deleting an Entra device also delete its BitLocker recovery keys?")
        assert forward["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        # a good pack whose lead article never names the product asked about (a false good) goes to the model
        flagged = hook("kb: " + FALSE_GOOD)
        assert "decision" not in flagged, "a good pack with a check: line must not be answered without the model"
        ctx = flagged["hookSpecificOutput"]["additionalContext"]
        assert "coverage: good" in ctx and "\ncheck: " in ctx and "Purview" in ctx, ctx[:400]

    def test_false_good_gets_a_check_line(self):
        res = kbfacts.pack(FALSE_GOOD)
        assert res["verdict"] == "good" and res["unmatched"] == ["purview"], (res["verdict"], res["unmatched"])
        assert res["text"].splitlines()[1].startswith("check: ") and "never mentions Purview" in res["text"]
        # the names an article holds only in its title or applies_to (SQL Server for sp_getapplock) count as held,
        # and two-letter names (AV, PC) are never flagged
        for q in ("What does sp_getapplock do in SQL Server and what lock modes does it take?",
                  "Does deleting an Entra device also delete its BitLocker recovery keys?"):
            res = kbfacts.pack(q)
            assert res["verdict"] == "good" and not res["unmatched"] and "\ncheck: " not in res["text"], (q, res["unmatched"])


class TestIds:
    URL = "https://learn.microsoft.com/en-us/windows/security/example"

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
        assert [kbid.canonical_id(x) for x in ("s0100", "s-K3F7Q2ZD")] == ["S0100", "S-k3f7q2zd"]

    def test_answer_ids(self):
        assert kbid.answer_id("How does Dataverse sync with an on-prem SQL Server?") == "QK-dataverse-sync-prem-sql-server"
        assert re.search(kbid.QK_ID.pattern, kbid.answer_id("???"))
        ids = kbid.answer_ids("## Q1. a\n## QK-x-y. b\n## QK-x-y. c\n### Q2. no\n## QG1 (no dot)\n")
        assert ids == ["Q1", "QK-x-y", "QK-x-y"]
        real = kbid.answer_ids(text("_answers.md") or "")
        assert len(real) == len(set(real)), "duplicate answer ids in _answers.md"


class TestLeaks:
    SECRETS = [
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY-----",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bgh[pousr]_[A-Za-z0-9]{36}\b", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b",
        r"\bglpat-[A-Za-z0-9_-]{20,}\b", r"\bglrt-[A-Za-z0-9_-]{20,}\b",
        r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
        r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b",
        r"AccountKey=[A-Za-z0-9+/]{40,}={0,2}", r"[?&]sig=[A-Za-z0-9%+/]{30,}",
        r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        r"(?i)\b(?:password|passwd|pwd|client_secret|api_key|apikey|secret)\b\s*[:=]\s*[\"'][^\"'\s<>${}]{8,}[\"']",
    ]

    def test_no_secrets(self):
        allow = allowlist().get("secret", set())
        files = [f for f in tracked() if text(f) is not None]
        rx = "|".join(f"(?i:{p[4:]})" if p.startswith("(?i)") else f"(?:{p})" for p in self.SECRETS)  # one pass per file
        found = [h for h in hits(rx, files) if h[2].lower() not in allow]
        assert not found, "possible secrets:\n" + fmt(found)

    def test_no_home_paths(self):
        found = hits(r"(?:/Users/|/home/|[A-Za-z]:\\+Users\\+)(?!<)[A-Za-z][\w.-]+", authored())
        generic = ("public", "default", "all users", "username", "user", "administrator")
        found = [h for h in found if re.split(r"[/\\]+", h[2])[-1].lower() not in generic]
        assert not found, "machine-specific home paths:\n" + fmt(found)

    def test_no_private_ipv4(self):
        allow = allowlist().get("ip", set())
        rx = r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![\w.])"
        found = [h for h in hits(rx, authored(), strip_urls=True) if h[2] not in allow
                 and all(int(x) < 256 for x in h[2].split("."))]
        assert not found, "private IPv4 addresses (use 192.0.2.x/198.51.100.x/203.0.113.x, or allowlist):\n" + fmt(found)

    def test_no_real_email_addresses(self):
        allow = allowlist().get("email", set())
        found = [h for h in hits(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b", authored(), strip_urls=True)
                 if not re.search(r"(?i)@([\w-]+\.)*example\.(com|org|net)$|@noreply\.|@users\.noreply\.github\.com$", h[2])
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
        found = [h for h in hits(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", md, strip_urls=True)
                 if not re.fullmatch(r"0{8}-0{4}-0{4}-0{4}-0{8}[0-9a-f]{4}", h[2].lower()) and h[2].lower() not in allow]
        assert not found, "GUIDs in prose that are neither placeholders nor reviewed public ids " \
                                "(tenant/object ids leak; add public ones to _tools/tests_allowlist.txt with a reason):\n" + fmt(found)

    def test_no_forbidden_files_tracked(self):
        rx = re.compile(r"(^|/)(_cache|_private|__pycache__)/|(^|/)\.env(\.|$)|\.(pem|key|pfx|p12|kdbx|tmp)$|(^|/)id_(rsa|ed25519)|(^|/)\.DS_Store$")
        bad = [f for f in tracked() if rx.search(f)]
        assert not bad, "files that must not be committed:\n  " + "\n  ".join(bad)

    def test_no_oversized_files(self):
        big = [(f, os.path.getsize(os.path.join(KB, f))) for f in tracked() if os.path.getsize(os.path.join(KB, f)) > MAX_BYTES]
        assert not big, f"files over {MAX_BYTES // 2**20} MB:\n" + "\n".join(f"  {f}: {s} bytes" for f, s in big)

