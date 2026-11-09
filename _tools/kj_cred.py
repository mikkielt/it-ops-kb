"""The credential of a job's git: the identity a placement names, as environment variables (stdlib only; kb/_self/coordination.md,
section "Operation jobs").

  resolve(identity, group, operator, cred_dir, environ) -> {NAME: value}  what to add to the environment of the job's process
  cred_dir(environ)                                     -> the directory the credential files are read from
  Refused                                               the identity has no usable credential: the message names the identity
                                                        and the path or variable

`none` disables every push: `remote.origin.pushurl` and a catch-all `pushInsteadOf` (an empty prefix) name an invalid url, and no credential
helper or prompt answers. `group-bot` reads `CRED_DIR/group/<group path>` or the variable `KB_GROUP_TOKEN_<GROUP PATH>` (the group path in
upper case, every character outside A-Z and 0-9 as `_`: `corp/ops` is `KB_GROUP_TOKEN_CORP_OPS`), the file first. `operator` reads
`CRED_DIR/operator/<operator path>`. A file is a regular file with no group or other bit (mode 0600; not checked where the host has no
mode bits) and is not empty; a missing, empty or too open credential raises `Refused`.

The token reaches git only through the helper `GIT_ASKPASS` names, a script `resolve` writes once to a directory of its own (mode 0700,
the user's): it prints the file named by `KB_CRED_FILE` or the variable named by `KB_CRED_VAR`, and a user name for a `Username` prompt
(`KB_CRED_USER`). The result holds those names and paths, never the token: no value of it, no argument of a command holds one.
`resolve` never reads a file's content. A caller merges the result over its own environment, after dropping the helper names it
holds (`clean`), so the host's own credential helpers and prompts are never used (`credential.helper` is reset).
"""
import getpass
import os
import re
import stat
import tempfile
from pathlib import Path

IDENTITIES = ("none", "group-bot", "operator")
SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
VAR_PREFIX = "KB_GROUP_TOKEN_"
ENV_DIR = "KB_CRED_DIR"
HELPER_NAMES = ("KB_CRED_FILE", "KB_CRED_VAR", "KB_CRED_USER")  # what `resolve` sets for the helper
NO_PUSH_URL = "kb-push-disabled://invalid/"
HELPER_DIR = "kb-askpass"
HELPER = """#!/bin/sh
case "$1" in
  Username*) printf '%s' "${KB_CRED_USER:-oauth2}"; exit 0 ;;
esac
if [ -n "$KB_CRED_FILE" ]; then exec cat -- "$KB_CRED_FILE"; fi
if [ -n "$KB_CRED_VAR" ]; then exec printenv "$KB_CRED_VAR"; fi
exit 1
"""


class Refused(Exception):
    """A job's identity has no usable credential; the message names the identity and the path or variable."""


def cred_dir(environ=None):
    """The directory credentials are read from: `KB_CRED_DIR` in ENVIRON (the process environment when None), else
    `~/.config/it-ops-kb/credentials`."""
    given = (os.environ if environ is None else environ).get(ENV_DIR)
    return Path(given) if given else Path.home() / ".config" / "it-ops-kb" / "credentials"


def clean(environ):
    """A copy of ENVIRON without the names `resolve` sets for the helper, so a name of an earlier job cannot reach the next."""
    return {k: v for k, v in environ.items() if k not in HELPER_NAMES}


def segments(path, what, identity):
    """The segments of the group or operator PATH (`corp/ops`), each a safe file name; Refused when PATH is empty or holds another."""
    parts = str(path or "").split("/")
    if not path or not all(SEGMENT.fullmatch(p) and ".." not in p for p in parts):
        raise Refused(f"{identity}: the {what} {str(path)[:60]!r} is no path of names (letters, digits, `_`, `.`, `-`) joined by `/`")
    return parts


def variable_name(group):
    """The CI variable of a group: KB_GROUP_TOKEN_ and the group path in upper case, every character outside A-Z and 0-9 as `_`."""
    return VAR_PREFIX + re.sub(r"[^A-Z0-9]", "_", group.upper())


