#!/usr/bin/env python3
"""Survey a git repository before its knowledge goes into a kb root (stdlib only; the /kb-ingest skill).

  kbingest.py survey REPO [--rev REV] [--forge gitlab|github] [--max-bytes N] [--files] [--pins]
      REPO is a local clone. Prints the remote (host and project path, never credentials), the commit REV (default
      HEAD) resolves to, whether a remote-tracking branch holds it (as of the last fetch: else the pinned urls do
      not resolve for anyone else yet), the pinned url form a CODE source row takes, whether .gitattributes were read
      at the commit, then per top-level area the kept files by kind and the files left out. `--files` adds one
      tab-separated line per file: `keep KIND PATH URL [secret]` or `skip REASON PATH`. `--pins` adds one tab-separated
      line per pin, `pin FILE PIN VALUE`, and a `note: pins: FILE: ...` line per pin file that could not be read. The pin
      files are those of kb/public/agents/codebase-mapping.csv: Python (.python-version, pyproject requires-python,
      uv.lock), Node (package.json engines, devEngines, packageManager; .nvmrc), TypeScript (tsconfig extends), Go
      (go.mod and go.work go, toolchain, use), Rust (rust-toolchain(.toml), Cargo.toml rust-version, edition), Java
      (pom.xml maven.compiler.release and <release>, gradle-wrapper distributionUrl, build.gradle languageVersion),
      .NET (global.json sdk, project and Directory.Build files TargetFramework(s) and LangVersion,
      Directory.Packages.props, packages.lock.json), PowerShell (#Requires in .ps1/.psm1, .psd1 PowerShellVersion,
      CompatiblePSEditions, RequiredModules) and environment (devcontainer.json image and features,
      devcontainer-lock.json, .tool-versions, mise.toml). Pins come from the files the survey keeps, plus
      packages.lock.json and uv.lock, which it leaves out as generated but which are pin files. They are read at the
      commit with tomllib, json, xml.etree and line scans only: a file with comments (global.json, tsconfig.json,
      devcontainer.json) has them scanned out, a .psd1 is read as text; nothing is run, imported or evaluated.
  kbingest.py url REPO PATH [--rev REV] [--forge gitlab|github]
      the pinned url of one file at the commit: the url of its source row (`kbid.py url <URL> --root NAME`).

  kbingest.py map REPO [--rev REV] [--out FILE] [--lang LANG[,LANG]] [--timeout SECONDS] [--max-bytes N]
      Opt-in and read-only (the survey never runs it). Checks the commit out into a scratch git worktree (no hook runs,
      no LFS filter fetches), and for each language that has kept files (the survey's rules) and an installed toolchain
      runs its mapper: read-only commands only (kb/public/agents/codebase-mapping.csv), each as an argument list with a
      timeout, in a network-off environment (no credentials or proxies passed; refusing proxies, GOTOOLCHAIN=local,
      offline switches). Writes one JSON map, by default _cache/ingest/<repo>-<commit12>.json, never under kb/, then
      removes the worktree. The map holds the format version, the commit, `tools` (name and version per language),
      `packages`, `imports` (per file), `entry_points` and `notes`. A missing toolchain, a timeout, a non-zero exit, an
      output that is not JSON and a file that does not parse are notes, not errors. Python is mapped with
      `python -I -B -m ast` in a subprocess per file; another language is a Mapper subclass added to MAPPERS.
      Go and Cargo run at the root; .NET (`dotnet msbuild -getProperty -getItem`, never `-target` or `-restore`, and
      never `dotnet package list`), npm (`npm ls --all --json --package-lock-only`) and TypeScript (`tsc
      --showConfig`, `--listFilesOnly`) run per project directory. `tsc` is the one on PATH, never `npx` and never
      a program inside the worktree; a toolchain is never installed.

  kbingest.py drift REPO [--rev NEW] [--root NAME] [--prefix TOPIC] [--remote HOST/PROJECT]
      Read-only: writes no file. For each CODE fact (`[CODE S-id: path#symbol]`, or `path#L10-L20`) of the served roots
      (or one --root, one --prefix) whose source row is a pinned url into this repository (the origin's host and
      project, else --remote), compares the cited file at the url's commit with the file at NEW (default HEAD), both
      read with `git cat-file`, and prints one tab-separated line per fact whose evidence differs:
      `finding KIND KBPATH:LINE SOURCE-ID PATH#SYMBOL DETAIL`, then a `checked=N unchanged=N findings=N elsewhere=N`
      line (`elsewhere`: CODE facts of other repositories, not compared). KIND is file-missing (the path is not at NEW
      and git sees no rename), moved (renamed: the detail says what the symbol did there; or a line range that now
      sits elsewhere), symbol-missing (no definition of the symbol at NEW: the detail tells whether it is still
      mentioned), changed (the definition, or the lines of a range, read differently) or unverifiable (the pinned
      commit or the file is not in the clone: fetch it). The symbol is the last segment of `Class.method` or
      `mod::func`; a definition is found by a heuristic, not a parser: a keyword (def, class, function, fn, func,
      struct, type, const, ...) then the name, the name at the start of a line as a key or constant, or a function head
      `name(...) {` or with a type before it. Its body runs to the next line at the same or a lower indent, plus a
      closing bracket, and is compared as text; a file that changed elsewhere, or a definition that only moved to
      another line, is not a finding. It rewrites no fact, source row or date: the findings are for /kb-refresh.

Everything is read at the commit (git ls-tree, check-attr --source, cat-file), never from the working tree, so the
facts match the pinned urls. Left out, first reason wins:
  secret-file   names that hold keys or credentials: .env (not .env.example), *.pem, *.key, *.pfx, *.p12, *.jks,
                *.kdbx, *.ppk, id_rsa and siblings, credentials/secrets config files, .netrc, .npmrc, .pypirc, *.tfstate
  vendored      a submodule, `linguist-vendored` set, or a vendor path (vendor/, third_party/, node_modules/, ...)
  generated     `linguist-generated` or `gitlab-generated` set; a lock file, minified or source-map file, protobuf
                or designer output, a dist/ or generated/ path; or a generated-code header in the first lines
                (Go's `// Code generated ... DO NOT EDIT.`, or "generated" with "do not edit" on one line)
  large         over --max-bytes (default 1000000)
  binary        a NUL byte in the first 8000 bytes
An attribute that is unset (`-linguist-generated`, `-linguist-vendored`, `-gitlab-generated`) keeps a file the
default lists would leave out (kb topic agents/repository-ingestion). A kept file whose text matches a secret shape
(kbcommon.SECRETS, the kb's leak scan) is flagged `secret`: describe it, never copy its values, and tell the owner.
Kinds of kept files: doc, ci, config, code, test, other.

Pinned urls: GitHub (github.com) as raw.githubusercontent.com/<owner>/<repo>/<commit>/<path>; GitLab (gitlab.com or
a self-managed host) as https://<host>/<project>/-/raw/<commit>/<path>. A host named neither github.com nor gitlab.*
needs --forge; another forge gets no url (`url` refuses; the skill says what to do).

Exit: 0 done (`drift`: no finding), 1 `map` could not create its worktree or `drift` printed findings, 2 refused (not a
git repository, an unknown REV, `url` with no pinned url form, `map` with an unknown language or an --out under kb/,
`drift` with an unknown --root or a repository with no remote and no --remote).
"""
import argparse, contextlib, json, os, posixpath, re, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kbcommon, kbfacts  # noqa: E402

ATTRS = ("linguist-generated", "linguist-vendored", "gitlab-generated")
KINDS = ("doc", "code", "config", "ci", "test", "other")
SKIPS = ("secret-file", "vendored", "generated", "large", "binary")

SECRET_FILE = re.compile(
    r"(?i)(?:^|/)\.env(?:\.(?!example$|sample$|template$|dist$)[^/]+)?$"
    r"|\.(?:pem|key|pfx|p12|jks|keystore|kdbx|ppk)$"
    r"|(?:^|/)id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?$"
    r"|(?:^|/)(?:credentials|secrets?)(?:\.(?:json|ya?ml|toml|ini|env|txt|xml|conf|cfg))?$"
    r"|(?:^|/)\.(?:netrc|pgpass|npmrc|pypirc|htpasswd)$|\.tfstate(?:\.backup)?$")
VENDOR_PATH = re.compile(r"(?:^|/)(?:vendor|vendors|third[_-]?party|3rdparty|node_modules|bower_components|\.venv|venv|"
                         r"site-packages|Pods|Carthage)/", re.I)
GENERATED_NAME = re.compile(
    r"(?i)(?:^|/)(?:package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|Gopkg\.lock|go\.sum|Cargo\.lock|"
    r"poetry\.lock|uv\.lock|Pipfile\.lock|composer\.lock|Gemfile\.lock|packages\.lock\.json|flake\.lock)$"
    r"|\.min\.(?:js|css)$|\.(?:js|css)\.map$|_pb2(?:_grpc)?\.pyi?$|\.pb\.(?:go|cc|h)$|\.g\.cs$|\.designer\.cs$"
    r"|(?:^|/)(?:dist|generated|__generated__)/")
GO_HEADER = re.compile(rb"^// Code generated .* DO NOT EDIT\.$", re.M)  # Go's convention (cmd/go, go generate)
ANY_HEADER = re.compile(rb"(?i)\bgenerated\b.*\bdo not edit\b")
HEAD_LINES = 10  # a generated-code header sits before the first code: look this far
BINARY_PEEK = 8000

CI = re.compile(r"(?i)(?:^|/)\.gitlab-ci\.ya?ml$|^\.gitlab/|^\.github/workflows/|(?:^|/)jenkinsfile$|"
                r"(?:^|/)azure-pipelines[^/]*\.ya?ml$|(?:^|/)\.pre-commit-config\.ya?ml$")
TEST = re.compile(r"(?i)(?:^|/)(?:tests?|__tests__|specs?|testdata|fixtures)/|(?:^|/)test_[^/]+\.py$|_test\.(?:go|py)$|"
                  r"\.tests?\.ps1$|\.(?:spec|test)\.[jt]sx?$")
CONFIG_NAME = re.compile(r"(?i)(?:^|/)(?:dockerfile|containerfile|makefile|\.gitattributes|\.gitignore|"
                         r"requirements[^/]*\.txt|\.env\.[^/]+)$")
DOC = re.compile(r"(?i)(?:^|/)(?:docs?|documentation|wiki|adrs?|runbooks?)/|\.(?:md|markdown|rst|adoc|txt)$|"
                 r"(?:^|/)(?:readme|changelog|contributing|codeowners|license|notice)[^/]*$")
CONFIG = re.compile(r"(?i)\.(?:json|jsonc|ya?ml|toml|ini|cfg|conf|config|properties|psd1|xml|tfvars|editorconfig)$")
CODE = re.compile(r"(?i)\.(?:py|pyi|ps1|psm1|cs|go|rs|ts|tsx|js|jsx|mjs|cjs|sh|bash|java|kt|rb|php|sql|bicep|tf|c|h|"
                  r"cpp|hpp|swift|lua|pl|bat|cmd|vbs|groovy)$")
SECRET_TEXT = [re.compile(p.encode()) for p in kbcommon.SECRETS]


def git(repo, *args, stdin=None):
    """A git command in REPO, as bytes: an argument list, never a shell."""
    return subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True)


def remote_of(repo):
    """(remote name, host, project path) of the repository's `origin` (else its first remote), or None."""
    names = git(repo, "remote").stdout.decode("utf-8", "replace").split()
    if not names:
        return None
    name = "origin" if "origin" in names else names[0]
    url = git(repo, "remote", "get-url", name).stdout.decode("utf-8", "replace").strip()
    host, path = parse_remote(url)
    return (name, host, path) if host else None


def parse_remote(url):
    """(host, project path) of a remote url (https, ssh:// or scp-like `git@host:group/repo.git`); credentials,
    ssh ports and `.git` dropped. (None, None) for a local path."""
    if url.startswith(("/", "./", "../", "file:")) or re.match(r"^[A-Za-z]:[\\/]", url):
        return None, None
    if "://" in url:
        u = urlsplit(url)
        host = u.hostname or ""
        if u.port and u.scheme in ("http", "https"):
            host += f":{u.port}"
        path = u.path
    else:
        m = re.match(r"^(?:[^@/]+@)?([^:/]+):(.+)$", url)
        if not m:
            return None, None
        host, path = m.group(1), m.group(2)
    path = path.strip("/")
    path = path[:-4] if path.endswith(".git") else path
    return (host.lower(), path) if host and path else (None, None)


