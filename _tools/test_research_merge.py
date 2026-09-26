#!/usr/bin/env python3
"""Two parallel research branches with colliding ids, merged the documented way (stdlib only). tests.py runs it.

  test_research_merge.py   run it on its own

ResearchMergeInGit replays a two-researcher merge in a temp dir, never against the real origin:
  - the kb as it is now (history plus the working tree) is committed; a fork commit before it narrows one article's
    `files:` line, and the working tree on top of it (the upstream edit made since the fork) is pushed as `main`
    to a throwaway bare remote;
  - research-a and research-b fork from that fork commit (today's _sources.csv layout and tools) and both take the
    next legacy ids (S2205.. today) for different urls and the same answer id, with the same `_Agent: kb-research_`
    footer, hand-edited coverage rows, and (B) a front-matter edit next to the upstream one;
  - person A: install-hooks, `sync --push` (a clean rebase);
  - person B: install-hooks, `sync --push` stops with exit 3 on the article; it is resolved as /kb-git-sync says
    (sources = ids cited, status partial while an [UNK] remains, files = the union), then the printed
    `fix --base --upstream --side`, `git add`, `rebase --continue`, `sync --push`;
  - a fresh clone: check.py, build_index.py --check, kbgit.py fix --check and check-trailers pass; A keeps its ids,
    B's colliding rows got hash ids with their citations; both answers are distinct QK-<slug> ids and whole;
    B's research commit's trailers name only B's ids; `kbgit.py log <new hash id>` finds it.
Skipped without git. The gate skips tests.py (KB_SYNC_NO_TESTS=1). About 10 s.
"""
import csv, io, os, re, shutil, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import kbid  # noqa: E402

GIT = shutil.which("git")
A_URLS = [f"https://learn.microsoft.com/en-us/power-apps/maker/data-platform/research-merge-a{i}" for i in range(1, 6)]
B_URLS = [f"https://docs.keeper.io/en/research-merge/b{i}" for i in range(1, 4)]
Q_A = "Research-merge test: how does Dataverse reach an on-prem SQL Server?"
Q_B = "Research-merge test: can Keeper Secrets Manager hold agent tokens?"
ARTICLE_A = "powerbi/research-merge-test-dataverse.md"
ARTICLE_B = "agents/api-tokens-issue-and-store.md"
KEEPER = "### Research-merge test: Keeper Secrets Manager"
FOOTER = "_Agent: kb-research_"


def next_legacy():
    """The number both branches take: the next legacy id after the kb's own."""
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8", newline="") as f:
        nums = [int(r["id"][1:]) for r in csv.DictReader(f) if re.fullmatch(r"S\d+", r["id"] or "")]
    return max(nums + [2204]) + 1


FIRST = next_legacy()
LEG = [f"S{FIRST + i}" for i in range(5)]


FILES_NOW = "files: [agents/api-tokens.csv, agents/secret-storage-options.csv]\n"
FILES_FORK = "files: [agents/api-tokens.csv]\n"
QID = kbid.answer_id(Q_A)  # both branches head their answer with it (B's copy is the collision)


def rows(first, urls, publisher, licence):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for i, u in enumerate(urls):
        w.writerow([f"S{first + i}", u, f"Research merge page {i + 1}, {publisher}", publisher, licence, "2026-09-25",
                    "retrieved 2026-09-25", "", "", ""])
    return buf.getvalue()


def answer(q, bullets, see):
    return f"## {QID}. {q}\n" + "".join(f"- {b}\n" for b in bullets) + f"- See {see}.\n\n{FOOTER}\n"


