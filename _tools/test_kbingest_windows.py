"""kbingest.py under Windows path semantics, planted through ntpath on any host.

`names_clone_code` exempts a drive-less rooted piece (HOMEPATH `\\Users\\x`), which is no relative path and cannot lie
inside a drive-qualified top, and keeps counting a drive-qualified piece inside a top, a relative piece with a folder
part, `..\\x` and a UNC piece as clone code. On posix semantics nothing changes.
"""
import ntpath

import pytest

import kbingest

TOP = "C:\\work\\tree"


@pytest.fixture
def nt_paths(monkeypatch):
    monkeypatch.setattr(kbingest.os, "path", ntpath)
    monkeypatch.setattr(kbingest.os, "pathsep", ";")
    monkeypatch.setattr(kbingest.os, "sep", "\\")

    def inside(path, root):  # what under_worktree answers for a Windows path: a UNC share cannot be resolved, so inside
        if path.startswith("\\\\"):
            return True
        return ntpath.normcase(path).startswith(ntpath.normcase(root).rstrip("\\") + "\\")

    monkeypatch.setattr(kbingest, "under_worktree", inside)


@pytest.mark.parametrize("value", ["\\Users\\x", "/Users/x", "\\Windows\\system32", "\\Users\\x;\\Windows"])
def test_names_clone_code_drive_less_rooted_is_exempt(nt_paths, value):
    assert kbingest.drive_less_rooted(value.split(";")[0])
    assert not kbingest.names_clone_code(value, [TOP, None])


@pytest.mark.parametrize("value", ["C:\\work\\tree\\hook.js", "--require=C:\\work\\tree\\hook.js", "tools\\w", "..\\x",
                                   ".\\hook.js", "\\\\server\\share\\x", "\\Users\\x;tools\\w", ".."])
def test_names_clone_code_drive_less_rooted_keeps_the_rest_counting(nt_paths, value):
    assert kbingest.names_clone_code(value, [TOP, None])


def test_names_clone_code_drive_less_rooted_kept_env_homepath(nt_paths):
    assert kbingest.kept_env("HOMEPATH", "\\Users\\x", [TOP])
    assert not kbingest.kept_env("HOMEPATH", "\\\\server\\share\\x", [TOP])


def test_names_clone_code_drive_less_rooted_posix_unchanged():
    assert not kbingest.drive_less_rooted("\\Users\\x")
    assert kbingest.names_clone_code("\\Users\\x", [None])
    assert kbingest.names_clone_code("tools/w", [None])
