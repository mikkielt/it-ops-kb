"""kbfacts.topics_for(imports=True): the package names a file declares, matched against the signals instead of its text.

Planted fixtures (fixtures/topics_for/imports/) prove each reader: Python (ast, never run), package.json, go.mod,
csproj and Directory.Packages.props (xml.etree), PowerShell #Requires and .psd1 RequiredModules. A signal that a file
only mentions in a comment, a docstring or a string is found lexically and not with imports; files git marks
linguist-generated or linguist-vendored are skipped; an import of one topic ranks above one shared by many; the
default lexical mode is unchanged.
"""
import json, subprocess
from pathlib import Path

import pytest

from conftest import TOOLS, git_env, requires_git

import kbfacts

FIX = Path(TOOLS) / "fixtures" / "topics_for" / "imports"
MSAL, LDAP, KERB, WI, AZ = "public/auth/msal", "public/auth/ldap", "public/auth/kerberos", "public/auth/wi", "public/az/az"
SIGNALS = [("msal", MSAL), ("@azure/msal-node", MSAL), ("Microsoft.Identity.Client", MSAL),
           ("ldap3", LDAP), ("ldapjs", LDAP), ("go-ldap/ldap", LDAP),
           ("gssapi", KERB), ("kerberos", KERB), ("kinit", KERB),
           ("Azure.Identity", WI), ("Az.Accounts", AZ)]


def plant(monkeypatch, pairs):
    table = [(s, t, kbfacts.signal_regex(s)) for s, t in pairs]
    monkeypatch.setattr(kbfacts, "signals", lambda: table)


@pytest.fixture(autouse=True)
def planted_signals(monkeypatch):
    plant(monkeypatch, SIGNALS)


def names(fixture):
    """The imports the reader for the fixture file finds, as a sorted list of names."""
    return sorted(n for n, _ in kbfacts.imports_of(fixture, (FIX / fixture).read_text(encoding="utf-8")))