def check_file(identity, path):
    """Refused unless PATH is a non-empty regular file with no group or other bit (the mode bits are not read where the host has none)."""
    try:
        info = os.stat(path)
    except OSError:
        raise Refused(f"{identity}: no credential: the file {path} is missing") from None
    if not stat.S_ISREG(info.st_mode):
        raise Refused(f"{identity}: no credential: {path} is no regular file")
    if os.name == "posix" and info.st_mode & 0o077:
        raise Refused(f"{identity}: {path} has mode {stat.S_IMODE(info.st_mode):04o}: a credential file must be 0600 (no group or other bit)")
    if info.st_size == 0:
        raise Refused(f"{identity}: no credential: the file {path} is empty")


def helper_path():
    """The askpass script (written once, replaced when its text differs) in a directory of the user's own, mode 0700; Refused when
    that directory belongs to another user or is open to others."""
    user = getpass.getuser()
    folder = Path(tempfile.gettempdir()) / f"{HELPER_DIR}-{re.sub(r'[^A-Za-z0-9_.-]', '_', user)}"
    try:
        folder.mkdir(mode=0o700, exist_ok=True)
        info = os.lstat(folder)
    except OSError as error:
        raise Refused(f"the askpass directory {folder} cannot be made: {error}") from None
    if os.name == "posix" and (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise Refused(f"the askpass directory {folder} is not the user's own with mode 0700")
    path = folder / "askpass"
    try:
        same = path.read_text(encoding="utf-8") == HELPER
    except OSError:
        same = False
    if not same:
        part = folder / f"askpass.{os.getpid()}"
        with open(part, "w", encoding="utf-8", newline="\n") as f:
            f.write(HELPER)
        os.chmod(part, 0o700)
        os.replace(part, path)
    return str(path)


def git_config(environ, pairs):
    """The GIT_CONFIG_COUNT variables that append PAIRS ([(key, value)]) to the configuration ENVIRON already names."""
    try:
        have = max(0, int(environ.get("GIT_CONFIG_COUNT", "0")))
    except ValueError:
        have = 0
    out = {"GIT_CONFIG_COUNT": str(have + len(pairs))}
    for i, (key, value) in enumerate(pairs, have):
        out[f"GIT_CONFIG_KEY_{i}"] = key
        out[f"GIT_CONFIG_VALUE_{i}"] = value
    return out


def resolve(identity, group, operator, cred_dir, environ):
    """The environment to add to a job's process for IDENTITY (none, group-bot or operator), the job's GROUP path and OPERATOR path,
    the credential directory CRED_DIR and the environment ENVIRON the job inherits (read for the CI variable and the git
    configuration it holds). Raises Refused for an identity with no usable credential, one outside the table included."""
    if identity not in IDENTITIES:
        raise Refused(f"{str(identity)[:40]!r} is none of {', '.join(IDENTITIES)}")
    environ = environ if environ is not None else {}
    base = {"GIT_TERMINAL_PROMPT": "0"}
    if identity == "none":
        return {**base, **git_config(environ, [("credential.helper", ""), ("remote.origin.pushurl", NO_PUSH_URL),
                                              (f"url.{NO_PUSH_URL}.pushInsteadOf", "")])}
    config = git_config(environ, [("credential.helper", "")])
    if identity == "group-bot":
        parts = segments(group, "group", identity)
        path = Path(cred_dir, "group", *parts)
        var = variable_name("/".join(parts))
        user = "group-bot"
        if path.exists():
            check_file(identity, path)
            source = {"KB_CRED_FILE": str(path)}
        elif environ.get(var):
            source = {"KB_CRED_VAR": var}
        else:
            raise Refused(f"{identity}: no credential for {group}: the file {path} is missing and the variable {var} is not set")
    else:
        parts = segments(operator, "operator", identity)
        path = Path(cred_dir, "operator", *parts)
        check_file(identity, path)
        source, user = {"KB_CRED_FILE": str(path)}, parts[-1]
    return {**base, **config, **source, "KB_CRED_USER": user, "GIT_ASKPASS": helper_path()}
