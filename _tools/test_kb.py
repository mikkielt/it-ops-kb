"""The kb's own checks: documentation cohesion, deterministic lookup, ids and leak detection (`python3 _tools/tests.py`
runs them with every other test module).

TestToolChecks, TestCohesion: check.py and fetch.py --offline pass; no lint errors beyond the recorded baseline; the
generated index files (every root's _coverage.csv, _coverage.md table and used_in) are up to date (build_index.py --check); links,
backtick paths and used_in paths resolve; every CLI flag the docs mention exists in that tool; the docs servers' .mcp.json (.claude-plugin/it-ops-kb-docs/), .claude/settings.json and AGENTS.md agree;
skills are well-formed; of the plugin skills only /kb-lookup is model-invocable, and the clone-only change skills all are
(a change request must reach them); the change router hook routes change prompts; AGENTS.md stays under 4 KB (every session and subagent
loads it; maintainer rules live in kb/_self/maintaining.md) and README.md under 8 KB (people read it); kb/_self/map.csv names
every _self doc and matches files (selfdoc.py check); `ruff check` is clean (pyproject.toml).
TestSelfDocs: kb/_self/ stays out of the pack and the default search, and a search with index finds it.
TestLookup (deterministic retrieval): kbfacts.py parses tag variants and ledger topic markers one way; `rag.py eval` passes
every question of kb/public/_retrieval/lookup_eval.csv (expected article in the pack, right coverage verdict); the kb: hook blocks
a covered question, forwards an uncovered one with the pack, and leaves other prompts alone.
TestIds: kbid.py hash source ids are deterministic and normalization-stable; bad ids and answer-id clashes are caught.
TestLeaks (tracked files): secrets in any file; in authored files (not those of `visibility: internal` roots) also home-directory paths, private IPv4 addresses,
non-placeholder e-mail addresses and GUIDs outside the reviewed allowlist (_tools/tests_allowlist.txt); files that
must never be committed; oversized files.
"""
import csv, functools, glob, json, os, re, subprocess, sys

import pytest

import kb_hook, kbcommon, kbfacts, kbid
from conftest import KB, P, SELF_REL, TOOLS, copy_kb, querylog_env

PUBLIC = kbcommon.PUBLIC  # the public root: ledgers, articles, retrieval data (KB here is the repository)
SELF = kbcommon.SELF

LINT = os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py")
BASELINE = os.path.join(TOOLS, "lint_baseline.txt")
ALLOWLIST = os.path.join(TOOLS, "tests_allowlist.txt")
MAX_BYTES = 10 * 1024 * 1024
PLUGIN_SKILLS = {os.path.basename(s.rstrip("/")) for s in json.load(open(os.path.join(KB, ".claude-plugin", "plugin.json"),
                                                                        encoding="utf-8"))["skills"]}
# the benchmark's false good (agent_bench s8): the pack matched Copilot Studio's "data-loss-prevention (DLP)" words
FALSE_GOOD = "How do I integrate ServiceNow with Intune?"  # ServiceNow is held by a Copilot connector line only
SPREAD_GOOD = "Which Graph API migrates mailboxes, calendars and contacts between tenants?"


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
            dirs[:] = [d for d in dirs if d not in {".git", "_cache", "_private", "__pycache__", ".venv", ".pytest_cache",
                                                    ".ruff_cache", ".uv-cache", "node_modules"}]  # never scan installed packages
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
    """Repository paths of every root's pinned artifacts."""
    out = set()
    for r in kbcommon.roots():
        with open(os.path.join(r.path, kbcommon.ARTIFACTS), encoding="utf-8-sig", newline="") as f:
            out |= {kbcommon.repo_rel(x["path"], r.path) for x in csv.DictReader(f)}
    return out


def internal_prefixes():
    """Repository path prefixes of the roots marked `visibility: internal`: they may hold real names and addresses."""
    return tuple(kbcommon.repo_rel(".", r.path) + "/" for r in kbcommon.roots() if r.visibility != "public")


@functools.lru_cache(maxsize=None)
def authored():
    """Tracked text files we wrote ourselves that the placeholders-only rule covers: not pinned artifacts, not vendor
    exports under */artifacts/ or snapshots of copy sources under */_snapshots/, not files of internal roots (secrets are
    checked everywhere: test_no_secrets)."""
    p, internal = pinned(), internal_prefixes()
    return tuple(f for f in tracked() if f not in p and "/artifacts/" not in f and f"/{kbcommon.SNAPSHOTS}/" not in f
                 and not f.startswith(internal) and text(f) is not None)


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


