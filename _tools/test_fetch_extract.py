"""fetch.py text unpacks an archive it has no reader for by running a program from a table on a file nobody here wrote:
the program runs in the sandbox `kbingest map` uses, its output is read with caps and removed, and only the shipped table
and an internal root's own rows say what runs. One planted failure each."""
import os, stat, sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import fetch, kbcommon

FAKEX = str(Path(__file__).resolve().parent / "fixtures" / "extract" / "fakex.py")
TABLE = "extension,argv,out\n.fx,fakex x {in} -o{out},_cache/extract\n"


def extractor_on_path(tmp_path, monkeypatch):
    """A `fakex` program on a PATH outside the clone, a table row for it, and the folder the rows extract into."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if os.name == "nt":
        (bin_dir / "fakex.cmd").write_text(f'@"{sys.executable}" "{FAKEX}" %*\r\n', encoding="utf-8")
    else:
        launcher = bin_dir / "fakex"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKEX}" "$@"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    table = tmp_path / "table.csv"
    table.write_text(TABLE, encoding="utf-8")
    monkeypatch.setattr(fetch, "EXTRACTORS", str(table))
    monkeypatch.setenv("PATH", os.pathsep.join([str(bin_dir), os.path.dirname(sys.executable)]))
    return Path(kbcommon.HOME) / "_cache" / "extract"


def unpack(mode):
    body = (mode + "\nsynthetic\n").encode("utf-8")
    return fetch._extract_text("/p/pack.fx", body[:8], body, fetch.extractor_table(roots=[]))


def test_extractor_runs_in_the_sandbox_is_read_with_caps_and_is_removed(tmp_path, monkeypatch, capsys):
    out = extractor_on_path(tmp_path, monkeypatch)
    before = set(out.glob("*")) if out.exists() else set()
    secret = "s3" + "cr3t-" + "v" * 12
    monkeypatch.setenv("GITLAB_" + "TOKEN", secret)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.example.com:8080")
    text = unpack("ok")
    assert "== sub/note.txt ==\nsynthetic note" in text and "== blob.bin == (binary, printable strings)" in text
    assert "Synthetic.Package.Name" in text
    assert secret not in text and "GITLAB_" + "TOKEN" not in text  # the child got the allow-list environment
    assert "== proxy.txt ==\n" + fetch.kbsandbox.NETWORK_OFF["HTTPS_PROXY"] in text  # offline wins over the caller's proxy
    assert "extracting a .fx file with " in capsys.readouterr().err  # each run names the program it started
    assert set(out.glob("*")) == before, "the extraction folder was not removed"
    for mode, cap, want in (("link", None, "left a link"), ("many", ("EXTRACT_FILES_CAP", 3), "more than 3 files"),
                            ("deep", ("EXTRACT_DEPTH_CAP", 3), "deep"), ("hang", ("EXTRACT_TIMEOUT", 1), "ran over 1 seconds")):
        if cap:
            monkeypatch.setattr(fetch, *cap)
        if mode == "link" and not hasattr(os, "symlink"):
            continue
        with pytest.raises(ValueError, match=want):
            unpack(mode)
        assert set(out.glob("*")) == before, f"{mode}: the extraction folder was not removed"
    monkeypatch.setenv("PATH", os.path.dirname(sys.executable))
    with pytest.raises(ValueError, match="fakex is not installed"):
        unpack("ok")


def test_only_the_shipped_table_and_an_internal_root_name_what_runs(tmp_path, capsys):
    rows = "extension,argv,out\n"
    internal = tmp_path / "team"
    internal.mkdir()
    (internal / "_extractors.csv").write_text(rows + ".fx,fakex x {in} -o{out},_private/extract\n"
                                              ".cab,fakex x {in} -o{out},_cache/extract\n"  # a shipped extension stays
                                              ".up,../fakex x {in},_cache/x\n"  # a program with a folder part
                                              ".ab,fakex x {in},/tmp/x\n.pa,fakex x {in},_cache/../x\n"  # out leaves the clone
                                              ".no,fakex x,_cache/x\n", encoding="utf-8")  # no {in}
    public = tmp_path / "pub"
    public.mkdir()
    (public / "_extractors.csv").write_text(rows + ".px,fakex x {in},_cache/x\n", encoding="utf-8")
    roots = [SimpleNamespace(name="team", path=str(internal), visibility="internal"),
             SimpleNamespace(name="pub", path=str(public), visibility="public")]
    table = fetch.extractor_table(roots=roots)
    assert {".msi", ".cab", ".wim"} <= set(table) and all(table[e][0][0] == "7z" for e in (".msi", ".cab", ".wim"))
    assert table[".fx"] == (["fakex", "x", "{in}", "-o{out}"], "_private/extract", False)  # an internal root adds a row
    assert not set(table) & {".px", ".up", ".ab", ".pa", ".no"}, sorted(table)  # a public root adds none; bad rows are skipped
    assert capsys.readouterr().err.count("skipped") == 4
    with pytest.raises(ValueError, match=r"\.doc file \(an OLE compound file\): no extractor row names \.doc"):
        fetch._extract_text("/p/old.doc", fetch.OLE_MAGIC, fetch.OLE_MAGIC + b"x", table)