def forge_of(host, override=None):
    if override:
        return override
    if host == "github.com":
        return "github"
    if host.split(":")[0] == "gitlab.com" or host.startswith("gitlab.") or ".gitlab." in host:
        return "gitlab"
    return None


def pin_url(forge, host, path, commit, rel):
    """The pinned url of file REL at COMMIT, or None when the forge has no raw url form here."""
    q = quote(rel, safe="/")
    if forge == "github" and host == "github.com":
        return f"https://raw.githubusercontent.com/{path}/{commit}/{q}"
    if forge == "gitlab":
        return f"https://{host}/{path}/-/raw/{commit}/{q}"
    return None


def resolve(repo, rev):
    p = git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return p.stdout.decode().strip() if p.returncode == 0 else None


def off_commit(repo, commit):
    """True when the checked-out tracked files are not COMMIT's: HEAD's tree differs from the commit's (another
    commit with the same tree is fine) or a tracked file has uncommitted changes. Untracked files do not count. False
    for a bare repository or one without a work tree."""
    if git(repo, "rev-parse", "--is-inside-work-tree").stdout.strip() != b"true":
        return False
    trees = [git(repo, "rev-parse", "--verify", "--quiet", f"{r}^{{tree}}").stdout.strip() for r in ("HEAD", commit)]
    if trees[0] != trees[1]:
        return True
    return bool(git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip())


def tree(repo, commit):
    """[(path, type, object id, size)] of every entry at the commit (submodules have type `commit`, size 0)."""
    out = git(repo, "ls-tree", "-r", "-l", "-z", "--full-tree", commit).stdout
    entries = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        _mode, kind, oid, size = meta.split()
        entries.append((path.decode("utf-8", "surrogateescape"), kind.decode(), oid.decode(),
                        int(size) if size.isdigit() else 0))
    return entries


def symlinks(repo, commit):
    """{path} of the entries at the commit that git stores as symbolic links (mode 120000)."""
    out = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).stdout
    return {rec.split(b"\t", 1)[1].decode("utf-8", "surrogateescape")
            for rec in out.split(b"\0") if rec.startswith(b"120000 ")}


def attributes(repo, commit, paths):
    """({path: {attr: info}}, where): the attributes at the commit, or of the working tree when this git has no
    `check-attr --source` (before 2.40)."""
    data = b"".join(p.encode("utf-8", "surrogateescape") + b"\0" for p in paths)
    where = "at the commit"
    p = git(repo, "check-attr", "--stdin", "-z", f"--source={commit}", *ATTRS, stdin=data)
    if p.returncode:
        where = "of the working tree (this git has no check-attr --source)"
        p = git(repo, "check-attr", "--stdin", "-z", *ATTRS, stdin=data)
    parts = p.stdout.split(b"\0")
    out = {}
    for i in range(0, len(parts) - 2, 3):
        path = parts[i].decode("utf-8", "surrogateescape")
        out.setdefault(path, {})[parts[i + 1].decode()] = parts[i + 2].decode()
    return out, where


def contents(repo, oids):
    """{object id: bytes} for the blobs, in one `git cat-file --batch`."""
    if not oids:
        return {}
    out = git(repo, "cat-file", "--batch", stdin="".join(o + "\n" for o in oids).encode()).stdout
    found, i = {}, 0
    while i < len(out):
        nl = out.index(b"\n", i)
        head = out[i:nl].split()
        if len(head) < 3 or head[1] == b"missing":
            i = nl + 1
            continue
        size = int(head[2])
        found[head[0].decode()] = out[nl + 1:nl + 1 + size]
        i = nl + 1 + size + 1
    return found


def kind_of(path):
    for kind, rx in (("ci", CI), ("test", TEST), ("config", CONFIG_NAME), ("doc", DOC), ("config", CONFIG), ("code", CODE)):
        if rx.search(path):
            return kind
    return "other"


def generated_header(data):
    head = b"\n".join(data.splitlines()[:HEAD_LINES])
    return bool(GO_HEADER.search(head) or ANY_HEADER.search(head))


def classify(entries, attrs, max_bytes, read):
    """[(path, "keep", kind, secret) or (path, "skip", reason, False)] for every tree entry. `read(oids)` returns
    {oid: bytes} for the entries that pass the name, attribute and size rules."""
    result, pending = {}, []
    for path, kind, oid, size in entries:
        a = attrs.get(path, {})
        unset_gen = "unset" in (a.get("linguist-generated"), a.get("gitlab-generated"))
        if kind == "commit":
            result[path] = ("skip", "vendored", False)  # a submodule: another repository's code
        elif kind != "blob":
            continue
        elif SECRET_FILE.search(path):
            result[path] = ("skip", "secret-file", False)
        elif a.get("linguist-vendored") == "set" or (a.get("linguist-vendored") != "unset" and VENDOR_PATH.search(path)):
            result[path] = ("skip", "vendored", False)
        elif "set" in (a.get("linguist-generated"), a.get("gitlab-generated")) or (not unset_gen and GENERATED_NAME.search(path)):
            result[path] = ("skip", "generated", False)
        elif size > max_bytes:
            result[path] = ("skip", "large", False)
        else:
            pending.append((path, oid, unset_gen))
    data = read([oid for _, oid, _ in pending])
    for path, oid, unset_gen in pending:
        text = data.get(oid, b"")
        if b"\0" in text[:BINARY_PEEK]:
            result[path] = ("skip", "binary", False)
        elif not unset_gen and generated_header(text):
            result[path] = ("skip", "generated", False)
        else:
            result[path] = ("keep", kind_of(path), any(rx.search(text) for rx in SECRET_TEXT))
    return [(p, *result[p]) for p, *_ in entries if p in result]


def area_of(path):
    return path.split("/", 1)[0] if "/" in path else "."


def cmd_survey(a):
    repo = Path(a.repo).expanduser().resolve()
    commit = resolve(repo, a.rev)
    if commit is None:
        print(f"refused: {repo.name}: not a git repository, or {a.rev!r} names no commit")
        return 2
    rem = remote_of(repo)
    forge = forge_of(rem[1], a.forge) if rem else None
    entries = tree(repo, commit)
    attrs, where = attributes(repo, commit, [p for p, k, _, _ in entries if k == "blob"])
    rows = classify(entries, attrs, a.max_bytes, lambda oids: contents(repo, oids))
    pushed = git(repo, "branch", "-r", "--contains", commit).stdout.strip()
    dirty = off_commit(repo, commit)
    date = git(repo, "show", "-s", "--format=%cs", commit).stdout.decode().strip()

    print(f"repo: {repo.name}")
    print(f"remote: {rem[0]} {rem[1]}/{rem[2]} (forge {forge or 'unknown: pass --forge gitlab|github'})" if rem
          else "remote: none (a source row needs a url others can open: push the repository first)")
    print(f"commit: {commit} ({a.rev}, {date}); on a remote branch: "
          f"{'yes' if pushed else 'no (push it, or the pinned urls will not resolve)'} (as of the last fetch)")
    sample = pin_url(forge, rem[1], rem[2], commit, "PATH") if rem else None
    print(f"pin: {sample[:-4] + '<path>' if sample else 'none: no raw url form for this forge (see the /kb-ingest skill)'}")
    print(f"attributes: {where}")
    if dirty:
        print(f"worktree: differs from the commit: read files with `git -C {repo.name} show {commit[:12]}:<path>`")
    kept = [r for r in rows if r[1] == "keep"]
    skip_counts = {s: sum(1 for r in rows if r[1] == "skip" and r[2] == s) for s in SKIPS}
    flagged = [r[0] for r in kept if r[3]]
    print(f"files={len(rows)} keep={len(kept)} skip={len(rows) - len(kept)} ("
          + " ".join(f"{s}={n}" for s, n in skip_counts.items() if n) + f") secret-flagged={len(flagged)}")
    areas = sorted({area_of(r[0]) for r in rows})
    width = max([len(x) for x in areas] + [4])
    print(f"{'area':<{width}}  " + " ".join(f"{k:>6}" for k in KINDS) + f" {'skip':>6}")
    for ar in areas:
        mine = [r for r in rows if area_of(r[0]) == ar]
        counts = [sum(1 for r in mine if r[1] == "keep" and r[2] == k) for k in KINDS]
        print(f"{ar:<{width}}  " + " ".join(f"{n:>6}" for n in counts) + f" {sum(1 for r in mine if r[1] == 'skip'):>6}")
    for path in flagged:
        print(f"secret-flagged: {path} (a secret shape matched: describe the file, never copy its values; if the value "
              "is real, tell the owner)")
    if a.files:
        for path, verdict, what, secret in rows:
            if verdict == "keep":
                url = pin_url(forge, rem[1], rem[2], commit, path) if rem else None
                print("\t".join(["keep", what, path, url or "-"] + (["secret"] if secret else [])))
            else:
                print("\t".join(["skip", what, path]))
    if a.pins:
        print_pins(entries, rows, repo, a.max_bytes)
    return 0


def cmd_url(a):
    repo = Path(a.repo).expanduser().resolve()
    commit = resolve(repo, a.rev)
    if commit is None:
        print(f"refused: {repo.name}: not a git repository, or {a.rev!r} names no commit")
        return 2
    rel = a.path.replace("\\", "/").lstrip("/")
    if git(repo, "cat-file", "-e", f"{commit}:{rel}").returncode:
        print(f"refused: {rel} is not in {commit[:12]}")
        return 2
    rem = remote_of(repo)
    url = pin_url(forge_of(rem[1], a.forge), rem[1], rem[2], commit, rel) if rem else None
    if not url:
        print("refused: no pinned url form: the repository has no GitHub or GitLab remote (or pass --forge)")
        return 2
    print(url)
    return 0


# ---- pins: the toolchain versions a repository asks for, read as text at the commit -----------------------------------

PIN_MAX_ROWS = 200  # rows one file adds before a note counts the rest
PIN_VALUE_MAX = 200  # characters of a value
PIN_LOCKS = re.compile(r"(?i)(?:^|/)(?:packages\.lock\.json|uv\.lock)$")  # pin files the survey leaves out as generated
PIN_TABLE = "pin files: kb/public/agents/codebase-mapping.csv"


class PinOut:
    """Where one pin file's reader puts its rows and notes."""

    def __init__(self, path, rows, notes):
        self.path, self.rows, self.notes, self.count = path, rows, notes, 0

    def add(self, pin, value):
        text = " ".join(str(value).split())
        if self.count == PIN_MAX_ROWS:
            self.note(f"more than {PIN_MAX_ROWS} pins: the rest are not listed")
        self.count += 1
        if self.count <= PIN_MAX_ROWS:
            self.rows.append((self.path, pin, text if len(text) <= PIN_VALUE_MAX else text[:PIN_VALUE_MAX - 3] + "..."))

    def note(self, message):
        self.notes.append((self.path, message))


def jsonc(text):
    """The value of JSON with comments and trailing commas (global.json, tsconfig.json, devcontainer.json): `//` and
    `/* */` comments and a comma before `}` or `]` are dropped outside strings by a scan, then json.loads reads it.
    Nothing is evaluated. ValueError when a comment or the JSON is malformed."""
    text = text.lstrip("﻿")
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise ValueError("unterminated /* comment")
            out.append(" ")
            i = j + 2
        elif c in "}]":
            k = len(out) - 1
            while k >= 0 and out[k].isspace():
                k -= 1
            if k >= 0 and out[k] == ",":
                del out[k]
            out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return json.loads("".join(out))


def toml_of(text):
    import tomllib
    return tomllib.loads(text)


