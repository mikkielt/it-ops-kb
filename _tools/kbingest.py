#!/usr/bin/env python3
"""Survey a git repository before its knowledge goes into a kb root (stdlib only; the /kb-ingest skill).

  kbingest.py survey REPO [--rev REV] [--forge gitlab|github] [--max-bytes N] [--files]
      REPO is a local clone. Prints the remote (host and project path, never credentials), the commit REV (default
      HEAD) resolves to, whether a remote-tracking branch holds it (as of the last fetch: else the pinned urls do
      not resolve for anyone else yet), the pinned url form a CODE source row takes, whether .gitattributes were read
      at the commit, then per top-level area the kept files by kind and the files left out. `--files` adds one
      tab-separated line per file: `keep KIND PATH URL [secret]` or `skip REASON PATH`.
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

Exit: 0 done, 1 `map` could not create its worktree, 2 refused (not a git repository, an unknown REV, `url` with no
pinned url form, `map` with an unknown language or an --out under kb/).
"""
import argparse, contextlib, json, os, re, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kbcommon  # noqa: E402

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
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()
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


# ---- map: read-only toolchain mapping in a scratch worktree ----------------------------------------------------------

MAP_FORMAT = 1
INGEST_CACHE = Path(kbcommon.HOME) / "_cache" / "ingest"
MAP_TIMEOUT = 60  # seconds per mapper command
MAP_MAX_FILES = 2000  # files one per-file mapper maps before it stops with a note
MAP_MAX_OUTPUT = 64 * 1024 * 1024  # bytes of a command's output that are parsed
NOTE_LIMIT = 20  # notes one language keeps before it counts the rest
# what makes a mapper command's environment offline: proxies that refuse, the tools' own offline switches
NETWORK_OFF = {
    "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "ALL_PROXY": "http://127.0.0.1:9",
    "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "all_proxy": "http://127.0.0.1:9",
    "NO_PROXY": "", "no_proxy": "",
    "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOFLAGS": "-mod=readonly",
    "CARGO_NET_OFFLINE": "true", "npm_config_offline": "true", "npm_config_update_notifier": "false",
    "COREPACK_ENABLE_NETWORK": "0", "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1",
    "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "PIP_NO_INDEX": "1", "GIT_TERMINAL_PROMPT": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}
SECRET_ENV = re.compile(r"(?i)token|secret|passw|credential|api[_-]?key|private[_-]?key|auth|cookie|session")
PROXY_ENV = re.compile(r"(?i)^(?:https?|all|ftp|no)_proxy$")


def scrub_env(base=None):
    """The environment of a mapper command: the caller's, without credentials and proxies, plus NETWORK_OFF."""
    env = {k: v for k, v in (os.environ if base is None else base).items()
           if not SECRET_ENV.search(k) and not PROXY_ENV.match(k)}
    env.update(NETWORK_OFF)
    return env


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
    A program not found on ENV's PATH is `missing`, not an error."""
    exe = shutil.which(args[0], path=env.get("PATH"))
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


class MapCtx:
    """What a mapper sees: the worktree ROOT, `run`/`json` for commands, `add_*` and `note` for results."""

    def __init__(self, root, env, timeout, language):
        self.root, self.env, self.timeout, self.language = Path(root), env, timeout, language
        self.packages, self.imports, self.entry_points, self.notes = [], [], [], []
        self._dropped = 0

    def note(self, text):
        if len(self.notes) >= NOTE_LIMIT:
            self._dropped += 1
        else:
            self.notes.append(text.replace(str(self.root), "<worktree>"))

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
        """The file REL of the worktree, or None (with a note) when it is a symbolic link or not a file."""
        p = self.root / rel
        if p.is_symlink() or not p.is_file():
            self.note(f"{rel}: not a regular file in the worktree (a symbolic link?), not read")
            return None
        return p

    def run(self, args, label=None, timeout=None):
        """A Run of ARGS in the worktree; a missing program, a timeout and a non-zero exit each add a note."""
        r = run_tool(list(args), self.root, self.env, timeout or self.timeout)
        what = label or " ".join(str(a) for a in args)[:100]
        if r.missing:
            self.note(f"{what}: program not found on PATH")
        elif r.timed_out:
            self.note(f"{what}: timed out after {timeout or self.timeout}s")
        elif r.rc != 0:
            first = (r.err.decode("utf-8", "replace").strip().splitlines() or [""])[0][:200]
            self.note(f"{what}: exit {r.rc}" + (f": {first}" if first else ""))
        return r

    def json(self, args, label=None):
        """The parsed JSON a command prints, or None (with a note)."""
        what = label or " ".join(str(a) for a in args)[:100]
        r = self.run(args, what)
        if r.missing or r.timed_out or r.rc != 0:
            return None
        if len(r.out) > MAP_MAX_OUTPUT:
            self.note(f"{what}: output over {MAP_MAX_OUTPUT} bytes, not parsed")
            return None
        try:
            return json.loads(r.out.decode("utf-8", "replace"))
        except ValueError as e:
            self.note(f"{what}: output is not JSON ({str(e)[:80]})")
            return None


class Mapper:
    """One language's mapper. `name` is what the map records; `tool` the program looked up on PATH; `files(rows)` the
    kept (path, kind) pairs it maps (none: the language is absent and the mapper does not run); `map(ctx, files)` runs
    only read-only commands, through ctx, and records packages, imports and entry points."""
    language = ""
    name = ""
    tool = ""
    version_args = ("--version",)

    def files(self, rows):
        return []

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
        if not p.is_file() or p.is_symlink():
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


MAPPERS = [PythonMapper()]


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
    note. ROWS is `classify`'s result: only kept files are mapped."""
    env = scrub_env(base_env)
    kept = [(p, k) for p, verdict, k, _secret in rows if verdict == "keep"]
    doc = {"format": MAP_FORMAT, "repo": Path(repo).name, "commit": commit, "rev": rev, "tools": {}, "packages": [],
           "imports": [], "entry_points": [], "notes": []}
    with scratch_worktree(repo, commit) as root:
        for m in MAPPERS:
            if langs and m.language not in langs:
                continue
            files = m.files(kept)
            if not files:
                continue
            ctx = MapCtx(root, env, timeout, m.language)
            if shutil.which(m.tool, path=env.get("PATH")) is None:
                ctx.note(f"toolchain not installed: {m.name} ({len(files)} {m.language} files not mapped)")
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
    a = ap.parse_args(argv)
    return {"survey": cmd_survey, "url": cmd_url, "map": cmd_map}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
