"""The kb's documentation cohesion checks (`python3 _tools/tests.py` runs them with every other test module).

TestToolChecks, TestCohesion: check.py and fetch.py --offline pass; no lint errors beyond the recorded baseline; the
generated index files (every root's _coverage.csv, _coverage.md table and used_in) are up to date (build_index.py --check); links,
backtick paths and used_in paths resolve; every CLI flag the docs mention exists in that tool; the docs servers' .mcp.json (.claude-plugin/it-ops-kb-docs/), .claude/settings.json and AGENTS.md agree;
skills are well-formed; of the plugin skills only /kb-lookup is model-invocable, and the clone-only change skills all are
(a change request must reach them); the change router hook routes change prompts; AGENTS.md stays under 4 KB (every session and subagent
loads it; maintainer rules live in kb/_self/maintaining.md) and README.md under 8 KB (people read it); kb/_self/map.csv names
every _self doc and matches files, and no (kb/_self doc, Section) reference names a missing heading (selfdoc.py check;
a planted dead reference fails it); `ruff check` is clean (pyproject.toml).
TestSelfDocs: kb/_self/ stays out of the pack and the default search, and a search with index finds it.
"""
import csv, glob, json, os, re, subprocess, sys

import pytest

import kbcommon, kbfacts
from conftest import KB, KbTemplate, P, SELF_REL, TOOLS, allowlist, authored, copy_kb, fmt, git_env, requires_git, run, text, tracked
from test_kb_root import SID, make_root

PUBLIC = kbcommon.PUBLIC  # the public root: ledgers, articles, retrieval data (KB here is the repository)
SELF = kbcommon.SELF

LINT = os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py")
BASELINE = os.path.join(TOOLS, "lint_baseline.txt")
PLUGIN_SKILLS = {os.path.basename(s.rstrip("/")) for s in json.load(open(os.path.join(KB, ".claude-plugin", "plugin.json"),
                                                                        encoding="utf-8"))["skills"]}


def lint_errors():
    code, out = run(LINT)
    return {ln.strip() for ln in out.splitlines() if ln.startswith("ERROR")}