def xml_of(data):
    """The root of an XML file with its namespaces dropped from tag names (a DOCTYPE's external entities are never
    fetched: expat does not load them)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(data)
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.rsplit("}", 1)[1]
    return root


def lines_of(text):
    """The non-blank lines of TEXT with `#` comments dropped and the ends trimmed."""
    return [ln.split("#", 1)[0].strip() for ln in text.splitlines() if ln.split("#", 1)[0].strip()]


def scalar(value):
    """A pin's value as text: a string as is, a table as `key=value` pairs (a table of tables as its keys)."""
    if isinstance(value, dict):
        return ", ".join(f"{k}={scalar(v) if not isinstance(v, dict) else '{...}'}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(scalar(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def pin_python_version(text, out):
    lines = lines_of(text)
    if lines:
        out.add("python-version", ", ".join(lines))
    else:
        out.note("empty: no version")


def pin_pyproject(text, out):
    v = toml_of(text).get("project", {})
    if isinstance(v, dict) and "requires-python" in v:
        out.add("requires-python", v["requires-python"])


def pin_uv_lock(text, out):
    doc = toml_of(text)
    for key in ("requires-python", "version", "revision"):
        if key in doc:
            out.add(f"uv.lock {key}", doc[key])


def pin_package_json(text, out):
    doc = json.loads(text.lstrip("﻿"))
    if not isinstance(doc, dict):
        raise ValueError("not an object")
    if isinstance(doc.get("engines"), dict):
        for k, v in doc["engines"].items():
            out.add(f"engines.{k}", scalar(v))
    dev = doc.get("devEngines")
    if isinstance(dev, dict):
        for field, spec in dev.items():
            for item in spec if isinstance(spec, list) else [spec]:
                if isinstance(item, dict):
                    on_fail = f" (onFail {item['onFail']})" if "onFail" in item else ""
                    out.add(f"devEngines.{field}", f"{item.get('name', '?')} {item.get('version', '')}".rstrip() + on_fail)
    if "packageManager" in doc:
        out.add("packageManager", doc["packageManager"])


def pin_nvmrc(text, out):
    lines = lines_of(text)
    if lines:
        out.add(".nvmrc", lines[0])
    else:
        out.note("empty: no version")


def pin_tsconfig(text, out):
    doc = jsonc(text)
    if isinstance(doc, dict) and "extends" in doc:
        for item in doc["extends"] if isinstance(doc["extends"], list) else [doc["extends"]]:
            out.add("extends", item)


def pin_go_mod(text, out):
    seen = set()
    for ln in lines_of(text.replace("//", "#")):
        parts = ln.split()
        if parts[0] in ("go", "toolchain") and parts[0] not in seen:
            seen.add(parts[0])
            if len(parts) > 1:
                out.add(parts[0], parts[1])
            else:
                out.note(f"`{parts[0]}` directive with no version")


def pin_go_work(text, out):
    pin_go_mod(text, out)
    block = False
    for ln in lines_of(text.replace("//", "#")):
        parts = ln.split()
        if block:
            if parts[0] == ")":
                block = False
            else:
                out.add("use", parts[0])
        elif parts[0] == "use" and len(parts) > 1 and parts[1] == "(":
            block = True
        elif parts[0] == "use" and len(parts) > 1:
            out.add("use", parts[1])
    if block:
        raise ValueError("`use (` block is not closed")


def pin_rust_toolchain(text, out, legacy=False):
    doc = None
    if not legacy or "[toolchain]" in text or re.search(r"(?m)^\s*channel\s*=", text):
        doc = toml_of(text)
    if doc is not None:
        t = doc.get("toolchain", {})
        for key in ("channel", "path"):
            if isinstance(t, dict) and key in t:
                out.add(key, t[key])
        return
    lines = lines_of(text)
    if lines:
        out.add("channel", lines[0])
    else:
        out.note("empty: no channel")


def pin_rust_toolchain_legacy(text, out):
    pin_rust_toolchain(text, out, legacy=True)


def pin_cargo(text, out):
    doc = toml_of(text)
    for scope, prefix in ((doc.get("package"), ""), ((doc.get("workspace") or {}).get("package"), "workspace.")):
        if isinstance(scope, dict):
            for key in ("rust-version", "edition"):
                if key in scope:
                    out.add(prefix + key, scalar(scope[key]))


def pin_pom(data, out):
    root = xml_of(data)
    props = [e for e in root if e.tag == "properties"]
    for block in props:
        for e in block:
            if e.tag in ("maven.compiler.release", "maven.compiler.source", "maven.compiler.target") and (e.text or "").strip():
                out.add(e.tag, e.text.strip())
    for parent in root.iter():
        if parent.tag == "configuration":
            for e in parent:
                if e.tag == "release" and (e.text or "").strip():
                    out.add("release", e.text.strip())


def pin_gradle_wrapper(text, out):
    for ln in text.splitlines():
        m = re.match(r"\s*(distributionUrl|distributionSha256Sum)\s*[=:]\s*(.*?)\s*$", ln)
        if m:
            value = m.group(2).replace("\\:", ":").replace("\\=", "=")
            if value:
                out.add(m.group(1), value)
            else:
                out.note(f"{m.group(1)} has no value")


def pin_gradle_build(text, out):
    m = re.search(r"languageVersion\s*(?:=|\.set\s*\()\s*JavaLanguageVersion\.of\(\s*[\"']?(\d+)", text)
    if m:
        out.add("java.toolchain.languageVersion", m.group(1))


def pin_global_json(text, out):
    doc = jsonc(text)
    sdk = doc.get("sdk") if isinstance(doc, dict) else None
    if isinstance(sdk, dict):
        for key in ("version", "rollForward", "allowPrerelease"):
            if key in sdk:
                out.add(f"sdk.{key}", scalar(sdk[key]))


DOTNET_PROPS = ("TargetFramework", "TargetFrameworks", "TargetFrameworkVersion", "LangVersion")


def pin_dotnet_project(data, out):
    root = xml_of(data)
    for e in root.iter():
        if e.tag in DOTNET_PROPS and (e.text or "").strip():
            out.add(e.tag, e.text.strip())


def pin_central_packages(data, out):
    root = xml_of(data)
    for e in root.iter():
        if e.tag in ("ManagePackageVersionsCentrally", "CentralPackageTransitivePinningEnabled") and (e.text or "").strip():
            out.add(e.tag, e.text.strip())
        elif e.tag in ("PackageVersion", "GlobalPackageReference"):
            name = e.get("Include") or e.get("Update")
            version = e.get("Version") or (e.findtext("Version") or "").strip()
            if name:
                out.add(f"{e.tag} {name}", version)


def pin_packages_lock(text, out):
    doc = json.loads(text.lstrip("﻿"))
    if not isinstance(doc, dict):
        raise ValueError("not an object")
    if "version" in doc:
        out.add("packages.lock.json version", doc["version"])
    deps = doc.get("dependencies")
    for tfm, pkgs in (deps.items() if isinstance(deps, dict) else []):
        for name, info in (pkgs.items() if isinstance(pkgs, dict) else []):
            if isinstance(info, dict) and info.get("type") == "Direct":
                out.add(f"locked {tfm}/{name}", info.get("resolved", ""))


def pin_requires(text, out):
    for m in re.finditer(r"(?im)^[ \t]*#requires\b[ \t]*(.*)$", text):
        value = re.split(r"\s#", m.group(1), maxsplit=1)[0].strip()
        if value:
            out.add("#Requires", value)
        else:
            out.note("#Requires with nothing after it")


PSD1_KEYS = ("PowerShellVersion", "CompatiblePSEditions", "RequiredModules")


def psd1_mask(text):
    """TEXT with its comments (`# ...`, `<# ... #>`) blanked, outside strings. ValueError when a string or a block
    comment is not closed. The file is only scanned: PowerShell never runs and Import-PowerShellDataFile is not used."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            j = i + 1
            while True:
                if j >= n:
                    raise ValueError("unterminated string")
                if c == '"' and text[j] == "`":
                    j += 2
                elif text[j] == c and text[j + 1:j + 2] == c:
                    j += 2
                elif text[j] == c:
                    break
                else:
                    j += 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("<#", i):
            j = text.find("#>", i + 2)
            if j < 0:
                raise ValueError("unterminated <# block comment")
            out.append(" ")
            i = j + 2
        elif c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def psd1_value(text, start):
    """The expression that starts at START (after `Key =`): to a `;`, a line end (unless the line ends in a comma) or an
    unmatched `}` outside strings and brackets. ValueError when a bracket or string is not closed."""
    depth, i, n = 0, start, len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            j = i + 1
            while j < n and not (text[j] == c and text[j + 1:j + 2] != c):
                j += 2 if text[j] == c or (c == '"' and text[j] == "`") else 1
            i = j + 1
            continue
        if c in "({[":
            depth += 1
        elif c in ")}]":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and (c == ";" or (c == "\n" and not text[start:i].rstrip().endswith(","))):
            break
        i += 1
    if depth:
        raise ValueError("unbalanced brackets")
    return text[start:i]


def pin_psd1(text, out):
    clean = psd1_mask(text)
    for m in re.finditer(r"(?i)(?:^|[;{\n])[ \t]*['\"]?(" + "|".join(PSD1_KEYS) + r")['\"]?[ \t]*=[ \t]*", clean):
        key = next(k for k in PSD1_KEYS if k.lower() == m.group(1).lower())
        out.add(key, psd1_value(clean, m.end()).strip())


def pin_devcontainer(text, out):
    doc = jsonc(text)
    if not isinstance(doc, dict):
        raise ValueError("not an object")
    if "image" in doc:
        out.add("image", doc["image"])
    features = doc.get("features")
    for fid, opts in (features.items() if isinstance(features, dict) else []):
        if isinstance(opts, dict):
            value = scalar(opts["version"]) if "version" in opts else ("options: " + ", ".join(opts) if opts else "")
        else:
            value = scalar(opts)
        out.add(f"feature {fid}", value)


def pin_devcontainer_lock(text, out):
    doc = jsonc(text)
    features = doc.get("features") if isinstance(doc, dict) else None
    for fid, info in (features.items() if isinstance(features, dict) else []):
        if isinstance(info, dict):
            out.add(f"locked feature {fid}", " ".join(str(info[k]) for k in ("version", "resolved") if k in info))


def pin_tool_versions(text, out):
    for ln in lines_of(text):
        parts = ln.split()
        if len(parts) > 1:
            out.add(parts[0], " ".join(parts[1:]))
        else:
            out.note(f"`{parts[0]}` has no version")


def pin_mise(text, out):
    tools = toml_of(text).get("tools")
    for name, spec in (tools.items() if isinstance(tools, dict) else []):
        out.add(f"tools.{name}", scalar(spec["version"] if isinstance(spec, dict) and "version" in spec else spec))


# (path pattern, reader, whether it reads bytes): the first pattern that matches a path picks its reader
PIN_READERS = [
    (re.compile(r"(?:^|/)\.python-version$"), pin_python_version, False),
    (re.compile(r"(?:^|/)pyproject\.toml$"), pin_pyproject, False),
    (re.compile(r"(?:^|/)uv\.lock$"), pin_uv_lock, False),
    (re.compile(r"(?:^|/)package\.json$"), pin_package_json, False),
    (re.compile(r"(?:^|/)\.nvmrc$"), pin_nvmrc, False),
    (re.compile(r"(?:^|/)tsconfig[^/]*\.json$"), pin_tsconfig, False),
    (re.compile(r"(?:^|/)go\.mod$"), pin_go_mod, False),
    (re.compile(r"(?:^|/)go\.work$"), pin_go_work, False),
    (re.compile(r"(?:^|/)rust-toolchain\.toml$"), pin_rust_toolchain, False),
    (re.compile(r"(?:^|/)rust-toolchain$"), pin_rust_toolchain_legacy, False),
    (re.compile(r"(?:^|/)Cargo\.toml$"), pin_cargo, False),
    (re.compile(r"(?:^|/)pom\.xml$"), pin_pom, True),
    (re.compile(r"(?:^|/)gradle-wrapper\.properties$"), pin_gradle_wrapper, False),
    (re.compile(r"(?:^|/)build\.gradle(?:\.kts)?$"), pin_gradle_build, False),
    (re.compile(r"(?:^|/)global\.json$"), pin_global_json, False),
    (re.compile(r"(?:^|/)Directory\.Packages\.props$"), pin_central_packages, True),
    (re.compile(r"(?i)(?:^|/)(?:Directory\.Build\.(?:props|targets)|[^/]+\.(?:cs|fs|vb)proj)$"), pin_dotnet_project, True),
    (re.compile(r"(?:^|/)packages\.lock\.json$"), pin_packages_lock, False),
    (re.compile(r"(?i)\.(?:ps1|psm1)$"), pin_requires, False),
    (re.compile(r"(?i)\.psd1$"), pin_psd1, False),
    (re.compile(r"(?:^|/)\.?devcontainer-lock\.json$"), pin_devcontainer_lock, False),
    (re.compile(r"(?:^|/)\.?devcontainer\.json$"), pin_devcontainer, False),
    (re.compile(r"(?:^|/)\.tool-versions$"), pin_tool_versions, False),
    (re.compile(r"(?:^|/)(?:\.?mise(?:\.[A-Za-z0-9_-]+)?\.toml|\.config/mise(?:/config)?\.toml|\.?mise/config\.toml)$"),
     pin_mise, False),
]


def pins(entries, rows, read, max_bytes=1_000_000):
    """([(file, pin, value)], [(file, note)]): the pins of every pin file of the survey, read as text with tomllib,
    json (comments and trailing commas scanned out), xml.etree and line scans; no file is run, imported or evaluated
    (a .psd1 is scanned, never handed to PowerShell).

    ENTRIES is `tree`'s result and ROWS `classify`'s: the files the survey KEEPS, plus `packages.lock.json` and
    `uv.lock`, which it leaves out as generated by name but which are pin files (a file left out for any other
    reason, and a lock file over MAX_BYTES, is never read). READ(oids) returns {oid: bytes}. A file that does not
    parse gives a note and no rows; a reader's bug does too. Rows come in path order."""
    kept = {r[0] for r in rows if r[1] == "keep"}
    generated = {r[0] for r in rows if r[1] == "skip" and r[2] == "generated"}
    todo = []
    for path, kind, oid, size in entries:
        if kind != "blob":
            continue
        if path in kept or (path in generated and PIN_LOCKS.search(path) and size <= max_bytes):
            for rx, reader, binary in PIN_READERS:
                if rx.search(path):
                    todo.append((path, oid, reader, binary))
                    break
    data = read(sorted({oid for _, oid, _, _ in todo}))
    out_rows, notes = [], []
    for path, oid, reader, binary in sorted(todo, key=lambda t: t[0]):
        if oid not in data:
            notes.append((path, "not read: the blob is missing"))
            continue
        raw = data[oid]
        out, before = PinOut(path, out_rows, notes), len(out_rows)
        try:
            reader(raw if binary else raw.decode("utf-8-sig", "replace"), out)
        except Exception as e:  # noqa: BLE001 - a malformed or odd file must give a note, never lose the other files' pins
            del out_rows[before:]
            detail = " ".join(str(e).split())[:120]
            notes.append((path, f"not read: {type(e).__name__}" + (f": {detail}" if detail else "")))
    return out_rows, notes


def print_pins(entries, rows, repo, max_bytes):
    out_rows, notes = pins(entries, rows, lambda oids: contents(repo, oids), max_bytes)
    print(f"pins: {len(out_rows)} in {len({r[0] for r in out_rows})} files ({PIN_TABLE}), read at the commit, never run")
    for path, pin, value in out_rows:
        print("\t".join(["pin", path, pin, value]))
    for path, message in notes:
        print(f"note: pins: {path}: {message}")


# ---- map: read-only toolchain mapping in a scratch worktree ----------------------------------------------------------

MAP_FORMAT = 1
INGEST_CACHE = Path(kbcommon.HOME) / "_cache" / "ingest"
MAP_TIMEOUT = 60  # seconds per mapper command
MAP_MAX_FILES = 2000  # files one per-file mapper maps before it stops with a note
MAP_MAX_PROJECTS = 50  # projects one per-project mapper (.NET, npm, tsc) maps before it stops with a note
MAP_MAX_OUTPUT = 64 * 1024 * 1024  # bytes of a command's output that are parsed
NOTE_LIMIT = 20  # notes one language keeps before it counts the rest
# what makes a mapper command's environment offline: proxies that refuse, the tools' own offline switches (RUSTUP_AUTO_INSTALL=0:
# a rustup cargo proxy never installs the absent toolchain a rust-toolchain.toml names; MSBUILDDISABLENUGETSDKRESOLVER=1:
# MSBuild's NuGet SDK resolver resolves no SDK, so a versioned Sdk="Name/1.2.3" or a global.json msbuild-sdks entry
# queries no feed and imports no package. That variable is read by the resolver's current implementation, not
# documented on Microsoft Learn: kb agents/codebase-mapping, CODE)
NETWORK_OFF = {
    "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "ALL_PROXY": "http://127.0.0.1:9",
    "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "all_proxy": "http://127.0.0.1:9",
    "NO_PROXY": "", "no_proxy": "",
    "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOFLAGS": "-mod=readonly",
    "CARGO_NET_OFFLINE": "true", "RUSTUP_AUTO_INSTALL": "0", "npm_config_offline": "true", "npm_config_update_notifier": "false",
    "npm_config_ignore_scripts": "true", "COREPACK_ENABLE_NETWORK": "0", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
    "DOTNET_NOLOGO": "1", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "MSBUILDDISABLENODEREUSE": "1",
    "MSBUILDDISABLENUGETSDKRESOLVER": "1", "PIP_NO_INDEX": "1", "GIT_TERMINAL_PROMPT": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}
SECRET_ENV = re.compile(r"(?i)token|secret|passw|credential|api[_-]?key|private[_-]?key|auth|cookie|session")
PROXY_ENV = re.compile(r"(?i)^(?:https?|all|ftp|no)_proxy$")


def under_worktree(path, root):
    """True when the absolute PATH is ROOT or lies under it: as given or resolved, compared case-normalised (the
    spellings MapCtx masks), or through an existing folder on its way that is ROOT itself (a case-insensitive file
    system, a Windows short name, a second link to it). A path that cannot be resolved counts as inside."""
    try:
        real = Path(path).resolve()
        paths = {os.path.normcase(str(p)) for p in (Path(path), real)}
        tops = {os.path.normcase(str(p)) for p in (Path(root), Path(root).resolve())}
        top = os.stat(root)
    except (OSError, RuntimeError, ValueError):
        return True
    if any(p == t or p.startswith(t.rstrip("\\/") + os.sep) for p in paths for t in tops):
        return True
    for folder in (real, *real.parents):
        try:
            if os.path.samestat(os.stat(folder), top):
                return True
        except (OSError, ValueError):
            continue
    return False


def scrub_env(base=None, windows=None, root=None, repo=None):
    """The environment of a mapper command: the caller's, without credentials and proxies, plus NETWORK_OFF. On
    Windows (WINDOWS, by default os.name) it also sets NoDefaultCurrentDirectoryInExePath: cmd.exe, which runs an npm
    cmd-shim (tsc.cmd, npm.cmd), otherwise looks for a bare `node` in the working folder before PATH, and that folder
    is the repository's (https://learn.microsoft.com/windows/win32/api/processenv/nf-processenv-needcurrentdirectoryforexepathw:
    the variable's existence, not its value, drops the current directory from cmd.exe's search).
    PATH keeps only its absolute entries outside the worktree ROOT and outside the source repository REPO (its own
    clone, which the operator's PATH can name too: a `node_modules/.bin` there, a direnv-added bin folder): a child
    resolves a relative entry (`.`, `node_modules/.bin`, an empty one) against its own working folder, the repository's,
    so `#!/usr/bin/env node` or a rustup proxy there would run the repository's program."""
    env = {k: v for k, v in (os.environ if base is None else base).items()
           if not SECRET_ENV.search(k) and not PROXY_ENV.match(k)}
    env.update(NETWORK_OFF)
    for k in [k for k in env if k.upper() == "PATH"]:
        env[k] = os.pathsep.join(e for e in env[k].split(os.pathsep) if e and Path(e).is_absolute()
                                 and not any(top is not None and under_worktree(e, top) for top in (root, repo)))
    if os.name == "nt" if windows is None else windows:
        env["NoDefaultCurrentDirectoryInExePath"] = "1"
    return env


def which(tool, path):
    """The absolute path of the program TOOL in the folders of the PATH string, in order, or None. Only those folders:
    on Windows shutil.which searches this process's working folder first unless NoDefaultCurrentDirectoryInExePath is
    in this process's own environment (scrub_env sets it in the child's only), and that folder can be the repository
    being mapped (`map .`, the source clone in plugin mode). Each entry is searched as a folder of its own, which
    shutil.which never prefixes with the working folder; an empty entry (the working folder on POSIX) is skipped. A TOOL
    with a folder part is taken only when that part is absolute."""
    if os.path.dirname(tool):
        exe = shutil.which(tool) if os.path.isabs(tool) else None
        return os.path.abspath(exe) if exe else None
    for entry in (path or "").split(os.pathsep):
        if entry:
            exe = shutil.which(os.path.join(entry, tool)) or _pathext(os.path.join(entry, tool))
            if exe is not None:
                return os.path.abspath(exe)  # a relative entry is relative to this process, never to the child's CWD
    return None


def _pathext(base):
    """BASE plus the first PATHEXT extension that names a file, on Windows; else None. shutil.which applies PATHEXT to
    a name with a folder part only since Python 3.12, and the floor is 3.11."""
    if os.name != "nt":
        return None
    for ext in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep):
        if ext and os.path.isfile(base + ext):
            return base + ext
    return None


