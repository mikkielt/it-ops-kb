"""Sync tests: `kbgit.py sync` against a throwaway remote (`python3 _tools/tests.py -k sync`).

  TestSyncRules            sync's argument handling and path classes (no git needed)
  TestSyncInGit            (marker git) a copy of the kb committed into a temp repo, a bare clone of it as the "remote" (never the
                           real origin) and two clones A and B with the hooks installed. In order:
                           1. A adds a source row and an article and pushes with `sync --push`; B (now behind) adds
                              another source row and an answer: `sync --dry-run` changes nothing, a dirty tree is
                              refused (exit 2), then `sync --push` rebases, fixes, passes the gate and pushes;
                           2. A and B both take the legacy id S9999 for different urls, both head an answer
                              QK-sync-shared (different questions): A's pushed S9999 and QK-sync-shared stay, B's sync
                              renumbers its own (citations and mentions follow), trailers are refreshed and check.py passes;
                           3. A and B edit the same article line: B's sync stops with exit 3, the rebase in progress.
                           The gate skips tests.py here (KB_SYNC_NO_TESTS=1: no recursive test run). Skipped without git.
  TestPrePushInGit         (marker git) the pre-push hook blocks a plain push when the gate fails; tags and sync pushes pass.
"""
import csv, io, os, re, shutil

import pytest

import kbgit, kbid
from conftest import Repo, copy_kb, git_env, requires_git


def rows(text):
    return {r["id"]: r for r in csv.DictReader(io.StringIO(text))}


class TestSyncRules:
    def test_mechanical_paths(self):
        for p in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_conflicts.md", "_coverage.csv",
                  "_tools/lint_baseline.txt", "_self/coverage.md"):
            assert p in kbgit.MECHANICAL
        for p in ("auth/kerberos.md", "_tools/kbgit.py", "AGENTS.md", "README.md", ".gitattributes", "_artifacts.csv"):
            assert p not in kbgit.MECHANICAL

    def test_fix_args_and_renumber_lines(self):
        assert kbgit.fix_args(None, "u", "o") == ["fix"]
        assert kbgit.fix_args("b", "u", "o") == ["fix", "--base", "b", "--upstream", "u", "--side", "o"]
        out = "  _sources.csv: S9999 collision: https://a.example.com/ -> S-aaaaaaaa (hash id)\n  wrote _sources.csv\n"
        assert kbgit.renumbered(out) == ["_sources.csv: S9999 collision: https://a.example.com/ -> S-aaaaaaaa (hash id)"]

    def test_push_rejection_patterns(self):
        assert kbgit.REJECTED.search(" ! [rejected]        HEAD -> main (fetch first)")
        assert kbgit.REJECTED.search("Updates were rejected because the tip ... non-fast-forward")
        assert not kbgit.REJECTED.search("fatal: Could not read from remote repository.")