# the docs held to the code: the root docs, the kb/_self/ docs and the skills; flags in kb/_self/reports/ are not checked, since a
# report shows the command lines a measurement ran
DOCS = ["README.md", "AGENTS.md"] + sorted(os.path.relpath(p, KB) for p in glob.glob(os.path.join(SELF, "*.md"))) \
    + sorted(os.path.relpath(p, KB) for p in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")))


class TestToolChecks:
    def test_check_py_passes(self):
        code, out = run(os.path.join(TOOLS, "check.py"))
        assert code == 0, out[-3000:]

    def test_check_py_reads_a_tag_wrapped_after_its_kind(self, tmp_path):
        # `[DOC\n  S-id]` (a fact wrapped by the editor) must still be checked for unknown ids
        d = copy_kb(str(tmp_path / "kb"))
        with open(os.path.join(d, P("auth/kerberos.md")), "a", encoding="utf-8", newline="\n") as f:
            f.write("\n- A wrapped fact. [DOC\n  S-zzzzzzzz]\n")
        p = subprocess.run([sys.executable, os.path.join(d, "_tools", "check.py")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert "auth/kerberos.md cites unknown source S-zzzzzzzz" in p.stdout, p.stdout[-2000:]

    def test_check_py_reads_source_columns_of_data_csvs(self, tmp_path):
        d = copy_kb(str(tmp_path / "kb"))
        with open(os.path.join(d, P("auth/threats.csv")), "a", encoding="utf-8", newline="\n") as f:
            f.write("X,y,z,S3 bucket and S-1-5-18 are not ids here,S-zzzzzzzz\n")
        p = subprocess.run([sys.executable, os.path.join(d, "_tools", "check.py")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert "cites unknown source S-zzzzzzzz" in p.stdout and "S3" not in p.stdout.split("cites unknown source")[-1], p.stdout[-2000:]

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
    def test_session_start_names_the_focused_gate(self):
        """The cloud SessionStart notice states the gate as maintaining.md does (kbgit.py sync with tests.py --changed),
        not the old full gate run before every commit."""
        with open(os.path.join(KB, ".claude", "hooks", "session_start.py"), encoding="utf-8") as f:
            text = f.read()
        assert "tests.py --changed" in text and "kbgit.py sync --push" in text
        assert "about 60 s" not in text and "stress_test.py (~35 s)" not in text


    def test_generated_indexes_up_to_date(self):
        """_coverage.csv, the _coverage.md table and used_in are generated; a hand edit or a missed rebuild fails."""
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
        roots = {d for base in (KB, PUBLIC) for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))} \
            - {"_private", "_cache"}
        allow = allowlist().get("path", set())
        bad = []
        for f in [x for x in authored() if x.endswith(".md")] + DOCS:
            for ref in set(re.findall(r"`((?:[\w.-]+/)+[\w.-]+\.(?:md|csv|ya?ml|json|xml|py|ts|proto|txt))`", text(f) or "")):
                top = ref.split("/")[0]
                if top in roots and ref.lower() not in allow and not os.path.exists(os.path.join(KB, ref)) \
                        and not os.path.exists(os.path.join(PUBLIC, ref)) \
                        and not os.path.exists(os.path.join(KB, os.path.dirname(f), ref)):
                    bad.append((f, 0, ref))
        assert not bad, "backtick paths that do not exist:\n" + fmt(bad)

    def test_used_in_paths_exist(self):
        with open(os.path.join(PUBLIC, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
            bad = [(r["id"], 0, u) for r in csv.DictReader(f)
                   for u in filter(None, (x.strip() for x in (r.get("used_in") or "").split(";")))
                   if not os.path.exists(os.path.join(PUBLIC, u))]
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
        live = text("AGENTS.md").split("## Live documentation", 1)[1].split("\n## ", 1)[0]
        named = set(re.findall(r"`([\w-]+)` for ", live))
        assert named == set(servers), "AGENTS.md docs servers != the docs .mcp.json"
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

    def test_powershell_rules_mirror_bash(self):
        """On Windows Claude Code runs shell commands through the PowerShell tool, and a Bash(...) rule never covers a
        PowerShell call (public/claude/powershell-tool.md): each allowed read-only command has both rules."""
        allow = json.loads(text(".claude/settings.json")).get("permissions", {}).get("allow", [])
        bash = {r[len("Bash("):-1] for r in allow if r.startswith("Bash(")}
        ps = {r[len("PowerShell("):-1] for r in allow if r.startswith("PowerShell(")}
        assert bash and bash == ps, f"Bash only: {sorted(bash - ps)}; PowerShell only: {sorted(ps - bash)}"

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
            name = os.path.basename(os.path.dirname(p))
            manual = bool(re.search(r"(?m)^disable-model-invocation: true$", fm))
            if name in PLUGIN_SKILLS:  # shipped to hosts: a description there loads into every host session
                assert manual == (name != "kb-lookup"), f"{p}: of the plugin skills only /kb-lookup is model-invocable"
            else:  # clone-only skills that change the kb: Claude must reach them when a person asks for a change
                assert not manual, f"{p}: a skill that changes the kb must stay model-invocable (disable-model-invocation)"
                assert fm.split("description:", 1)[1].lstrip().startswith("Use "), f"{p}: description must start with its trigger (Use when ...)"

    def test_python_passes_ruff_when_installed(self):
        """pyflakes rules (pyproject.toml [tool.ruff]): no unused or undefined names; skipped without ruff."""
        try:
            p = subprocess.run([sys.executable, "-m", "ruff", "check", "--output-format", "concise", "."], cwd=KB,
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
        except (OSError, subprocess.SubprocessError):
            pytest.skip("ruff not runnable")
        if "No module named ruff" in p.stderr:
            pytest.skip("ruff is not installed (dev group in pyproject.toml)")
        assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-1000:]

    def test_claude_md_imports_agents_md(self):
        assert "@AGENTS.md" in (text("CLAUDE.md") or "")
        assert "kb/_self/" not in (text("CLAUDE.md") or ""), "kb/_self/ docs are read on demand, never imported"

    OLD_NONE = ("say the kb does not cover it", "Say so. Do not fill the gap from memory", "say so and add nothing from memory",
                "say so, or research it with /kb-research")

    @staticmethod
    def none_rule_problems(texts, instructions, agents_md):
        """The none rule in each text it lives in (name -> text): what the kb has and lacks, the live docs for the rest,
        never from memory, none of the old wordings; AGENTS.md and the server instructions within their sizes."""
        out = []
        for name, body in texts.items():
            out += [f"{name}: old wording {old!r}" for old in TestCohesion.OLD_NONE if old in body]
            out += [f"{name}: lacks {need!r}" for need in ("lacks", "live docs", "from memory") if need not in body]
        if len(agents_md.encode()) > 4096:
            out.append("AGENTS.md is over 4096 bytes")
        if len(instructions) > 1004:
            out.append("the server instructions are over 1,004 characters")
        if "live docs, not in the kb" not in instructions:
            out.append("the server instructions lack the label")
        return out

    def test_none_rule_texts(self):
        sys.path.insert(0, TOOLS)
        import kb_mcp
        agents = text("AGENTS.md")
        rule = [ln for ln in agents.splitlines() if ln.lstrip().startswith("- `none`")]
        assert len(rule) == 1 and "`route:`" in rule[0], rule
        skill = text(".claude/skills/kb-lookup/SKILL.md")
        skill_rule = [ln for ln in skill.splitlines() if ln.lstrip().startswith("- `none`")]
        agent_rule = [ln for ln in text(".claude/agents/kb-lookup.md").splitlines() if "`none`" in ln]
        assert len(skill_rule) == 1 and len(agent_rule) == 1
        assert "`route:`" in skill_rule[0] and "`route:`" in agent_rule[0]
        pack_line = kbfacts.pack("How do I configure VMware Horizon instant clones?")["text"].splitlines()[1]
        assert pack_line == kbfacts.NONE_SENTENCE
        texts = {"AGENTS.md": rule[0], "kb-lookup skill": skill_rule[0] + skill.split("5. **Live docs", 1)[1].split("\n", 1)[0],
                 "kb-lookup agent": agent_rule[0], "server instructions": kb_mcp.INSTRUCTIONS, "pack": pack_line}
        assert self.none_rule_problems(texts, kb_mcp.INSTRUCTIONS, agents) == []
        # planted failures: each old wording, a missing part, a size overrun
        for name in texts:
            for old in self.OLD_NONE:
                assert self.none_rule_problems(dict(texts, **{name: texts[name] + " " + old}), kb_mcp.INSTRUCTIONS, agents), (name, old)
            for need in ("lacks", "live docs", "from memory"):
                assert self.none_rule_problems(dict(texts, **{name: texts[name].replace(need, "")}), kb_mcp.INSTRUCTIONS, agents), (name, need)
        assert self.none_rule_problems(texts, kb_mcp.INSTRUCTIONS, agents + "x" * 4096)
        assert self.none_rule_problems(texts, kb_mcp.INSTRUCTIONS + "x" * 1004, agents)
        assert self.none_rule_problems(texts, kb_mcp.INSTRUCTIONS.replace("live docs, not in the kb", "the web"), agents)

    def test_agents_md_stays_small(self):
        size = len((text("AGENTS.md") or "").encode())
        assert size <= 4096, f"AGENTS.md is {size} bytes: it loads into every session and subagent; " \
                                         "move maintainer detail to kb/_self/"
        for s in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")):
            if os.path.basename(os.path.dirname(s)) not in ("kb-lookup", "kb-review-workspace", "kb-gap"):  # read-only skills
                assert "kb/_self/" in text(os.path.relpath(s, KB)), f"{s}: a skill that changes the kb must name the kb/_self/ docs it follows"

    def test_appended_files_have_lf_endings(self):
        """Python's csv writer ends rows with \\r\\n unless told otherwise; the union-merged ledgers, the tool data and
        kb/_self/ must stay \\n-only, or merges and the duplicate checks compare rows that differ only in \\r."""
        data = os.path.join(PUBLIC, kbcommon.DATA_DIR)
        paths = glob.glob(os.path.join(PUBLIC, "_*.csv")) + glob.glob(os.path.join(PUBLIC, "_*.md")) \
            + glob.glob(os.path.join(TOOLS, "*.csv")) + glob.glob(os.path.join(data, "*.csv")) \
            + glob.glob(os.path.join(data, "doc2query", "*.csv")) + glob.glob(os.path.join(SELF, "**", "*.*"), recursive=True)
        paths = sorted(set(paths))
        bad = [os.path.relpath(p, KB) for p in sorted(paths) if b"\r" in open(p, "rb").read()]
        assert not bad, "CR line endings (write with csv.writer(f, lineterminator='\\n'), or kbcommon.csv_text): " + ", ".join(bad)

    def test_readme_stays_short(self):
        size = len((text("README.md") or "").encode())
        assert size <= 8192, f"README.md is {size} bytes: it is the short overview for people; move agent detail to kb/_self/"
        assert "coverage:start" not in (text("README.md") or ""), "the coverage table lives in each root's _coverage.md"

    def test_self_map_is_complete(self):
        code, out = run(os.path.join(TOOLS, "selfdoc.py"), "check")
        assert code == 0, out[-3000:]


class TestSelfDocs:
    def test_self_docs_stay_out_of_the_pack(self):
        """kb/_self/ words (hook, skill, plugin, pack) must never compete with the domain articles in a pack."""
        main = [u for u in kbfacts.corpus() if not u.get("root")]
        is_self = lambda p: "kb/_self/" in p.replace(os.sep, "/")  # noqa: E731
        assert main and not [u["path"] for u in main if is_self(u["path"])]
        assert not [f for f in kbfacts.kb_files() if is_self(f)]
        assert "_self" not in __import__("rag").topics(None) and SELF_REL not in __import__("rag").topics(None)

    def test_self_code_pointers_resolve(self):
        """A CODE part without a source id (allowed in kb/_self/ only) points into this repository: the file exists and
        the symbol is defined in it (or the line range is inside it)."""
        found, bad = 0, []
        for p in sorted(glob.glob(os.path.join(SELF, "*.md"))):
            for part in kbfacts.tags_in(open(p, encoding="utf-8").read()):
                if part["kind"] != "CODE" or part["ids"] or "<" in part["note"]:
                    continue  # a cited source, or a `<id>: <path>#<symbol>` placeholder in a rule
                found += 1
                ptr = kbfacts.code_pointer(part)
                src = text(ptr[0]) if ptr else None
                lines = re.fullmatch(r"L(\d+)(?:-L(\d+))?", ptr[1]) if ptr else None
                ok = src is not None and (int(lines.group(lines.lastindex)) <= src.count("\n") + 1 if lines else
                                          re.search(rf"^\s*(?:def|class)\s+{re.escape(ptr[1])}\b|^{re.escape(ptr[1])}\s*=", src, re.M))
                if not ok:
                    bad.append((os.path.relpath(p, KB), 0, part["note"]))
        assert found, "expected at least one repository CODE pointer in kb/_self/ (tools.md)"
        assert not bad, "CODE pointers into this repository that do not resolve:\n" + fmt(bad)

    def test_search_with_index_finds_self_docs(self):
        import rag
        paths = lambda index: [h["path"].replace(os.sep, "/") for h in rag.search("selfdoc stale map.csv docs", 5, None, index, [])]  # noqa: E731
        assert not [p for p in paths(False) if "kb/_self/" in p]
        assert any("kb/_self/" in p for p in paths(True)), paths(True)


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
                               text=True, encoding="utf-8", cwd=KB, timeout=60, env=querylog_env(tmp_path))
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
                           capture_output=True, text=True, encoding="utf-8", cwd=KB, timeout=60, env=env)
        assert p.returncode == 2 and p.stdout.startswith("coverage: good") and "windows/laps.md:" in p.stdout, p.stdout + p.stderr

    def test_kb_hook(self, tmp_path):
        def hook(prompt):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "kb_hook.py")], input=json.dumps({"prompt": prompt}),
                               capture_output=True, text=True, encoding="utf-8", cwd=KB, timeout=60,
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

    def test_clean_good_is_blocked_and_kb_plus_keeps_its_context(self, monkeypatch):
        self.planted(monkeypatch, "good", None, ["coverage: good"], facts=False)
        out, row = kb_hook.respond("kb: a b")
        assert out["decision"] == "block" and out["reason"].startswith("coverage: good") and row["answered"] is True
        assert self.INSTRUCTION not in json.dumps(out)
        ctx = kb_hook.respond("kb+: a b")[0]["hookSpecificOutput"]["additionalContext"]
        assert ctx.startswith("The kb: hook ran the kb evidence pack for this question (coverage: good). Answer from it")
        assert self.INSTRUCTION not in ctx and ctx.endswith("coverage: good")


class TestRawReadNudge:
    """kb_hook on a PreToolUse Bash or PowerShell event: a whole-file read of a kb article gets a hint and runs; all else is silent."""
    READS = ["cat kb/public/claude/hooks.md", "cat ./kb/public/claude/hooks.md kb/public/ad/gpo.md",
             "sed -n 1,40p kb/public/claude/hooks.md", "sed -n '20,30p' kb/public/x/y.md", "head -n 40 kb/public/x/y.md",
             "tail -20 kb/public/x/y.md", "grep -n LAPS kb/public/windows/laps.md", "grep -in laps kb/public/windows/laps.md",
             "cat kb/public/_gaps.md", "cat kb/acme/_gaps.md", "cat kb/acme/net/vpn.md",
             "cd /work/it-ops-kb && cat /work/it-ops-kb/kb/public/x/y.md | head -5", "FOO=1 cat kb/public/x/y.md",
             "git status\ncat kb/public/x/y.md"]
    SILENT = ["ls kb/public/claude", "cat README.md", "cat _tools/kb_hook.py", "cat kb/_self/backlog.md",
              "cat kb/public/_sources.csv", "grep -rn LAPS kb/public", "grep LAPS kb/public/windows/laps.md",
              "sed -i s/a/b/ kb/public/x/y.md", "sed s/a/b/ kb/public/x/y.md", "cat notes > kb/public/x/y.md",
              "cat notes >> kb/public/x/y.md", "python3 _tools/rag.py show kb/public/claude/hooks.md:23 -n 30",
              "python3 _tools/rag.py search \"laps\" --index", "git add kb/public/x/y.md", "wc -l kb/public/x/y.md",
              "echo cat kb/public/x/y.md", "cat \"kb/public/x/y.md", "", "   "]

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
        entries = json.loads(text(".claude/settings.json"))["hooks"]["PreToolUse"]
        assert [e["matcher"] for e in entries] == ["Bash", "PowerShell"], entries
        hooks = [h for e in entries for h in e["hooks"]]
        assert hooks[0]["command"] == 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/kb_hook.py', hooks
        assert hooks[1]["shell"] == "powershell" and "/_tools/kb_hook.py" in hooks[1]["command"], hooks
        assert len(hooks) == 2, hooks


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