def tool_exe(tool, env, root):
    """(the program TOOL is on ENV's PATH, whether it lies inside ROOT): None when it is not found. A program that is
    inside the worktree is the repository's own (a `node_modules/.bin` entry on PATH), and a mapper never runs it."""
    exe = which(tool, env.get("PATH"))
    if exe is None:
        return None, False
    return exe, under_worktree(exe, root)


class Run(NamedTuple):
    rc: int
    out: bytes
    err: bytes
    timed_out: bool = False
    missing: bool = False


def kill_tree(proc):
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    else:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    try:
        proc.kill()
    except OSError:
        pass


def run_tool(args, cwd, env, timeout):
    """Run an argument list (never a shell) in CWD with ENV and a TIMEOUT in seconds; the process group dies with it.
    A program not found on ENV's PATH is `missing`, not an error. An interrupt (any BaseException while it waits)
    kills the process group too, then propagates."""
    exe = which(args[0], env.get("PATH"))  # never this process's working folder, whatever the platform
    if exe is None:
        return Run(127, b"", b"", missing=True)
    kw = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    try:
        proc = subprocess.Popen([exe, *args[1:]], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    except OSError as e:
        return Run(126, b"", str(e).encode("utf-8", "replace"), missing=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        return Run(proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # a grandchild still holds the pipes
            out = err = b""
            for pipe in (proc.stdout, proc.stderr):
                pipe.close()
        return Run(-1, out, err, timed_out=True)
    except BaseException:  # an interrupt: the caller removes the worktree next, never under a live process group
        kill_tree(proc)
        for pipe in (proc.stdout, proc.stderr):
            pipe.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise


class MapCtx:
    """What a mapper sees: the worktree ROOT, `run`/`json` for commands, `add_*` and `note` for results."""

    def __init__(self, root, env, timeout, language, links=()):
        self.root, self.env, self.timeout, self.language = Path(root), env, timeout, language
        self.links = frozenset(links)  # paths git stores as symbolic links, however the checkout wrote them
        self.packages, self.imports, self.entry_points, self.notes = [], [], [], []
        self._dropped = 0
        spellings = {str(self.root), self.root.as_posix()}
        try:
            real = self.root.resolve()
            spellings |= {str(real), real.as_posix()}
        except OSError:
            pass
        self._root_spellings = sorted(spellings, key=len, reverse=True)  # on Windows a root has several

    def note(self, text):
        if len(self.notes) >= NOTE_LIMIT:
            self._dropped += 1
        else:
            for s in self._root_spellings:
                text = text.replace(s, "<worktree>")
            self.notes.append(text)

    def finish(self):
        if self._dropped:
            self.notes.append(f"{self._dropped} more notes left out")

    def add_package(self, name, path, **extra):
        self.packages.append({"language": self.language, "name": name, "path": path, **extra})

    def add_imports(self, path, modules):
        if modules:
            self.imports.append({"language": self.language, "path": path, "imports": sorted(set(modules))})

    def add_entry_point(self, path, kind, name=None):
        self.entry_points.append({"language": self.language, "path": path, "kind": kind, **({"name": name} if name else {})})

    def readable(self, rel):
        """The file REL of the worktree, or None (with a note) when it is a symbolic link or not a file. A link counts
        as one from git's mode too: with core.symlinks=false (Windows) git checks it out as a plain file."""
        p = self.root / rel
        if rel in self.links or p.is_symlink() or not p.is_file():
            self.note(f"{rel}: not a regular file in the worktree (a symbolic link?), not read")
            return None
        return p

    def run(self, args, label=None, timeout=None, cwd=None):
        """A Run of ARGS in the worktree, or in its directory CWD (a `/` path relative to the root: a project's own
        directory, where the SDK's global.json and the nearest tsconfig.json apply); a missing program, a timeout and
        a non-zero exit each add a note."""
        where = self.root if cwd in (None, "", ".") else self.root / cwd
        r = run_tool(list(args), where, self.env, timeout or self.timeout)
        what = label or " ".join(str(a) for a in args)[:100]
        if r.missing:
            self.note(f"{what}: program not found on PATH")
        elif r.timed_out:
            self.note(f"{what}: timed out after {timeout or self.timeout}s")
        elif r.rc != 0:
            first = (r.err.decode("utf-8", "replace").strip().splitlines() or [""])[0][:200]
            self.note(f"{what}: exit {r.rc}" + (f": {first}" if first else ""))
        return r

    def output(self, args, what, cwd=None, nonzero_ok=False):
        """The text a command prints, or None (with a note) when it failed, was not found or printed too much.
        NONZERO_OK keeps the output of a command that exited non-zero (still with its note): `npm ls` prints its
        tree, then exits 1 for the problems it lists."""
        r = self.run(args, what, cwd=cwd)
        if r.missing or r.timed_out or (r.rc != 0 and not (nonzero_ok and r.out.strip())):
            return None
        if len(r.out) > MAP_MAX_OUTPUT:
            self.note(f"{what}: output over {MAP_MAX_OUTPUT} bytes, not parsed")
            return None
        return r.out.decode("utf-8", "replace")

    def json(self, args, label=None, cwd=None, nonzero_ok=False):
        """The parsed JSON a command prints, or None (with a note)."""
        what = label or " ".join(str(a) for a in args)[:100]
        text = self.output(args, what, cwd=cwd, nonzero_ok=nonzero_ok)
        if text is None:
            return None
        try:
            return json.loads(text)
        except ValueError as e:
            self.note(f"{what}: output is not JSON ({str(e)[:80]})")
            return None

    def json_stream(self, args, label=None):
        """The list of JSON values a command prints one after another (`go list -json`: objects with nothing between
        them, not an array), or None (with a note) when the output is not such a stream."""
        what = label or " ".join(str(a) for a in args)[:100]
        text = self.output(args, what)
        if text is None:
            return None
        dec, pos, values = json.JSONDecoder(), 0, []
        try:
            while True:
                while pos < len(text) and text[pos].isspace():
                    pos += 1
                if pos >= len(text):
                    return values
                value, pos = dec.raw_decode(text, pos)
                values.append(value)
        except ValueError as e:
            self.note(f"{what}: output is not a JSON stream ({str(e)[:80]})")
            return None

    def rel(self, path):
        """PATH (absolute in the worktree, in either separator) as a relative `/` path (`.` for the root), or None
        when it lies outside the worktree."""
        if not isinstance(path, str) or not path:
            return None
        for base in (self.root, self.root.resolve()):
            try:
                return Path(path).relative_to(base).as_posix()
            except ValueError:
                continue
        return None


class Mapper:
    """One language's mapper. `name` is what the map records; `tool` the program looked up on PATH; `files(rows)` the
    kept (path, kind) pairs it maps (none: the language is absent and the mapper does not run); `map(ctx, files)` runs
    only read-only commands, through ctx, and records packages, imports and entry points. `preflight(ctx, files)` reads
    files only, before any command of the language runs (the version probe included): a note declines the language."""
    language = ""
    name = ""
    tool = ""
    version_args = ("--version",)

    def files(self, rows):
        return []

    def preflight(self, ctx, files):
        return None

    def map(self, ctx, files):
        raise NotImplementedError


IMPORT_BLOCK = re.compile(r"^(\s*)(Import|ImportFrom)\($")
PY_ALIAS = re.compile(r"\bname='([^']*)'")
PY_MODULE = re.compile(r"^\s*module='([^']*)'", re.M)
PY_LEVEL = re.compile(r"\blevel=(\d+)")


def ast_imports_and_main(dump):
    """(imported module names, has an `if __name__ == "__main__"` guard) from the text of `python -m ast -i 1 FILE`.
    Every node starts a line and a string is one line inside `value=...`, so a string cannot pass for a node."""
    lines = dump.splitlines()
    mods, guard = set(), False
    for i, line in enumerate(lines):
        m = IMPORT_BLOCK.match(line)
        if not m and line.strip() != "If(":
            continue
        indent = len(line) - len(line.lstrip())
        j = i + 1
        while j < len(lines) and len(lines[j]) - len(lines[j].lstrip()) > indent:
            j += 1
        block = "\n".join(lines[i + 1:j])
        if m:
            names = PY_ALIAS.findall(block)
            mod = PY_MODULE.search(block)
            lv = PY_LEVEL.search(block)
            dots = "." * (int(lv.group(1)) if lv else 0)
            if m.group(2) == "Import":
                mods.update(names)
            elif mod and mod.group(1):
                mods.add(dots + mod.group(1))
            else:  # from . import x: the names are the modules
                mods.update(dots + n for n in names)
        elif not guard:
            head = block.split("body=[", 1)[0]
            guard = "Name(id='__name__'" in head and "value='__main__'" in head
    return mods, guard


class PythonMapper(Mapper):
    """`python -m ast` per kept .py file, in isolated mode (no working directory on sys.path, so a file named ast.py in
    the repository is never run). It reads source only and writes nothing (`-B`, PYTHONDONTWRITEBYTECODE)."""
    language = "python"
    name = "python"
    tool = sys.executable
    version_args = ("--version",)

    def files(self, rows):
        return sorted(path for path, _kind in rows if path.endswith(".py"))

    def map(self, ctx, files):
        have = set(files)
        for rel in files:  # a package is a directory with __init__.py; its name runs from the first directory without one
            if rel.rsplit("/", 1)[-1] == "__init__.py" and "/" in rel:
                pkg = rel.rsplit("/", 1)[0]
                parts = pkg.split("/")
                top = len(parts)
                while top > 1 and "/".join(parts[:top - 1]) + "/__init__.py" in have:
                    top -= 1
                ctx.add_package(".".join(parts[top - 1:]), pkg)
        for n, rel in enumerate(files):
            if n >= MAP_MAX_FILES:
                ctx.note(f"stopped after {MAP_MAX_FILES} files ({len(files) - n} not mapped)")
                break
            if ctx.readable(rel) is None:
                continue
            r = ctx.run([self.tool, "-I", "-B", "-m", "ast", "-i", "1", "./" + rel], label=f"python -m ast {rel}")
            if r.missing or r.timed_out or r.rc != 0:
                continue
            mods, guard = ast_imports_and_main(r.out.decode("utf-8", "replace"))
            ctx.add_imports(rel, mods)
            if guard:
                ctx.add_entry_point(rel, "main-guard")
            if rel.rsplit("/", 1)[-1] == "__main__.py":
                ctx.add_entry_point(rel, "module-main")
        self.pyproject_scripts(ctx)

    def pyproject_scripts(self, ctx):
        p = ctx.root / "pyproject.toml"
        if "pyproject.toml" in ctx.links or not p.is_file() or p.is_symlink():
            return
        try:
            import tomllib
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except ImportError:
            ctx.note("pyproject.toml scripts not read: this Python has no tomllib")
            return
        except (OSError, ValueError) as e:
            ctx.note(f"pyproject.toml not read: {str(e)[:100]}")
            return
        proj = data.get("project") if isinstance(data.get("project"), dict) else {}
        for table, kind in (("scripts", "console-script"), ("gui-scripts", "gui-script")):
            scripts = proj.get(table)
            for script, target in sorted(scripts.items()) if isinstance(scripts, dict) else ():
                ctx.add_entry_point("pyproject.toml", kind, f"{script} = {target}")


def strings(value):
    """The strings of a JSON list, else an empty list: a tool's field of another shape adds nothing."""
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


class GoMapper(Mapper):
    """`go mod edit -json` (the module path, the go line, the requirements) and `go list -e -json ./...` (each package:
    import path, directory, imports, and `main` as an entry point) at the worktree root. `GOTOOLCHAIN=local` and
    `GOFLAGS=-mod=readonly` come from the mapper environment, so no toolchain or module is downloaded and go.mod is
    not rewritten. Both commands read source; neither compiles or runs it."""
    language = "go"
    name = "go"
    tool = "go"
    version_args = ("version",)

    def files(self, rows):
        return sorted(path for path, _kind in rows
                      if path.endswith(".go") or path.rsplit("/", 1)[-1] in ("go.mod", "go.work"))

    def map(self, ctx, files):
        have = set(files)
        if "go.mod" not in have and "go.work" not in have:
            ctx.note("no go.mod or go.work at the repository root: no Go module mapped")
            return
        nested = [f for f in files if f.endswith("/go.mod")]
        if nested:
            ctx.note(f"{len(nested)} nested go.mod file(s) not mapped (`go list ./...` stays in the root module)")
        if "go.mod" in have:
            mod = ctx.json(["go", "mod", "edit", "-json"], label="go mod edit -json")
            if isinstance(mod, dict):
                self.module(ctx, mod)
        for pkg in ctx.json_stream(["go", "list", "-e", "-json", "./..."], label="go list -e -json ./...") or ():
            if isinstance(pkg, dict):
                self.package(ctx, pkg)
            else:
                ctx.note("go list -e -json ./...: a value that is not an object, left out")

    def module(self, ctx, mod):
        module = mod.get("Module") if isinstance(mod.get("Module"), dict) else {}
        path = module.get("Path")
        if not isinstance(path, str) or not path:
            ctx.note("go mod edit -json: no module path")
            return
        extra = {k.lower(): mod[k] for k in ("Go", "Toolchain") if isinstance(mod.get(k), str)}
        ctx.add_package(path, ".", kind="module", **extra)
        ctx.add_imports("go.mod", [r["Path"] for r in mod.get("Require") or ()
                                   if isinstance(r, dict) and isinstance(r.get("Path"), str)])

    def package(self, ctx, pkg):
        ip = pkg.get("ImportPath")
        if not isinstance(ip, str) or not ip:
            return
        err = pkg.get("Error")
        if isinstance(err, dict) and err.get("Err"):
            ctx.note(f"{ip}: {(str(err['Err']).splitlines() or [''])[0][:150]}")
        rel = ctx.rel(pkg.get("Dir"))
        if rel is None:
            ctx.note(f"{ip}: directory outside the worktree, not mapped")
            return
        mod = pkg.get("Module")
        extra = {"module": mod["Path"]} if isinstance(mod, dict) and isinstance(mod.get("Path"), str) else {}
        ctx.add_package(ip, rel, **extra)
        ctx.add_imports(rel, strings(pkg.get("Imports")))
        if pkg.get("Name") == "main":
            ctx.add_entry_point(rel, "main", ip)


class CargoMapper(Mapper):
    """`cargo metadata --format-version 1 --no-deps --offline --locked` at the worktree root: the workspace members
    (name, directory), their dependencies as imports and their `bin` targets as entry points. `--no-deps` fetches
    nothing and `--locked` refuses to change Cargo.lock; the command reads manifests and builds nothing, so no build
    script runs. A repository cargo configuration that names a program (see `config_program`) is not run under."""
    language = "rust"
    name = "cargo"
    tool = "cargo"

    def files(self, rows):
        return sorted(path for path, _kind in rows if path.endswith(".rs") or path.rsplit("/", 1)[-1] == "Cargo.toml")

    def preflight(self, ctx, files):
        """A note when a toolchain file at the worktree root (where every cargo command runs) sets `path`: a rustup
        proxy then runs the toolchain in the directory it names, which would be the repository's own programs
        (https://rust-lang.github.io/rustup/overrides.html, "The toolchain file"). The legacy `rust-toolchain` is TOML
        or a bare toolchain name; one that is neither, a `rust-toolchain.toml` that is not TOML, and a toolchain file
        that is not a regular file or cannot be read decline too."""
        for rel in ("rust-toolchain", "rust-toolchain.toml"):
            path = ctx.root / rel
            if rel not in ctx.links and not path.is_symlink() and not path.exists():
                continue
            why = None
            p = ctx.readable(rel)
            if p is None:
                why = "not a regular file"
            else:
                try:
                    text = p.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as e:
                    why = f"not read ({type(e).__name__})"
                else:
                    try:
                        doc = toml_of(text)
                    except (ValueError, RecursionError) as e:
                        lines = lines_of(text)
                        bare = (rel == "rust-toolchain" and len(lines) == 1
                                and not re.search(r"[\[=/\\]", lines[0]))  # a name, never a path
                        if not bare:
                            why = f"not read ({type(e).__name__})"
                    else:
                        t = doc.get("toolchain")
                        if isinstance(t, dict) and "path" in t:
                            why = "sets path (a toolchain from the directory it names)"
            if why:
                return f"{rel}: {why}, Cargo not mapped and no cargo command run"
        for rel in (".cargo/config.toml", ".cargo/config"):
            why = self.config_program(ctx, rel)
            if why:
                return f"{rel}: {why}, Cargo not mapped and no cargo command run"
        return None

    def config_program(self, ctx, rel):
        """Why the cargo configuration file REL at the worktree root (cargo reads `.cargo/config.toml`, and the
        deprecated `.cargo/config`, from the working directory and its parents) is not safe to run cargo under, or
        None. Whether `cargo metadata --no-deps` starts `rustc` or one of these programs is not settled in the kb
        (`_gaps.md`), so the command is not run under a file that names one: `build.rustc`, `build.rustc-wrapper`,
        `build.rustc-workspace-wrapper`, `build.rustdoc`, a `target.<triple>.runner` or `.linker`, or an `include` of
        another file (not followed). A file that is not a regular file, cannot be read or is not TOML declines too."""
        path = ctx.root / rel
        if rel not in ctx.links and not path.is_symlink() and not path.exists():
            return None
        p = ctx.readable(rel)
        if p is None:
            return "not a regular file"
        try:
            doc = toml_of(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError, RecursionError) as e:
            return f"not read ({type(e).__name__})"
        found = []
        build = doc.get("build")
        if isinstance(build, dict):
            found += [f"build.{k}" for k in ("rustc", "rustc-wrapper", "rustc-workspace-wrapper", "rustdoc")
                      if k in build]
        target = doc.get("target")
        if isinstance(target, dict):
            for triple, table in sorted(target.items()):
                if isinstance(table, dict):
                    found += [f"target.{triple}.{k}" for k in ("runner", "linker") if k in table]
        if "include" in doc:
            found.append("include")
        if found:
            return f"names {', '.join(found)} (a program the repository chooses)"
        return None

    def map(self, ctx, files):
        if "Cargo.toml" not in files:
            ctx.note("no Cargo.toml at the repository root: no Cargo workspace mapped")
            return
        meta = ctx.json(["cargo", "metadata", "--format-version", "1", "--no-deps", "--offline", "--locked"],
                        label="cargo metadata")
        if not isinstance(meta, dict):
            return
        seen = set()
        for pkg in meta.get("packages") or ():
            if isinstance(pkg, dict) and isinstance(pkg.get("name"), str):
                manifest = self.member(ctx, pkg)
                if manifest:
                    seen.add(manifest)
        outside = [f for f in files if f.endswith("/Cargo.toml") and f not in seen]
        if outside:
            ctx.note(f"{len(outside)} Cargo.toml file(s) outside the root workspace not mapped")

    def member(self, ctx, pkg):
        name = pkg["name"]
        manifest = ctx.rel(pkg.get("manifest_path"))
        if manifest is None:
            ctx.note(f"{name}: manifest outside the worktree, not mapped")
            return None
        extra = {"version": pkg["version"]} if isinstance(pkg.get("version"), str) else {}
        ctx.add_package(name, manifest.rsplit("/", 1)[0] if "/" in manifest else ".", **extra)
        ctx.add_imports(manifest, [d["name"] for d in pkg.get("dependencies") or ()
                                   if isinstance(d, dict) and isinstance(d.get("name"), str)])
        for target in pkg.get("targets") or ():
            if isinstance(target, dict) and "bin" in strings(target.get("kind")):
                src = ctx.rel(target.get("src_path"))
                if src is not None:
                    tname = target.get("name")
                    ctx.add_entry_point(src, "bin", tname if isinstance(tname, str) else None)
        return manifest


def folder_of(path):
    """The directory of a `/` path in the worktree, `.` for the root."""
    return path.rsplit("/", 1)[0] if "/" in path else "."


def within(folder, name):
    """FOLDER/NAME as a `/` path (NAME alone in the root)."""
    return name if folder == "." else f"{folder}/{name}"


def capped(ctx, items, what):
    """The first MAP_MAX_PROJECTS of ITEMS; a note counts the rest."""
    if len(items) > MAP_MAX_PROJECTS:
        ctx.note(f"stopped after {MAP_MAX_PROJECTS} {what} ({len(items) - MAP_MAX_PROJECTS} not mapped)")
    return items[:MAP_MAX_PROJECTS]


PROJECT_EXTS = (".csproj", ".fsproj", ".vbproj")
# The shapes an evaluated .NET value must have to go into the map. Evaluation expands property functions, so a
# repository can set a property to a file's text or an environment variable ($([System.IO.File]::ReadAllText(..)),
# $([System.Environment]::GetEnvironmentVariable(..))); only a value of the expected shape is kept.
NUGET_VERSION = r"(?:\d|\*)[0-9A-Za-z.*+-]*"  # 1.0.0-beta.1+meta, 8.*, *
DOTNET_SHAPES = {
    "TargetFrameworkMoniker": re.compile(r"\.?[A-Za-z][A-Za-z0-9.+-]*(?:,Version=v\d+(?:\.\d+){0,3})?"
                                         r"(?:,Profile=[A-Za-z0-9.+-]+)?"),  # .NETCoreApp,Version=v8.0, net8.0-windows
    "LangVersion": re.compile(r"(?i)latest(?:major|minor)?|preview|default|iso-[12]|\d{1,2}(?:\.\d{1,2})?"),
    "PackageReference Identity": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}"),  # NuGet: at most 100 characters
    "PackageReference Version": re.compile(rf"{NUGET_VERSION}|[\[(] ?(?:{NUGET_VERSION})? ?(?:, ?(?:{NUGET_VERSION})? ?)?[\])]"),
    "ProjectReference": re.compile(r"(?:[\w.()+ -]+[\\/])*[\w.()+ -]+\.\w*proj"),  # relative: no drive, no root
}
DOTNET_MAX_VALUE = 260


class DotnetMapper(Mapper):
    """Per kept .csproj, .fsproj or .vbproj, run in the project's own directory (the SDK the nearest global.json names
    is the one that runs), the one command:
      `dotnet msbuild -noAutoResponse PROJECT -getProperty:TargetFrameworkMoniker,LangVersion
       -getItem:PackageReference,ProjectReference`
    Without `-target` MSBuild only evaluates the project (MSBuild 17.8+; kb agents/codebase-mapping): no target and
    no task runs, nothing is built or restored, and `-restore` and `-target` are never passed. Evaluation still reads
    every import the project pulls in (Directory.Build.props, the SDK's .props and .targets, NuGet's obj/*.g.props when
    present) and expands property functions, which are calls to .NET methods (live docs, Microsoft Learn, "Property
    functions" and "How MSBuild builds projects": evaluation runs no task, and targets are only created in memory). A
    project whose Sdk names a NuGet version (`Sdk="Name/1.0"`), or a global.json msbuild-sdks entry, would be resolved
    from a feed by the NuGet SDK resolver; the mapper environment switches that resolver off
    (MSBUILDDISABLENUGETSDKRESOLVER, NETWORK_OFF) and refuses proxies besides, so the missing SDK fails the evaluation
    as a note. The packages are the evaluated PackageReference items with the version
    each asks for, not a resolved one: `dotnet package list` is not run, because once ProjectAssetsFile names an
    existing file (a committed obj/project.assets.json) it builds NuGet's collection targets, and with them the
    project's InitialTargets and any repository target hooked to them (kb agents/codebase-mapping). Each evaluated
    value is kept only when it has its shape (DOTNET_SHAPES), else left out with a note."""
    language = "dotnet"
    name = "dotnet"
    tool = "dotnet"

    def files(self, rows):
        return sorted(path for path, _kind in rows
                      if path.endswith(PROJECT_EXTS + (".cs", ".fs", ".vb", ".sln", ".slnx"))
                      or path.rsplit("/", 1)[-1] == "global.json")

    def preflight(self, ctx, files):
        """A note when a global.json in a project's folder or above it (to the worktree root, where the version probe
        runs) sets sdk.paths: the .NET 10+ host then loads an SDK from the folders it names, relative to the global.json,
        which would be the repository's own code (https://learn.microsoft.com/dotnet/core/tools/global-json, `paths`).
        One that is not a regular file (a symbolic link on disk or in git's mode, as MapCtx.readable) or cannot be read
        declines too."""
        folders = {"."}
        for proj in files:
            if proj.endswith(PROJECT_EXTS):
                folder = folder_of(proj)
                while folder != ".":
                    folders.add(folder)
                    folder = folder_of(folder)
        for folder in sorted(folders):
            rel = within(folder, "global.json")
            path = ctx.root / rel
            link = rel in ctx.links or path.is_symlink()  # git's mode too: core.symlinks=false writes a plain file
            if not link and not path.exists():
                continue
            why = None
            if link or not path.is_file():
                why = "not a regular file"
            else:
                try:
                    doc = jsonc(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, ValueError, RecursionError) as e:
                    why = f"not read ({type(e).__name__})"
                else:
                    sdk = doc.get("sdk") if isinstance(doc, dict) else None
                    if isinstance(sdk, dict) and "paths" in sdk:
                        why = "sets sdk.paths (an SDK from folders it names)"
            if why:
                return f"{rel}: {why}, .NET not mapped and no dotnet command run"
        return None

    def map(self, ctx, files):
        projects = [f for f in files if f.endswith(PROJECT_EXTS)]
        if not projects:
            ctx.note("no .csproj, .fsproj or .vbproj file: no .NET project mapped")
            return
        for proj in capped(ctx, projects, "projects"):
            self.project(ctx, proj)

    def project(self, ctx, proj):
        if ctx.readable(proj) is None:
            return
        folder, base = folder_of(proj), proj.rsplit("/", 1)[-1]
        # -noAutoResponse: MSBuild reads a Directory.Build.rsp from the project's folder or any folder above it by
        # itself, so the repository could add -target, -restore or -logger; only this switch turns that off
        # (https://learn.microsoft.com/visualstudio/msbuild/msbuild-response-files, "Disabling response files")
        ev = ctx.json(["dotnet", "msbuild", "-noAutoResponse", base, "-getProperty:TargetFrameworkMoniker,LangVersion",
                       "-getItem:PackageReference,ProjectReference"], label=f"dotnet msbuild {proj}", cwd=folder)
        props = ev.get("Properties") if isinstance(ev, dict) and isinstance(ev.get("Properties"), dict) else {}
        items = ev.get("Items") if isinstance(ev, dict) and isinstance(ev.get("Items"), dict) else {}
        extra = {"project": proj, "kind": "project"}
        for key, field in (("TargetFrameworkMoniker", "framework"), ("LangVersion", "langversion")):
            if self.shaped(ctx, proj, key, props.get(key)):
                extra[field] = props[key]
        refs = []
        for item in items.get("ProjectReference") or ():
            ident = item.get("Identity") if isinstance(item, dict) else None
            if not self.shaped(ctx, proj, "ProjectReference", ident):
                continue
            target = posixpath.normpath(posixpath.join("" if folder == "." else folder, ident.replace("\\", "/")))
            if target == ".." or target.startswith("../"):
                ctx.note(f"{proj}: a project reference outside the worktree, left out")
            else:
                refs.append(target)
        if refs:
            extra["references"] = sorted(set(refs))
        packages, requested = [], {}
        for item in items.get("PackageReference") or ():
            ident = item.get("Identity") if isinstance(item, dict) else None
            if not self.shaped(ctx, proj, "PackageReference Identity", ident):
                continue
            packages.append(ident)
            if self.shaped(ctx, proj, "PackageReference Version", item.get("Version"), f"PackageReference {ident} Version"):
                requested[ident] = item["Version"]
        if requested:
            extra["requested"] = dict(sorted(requested.items()))
        ctx.add_package(base.rsplit(".", 1)[0], folder, **extra)
        ctx.add_imports(proj, packages)

    @staticmethod
    def shaped(ctx, proj, key, value, what=None):
        """True when VALUE is a non-empty string of KEY's shape (DOTNET_SHAPES). A missing or empty value is False
        without a note; any other is False with a note naming the project and the property, never the value, since
        evaluation may have filled it from a file or the environment."""
        if not isinstance(value, str) or not value:
            return False
        if len(value) <= DOTNET_MAX_VALUE and DOTNET_SHAPES[key].fullmatch(value):
            return True
        ctx.note(f"{proj}: {what or key}: the evaluated value is not of its shape, left out")
        return False


class NodeMapper(Mapper):
    """`npm ls --all --json --package-lock-only` in each directory that has a kept package.json and a package-lock.json
    (the survey leaves lock files out, so the worktree is asked). `--package-lock-only` builds the tree from the lock
    file: nothing is installed, no node_modules is read and no lifecycle script runs (`ls` runs none, and the mapper
    environment sets npm_config_ignore_scripts and npm_config_offline besides). `npm ls` prints its JSON and then exits
    1 when it has problems to list, so the output is read whatever the exit status."""
    language = "node"
    name = "npm"
    tool = "npm"

    def files(self, rows):
        return sorted(path for path, _kind in rows
                      if path.endswith((".js", ".mjs", ".cjs", ".jsx")) or path.rsplit("/", 1)[-1] == "package.json")

    def map(self, ctx, files):
        folders = sorted(folder_of(f) for f in files if f.rsplit("/", 1)[-1] == "package.json")
        if not folders:
            ctx.note("no package.json: no npm project mapped")
            return
        locked = [d for d in folders if (ctx.root / within(d, "package-lock.json")).exists()]
        if len(locked) < len(folders):
            ctx.note(f"{len(folders) - len(locked)} package.json file(s) without a package-lock.json beside them, "
                     "npm ls not run")
        for folder in capped(ctx, locked, "npm projects"):
            if ctx.readable(within(folder, "package-lock.json")) is not None:
                self.project(ctx, folder)

    def project(self, ctx, folder):
        tree = ctx.json(["npm", "ls", "--all", "--json", "--package-lock-only"], label=f"npm ls ({folder})",
                        cwd=folder, nonzero_ok=True)
        if not isinstance(tree, dict):
            if tree is not None:
                ctx.note(f"npm ls ({folder}): output is not an object")
            return
        deps = tree.get("dependencies") if isinstance(tree.get("dependencies"), dict) else {}
        extra = {"kind": "npm"}
        if isinstance(tree.get("version"), str):
            extra["version"] = tree["version"]
        name = tree["name"] if isinstance(tree.get("name"), str) and tree["name"] else folder
        ctx.add_package(name, folder, **extra)
        ctx.add_imports(within(folder, "package.json"), list(deps))
        problems = strings(tree.get("problems"))
        if problems:
            ctx.note(f"npm ls ({folder}): {len(problems)} problem(s), first: {problems[0][:150]}")


class TypeScriptMapper(Mapper):
    """`tsc --showConfig` (the effective options after `extends`) and `tsc --listFilesOnly` (the files of the
    compilation; it lists and stops) in each directory that has a kept tsconfig.json, with no file on the command line
    (a named file makes tsc ignore tsconfig.json, and TypeScript 7 refuse it). `tsc` is the one found on PATH: the
    mapper never goes through `npx` (which would run the repository's node_modules/.bin/tsc, or download one), and
    build_map refuses a `tsc` that lies inside the worktree."""
    language = "typescript"
    name = "tsc"
    tool = "tsc"

    def files(self, rows):
        return sorted(path for path, _kind in rows
                      if path.endswith((".ts", ".tsx", ".mts", ".cts")) or path.rsplit("/", 1)[-1] == "tsconfig.json")

    def map(self, ctx, files):
        configs = [f for f in files if f.rsplit("/", 1)[-1] == "tsconfig.json"]
        if not configs:
            ctx.note("no tsconfig.json: no TypeScript project mapped")
            return
        for cfg in capped(ctx, configs, "tsconfig.json files"):
            if ctx.readable(cfg) is not None:
                self.project(ctx, cfg)

    def project(self, ctx, cfg):
        folder = folder_of(cfg)
        conf = ctx.json(["tsc", "--showConfig"], label=f"tsc --showConfig ({folder})", cwd=folder)
        listing = ctx.output(["tsc", "--listFilesOnly"], f"tsc --listFilesOnly ({folder})", cwd=folder)
        if not isinstance(conf, dict) and listing is None:
            return
        options = conf.get("compilerOptions") if isinstance(conf, dict) else None
        options = options if isinstance(options, dict) else {}
        extra = {"kind": "tsconfig"}
        for key in ("target", "module", "moduleResolution"):
            if isinstance(options.get(key), str):
                extra[key] = options[key]
        if isinstance(options.get("strict"), bool):
            extra["strict"] = options["strict"]
        if listing is not None:
            mine = [r for r in (ctx.rel(ln.strip()) for ln in listing.splitlines() if ln.strip())
                    if r is not None and "node_modules/" not in r]
            extra["files"] = len(mine)  # the compiler's own lib files and installed packages lie outside the worktree
        ctx.add_package(cfg, folder, **extra)


MAPPERS = [PythonMapper(), GoMapper(), CargoMapper(), DotnetMapper(), NodeMapper(), TypeScriptMapper()]


@contextlib.contextmanager
def scratch_worktree(repo, commit):
    """A detached worktree of the repository at COMMIT in a temporary directory, removed on exit. No hook runs and no
    LFS filter fetches on the way in."""
    base = Path(tempfile.mkdtemp(prefix="kbingest-map-"))
    (base / "hooks").mkdir()
    tree_dir = base / "tree"
    try:
        p = git(repo, "-c", f"core.hooksPath={base / 'hooks'}", "-c", "core.fsmonitor=false",
                "-c", "filter.lfs.smudge=", "-c", "filter.lfs.process=", "-c", "filter.lfs.required=false",
                "worktree", "add", "--detach", "--quiet", str(tree_dir), commit)
        if p.returncode:
            raise RuntimeError("git worktree add failed: " + p.stderr.decode("utf-8", "replace").strip()[:300])
        yield tree_dir
    finally:
        git(repo, "worktree", "remove", "--force", str(tree_dir))
        shutil.rmtree(base, ignore_errors=True)
        git(repo, "worktree", "prune")


def first_line(r):
    for blob in (r.out, r.err):
        for ln in blob.decode("utf-8", "replace").splitlines():
            if ln.strip():
                return ln.strip()[:200]
    return ""


def build_map(repo, commit, rev, rows, langs=None, timeout=MAP_TIMEOUT, base_env=None):
    """The map of the repository at COMMIT: for each language with kept files and an installed toolchain, its mapper's
    packages, imports and entry points, read in a scratch worktree. A missing toolchain and every failed command is a
    note. ROWS is `classify`'s result: only kept files are mapped. The leak scan redacts the map before it is returned
    (`redact_leaks`)."""
    kept = [(p, k) for p, verdict, k, _secret in rows if verdict == "keep"]
    links = symlinks(repo, commit)
    doc = {"format": MAP_FORMAT, "repo": Path(repo).name, "commit": commit, "rev": rev, "tools": {}, "packages": [],
           "imports": [], "entry_points": [], "notes": []}
    with scratch_worktree(repo, commit) as root:
        env = scrub_env(base_env, root=root, repo=repo)
        for m in MAPPERS:
            if langs and m.language not in langs:
                continue
            files = m.files(kept)
            if not files:
                continue
            ctx = MapCtx(root, env, timeout, m.language, links)
            exe, inside = tool_exe(m.tool, env, root)
            if exe is None:
                ctx.note(f"toolchain not installed: {m.name} ({len(files)} {m.language} files not mapped)")
            elif inside:
                ctx.note(f"{m.name}: found inside the worktree, the repository's own program is never run "
                         f"({len(files)} {m.language} files not mapped)")
            elif (why := m.preflight(ctx, files)) is not None:
                ctx.note(why)
            else:
                v = run_tool([m.tool, *m.version_args], root, env, timeout)
                ok = v.rc == 0 and not v.timed_out and not v.missing
                doc["tools"][m.language] = {"tool": m.name, "version": first_line(v) if ok else "unknown"}
                if not ok:
                    ctx.note(f"{m.name}: version not read")
                try:
                    m.map(ctx, files)
                except Exception as e:  # noqa: BLE001 - a mapper's bug must not lose the other languages' maps
                    ctx.note(f"{m.name}: mapper failed: {type(e).__name__}: {str(e)[:150]}")
            ctx.finish()
            doc["packages"] += ctx.packages
            doc["imports"] += ctx.imports
            doc["entry_points"] += ctx.entry_points
            doc["notes"] += [{"language": m.language, "note": n} for n in ctx.notes]
    return redact_leaks(doc)


def redact_leaks(doc):
    """DOC with every string the leak scan flags (kbcommon.leak_hits: a secret, a home folder, a private address, an
    email or a GUID) replaced by `<redacted>`, and every mapping entry whose key it flags removed, with one note per
    place naming where and the kinds, never the value. The rest of the map is kept: a tool's output or an evaluated
    value can carry the environment or a file of the machine into the map, and from there into kb facts."""
    found = []

    def walk(value, where):
        if isinstance(value, str):
            hits = kbcommon.leak_hits(value)
            if hits:
                found.append((where, sorted({kind for kind, _ in hits})))
                return "<redacted>"
            return value
        if isinstance(value, list):
            return [walk(v, f"{where}[{i}]") for i, v in enumerate(value)]
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                hits = kbcommon.leak_hits(k) if isinstance(k, str) else []
                if hits:
                    found.append((f"{where}: a key", sorted({kind for kind, _ in hits})))
                else:
                    out[k] = walk(v, f"{where}.{k}" if where else k)
            return out
        return value

    doc = walk(doc, "")
    doc["notes"] += [{"language": "map", "note": f"{where}: a value of the leak scan's shapes ({', '.join(kinds)}) "
                      "redacted"} for where, kinds in found]
    return doc


def under_kb(path):
    """True when PATH is inside kb/ (any root): a map is a cache, never knowledge."""
    p = Path(path).resolve()
    dirs = [Path(kbcommon.KB_DIR).resolve()]
    try:
        dirs += [Path(r.path).resolve() for r in kbcommon.roots()]
    except (kbcommon.RootError, OSError):
        pass  # kb/ itself is checked above
    return any(p == d or d in p.parents for d in dirs)


def cmd_map(a):
    repo = Path(a.repo).expanduser().resolve()
    commit = resolve(repo, a.rev)
    if commit is None:
        print(f"refused: {repo.name}: not a git repository, or {a.rev!r} names no commit")
        return 2
    out = Path(a.out).expanduser() if a.out else INGEST_CACHE / f"{repo.name}-{commit[:12]}.json"
    if under_kb(out):
        print(f"refused: {out}: a map goes under _cache/ingest/, never under kb/")
        return 2
    langs = {x.strip().lower() for x in a.lang.split(",") if x.strip()} if a.lang else None
    known = {m.language for m in MAPPERS}
    if langs and langs - known:
        print(f"refused: unknown language {', '.join(sorted(langs - known))} (known: {', '.join(sorted(known))})")
        return 2
    entries = tree(repo, commit)
    attrs, _where = attributes(repo, commit, [p for p, k, _, _ in entries if k == "blob"])
    rows = classify(entries, attrs, a.max_bytes, lambda oids: contents(repo, oids))
    try:
        doc = build_map(repo, commit, a.rev, rows, langs, a.timeout)
    except RuntimeError as e:
        print(f"failed: {e}")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, out)
    print(f"map: {out}")
    print(f"commit: {commit} ({a.rev})")
    for lang, t in sorted(doc["tools"].items()):
        print(f"tool: {lang} {t['tool']} {t['version']}")
    print(f"packages={len(doc['packages'])} imports={len(doc['imports'])} entry_points={len(doc['entry_points'])} "
          f"notes={len(doc['notes'])}")
    for n in doc["notes"]:
        print(f"note: {n['language']}: {n['note']}")
    return 0


# ---------------------------------------------------------------- drift

PIN_URLS = (re.compile(r"^https://raw\.githubusercontent\.com/([^/]+/[^/]+)/((?:refs/tags/)?[^/]+)/(.+)$"),
            re.compile(r"^https://github\.com/([^/]+/[^/]+)/(?:blob|raw)/((?:refs/tags/)?[^/]+)/(.+)$"),
            re.compile(r"^https://([^/?#]+/.+?)/-/(?:raw|blob)/((?:refs/tags/)?[^/?#]+)/(.+)$"))
DEF_WORDS = ("def", "class", "function", "fn", "func", "fun", "struct", "enum", "trait", "interface", "type", "const",
             "let", "var", "val", "static", "module", "namespace", "record", "impl", "filter", "workflow", "macro_rules!",
             "configuration", "sub", "proc")
MODIFIERS = (r"(?:(?:export|pub(?:\([^)]*\))?|public|private|protected|internal|static|async|abstract|override|final|"
             r"extern|unsafe|default|declare|readonly|sealed|partial|virtual)\s+)*")
NOT_A_TYPE = {"return", "await", "new", "throw", "yield", "else", "elif", "in", "and", "or", "not", "del", "print",
              "assert", "raise", "case", "when", "if", "while", "for"}
LINE_RANGE = re.compile(r"L(\d+)(?:-L?(\d+))?")


def pin_parts(url):
    """(host, project path, ref, file path) of a repository file url at a ref (GitHub raw or blob, GitLab -/raw or
    -/blob), else None."""
    for i, rx in enumerate(PIN_URLS):
        m = rx.match(url.strip())
        if m and not m.group(2).startswith("-"):  # a ref that looks like an option is no ref
            rel = unquote(re.split(r"[?#]", m.group(3))[0])
            if i < 2:
                return "github.com", m.group(1), m.group(2), rel
            host, _, project = m.group(1).partition("/")
            return host.lower(), project, m.group(2), rel
    return None


def symbol_of(anchor):
    """The name the last segment of a pointer's symbol gives (`Class.method`, `mod::func`, `a.b.key`), or None for
    a line range (`L10-L20`)."""
    segs = [s for s in re.split(r"[.:]+", anchor) if s]
    return None if LINE_RANGE.fullmatch(anchor) or not segs else segs[-1]


def indent_of(line):
    return len(line) - len(line.lstrip())


def definition_lines(lines, name):
    """The 0-based indexes of the lines that define NAME, by a language-agnostic heuristic: a definition keyword
    (def, class, function, fn, func, struct, type, const, ...) after any modifiers, then NAME as a whole word; or NAME
    at the start of a line as a key or constant (`name:`, `name =`); or a function head (`name(...) {`, `name(...):`,
    or a declaration with a type before NAME). A call is not a definition."""
    n = re.escape(name)
    word = rf"(?<![\w-]){n}(?![\w-])"
    kw = re.compile(rf"^\s*{MODIFIERS}(?:{'|'.join(map(re.escape, DEF_WORDS))})\s[^\n]*?{word}")
    key = re.compile(rf"^\s*{MODIFIERS}[\"']?{n}[\"']?\s*(?::|=(?!=))")
    head = re.compile(rf"^\s*((?:[\w<>\[\],.*&?]+\s+)*){word}\s*\(")
    found = []
    for i, ln in enumerate(lines):
        if kw.match(ln) or key.match(ln):
            found.append(i)
            continue
        m = head.match(ln)
        types = m.group(1).split() if m else []
        if m and not (types and types[-1] in NOT_A_TYPE):
            tail = ln.rstrip()
            if tail.endswith(("{", ":")) or (types and not tail.endswith(";")):
                found.append(i)
    return found


def span_of(lines, i):
    """The definition at line I with its body: the following lines indented deeper (blank lines between them
    included) and a closing `}`, `)` or `]` at the same indent."""
    ind, out = indent_of(lines[i]), [lines[i]]
    for ln in lines[i + 1:]:
        if not ln.strip() or indent_of(ln) > ind:
            out.append(ln)
        else:
            if indent_of(ln) == ind and ln.lstrip().startswith(("}", ")", "]")):
                out.append(ln)
            break
    return "\n".join(x.rstrip() for x in out).rstrip()


def blob_lines(repo, commit, rel, cache):
    """The lines of file REL at COMMIT, or None when the commit has no such file (memoised in CACHE)."""
    key = (commit, rel)
    if key not in cache:
        p = git(repo, "cat-file", "blob", f"{commit}:{rel}")
        cache[key] = p.stdout.decode("utf-8", "replace").splitlines() if p.returncode == 0 else None
    return cache[key]


def renames(repo, old, new, cache):
    """{old path: new path} of the files git sees renamed between the commits OLD and NEW."""
    if (old, new) not in cache:
        out = git(repo, "diff", "--name-status", "-M", "--diff-filter=R", "-z", old, new).stdout.split(b"\0")
        cache[(old, new)] = {out[i + 1].decode("utf-8", "surrogateescape"): out[i + 2].decode("utf-8", "surrogateescape")
                             for i in range(0, len(out) - 2, 3) if out[i].startswith(b"R")}
    return cache[(old, new)]


def compare_evidence(old_lines, new_lines, anchor):
    """(kind, detail) when the evidence a pointer's ANCHOR names differs between two versions of a file, else None
    (a line shift alone is no difference). Kinds: symbol-missing, changed, moved, unverifiable."""
    rng = LINE_RANGE.fullmatch(anchor)
    if rng:
        a = int(rng.group(1))
        b = int(rng.group(2) or a)
        block = old_lines[a - 1:b] if 1 <= a <= b else []
        if not block:
            return "unverifiable", f"{anchor}: no such lines at the pinned commit"
        if new_lines[a - 1:b] == block:
            return None
        for k in range(len(new_lines) - len(block) + 1):
            if new_lines[k:k + len(block)] == block:
                return "moved", f"lines {a}-{b} are now lines {k + 1}-{k + len(block)}"
        return "changed", f"lines {a}-{b} no longer read as at the pinned commit"
    name = symbol_of(anchor)
    if name is None:
        return "unverifiable", f"{anchor}: no symbol"
    olds, news = definition_lines(old_lines, name), definition_lines(new_lines, name)
    word = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
    seen = sum(1 for x in new_lines if word.search(x))
    if (olds and not news) or not seen:
        return "symbol-missing", (f"{name} is no longer defined (still mentioned on {seen} lines)" if seen
                                  else f"{name} does not occur")
    if not olds:
        return None if old_lines == new_lines else (
            "changed", f"{name} has no definition the heuristic finds at the pinned commit, and the file changed")
    want = span_of(old_lines, olds[0])
    if any(span_of(new_lines, i) == want for i in news):
        return None
    return "changed", f"the definition of {name} differs (line {olds[0] + 1} at the pinned commit, line {news[0] + 1})"


def drift_findings(repo, new, facts, sources, project):
    """([(kb path, line, source id, pointer, kind, detail)], checked, elsewhere): each CODE citation in FACTS whose
    source is a pinned url into the repository (PROJECT: host, lower-case project path) compared between the commit
    of that url and NEW; `elsewhere` counts the citations of other sources."""
    files, moves, commits, findings = {}, {}, {}, []
    checked = elsewhere = 0
    for u in facts:
        for part in u["tags"]:
            ptr = kbfacts.code_pointer(part) if part["kind"] == "CODE" else None
            if not ptr:
                continue
            cands = []
            for sid in part["ids"]:
                pin = pin_parts((sources.get(sid) or {}).get("url") or "")
                if pin and (pin[0], pin[1].lower()) == project:
                    cands.append((sid, pin))
            if not cands:
                elsewhere += 1
                continue
            sid, pin = next(((s, p) for s, p in cands if p[3] == ptr[0] or p[3].endswith("/" + ptr[0])), cands[0])
            checked += 1
            label = f"{ptr[0]}#{ptr[1]}"
            # a pointer may name the file by the last segments of its path (utils.ts for src/spec-node/utils.ts)
            path, anchor = (pin[3] if pin[3].endswith("/" + ptr[0]) else ptr[0]), ptr[1]

            def found(kind, detail):
                findings.append((u["path"], u["line"], sid, label, kind, detail))
            if pin[2] not in commits:
                commits[pin[2]] = resolve(repo, pin[2])
            old = commits[pin[2]]
            if old is None:
                found("unverifiable", f"the pinned commit {pin[2][:12]} is not in this clone")
                continue
            if old == new:
                continue
            before = blob_lines(repo, old, path, files)
            if before is None:
                found("unverifiable", f"{path} is not in the pinned commit {pin[2][:12]}")
                continue
            at, note = path, ""
            after = blob_lines(repo, new, at, files)
            if after is None:
                at = renames(repo, old, new, moves).get(path)
                if at is None:
                    found("file-missing", f"{path} is not in {new[:12]}")
                    continue
                note, after = f"file moved to {at}", blob_lines(repo, new, at, files)
            diff = compare_evidence(before, after or [], anchor)
            if note:
                found("moved", note + (f"; {diff[0]}: {diff[1]}" if diff else "; the cited evidence is unchanged"))
            elif diff:
                found(*diff)
    return findings, checked, elsewhere


def cmd_drift(a):
    repo = Path(a.repo).expanduser().resolve()
    new = resolve(repo, a.rev)
    if new is None:
        print(f"refused: {repo.name}: not a git repository, or {a.rev!r} names no commit")
        return 2
    if a.remote:
        host, _, path = a.remote.strip().partition("/")
        project = (host.lower(), path.strip("/").lower())
    else:
        r = remote_of(repo)
        project = (r[1], r[2].lower()) if r else None
    if not project or not project[1]:
        print(f"refused: {repo.name} has no remote to match the source rows to; pass --remote HOST/PROJECT")
        return 2
    try:
        names = [r.name for r in kbcommon.roots()]
        if a.root and a.root not in names:
            print(f"refused: no root {a.root!r} (roots: {', '.join(names)})")
            return 2
        facts = [u for u in kbfacts.units(a.prefix) if not a.root or kbfacts.root_name(u["path"]) == a.root]
        sources = kbfacts.source_rows()
    except (kbcommon.RootError, OSError) as e:
        print(f"refused: {e}")
        return 2
    findings, checked, elsewhere = drift_findings(repo, new, facts, sources, project)
    print(f"commit: {new} ({a.rev})")
    for path, line, sid, label, kind, detail in sorted(findings):
        print(f"finding\t{kind}\t{path}:{line}\t{sid}\t{label}\t{detail}")
    print(f"checked={checked} unchanged={checked - len(findings)} findings={len(findings)} elsewhere={elsewhere}")
    return 1 if findings else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey", help="what a repository holds at a commit, and what to leave out")
    s.add_argument("repo")
    s.add_argument("--rev", default="HEAD")
    s.add_argument("--forge", choices=("gitlab", "github"))
    s.add_argument("--max-bytes", type=int, default=1_000_000)
    s.add_argument("--files", action="store_true", help="one line per file")
    s.add_argument("--pins", action="store_true", help="one line per toolchain pin (versions, runtimes, frameworks)")
    u = sub.add_parser("url", help="the pinned url of one file at the commit")
    u.add_argument("repo")
    u.add_argument("path")
    u.add_argument("--rev", default="HEAD")
    u.add_argument("--forge", choices=("gitlab", "github"))
    mp = sub.add_parser("map", help="packages, imports and entry points by each installed toolchain's read-only commands")
    mp.add_argument("repo")
    mp.add_argument("--rev", default="HEAD")
    mp.add_argument("--out", help="the JSON map (default: _cache/ingest/<repo>-<commit>.json; never under kb/)")
    mp.add_argument("--lang", help="only these languages, comma-separated (default: every language with files)")
    mp.add_argument("--timeout", type=int, default=MAP_TIMEOUT, help="seconds per mapper command (default %(default)s)")
    mp.add_argument("--max-bytes", type=int, default=1_000_000)
    d = sub.add_parser("drift", help="the CODE facts whose cited file or symbol moved, changed or vanished at a new commit")
    d.add_argument("repo")
    d.add_argument("--rev", default="HEAD", help="the new commit (default HEAD)")
    d.add_argument("--root", help="only the facts of this kb root")
    d.add_argument("--prefix", help="only the facts under this topic or path prefix (`dsc`, `public/dsc/what-if`)")
    d.add_argument("--remote", help="HOST/PROJECT the source rows are matched to (default: the repository's origin)")
    a = ap.parse_args(argv)
    return {"survey": cmd_survey, "url": cmd_url, "map": cmd_map, "drift": cmd_drift}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