# the docs held to the code: the root docs, the kb/_self/ docs and the skills; flags in kb/_self/reports/ are not checked, since a
# report shows the command lines a measurement ran
DOCS = ["README.md", "AGENTS.md"] + sorted(os.path.relpath(p, KB) for p in glob.glob(os.path.join(SELF, "*.md"))) \
    + sorted(os.path.relpath(p, KB) for p in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")))


class TestToolChecks:
    def test_check_py_passes(self):
        code, out = run(os.path.join(TOOLS, "check.py"))
        assert code == 0, out[-3000:]

    def test_kb_copies_template_untouched_check_sees_a_write_through_a_link(self, tmp_path, monkeypatch):
        """Kb copies link the files of conftest.LINKED_DIRS to one template: a planted write through a link fails the
        template's end-of-run check, an untouched template, a write to a real copy and the link-less fallback pass."""
        src = tmp_path / "src"
        (src / "_census").mkdir(parents=True)
        (src / "notes").mkdir()
        (src / "_census" / "S1.txt").write_text("snapshot\n", encoding="utf-8")
        (src / "notes" / "a.md").write_text("article\n", encoding="utf-8")
        t = KbTemplate(str(src), None)
        try:
            d = t.copy_to(tmp_path / "one")
            assert os.path.samefile(d / "_census" / "S1.txt", t.root + "/_census/S1.txt")
            assert not os.path.samefile(d / "notes" / "a.md", t.root + "/notes/a.md"), "an article is a real copy"
            assert t.changed() == [], "an untouched template passes"
            (d / "notes" / "a.md").write_text("edited\n", encoding="utf-8")
            assert t.changed() == [], "a write to a real copy leaves the template as it was"
            real = t.copy_to(tmp_path / "two", copy=("_census",))
            (real / "_census" / "S1.txt").write_text("edited\n", encoding="utf-8")
            assert t.changed() == [], "a path in `copy` is a real copy"
            monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError("cross-device")))
            fallback = t.copy_to(tmp_path / "three")
            monkeypatch.undo()
            (fallback / "_census" / "S1.txt").write_text("edited\n", encoding="utf-8")
            assert t.changed() == [], "where a link fails the file is copied"
            (d / "_census" / "S1.txt").write_text("planted\n", encoding="utf-8")  # through the link
            assert t.changed() == ["_census/S1.txt"], "a write through a link is found"
        finally:
            t.remove()

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

    def test_decisions_store_self_files_exist_in_the_format_with_roles_only(self):
        """kb/_self keeps the central register and its own decisions: both files exist, with their headers, and the
        register holds roles only: no maker row has a name, and none is a storage policy."""
        for name, cols in ((kbcommon.DECISIONS, kbcommon.DECISION_COLS), (kbcommon.DECISION_MAKERS, kbcommon.MAKER_COLS)):
            header, rows = kbcommon.load_csv(os.path.join(SELF, name))
            assert header == cols, (name, header)
            if name == kbcommon.DECISION_MAKERS:
                assert all(r["role"] and not r["name"] and r["id"] != kbcommon.POLICY_ROW for r in rows), (name, rows)

    def test_decisions_store_checks_kb_self_and_resolves_the_central_register(self, tmp_path):
        """A planted failure in kb/_self's files is reported by its path; a root's by_ref names a maker of the central
        register; kb/_self writes an article or domain as <root>/<path>."""
        d = copy_kb(str(tmp_path / "kb"))
        self_dir = os.path.join(d, "kb", "_self")
        good = {"id": "D-aaaaaaaa", "text": "A rule of the kb's own docs.", "by": "maintainer", "by_ref": "maint", "source": "S100",
                "date": "2026-10-01", "context": "article:public/auth/kerberos; domain:public/auth; item:TK-abcd2345",
                "status": "active", "invalidated_reason": "", "invalidated_date": "", "supersedes": "", "review_by": "",
                "links": ""}
        makers = [{"id": "maint", "role": "maintainer", "name": "", "source": ""}]  # kb/_self is published: roles only
        env = {k: v for k, v in os.environ.items() if k != "KB_ROOTS"}

        def check(*decisions, roots=""):
            kbcommon.write_csv(os.path.join(self_dir, kbcommon.DECISIONS), kbcommon.DECISION_COLS, list(decisions))
            kbcommon.write_csv(os.path.join(self_dir, kbcommon.DECISION_MAKERS), kbcommon.MAKER_COLS, makers)
            p = subprocess.run([sys.executable, os.path.join(d, "_tools", "check.py")], capture_output=True, text=True,
                               encoding="utf-8", timeout=120, env={**env, "KB_ROOTS": roots})
            return p.returncode, p.stdout
        code, out = check(good)
        assert code == 0 and "errors=0" in out, out[-1500:]
        for rule, over in (("id 'x' is not D-<8 base32>", {"id": "x"}),
                           ("by_ref 'nobody' names no decision maker", {"by_ref": "nobody"}),
                           ("context article:auth/kerberos names no root", {"context": "article:auth/kerberos"}),
                           ("context article:public/auth/nope names no article public/auth/nope",
                            {"context": "article:public/auth/nope"}),
                           ("context domain:public/nope names no domain public/nope", {"context": "domain:public/nope"}),
                           ("cites unknown source S-zzzzzzzz", {"source": "S-zzzzzzzz"}),
                           ("by 'Jan Kowalski' is not the role 'maintainer' of maint: kb/_self, which is published",
                            {"by": "Jan Kowalski"}),
                           ("by_ref is empty: kb/_self, which is published, not an internal root, keeps no names",
                            {"by_ref": ""})):
            code, out = check({**good, **over})
            assert code == 1 and f"ERROR kb/_self/_decisions.csv:2 {rule}" in out, (rule, out[-800:])
        # a name in the central register is an error: kb/_self is published, so it is not an internal root
        makers[0]["name"] = "Jan Kowalski"
        code, out = check(good)
        assert code == 1 and ("ERROR kb/_self/decision-makers.csv:2 a name in kb/_self, which is published, "
                              "not an internal root: keep the role only") in out, out[-800:]
        makers[0]["name"] = ""
        # a root that is not internal references the central register: its by is the register's role, never the name
        root = str(tmp_path / "team-kb")
        make_root(root)
        with open(os.path.join(root, "_root.md"), encoding="utf-8") as f:
            meta = f.read().replace("visibility: internal", "visibility: public")
        with open(os.path.join(root, "_root.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(meta)
        with open(os.path.join(root, "_artifacts.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("path,source_id,sha256\n")
        row = {**good, "by": "maintainer", "by_ref": "maint", "source": SID, "context": "article:print/queues"}
        kbcommon.write_csv(os.path.join(root, kbcommon.DECISIONS), kbcommon.DECISION_COLS, [row])
        code, out = check(good, roots=root)
        assert code == 0 and "errors=0" in out, out[-1500:]
        kbcommon.write_csv(os.path.join(root, kbcommon.DECISIONS), kbcommon.DECISION_COLS, [{**row, "by": "Jan Kowalski"}])
        code, out = check(good, roots=root)
        assert code == 1 and "ERROR fixture/_decisions.csv:2 by 'Jan Kowalski' is not the role 'maintainer' of maint" in out, out[-800:]

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

    @requires_git
    @pytest.mark.git
    def test_git_env_no_maintenance(self, tmp_path):
        """A commit in a git_env repository starts no gc or maintenance child, and git_env keeps the caller's
        GIT_CONFIG_COUNT entries: the trace of the commit names no `gc` or `maintenance` command."""
        base = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"}
        env = git_env(**base)
        assert (env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == ("safe.directory", "*")
        assert env["GIT_CONFIG_COUNT"] == "3"
        trace = tmp_path / "trace.json"
        repo = tmp_path / "r"
        repo.mkdir()
        for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"]):
            e = {**env, "GIT_TRACE2_EVENT": str(trace)} if args[0] == "commit" else env
            subprocess.run(["git", *args], cwd=repo, env=e, check=True, capture_output=True)
        started = [json.loads(l).get("argv") for l in trace.read_text(encoding="utf-8").splitlines() if '"child_start"' in l]
        assert not [a for a in started if a and any(w in ("gc", "maintenance") for w in a)], started
        got = subprocess.run(["git", "config", "--get-all", "maintenance.auto"], cwd=repo, env=env, capture_output=True, text=True)
        assert got.stdout.split() == ["false"], got

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

    @staticmethod
    def goal_clause_problems(skill, runbook):
        """Problems with how the sprint plan maps goal clauses to items: the skill's plan step and the runbook's Sprints say it."""
        plan = skill.split("## plan", 1)[-1].split("\n## start", 1)[0]
        sprints = runbook.split("## Sprints", 1)[-1].split("\n## Working on items", 1)[0]
        problems = []
        for name, part in (("kb-sprint plan", plan), ("backlog.md Sprints", sprints)):
            for need in ("clause", "already met", "earlier item"):
                if need not in part:
                    problems.append(f"{name}: no `{need}`")
        return problems

    def test_sprint_plan_goal_clauses(self):
        skill, runbook = text(".claude/skills/kb-sprint/SKILL.md"), text("kb/_self/backlog.md")
        assert self.goal_clause_problems(skill, runbook) == []
        plan = skill.split("## plan", 1)[1].split("\n## start", 1)[0]
        assert plan.index("clause") < plan.index("Ask the operator"), "the mapping comes before the operator's approval"
        # planted failures: each part removed from either text
        for need in ("clause", "already met", "earlier item"):
            assert self.goal_clause_problems(skill.replace(need, "x"), runbook), need
            assert self.goal_clause_problems(skill, runbook.replace(need, "x")), need

    @staticmethod
    def goal_lane_order_problems(skill, backlog_skill, runbook):
        """Problems with how sprint planning checks a goal's step order: each text names the rule and the merge request."""
        plan = skill.split("## plan", 1)[-1].split("\n## start", 1)[0]
        sprints = runbook.split("## Sprints", 1)[-1].split("\n## Working on items", 1)[0]
        problems = []
        for name, part in (("kb-sprint plan", plan), ("kb-backlog", backlog_skill), ("backlog.md Sprints", sprints)):
            for need in ("code/<id>", "merge", "a push to `main`"):
                if need not in part:
                    problems.append(f"{name}: no `{need}`")
        for need in ("step order", "gate"):
            if need not in plan:
                problems.append(f"kb-sprint plan: no `{need}`")
        return problems

    def test_plan_goal_lane_order(self):
        skill, backlog_skill, runbook = (text(".claude/skills/kb-sprint/SKILL.md"), text(".claude/skills/kb-backlog/SKILL.md"),
                                         text("kb/_self/backlog.md"))
        assert self.goal_lane_order_problems(skill, backlog_skill, runbook) == []
        plan = skill.split("## plan", 1)[1].split("\n## start", 1)[0]
        assert plan.index("step order") < plan.index("Ask the operator"), "the check comes before the operator's approval"
        # planted failures: each part removed from each text
        for need in ("code/<id>", "merge", "a push to `main`", "step order", "gate"):
            assert self.goal_lane_order_problems(skill.replace(need, "x"), backlog_skill, runbook), need
        for need in ("code/<id>", "merge", "a push to `main`"):
            assert self.goal_lane_order_problems(skill, backlog_skill.replace(need, "x"), runbook), need
            assert self.goal_lane_order_problems(skill, backlog_skill, runbook.replace(need, "x")), need

    @staticmethod
    def premise_problems(backlog_skill, runbook):
        """Problems with how planning treats a story's premise: each text names the command in notes, the reproduction
        and the two ways out."""
        plan = backlog_skill.split("## Plan", 1)[-1]
        steps = runbook.split("## Sprints", 1)[-1].split("\n## Working on items", 1)[0]
        problems = []
        for name, part in (("kb-backlog Plan", plan), ("backlog.md Sprints", steps)):
            for need in ("premise", "`notes`", "does not reproduce", "test-only", "drops it"):
                if need not in part:
                    problems.append(f"{name}: no `{need}`")
        return problems

    def test_plan_premise_reproduces(self):
        backlog_skill, runbook = text(".claude/skills/kb-backlog/SKILL.md"), text("kb/_self/backlog.md")
        assert self.premise_problems(backlog_skill, runbook) == []
        # planted failures: each part removed from each text
        for need in ("premise", "`notes`", "does not reproduce", "test-only", "drops it"):
            assert self.premise_problems(backlog_skill.replace(need, "x"), runbook), need
            assert self.premise_problems(backlog_skill, runbook.replace(need, "x")), need

    @staticmethod
    def new_check_live_problems(backlog_skill, runbook):
        """Problems with how planning treats an item that adds a check: each text says it runs over the live
        repository before the sprint commits it and where the findings go."""
        plan = backlog_skill.split("## Plan", 1)[-1]
        steps = runbook.split("## Sprints", 1)[-1].split("\n## Working on items", 1)[0]
        problems = []
        for name, part in (("kb-backlog Plan", plan), ("backlog.md Sprints", steps)):
            for need in ("adds a check", "live repository", "draft of it", "`touches`", "a bug the item depends on", "lands green"):
                if need not in part:
                    problems.append(f"{name}: no `{need}`")
        return problems

    def test_plan_new_check_runs_on_live_repository(self):
        backlog_skill, runbook = text(".claude/skills/kb-backlog/SKILL.md"), text("kb/_self/backlog.md")
        assert self.new_check_live_problems(backlog_skill, runbook) == []
        # planted failures: each part removed from each text
        for need in ("adds a check", "live repository", "draft of it", "`touches`", "a bug the item depends on", "lands green"):
            assert self.new_check_live_problems(backlog_skill.replace(need, "x"), runbook), need
            assert self.new_check_live_problems(backlog_skill, runbook.replace(need, "x")), need

    @staticmethod
    def push_check_problems(backlog_skill, runbook):
        """Problems with how planning treats a check that guards a push: each text asks what the push carries,
        every commit of the range and not only the final tree."""
        plan = backlog_skill.split("## Plan", 1)[-1]
        steps = runbook.split("## Sprints", 1)[-1].split("\n## Working on items", 1)[0]
        problems = []
        for name, part in (("kb-backlog Plan", plan), ("backlog.md Sprints", steps)):
            for need in ("guarding a push", "what the push carries", "every commit of the pushed range", "not only the final tree"):
                if need not in part:
                    problems.append(f"{name}: no `{need}`")
        return problems

    def test_plan_push_check_names_what_push_carries(self):
        backlog_skill, runbook = text(".claude/skills/kb-backlog/SKILL.md"), text("kb/_self/backlog.md")
        assert self.push_check_problems(backlog_skill, runbook) == []
        # planted failures: each part removed from each text
        for need in ("guarding a push", "what the push carries", "every commit of the pushed range", "not only the final tree"):
            assert self.push_check_problems(backlog_skill.replace(need, "x"), runbook), need
            assert self.push_check_problems(backlog_skill, runbook.replace(need, "x")), need

    @staticmethod
    def shared_file_move_problems(skill, runbook):
        """Problems with how a task that moves code out of a shared file is run: each text names the announce, the
        drain, the check and the atomic commit."""
        run = skill.split("## run", 1)[-1].split("\n## review", 1)[0]
        steps = runbook.split("## Working on items", 1)[-1].split("\n## ", 1)[0]
        problems = []
        for name, part in (("kb-sprint run", run), ("backlog.md Working on items", steps)):
            for need in ("moves code out of a file other items edit", "announced first", "drain",
                         "held --overlaps ID --ref origin/main", "one atomic commit per file moved"):
                if need not in part:
                    problems.append(f"{name}: no `{need}`")
        return problems

    def test_sprint_shared_file_move_rule(self):
        skill, runbook = text(".claude/skills/kb-sprint/SKILL.md"), text("kb/_self/backlog.md")
        assert self.shared_file_move_problems(skill, runbook) == []
        # planted failures: each part removed from each text
        for need in ("moves code out of a file other items edit", "announced first", "drain",
                     "held --overlaps ID --ref origin/main", "one atomic commit per file moved"):
            assert self.shared_file_move_problems(skill.replace(need, "x"), runbook), need
            assert self.shared_file_move_problems(skill, runbook.replace(need, "x")), need

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

    def test_selfdoc_flags_dead_section_reference(self, tmp_path):
        """selfdoc.py check names a `(kb/_self/<doc>.md, <Section>)` or `(<doc>.md, <Section>)` reference whose heading
        is not in that doc, in kb/_self docs, AGENTS.md, SKILL.md files and _tools/ docstrings and comments; a heading
        named whole, by its first words, or as `A and B`, and a file list such as `(README.md, AGENTS.md)`, pass. On the
        live repository the query log's Learn and Apply references resolve."""
        import selfdoc
        self_dir = tmp_path / SELF_REL
        (self_dir).mkdir(parents=True)
        (tmp_path / "_tools").mkdir()
        (tmp_path / ".claude" / "skills" / "kb-x").mkdir(parents=True)
        w = lambda p, s: p.write_text(s, encoding="utf-8", newline="\n")  # noqa: E731
        w(self_dir / "map.csv", f"doc,pattern\n{SELF_REL}/querylog.md,-\n{SELF_REL}/rules.md,-\n")
        w(self_dir / "querylog.md", "# Query log\n\n## Learn\n\n## Apply\n\n## Capture (`querylog.py capture`)\n\n"
                                    "```\n## Fenced\n```\n")
        w(self_dir / "rules.md", "# Rules\n\n## Ledgers and retrieval data\n\nSee (`kb/_self/querylog.md`, Learn and Apply)"
                                 " and (querylog.md, Capture).\n")
        w(tmp_path / "README.md", "# Readme\n")  # the repository's own file, so a bare name for it is no dead doc
        w(tmp_path / "AGENTS.md", "Rules (`kb/_self/rules.md`, Ledgers); files (README.md, AGENTS.md).\n")
        w(tmp_path / ".claude" / "skills" / "kb-x" / "SKILL.md", "Read (kb/_self/querylog.md, Delivery) first.\n")
        w(tmp_path / "_tools" / "t.py", '"""Tool (kb/_self/querylog.md,\n    Fenced)."""\n'
                                        'X = "(querylog.md, Planted string)"  # (rules.md, Gone)\n'
                                        'def f():\n    """Uses (querylog.md, Apply)."""\n')
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        got = sorted(p for p in selfdoc.check(str(tmp_path)) if "names" in p)
        assert got == [
            f".claude/skills/kb-x/SKILL.md:1: (kb/_self/querylog.md, Delivery) names no heading of {SELF_REL}/querylog.md",
            f"_tools/t.py:1: (kb/_self/querylog.md, Fenced) names no heading of {SELF_REL}/querylog.md",
            f"_tools/t.py:3: (rules.md, Gone) names no heading of {SELF_REL}/rules.md",
        ], got
        live = selfdoc.dead_section_refs()
        found = [p for p in live if re.search(r"querylog\.md, (Learn|Apply)\b", p)]
        assert not found, found
        n = sum(1 for f, parts in selfdoc.ref_sources(KB, set(tracked())) for _, t in parts for m in selfdoc.SECTION_REF_RX.finditer(t)
                if m["sec"].split()[0] in ("Learn", "Apply"))
        assert n >= 2, "the query log's Learn and Apply references are no longer read as section references"

    def test_selfdoc_flags_dead_doc_odd_section_text_and_subdirectory_references(self, tmp_path):
        """A bare reference to a kb/_self doc that no longer exists and has no namesake elsewhere, a section text holding
        parentheses, a backtick, a colon or a semicolon or wrapping onto the next line, and a reference into a
        kb/_self subdirectory are each read; a bare name that is another file of the repository, and a heading named
        whole with its note, pass."""
        import selfdoc
        self_dir = tmp_path / SELF_REL
        (self_dir / "reports").mkdir(parents=True)
        (tmp_path / "docs").mkdir()
        w = lambda p, s: p.write_text(s, encoding="utf-8", newline="\n")  # noqa: E731
        w(self_dir / "a.md", "# A\n\n## Real\n\n## Capture (`a.py capture`)\n\n## Wrapped heading text\n")
        w(self_dir / "reports" / "r.md", "# R\n\n## Findings\n")
        w(tmp_path / "docs" / "README.md", "# Readme\n")
        w(tmp_path / "AGENTS.md",
          "Dead doc (gone.md, Real). Parens (a.md, Missing (note)). Colon (a.md, Gone: x). Semicolon (a.md, Real; more).\n"
          "Wrapped (a.md, Wrapped\nmissing text). Subdir (kb/_self/reports/r.md, Absent).\n"
          "Fine: (a.md, Real) (a.md, Capture (`a.py capture`)) (kb/_self/reports/r.md, Findings) (README.md, Setup)\n"
          "(kb/_self/gone2.md, Real).\n")
        got = selfdoc.dead_section_refs(str(tmp_path), {"AGENTS.md", f"{SELF_REL}/a.md", f"{SELF_REL}/reports/r.md",
                                                       "docs/README.md"})
        assert got == [
            "AGENTS.md:1: (gone.md, Real) names a doc that does not exist",
            f"AGENTS.md:1: (a.md, Missing (note)) names no heading of {SELF_REL}/a.md",
            f"AGENTS.md:1: (a.md, Gone: x) names no heading of {SELF_REL}/a.md",
            f"AGENTS.md:1: (a.md, Real; more) names no heading of {SELF_REL}/a.md",
            f"AGENTS.md:2: (a.md, Wrapped missing text) names no heading of {SELF_REL}/a.md",
            f"AGENTS.md:3: (kb/_self/reports/r.md, Absent) names no heading of {SELF_REL}/reports/r.md",
            "AGENTS.md:5: (kb/_self/gone2.md, Real) names a doc that does not exist",
        ], got

    def test_selfdoc_short_name_must_end_at_a_heading_separator(self):
        """A leading word that cuts a phrase (`The` for `The research queue`, `Store` and `Tests` for `Store layout` and
        `Tests plan`) names no heading; a prefix that ends at a note, a colon or a joining `and` still does."""
        import selfdoc
        keys = selfdoc.heading_keys(["## The research queue", "## Store layout", "## Tests plan",
                                     "## Ledgers and retrieval data", "## Staging levels: what to know",
                                     "## Capture (`querylog.py capture`)"])
        for bad in ("The", "Store", "Tests", "Ledgers and", "Staging"):
            assert not selfdoc.names_heading(bad, keys), bad
        for good in ("The research queue", "Ledgers", "Staging levels", "Capture", "capture (querylog.py capture)"):
            assert selfdoc.names_heading(good, keys), good

    def test_selfdoc_flags_a_cut_phrase_reference(self, tmp_path):
        """A reference naming only `The`, or `Store and Tests`, is reported when the doc has only the headings `The research
        queue`, `Store layout` and `Tests plan`; the whole heading and a short name for `Ledgers and retrieval data` pass."""
        import selfdoc
        self_dir = tmp_path / SELF_REL
        self_dir.mkdir(parents=True)
        (tmp_path / "_tools").mkdir()
        w = lambda p, s: p.write_text(s, encoding="utf-8", newline="\n")  # noqa: E731
        w(self_dir / "map.csv", f"doc,pattern\n{SELF_REL}/querylog.md,-\n{SELF_REL}/rules.md,-\n")
        w(self_dir / "querylog.md", "# Query log\n\n## The research queue\n\n## Store layout\n\n## Tests plan\n")
        w(self_dir / "rules.md", "# Rules\n\n## Ledgers and retrieval data\n\n(querylog.md, The) (querylog.md, Store and Tests)"
                                 " (querylog.md, The research queue) (rules.md, Ledgers)\n")
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        got = sorted(p for p in selfdoc.check(str(tmp_path)) if "names" in p)
        assert got == [
            f"{SELF_REL}/rules.md:5: (querylog.md, Store and Tests) names no heading of {SELF_REL}/querylog.md",
            f"{SELF_REL}/rules.md:5: (querylog.md, The) names no heading of {SELF_REL}/querylog.md",
        ], got


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
