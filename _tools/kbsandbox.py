"""The sandbox a command runs in when it handles a file nobody here wrote (stdlib only): an allow-list environment
plus offline settings, PATH cut to absolute folders outside the clone, a program looked up on that PATH only, a timeout,
and the process group killed with it. `kbingest.py map` runs a toolchain's read-only commands in it and `fetch.py text`
an extractor over a downloaded archive. Docs: kb/_self/tools.md.

Answers: how the commands that read an untrusted repository or archive are kept offline, scrubbed and bounded
"""
import os, re, shutil, signal, subprocess
from pathlib import Path
from typing import NamedTuple

# what makes a sandboxed command's environment offline: proxies that refuse, the tools' own offline switches (RUSTUP_AUTO_INSTALL=0:
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
# the variables a mapper command keeps of the caller's environment, an allow-list: everything else is dropped, so a
# toolchain hook nobody listed (CARGO_BUILD_RUSTC_WRAPPER, CARGO_TARGET_<triple>_LINKER, RUSTFLAGS, GOFLAGS, RUBYOPT,
# PERL5OPT, JAVA_TOOL_OPTIONS, BASH_ENV, GIT_EXEC_PATH, GIT_CONFIG_GLOBAL, GIT_SSH_COMMAND, npm_config_userconfig,
# LD_LIBRARY_PATH, NODE_OPTIONS, ...) never reaches a child that resolves a relative program against the repository.
# Compared without case (Windows spells them either way). Plain names: PATH (scrubbed below), where a home, a temporary
# folder and the locale are; on Windows the system and profile folders a process starts with
ENV_KEEP = frozenset((
    "PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LANGUAGE",
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "OS", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA",
    "LOCALAPPDATA", "PROGRAMDATA", "ALLUSERSPROFILE", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE"))
ENV_KEEP_PREFIX = ("LC_",)  # the locale categories
# the folders where a toolchain lives, kept only as an absolute path outside the worktree and the source clone: a
# toolchain installed away from its default, which a child could not find otherwise
ENV_HOMES = frozenset(("CARGO_HOME", "RUSTUP_HOME", "DOTNET_ROOT", "GOROOT", "GOPATH", "GOMODCACHE", "GOCACHE"))


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


def drive_less_rooted(piece):
    """True on Windows path semantics when PIECE is rooted but names no drive and is not UNC: one `\\` or `/` first,
    then no second separator (`\\Users\\x`, HOMEPATH). Such a piece is not `os.path.isabs` in older Pythons, and the
    tops are drive-qualified, so it cannot lie inside one."""
    return (os.path.sep == "\\" and piece[:1] in ("\\", "/") and piece[1:2] not in ("\\", "/")
            and not os.path.splitdrive(piece)[0])


def names_clone_code(value, tops):
    """True when the environment value VALUE names code of the clone: a path inside one of TOPS (the worktree and the
    source clone, None ones skipped), or a relative one with a folder part (`tools/w`, `./hook.js`), which the child
    resolves against its working folder, the worktree. VALUE is split on the path-list separator, white space, `=`
    and quotes, so `--require=/clone/hook.js` and a list of paths all show their pieces; an absolute piece counts when
    it lies inside a top. A drive-less rooted piece on Windows (`drive_less_rooted`: HOMEPATH `\\Users\\x`) is exempt: it
    is no relative path, and no top is drive-less; a UNC piece (`\\\\server\\share`) is not exempt."""
    for piece in re.split("[\\s=\"'" + re.escape(os.pathsep) + "]+", value):
        if not piece:
            continue
        if drive_less_rooted(piece):
            continue
        if os.path.isabs(piece):
            if any(top is not None and under_worktree(piece, top) for top in tops):
                return True
        elif re.search(r"[\\/]", piece) or piece in (".", ".."):
            return True
    return False


def kept_env(name, value, tops):
    """True when the mapper child keeps the variable NAME set to VALUE: it is in ENV_KEEP or begins with an
    ENV_KEEP_PREFIX and names no code of the clone (`names_clone_code`), or it is in ENV_HOMES and is an absolute path
    outside the clone. PATH is kept here and cleaned by `scrub_env`."""
    up = name.upper()
    if up == "PATH":
        return True
    if up in ENV_HOMES:
        return os.path.isabs(value) and not names_clone_code(value, tops)
    return (up in ENV_KEEP or up.startswith(ENV_KEEP_PREFIX)) and not names_clone_code(value, tops)


def scrub_env(base=None, windows=None, root=None, repo=None):
    """The environment of a mapper command: an allow-list of the caller's (`kept_env`: ENV_KEEP, ENV_KEEP_PREFIX and
    ENV_HOMES, so no credential, proxy or toolchain hook whatever its name) plus NETWORK_OFF. On
    Windows (WINDOWS, by default os.name) it also sets NoDefaultCurrentDirectoryInExePath: cmd.exe, which runs an npm
    cmd-shim (tsc.cmd, npm.cmd), otherwise looks for a bare `node` in the working folder before PATH, and that folder
    is the repository's (https://learn.microsoft.com/windows/win32/api/processenv/nf-processenv-needcurrentdirectoryforexepathw:
    the variable's existence, not its value, drops the current directory from cmd.exe's search).
    PATH keeps only its absolute entries outside the worktree ROOT and outside the source repository REPO (its own
    clone, which the operator's PATH can name too: a `node_modules/.bin` there, a direnv-added bin folder): a child
    resolves a relative entry (`.`, `node_modules/.bin`, an empty one) against its own working folder, the repository's,
    so `#!/usr/bin/env node` or a rustup proxy there would run the repository's program. A kept variable whose value
    names a path inside ROOT or REPO, or a relative path with a folder part, is dropped too."""
    tops = (root, repo)
    env = {k: v for k, v in (os.environ if base is None else base).items() if kept_env(k, v, tops)}
    env.update(NETWORK_OFF)
    for k in [k for k in env if k.upper() == "PATH"]:
        env[k] = os.pathsep.join(e for e in env[k].split(os.pathsep) if e and Path(e).is_absolute()
                                 and not any(top is not None and under_worktree(e, top) for top in tops))
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
