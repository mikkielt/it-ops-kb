"""The host-wide main lock (kb/_self/git.md, Two runners on one host): one O_EXCL file `kb-main.lock` in the host lock
directory (KB_HOST_LOCK_DIR, else /tmp), held while a process moves the integration main: `backlog.py land`'s fetch and
rebase, and `kbgit.py sync --push`. A second process prints who holds it and what it is doing, and waits. It is the
test lock's mechanism (`tests.py`: the holder record, the grace for an unwritten record, the atomic clearing of a
holder whose pid no longer runs), on its own file.

Order of the two host locks: the main lock first, the test lock second. `sync --push` holds the main lock while its
gate runs `tests.py`, which takes the test lock; nothing that holds the test lock waits for the main lock (a run
inside a test takes none: `wanted`), so the two cannot wait on each other.

A process the lock holder starts (the re-run of sync with rebased code) inherits KB_MAIN_LOCK_HELD, the holder's pid;
it takes no second lock while the file still names that pid. Standard library only; imports no facade.
"""
import contextlib, datetime, os, signal, sys, time

LOCK_NAME = "kb-main.lock"
HELD_ENV = "KB_MAIN_LOCK_HELD"


class LockOrderError(RuntimeError):
    """The main lock was asked for by a process that holds the test lock: the one order is main, then test."""


def wanted():
    """Whether this process takes the lock: not inside a test (PYTEST_CURRENT_TEST), whose repositories are scratch
    clones that move no real main, and which may already hold the test lock."""
    return not os.environ.get("PYTEST_CURRENT_TEST")


def holder_step(text):
    """The `step=` line of a lock file's text: what its holder does; '?' when it has none."""
    for ln in (text or "").splitlines():
        if ln.startswith("step="):
            return ln[len("step="):] or "?"
    return "?"


@contextlib.contextmanager
def main_lock(step, label="kbgit.py", poll=None, clone=None, on_stale=None):
    """Hold the main lock for the block: STEP names what the holder does (it is written in the record and printed to
    a waiter). Takes it by exclusive create, prints the holder and its step and waits while a live process holds it,
    clears a holder whose pid no longer runs, and releases on exit, on an error and on SIGTERM. Inside a process the
    holder started (HELD_ENV names the pid the file records) it takes nothing. on_stale(label) is called after a lock
    is judged stale and before it is cleared (a test's hook)."""
    import tests as tests_py  # the test lock's helpers: one mechanism, a second file
    path = os.path.join(tests_py.host_lock_dir(), LOCK_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mine = tests_py.read_holder(os.path.join(tests_py.host_lock_dir(), tests_py.HOST_LOCK_NAME))
    if mine and mine["pid"] == os.getpid():
        raise LockOrderError("the host main lock is taken before the host test lock, never after it: this process "
                             "holds the test lock")
    held = tests_py.read_holder(path)
    if held and os.environ.get(HELD_ENV) == str(held["pid"]) and tests_py.pid_alive(held["pid"]):
        yield path
        return
    poll = poll if poll is not None else float(os.environ.get("KB_HOST_LOCK_POLL", "5"))
    me = (f"pid={os.getpid()}\nclone={clone or os.getcwd()}\n"
          f"started={datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\nstep={step}\n")
    told = None
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            text = tests_py.read_lock(path)
            if text is None and not os.path.exists(path):  # released: look again
                continue
            holder = tests_py.parse_holder(text or "")
            if holder is None:
                try:
                    young = time.time() - os.stat(path).st_mtime < tests_py.lock_grace()
                except OSError:
                    continue
                if young:  # its holder has not written the record yet
                    time.sleep(poll)
                    continue
            if holder is None or not tests_py.pid_alive(holder["pid"]):
                if on_stale:
                    on_stale(label)
                if tests_py.clear_stale(path, text):
                    print(f"{label}: clearing a stale host main lock ({holder['pid'] if holder else 'unreadable'})",
                          flush=True)
                continue
            if holder != told:
                print(f"{label}: waiting for the host main lock held by pid {holder['pid']} "
                      f"(clone {holder['clone']}, started {holder['started']}, {holder_step(text)})", flush=True)
                told = holder
            time.sleep(poll)
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(me)
        break
    prev = None
    try:
        prev = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    except (ValueError, OSError):  # not the main thread
        pass
    before = os.environ.get(HELD_ENV)
    os.environ[HELD_ENV] = str(os.getpid())
    try:
        yield path
    finally:
        if before is None:
            os.environ.pop(HELD_ENV, None)
        else:
            os.environ[HELD_ENV] = before
        if prev is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGTERM, prev)
        holder = tests_py.read_holder(path)
        if holder and holder["pid"] == os.getpid():
            with contextlib.suppress(OSError):
                os.unlink(path)


def guarded(step, label="kbgit.py", **kw):
    """main_lock(step) when this process takes the lock, else a block that holds nothing."""
    return main_lock(step, label, **kw) if wanted() else contextlib.nullcontext()
