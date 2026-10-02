"""Sync tests: `kbgit.py sync` against a throwaway remote (`python3 _tools/tests.py -k sync`).

  TestSyncRules            sync's argument handling and path classes (no git needed)
  TestSyncInGit            (marker git) a bare clone of the run's shared kb seed (conftest.kb_seed) as the "remote" (never
                           the real origin) and two clones A and B with the hooks installed. In order:
                           1. A adds a source row and an article and pushes with `sync --push`; B (now behind) adds
                              another source row and an answer: `sync --dry-run` changes nothing, a dirty tree is
                              refused (exit 2), then `sync --push` rebases, fixes, passes the gate and pushes;
                           2. A and B both take the legacy id S9999 for different urls, both head an answer
                              QK-sync-shared (different questions): A's pushed S9999 and QK-sync-shared stay, B's sync
                              renumbers its own (citations and mentions follow), trailers are refreshed and check.py passes;
  TestSyncConflictInGit    (marker git) the same set-up, apart so the two run in parallel: A pushes an article and B pulls
                           it, then A and B edit the same line: B's sync stops with exit 3, the rebase in progress.
                           The gate skips tests.py here (KB_SYNC_NO_TESTS=1: no recursive test run). Skipped without git.
  TestSyncSessionRules     (`tests.py -k sync_foreign_session`, with the next) the session sync runs in and a trailer's
                           comparable form, no git needed
  TestSyncForeignSessionInGit  (marker git) a planted local commit whose Claude-Session trailer names another session:
                           `sync --push` refuses it (exit 1, naming it, nothing pushed); a same-session commit, one
                           already on the remote and an unknown current session pass (`--dry-run`)
  TestPrePushInGit         (marker git) the pre-push hook blocks a plain push when the gate fails; tags and sync pushes pass.
  TestSprintWorktreeHooks  (marker git; `tests.py -k sprint_worktree_has_commit_hooks`) a `git worktree` of a clone with
                           the hooks installed, relative or as an absolute path to the main clone's .githooks, runs them:
                           its commit gets KB-* trailers and install-hooks there says installed; planted: unset hooks
                           (no trailers, check-trailers exit 1), a .githooks outside the clone's worktrees or one
                           without the scripts (not installed).
  TestSyncReexec           (marker git; `tests.py -k sync_reexec_after_kbgit_rebase`) an incoming commit changes kbgit.py's
                           push decision: sync re-runs itself with the rebased code, which decides the push; with the
                           re-run disabled (KB_SYNC_REEXEC=1) the planted failure: it stops, exit 3, nothing pushed.
  TestAutonomousWrite      (marker git; `tests.py -k autonomous_write`) the writers that run without a person reach
                           origin's main only through `kbgit.py sync --push` (kb/_self/querylog.md, Delivery): the
                           query log's `apply --push` (ql_deliver.Pusher) against a small fixture origin, every
                           command it starts watched (WritePaths: a `git push` outside sync, or origin's main moving
                           outside sync, is a violation), sync itself a stub that pushes HEAD, so the scenario takes
                           seconds (the real sync is TestSyncInGit's); a red automatic push is reverted through sync
                           and files one bug item, and the next run files none; research (ql_research) and ingest
                           (kbingest.py) push nothing and start no `git push` or `git commit`; a planted direct push,
                           through the pusher's `run` or around it, and a planted push in a writer's source fail.
  TestSyncPushRetries      (`tests.py -k sync_push_retries_backoff` and `-k push_retry_skips_gates_when_rebase_touches_no_gate_path`)
                           a push rejected because origin/main moved is tried again with a doubling pause up to a bound, the
                           pause schedule and the bound over a range of values with sleeping patched out, and against a bare
                           remote whose pre-receive hook rejects the first pushes; the gates are not re-run when the rebase
                           changed no path a gate reads, and the one that reads a changed path is.
  TestSyncGateTests        (`tests.py -k sync_gate_`) the gate's tests.py run keeps the git scenarios of the test files a
                           changed tool selects: a planted tool change that breaks one fails the gate (real pytest over a
                           planted tree), a content-only change leaves its own out; a change to kbgit.py or querylog.py
                           collects TestCloudInGit.
"""
import ast, contextlib, csv, io, json, os, re, shutil, subprocess
from pathlib import Path

import pytest

import build_index, kbgit, kbid, kblane, kg_bridge, kg_history, kg_hooks, kg_lane, kg_merge, kg_sync, kg_trailers
from conftest import TOOLS, P, Repo, git_env, requires_git


def clones(kb_seed, tmp, env, names):
    """A bare clone of the shared seed as the remote and one clone per name with the hooks installed: (remote, clones,
    base commit). The seed is committed once per run: a fresh kb tree is slow to read the first time on Windows."""
    top, remote = Repo(tmp, env), os.path.join(tmp, "remote.git")
    top.git("clone", "-q", "--bare", str(kb_seed[0]), remote)
    out = []
    for n in names:
        d = Repo(os.path.join(tmp, n), env)
        top.git("clone", "-q", remote, d.path)
        assert d.kbgit("install-hooks").returncode == 0
        out.append(d)
    return remote, out, kb_seed[1]


def rows(text):
    return {r["id"]: r for r in csv.DictReader(io.StringIO(text))}


class TestSyncRules:
    def test_mechanical_paths(self):
        for p in [P(f) for f in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_conflicts.md",
                                 "_coverage.csv")] + ["_tools/lint_baseline.txt", kbgit.FB(build_index.COVERAGE_MD)]:
            assert p in kg_sync.MECHANICAL
        for p in (P("auth/kerberos.md"), "_tools/kbgit.py", "AGENTS.md", "README.md", ".gitattributes", P("_artifacts.csv")):
            assert p not in kg_sync.MECHANICAL

    def test_fix_args_and_renumber_lines(self):
        assert kg_sync.fix_args(None, "u", "o") == ["fix"]
        assert kg_sync.fix_args("b", "u", "o") == ["fix", "--base", "b", "--upstream", "u", "--side", "o"]
        out = "  _sources.csv: S9999 collision: https://a.example.com/ -> S-aaaaaaaa (hash id)\n  wrote _sources.csv\n"
        assert kg_sync.renumbered(out) == ["_sources.csv: S9999 collision: https://a.example.com/ -> S-aaaaaaaa (hash id)"]

    def test_push_rejection_patterns(self):
        assert kg_sync.REJECTED.search(" ! [rejected]        HEAD -> main (fetch first)")
        assert kg_sync.REJECTED.search("Updates were rejected because the tip ... non-fast-forward")
        assert kg_sync.REJECTED.search("remote: error: cannot lock ref 'refs/heads/main': is at 1478 but expected f8d8")  # main moved mid-push
        assert not kg_sync.REJECTED.search("fatal: Could not read from remote repository.")


