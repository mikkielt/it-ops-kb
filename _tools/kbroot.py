#!/usr/bin/env python3
"""The kb's roots (stdlib only): list them, add one beside kb/public, or keep one from another repository.

  kbroot.py list                         name, id prefix, visibility, team (when it names one), articles, sources and path of every root, then a
                                         row `missing` with its reason for each pointer whose root is not here
  kbroot.py add-remote NAME --url URL --prefix P --team T [--visibility internal|public] [--ref BRANCH]
                        [--access fetch|submodule] [--description TEXT]
                                         write the pointer file kb/_roots/NAME.md (no `pin`; `ref` empty follows the
                                         remote's default branch); `submodule` access also runs `git submodule add` at
                                         kb/NAME (a failure removes the pointer again, exit 1)
  kbroot.py fetch [--pin] [NAME ...]     clone or update each fetch root (all, or those named) into _cache/roots/NAME/
                                         (${CLAUDE_PLUGIN_DATA}/roots/NAME/ when this copy runs as the plugin) at its
                                         `pin` or the tip of its `ref`, with no credential prompt; a failed git command
                                         reports its reason line (the `! [rejected]` line of a refused push, else the last
                                         line that is no `hint:` line, the url left out); a failure is kept as the
                                         reason `list` gives for a root with no clone, and the clone of an update that
                                         fails stays as it was. `--pin` writes the commit the clone is at into the
                                         pointer's `pin`, so the root stays there until `pin` is emptied (refused, exit 2,
                                         when this copy runs as the plugin: the pointer is in the plugin copy). A fetch of a
                                         root with a `pin` checks out the pin, whatever its `ref` has moved to. Only
                                         this command and its --hook form fetch: lookups read what is on disk
  kbroot.py fetch --hook                 the SessionStart form: fetch each fetch root for which any one of these holds: it has
                                         no clone, its last fetch is older than HOOK_MAX_AGE_S, or its last fetch used another
                                         url, ref or pin (any one of them); each bounded at HOOK_FETCH_BOUND_S and all within HOOK_BUDGET_S
                                         (a root not reached is left to the next session); prints one line per failed
                                         root and nothing else; always exit 0
  kbroot.py push NAME                    push the commits of the checked-out submodule root kb/NAME to its own remote
                                         (the pointer's `ref`, else the branch it is on), then commit the gitlink bump
                                         in this repository, so neither holds a commit the other cannot reach. A fetch
                                         root is read-only; a root with uncommitted changes is refused
  kbroot.py add NAME --prefix P [--visibility internal|public] [--description TEXT]
                                         create kb/NAME/: its _root.md, empty ledgers with their headers, a coverage
                                         page with the table markers, _retrieval/ with empty data tables, and empty
                                         _decisions.csv and decision-makers.csv

A root is a directory of knowledge with its own sources and id prefix (kbcommon.py, "Roots"): kb/public holds the
upstream facts, and a team adds its own roots (its systems, its repositories, its internal runbooks) beside it.
NAME: lowercase letters, digits and `-`. P: 1-4 capital letters, not taken by another root and not one of
kbcommon.RESERVED_PREFIXES. `internal` (the default) exempts the root from the placeholders-only rule; `public`
keeps it (AGENTS.md, "Agent conduct").

A root in another repository is named by a pointer file kb/_roots/<name>.md (kbcommon.py): `list` shows one whose
root is not on disk as `missing` and exits 0; `add` refuses a name or prefix a pointer holds.

Exit: 0 done (always, for `fetch --hook`), 1 a fetch, a submodule add or a push failed (stderr names the root), 2 refused (bad name or prefix, taken, the directory exists,
a name that is no fetch root, or for `push` a fetch root, a root not checked out, or one with uncommitted changes).
Where this copy runs as the plugin (kbcommon.plugin_hosted: the copy is read-only), `add`, `add-remote`, `push` and
`fetch --pin` are refused, exit 2, before any git call or write: they write the plugin copy.

Answers: which roots the kb has, their id prefix, visibility and size, and how to add or fetch one
Use: python3 _tools/kbroot.py list|add|add-remote|fetch|push [ARGS]
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index, kbcommon, kg_lock  # noqa: E402

FETCH_TIMEOUT_S = 120  # one git command of a fetch
HOOK_MAX_AGE_S = 24 * 3600  # `fetch --hook` fetches a root again once its last fetch is older than this
HOOK_FETCH_BOUND_S = 20  # `fetch --hook`: the longest one root's fetch may take
HOOK_BUDGET_S = 50  # `fetch --hook`: all its fetches, inside the 60 s timeout of the hook that runs it

SOURCES_HEADER = "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
FILES = {
    kbcommon.SOURCES: SOURCES_HEADER,
    kbcommon.ARTIFACTS: "path,source_id,sha256,zip_member\n",
    kbcommon.STATE: ",".join(kbcommon.STATE_COLS) + "\n",
    kbcommon.COVERAGE_CSV: ",".join(build_index.COVERAGE_FIELDS) + "\n",
    kbcommon.ANSWERS: "# Answers to research questions\n\nEach answer is headed `## QK-<slug>. <question>` "
                      "(`python3 _tools/kbid.py answer \"<question>\" --root {name}`); every bullet carries one tag.\n",
    kbcommon.GAPS: "# Gaps (UNK items: what was tried, where)\n",
    kbcommon.CONFLICTS: "# Conflicts (both sources linked)\n",
    kbcommon.DATA_DIR + "/lookup_eval.csv": "id,question,expect_paths,expect_verdict,allow_weak\n",
    kbcommon.DATA_DIR + "/signals.csv": "signal,topic\n",
    kbcommon.DATA_DIR + "/index_extra.csv": "topic,priority,status,files\n",
    kbcommon.DECISIONS: ",".join(kbcommon.DECISION_COLS) + "\n",
    kbcommon.DECISION_MAKERS: ",".join(kbcommon.MAKER_COLS) + "\n",
}


def root_md(name, prefix, visibility, description):
    return (f"---\nroot: {name}\nid_prefix: {prefix}\nvisibility: {visibility}\ndescription: {description}\n---\n\n"
            f"# {name}\n\n{description or 'A knowledge root.'}\n\nSource ids of this root are `{prefix}-<8 characters>`: "
            f"`python3 _tools/kbid.py url <URL> --root {name}`.\n")


def cmd_list():
    try:
        roots = kbcommon.roots()
    except kbcommon.RootError as e:
        print("ERROR", e)
        return 2
    for r in roots:
        n_art = sum(1 for p in build_index.content_files(r)
                    if p.endswith(".md") and build_index.front_matter(build_index.read(p, r) or "") is not None)
        try:
            n_src = len(kbcommon.load_csv(os.path.join(r.path, kbcommon.SOURCES), ("id",))[1])
        except kbcommon.CsvError:
            n_src = 0
        where = os.path.relpath(r.path, kbcommon.HOME) if r.path.startswith(kbcommon.HOME + os.sep) else r.path
        team = f"\tteam={r.team}" if r.team else ""
        print(f"{r.name}\tprefix={r.id_prefix}\t{r.visibility}{team}\tarticles={n_art}\tsources={n_src}\t{where}")
    missing = kbcommon.missing_roots()
    for m in missing:
        print(f"{m.name}\tprefix={m.id_prefix or '?'}\t{m.visibility or '?'}\tmissing\t{m.reason}\t{os.path.relpath(m.path, kbcommon.HOME)}")
    print(f"roots={len(roots)}" + (f" missing={len(missing)}" if missing else ""))
    return 0


def plugin_refusal(writes):
    """The refusal (exit 2) of a command whose `writes` land in the plugin copy, read-only here; 0 where this copy is not run as the plugin."""
    if not kbcommon.plugin_hosted():
        return 0
    print(f"refused: {writes}, which is in the plugin copy, read-only here; run it in a clone of the team's repository")
    return 2


def cmd_add(a):
    refused = plugin_refusal("`add` creates kb/NAME/")
    if refused:
        return refused
    name, prefix = a.name, a.prefix
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name == "kb":
        print(f"refused: root name {name!r} must be lowercase letters, digits and -")
        return 2
    if not kbcommon.PREFIX.fullmatch(prefix) or prefix in kbcommon.RESERVED_PREFIXES:
        print(f"refused: id prefix {prefix!r} must be 1-4 capital letters, not one of "
              f"{', '.join(sorted(kbcommon.RESERVED_PREFIXES))}")
        return 2
    try:
        roots = kbcommon.roots()
    except kbcommon.RootError as e:
        print("refused: fix the existing roots first:", e)
        return 2
    for r in [*roots, *kbcommon.missing_roots()]:  # a pointer keeps its name and prefix whether or not its root is here
        if r.name == name or r.id_prefix == prefix:
            print(f"refused: root {r.name} ({getattr(r, 'path', '')}) already has the "
                  f"{'name' if r.name == name else 'id prefix'} {name if r.name == name else prefix!r}")
            return 2
    d = os.path.join(kbcommon.KB_DIR, name)
    if os.path.exists(d):
        print(f"refused: {os.path.relpath(d, kbcommon.HOME)} exists")
        return 2
    os.makedirs(os.path.join(d, kbcommon.DATA_DIR))
    files = {kbcommon.ROOT_FILE: root_md(name, prefix, a.visibility, " ".join(a.description.split())),
             kbcommon.COVERAGE_MD: f"# Coverage: {name}\n\nEvery topic of this root, generated by "
                                   f"`python3 _tools/build_index.py`: never edit the table by hand.\n\n"
                                   f"{build_index.START}\n{build_index.END}\n",
             **{k: v.format(name=name) for k, v in FILES.items()}}
    for rel, text in files.items():
        with open(os.path.join(d, rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    print(f"created {os.path.relpath(d, kbcommon.HOME)}/ (root {name}, id prefix {prefix}, {a.visibility}): "
          f"add domain directories of articles, then python3 _tools/build_index.py and python3 _tools/check.py")
    return 0


def pointer_md(name, prefix, visibility, team, url, ref, access, description):
    return (f"---\nroot: {name}\nid_prefix: {prefix}\nvisibility: {visibility}\nteam: {team}\nurl: {url}\nref: {ref}\n"
            f"pin: \naccess: {access}\ndescription: {description}\n---\n\n"
            f"# {name}\n\n{description or 'A root kept in its own repository.'}\n")


def cmd_add_remote(a):
    refused = plugin_refusal("`add-remote` writes the pointer file kb/_roots/NAME.md")
    if refused:
        return refused
    name, prefix = a.name, a.prefix
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name == "kb":
        print(f"refused: root name {name!r} must be lowercase letters, digits and -")
        return 2
    if not kbcommon.PREFIX.fullmatch(prefix) or prefix in kbcommon.RESERVED_PREFIXES:
        print(f"refused: id prefix {prefix!r} must be 1-4 capital letters, not one of "
              f"{', '.join(sorted(kbcommon.RESERVED_PREFIXES))}")
        return 2
    for what, v, required in (("url", a.url, True), ("team", a.team, True), ("ref", a.ref, False),
                              ("description", a.description, False)):
        if "\n" in v or "\r" in v or (required and not v.strip()):
            print(f"refused: {what} must be one {'non-empty ' if required else ''}line")
            return 2
    if kbcommon.url_holds_credential(a.url):  # refused before anything is written, and the url is not echoed
        print("refused: url holds a credential (a user:password@ or token@ part); give the repository's url without it "
              "and let git's credential helper or an ssh key supply it")
        return 2
    try:
        roots = kbcommon.roots()
    except kbcommon.RootError as e:
        print("refused: fix the existing roots first:", e)
        return 2
    for r in [*roots, *kbcommon.missing_roots()]:
        if r.name == name or r.id_prefix == prefix:
            print(f"refused: root {r.name} already has the {'name' if r.name == name else 'id prefix'} "
                  f"{name if r.name == name else prefix!r}")
            return 2
    if os.path.exists(os.path.join(kbcommon.KB_DIR, name)):
        print(f"refused: kb/{name} exists")
        return 2
    d = os.path.join(kbcommon.KB_DIR, kbcommon.POINTERS_DIR)
    path = os.path.join(d, name + ".md")
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(pointer_md(name, prefix, a.visibility, a.team.strip(), a.url.strip(), a.ref.strip(), a.access,
                           " ".join(a.description.split())))
    problems = kbcommon.pointer_problems(path)
    if problems:
        os.remove(path)
        print("refused:", "; ".join(problems))
        return 2
    rel = os.path.relpath(path, kbcommon.HOME).replace(os.sep, "/")
    if a.access == "fetch":
        print(f"created {rel} (root {name}, id prefix {prefix}, {a.visibility}, fetch): python3 _tools/kbroot.py fetch {name}")
        return 0
    why = submodule_add(kbcommon.read_pointer(path))
    if why:
        os.remove(path)
        print(f"submodule add failed: {name}: {why}", file=sys.stderr)
        return 1
    print(f"created {rel} (root {name}, id prefix {prefix}, {a.visibility}, submodule) and the submodule kb/{name}: "
          f"commit .gitmodules, kb/{name} and the pointer")
    return 0


def fetch_env():
    """The environment of a git run by a fetch: no credential prompt (a missing credential fails at once). No
    askpass program is named (GIT_ASKPASS, SSH_ASKPASS dropped, `core.askPass` set empty for the run), and GCM is
    told not to interact."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="false", LC_ALL="C")
    for k in ("GIT_ASKPASS", "SSH_ASKPASS"):
        env.pop(k, None)
    try:
        n = max(int(env.get("GIT_CONFIG_COUNT", "0")), 0)
    except ValueError:
        n = 0
    env.update({"GIT_CONFIG_COUNT": str(n + 1), f"GIT_CONFIG_KEY_{n}": "core.askPass", f"GIT_CONFIG_VALUE_{n}": ""})
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def run_bounded(args, cwd, timeout):
    """`git ARGS` as the leader of a process group of its own: a CompletedProcess with text output. Past TIMEOUT
    seconds (or an interrupt) the whole group ends (git and the ssh or remote helper it started: subprocess.run's
    timeout kills git alone) and subprocess.TimeoutExpired is raised."""
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    argv = ["git", *args]
    proc = subprocess.Popen(argv, cwd=cwd, env=fetch_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **group)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kg_lock.end_group(proc)
        try:
            proc.communicate(timeout=5)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        raise
    except BaseException:
        kg_lock.end_group(proc)
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


