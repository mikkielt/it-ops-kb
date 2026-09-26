"""Two parallel research branches with colliding ids, merged the documented way (`python3 _tools/tests.py -k research`).

TestResearchMergeInGit (marker git) replays a two-researcher merge in a temp dir, never against the real origin:
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
import csv, io, os, re, shutil

import pytest

import kbid
from conftest import KB, Repo, git_env, requires_git

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


@requires_git
@pytest.mark.git
class TestResearchMergeInGit:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        cls.tmp = str(tmp_path_factory.mktemp("kb-research-merge"))
        cls.env = git_env(KB_SYNC_NO_TESTS="1", GIT_EDITOR="true")
        top = Repo(cls.tmp, cls.env)
        src, cls.remote = Repo(os.path.join(cls.tmp, "src"), cls.env), os.path.join(cls.tmp, "remote.git")
        top.git("clone", "-q", "--no-hardlinks", KB, src.path)
        src.git("checkout", "-q", "--detach")
        for name in os.listdir(src.path):  # the working tree as it is now (tools under test included), over HEAD
            if name != ".git":
                p = src.file(name)
                shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
        for name in os.listdir(KB):
            if name in (".git", "_cache", "_private", "__pycache__", "_fetch_state.csv"):
                continue
            s, d = os.path.join(KB, name), src.file(name)
            shutil.copytree(s, d, symlinks=True, ignore=shutil.ignore_patterns("__pycache__")) if os.path.isdir(s) else shutil.copy2(s, d)
        src.git("add", "-A")
        if src.git("status", "--porcelain").strip():
            src.git("commit", "-q", "--no-verify", "-m", "the working tree under test")
        now = src.read(ARTICLE_B)
        assert FILES_NOW in now, f"{ARTICLE_B} no longer lists {FILES_NOW.strip()}: update the test"
        src.write(ARTICLE_B, now.replace(FILES_NOW, FILES_FORK, 1))
        src.git("commit", "-q", "--no-verify", "-am", "the fork point")
        fork = src.git("rev-parse", "HEAD").strip()
        src.write(ARTICLE_B, now)
        src.git("commit", "-q", "--no-verify", "-am", "docs(kb): the upstream edit made since the fork")
        top.git("init", "-q", "--bare", "-b", "main", cls.remote)
        src.git("push", "-q", cls.remote, "HEAD:refs/heads/main")
        cls.main0 = src.git("rev-parse", "HEAD").strip()
        for name, build in (("research-a", cls.research_a), ("research-b", cls.research_b)):
            src.git("checkout", "-q", "-B", name, fork)
            build(src)
            src.git("add", "-A")
            src.git("commit", "-q", "--no-verify", "-m", f"docs(kb): {name}")
            src.git("push", "-q", cls.remote, f"{name}:refs/heads/scratch/{name}")
        cls.a, cls.b = Repo(os.path.join(cls.tmp, "a"), cls.env), Repo(os.path.join(cls.tmp, "b"), cls.env)
        for d, name in ((cls.a, "research-a"), (cls.b, "research-b")):
            top.git("clone", "-q", "-b", f"scratch/{name}", cls.remote, d.path)
            d.git("checkout", "-q", "-b", name)

        # person A: sync (a clean rebase)
        cls.a.kbgit("install-hooks")
        cls.sync_a = cls.a.kbgit("sync", "--push")

        # person B: sync stops with exit 3; resolve as the skill says
        cls.b.kbgit("install-hooks")
        cls.stop_b = cls.b.kbgit("sync", "--push")
        cls.conflicted_b = sorted(cls.b.git("diff", "--name-only", "--diff-filter=U").split())
        cls.resolve_article(cls.b)
        state = re.search(r"^sync-state: base=(\S+) upstream=(\S+) orig_head=(\S+)$", cls.stop_b.stdout, re.M)
        assert state, cls.stop_b.stdout + cls.stop_b.stderr
        cls.fix_b = cls.b.kbgit("fix", "--base", state[1], "--upstream", state[2], "--side", state[3])
        cls.b.git("add", "-A")
        cls.cont_b = cls.b.run_git("-c", "merge.conflictStyle=diff3", "rebase", "--continue")
        cls.sync_b = cls.b.kbgit("sync", "--push")

        # a fresh clone
        cls.v = Repo(os.path.join(cls.tmp, "verify"), cls.env)
        top.git("clone", "-q", cls.remote, cls.v.path)
        cls.checks = {f"{t} {' '.join(args)}".strip(): cls.v.tool(t, *args) for t, args in
                      (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")),
                       ("kbgit.py", ("check-trailers", f"{cls.main0}..HEAD")))}
        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- the two research branches

    @classmethod
    def research_a(cls, d):
        d.append("_sources.csv", rows(FIRST, A_URLS, "Microsoft", "Microsoft Learn terms of use (paraphrased; quote <=25 words)"))
        facts = [f"Dataverse reaches an on-prem SQL Server only through the on-premises data gateway. [DOC {LEG[0]}]",
                 f"Virtual tables expose external rows without copying them. [DOC {LEG[1]}]",
                 f"Azure Synapse Link replaces the retired Export to Data Lake service. [DOC {LEG[2]}]",
                 f"Dataflows can load SQL Server tables into Dataverse on a schedule. [DOC {LEG[3]}]",
                 f"Fabric shortcuts read Dataverse tables without an export job. [DOC {LEG[4]}]",
                 f"The research answer is `_answers.md` {QID}. [DER {LEG[0]}, {LEG[1]}]",
                 "The exact refresh latency is not documented. [UNK]"]
        d.write(ARTICLE_A,
                  f"---\ntopic: {ARTICLE_A[:-3]}\npriority: P3\napplies_to: \"Dataverse\"\nretrieved_utc: 2026-09-25\n"
                  f"sources: [{', '.join(LEG)}]\nstatus: partial\n---\n\n# Dataverse and an on-prem SQL Server estate\n\n"
                  "## Summary\n\nResearch-a.\n\n## Facts\n\n" + "".join(f"- {f}\n" for f in facts)
                  + "\n## Reference\n\n- powerbi/on-prem-gateway-sql.md\n\n## Examples\n\n- `PL-SRV-0042` in `corp.example.com`.\n")
        cls.before_r1(d, answer(Q_A, [f"Through the gateway, with virtual tables or dataflows. [DOC {LEG[0]}, {LEG[1]}, {LEG[3]}]"],
                                ARTICLE_A))
        d.append("_gaps.md", f"\n## {ARTICLE_A[:-3]}\n\n- Refresh latency of virtual tables: not on the pages searched. (research-a)\n")
        d.write("_coverage.csv", d.read("_coverage.csv").replace(
            "powerbi/configmgr-views,P2,partial,powerbi/configmgr-views.md,2\n",
            f"powerbi/configmgr-views,P2,partial,powerbi/configmgr-views.md,2\n{ARTICLE_A[:-3]},P3,partial,{ARTICLE_A},5\n"))

    @classmethod
    def research_b(cls, d):
        d.append("_sources.csv", rows(FIRST, B_URLS, "Keeper Security", "not verified (summarized only)"))
        t = d.read(ARTICLE_B)
        t = t.replace("S2056, S2057]\nstatus: complete\n", f"S2056, S2057, {', '.join(LEG[:3])}]\nstatus: partial\n", 1)
        t = t.replace("\n## Reference: each option's threat", f"\n{KEEPER}\n\n"
                      f"- Keeper Secrets Manager serves secrets through a zero-knowledge client device. [COMMUNITY {LEG[0]}]\n"
                      f"- Its Python SDK binds with a one-time access token. [COMMUNITY {LEG[1]}]\n"
                      "- Rotation of the client device's config is not described. [UNK]\n"
                      f"- The research answer is `_answers.md` {QID}. [COMMUNITY {LEG[2]}]\n"
                      "\n## Reference: each option's threat", 1)
        d.write(ARTICLE_B, t)
        cls.before_r1(d, answer(Q_B, [f"Yes, through its SDK and a client device per host. [COMMUNITY {LEG[0]}, {LEG[1]}]",
                                      "Open: config rotation. [UNK]"], ARTICLE_B))
        d.write("_coverage.csv", d.read("_coverage.csv").replace(
            "agents/api-tokens-issue-and-store,P1,complete,", "agents/api-tokens-issue-and-store,P1,partial,"))
        d.write("README.md", d.read("README.md").replace(
            "| `agents/api-tokens-issue-and-store` | P1 | complete |", "| `agents/api-tokens-issue-and-store` | P1 | partial |"))

    @classmethod
    def resolve_article(cls, d):
        """Resolved by meaning, as /kb-git-sync says: facts added on both sides are both kept (upstream's first); the
        front matter gets the ids the resolved body cites, partial (an [UNK] is left) and the union of files:."""
        rx = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^(?:\|\|\|\|\|\|\| [^\n]*\n.*?)?^=======\n(.*?)^>>>>>>> [^\n]*\n", re.S | re.M)
        t = d.read(ARTICLE_B)
        fm = [m for m in rx.finditer(t) if "sources:" in m.group(0)]
        t = rx.sub(lambda m: m.group(0) if "sources:" in m.group(0) else m.group(1) + m.group(2), t)
        m = next(rx.finditer(t), None) if fm else None
        if m:
            body = t[m.end():]
            files = re.search(r"^files: .*\n", m.group(0), re.M)
            cited = sorted(set(kbid.SOURCE_ID.findall(body)), key=kbid.sort_key)
            new = f"sources: [{', '.join(cited)}]\nstatus: {'partial' if '[UNK]' in body else 'complete'}\n" + (files.group(0) if files else "")
            t = t[:m.start()] + new + body
        d.write(ARTICLE_B, t)

    # ---------------------------------------------------------------- helpers

    @classmethod
    def before_r1(cls, d, block):
        t = d.read("_answers.md")
        i = t.index("\n## R1. ")
        d.write("_answers.md", t[:i] + "\n" + block + t[i:])

    def sources(self):
        return {r["id"]: r for r in csv.DictReader(io.StringIO(self.v.read("_sources.csv")))}

    # ---------------------------------------------------------------- tests

    def test_a_rebases_cleanly_and_pushes(self):
        assert self.sync_a.returncode == 0, self.sync_a.stdout + self.sync_a.stderr
        assert "pushed: yes" in self.sync_a.stdout

    def test_b_stops_on_the_article_then_finishes(self):
        assert self.stop_b.returncode == 3, self.stop_b.stdout + self.stop_b.stderr
        assert f"needs-human: {ARTICLE_B}" in self.stop_b.stdout
        assert ARTICLE_B in self.conflicted_b
        assert self.fix_b.returncode == 0, self.fix_b.stdout
        assert f"{QID} collision" in self.fix_b.stdout
        assert self.cont_b.returncode == 0, self.cont_b.stdout + self.cont_b.stderr
        assert self.sync_b.returncode == 0, self.sync_b.stdout + self.sync_b.stderr
        assert "pushed: yes" in self.sync_b.stdout

    def test_fresh_clone_passes_the_gate(self):
        for name, p in self.checks.items():
            assert p.returncode == 0, f"{name}: " + (p.stdout + p.stderr)[-2500:]

    def test_pushed_ids_stay_and_collisions_get_hash_ids(self):
        src = self.sources()
        for sid, u in zip(LEG, A_URLS):
            assert src[sid]["url"] == u
        hb = [kbid.source_id(u) for u in B_URLS]
        for h, u in zip(hb, B_URLS):
            assert src[h]["url"] == u
        art = self.v.read(ARTICLE_B)
        keeper = art[art.index(KEEPER):art.index("## Reference: each option")]
        for sid in LEG:
            assert not re.search(rf"{sid}\b", keeper + art.split("---")[1])
        for h in hb:
            assert h in keeper
            assert h in art.split("---")[1], "front matter sources: must list the renumbered ids"
        assert FILES_NOW in art
        assert "status: partial" in art
        assert f"[DOC {LEG[0]}]" in self.v.read(ARTICLE_A)

    def test_answers_distinct_and_whole(self):
        ans = self.v.read("_answers.md")
        qa, qb = QID, kbid.answer_id(Q_B)
        assert qa != qb
        assert ans.count(f"## {qa}. ") == 1
        for q in (qa, qb):
            sec = ans[ans.index(f"## {q}. "):]
            sec = sec[:sec.index("\n## ", 1)].rstrip()
            assert sec.endswith(FOOTER), sec
        assert f"`_answers.md` {qb}." in self.v.read(ARTICLE_B)
        assert f"`_answers.md` {qa}." in self.v.read(ARTICLE_A)

    def test_b_trailers_name_only_b_and_log_finds_it(self):
        hb = kbid.source_id(B_URLS[0])
        out = self.v.git("log", "--format=%s%x1f%(trailers:only,unfold)%x1e", f"{self.main0}..HEAD")
        recs = dict(r.strip("\n").split("\x1f") for r in out.split("\x1e") if "\x1f" in r)
        tb = recs["docs(kb): research-b"]
        assert f"KB-Answers: {kbid.answer_id(Q_B)}\n" in tb + "\n"
        assert "KB-Topics: agents/api-tokens-issue-and-store" in tb
        assert LEG[0] not in tb
        log = self.v.kbgit("log", hb)
        assert log.returncode == 0, log.stdout
        assert "docs(kb): research-b" in log.stdout
        assert "[trailer]" in log.stdout
