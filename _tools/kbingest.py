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

Exit: 0 done, 2 refused (not a git repository, an unknown REV, or `url` with no pinned url form).
"""
import argparse, re, subprocess, sys
from pathlib import Path
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
    a = ap.parse_args(argv)
    return cmd_survey(a) if a.cmd == "survey" else cmd_url(a)


if __name__ == "__main__":
    sys.exit(main())