def py(tmp_path, name):
    """A Python fixture stored as `<name>.txt` (a .py file in the tree would be linted and scanned), copied under its
    own name into `tmp_path`: its path."""
    dst = tmp_path / name
    dst.write_text((FIX / f"{name}.txt").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return dst


def topics(res):
    return {x["topic"]: x for x in res["topics"]}


def test_import_topics_python_reader_reads_imports_not_comments(tmp_path):
    got = kbfacts.imports_of("app.py", py(tmp_path, "app.py").read_text(encoding="utf-8"))
    assert sorted(n for n, _ in got) == ["gssapi", "ldap3.Connection", "ldap3.Server", "msal", "os", "requests_kerberos",
                                         "vendorlib"]
    assert dict(got)["msal"] == 3 and dict(got)["ldap3.Server"] == 4 and dict(got)["gssapi"] == 9
    # the relative import, the docstring, and the `# uses kinit` comment name nothing
    assert not any(n in ("helper", "local", "kinit", "kerberos") for n, _ in got)


def test_import_topics_python_never_runs_the_source(tmp_path):
    marker = tmp_path / "ran.txt"
    src = f"import msal\nopen({str(marker)!r}, 'w').write('ran')\nraise SystemExit(7)\n"
    assert [n for n, _ in kbfacts.imports_of("boom.py", src)] == ["msal"]
    assert not marker.exists()


def test_import_topics_python_unparsable_and_oversize_give_none(monkeypatch, tmp_path):
    app = py(tmp_path, "app.py")
    assert kbfacts.imports_of("broken.py", py(tmp_path, "broken.py").read_text(encoding="utf-8")) == []
    monkeypatch.setattr(kbfacts, "MAX_AST_BYTES", 10)
    assert kbfacts.imports_of("app.py", app.read_text(encoding="utf-8")) == []
    res = kbfacts.topics_for([str(app)], imports=True)
    assert res["topics"] == [] and any("over" in s and "Python reader" in s for s in res["skipped"])


def test_import_topics_package_json_reader():
    assert names("package.json") == ["@azure/msal-node", "express", "ldapjs", "react"]  # not the `kinit` script text


def test_import_topics_go_mod_reader():
    assert names("go.mod") == ["github.com/AzureAD/microsoft-authentication-library-for-go", "github.com/go-ldap/ldap/v3",
                               "golang.org/x/sys"]  # not the comment, the module line or the replace


def test_import_topics_csproj_reader():
    assert names("App.csproj") == ["Microsoft.Identity.Client", "Newtonsoft.Json"]  # not the comment or the prose


def test_import_topics_directory_packages_props_reader():
    assert names("Directory.Packages.props") == ["Azure.Identity", "Microsoft.Identity.Client"]


def test_import_topics_csproj_with_a_doctype_or_bad_xml_gives_none():
    bomb = '<?xml version="1.0"?><!DOCTYPE p [<!ENTITY a "x">]><Project><PackageReference Include="msal"/></Project>'
    assert kbfacts.imports_of("x.csproj", bomb) == []
    assert kbfacts.imports_of("x.csproj", "<Project><PackageReference Include='msal'>") == []
    ns = '<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><ItemGroup><PackageReference Include="msal"/></ItemGroup></Project>'
    assert [n for n, _ in kbfacts.imports_of("old.csproj", ns)] == ["msal"]


def test_import_topics_powershell_requires_reader():
    got = kbfacts.imports_of("deploy.ps1", (FIX / "deploy.ps1").read_text(encoding="utf-8"))
    assert sorted(n for n, _ in got) == ["Az.Accounts", "ConfigurationManager", "Microsoft.Graph.Intune"]
    assert dict(got)["Az.Accounts"] == 2 and dict(got)["ConfigurationManager"] == 3
    # `# #Requires` inside a comment and a module named in a comment are not requirements
    assert not any(n in ("Fake.Module", "Az.Storage") for n, _ in got)


def test_import_topics_psd1_required_modules_reader():
    assert names("Tool.psd1") == ["Az.Accounts", "Microsoft.Graph.Authentication", "PSDesiredStateConfiguration"]


def test_import_topics_unknown_file_names_have_no_reader():
    assert kbfacts.import_reader("README.md") is None and kbfacts.import_reader("app.js") is None
    assert kbfacts.imports_of("README.md", "import msal") == []


def test_import_topics_comment_only_signal_is_found_lexically_not_by_imports(tmp_path):
    notes = py(tmp_path, "notes.py")
    lexical = kbfacts.topics_for([str(notes)])
    assert set(topics(lexical)) == {MSAL, LDAP, KERB}
    assert "mode" not in lexical
    by_imports = kbfacts.topics_for([str(notes)], imports=True)
    assert by_imports["topics"] == [] and by_imports["mode"] == "imports" and by_imports["imports"] == 0
    assert by_imports["files"] == 1


def test_import_topics_match_signals_against_the_import_names_only(tmp_path):
    app = py(tmp_path, "app.py")
    res = kbfacts.topics_for([str(app), str(FIX / "package.json")], imports=True)
    t = topics(res)
    assert set(t) == {MSAL, LDAP, KERB}  # `kinit` and the docstring's kerberos are not imports; requests_kerberos is no word match
    assert [i["import"] for i in t[KERB]["imports"]] == ["gssapi"]
    assert sorted(i["import"] for i in t[LDAP]["imports"]) == ["ldap3.Connection", "ldap3.Server", "ldapjs"]
    assert {i["import"]: i["where"] for i in t[MSAL]["imports"]} == {"msal": f"{app}:3",
                                                                       "@azure/msal-node": f"{FIX / 'package.json'}:5"}
    assert res["imports"] == 11  # distinct import names of the two files
    json.dumps(res)  # plain data for rag.py --json and kb_mcp


def test_import_topics_ranks_an_import_of_one_topic_above_one_shared_by_many(monkeypatch):
    plant(monkeypatch, [("msal", MSAL), ("azure", WI), ("azure", AZ)])
    res = kbfacts.topics_for(text="import azure.storage\nimport msal\n", imports=True)
    assert [x["topic"] for x in res["topics"]] == [MSAL, WI, AZ]
    t = topics(res)
    assert t[MSAL]["score"] == 1.0 and t[AZ]["score"] == 0.5 and t[WI]["score"] == 0.5
    assert t[MSAL]["imports"][0]["topics"] == 1 and t[WI]["imports"][0] == {
        "import": "azure.storage", "where": "text:1", "signals": ["azure"], "topics": 2}


def test_import_topics_text_is_read_as_python_then_powershell():
    assert set(topics(kbfacts.topics_for(text="from ldap3 import Server\n", imports=True))) == {LDAP}
    assert set(topics(kbfacts.topics_for(text="#Requires -Modules Az.Accounts\n", imports=True))) == {AZ}
    assert kbfacts.topics_for(text="# import msal\nprint('ldap3')\n", imports=True)["topics"] == []


def test_import_topics_lexical_mode_is_unchanged_by_the_signature(tmp_path):
    res = kbfacts.topics_for([str(py(tmp_path, "app.py"))])
    assert set(res) == {"topics", "files", "text", "skipped"}
    assert set(topics(res)) == {MSAL, LDAP, KERB}
    assert set(topics(res)[KERB]["signals"]) == {"kerberos", "kinit", "gssapi"}  # the docstring and the comment count


def test_import_topics_real_signals_map_a_msal_import(monkeypatch):
    monkeypatch.undo()  # the kb's own signals.csv
    res = kbfacts.topics_for(text="import msal\n", imports=True)
    assert "public/auth/msal-public-client" in topics(res)


def test_import_topics_format_names_the_import_that_matched(monkeypatch):
    plant(monkeypatch, [("msal", MSAL), ("azure", WI), ("azure", AZ)])
    out = kbfacts.format_topics_for(kbfacts.topics_for(text="import azure.storage\nimport msal\n", imports=True))
    assert "by their imports (2 found)" in out
    assert f"- {MSAL}  imports: msal (text:2; msal)" in out
    assert "azure.storage (text:1; azure; also 1 other topic(s))" in out
    none = kbfacts.format_topics_for(kbfacts.topics_for(text="import os\n", imports=True))
    assert "no kb signal found among the imports" in none


def attr_repo(tmp_path, attributes):
    """A throwaway repository with one file per case, each importing a different signal."""
    repo = tmp_path / "svc"
    for rel, body in {"gen/a.py": "import msal\n", "third_party/b.py": "import ldap3\n", "kept/c.py": "import Azure.Identity\n",
                      "unset/d.py": "import gssapi\n"}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body, encoding="utf-8", newline="\n")
    (repo / ".gitattributes").write_text(attributes, encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env(), capture_output=True)
    return repo