class SyncScenario:
    """Helpers of the sync scenarios: a source row, an article, a commit, a file on the remote."""

    @classmethod
    def add_source(cls, d, sid, url, tag):
        sid = kbid.source_id(url) if sid == "S-" else sid
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerow([sid, url, f"Sync test {tag}", "Microsoft", "MIT", "copy", "2026-09-25", "v", "", "",
                                                         ""])
        d.append(P("_sources.csv"), buf.getvalue())

    @classmethod
    def article(cls, d, name, sids, facts):
        d.write(P(f"windows/sync-test-{name}.md"),
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


@requires_git
@pytest.mark.git
class TestSyncInGit(SyncScenario):
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
    def scenario(cls, tmp_path_factory, kb_seed):
        cls.tmp = str(tmp_path_factory.mktemp("kb-sync"))
        cls.env = git_env(KB_SYNC_NO_TESTS="1")
        cls.remote, (cls.a, cls.b), cls.base = clones(kb_seed, cls.tmp, cls.env, ("a", "b"))

        # 1. A: a source row + an article; B: another source row + an answer
        cls.add_source(cls.a, "S-", cls.URL_A1, "a1")
        cls.article(cls.a, "a", [kbid.source_id(cls.URL_A1)], ["The first fact from clone a."])
        cls.commit(cls.a, "docs(kb): sync test a1")
        cls.push_a1 = cls.a.kbgit("sync", "--push")
        # A's push is 1 commit, or 2 when fix had to sort its row into place (its hash id sorts before a later one)
        cls.a1_pushed = int(Repo(cls.remote, cls.env).git("rev-list", "--count", f"{cls.base}..main").strip())
        hb = kbid.source_id(cls.URL_B1)
        cls.add_source(cls.b, "S-", cls.URL_B1, "b1")
        cls.b.append(P("_answers.md"), f"\n## {kbid.answer_id(cls.Q_B)}. {cls.Q_B}\n\nYes, it does. [DOC {hb}]\n")
        cls.commit(cls.b, "docs(kb): sync test b1")
        cls.b_head_before = cls.b.rev("HEAD")
        cls.b_sources_before = cls.b.read(P("_sources.csv"))
        cls.dry = cls.b.kbgit("sync", "--dry-run", "--push")
        cls.b_after_dry = (cls.b.rev("HEAD"), cls.b.git("status", "--porcelain"), cls.b.read(P("_sources.csv")))
        cls.b.append("README.md", "x\n")
        cls.b.git("add", "README.md")
        cls.b.append(P("_gaps.md"), "x\n")
        cls.dirty = cls.b.kbgit("sync", "--push")
        cls.b.git("reset", "-q", "--hard", "HEAD")
        cls.push_b1 = cls.b.kbgit("sync", "--push")

        # 2. both clones take the legacy id S9999 for different urls
        cls.add_source(cls.a, "S9999", cls.URL_A2, "a2")
        cls.article(cls.a, "a2", ["S9999"], ["Clone a cites its S9999."])
        cls.a.append(P("_answers.md"), f"\n## QK-sync-shared. {cls.Q_SHARED_A}\n\nClone a answers. [DOC S9999]\n")
        cls.commit(cls.a, "docs(kb): sync test a2 with S9999")
        cls.push_a2 = cls.a.kbgit("sync", "--push")
        cls.add_source(cls.b, "S9999", cls.URL_B2, "b2")
        cls.article(cls.b, "b2", ["S9999"], ["Clone b cites its S9999.", "Answer: `_answers.md` QK-sync-shared."])
        cls.b.append(P("_answers.md"), f"\n## QK-sync-shared. {cls.Q_SHARED_B}\n\nClone b answers. [DOC S9999]\n")
        cls.commit(cls.b, "docs(kb): sync test b2 with S9999")
        cls.push_b2 = cls.b.kbgit("sync", "--push")
        cls.b2_checks = {t: cls.b.tool(t, *args) for t, args in
                         (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")))}
        cls.b2_trailers = cls.b.kbgit("check-trailers", f"{cls.base}..HEAD")

        # 2b. both clones add a research answer at the same place, with the same footer line (a zealous merge splices)
        for d, q in ((cls.a, cls.Q_FOOT_A), (cls.b, cls.Q_FOOT_B)):
            t = d.read(P("_answers.md"))
            i = t.index("\n## R1. ")
            d.write(P("_answers.md"), t[:i] + cls.foot_block(q) + t[i:])
            cls.commit(d, f"docs(kb): answer {kbid.answer_id(q)}")
        cls.push_a4 = cls.a.kbgit("sync", "--push")
        cls.push_b4 = cls.b.kbgit("sync", "--push")
        cls.b4_log = cls.b.git("log", "--format=%s%x1f%(trailers:key=KB-Answers,valueonly,unfold)%x1e", "-n", "5")

        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

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
        assert f"mechanical (fix): {P('_sources.csv')}" in r.stdout
        assert self.b_after_dry == (self.b_head_before, "", self.b_sources_before)
        assert "pushed: yes" not in r.stdout

    def test_dirty_tree_is_refused(self):
        r = self.dirty
        assert r.returncode == 2, r.stdout + r.stderr
        assert "staged:   README.md" in r.stdout
        assert f"unstaged: {P('_gaps.md')}" in r.stdout
        assert "git stash" in r.stdout

    def test_clean_rebase_is_fixed_gated_and_pushed(self):
        r = self.push_b1
        assert r.returncode == 0, r.stdout + r.stderr
        assert "commits rebased: 1" in r.stdout
        assert re.search(r"gate check.py: ok", r.stdout)
        assert re.search(r"gate check-trailers origin/main\.\.HEAD: ok", r.stdout)
        assert "gate tests.py (changed): skipped" in r.stdout
        assert "gate build_index.py --check" not in r.stdout  # sync's fix rebuilt the generated files already
        assert "pushed: yes" in r.stdout
        src = rows(self.remote_file(P("_sources.csv")))
        ha, hb = kbid.source_id(self.URL_A1), kbid.source_id(self.URL_B1)
        assert ha in src
        assert hb in src
        assert src[ha]["used_in"] == "windows/sync-test-a.md"
        assert kbid.answer_id(self.Q_B) in self.remote_file(P("_answers.md"))
        ids = list(rows(self.remote_file(P("_sources.csv"))))
        assert ids == sorted(ids, key=kbid.sort_key)

    def test_collision_renumbered_with_trailers_refreshed(self):
        assert self.push_a2.returncode == 0, self.push_a2.stdout + self.push_a2.stderr
        r = self.push_b2
        assert r.returncode == 0, r.stdout + r.stderr
        assert re.search(r"ids renumbered: .*S9999", r.stdout)
        assert re.search(r"ids renumbered: .*QK-sync-shared collision", r.stdout)
        assert "trailers refreshed on" in r.stdout
        assert "pushed: yes" in r.stdout
        src = rows(self.remote_file(P("_sources.csv")))
        hb = kbid.source_id(self.URL_B2)
        assert (src["S9999"]["url"], src[hb]["url"]) == (self.URL_A2, self.URL_B2)  # pushed ids are never renumbered
        assert "[DOC S9999]" in self.remote_file(P("windows/sync-test-a2.md"))
        b2 = self.remote_file(P("windows/sync-test-b2.md"))
        qb = kbid.answer_id(self.Q_SHARED_B)
        assert f"[DOC {hb}]" in b2
        assert f"`_answers.md` {qb}." in b2
        ans = self.remote_file(P("_answers.md"))
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
        ans = self.remote_file(P("_answers.md"))
        blocks = [self.foot_block(q) for q in (self.Q_FOOT_A, self.Q_FOOT_B)]
        assert blocks[0] + blocks[1] in ans
        subjects = dict(ln.strip("\n").split("\x1f") for ln in self.b4_log.split("\x1e") if "\x1f" in ln)
        assert subjects.get(f"docs(kb): answer {kbid.answer_id(self.Q_FOOT_B)}", "").strip() == kbid.answer_id(self.Q_FOOT_B)




@requires_git
@pytest.mark.git
class TestSyncConflictInGit(SyncScenario):
    URL_A1 = TestSyncInGit.URL_A1

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        cls.tmp = str(tmp_path_factory.mktemp("kb-sync-conflict"))
        cls.env = git_env(KB_SYNC_NO_TESTS="1")
        cls.remote, (cls.a, cls.b), cls.base = clones(kb_seed, cls.tmp, cls.env, ("a", "b"))
        cls.add_source(cls.a, "S-", cls.URL_A1, "a1")
        cls.article(cls.a, "a", [kbid.source_id(cls.URL_A1)], ["The first fact from clone a."])
        cls.commit(cls.a, "docs(kb): sync test a1")
        cls.push_a1 = cls.a.kbgit("sync", "--push")
        assert cls.push_a1.returncode == 0, cls.push_a1.stdout + cls.push_a1.stderr
        cls.pull_b = cls.b.kbgit("sync")

        # the same article line edited on both sides
        for d, who in ((cls.a, "clone a now words it"), (cls.b, "clone b words it")):
            d.write(P("windows/sync-test-a.md"), d.read(P("windows/sync-test-a.md")).replace(
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

    def test_same_line_edit_needs_a_human(self):
        assert self.pull_b.returncode == 0, self.pull_b.stdout + self.pull_b.stderr
        assert "pushed: no (without --push)" in self.pull_b.stdout
        assert self.push_a3.returncode == 0, self.push_a3.stdout + self.push_a3.stderr
        r = self.push_b3
        assert r.returncode == 3, r.stdout + r.stderr
        assert f"needs-human: {P('windows/sync-test-a.md')}" in r.stdout
        assert "git rebase --abort" in r.stdout
        assert "  python3 _tools/kbgit.py sync --push\n" in r.stdout  # the next step repeats the user's own command
        assert re.search(r"sync-state: base=[0-9a-f]{40} upstream=[0-9a-f]{40} orig_head=[0-9a-f]{40}", r.stdout)
        assert self.b3_rebasing, "the rebase must be left in progress"
        assert self.b3_again.returncode == 2, self.b3_again.stdout
        assert "rebase is in progress" in self.b3_again.stdout
        assert self.b3_after_abort == self.b3_head
        assert "clone b words it" not in self.remote_file(P("windows/sync-test-a.md"))


SESSION_A, SESSION_B = "session_01AAAAAAAAAAAAAAAAAAAAAAAA", "session_01BBBBBBBBBBBBBBBBBBBBBBBB"


def session_url(s):
    return f"https://claude.ai/code/{s}"


class TestSyncPushRetries:
    """Backoff of a rejected push (`tests.py -k sync_push_retries_backoff`): sync_rounds over a stubbed round, no sleeping."""

    @pytest.fixture
    def rounds(self, monkeypatch):
        for k in ("KB_SYNC_PUSH_TRIES", "KB_SYNC_PUSH_PAUSE_S", "KB_SYNC_PUSH_PAUSE_MAX_S"):
            monkeypatch.delenv(k, raising=False)
        slept = []
        monkeypatch.setattr(kg_sync.time, "sleep", slept.append)

        def run(rejections):
            calls = []
            slept.clear()

            def once(a, r, host):
                calls.append(1)
                return "retry" if len(calls) <= rejections else 0
            monkeypatch.setattr(kg_sync, "sync_once", once)
            r = {"notes": []}
            a = type("A", (), dict(remote="origin", branch="main"))()
            return kg_sync.sync_rounds(a, r, None), r, slept, calls
        return run

    def test_sync_push_retries_backoff_until_the_bound_for_any_number_of_rejections(self, rounds):
        bound = kg_sync.push_tries()
        assert bound > 2
        for rejected in range(0, bound + 3):
            code, r, slept, calls = rounds(rejected)
            if rejected < bound:
                assert (code, r["tries"], len(calls)) == (0, rejected + 1, rejected + 1), rejected
            else:
                assert (code, r["tries"], len(calls)) == (1, bound, bound), rejected
                assert r["pushed"] == f"no (rejected {bound} times)"
            assert slept == [kg_sync.push_pause(n) for n in range(1, min(rejected, bound - 1) + 1)], rejected

    def test_sync_push_retries_backoff_pause_grows_and_is_capped(self, rounds, monkeypatch):
        pauses = [kg_sync.push_pause(n) for n in range(1, 12)]
        assert pauses == sorted(pauses) and pauses[0] < pauses[1] < pauses[2]
        assert max(pauses) == kg_sync.PUSH_PAUSE_MAX_S and pauses[-1] == pauses[-2]
        monkeypatch.setenv("KB_SYNC_PUSH_PAUSE_S", "0")
        assert [kg_sync.push_pause(n) for n in (1, 5)] == [0, 0]

    def test_sync_push_retries_backoff_environment_sets_the_bound_and_pause(self, rounds, monkeypatch):
        monkeypatch.setenv("KB_SYNC_PUSH_TRIES", "3")
        monkeypatch.setenv("KB_SYNC_PUSH_PAUSE_S", "0.5")
        code, r, slept, calls = rounds(10)
        assert (code, r["tries"], len(calls), slept) == (1, 3, 3, [0.5, 1.0])
        monkeypatch.setenv("KB_SYNC_PUSH_TRIES", "junk")
        assert kg_sync.push_tries() == kg_sync.PUSH_TRIES
        monkeypatch.setenv("KB_SYNC_PUSH_TRIES", "0")
        assert kg_sync.push_tries() == 1

    def test_sync_push_retries_backoff_planted_two_tries_would_fail(self, rounds):
        """The old rule gave up after two rejections: a third round must run and succeed."""
        code, r, _, calls = rounds(2)
        assert code == 0 and len(calls) == 3 and r["tries"] == 3


REJECT_N = """#!/bin/sh
d=$(dirname "$0")/..
n=$(cat "$d/reject-left" 2>/dev/null || echo 0)
if [ "$n" -gt 0 ]; then
  echo $((n - 1)) > "$d/reject-left"
  echo "! non-fast-forward (planted)" >&2
  exit 1
fi
"""

MOVE_MAIN = """#!/bin/sh
# A's pre-push hook: before A's first push another session's commit lands on origin/main, so git rejects the push itself.
if [ -f "{flag}" ]; then
  rm "{flag}"
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
  git -C "{other}" push -q --no-verify origin HEAD:refs/heads/main
fi
"""


@requires_git
@pytest.mark.git
class TestSyncPushRetriesInGit(SyncScenario):
    """A bare remote whose pre-receive hook rejects the first pushes as a moved main does, `sync --push` of clone A."""

    @pytest.fixture
    def world(self, tmp_path, kb_seed):
        env = git_env(KB_SYNC_NO_TESTS="1", KB_SYNC_PUSH_PAUSE_S="0")
        remote, (a, b), base = clones(kb_seed, str(tmp_path), env, ("a", "b"))
        w = type("World", (), {})()
        w.env, w.remote, w.a, w.b, w.base, w.bare = env, remote, a, b, base, Repo(remote, env)
        url = "https://learn.microsoft.com/en-us/sync-test/retry-a"
        self.add_source(a, "S-", url, "retry-a")
        self.article(a, "retry-a", [kbid.source_id(url)], ["Retry fact."])
        self.commit(a, "docs(kb): retry test a")
        return w

    @staticmethod
    def reject(w, n):
        hook = Path(w.remote) / "hooks" / "pre-receive"
        hook.write_text(REJECT_N, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        (Path(w.remote) / "reject-left").write_text(f"{n}\n", encoding="utf-8", newline="\n")

    def move_main_at_first_push(self, w, content):
        """B commits (content, or nothing but an empty commit) and its commit lands on origin/main just before A's first
        push, so that push is rejected for real (fetch first)."""
        if content:
            url = "https://learn.microsoft.com/en-us/sync-test/retry-b"
            self.add_source(w.b, "S-", url, "retry-b")
            self.article(w.b, "retry-b", [kbid.source_id(url)], ["Other fact."])
            self.commit(w.b, "docs(kb): retry test b")
        else:
            w.b.git("commit", "-q", "--allow-empty", "-m", "chore: nothing changed")
        hooks = Path(w.a.path).parent / "a-hooks"
        hooks.mkdir()
        flag = hooks / "move-main"
        flag.write_text("1\n", encoding="utf-8", newline="\n")
        hook = hooks / "pre-push"
        hook.write_text(MOVE_MAIN.format(flag=flag.as_posix(), other=Path(w.b.path).as_posix()), encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        w.a.git("config", "core.hooksPath", hooks.as_posix())
        return w.b.rev("HEAD")

    def test_sync_push_retries_backoff_succeeds_on_the_fourth_try_and_says_so(self, world):
        w = world
        self.reject(w, 3)
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "sync: exit 0, 4 push tries" in r.stdout, r.stdout
        assert "pushed: yes" in r.stdout
        assert w.bare.git("rev-parse", "main").strip() == w.a.rev("HEAD")

    def test_sync_push_retries_backoff_gives_up_at_the_bound_it_names(self, world):
        w = world
        self.reject(w, 50)
        env = {"KB_SYNC_PUSH_TRIES": "3"}
        r = w.a.tool("kbgit.py", "sync", "--push", env=env)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "push rejected 3 times" in r.stdout and "pushed: no (rejected 3 times)" in r.stdout, r.stdout
        assert "sync: exit 1, 3 push tries" in r.stdout
        assert w.bare.git("rev-parse", "main").strip() == w.base

    def test_push_retry_skips_gates_when_rebase_touches_no_gate_path(self, world):
        w = world
        theirs = self.move_main_at_first_push(w, content=False)
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "sync: exit 0, 2 push tries" in r.stdout, r.stdout
        assert "gate check.py: skipped: no path it reads changed" in r.stdout, r.stdout
        assert "gate check-trailers origin/main..HEAD: ok" in r.stdout
        assert "gates not re-run after the rejected push" in r.stdout
        assert w.bare.git("rev-parse", "main").strip() == w.a.rev("HEAD") and "push rejected (origin/main moved)" in r.stdout
        assert w.bare.git("merge-base", "--is-ancestor", theirs, "main") == ""

    def test_push_retry_skips_gates_when_rebase_touches_no_gate_path_planted_gate_path_reruns(self, world):
        """Planted: the incoming commit changes kb content, which check.py reads: it runs again."""
        w = world
        theirs = self.move_main_at_first_push(w, content=True)
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "sync: exit 0, 2 push tries" in r.stdout, r.stdout
        assert re.search(r"gate check.py: ok", r.stdout), r.stdout
        assert "gates not re-run after the rejected push" not in r.stdout
        assert "push rejected (origin/main moved)" in r.stdout
        assert w.bare.git("merge-base", "--is-ancestor", theirs, "main") == ""


class TestSyncSessionRules:
    """Which session sync runs in (kg_sync.current_session) and how a trailer value compares (kg_sync.session_key)."""

    def test_sync_foreign_session_key_forms(self):
        assert kg_sync.session_key(session_url(SESSION_A)) == SESSION_A
        assert kg_sync.session_key(SESSION_A + "\n") == SESSION_A
        assert kg_sync.session_key("cse_01AAAAAAAAAAAAAAAAAAAAAAAA") == SESSION_A  # a cloud session's variable
        assert kg_sync.session_key("") == kg_sync.session_key(None) == ""

    def test_sync_foreign_session_current_order(self):
        cloud, bridge = {"CLAUDE_CODE_REMOTE_SESSION_ID": "cse_01BBBBBBBBBBBBBBBBBBBBBBBB"}, {"CLAUDE_CODE_BRIDGE_SESSION_ID": SESSION_A}
        assert kg_sync.current_session(None, {}) == ""
        assert kg_sync.current_session(None, bridge) == SESSION_A
        assert kg_sync.current_session(None, {**bridge, **cloud}) == SESSION_B
        assert kg_sync.current_session(None, {**bridge, "KB_SESSION": session_url(SESSION_B)}) == SESSION_B
        assert kg_sync.current_session(None, {**bridge, "KB_SESSION": ""}) == ""  # set empty: unknown
        assert kg_sync.current_session(session_url(SESSION_B), bridge) == SESSION_B
        assert kg_sync.current_session("", bridge) == ""


@requires_git
@pytest.mark.git
class TestSyncForeignSessionInGit:
    """`sync --push` refuses (exit 1, naming them) local commits whose Claude-Session trailer names another session:
    one session's sync must not push another's commits from a shared checkout. A commit already on the remote, a commit
    of the same session and an unknown current session refuse nothing (`tests.py -k sync_foreign_session`)."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        tmp = str(tmp_path_factory.mktemp("kb-sync-session"))
        env = git_env(KB_SYNC_NO_TESTS="1")
        for k in ("KB_SESSION", *kg_sync.SESSION_ENV):  # this run's own session must not reach the scenario
            env.pop(k, None)
        remote, (c,), cls.base = clones(kb_seed, tmp, env, ("c",))
        cls.remote, cls.c = Repo(remote, env), c

        def commit(subject, session):
            c.git("commit", "-q", "--allow-empty", "-m", subject, "-m", f"{kg_sync.SESSION_TRAILER}: {session_url(session)}")
            return c.rev("HEAD")

        def sync(*args, **extra):
            return c.tool("kbgit.py", "sync", *args, env=extra)

        # a commit of session B already on the remote is not a local commit: it never counts
        commit("chore: pushed earlier by session b", SESSION_B)
        c.git("push", "-q", "origin", "HEAD:main", env={"KB_GATE_DONE": "1"})
        cls.pushed_before = cls.remote.rev("main")
        cls.own = commit("chore: session a's own commit", SESSION_A)
        cls.same = sync("--push", "--dry-run", KB_SESSION=session_url(SESSION_A))
        cls.foreign = commit("chore: session b's local commit", SESSION_B)
        cls.refused = sync("--push", KB_SESSION=session_url(SESSION_A))
        cls.refused_dry = sync("--push", "--dry-run", CLAUDE_CODE_BRIDGE_SESSION_ID=SESSION_A)
        cls.refused_arg = sync("--push", "--dry-run", "--session", SESSION_A, KB_SESSION=SESSION_B)
        cls.unknown = sync("--push", "--dry-run")
        cls.unknown_empty = sync("--push", "--dry-run", KB_SESSION="", CLAUDE_CODE_BRIDGE_SESSION_ID=SESSION_A)
        cls.no_push = sync("--dry-run", KB_SESSION=SESSION_A)
        cls.after = (cls.remote.rev("main"), c.rev("HEAD"))
        yield
        shutil.rmtree(tmp, ignore_errors=True)

    def test_sync_foreign_session_commit_is_refused(self):
        r = self.refused
        assert r.returncode == 1, r.stdout + r.stderr
        assert "refused: 1 local commit(s) were made by another Claude session" in r.stdout
        assert f"  {self.foreign[:7]}" in r.stdout and "session b's local commit" in r.stdout
        assert SESSION_B in r.stdout
        assert "session a's own commit" not in r.stdout and "pushed earlier" not in r.stdout
        assert "pushed: no (another session's commits)" in r.stdout
        assert self.after == (self.pushed_before, self.foreign)  # nothing pushed, nothing rebased

    def test_sync_foreign_session_refusal_names_the_override(self):
        """a refusal is never a dead end: it says how to push them when the session that made them is gone"""
        for r in (self.refused, self.refused_dry, self.refused_arg):
            assert "--session" in r.stdout and "KB_SESSION" in r.stdout and "no longer exists" in r.stdout, r.stdout
        # the override works: naming the commit's own session pushes (dry-run) instead of refusing
        assert self.same.returncode == 0, self.same.stdout + self.same.stderr

    def test_sync_foreign_session_found_from_env_and_argument(self):
        for r in (self.refused_dry, self.refused_arg):
            assert r.returncode == 1, r.stdout + r.stderr
            assert "session b's local commit" in r.stdout

    def test_sync_foreign_session_same_session_passes(self):
        r = self.same
        assert r.returncode == 0, r.stdout + r.stderr
        assert "refused" not in r.stdout
        assert "would push 1 commit(s)" in r.stdout

    def test_sync_foreign_session_unknown_session_passes(self):
        for r in (self.unknown, self.unknown_empty, self.no_push):
            assert r.returncode == 0, r.stdout + r.stderr
            assert "refused" not in r.stdout


@requires_git
@pytest.mark.git
class TestPrePushInGit:
    """The pre-push hook (.githooks/pre-push -> `kbgit.py hook pre-push`): a plain `git push` of the checked-out branch
    runs the gate and is refused when a check fails; a tag push and sync's own push (KB_GATE_DONE=1) are not gated."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        tmp = str(tmp_path_factory.mktemp("kb-prepush"))
        env = git_env(KB_SYNC_NO_TESTS="1")
        remote, (c,), cls.base = clones(kb_seed, tmp, env, ("c",))
        cls.remote, cls.c = Repo(remote, env), c
        # a hand edit of the generated _coverage.csv: build_index.py --check fails
        c.write(P("_coverage.csv"), c.read(P("_coverage.csv")).replace(",P1,", ",P9,", 1))
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


@requires_git
@pytest.mark.git
class TestSprintWorktreeHooks(SyncScenario):
    """A sprint worker's `git worktree` of a clone with the hooks installed runs them (`tests.py -k
    sprint_worktree_has_commit_hooks`): core.hooksPath lives in the config the worktrees share, and git runs a commit
    hook in the worktree's top level. With install-hooks' relative `.githooks` and with an absolute path to the main
    clone's .githooks (a clone set up by hand), a commit in the worktree gets its KB-* trailers and install-hooks there
    says `already installed`, the check sync's note uses. Planted: with core.hooksPath unset the worktree's commit
    lacks them and check-trailers refuses it; an absolute path to a .githooks of no worktree of the clone, or to the
    main clone's .githooks without the scripts, is not counted as installed."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        tmp = str(tmp_path_factory.mktemp("kb-wthooks"))
        env = git_env(KB_SYNC_NO_TESTS="1")
        _, (c,), _ = clones(kb_seed, tmp, env, ("c",))
        wt = Repo(os.path.join(c.path, ".claude", "worktrees", "w1"), env)
        c.git("worktree", "add", "-q", wt.path, "-b", "work/w1")
        cls.c, cls.wt, cls.got = c, wt, {}
        absolute = os.path.join(c.path, kg_hooks.HOOKS_DIR)
        stray = os.path.join(tmp, "stray")
        shutil.copytree(absolute, os.path.join(stray, kg_hooks.HOOKS_DIR))
        for case, value in (("relative", None), ("absolute", absolute), ("unset", ""),
                            ("stray", os.path.join(stray, kg_hooks.HOOKS_DIR))):
            if value == "":
                c.git("config", "--unset", "core.hooksPath")
            elif value:
                c.git("config", "core.hooksPath", value)
            committed = cls.commit_article(wt, case)  # before install-hooks, which installs them when unset
            cls.got[case] = (wt.kbgit("install-hooks"), committed)
        c.git("config", "core.hooksPath", absolute)
        os.rename(absolute, absolute + "-gone")
        cls.got["absolute-empty"] = (wt.kbgit("install-hooks"), None)
        os.rename(absolute + "-gone", absolute)

    @classmethod
    def commit_article(cls, d, name):
        """Commit a new article in D (no index rebuild: an article outside _coverage.csv counts under its own path):
        (its KB-Topics trailer, check-trailers on it)."""
        cls.article(d, f"wt-{name}", ["S0001"], [f"Worktree hook test {name}."])
        d.git("add", "-A")
        d.git("commit", "-q", "-m", f"docs(kb): worktree hook test {name}")
        return (d.git("log", "-1", "--format=%(trailers:key=KB-Topics,valueonly)").strip(),
                d.kbgit("check-trailers", "HEAD"))

    def test_sprint_worktree_has_commit_hooks(self):
        for case in ("relative", "absolute"):
            install, (topics, check) = self.got[case]
            assert install.returncode == 0 and "already installed" in install.stdout, (case, install.stdout)
            assert topics.endswith(f"windows/sync-test-wt-{case}"), (case, topics)
            assert check.returncode == 0, (case, check.stdout + check.stderr)

    def test_sprint_worktree_has_commit_hooks_planted_unset(self):
        install, (topics, check) = self.got["unset"]
        assert topics == ""
        assert check.returncode == 1, check.stdout + check.stderr
        assert install.returncode == 0 and "installed: core.hooksPath=.githooks" in install.stdout, install.stdout

    def test_sprint_worktree_has_commit_hooks_planted_not_ours(self):
        for case in ("stray", "absolute-empty"):
            install = self.got[case][0]
            assert install.returncode == 2 and "not changed" in install.stdout, (case, install.stdout)


# ---------------------------------------------------------------- autonomous writers

def git_verb(argv):
    """The git subcommand of an argument list (`git -C DIR -c K=V push ...` -> 'push'), or None when it is no git."""
    argv = [str(a) for a in (argv if isinstance(argv, (list, tuple)) else [argv])]
    if not argv or Path(argv[0]).name.lower() not in ("git", "git.exe"):
        return None
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in ("-C", "-c") else 1
    return argv[i] if i < len(argv) else None


def push_targets(argv):
    """The destination refs of a `git push` argument list: the part after ':' of each refspec, the refspec itself
    without one; [] for a push that names no refspec (git's push.default decides)."""
    argv = [str(a) for a in argv]
    rest = argv[argv.index("push") + 1:]
    words, skip = [], False
    for a in rest:
        if skip:
            skip = False
        elif a in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
            skip = True
        elif not a.startswith("-"):
            words.append(a)
    return [w.rsplit(":", 1)[-1].lstrip("+") for w in words[1:]]


def main_target(ref):
    return ref in ("main", "refs/heads/main", "HEAD")


class WritePaths:
    """Watches one autonomous writer run against the bare fixture `origin`: every process it starts (subprocess.Popen,
    which subprocess.run and ql_base.run_cmd use) and origin's main before and after each command of the writer's
    `run`. A violation is a `git push` to main (or naming no refspec) started outside `kbgit.py sync --push`, or
    origin's main moving during a command that is not sync, or between commands (a push around `run`)."""

    def __init__(self, origin, env):
        self.origin, self.env = str(origin), env
        self.in_sync = False
        self.started, self.syncs, self.violations = [], [], []
        self.main = self.origin_main()

    def origin_main(self):
        with self.quiet():
            p = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/main"], cwd=self.origin,
                               env=self.env, capture_output=True, text=True, encoding="utf-8")
        return p.stdout.strip() or None

    @contextlib.contextmanager
    def quiet(self):
        """The watcher's own commands are not the writer's."""
        was, self.in_sync = self.in_sync, None
        try:
            yield
        finally:
            self.in_sync = was

    def seen(self, argv):
        if self.in_sync is None:
            return
        argv = [str(a) for a in (argv if isinstance(argv, (list, tuple)) else [argv])]
        self.started.append(argv)
        if git_verb(argv) == "push" and not self.in_sync:
            dst = push_targets(argv)
            if not dst or any(main_target(d) for d in dst):
                self.violations.append(f"git push outside kbgit.py sync --push: {' '.join(argv[1:])}")

    @contextlib.contextmanager
    def spying(self):
        """subprocess.Popen replaced by a subclass that reports each argument list before it starts."""
        orig, watch = subprocess.Popen, self

        class Spy(orig):
            def __init__(self, args, *a, **k):
                watch.seen(args)
                super().__init__(args, *a, **k)

        subprocess.Popen = Spy
        try:
            yield self
        finally:
            subprocess.Popen = orig

    def moved(self, during):
        now = self.origin_main()
        if now != self.main:
            if during is None:
                self.violations.append(f"origin's main moved outside any command: {self.main} -> {now}")
            elif not during:
                self.violations.append(f"origin's main moved during a command that is not sync: {self.main} -> {now}")
            self.main = now

    def wrap(self, run):
        """The writer's `run`, watched: origin's main before and after each command."""
        def watched(argv, cwd=None):
            self.moved(None)
            is_sync = len(argv) > 3 and Path(str(argv[1])).name == "kbgit.py" and list(argv[2:4]) == ["sync", "--push"]
            code, o, e = run(argv, cwd=cwd)
            self.moved(is_sync)
            return code, o, e
        return watched


class FixtureOrigin:
    """A small repository shaped like a kb for ql_deliver.Pusher (the query log's store with one run file, a public
    `_gaps.md`, an empty doc map and backlog), its bare origin and a clone; `apply --push` runs in that clone's
    worktree with sync, the trailers and the store check as stubs, `glab` answering `ci` (default: signed out)."""

    def __init__(self, tmp, env):
        from ql_testkit import golden_store
        self.tmp, self.env = Path(tmp), env
        seed = Repo(self.tmp / "seed", env)
        os.makedirs(seed.path)
        seed.git("init", "-q", "-b", "main")
        seed.write("kb/_self/map.csv", "doc,pattern\n")
        seed.write("kb/_self/backlog/.keep", "")
        seed.write(P("_gaps.md"), "# Gaps\n")
        golden_store(Path(seed.path) / "kb" / "_querylog")
        seed.git("add", "-A")
        seed.git("commit", "-qm", "seed")
        self.origin = self.tmp / "origin.git"
        seed.git("clone", "-q", "--bare", seed.path, str(self.origin))
        self.home = Repo(self.tmp / "home", env)
        seed.git("clone", "-q", str(self.origin), self.home.path)
        self.remote = Repo(self.origin, env)
        self.base = self.remote.rev("main")
        self.qdir = self.tmp / "q"
        self.qdir.mkdir()
        self.ci = None
        self.n = 0
        self.watch = None

    def run(self, argv, cwd=None):
        """git for real; the worktree's kbgit.py sync --push a stub that pushes HEAD to origin's branch, its
        `trailers --amend` and `querylog.py check` passing stubs; glab and gh as `ci` answers."""
        import ql_base
        argv = [str(a) for a in argv]
        if argv[0] in ("glab", "gh"):
            return self.ci(argv) if self.ci else (1, "", "not logged in")
        tool = Path(argv[1]).name if len(argv) > 1 else ""
        if tool == "kbgit.py" and argv[2:4] == ["sync", "--push"]:
            branch = argv[argv.index("--branch") + 1] if "--branch" in argv else "main"
            self.watch.in_sync = True
            try:
                code, o, e = ql_base.run_cmd(["git", "push", "--quiet", "origin", f"HEAD:refs/heads/{branch}"],
                                             cwd=cwd, env=self.env)
            finally:
                self.watch.in_sync = False
            self.watch.syncs.append(argv[2:])
            return code, ("pushed: yes\n" if code == 0 else ""), e
        if tool in ("kbgit.py", "querylog.py"):
            return 0, "", ""
        return ql_base.run_cmd(argv, cwd=cwd, env=self.env)

    def gap_step(self, wt, store, hold, out):
        """What apply writes on its own: a `_gaps.md` entry and a findings file recording its finding applied."""
        self.n += 1
        run_id = f"20260928T1300{self.n:02d}Z-0000fe{self.n:02d}"
        fid = f"F-00000000fe{self.n:02d}"
        with open(Path(wt) / P("_gaps.md"), "a", encoding="utf-8", newline="\n") as f:
            f.write(f"\n- **Autonomous write test question {self.n}?** ({fid}) (topic: windows/test)\n")
        head = {"run": run_id, "pipeline": 5, "retrieval": 4, "kb_commit": "0" * 40,
                "counts": {"findings": 1, "applied": 1}}
        rec = {"id": fid, "kind": "gap", "state": "applied", "stage": "gap", "promotions": [],
               "entry": "22222222-0000-4000-8000-0000000000a1", "article": P("windows/test.md")}
        f = Path(store) / "findings" / "2026-09" / f"{run_id}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(json.dumps(o) + "\n" for o in (head, rec)), encoding="utf-8", newline="\n")
        return 0

    def apply_push(self, pusher_class=None, step=None):
        """One `apply --push` of the clone, watched: (exit code, output lines, WritePaths)."""
        import ql_deliver
        said = []
        self.watch = WritePaths(self.origin, self.env)
        cls = pusher_class or ql_deliver.Pusher
        p = cls(self.home.path, self.qdir, self.watch.wrap(self.run), step or (lambda *a: 0), said.append,
                cloud=False)
        with self.watch.spying():
            rc = p()
        self.watch.moved(None)
        return rc, said, self.watch

    def bugs(self, rev="main"):
        return [n for n in self.remote.git("ls-tree", "--name-only", rev, "kb/_self/backlog/").split()
                if n.endswith(".json")]


RECORD_OPTIONS = """#!/bin/sh
n=${GIT_PUSH_OPTION_COUNT:-0}
i=0
while [ "$i" -lt "$n" ]; do
  eval "echo \\"\\$GIT_PUSH_OPTION_$i\\""
  i=$((i + 1))
done >> "$(dirname "$0")/../pushed-options.txt"
echo "--" >> "$(dirname "$0")/../pushed-options.txt"
"""


@requires_git
@pytest.mark.git
class TestCodeLaneSync(SyncScenario):
    """sync --push by lane against local bare remotes: content to main, code as a code/<id> branch with the merge
    request push options (or without them when the remote does not advertise them)."""

    @pytest.fixture
    def world(self, tmp_path, kb_seed):
        env = git_env(KB_SYNC_NO_TESTS="1")
        remote, (a, b), base = clones(kb_seed, str(tmp_path), env, ("a", "b"))
        w = type("World", (), {})()
        w.env, w.remote, w.a, w.b, w.base, w.bare = env, remote, a, b, base, Repo(remote, env)
        return w

    @staticmethod
    def advertise(w, on=True):
        w.bare.git("config", "receive.advertisePushOptions", "true" if on else "false")
        hook = Path(w.remote) / "hooks" / "pre-receive"
        hook.write_text(RECORD_OPTIONS, encoding="utf-8", newline="\n")
        hook.chmod(0o755)

    @staticmethod
    def options(w):
        f = Path(w.remote) / "pushed-options.txt"
        return [] if not f.exists() else [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln != "--"]

    @classmethod
    def content(cls, d, n):
        url = f"https://learn.microsoft.com/en-us/sync-test/lane{n}"
        cls.add_source(d, "S-", url, f"lane{n}")
        cls.article(d, f"lane{n}", [kbid.source_id(url)], [f"Lane fact {n}."])
        cls.commit(d, f"docs(kb): lane test {n}")

    @staticmethod
    def code(d, n, work=None):
        d.write(f"_tools/lane_test_{n}.txt", f"code {n}\n")
        d.git("add", "-A")
        d.git("commit", "-q", "-m", f"chore(tools): lane test {n}" + (f"\n\nKB-Work: {work}" if work else ""))

    @staticmethod
    def item(d, i):
        """Task `i`, claimed, under a story of an active sprint with its review story, so a commit may name it in
        KB-Work and the items pass the gate's backlog.py check (a backlog-planning commit)."""
        check = [{"run": ["python3", "-c", "pass"], "exit": 0}]
        sp, rv, st = "SP-aaaaaaaa", "ST-bbbbbbbb", "ST-aaaaaaaa"
        items = [{"id": sp, "kind": "sprint", "title": "Lane test", "status": "active", "goal": "Lane test",
                  "gates": [{"id": "start", "kind": "blocking", "question": "Approve this sprint's goal and committed items?",
                             "options": ["approve", "change", "cancel"], "recommendation": "approve", "answer": "approve", "by": "operator"}]},
                 {"id": rv, "kind": "story", "title": "Review sprint: Lane test", "status": "todo", "sprint": sp, "review": True,
                  "priority": "P3", "rank": 0, "goal": "Lane test reviewed", "checks": check},
                 {"id": st, "kind": "story", "title": "Lane test story", "status": "doing", "sprint": sp, "priority": "P3", "rank": 0,
                  "goal": "Lane test", "checks": check, "claimed_by": "lane-test"},
                 {"id": i, "kind": "task", "title": "Lane test", "status": "doing", "parent": st, "priority": "P3", "rank": 0,
                  "goal": "Lane test", "checks": check, "touches": ["_tools/**"], "claimed_by": "lane-test"}]
        for it in items:
            d.write(f"kb/_self/backlog/{it['id']}.json", json.dumps(it, indent=2) + "\n")
        fmt = d.tool("backlog.py", "fmt")
        assert fmt.returncode == 0, fmt.stdout + fmt.stderr
        d.git("add", "-A")
        d.git("commit", "-q", "-m", f"chore(backlog): plan {i}")

    def branches(self, w):
        return sorted(x.strip().replace("refs/heads/", "") for x in w.bare.git("for-each-ref", "--format=%(refname)", "refs/heads/").split())

    def test_content_only_goes_to_main(self, world):
        w = world
        self.advertise(w)
        self.content(w.a, 1)
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert self.branches(w) == ["main"]
        assert w.bare.rev("main") == w.a.rev("HEAD")
        assert self.options(w) == []
        assert "lane: code" not in r.stdout

    def test_code_goes_to_a_branch_with_options(self, world):
        w = world
        self.advertise(w)
        self.code(w.a, 1)
        head = w.a.rev("HEAD")
        d = w.a.kbgit("sync", "--dry-run", "--push")
        assert "lane: code" in d.stdout and f"code/{head[:9]}" in d.stdout and self.branches(w) == ["main"], d.stdout
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        branch = f"code/{head[:9]}"
        assert self.branches(w) == [branch, "main"]
        assert w.bare.rev("main") == w.base and w.bare.rev(branch) == head
        assert w.a.rev("main") == head
        assert self.options(w) == ["merge_request.create", "merge_request.target=main", "merge_request.auto_merge",
                                   "merge_request.remove_source_branch"]
        assert "main did not move" in r.stdout

    def test_a_push_to_another_branch_is_not_routed(self, world):
        """A cloud session pushes its working branch (the only one its git proxy allows) whatever the lane: lanes
        route pushes to main only. Planted failure: routing every target would push code/<id> here."""
        w = world
        self.advertise(w)
        self.code(w.a, 5)
        head = w.a.rev("HEAD")
        d = w.a.kbgit("sync", "--dry-run", "--push", "--branch", "work")
        assert "lane: not routed (a push to work)" in d.stdout, d.stdout
        r = w.a.kbgit("sync", "--push", "--branch", "work")
        assert r.returncode == 0, r.stdout + r.stderr
        assert self.branches(w) == ["main", "work"]
        assert w.bare.rev("work") == head and w.bare.rev("main") == w.base
        assert self.options(w) == []

    def test_mixed_range_rides_content_along(self, world):
        w = world
        self.advertise(w)
        self.content(w.a, 2)
        self.code(w.a, 2)
        self.content(w.a, 3)
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert w.bare.rev("main") == w.base
        (branch,) = [x for x in self.branches(w) if x.startswith("code/")]
        assert w.bare.rev(branch) == w.a.rev("HEAD")
        assert w.bare.git("rev-list", "--count", f"{w.base}..{branch}").strip() >= "3"

    def test_no_push_options_falls_back_and_says_so(self, world):
        w = world
        self.advertise(w, on=False)
        self.code(w.a, 4)
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert any(x.startswith("code/") for x in self.branches(w))
        assert self.options(w) == []
        assert "does not support push options: open a merge or pull request from code/" in r.stdout, r.stdout

    def test_repush_after_main_moved_uses_a_lease(self, world):
        w = world
        self.advertise(w)
        self.item(w.a, "TK-aaaaaaaa")
        self.code(w.a, 5, work="TK-aaaaaaaa")
        first_run = w.a.kbgit("sync", "--push")
        assert first_run.returncode == 0, first_run.stdout + first_run.stderr
        (branch,) = [x for x in self.branches(w) if x.startswith("code/")]
        first = w.bare.rev(branch)
        self.content(w.b, 5)
        assert w.b.kbgit("sync", "--push").returncode == 0  # main moves
        self.advertise(w)
        Path(w.remote, "pushed-options.txt").unlink()
        r = w.a.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "lease" in r.stdout
        assert w.bare.rev(branch) != first and w.bare.rev(branch) == w.a.rev("HEAD")
        assert w.bare.rev("main") == w.b.rev("HEAD")
        assert "merge_request.auto_merge" in self.options(w)

    def test_lease_refuses_a_branch_someone_else_moved(self, world, monkeypatch, capsys):
        w = world
        self.advertise(w)
        self.item(w.a, "TK-aaaaaaaa")
        self.code(w.a, 6, work="TK-aaaaaaaa")
        first_run = w.a.kbgit("sync", "--push")
        assert first_run.returncode == 0, first_run.stdout + first_run.stderr
        (branch,) = [x for x in self.branches(w) if x.startswith("code/")]
        self.content(w.b, 6)
        assert w.b.kbgit("sync", "--push").returncode == 0
        w.a.git("fetch", "-q", "origin")
        w.a.git("rebase", "-q", "origin/main")  # not an ancestor of the remote branch any more
        theirs = w.b.rev("HEAD")
        w.b.git("checkout", "-q", "-b", "other")
        real, moved = kg_sync.gitx, []

        def racing(*args, **kw):
            if args and args[0] == "push" and not moved:
                moved.append(1)
                w.b.git("push", "-q", "origin", f"{theirs}:refs/heads/{branch}", "--force", "--no-verify")
            return real(*args, **kw)

        monkeypatch.setattr(kg_sync, "KB", w.a.path)
        monkeypatch.setattr(kg_sync, "gitx", racing)
        ns = type("A", (), dict(remote="origin", branch="main"))()
        r = {"notes": []}
        assert kg_sync.push_branch(ns, r, branch, "origin/main") == 1
        out = capsys.readouterr().out
        assert "nothing was overwritten" in out and branch in out
        assert w.bare.rev(branch) == theirs

    def test_branch_id_is_the_first_work_id(self, world, monkeypatch):
        w = world
        self.code(w.a, 7, work="TK-aaaaaaaa")
        self.code(w.a, 8, work="TK-bbbbbbbb")
        assert kg_lane.lane_plan(w.a.path, w.base, "HEAD") == ("code", "code/TK-aaaaaaaa")
        assert kg_lane.lane_plan(w.a.path, w.a.rev("HEAD"), "HEAD") == ("content", None)

    def test_kg_lane_takes_root(self, world, tmp_path):
        """The branch is named for the root it is given, not a module global: a worktree root and the clone root of
        one repository (kbgit.KB pointing elsewhere) each get the name of the range their checkout holds. Planted
        failure: the clone's name asked of the worktree root is not the worktree's."""
        w = world
        self.code(w.a, 20, work="TK-aaaaaaaa")
        wt = str(tmp_path / "wt")
        w.a.git("worktree", "add", "-q", "--detach", wt, w.base)
        sh = lambda *a: subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)  # noqa: E731
        sh("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "x")
        (Path(wt) / "_tools").mkdir(exist_ok=True)
        (Path(wt) / "_tools" / "wt_code.txt").write_text("c\n", encoding="utf-8")
        sh("add", "-A")
        sh("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m",
           "chore(tools): wt code\n\nKB-Work: TK-bbbbbbbb")
        assert kbgit.KB not in (wt, w.a.path)
        assert kg_lane.lane_plan(wt, w.base, "HEAD") == ("code", "code/TK-bbbbbbbb")
        assert kg_lane.lane_plan(w.a.path, w.base, "HEAD") == ("code", "code/TK-aaaaaaaa")
        assert kg_lane.lane_plan(wt, w.base, "HEAD", "other") == (None, None)
        with pytest.raises(AssertionError):
            assert kg_lane.code_branch(w.a.path, w.base, "HEAD") == kg_lane.code_branch(wt, w.base, "HEAD")

    @staticmethod
    def claim(d, i):
        """A content-lane claim of item `i`: its item file alone, KB-Work naming it."""
        d.write(f"kb/_self/backlog/{i}.json", json.dumps({"id": i, "status": "doing"}) + "\n")
        d.git("add", "-A")
        d.git("commit", "-q", "-m", f"chore(backlog): claim {i}\n\nKB-Work: {i}")

    def test_code_branch_named_after_code_commit(self, world, monkeypatch):
        """Item A's content-lane claim, then item B's code commit: the branch is code/B, named after the item whose
        code it carries (SP-v5xagbyv's code/TK-5mrfocpz carried TK-opkxumeu's code). Planted failures: the old rule
        (the range's first KB-Work id) and a code_branch that reads every commit as code-lane name code/A."""
        w = world
        self.claim(w.a, "TK-aaaaaaaa")
        self.code(w.a, 9, work="TK-bbbbbbbb")
        monkeypatch.setattr(kbgit, "KB", w.a.path)
        rng = [f"{w.base}..HEAD"]
        assert [lane for _, lane, _ in kblane.commit_lanes(w.a.path, rng)] == ["content", "code"]

        def names_code_item(branch):
            assert branch == "code/TK-bbbbbbbb", branch

        names_code_item(kg_lane.code_branch(w.a.path, w.base, "HEAD"))
        assert kg_lane.lane_plan(w.a.path, w.base, "HEAD") == ("code", "code/TK-bbbbbbbb")
        out = kg_merge.git("log", "--reverse", "--format=%(trailers:key=KB-Work,valueonly,unfold)", *rng, kb=w.a.path)
        old_rule = kg_lane.CODE_BRANCH_PREFIX + re.split(r"[,\s]+", out.strip())[0]
        with pytest.raises(AssertionError):
            names_code_item(old_rule)
        real = kblane.commit_lanes
        with monkeypatch.context() as m:
            m.setattr(kblane, "commit_lanes", lambda repo, spec: [(h, "code", c) for h, _, c in real(repo, spec)])
            with pytest.raises(AssertionError):
                names_code_item(kg_lane.code_branch(w.a.path, w.base, "HEAD"))

    def test_code_branch_falls_back_to_the_range(self, world, monkeypatch):
        """A code commit without KB-Work: the range's first KB-Work id (the claim's), and with none, HEAD's short hash."""
        w = world
        self.code(w.a, 10)
        assert kg_lane.code_branch(w.a.path, w.base, "HEAD") == f"code/{w.a.rev('HEAD')[:9]}"
        self.claim(w.a, "TK-aaaaaaaa")
        self.code(w.a, 11)
        assert kg_lane.code_branch(w.a.path, w.base, "HEAD") == "code/TK-aaaaaaaa"
        assert kg_lane.code_branch(w.a.path, w.a.rev("HEAD~1"), "HEAD~1") is None  # an empty range has no code-lane commit

    def test_only_code_branches_are_pushed_this_way(self, world, monkeypatch, capsys):
        w = world
        monkeypatch.setattr(kg_sync, "KB", w.a.path)
        ns = type("A", (), dict(remote="origin", branch="main"))()
        assert kg_sync.push_branch(ns, {"notes": []}, "main", "origin/main") == 2
        assert "not a code/*" in capsys.readouterr().out


PLANTED_LANE = "code/planted-by-rebase"
CONTENT_RETURN = "        return kblane.CONTENT, None\n"


@requires_git
@pytest.mark.git
class TestSyncReexec(SyncScenario):
    """A rebase inside sync that changes the push decision (kg_lane.py here) (`tests.py -k sync_reexec_after_kbgit_rebase`): B
    pushes a kg_lane.py whose lane_plan routes every push to PLANTED_LANE, A (behind, one content commit) runs
    `sync --push`. The re-run with the rebased code decides: A's commit goes to PLANTED_LANE, main stays B's. The planted
    failure: the same run with the re-run disabled (KB_SYNC_REEXEC=1, as inside a re-run) does not route it there."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        tmp = str(tmp_path_factory.mktemp("kb-sync-reexec"))
        env = git_env(KB_SYNC_NO_TESTS="1")
        env.pop(kg_sync.REEXEC_ENV, None)  # a gate run inside a re-run must not disable this one
        cls.runs = {}
        for name, extra in (("reexec", {}), ("disabled", {kg_sync.REEXEC_ENV: "1"})):
            os.makedirs(os.path.join(tmp, name))
            remote, (a, b), _ = clones(kb_seed, os.path.join(tmp, name), env, ("a", "b"))
            src = b.read("_tools/kg_lane.py")
            assert src.count(CONTENT_RETURN) == 1
            b.write("_tools/kg_lane.py", src.replace(CONTENT_RETURN, f"        return kblane.CODE, {PLANTED_LANE!r}\n"))
            b.git("commit", "-q", "-am", "chore(tools): planted lane rule")
            b.git("push", "-q", "--no-verify", "origin", "HEAD:main", env={"KB_GATE_DONE": "1"})
            url = "https://learn.microsoft.com/en-us/sync-test/reexec"
            cls.add_source(a, "S-", url, "reexec")
            cls.article(a, "reexec", [kbid.source_id(url)], ["Reexec fact."])
            cls.commit(a, "docs(kb): reexec test")
            r = a.tool("kbgit.py", "sync", "--push", "--session", "session_reexec", env=extra)
            bare = Repo(remote, env)
            heads = {x.split()[1].replace("refs/heads/", ""): x.split()[0]
                     for x in bare.git("for-each-ref", "--format=%(objectname) %(refname)", "refs/heads/").splitlines()}
            cls.runs[name] = (r, heads, b.rev("HEAD"), a.rev("HEAD"))
        yield
        shutil.rmtree(tmp, ignore_errors=True)

    @staticmethod
    def assert_new_code_decided(run):
        r, heads, theirs, head = run
        assert r.returncode == 0, r.stdout + r.stderr
        assert "the rebase changed the code sync runs: _tools/kg_lane.py" in r.stdout, r.stdout
        assert "re-running sync once with the rebased code" in r.stdout, r.stdout
        assert heads.get(PLANTED_LANE) == head, (heads, r.stdout)
        assert heads["main"] == theirs  # the old code would have pushed A's commit to main
        assert "local 1 ahead, 0 behind" in r.stdout  # the re-run did not rebase again

    def test_sync_reexec_after_kbgit_rebase_new_code_decides_the_push(self):
        self.assert_new_code_decided(self.runs["reexec"])

    def test_sync_reexec_after_kbgit_rebase_disabled_fails(self):
        run = self.runs["disabled"]
        with pytest.raises(AssertionError):
            self.assert_new_code_decided(run)
        r, heads, theirs, _ = run
        assert r.returncode == 3, r.stdout + r.stderr
        assert "Run the same kbgit.py sync command again" in r.stdout
        assert PLANTED_LANE not in heads and heads["main"] == theirs  # stopped: nothing pushed with the old code

    def test_sync_reexec_after_kbgit_rebase_watches_imported_modules(self):
        loaded = kg_sync.loaded_tools()
        for rel in ("_tools/kbgit.py", "_tools/kblane.py", "_tools/kbpublic.py", "_tools/kg_merge.py", "_tools/kg_lane.py", "_tools/kg_sync.py", "_tools/kg_base.py",
                    "_tools/kbcommon.py"):
            assert rel in loaded
        assert all(p.startswith("_tools/") and p.endswith(".py") for p in loaded)


def red(pid):
    def ci(argv):
        if argv[1:3] == ["auth", "status"]:
            return 0, "", "Logged in"
        return 0, json.dumps([{"id": pid, "status": "failed",
                               "web_url": f"https://gitlab.corp.example.com/grp/proj/-/pipelines/{pid}"}]), ""
    return ci


def writer_push_calls(source):
    """Lines of a writer's source that pass the git verb 'push' or 'commit' to a call or put it in an argument list."""
    out = []
    for node in ast.walk(ast.parse(source)):
        items = list(node.args) if isinstance(node, ast.Call) else list(node.elts) if isinstance(
            node, (ast.List, ast.Tuple)) else []
        for a in items:
            if isinstance(a, ast.Constant) and a.value in ("push", "commit"):
                out.append(a.lineno)
    return sorted(set(out))


@requires_git
@pytest.mark.git
class TestAutonomousWrite:
    PID = 4242

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        import ql_deliver
        cls.tmp = tmp_path_factory.mktemp("kb-autonomous")
        cls.env = git_env()
        cls.fx = fx = FixtureOrigin(cls.tmp / "one", cls.env)
        cls.first = fx.apply_push(step=fx.gap_step)
        cls.main1 = fx.remote.rev("main")
        fx.ci = red(cls.PID)
        cls.second = fx.apply_push(step=fx.gap_step)
        cls.main2 = fx.remote.rev("main")
        cls.log2 = fx.remote.git("log", "--format=%H%x1f%s%x1f%(trailers:key=KB-Auto,valueonly)%x1e",
                                 f"{cls.main1}..main")
        cls.third = fx.apply_push()
        cls.main3 = fx.remote.rev("main")

        class DirectPusher(ql_deliver.Pusher):
            """A planted writer: its commits go to main by a plain `git push` through `run`."""
            def deliver(self, run_id):
                code, o, e = self.git("push", "--quiet", ql_deliver.REMOTE, f"HEAD:refs/heads/{ql_deliver.BRANCH}")
                self.landed = code == 0
                return code

        class AroundPusher(ql_deliver.Pusher):
            """A planted writer: its push goes around `run`, straight to subprocess."""
            def deliver(self, run_id):
                p = subprocess.run(["git", "push", "--quiet", ql_deliver.REMOTE, "HEAD:main"], cwd=str(self.wt),
                                   env=cls.env, capture_output=True)
                self.landed = p.returncode == 0
                return p.returncode

        cls.planted = {}
        for name, klass in (("direct", DirectPusher), ("around", AroundPusher)):
            f = FixtureOrigin(cls.tmp / name, cls.env)
            cls.planted[name] = (f, f.apply_push(klass, f.gap_step))
        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_autonomous_write_apply_push_goes_through_sync(self):
        rc, said, w = self.first
        assert rc == 0, said
        assert w.violations == [], w.violations
        assert w.syncs == [["sync", "--push", "--remote", "origin", "--branch", "main"]], said
        assert self.main1 != self.fx.base
        assert "Autonomous write test question 1?" in self.fx.remote.git("show", f"{self.main1}:{P('_gaps.md')}")
        assert [git_verb(a) for a in w.started].count("push") == 1  # the one push is sync's

    def test_autonomous_write_red_push_is_reverted_through_sync_with_one_bug(self):
        rc, said, w = self.second
        assert rc == 0, said
        assert w.violations == [], w.violations
        assert w.syncs == [["sync", "--push", "--remote", "origin", "--branch", "main"]], said
        commits = [c.strip("\n").split("\x1f") for c in self.log2.split("\x1e") if "\x1f" in c]
        assert len(commits) == 1, commits  # the revert only: nothing new is applied in the run that reverts
        assert commits[0][1] == f"revert: query log commit {self.main1[:9]}"
        assert commits[0][2].strip() == "revert"
        assert "Autonomous write test question 1?" not in self.fx.remote.git("show", f"main:{P('_gaps.md')}")
        bugs = self.fx.bugs()
        assert len(bugs) == 1, bugs
        item = json.loads(self.fx.remote.git("show", f"main:{bugs[0]}"))
        assert item["kind"] == "bug" and item["severity"] == "S2" and f"pipeline {self.PID}" in item["title"]
        failed = self.fx.remote.git("diff", "--name-only", "--diff-filter=A", self.main1, "main", "--",
                                    "kb/_querylog/findings").split()
        assert len(failed) == 1
        assert '"apply-failed"' in self.fx.remote.git("show", f"main:{failed[0]}")

    def test_autonomous_write_next_run_files_no_second_bug(self):
        rc, said, w = self.third
        assert rc == 0, said
        assert w.violations == [] and w.syncs == [], (w.violations, said)
        assert self.main3 == self.main2
        assert len(self.fx.bugs()) == 1

    @pytest.mark.parametrize("name", ["direct", "around"])
    def test_autonomous_write_planted_direct_push_fails(self, name):
        f, (rc, said, w) = self.planted[name]
        assert f.remote.rev("main") != f.base, said  # the planted push did land ...
        assert w.syncs == []
        assert w.violations, "a direct git push to main must be a violation"  # ... and the watcher names it
        assert any("git push outside kbgit.py sync --push" in v for v in w.violations), w.violations
        assert any("origin's main moved" in v for v in w.violations), w.violations

    def test_autonomous_write_research_and_ingest_do_not_push(self, tmp_path, capsys):
        """ql_research's queue and close and kbingest.py's survey and url, run against a fixture clone of a fixture
        origin: nothing pushed, no `git push` or `git commit` started; research's model run has no shell tool."""
        import kbingest, ql_research
        fx = FixtureOrigin(tmp_path / "rw", self.env)
        store = Path(fx.home.path) / "kb" / "_querylog"
        # a forge url for ingest's pinned urls; a push would still go to the fixture origin
        fx.home.git("remote", "set-url", "origin", "https://gitlab.corp.example.com/grp/proj.git")
        fx.home.git("remote", "set-url", "--push", "origin", str(fx.origin))
        w = WritePaths(fx.origin, self.env)
        with w.spying():
            ql_research.queue(store=store, day="2026-09-29", kb_commit="0" * 40, out=lambda *a: None)
            ql_research.close("F-000000000000", claim=True, store=store, day="2026-09-29", out=lambda *a: None)
            assert kbingest.main(["survey", fx.home.path, "--files"]) == 0
            assert kbingest.main(["url", fx.home.path, P("_gaps.md")]) == 0
        w.moved(None)
        capsys.readouterr()
        assert w.violations == [] and fx.remote.rev("main") == fx.base, w.violations
        assert [a for a in w.started if git_verb(a) in ("push", "commit")] == []
        assert any(git_verb(a) for a in w.started)  # the spy saw ingest's git commands
        argv = ql_research.research_argv()
        tools = argv[argv.index("--tools") + 1].split(",")
        assert set(tools) == set(ql_research.RESEARCH_TOOLS) and "Bash" not in tools and "PowerShell" not in tools
        assert "--dangerously-skip-permissions" not in argv and not any("Bash" in a for a in argv)

    @pytest.mark.parametrize("module", ["ql_research.py", "kbingest.py", "ql_apply.py", "ql_learn.py"])
    def test_autonomous_write_writers_hold_no_push(self, module):
        """The writers that do not push hold no git `push` or `commit` in their source; a planted one is found."""
        source = Path(TOOLS, module).read_text(encoding="utf-8")
        assert writer_push_calls(source) == [], module
        planted = source + '\n\ndef sneak(repo):\n    return git(repo, "push", "origin", "HEAD:main")\n'
        assert writer_push_calls(planted) == [len(planted.splitlines())]


class TestSyncGateTests:
    """The gate's tests.py run (`tests.py -k sync_gate_`): a fast run keeps the git scenarios of the test files the
    changed code selects (TestCloudInGit for kbgit.py and querylog.py), and leaves out those only kb content selects."""

    PLANTED = {"_tools/widget.py": ["_tools/test_widget.py"], "kb/public/x.md": ["_tools/test_content.py"]}

    @staticmethod
    def plant(root, value):
        """A tree of its own: a tool, its test file with a git scenario that passes only when the tool's VALUE is 1
        (and leaves a mark), and a content test file whose git scenario always fails."""
        tools = Path(root, "_tools")
        tools.mkdir(parents=True, exist_ok=True)
        (tools / "conftest.py").write_text('def pytest_configure(config):\n    config.addinivalue_line("markers", "git: x")\n'
                                           '    config.addinivalue_line("markers", "stress: x")\n', encoding="utf-8", newline="\n")
        (tools / "widget.py").write_text(f"VALUE = {value}\n", encoding="utf-8", newline="\n")
        mark = "@pytest.mark.git"
        (tools / "test_widget.py").write_text("\n".join([
            "import os, pytest, widget", "", "", "def test_fast():", "    pass", "", "", mark, "def test_slow():",
            "    open(os.path.join(os.path.dirname(__file__), 'ran-slow'), 'w').close()", "    assert widget.VALUE == 1", ""]),
            encoding="utf-8", newline="\n")
        (tools / "test_content.py").write_text("\n".join([
            "import pytest", "", "", "def test_fast():", "    pass", "", "", mark, "def test_slow():", "    assert False", ""]),
            encoding="utf-8", newline="\n")
        return tools

    def gate(self, monkeypatch, root, paths):
        """kbgit's gate over PATHS, its tests.py run in this process over the planted tree (real pytest, no xdist):
        (passed, the tests.py line of the report)."""
        import sys, testmap
        import tests as tests_py

        def select(ps):
            nodes = sorted({n for p in ps for n in self.PLANTED.get(p, [])})
            return (nodes or testmap.NONE), []

        def tool(name, *args, env=None):
            if name != "tests.py":
                return 0, "ok"
            with monkeypatch.context() as m:
                for k, v in (env or {}).items():
                    m.setenv(k, v)
                return tests_py.main(list(args)), ""
        monkeypatch.delenv("KB_SYNC_NO_TESTS", raising=False)
        monkeypatch.setattr(tests_py, "KB", str(root))
        monkeypatch.setattr(tests_py, "TOOLS", str(Path(root, "_tools")))
        monkeypatch.setattr(tests_py, "pytest_cmd", lambda: [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"])  # -B: no stale .pyc
        monkeypatch.setattr(tests_py, "XDIST", ["-n", "0"])
        monkeypatch.setattr(testmap, "changed", lambda rev: sorted(paths))
        monkeypatch.setattr(testmap, "select", select)
        monkeypatch.setattr(kg_sync, "gate_paths", lambda up: set(paths))
        monkeypatch.setattr(kbgit, "trailer_audit", lambda rng, quiet=False, **k: (0, 0, []))
        monkeypatch.setattr(kg_sync, "tool", tool)
        r = {"target": "origin/main"}
        ok = kbgit.gate(r, "origin/main")
        return ok, {label: out for label, out, _ in r["gate"]}["tests.py (changed)"]

    def test_sync_gate_runs_changed_slow_tests(self, tmp_path, monkeypatch):
        """Planted: a tool change that breaks a git scenario of its test file fails the gate (with every git scenario
        left out, as KB_TESTS_FAST=1 did, it passed); the fixed tool passes, the scenario having run; a content-only
        change leaves its failing git scenario out."""
        tools = self.plant(tmp_path, 2)
        ok, out = self.gate(monkeypatch, tmp_path, ["_tools/widget.py"])
        assert not ok and out.startswith("FAILED"), out
        (tools / "ran-slow").unlink()
        self.plant(tmp_path, 1)
        ok, out = self.gate(monkeypatch, tmp_path, ["_tools/widget.py", "kb/public/x.md"])
        assert ok and out.startswith("ok"), out
        assert (tools / "ran-slow").exists()
        (tools / "ran-slow").unlink()
        ok, out = self.gate(monkeypatch, tmp_path, ["kb/public/x.md"])
        assert ok, out
        assert not (tools / "ran-slow").exists()

    def test_sync_gate_selects_cloud_scenarios(self):
        """A change to kbgit.py or querylog.py: the gate's fast run keeps the git scenarios of test_ql_deliver.py, and
        pytest collects TestCloudInGit with that run's -m (and not with the content run's); kb content alone keeps the
        fast run, and a run that is not fast is one run."""
        import sys
        import tests as tests_py
        node = "_tools/test_ql_deliver.py"
        for path in ("_tools/kbgit.py", "_tools/querylog.py"):
            runs = tests_py.plan([path], True)
            assert runs[0][1] == tests_py.FULL_M and node in runs[0][0], (path, runs)
            assert tests_py.plan([path], False) == [(runs[0][0], tests_py.FULL_M)]
        content = tests_py.plan(["kb/public/README.md"], True)
        assert [m for _, m in content] == [tests_py.FAST_M], content
        mixed = tests_py.plan(["_tools/kbgit.py", "kb/public/README.md"], True)
        assert mixed[0][1] == tests_py.FULL_M and all(m == tests_py.FAST_M for _, m in mixed[1:]), mixed
        for m, want in ((runs[0][1], True), (tests_py.FAST_M, False)):
            p = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-n", "0",
                                "-m", m, tests_py.target(node)], cwd=os.path.dirname(TOOLS), capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            assert ("TestCloudInGit" in p.stdout) == want, (m, p.stdout[-2000:] + p.stderr[-2000:])


MOVED_TO_SYNC = ("sync_once", "cmd_sync", "gate", "push_branch", "do_rebase", "gitx", "tool", "gate_paths", "MECHANICAL")


def defined_in(source, names):
    """The NAMES the module SOURCE defines at its top level (a def, a class or an assignment)."""
    out = set()
    for n in ast.parse(source).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    return {x for x in names if x in out}


def test_kg_split_sync_run_lives_in_kg_sync_and_kbgit_keeps_the_command():
    """kg_sync defines the sync run, its gate, its push and its rebase; kbgit.py defines none of the sync_once, push_branch,
    do_rebase, gitx, tool, gate_paths and MECHANICAL names (it imports what it needs) and keeps the command: a
    cmd_sync and a gate that give kg_sync the trailer code. Planted failure: a moved name put back into kbgit.py is
    reported."""
    kbgit_src = Path(TOOLS, "kbgit.py").read_text(encoding="utf-8")
    sync_src = Path(TOOLS, "kg_sync.py").read_text(encoding="utf-8")
    assert defined_in(sync_src, MOVED_TO_SYNC) == set(MOVED_TO_SYNC)
    keeps = {"cmd_sync", "gate"}
    assert defined_in(kbgit_src, MOVED_TO_SYNC) == keeps
    assert "kg_sync.cmd_sync(" in kbgit_src and "kg_sync.gate(" in kbgit_src
    planted = kbgit_src + "\n\ndef push_branch(a, r, branch, target):\n    return 0\n"
    assert defined_in(planted, MOVED_TO_SYNC) == keeps | {"push_branch"}


@requires_git
def test_kg_split_sync_imports_no_facade_and_runs_git_in_its_own_kb(tmp_path, monkeypatch):
    """kg_sync imports no kbgit and runs git in its own KB: a patch of kg_sync.KB moves its git calls to a directory
    that is no repository. Planted failure: the same patch on kbgit.KB leaves them in this repository."""
    imports = {a.name for n in ast.walk(ast.parse(Path(TOOLS, "kg_sync.py").read_text(encoding="utf-8")))
               if isinstance(n, ast.Import) for a in n.names}
    assert "kbgit" not in imports
    assert kg_sync.git("rev-parse", "--is-inside-work-tree") is not None
    with monkeypatch.context() as m:
        m.setattr(kbgit, "KB", str(tmp_path))
        assert kg_sync.git("rev-parse", "--is-inside-work-tree") is not None
    with monkeypatch.context() as m:
        m.setattr(kg_sync, "KB", str(tmp_path))
        assert kg_sync.git("rev-parse", "--is-inside-work-tree") is None


MOVED_TO_TRAILERS = ("trailer_audit", "trailers_from", "work_state", "work_ok", "cmd_check_trailers", "cmd_trailers",
                     "apply_trailers", "compute", "blob", "changed_paths")


def test_kg_split_trailers_live_in_kg_trailers_and_kbgit_imports_them():
    """kg_trailers defines the trailer audit, the trailer computation and the work state; kbgit.py defines none of
    them (it imports what its hooks, sync and the command line need), and kg_trailers imports no facade. Planted
    failure: a moved name put back into kbgit.py is reported."""
    kbgit_src = Path(TOOLS, "kbgit.py").read_text(encoding="utf-8")
    trailers_src = Path(TOOLS, "kg_trailers.py").read_text(encoding="utf-8")
    assert defined_in(trailers_src, MOVED_TO_TRAILERS) == set(MOVED_TO_TRAILERS)
    assert defined_in(kbgit_src, MOVED_TO_TRAILERS) == set()
    for name in ("trailer_audit", "work_state", "cmd_check_trailers"):
        assert getattr(kbgit, name) is getattr(kg_trailers, name)
    imports = {a.name for n in ast.walk(ast.parse(trailers_src)) if isinstance(n, ast.Import) for a in n.names}
    assert "kbgit" not in imports
    planted = kbgit_src + "\n\ndef work_state(values, paths, load):\n    return []\n"
    assert defined_in(planted, MOVED_TO_TRAILERS) == {"work_state"}


@requires_git
def test_kg_split_trailers_run_git_in_their_own_kb(tmp_path, monkeypatch):
    """kg_trailers runs git in its own KB: a patch of kg_trailers.KB moves its git calls to a directory that is no
    repository. Planted failure: the same patch on kbgit.KB leaves them in this repository."""
    assert kg_trailers.git("rev-parse", "--is-inside-work-tree") is not None
    with monkeypatch.context() as m:
        m.setattr(kbgit, "KB", str(tmp_path))
        assert kg_trailers.git("rev-parse", "--is-inside-work-tree") is not None
    with monkeypatch.context() as m:
        m.setattr(kg_trailers, "KB", str(tmp_path))
        assert kg_trailers.git("rev-parse", "--is-inside-work-tree") is None


MOVED_TO_HOOKS = ("HOOKS_DIR", "HOOKS", "ZERO", "worktree_tops", "hooks_path_is_ours", "lane_refusals", "cmd_install_hooks",
                  "hook_prepare", "hook_commit_msg")


def test_kg_split_hooks_live_in_kg_hooks_and_kbgit_imports_them():
    """kg_hooks defines the hook files, the hooks check, the lane refusal, the pre-push hook and install-hooks; kbgit.py
    defines none of the moved names (it imports the check and the command, and hands the pre-push hook its gate and its
    dirty paths), and kg_hooks imports no facade. Planted failure: a moved name put back into kbgit.py is reported."""
    kbgit_src = Path(TOOLS, "kbgit.py").read_text(encoding="utf-8")
    hooks_src = Path(TOOLS, "kg_hooks.py").read_text(encoding="utf-8")
    assert defined_in(hooks_src, MOVED_TO_HOOKS + ("hook_pre_push",)) == set(MOVED_TO_HOOKS + ("hook_pre_push",))
    assert defined_in(kbgit_src, MOVED_TO_HOOKS) == set()
    assert "kg_hooks.hook_pre_push(args, stdin, gate, kg_sync.dirty_paths)" in kbgit_src
    assert "kg_hooks.cmd_hook(a, gate, kg_sync.dirty_paths)" in kbgit_src
    for name in ("hooks_path_is_ours", "cmd_install_hooks", "HOOKS"):
        assert getattr(kbgit, name) is getattr(kg_hooks, name)
    imports = {a.name for n in ast.walk(ast.parse(hooks_src)) if isinstance(n, ast.Import) for a in n.names}
    assert "kbgit" not in imports
    planted = kbgit_src + "\n\ndef hooks_path_is_ours(cur):\n    return False\n"
    assert defined_in(planted, MOVED_TO_HOOKS) == {"hooks_path_is_ours"}


@requires_git
def test_kg_split_hooks_run_git_in_their_own_kb(tmp_path, monkeypatch):
    """kg_hooks runs git in its own KB: a patch of kg_hooks.KB moves its git calls to a directory that is no
    repository. Planted failure: the same patch on kbgit.KB leaves them in this repository."""
    assert kg_hooks.git("rev-parse", "--is-inside-work-tree") is not None
    with monkeypatch.context() as m:
        m.setattr(kbgit, "KB", str(tmp_path))
        assert kg_hooks.git("rev-parse", "--is-inside-work-tree") is not None
    with monkeypatch.context() as m:
        m.setattr(kg_hooks, "KB", str(tmp_path))
        assert kg_hooks.git("rev-parse", "--is-inside-work-tree") is None


MOVED_TO_HISTORY = ("user_path", "with_legacy", "id_regex", "split_arg", "classify", "cmd_log", "blame_line", "cmd_blame",
                    "cmd_asof", "census_message", "cmd_tag_census")
MOVED_TO_BRIDGE = ("BRIDGE_PREFIX", "bridge_dry_run", "cmd_bridge")
MOVED_TO_LANE_COMMANDS = ("cmd_lane", "cmd_check_lanes")


def test_kg_split_history_bridge_and_lane_commands_live_in_their_modules():
    """kg_history defines the log, blame, asof and tag-census commands with the paths they take, kg_bridge the bridge
    command and kg_lane the lane commands; kbgit.py defines none of the history and bridge names, keeps only the thin
    wrappers cmd_bridge, cmd_lane and cmd_check_lanes, and none of the three modules imports a facade. Planted failure:
    a moved name put back into kbgit.py is reported."""
    kbgit_src = Path(TOOLS, "kbgit.py").read_text(encoding="utf-8")
    for module, moved in (("kg_history", MOVED_TO_HISTORY), ("kg_bridge", MOVED_TO_BRIDGE),
                          ("kg_lane", MOVED_TO_LANE_COMMANDS)):
        src = Path(TOOLS, module + ".py").read_text(encoding="utf-8")
        assert defined_in(src, moved) == set(moved), module
        imports = {a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import) for a in n.names}
        assert "kbgit" not in imports, module
    assert defined_in(kbgit_src, MOVED_TO_HISTORY) == set()
    assert defined_in(kbgit_src, MOVED_TO_BRIDGE) == {"cmd_bridge"}
    assert defined_in(kbgit_src, MOVED_TO_LANE_COMMANDS) == set(MOVED_TO_LANE_COMMANDS)
    for call in ("kg_bridge.cmd_bridge(a, cmd_sync)", "kg_lane.cmd_lane(a, default_range)",
                 "kg_lane.cmd_check_lanes(a, default_range)"):
        assert call in kbgit_src
    for name in ("cmd_log", "cmd_blame", "cmd_asof", "cmd_tag_census"):
        assert getattr(kbgit, name) is getattr(kg_history, name)
    planted = kbgit_src + "\n\ndef classify(arg):\n    return None\n"
    assert defined_in(planted, MOVED_TO_HISTORY) == {"classify"}


@requires_git
def test_kg_split_history_bridge_and_lane_commands_run_git_in_their_own_kb(tmp_path, monkeypatch):
    """kg_history, kg_bridge and kg_lane run git in their own KB: a patch of the module's KB moves its git calls to a
    directory that is no repository. Planted failure: the same patch on kbgit.KB leaves them in this repository."""
    probes = {kg_history: lambda: kg_history.git("rev-parse", "--is-inside-work-tree"),
              kg_bridge: lambda: kg_bridge.git("rev-parse", "--is-inside-work-tree"),
              kg_lane: lambda: kg_merge.git("rev-parse", "--is-inside-work-tree", kb=kg_lane.KB)}
    for module, probe in probes.items():
        assert probe() is not None
        with monkeypatch.context() as m:
            m.setattr(kbgit, "KB", str(tmp_path))
            assert probe() is not None
        with monkeypatch.context() as m:
            m.setattr(module, "KB", str(tmp_path))
            assert probe() is None


FACADE_ALLOWED = {"main", "sync_host", "gate", "cmd_sync", "hook_pre_push", "cmd_hook", "cmd_lane", "cmd_check_lanes",
                  "cmd_bridge"}  # kb/_self/git.md, "kbgit.py keeps": the dispatch and the thin wrappers
FACADE_WRAPPER_LINES = 8  # a wrapper hands its arguments to a kg_ module; anything longer holds code of its own


def facade_extras(source):
    """The functions of SOURCE a facade may not define: a name outside FACADE_ALLOWED, or a wrapper (everything but
    main) longer than FACADE_WRAPPER_LINES lines."""
    out = set()
    for n in ast.parse(source).body:
        if isinstance(n, ast.FunctionDef) and (n.name not in FACADE_ALLOWED
                                               or (n.name != "main" and n.end_lineno - n.lineno + 1 > FACADE_WRAPPER_LINES)):
            out.add(n.name)
    return out


def test_bl_split_kbgit_facade_only():
    """kbgit.py defines main, the cmd_* wrappers and the thin sync wrappers, and no other function: what the allowed list
    names is the keep-whole verdict of kb/_self/git.md. Planted failures: a function outside the list and a wrapper
    that grew past the wrapper size are reported."""
    kbgit_src = Path(TOOLS, "kbgit.py").read_text(encoding="utf-8")
    assert facade_extras(kbgit_src) == set()
    assert facade_extras(kbgit_src + "\n\ndef classify(arg):\n    return None\n") == {"classify"}
    fat = "def cmd_lane(a):\n" + "    x = 1\n" * FACADE_WRAPPER_LINES + "    return x\n"
    assert facade_extras(fat) == {"cmd_lane"}