ABS_PATH_QUOTED = re.compile(r"\s*'(?:/|[A-Za-z]:[\\/]|\\\\)[^']*'")
ABS_PATH_BARE = re.compile(r"(?<![\w/.\\])(?:/|[A-Za-z]:[\\/]|\\\\)\S+")


def without_paths(line):
    """`line` without the absolute paths it names (git reports the directory it could not create in quotes): the
    home directory of the user never reaches a session."""
    return ABS_PATH_BARE.sub("a path", ABS_PATH_QUOTED.sub("", line))


def git(args, p, cwd=None, timeout=FETCH_TIMEOUT_S):
    """Run git with `args`; (True, '') or (False, the line of its stderr that gives the reason, without
    the pointer's url or an absolute path: the `! [rejected]` line of a refused push, else the last line that is no
    `hint:`)."""
    try:
        r = run_bounded(args, cwd, timeout)
    except subprocess.TimeoutExpired:
        return False, f"git {args[0]} timed out after {round(timeout)} s"
    except OSError as e:
        return False, f"git not run ({getattr(e, 'strerror', None) or e})"
    if r.returncode == 0:
        return True, ""
    lines = [ln.strip() for ln in (r.stderr or r.stdout).splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("hint:")]
    # a refused push names its reason on the `! [rejected] HEAD -> main (fetch first)` line, above git's summary line
    refused = [ln for ln in lines if ln.startswith("!") and "rejected" in ln]
    reason = (refused[-1] if refused else lines[-1] if lines else f"git {args[0]} exited {r.returncode}").replace(p.url, "the url")
    return False, without_paths(reason)


