"""The query log's shared ground (kb/_self/querylog.md): where it keeps its files, the per-user config, the per-machine
lock, atomic writes and the commands it runs. Standard library only; every stage module imports it.

  places()              (querylog directory, config file): a clone's _cache/querylog and _private/querylog.json, or
                        ${CLAUDE_PLUGIN_DATA}/querylog/ and its config.json when this copy runs as the plugin
  read_mode(cfg)        auto, local or off (fail closed); read_research(cfg) the research switch and daily cap
  logging_off(q, cfg)   mode off or the DISABLED marker
  acquire(q) / release  the distill lock: an O_EXCL file, stale by age only (querylog.md, Portability)
  claude_p(argv, ...)   one `claude -p` run in an empty directory, the prompt on stdin
"""
import datetime, json, os, subprocess, sys, tempfile, time, uuid
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
HOME = TOOLS.parent
ENTRY = TOOLS / "querylog.py"  # the command every hook and the launcher run
STORE_REL = "kb/_querylog"
STORE = HOME / STORE_REL

DEFAULT_MODE = "auto"
MODES = ("auto", "local", "off")
DEFAULT_RESEARCH = False  # research writes facts: each person turns it on in their own config file
DEFAULT_RESEARCH_DAILY = 3  # research runs per user per day when the config file turns research on and names no cap
DISABLED_NAME = "DISABLED"  # beside the spool: logging off for good
LOCK_NAME = "distill.lock"
LOCK_STALE_S = 3600
PIPELINE_VERSION = 6 # bumped when what distill writes, or how it decides it, changes


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def plugin_data():
    """${CLAUDE_PLUGIN_DATA} when this copy runs as the plugin (the hook's CLAUDE_PLUGIN_ROOT is this copy), else
    None: a plugin host."""
    data, root = os.environ.get("CLAUDE_PLUGIN_DATA"), os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(data) if data and root and _same(root, HOME) else None


def places():
    """(querylog directory, config file): the plugin's data directory when this copy runs as the plugin, else the
    clone's _cache/querylog and _private/querylog.json."""
    data = plugin_data()
    if data is not None:
        d = data / "querylog"
        return d, d / "config.json"
    return HOME / "_cache" / "querylog", HOME / "_private" / "querylog.json"


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def read_mode(cfg):
    """The mode the config file sets: DEFAULT_MODE when there is no file, `off` when it cannot be read or names no
    known mode (fail closed: a broken file never turns logging on)."""
    try:
        data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_MODE
    except (OSError, ValueError):
        return "off"
    m = data.get("mode", DEFAULT_MODE) if isinstance(data, dict) else None
    return m if m in MODES else "off"


def read_research(cfg):
    """(on, daily cap) the config file sets for research: off with no file (DEFAULT_RESEARCH), off when the file
    cannot be read, `research` is not true, or `research_daily` is not a whole number of 0 or more (fail closed);
    the cap is `research_daily`, else DEFAULT_RESEARCH_DAILY."""
    try:
        data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_RESEARCH, DEFAULT_RESEARCH_DAILY if DEFAULT_RESEARCH else 0
    except (OSError, ValueError):
        return False, 0
    if not isinstance(data, dict) or data.get("research", DEFAULT_RESEARCH) is not True:
        return False, 0
    daily = data.get("research_daily", DEFAULT_RESEARCH_DAILY)
    if isinstance(daily, bool) or not isinstance(daily, int) or daily < 0:
        return False, 0
    return True, daily


def logging_off(qdir, cfg):
    """Whether the query log writes nothing: mode off (or an unreadable config) or the DISABLED marker."""
    return (Path(qdir) / DISABLED_NAME).exists() or read_mode(cfg) == "off"


def iso(t):
    """Epoch seconds in the spool's time format: UTC, milliseconds, `Z`."""
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z")


def now():
    return iso(time.time())


def one_line(s, n=300):
    return " ".join(str(s).split())[:n]


def write_text(path, text):
    """Write `text` to `path` atomically (a temporary file beside it, then os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def json_lines(objs):
    """Objects as compact JSON lines."""
    return "".join(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n" for o in objs)


def lock_age(path):
    """Seconds since the lock at `path` was taken (its recorded start, else its mtime); None when there is none."""
    try:
        started = Path(path).stat().st_mtime
    except OSError:
        return None
    data = read_json(path, {})
    if isinstance(data, dict) and isinstance(data.get("started_epoch"), (int, float)):
        started = data["started_epoch"]
    return time.time() - started


def acquire(qdir):
    """Take the distill lock of `qdir`: its path, or None when another distill holds it. A lock older than
    LOCK_STALE_S is taken over; the holder's PID is never signalled (os.kill(pid, 0) ends a process on Windows)."""
    path = Path(qdir) / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            age = lock_age(path)
            if attempt or (age is not None and age < LOCK_STALE_S):
                return None
            if age is not None:
                stale = path.with_name(f"{LOCK_NAME}.stale-{uuid.uuid4().hex[:8]}")
                try:
                    os.rename(path, stale)  # atomic: of two takers, one wins
                    stale.unlink()
                except OSError:
                    return None
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"pid": os.getpid(), "started": now(), "started_epoch": time.time()}, f)
        return path
    return None


def release(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def run_cmd(argv, cwd=None, env=None, timeout=600):
    """(exit code, stdout, stderr) of a command given as an argument list; 127 when it cannot start or times out."""
    try:
        p = subprocess.run(list(argv), cwd=None if cwd is None else str(cwd), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)
    return p.returncode, p.stdout, p.stderr


def claude_p(argv, prompt, timeout):
    """The reply of one `claude -p` run of `argv` (hooks off, built by its stage) in an empty temporary directory, so
    no project instructions load, with the prompt on stdin. OSError when it cannot answer."""
    with tempfile.TemporaryDirectory() as d:
        try:
            p = subprocess.run(argv, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired as e:
            raise OSError(f"claude -p gave no reply in {timeout} s") from e
    if p.returncode:
        raise OSError(f"claude -p exited {p.returncode}")
    return p.stdout


class Replay:
    """Recorded replies ({"replies": [text, ...]}), answered in order; OSError once they run out. Distill answers its
    Haiku calls from one (`distill --replay`), apply its research runs (`apply --replay-research`)."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.replies, self.prompts = list(self.data.get("replies") or []), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.replies:
            raise OSError("no recorded reply left")
        return self.replies.pop(0)


def restore(saved):
    """Put back files a change wrote: {path: its bytes before, or None for no file}."""
    for path, old in saved.items():
        if old is None:
            Path(path).unlink(missing_ok=True)
        else:
            Path(path).write_bytes(old)


def stdin_hook(fn):
    """A hook command: `fn(event)` on the JSON event read from stdin; no output, exit 0 whatever happens (a hook never
    gets in the way of a prompt or a session)."""
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        fn(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - see the docstring
        pass
    return 0