ATTRS = "gen/** linguist-generated\nthird_party/** linguist-vendored\nkept/** linguist-generated=false\nunset/** -linguist-vendored\n"


@requires_git
def test_import_topics_skip_files_git_marks_generated_or_vendored(tmp_path):
    repo = attr_repo(tmp_path, ATTRS)
    res = kbfacts.topics_for([str(repo)], imports=True, base=str(tmp_path))
    assert set(topics(res)) == {WI, KERB}  # msal (generated) and ldap3 (vendored) are skipped; false and unset keep
    assert sorted(res["skipped"]) == [f"{Path('svc/gen/a.py')}: linguist-generated",
                                      f"{Path('svc/third_party/b.py')}: linguist-vendored"]
    assert res["files"] == 2


@requires_git
def test_import_topics_without_the_attributes_every_file_counts(tmp_path):
    repo = attr_repo(tmp_path, "# nothing marked\n")
    res = kbfacts.topics_for([str(repo)], imports=True, base=str(tmp_path))
    assert set(topics(res)) == {MSAL, LDAP, WI, KERB} and res["skipped"] == []


@requires_git
def test_import_topics_no_git_or_no_repository_skips_nothing(tmp_path, monkeypatch):
    repo = attr_repo(tmp_path, ATTRS)
    def no_git(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(kbfacts.subprocess, "run", no_git)
    assert set(topics(kbfacts.topics_for([str(repo)], imports=True, base=str(tmp_path)))) == {MSAL, LDAP, WI, KERB}
    monkeypatch.undo()
    plain = tmp_path / "plain"
    (plain / "gen").mkdir(parents=True)
    (plain / "gen" / "a.py").write_text("import msal\n", encoding="utf-8", newline="\n")
    (plain / ".gitattributes").write_text("gen/** linguist-generated\n", encoding="utf-8", newline="\n")
    assert kbfacts.marked_files([str(plain / "gen" / "a.py")]) == {}  # no .git above it: no attribute is read