def git_out(args, p, cwd):
    """Run git with `args` in `cwd`; (True, its stdout stripped) or (False, why) as git() says."""
    try:
        r = run_bounded(args, cwd, FETCH_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"git {args[0]} not run ({e.__class__.__name__})"
    if r.returncode:
        return False, f"git {args[0]} exited {r.returncode}"
    return True, r.stdout.strip()


def submodule_add(p):
    """Check the root of submodule Pointer `p` out as a git submodule at kb/<name>/ of this repository (on its `ref`
    when it names one); '' when done, else why it failed, with nothing of it left behind."""
    d = kbcommon.pointer_root_dir(p)
    rel = os.path.relpath(d, kbcommon.HOME).replace(os.sep, "/")
    gm = os.path.join(kbcommon.HOME, ".gitmodules")
    try:
        with open(gm, "rb") as f:
            gm_before = f.read()
    except OSError:
        gm_before = None
    gm_clean = git(["diff", "--cached", "--quiet", "--", ".gitmodules"], p, kbcommon.HOME)[0]
    ok, why = git(["submodule", "add", "--quiet", *(["-b", p.ref] if p.ref else []), "--", p.url, rel], p, kbcommon.HOME)
    if ok and not os.path.isfile(os.path.join(d, kbcommon.ROOT_FILE)):
        ok, why = False, f"the repository holds no {kbcommon.ROOT_FILE}"
    if not ok:
        git(["submodule", "deinit", "--force", "--", rel], p, kbcommon.HOME)
        git(["rm", "--cached", "--force", "--quiet", "--", rel], p, kbcommon.HOME)
        if gm_before is None:
            if os.path.exists(gm):
                os.remove(gm)
            git(["rm", "--cached", "--force", "--quiet", "--ignore-unmatch", "--", ".gitmodules"], p, kbcommon.HOME)
        else:
            with open(gm, "wb") as f:
                f.write(gm_before)
            if gm_clean:
                git(["reset", "--quiet", "--", ".gitmodules"], p, kbcommon.HOME)
        shutil.rmtree(d, ignore_errors=True)
        found, gitdir = git_out(["rev-parse", "--absolute-git-dir"], p, kbcommon.HOME)
        if found:
            shutil.rmtree(os.path.join(gitdir, "modules", *rel.split("/")), ignore_errors=True)
    return why


def fetch_one(p, bound=None):
    """Clone or update the root of fetch Pointer `p` into its directory, at `pin` or the tip of `ref`; '' when done,
    else why it failed. A failed update leaves the clone as it was. `bound`: seconds all of it may take."""
    end = time.monotonic() + bound if bound else None

    def run(args, cwd=None):
        left = FETCH_TIMEOUT_S if end is None else min(FETCH_TIMEOUT_S, end - time.monotonic())
        if left <= 0:
            return False, f"fetch timed out after {round(bound)} s"
        return git(args, p, cwd, left)

    d = kbcommon.pointer_root_dir(p)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.isdir(os.path.join(d, ".git")):
        # a pointer whose url moved: the clone follows it, and goes back to its old url when the fetch fails
        known, old_url = git_out(["config", "--get", "remote.origin.url"], p, d)
        moved = not known or old_url != p.url
        if moved:
            ok, why = run(["remote", "set-url", "origin", "--", p.url], d)
            if not ok:
                return why
        ok, why = run(["fetch", "--quiet", "--tags", "--force", "origin", "+refs/heads/*:refs/remotes/origin/*"], d)
        if not ok:
            if moved and known:
                git(["remote", "set-url", "origin", "--", old_url], p, d)
            return why
    else:
        tmp = d + ".part"
        shutil.rmtree(tmp, ignore_errors=True)
        ok, why = run(["clone", "--quiet", "--no-checkout", "--", p.url, tmp])
        if not ok:
            shutil.rmtree(tmp, ignore_errors=True)
            return why
        shutil.rmtree(d, ignore_errors=True)
        os.replace(tmp, d)
    target = p.pin or (f"origin/{p.ref}" if p.ref else "origin/HEAD")
    ok, why = run(["checkout", "--quiet", "--force", "--detach", target + "^{commit}"], d)
    if not ok:
        return why
    if not os.path.isfile(os.path.join(d, kbcommon.ROOT_FILE)):
        return f"the repository holds no {kbcommon.ROOT_FILE} at {target}"
    return ""


def os_reason(e):
    """Why OSError `e` happened, without the path it names."""
    return getattr(e, "strerror", None) or e.__class__.__name__


def fetched_stamp(name):
    """The file whose mtime is when root `name` was last fetched without failing (beside its clone) and whose text is
    the fingerprint of the pointer that fetch used."""
    return os.path.join(kbcommon.roots_cache_dir(), name + ".fetched")


def fingerprint(p):
    """A short digest of the url, ref and pin of Pointer `p`: what a fetch of it depends on."""
    return hashlib.sha256("\0".join((p.url, p.ref, p.pin)).encode("utf-8")).hexdigest()[:16]


def stale(p, now):
    """Whether fetch Pointer `p` has no clone, no fetch within HOOK_MAX_AGE_S before `now` (time.time()), or a url, ref
    or pin other than the last fetch used (a stamp that holds no fingerprint counts as changed: one more fetch writes it)."""
    try:
        if not os.path.isfile(os.path.join(kbcommon.pointer_root_dir(p), kbcommon.ROOT_FILE)):
            return True
        stamp = fetched_stamp(p.name)
        if now - os.path.getmtime(stamp) > HOOK_MAX_AGE_S:
            return True
        with open(stamp, encoding="utf-8") as f:
            return f.read().strip() != fingerprint(p)
    except (OSError, UnicodeError):
        return True


def record_fetch(p, why):
    """Keep the result of a fetch of Pointer `p`: the reason it failed, else its time and the pointer it used."""
    err = kbcommon.fetch_error_path(p.name)
    if why:
        with open(err, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"fetch failed: {why}\n")
        return
    if os.path.exists(err):
        os.remove(err)
    with open(fetched_stamp(p.name), "w", encoding="utf-8", newline="\n") as f:
        f.write(fingerprint(p) + "\n")


def cmd_fetch_hook():
    """SessionStart: fetch each stale fetch root within its bound and the hook's budget; one line per failure."""
    try:
        start, now = time.monotonic(), time.time()
        for p in kbcommon.pointers():
            if p.access != "fetch" or not stale(p, now):
                continue
            left = HOOK_BUDGET_S - (time.monotonic() - start)
            if left < 1:
                break
            try:
                why = fetch_one(p, min(HOOK_FETCH_BOUND_S, left))
            except OSError as e:
                why = f"the clone directory is not usable ({os_reason(e)})"
            try:
                record_fetch(p, why)
            except OSError as e:
                why = (why + "; " if why else "") + f"the result is not recorded ({os_reason(e)})"
            if why:
                print(f"fetch failed: {p.name}: {why}")
    except Exception as e:  # a hook never fails a session
        print(f"fetch failed: {e.__class__.__name__}: {os_reason(e) if isinstance(e, OSError) else without_paths(str(e))}")
    return 0


def write_pin(p, commit):
    """Set `pin` in the front matter of Pointer `p`'s file to `commit`; False when the file has no front matter."""
    with open(p.path, encoding="utf-8", newline="") as f:
        text = f.read()
    m = re.match(r"\ufeff?(---\r?\n)(.*?)(\r?\n---)", text, re.S)
    if not m:
        return False
    head, eol = m.group(2), m.group(1)[3:]
    if re.search(r"^pin:[^\r\n]*", head, re.M):
        head = re.sub(r"^pin:[^\r\n]*", lambda _: f"pin: {commit}", head, count=1, flags=re.M)
    else:
        head += f"{eol}pin: {commit}"
    with open(p.path, "w", encoding="utf-8", newline="") as f:
        f.write(text[:m.start(2)] + head + text[m.end(2):])
    return True


def cmd_fetch(a):
    if a.hook:
        return cmd_fetch_hook()
    if a.pin:
        refused = plugin_refusal("--pin writes the pointer file kb/_roots/NAME.md")
        if refused:
            return refused
    fetchable = [p for p in kbcommon.pointers() if p.access == "fetch"]
    by_name = {p.name: p for p in fetchable}
    if a.names:
        unknown = [n for n in a.names if n not in by_name]
        if unknown:
            print(f"refused: no fetch root {', '.join(unknown)}; fetch roots: {', '.join(by_name) or 'none'}")
            return 2
        fetchable = [by_name[n] for n in dict.fromkeys(a.names)]
    failed = 0
    for p in fetchable:
        try:
            why = fetch_one(p)
        except OSError as e:
            why = f"the clone directory is not usable ({os_reason(e)})"
        try:
            record_fetch(p, why)
        except OSError as e:
            if why:
                why += f"; the failure is not recorded ({os_reason(e)})"
            else:
                print(f"fetch not recorded: {p.name}: {os_reason(e)}", file=sys.stderr)
        if why:
            failed += 1
            print(f"fetch failed: {p.name}: {why}", file=sys.stderr)
        else:
            print(f"fetched {p.name}")
            if a.pin:
                ok, commit = git_out(["rev-parse", "HEAD"], p, kbcommon.pointer_root_dir(p))
                if not ok:
                    failed += 1
                    print(f"pin failed: {p.name}: {commit}", file=sys.stderr)
                    continue
                try:
                    written = write_pin(p, commit)
                except OSError as e:
                    failed += 1
                    print(f"pin failed: {p.name}: the pointer is not written ({os_reason(e)})", file=sys.stderr)
                    continue
                if written:
                    print(f"pinned {p.name} at {commit}")
                    try:
                        record_fetch(p._replace(pin=commit), "")
                    except OSError as e:
                        print(f"fetch not recorded: {p.name}: {os_reason(e)}", file=sys.stderr)
                else:
                    failed += 1
                    print(f"pin failed: {p.name}: the pointer has no front matter", file=sys.stderr)
    print(f"fetch roots={len(fetchable)} failed={failed}")
    return 1 if failed else 0


def cmd_push(a):
    refused = plugin_refusal("`push` commits the gitlink bump of kb/NAME")
    if refused:
        return refused
    by_name = {p.name: p for p in kbcommon.pointers()}
    p = by_name.get(a.name)
    if p is None:
        print(f"refused: no remote root {a.name}; remote roots: {', '.join(by_name) or 'none'}")
        return 2
    if p.access != "submodule":
        print(f"refused: {a.name} is a fetch root, read-only (its clone is a cache that `kbroot.py fetch` replaces); "
              f"write in a clone of the team's repository or keep the root as a submodule")
        return 2
    d = kbcommon.pointer_root_dir(p)
    rel = os.path.relpath(d, kbcommon.HOME).replace(os.sep, "/")
    if not os.path.exists(os.path.join(d, ".git")):
        print(f"refused: {rel} is not a checked-out submodule: git submodule update --init -- {rel}")
        return 2
    ok, dirty = git_out(["status", "--porcelain"], p, d)
    if not ok:
        print(f"push failed: {a.name}: {dirty}", file=sys.stderr)
        return 1
    if dirty:
        print(f"refused: {rel} has uncommitted changes; commit them in the root first")
        return 2
    ok, branch = git_out(["symbolic-ref", "--short", "-q", "HEAD"], p, d)
    target = p.ref or (branch if ok else "")
    if not target:
        print(f"refused: {rel} is on no branch and the pointer names no `ref`; check out a branch in the root first")
        return 2
    ok, why = git(["push", "--quiet", "origin", f"HEAD:refs/heads/{target}"], p, d)
    if not ok:
        print(f"push failed: {a.name}: {why}", file=sys.stderr)
        return 1
    ok, commit = git_out(["rev-parse", "HEAD"], p, d)
    ok2, why = git(["add", "--", rel], p, kbcommon.HOME)
    if not (ok and ok2):
        print(f"gitlink bump failed: {a.name}: {commit if not ok else why}", file=sys.stderr)
        return 1
    if git(["diff", "--cached", "--quiet", "--", rel], p, kbcommon.HOME)[0]:
        print(f"pushed {a.name} to {target}; the superproject already holds {commit[:12]}")
        return 0
    ok, why = git(["commit", "--quiet", "-m", f"chore(kb): bump root {a.name} to {commit[:12]}", "--", rel], p, kbcommon.HOME)
    if not ok:
        print(f"gitlink bump failed: {a.name}: {why}", file=sys.stderr)
        return 1
    print(f"pushed {a.name} to {target} and committed the gitlink at {commit[:12]}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="every root")
    ar = sub.add_parser("add-remote", help="write the pointer file of a root kept in another repository")
    ar.add_argument("name")
    ar.add_argument("--url", required=True, help="the root's repository")
    ar.add_argument("--prefix", required=True, help="the root's source id prefix: 1-4 capital letters")
    ar.add_argument("--team", required=True, help="the team that owns the root")
    ar.add_argument("--visibility", choices=("internal", "public"), default="internal")
    ar.add_argument("--ref", default="", help="a branch (default: the remote's default branch)")
    ar.add_argument("--access", choices=kbcommon.ACCESS, default="fetch")
    ar.add_argument("--description", default="", help="one line: what the root holds")
    fe = sub.add_parser("fetch", help="clone or update fetch roots into the roots cache")
    fe.add_argument("--pin", action="store_true", help="write the commit each fetch root is at into its pointer's `pin`")
    fe.add_argument("--hook", action="store_true", help="SessionStart form: fetch the stale roots within a bound, print "
                    "only failures, exit 0")
    fe.add_argument("names", nargs="*", metavar="NAME", help="fetch roots to fetch (default: every one)")
    pu = sub.add_parser("push", help="push a submodule root's commits to its own remote, then commit the gitlink")
    pu.add_argument("name", metavar="NAME", help="a submodule root")
    ad = sub.add_parser("add", help="create a root beside kb/public")
    ad.add_argument("name")
    ad.add_argument("--prefix", required=True, help="the root's source id prefix: 1-4 capital letters")
    ad.add_argument("--visibility", choices=("internal", "public"), default="internal")
    ad.add_argument("--description", default="", help="one line: what the root holds")
    a = ap.parse_args()
    return {"list": lambda: cmd_list(), "add": lambda: cmd_add(a), "add-remote": lambda: cmd_add_remote(a),
            "fetch": lambda: cmd_fetch(a), "push": lambda: cmd_push(a)}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