@unittest.skipUnless(GIT, "git is not installed")
class ResearchMergeInGit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kb-research-merge-")
        cls.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                   "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                   "KB_SYNC_NO_TESTS": "1", "GIT_EDITOR": "true"}
        for k in ("KB_VERIFIED", "KB_TESTS_FAST", "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
            cls.env.pop(k, None)
        src, cls.remote = os.path.join(cls.tmp, "src"), os.path.join(cls.tmp, "remote.git")
        cls.git(cls.tmp, "clone", "-q", "--no-hardlinks", KB, src)
        cls.git(src, "checkout", "-q", "--detach")
        for name in os.listdir(src):  # the working tree as it is now (tools under test included), over HEAD
            if name != ".git":
                p = os.path.join(src, name)
                shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
        for name in os.listdir(KB):
            if name in (".git", "_cache", "_private", "__pycache__", "_fetch_state.csv"):
                continue
            s, d = os.path.join(KB, name), os.path.join(src, name)
            shutil.copytree(s, d, symlinks=True, ignore=shutil.ignore_patterns("__pycache__")) if os.path.isdir(s) else shutil.copy2(s, d)
        cls.git(src, "add", "-A")
        if cls.git(src, "status", "--porcelain").strip():
            cls.git(src, "commit", "-q", "--no-verify", "-m", "the working tree under test")
        now = cls.read(src, ARTICLE_B)
        assert FILES_NOW in now, f"{ARTICLE_B} no longer lists {FILES_NOW.strip()}: update the test"
        cls.write(src, ARTICLE_B, now.replace(FILES_NOW, FILES_FORK, 1))
        cls.git(src, "commit", "-q", "--no-verify", "-am", "the fork point")
        fork = cls.git(src, "rev-parse", "HEAD").strip()
        cls.write(src, ARTICLE_B, now)
        cls.git(src, "commit", "-q", "--no-verify", "-am", "docs(kb): the upstream edit made since the fork")
        cls.git(cls.tmp, "init", "-q", "--bare", "-b", "main", cls.remote)
        cls.git(src, "push", "-q", cls.remote, "HEAD:refs/heads/main")
        cls.main0 = cls.git(src, "rev-parse", "HEAD").strip()
        for name, build in (("research-a", cls.research_a), ("research-b", cls.research_b)):
            cls.git(src, "checkout", "-q", "-B", name, fork)
            build(src)
            cls.git(src, "add", "-A")
            cls.git(src, "commit", "-q", "--no-verify", "-m", f"docs(kb): {name}")
            cls.git(src, "push", "-q", cls.remote, f"{name}:refs/heads/scratch/{name}")
        cls.a, cls.b = os.path.join(cls.tmp, "a"), os.path.join(cls.tmp, "b")
        for d, name in ((cls.a, "research-a"), (cls.b, "research-b")):
            cls.git(cls.tmp, "clone", "-q", "-b", f"scratch/{name}", cls.remote, d)
            cls.git(d, "checkout", "-q", "-b", name)

        # person A: sync (a clean rebase)
        cls.kbgit(cls.a, "install-hooks")
        cls.sync_a = cls.kbgit(cls.a, "sync", "--push")

        # person B: sync stops with exit 3; resolve as the skill says
        cls.kbgit(cls.b, "install-hooks")
        cls.stop_b = cls.kbgit(cls.b, "sync", "--push")
        cls.conflicted_b = sorted(cls.git(cls.b, "diff", "--name-only", "--diff-filter=U").split())
        cls.resolve_article(cls.b)
        state = re.search(r"^sync-state: base=(\S+) upstream=(\S+) orig_head=(\S+)$", cls.stop_b.stdout, re.M)
        assert state, cls.stop_b.stdout + cls.stop_b.stderr
        cls.fix_b = cls.kbgit(cls.b, "fix", "--base", state[1], "--upstream", state[2], "--side", state[3])
        cls.git(cls.b, "add", "-A")
        cls.cont_b = cls.run_git(cls.b, "-c", "merge.conflictStyle=diff3", "rebase", "--continue")
        cls.sync_b = cls.kbgit(cls.b, "sync", "--push")

        # a fresh clone
        cls.v = os.path.join(cls.tmp, "verify")
        cls.git(cls.tmp, "clone", "-q", cls.remote, cls.v)
        cls.checks = {f"{t} {' '.join(args)}".strip(): cls.tool(cls.v, t, *args) for t, args in
                      (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")),
                       ("kbgit.py", ("check-trailers", f"{cls.main0}..HEAD")))}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- the two research branches

    @classmethod
    def research_a(cls, d):
        cls.append(d, "_sources.csv", rows(FIRST, A_URLS, "Microsoft", "Microsoft Learn terms of use (paraphrased; quote <=25 words)"))
        facts = [f"Dataverse reaches an on-prem SQL Server only through the on-premises data gateway. [DOC {LEG[0]}]",
                 f"Virtual tables expose external rows without copying them. [DOC {LEG[1]}]",
                 f"Azure Synapse Link replaces the retired Export to Data Lake service. [DOC {LEG[2]}]",
                 f"Dataflows can load SQL Server tables into Dataverse on a schedule. [DOC {LEG[3]}]",
                 f"Fabric shortcuts read Dataverse tables without an export job. [DOC {LEG[4]}]",
                 f"The research answer is `_answers.md` {QID}. [DER {LEG[0]}, {LEG[1]}]",
                 "The exact refresh latency is not documented. [UNK]"]
        cls.write(d, ARTICLE_A,
                  f"---\ntopic: {ARTICLE_A[:-3]}\npriority: P3\napplies_to: \"Dataverse\"\nretrieved_utc: 2026-09-25\n"
                  f"sources: [{', '.join(LEG)}]\nstatus: partial\n---\n\n# Dataverse and an on-prem SQL Server estate\n\n"
                  "## Summary\n\nResearch-a.\n\n## Facts\n\n" + "".join(f"- {f}\n" for f in facts)
                  + "\n## Reference\n\n- powerbi/on-prem-gateway-sql.md\n\n## Examples\n\n- `PL-SRV-0042` in `corp.example.com`.\n")
        cls.before_r1(d, answer(Q_A, [f"Through the gateway, with virtual tables or dataflows. [DOC {LEG[0]}, {LEG[1]}, {LEG[3]}]"],
                                ARTICLE_A))
        cls.append(d, "_gaps.md", f"\n## {ARTICLE_A[:-3]}\n\n- Refresh latency of virtual tables: not on the pages searched. (research-a)\n")
        cls.write(d, "_coverage.csv", cls.read(d, "_coverage.csv").replace(
            "powerbi/configmgr-views,P2,partial,powerbi/configmgr-views.md,2\n",
            f"powerbi/configmgr-views,P2,partial,powerbi/configmgr-views.md,2\n{ARTICLE_A[:-3]},P3,partial,{ARTICLE_A},5\n"))

    @classmethod
    def research_b(cls, d):
        cls.append(d, "_sources.csv", rows(FIRST, B_URLS, "Keeper Security", "not verified (summarized only)"))
        t = cls.read(d, ARTICLE_B)
        t = t.replace("S2056, S2057]\nstatus: complete\n", f"S2056, S2057, {', '.join(LEG[:3])}]\nstatus: partial\n", 1)
        t = t.replace("\n## Reference: each option's threat", f"\n{KEEPER}\n\n"
                      f"- Keeper Secrets Manager serves secrets through a zero-knowledge client device. [COMMUNITY {LEG[0]}]\n"
                      f"- Its Python SDK binds with a one-time access token. [COMMUNITY {LEG[1]}]\n"
                      "- Rotation of the client device's config is not described. [UNK]\n"
                      f"- The research answer is `_answers.md` {QID}. [COMMUNITY {LEG[2]}]\n"
                      "\n## Reference: each option's threat", 1)
        cls.write(d, ARTICLE_B, t)
        cls.before_r1(d, answer(Q_B, [f"Yes, through its SDK and a client device per host. [COMMUNITY {LEG[0]}, {LEG[1]}]",
                                      "Open: config rotation. [UNK]"], ARTICLE_B))
        cls.write(d, "_coverage.csv", cls.read(d, "_coverage.csv").replace(
            "agents/api-tokens-issue-and-store,P1,complete,", "agents/api-tokens-issue-and-store,P1,partial,"))
        cls.write(d, "README.md", cls.read(d, "README.md").replace(
            "| `agents/api-tokens-issue-and-store` | P1 | complete |", "| `agents/api-tokens-issue-and-store` | P1 | partial |"))

    @classmethod
    def resolve_article(cls, d):
        """Resolved by meaning, as /kb-git-sync says: facts added on both sides are both kept (upstream's first); the
        front matter gets the ids the resolved body cites, partial (an [UNK] is left) and the union of files:."""
        rx = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^(?:\|\|\|\|\|\|\| [^\n]*\n.*?)?^=======\n(.*?)^>>>>>>> [^\n]*\n", re.S | re.M)
        t = cls.read(d, ARTICLE_B)
        fm = [m for m in rx.finditer(t) if "sources:" in m.group(0)]
        t = rx.sub(lambda m: m.group(0) if "sources:" in m.group(0) else m.group(1) + m.group(2), t)
        m = next(rx.finditer(t), None) if fm else None
        if m:
            body = t[m.end():]
            files = re.search(r"^files: .*\n", m.group(0), re.M)
            cited = sorted(set(kbid.SOURCE_ID.findall(body)), key=kbid.sort_key)
            new = f"sources: [{', '.join(cited)}]\nstatus: {'partial' if '[UNK]' in body else 'complete'}\n" + (files.group(0) if files else "")
            t = t[:m.start()] + new + body
        cls.write(d, ARTICLE_B, t)

    # ---------------------------------------------------------------- helpers

    @classmethod
    def run_git(cls, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=cls.env, capture_output=True, text=True)

    @classmethod
    def git(cls, cwd, *args):
        p = cls.run_git(cwd, *args)
        if p.returncode:
            raise AssertionError(f"git {' '.join(args)}: {p.stdout}{p.stderr}")
        return p.stdout

    @classmethod
    def tool(cls, d, name, *args):
        return subprocess.run([sys.executable, os.path.join(d, "_tools", name), *args], cwd=d, env=cls.env,
                              capture_output=True, text=True, errors="replace")

    @classmethod
    def kbgit(cls, d, *args):
        return cls.tool(d, "kbgit.py", *args)

    @classmethod
    def read(cls, d, rel):
        with open(os.path.join(d, rel), encoding="utf-8", newline="") as f:
            return f.read()

    @classmethod
    def write(cls, d, rel, text):
        with open(os.path.join(d, rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    @classmethod
    def append(cls, d, rel, text):
        cls.write(d, rel, cls.read(d, rel) + text)

    @classmethod
    def before_r1(cls, d, block):
        t = cls.read(d, "_answers.md")
        i = t.index("\n## R1. ")
        cls.write(d, "_answers.md", t[:i] + "\n" + block + t[i:])

    def sources(self):
        return {r["id"]: r for r in csv.DictReader(io.StringIO(self.read(self.v, "_sources.csv")))}

    # ---------------------------------------------------------------- tests

    def test_a_rebases_cleanly_and_pushes(self):
        self.assertEqual(self.sync_a.returncode, 0, self.sync_a.stdout + self.sync_a.stderr)
        self.assertIn("pushed: yes", self.sync_a.stdout)

    def test_b_stops_on_the_article_then_finishes(self):
        self.assertEqual(self.stop_b.returncode, 3, self.stop_b.stdout + self.stop_b.stderr)
        self.assertIn(f"needs-human: {ARTICLE_B}", self.stop_b.stdout)
        self.assertIn(ARTICLE_B, self.conflicted_b)
        self.assertEqual(self.fix_b.returncode, 0, self.fix_b.stdout)
        self.assertIn(f"{QID} collision", self.fix_b.stdout)
        self.assertEqual(self.cont_b.returncode, 0, self.cont_b.stdout + self.cont_b.stderr)
        self.assertEqual(self.sync_b.returncode, 0, self.sync_b.stdout + self.sync_b.stderr)
        self.assertIn("pushed: yes", self.sync_b.stdout)

    def test_fresh_clone_passes_the_gate(self):
        for name, p in self.checks.items():
            self.assertEqual(p.returncode, 0, f"{name}: " + (p.stdout + p.stderr)[-2500:])

    def test_pushed_ids_stay_and_collisions_get_hash_ids(self):
        src = self.sources()
        for sid, u in zip(LEG, A_URLS):
            self.assertEqual(src[sid]["url"], u)
        hb = [kbid.source_id(u) for u in B_URLS]
        for h, u in zip(hb, B_URLS):
            self.assertEqual(src[h]["url"], u)
        art = self.read(self.v, ARTICLE_B)
        keeper = art[art.index(KEEPER):art.index("## Reference: each option")]
        for sid in LEG:
            self.assertNotRegex(keeper + art.split("---")[1], rf"{sid}\b")
        for h in hb:
            self.assertIn(h, keeper)
            self.assertIn(h, art.split("---")[1], "front matter sources: must list the renumbered ids")
        self.assertIn(FILES_NOW, art)
        self.assertIn("status: partial", art)
        self.assertIn(f"[DOC {LEG[0]}]", self.read(self.v, ARTICLE_A))

    def test_answers_distinct_and_whole(self):
        ans = self.read(self.v, "_answers.md")
        qa, qb = QID, kbid.answer_id(Q_B)
        self.assertNotEqual(qa, qb)
        self.assertEqual(ans.count(f"## {qa}. "), 1)
        for q in (qa, qb):
            sec = ans[ans.index(f"## {q}. "):]
            sec = sec[:sec.index("\n## ", 1)].rstrip()
            self.assertTrue(sec.endswith(FOOTER), sec)
        self.assertIn(f"`_answers.md` {qb}.", self.read(self.v, ARTICLE_B))
        self.assertIn(f"`_answers.md` {qa}.", self.read(self.v, ARTICLE_A))

    def test_b_trailers_name_only_b_and_log_finds_it(self):
        hb = kbid.source_id(B_URLS[0])
        out = self.git(self.v, "log", "--format=%s%x1f%(trailers:only,unfold)%x1e", f"{self.main0}..HEAD")
        recs = dict(r.strip("\n").split("\x1f") for r in out.split("\x1e") if "\x1f" in r)
        tb = recs["docs(kb): research-b"]
        self.assertIn(f"KB-Answers: {kbid.answer_id(Q_B)}\n", tb + "\n")
        self.assertIn("KB-Topics: agents/api-tokens-issue-and-store", tb)
        self.assertNotIn(LEG[0], tb)
        log = self.kbgit(self.v, "log", hb)
        self.assertEqual(log.returncode, 0, log.stdout)
        self.assertIn("docs(kb): research-b", log.stdout)
        self.assertIn("[trailer]", log.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