@requires_git
@pytest.mark.git
class TestSyncInGit:
    URL_A1, URL_B1 = "https://learn.microsoft.com/en-us/sync-test/a1", "https://learn.microsoft.com/en-us/sync-test/b1"
    URL_A2, URL_B2 = "https://learn.microsoft.com/en-us/sync-test/a2", "https://learn.microsoft.com/en-us/sync-test/b2"
    Q_B = "Does the sync test answer survive a rebase?"
    Q_SHARED_A, Q_SHARED_B = "What does clone a ask?", "What does clone b ask about sync?"
    Q_FOOT_A, Q_FOOT_B = "Which footer does clone a write?", "Which footer does clone b write?"

    @classmethod
    def foot_block(cls, q):
        return f"\n## {kbid.answer_id(q)}. {q}\n- An answer from the question {q[:26]!r}. [UNK]\n\n_Agent: kb-research_\n"

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        cls.tmp = str(tmp_path_factory.mktemp("kb-sync"))
        cls.env = git_env(KB_SYNC_NO_TESTS="1")
        top = Repo(cls.tmp, cls.env)
        seed = Repo(copy_kb(os.path.join(cls.tmp, "seed"), skip=("_fetch_state.csv",)), cls.env)
        seed.git("init", "-q", "-b", "main")
        seed.git("add", "-A")
        seed.git("commit", "-q", "-m", "base")
        cls.remote = os.path.join(cls.tmp, "remote.git")
        top.git("clone", "-q", "--bare", seed.path, cls.remote)
        cls.a, cls.b = Repo(os.path.join(cls.tmp, "a"), cls.env), Repo(os.path.join(cls.tmp, "b"), cls.env)
        for d in (cls.a, cls.b):
            top.git("clone", "-q", cls.remote, d.path)
            assert d.kbgit("install-hooks").returncode == 0
        cls.base = cls.a.git("rev-parse", "HEAD").strip()

        # 1. A: a source row + an article; B: another source row + an answer
        cls.add_source(cls.a, "S-", cls.URL_A1, "a1")
        cls.article(cls.a, "a", [kbid.source_id(cls.URL_A1)], ["The first fact from clone a."])
        cls.commit(cls.a, "docs(kb): sync test a1")
        cls.push_a1 = cls.a.kbgit("sync", "--push")
        # A's push is 1 commit, or 2 when fix had to sort its row into place (its hash id sorts before a later one)
        cls.a1_pushed = int(Repo(cls.remote, cls.env).git("rev-list", "--count", f"{cls.base}..main").strip())
        hb = kbid.source_id(cls.URL_B1)
        cls.add_source(cls.b, "S-", cls.URL_B1, "b1")
        cls.b.append("_answers.md", f"\n## {kbid.answer_id(cls.Q_B)}. {cls.Q_B}\n\nYes, it does. [DOC {hb}]\n")
        cls.commit(cls.b, "docs(kb): sync test b1")
        cls.b_head_before = cls.b.rev("HEAD")
        cls.b_sources_before = cls.b.read("_sources.csv")
        cls.dry = cls.b.kbgit("sync", "--dry-run", "--push")
        cls.b_after_dry = (cls.b.rev("HEAD"), cls.b.git("status", "--porcelain"), cls.b.read("_sources.csv"))
        cls.b.append("README.md", "x\n")
        cls.b.git("add", "README.md")
        cls.b.append("_gaps.md", "x\n")
        cls.dirty = cls.b.kbgit("sync", "--push")
        cls.b.git("reset", "-q", "--hard", "HEAD")
        cls.push_b1 = cls.b.kbgit("sync", "--push")

        # 2. both clones take the legacy id S9999 for different urls
        cls.add_source(cls.a, "S9999", cls.URL_A2, "a2")
        cls.article(cls.a, "a2", ["S9999"], ["Clone a cites its S9999."])
        cls.a.append("_answers.md", f"\n## QK-sync-shared. {cls.Q_SHARED_A}\n\nClone a answers. [DOC S9999]\n")
        cls.commit(cls.a, "docs(kb): sync test a2 with S9999")
        cls.push_a2 = cls.a.kbgit("sync", "--push")
        cls.add_source(cls.b, "S9999", cls.URL_B2, "b2")
        cls.article(cls.b, "b2", ["S9999"], ["Clone b cites its S9999.", "Answer: `_answers.md` QK-sync-shared."])
        cls.b.append("_answers.md", f"\n## QK-sync-shared. {cls.Q_SHARED_B}\n\nClone b answers. [DOC S9999]\n")
        cls.commit(cls.b, "docs(kb): sync test b2 with S9999")
        cls.push_b2 = cls.b.kbgit("sync", "--push")
        cls.b2_checks = {t: cls.b.tool(t, *args) for t, args in
                         (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")))}
        cls.b2_trailers = cls.b.kbgit("check-trailers", f"{cls.base}..HEAD")

        # 2b. both clones add a research answer at the same place, with the same footer line (a zealous merge splices)
        for d, q in ((cls.a, cls.Q_FOOT_A), (cls.b, cls.Q_FOOT_B)):
            t = d.read("_answers.md")
            i = t.index("\n## R1. ")
            d.write("_answers.md", t[:i] + cls.foot_block(q) + t[i:])
            cls.commit(d, f"docs(kb): answer {kbid.answer_id(q)}")
        cls.push_a4 = cls.a.kbgit("sync", "--push")
        cls.push_b4 = cls.b.kbgit("sync", "--push")
        cls.b4_log = cls.b.git("log", "--format=%s%x1f%(trailers:key=KB-Answers,valueonly,unfold)%x1e", "-n", "5")

        # 3. the same article line edited on both sides
        cls.pull_a = cls.a.kbgit("sync")
        for d, who in ((cls.a, "clone a now words it"), (cls.b, "clone b words it")):
            d.write("windows/sync-test-a.md", d.read("windows/sync-test-a.md").replace(
                "The first fact from clone a.", f"The first fact, as {who}."))
            cls.commit(d, "docs(kb): reword the first fact")
        cls.push_a3 = cls.a.kbgit("sync", "--push")
        cls.b3_head = cls.b.rev("HEAD")
        cls.push_b3 = cls.b.kbgit("sync", "--push")
        cls.b3_rebasing = os.path.isdir(cls.b.file(".git/rebase-merge")) or os.path.isdir(cls.b.file(".git/rebase-apply"))
        cls.b3_again = cls.b.kbgit("sync", "--push")
        cls.b.git("rebase", "--abort")
        cls.b3_after_abort = cls.b.rev("HEAD")
        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers

    @classmethod
    def add_source(cls, d, sid, url, tag):
        sid = kbid.source_id(url) if sid == "S-" else sid
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerow([sid, url, f"Sync test {tag}", "Microsoft", "MIT", "2026-09-25", "v", "", "", ""])
        d.append("_sources.csv", buf.getvalue())

    @classmethod
    def article(cls, d, name, sids, facts):
        d.write(f"windows/sync-test-{name}.md",
                f"---\ntopic: windows/sync-test-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-25\n"
                f"sources: [{', '.join(sids)}]\nstatus: partial\n---\n# Sync test {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
                + "".join(f"- {f} [DOC {sids[0]}]\n" for f in facts) + "\n## Reference\n\n## Examples\n")

    @classmethod
    def commit(cls, d, msg):
        r = d.tool("build_index.py")
        assert r.returncode == 0, r.stdout + r.stderr
        d.git("add", "-A")
        d.git("commit", "-q", "-m", msg)

    def remote_file(self, rel):
        return Repo(self.remote, self.env).git("show", f"main:{rel}")

    # ---------------------------------------------------------------- tests

    def test_clones_only_know_the_temp_remote(self):
        for d in (self.a, self.b):
            assert d.git("remote", "get-url", "origin").strip() == self.remote
            assert os.path.realpath(d.path).startswith(os.path.realpath(self.tmp))

    def test_first_push_needs_no_rebase(self):
        r = self.push_a1
        assert r.returncode == 0, r.stdout + r.stderr
        assert "local 1 ahead, 0 behind" in r.stdout
        assert "pushed: yes" in r.stdout

    def test_dry_run_changes_nothing(self):
        r = self.dry
        assert r.returncode == 0, r.stdout + r.stderr
        assert f"local 1 ahead, {self.a1_pushed} behind" in r.stdout
        assert "would rebase 1 local commit(s)" in r.stdout
        assert "mechanical (fix): _sources.csv" in r.stdout
        assert self.b_after_dry == (self.b_head_before, "", self.b_sources_before)
        assert "pushed: yes" not in r.stdout

    def test_dirty_tree_is_refused(self):
        r = self.dirty
        assert r.returncode == 2, r.stdout + r.stderr
        assert "staged:   README.md" in r.stdout
        assert "unstaged: _gaps.md" in r.stdout
        assert "git stash" in r.stdout

    def test_clean_rebase_is_fixed_gated_and_pushed(self):
        r = self.push_b1
        assert r.returncode == 0, r.stdout + r.stderr
        assert "commits rebased: 1" in r.stdout
        assert re.search(r"gate check.py: ok", r.stdout)
        assert re.search(r"gate check-trailers origin/main\.\.HEAD: ok", r.stdout)
        assert "gate tests.py (fast): skipped" in r.stdout
        assert "pushed: yes" in r.stdout
        src = rows(self.remote_file("_sources.csv"))
        ha, hb = kbid.source_id(self.URL_A1), kbid.source_id(self.URL_B1)
        assert ha in src
        assert hb in src
        assert src[ha]["used_in"] == "windows/sync-test-a.md"
        assert kbid.answer_id(self.Q_B) in self.remote_file("_answers.md")
        ids = list(rows(self.remote_file("_sources.csv")))
        assert ids == sorted(ids, key=kbid.sort_key)

    def test_collision_renumbered_with_trailers_refreshed(self):
        assert self.push_a2.returncode == 0, self.push_a2.stdout + self.push_a2.stderr
        r = self.push_b2
        assert r.returncode == 0, r.stdout + r.stderr
        assert re.search(r"ids renumbered: .*S9999", r.stdout)
        assert re.search(r"ids renumbered: .*QK-sync-shared collision", r.stdout)
        assert "trailers refreshed on" in r.stdout
        assert "pushed: yes" in r.stdout
        src = rows(self.remote_file("_sources.csv"))
        hb = kbid.source_id(self.URL_B2)
        assert (src["S9999"]["url"], src[hb]["url"]) == (self.URL_A2, self.URL_B2)  # pushed ids are never renumbered
        assert "[DOC S9999]" in self.remote_file("windows/sync-test-a2.md")
        b2 = self.remote_file("windows/sync-test-b2.md")
        qb = kbid.answer_id(self.Q_SHARED_B)
        assert f"[DOC {hb}]" in b2
        assert f"`_answers.md` {qb}." in b2
        ans = self.remote_file("_answers.md")
        for want in (f"## QK-sync-shared. {self.Q_SHARED_A}\n\nClone a answers. [DOC S9999]",
                     f"## {qb}. {self.Q_SHARED_B}\n\nClone b answers. [DOC {hb}]"):
            assert want in ans
        for t, p in self.b2_checks.items():
            assert p.returncode == 0, f"{t}: " + (p.stdout + p.stderr)[-2000:]
        assert self.b2_trailers.returncode == 0, self.b2_trailers.stdout

    def test_shared_footer_answers_stay_whole(self):
        """Rebased with diff3: B's answer is added after A's, A's section is untouched, B's trailers name only B's answer."""
        for r in (self.push_a4, self.push_b4):
            assert r.returncode == 0, r.stdout + r.stderr
        ans = self.remote_file("_answers.md")
        blocks = [self.foot_block(q) for q in (self.Q_FOOT_A, self.Q_FOOT_B)]
        assert blocks[0] + blocks[1] in ans
        subjects = dict(ln.strip("\n").split("\x1f") for ln in self.b4_log.split("\x1e") if "\x1f" in ln)
        assert subjects.get(f"docs(kb): answer {kbid.answer_id(self.Q_FOOT_B)}", "").strip() == kbid.answer_id(self.Q_FOOT_B)

    def test_same_line_edit_needs_a_human(self):
        assert self.pull_a.returncode == 0, self.pull_a.stdout + self.pull_a.stderr
        assert "pushed: no (without --push)" in self.pull_a.stdout
        assert self.push_a3.returncode == 0, self.push_a3.stdout + self.push_a3.stderr
        r = self.push_b3
        assert r.returncode == 3, r.stdout + r.stderr
        assert "needs-human: windows/sync-test-a.md" in r.stdout
        assert "git rebase --abort" in r.stdout
        assert "  python3 _tools/kbgit.py sync --push\n" in r.stdout  # the next step repeats the user's own command
        assert re.search(r"sync-state: base=[0-9a-f]{40} upstream=[0-9a-f]{40} orig_head=[0-9a-f]{40}", r.stdout)
        assert self.b3_rebasing, "the rebase must be left in progress"
        assert self.b3_again.returncode == 2, self.b3_again.stdout
        assert "rebase is in progress" in self.b3_again.stdout
        assert self.b3_after_abort == self.b3_head
        assert "clone b words it" not in self.remote_file("windows/sync-test-a.md")


@requires_git
@pytest.mark.git
class TestPrePushInGit:
    """The pre-push hook (.githooks/pre-push -> `kbgit.py hook pre-push`): a plain `git push` of the checked-out branch
    runs the gate and is refused when a check fails; a tag push and sync's own push (KB_GATE_DONE=1) are not gated."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        tmp = str(tmp_path_factory.mktemp("kb-prepush"))
        env = git_env(KB_SYNC_NO_TESTS="1")
        top = Repo(tmp, env)
        seed = Repo(copy_kb(os.path.join(tmp, "seed"), skip=("_fetch_state.csv",)), env)
        seed.git("init", "-q", "-b", "main")
        seed.git("add", "-A")
        seed.git("commit", "-q", "-m", "base")
        cls.remote = Repo(os.path.join(tmp, "remote.git"), env)
        top.git("clone", "-q", "--bare", seed.path, cls.remote.path)
        c = cls.c = Repo(os.path.join(tmp, "c"), env)
        top.git("clone", "-q", cls.remote.path, c.path)
        assert c.kbgit("install-hooks").returncode == 0
        cls.base = c.rev("HEAD")
        # a hand edit of the generated _coverage.csv: build_index.py --check fails
        c.write("_coverage.csv", c.read("_coverage.csv").replace(",P1,", ",P9,", 1))
        c.git("commit", "-qam", "chore: hand edit")
        cls.bad = c.run_git("push", "-q", "origin", "HEAD:main")
        cls.after_bad = cls.remote.rev("main")
        c.git("tag", "t-prepush")
        cls.tag = c.run_git("push", "-q", "origin", "t-prepush")
        cls.gated = c.run_git("push", "-q", "origin", "HEAD:main", env={"KB_GATE_DONE": "1"})
        cls.after_gated = cls.remote.rev("main")
        assert c.tool("build_index.py").returncode == 0
        c.git("commit", "-qam", "chore: rebuild the index")
        cls.good = c.run_git("push", "-q", "origin", "HEAD:main")
        cls.after_good = cls.remote.rev("main")
        cls.head = c.rev("HEAD")

    def test_failing_gate_blocks_a_plain_push(self):
        assert self.bad.returncode != 0, self.bad.stdout + self.bad.stderr
        assert "kb pre-push build_index.py --check: FAILED" in self.bad.stderr
        assert "nothing pushed" in self.bad.stderr
        assert self.after_bad == self.base

    def test_tags_and_sync_pushes_are_not_gated(self):
        assert self.tag.returncode == 0, self.tag.stderr
        assert self.gated.returncode == 0 and self.after_gated != self.base, self.gated.stderr

    def test_green_gate_pushes(self):
        assert self.good.returncode == 0, self.good.stdout + self.good.stderr
        assert "kb pre-push selfdoc.py stale" in self.good.stderr and "kb pre-push kbgit.py fix --check: ok" in self.good.stderr
        assert self.after_good == self.head
