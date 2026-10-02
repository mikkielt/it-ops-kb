"""selfdoc map rows of the ingest tool and its skill (`python3 _tools/tests.py -k kbingest_change`).

TestSelfdocIngest  the real kb/_self/map.csv maps _tools/kbingest.py to the kb-ingest skill as well as to its tools.md
                   row, so a change to the tool lists the skill as stale until the skill is edited or reviewed
                   (`-k kbingest_change_marks_the_ingest_skill_stale`).
"""
import pytest

import selfdoc
from conftest import LEAKY, SELF_REL as S, Repo, requires_git

TOOL = "_tools/kbingest.py"
SKILL = ".claude/skills/kb-ingest/SKILL.md"


class TestSelfdocIngest:
    def test_kbingest_map_names_the_ingest_skill(self):
        docs = selfdoc.describing(selfdoc.load_map(), [TOOL])
        assert SKILL in docs and f"{S}/tools.md" in docs

    @pytest.mark.git
    @requires_git
    def test_kbingest_change_marks_the_ingest_skill_stale(self, tmp_path, monkeypatch):
        """A throwaway repository holding the real map's rows for the tool: a commit to the tool lists the skill, and
        editing the skill clears it."""
        for k in LEAKY:
            monkeypatch.delenv(k, raising=False)
        real = selfdoc.load_map()
        rows = "".join(f"{doc},{TOOL}\n" for doc, pats in real.items() if TOOL in pats)
        assert SKILL in rows, "the real map has no row for the skill"
        repo = Repo(tmp_path)
        repo.git("init", "-q")
        repo.write(f"{S}/map.csv", "doc,pattern\n" + rows)
        for doc in selfdoc.load_map(repo.path):
            repo.write(doc, "doc\n")
        repo.write(TOOL, "print(1)\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "init")
        assert selfdoc.stale(repo.path) == []
        repo.write(TOOL, "print(2)\n")
        repo.git("commit", "-qam", "change the tool")
        assert SKILL in [doc for doc, _, _ in selfdoc.stale(repo.path)]
        assert [hit for doc, _, hit in selfdoc.stale(repo.path) if doc == SKILL] == [[TOOL]]
        repo.write(SKILL, "doc, updated\n")
        assert SKILL not in [doc for doc, _, _ in selfdoc.stale(repo.path)], "editing the skill counts as updating it"
