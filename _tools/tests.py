#!/usr/bin/env python3
"""CI tests for it-ops-kb (stdlib only): documentation cohesion and leak detection. Exit 1 on any failure.

  tests.py               run everything
  tests.py -k Leak       run tests whose name matches (unittest -k)
  tests.py --write-lint-baseline   record today's lint errors as known debt in _tools/lint_baseline.txt
  KB_TESTS_FAST=1 tests.py         leave out the git scenarios (MergeInGit, HistoryInGit, SyncInGit, ResearchMergeInGit):
                                   kbgit.py sync's gate

Cohesion: check.py and fetch.py --offline pass; no lint errors beyond the recorded baseline; the generated index
files (_coverage.csv, README coverage table, used_in) are up to date (build_index.py --check); links, backtick paths and used_in paths resolve; every CLI flag the docs mention exists
in that tool; .mcp.json, .claude/settings.json and AGENTS.md agree; skills are well-formed.
Ids: kbid.py hash source ids are deterministic and normalization-stable; bad ids and answer-id clashes are caught.
Merges (test_merge.py): union-merged ledgers plus kbgit.py fix give a clean kb; the git scenario is skipped without git.
History (test_history.py): KB-* trailers, the commit-msg hook, check-trailers, log, blame, asof, tag-census; git parts skip without git.
Sync (test_sync.py): kbgit.py sync against a throwaway bare remote and two clones; skipped without git.
Research merge (test_research_merge.py): two pre-regime research branches with colliding ids merged the documented way
(rebase, /kb-git-sync resolution, fix, sync), checked in a fresh clone; skipped without git or the fork commit.
Leaks (tracked files): secrets in any file; in authored files also home-directory paths, private IPv4 addresses,
non-placeholder e-mail addresses and GUIDs outside the reviewed allowlist (_tools/tests_allowlist.txt); files that
must never be committed; oversized files.
"""
import csv, glob, importlib.util, json, os, re, subprocess, sys, unittest

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(KB, "_tools")
LINT = os.path.join(KB, ".claude", "skills", "kb-verify", "lint.py")
BASELINE = os.path.join(TOOLS, "lint_baseline.txt")
ALLOWLIST = os.path.join(TOOLS, "tests_allowlist.txt")
MAX_BYTES = 10 * 1024 * 1024
sys.path.insert(0, TOOLS)
import kbid  # noqa: E402
from test_merge import MergeRules  # noqa: E402,F401  (run here too)
from test_history import TrailerRules  # noqa: E402,F401
from test_sync import SyncRules  # noqa: E402,F401
if os.environ.get("KB_TESTS_FAST") != "1":  # the git scenarios (each skips without git); kbgit.py sync's gate leaves them out
    from test_merge import MergeInGit  # noqa: E402,F401
    from test_history import HistoryInGit  # noqa: E402,F401
    from test_sync import SyncInGit  # noqa: E402,F401
    from test_research_merge import ResearchMergeInGit  # noqa: E402,F401


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=KB, capture_output=True, text=True, errors="replace")
    return p.returncode, p.stdout + p.stderr


def tracked():
    """Tracked files (git ls-files), or every file outside ignored dirs when git is unavailable."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=KB, capture_output=True, check=True).stdout
        return sorted(f for f in out.decode().split("\0") if f)
    except (OSError, subprocess.CalledProcessError):
        out = []
        for root, dirs, files in os.walk(KB):
            dirs[:] = [d for d in dirs if d not in {".git", "_cache", "_private", "__pycache__"}]
            out += [os.path.relpath(os.path.join(root, f), KB) for f in files]
        return sorted(out)


def text(rel):
    try:
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def pinned():
    with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8-sig", newline="") as f:
        return {r["path"] for r in csv.DictReader(f)}


def authored():
    """Tracked text files we wrote ourselves: not pinned artifacts and not vendor exports under */artifacts/."""
    p = pinned()
    return [f for f in tracked() if f not in p and "/artifacts/" not in f and text(f) is not None]


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


# urls, including git remotes: ssh:// and the scp-like `git@host:path` form (a remote, not an e-mail address)
URL_RX = re.compile(r"(?:https?|ssh|git)://\S+|(?<![\w.%+-])git@[\w.-]+:[\w./~-]+")


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


DOCS = ["README.md", "AGENTS.md"] + sorted(os.path.relpath(p, KB) for p in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")))


class ToolChecks(unittest.TestCase):
    def test_check_py_passes(self):
        code, out = run(os.path.join(TOOLS, "check.py"))
        self.assertEqual(code, 0, out[-3000:])

    def test_pinned_artifacts_match(self):
        code, out = run(os.path.join(TOOLS, "fetch.py"), "--offline")
        self.assertEqual(code, 0, out[-3000:])

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
        self.assertFalse(new, "new lint errors (fix them, or accept deliberately with --write-lint-baseline):\n" + "\n".join(new[:30]))


class Cohesion(unittest.TestCase):
    def test_generated_indexes_up_to_date(self):
        """_coverage.csv, the README coverage table and used_in are generated; a hand edit or a missed rebuild fails."""
        code, out = run(os.path.join(TOOLS, "build_index.py"), "--check")
        self.assertEqual(code, 0, "generated index files are out of date; run python3 _tools/build_index.py\n" + out[-3000:])

    def test_markdown_links_resolve(self):
        bad = []
        for f in [x for x in authored() if x.endswith(".md")] + [x for x in DOCS if x not in authored()]:
            t = re.sub(r"```.*?```|`[^`\n]*`", "", text(f) or "", flags=re.S)
            for link in re.findall(r"\]\(([^)\s]+)\)", t):
                if re.match(r"[a-z][a-z0-9+.-]*:", link) or link.startswith("#"):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(KB, os.path.dirname(f), link.split("#")[0]))):
                    bad.append((f, 0, link))
        self.assertFalse(bad, "broken relative links:\n" + fmt(bad))

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
        self.assertFalse(bad, "backtick paths that do not exist:\n" + fmt(bad))

    def test_used_in_paths_exist(self):
        with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
            bad = [(r["id"], 0, u) for r in csv.DictReader(f)
                   for u in filter(None, (x.strip() for x in (r.get("used_in") or "").split(";")))
                   if not os.path.exists(os.path.join(KB, u))]
        self.assertFalse(bad, "_sources.csv used_in names missing files:\n" + fmt(bad))

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
        self.assertFalse(bad, "documented flags missing from the tool:\n" + fmt(bad))

    def test_mcp_config_consistent(self):
        servers = json.loads(text(".mcp.json"))["mcpServers"]
        settings = json.loads(text(".claude/settings.json"))
        self.assertEqual(set(settings.get("enabledMcpjsonServers", [])), set(servers), "enabledMcpjsonServers != .mcp.json servers")
        table = dict(re.findall(r"^\s*\| `([\w-]+)` \| `(https://[^`]+)` \|", text("AGENTS.md"), re.M))
        self.assertEqual(table, {k: v["url"] for k, v in servers.items()}, "AGENTS.md server table != .mcp.json")
        perms = settings.get("permissions", {})
        for rule in perms.get("allow", []):
            m = re.match(r"mcp__([\w-]+?)__", rule)
            if m:
                self.assertIn(m.group(1), servers, f"allow rule {rule} names an unknown server")
            self.assertNotIn("submit_feedback", rule, "submit_feedback must never be allowed")
            self.assertFalse(rule.startswith("mcp__") and rule.endswith("__*") and rule[5:-3] in ("claude-code-docs", "mcp-docs"),
                             f"{rule} would allow submit_feedback")
        for s in ("claude-code-docs", "mcp-docs"):
            if s in servers:
                self.assertIn(f"mcp__{s}__submit_feedback", perms.get("deny", []))
        for s, v in servers.items():
            self.assertTrue(v.get("url", "").startswith("https://"), f"{s}: not an https url")
            self.assertNotIn("headers", v, f"{s}: shared config must not carry headers (credentials belong in user scope)")

    def test_skills_well_formed(self):
        skills = sorted(glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md")))
        self.assertTrue(skills, "no skills found")
        for p in skills:
            t = text(os.path.relpath(p, KB))
            self.assertTrue(t.startswith("---\n"), f"{p}: no front matter")
            fm = t.split("\n---", 1)[0]
            name = re.search(r"^name:\s*(\S+)", fm, re.M)
            self.assertTrue(name and name.group(1) == os.path.basename(os.path.dirname(p)), f"{p}: name must equal its directory")
            self.assertRegex(fm, r"(?m)^description:\s*\S.{20,}", f"{p}: description missing or too short")
            self.assertIn(os.path.basename(os.path.dirname(p)), text("AGENTS.md"), f"{p}: skill not listed in AGENTS.md")

    def test_claude_md_imports_agents_md(self):
        self.assertIn("@AGENTS.md", text("CLAUDE.md") or "")


class Ids(unittest.TestCase):
    URL = "https://learn.microsoft.com/en-us/windows/security/example"

    def test_hash_id_is_deterministic_and_well_formed(self):
        sid = kbid.source_id(self.URL)
        self.assertEqual(sid, kbid.source_id(self.URL))
        self.assertRegex(sid, r"^S-[a-z2-7]{8}$")
        self.assertTrue(kbid.is_source_id(sid) and kbid.is_source_id("S100") and not kbid.is_source_id("S-12"))
        self.assertEqual(kbid.source_id("https://example.com/"), "S-" + __import__("base64").b32encode(
            __import__("hashlib").sha256(b"https://example.com/").digest()).decode().lower()[:8])

    def test_normalization_equivalences(self):
        same = ["HTTPS://Learn.Microsoft.COM/en-us/windows/security/example", self.URL + "/", self.URL + "#section",
                "https://learn.microsoft.com:443/en-us/windows/security/example", "  " + self.URL + "  ", self.URL + "?"]
        for u in same:
            self.assertEqual(kbid.normalize_url(u), self.URL, u)
        self.assertEqual(kbid.normalize_url("http://Example.com"), "http://example.com/")
        self.assertEqual(kbid.normalize_url("http://example.com:80/a"), "http://example.com/a")
        differ = [self.URL.replace("windows", "Windows"), self.URL + "?view=1", "http://learn.microsoft.com/en-us/windows/security/example",
                  "https://learn.microsoft.com:8443/en-us/windows/security/example", self.URL + "%2F"]
        for u in differ:
            self.assertNotEqual(kbid.source_id(u), kbid.source_id(self.URL), u)

    def test_check_sources_catches_hand_typed_and_collisions(self):
        ok = [{"id": kbid.source_id(self.URL), "url": self.URL + "/"}, {"id": "S100", "url": self.URL}]
        self.assertEqual(kbid.check_sources(ok), [])
        typed = kbid.check_sources([{"id": "S-abcdefgh", "url": self.URL}])
        self.assertTrue(typed and "does not match its url" in typed[0])
        a, b = "https://example.com/c/266794", "https://example.com/c/514424"  # a real 40-bit collision
        self.assertEqual(kbid.source_id(a), kbid.source_id(b))
        self.assertTrue(any("collision" in e for e in kbid.check_sources([{"id": kbid.source_id(a), "url": a}, {"id": "S1", "url": b}])))

    def test_id_regexes_accept_both_forms(self):
        text = "fact [DOC S1289, S-k3f7q2zd] and S3 sleep, HTTPS-only"
        self.assertEqual(kbid.SOURCE_ID.findall(text), ["S1289", "S-k3f7q2zd", "S3"])
        self.assertEqual(kbid.ANY_ID.findall("S1480,S1483: HTTPS-only, S-BAD"), ["S1480", "S1483", "S-BAD"])
        spec = importlib.util.spec_from_file_location("lint", LINT)
        lint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lint)
        self.assertEqual(lint.SID.findall("[S100, S-k3f7q2zd]"), ["S100", "S-k3f7q2zd"])
        self.assertEqual(sorted(["S-bbbbbbbb", "S1000", "S-aaaaaaaa", "S999"], key=kbid.sort_key),
                         ["S999", "S1000", "S-aaaaaaaa", "S-bbbbbbbb"])
        self.assertEqual([kbid.canonical_id(x) for x in ("s0100", "s-K3F7Q2ZD")], ["S0100", "S-k3f7q2zd"])

    def test_answer_ids(self):
        self.assertEqual(kbid.answer_id("How does Dataverse sync with an on-prem SQL Server?"), "QK-dataverse-sync-prem-sql-server")
        self.assertRegex(kbid.answer_id("???"), kbid.QK_ID.pattern)
        ids = kbid.answer_ids("## Q1. a\n## QK-x-y. b\n## QK-x-y. c\n### Q2. no\n## QG1 (no dot)\n")
        self.assertEqual(ids, ["Q1", "QK-x-y", "QK-x-y"])
        real = kbid.answer_ids(text("_answers.md") or "")
        self.assertEqual(len(real), len(set(real)), "duplicate answer ids in _answers.md")


class Leaks(unittest.TestCase):
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
        found = [h for rx in self.SECRETS for h in hits(rx, files) if h[2].lower() not in allow]
        self.assertFalse(found, "possible secrets:\n" + fmt(found))

    def test_no_home_paths(self):
        found = hits(r"(?:/Users/|/home/|[A-Za-z]:\\+Users\\+)(?!<)[A-Za-z][\w.-]+", authored())
        generic = ("public", "default", "all users", "username", "user", "administrator")
        found = [h for h in found if re.split(r"[/\\]+", h[2])[-1].lower() not in generic]
        self.assertFalse(found, "machine-specific home paths:\n" + fmt(found))

    def test_no_private_ipv4(self):
        allow = allowlist().get("ip", set())
        rx = r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![\w.])"
        found = [h for h in hits(rx, authored(), strip_urls=True) if h[2] not in allow
                 and all(int(x) < 256 for x in h[2].split("."))]
        self.assertFalse(found, "private IPv4 addresses (use 192.0.2.x/198.51.100.x/203.0.113.x, or allowlist):\n" + fmt(found))

    def test_no_real_email_addresses(self):
        allow = allowlist().get("email", set())
        found = [h for h in hits(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b", authored(), strip_urls=True)
                 if not re.search(r"(?i)@([\w-]+\.)*example\.(com|org|net)$|@noreply\.|@users\.noreply\.github\.com$", h[2])
                 and h[2].lower() not in allow]
        self.assertFalse(found, "e-mail addresses outside example.com/noreply (placeholders only):\n" + fmt(found))

    def test_git_remotes_are_urls_not_email(self):
        self.assertEqual(URL_RX.sub("", "clone git@gitlab.com:group/kb.git here").split(), ["clone", "here"])
        self.assertEqual(URL_RX.sub("", "ssh://git@gitlab.com/group/kb.git"), "")
        for mail in ("jan.git@corp.example.com", "git@corp.example.com wrote", "mail git@corp.example.com: hi"):
            self.assertRegex(URL_RX.sub("", mail), r"@corp\.example\.com", mail)

    def test_no_unexpected_guids_in_prose(self):
        allow = allowlist().get("guid", set())
        md = [f for f in authored() if f.endswith(".md")]
        found = [h for h in hits(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", md, strip_urls=True)
                 if not re.fullmatch(r"0{8}-0{4}-0{4}-0{4}-0{8}[0-9a-f]{4}", h[2].lower()) and h[2].lower() not in allow]
        self.assertFalse(found, "GUIDs in prose that are neither placeholders nor reviewed public ids "
                                "(tenant/object ids leak; add public ones to _tools/leak_allowlist.txt with a reason):\n" + fmt(found))

    def test_no_forbidden_files_tracked(self):
        rx = re.compile(r"(^|/)(_cache|_private|__pycache__)/|(^|/)\.env(\.|$)|\.(pem|key|pfx|p12|kdbx|tmp)$|(^|/)id_(rsa|ed25519)|(^|/)\.DS_Store$")
        bad = [f for f in tracked() if rx.search(f)]
        self.assertFalse(bad, "files that must not be committed:\n  " + "\n  ".join(bad))

    def test_no_oversized_files(self):
        big = [(f, os.path.getsize(os.path.join(KB, f))) for f in tracked() if os.path.getsize(os.path.join(KB, f)) > MAX_BYTES]
        self.assertFalse(big, f"files over {MAX_BYTES // 2**20} MB:\n" + "\n".join(f"  {f}: {s} bytes" for f, s in big))


if __name__ == "__main__":
    if "--write-lint-baseline" in sys.argv:
        errs = sorted(lint_errors())
        with open(BASELINE, "w", encoding="utf-8") as f:
            f.write("".join(e + "\n" for e in errs))
        sys.exit(print(f"wrote {len(errs)} known lint errors to {os.path.relpath(BASELINE, KB)}"))
    unittest.main(verbosity=2)
