"""mon_split: open kbmon's live view in a pane beside the session (stdlib only). Docs: kb/_self/monitoring.md.

`kbmon.py --split` runs the live view (`kbmon.py --interval 60`) in a new pane of the terminal the session runs in:
tmux (TMUX set), WezTerm (WEZTERM_PANE set) or Windows Terminal (WT_SESSION set), whichever of them is found first in that
order. Anywhere else it prints the command to run in a second terminal. It exits 0 in every case.
"""
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SPLIT_INTERVAL = 60  # seconds between frames of the split pane's live view: low CPU, no constant load
PANE_SHARE = 40  # percent of the width the new pane takes
RUN_TIMEOUT = 20  # seconds the splitting command may take

HINT = """no pane to split: none of TMUX, WEZTERM_PANE and WT_SESSION is set.
Run the live view in a second terminal:
  {command}
WezTerm is optional and can split the window for you: python3 _tools/install_wezterm.py --plan"""


def live_command(script, extra=(), python=sys.executable):
    """The argument list of the live view the pane runs (`python`: the interpreter that starts it)."""
    return [python, str(script), "--interval", str(SPLIT_INTERVAL), *extra]


def join(argv):
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


def splitter(env):
    """The name of the terminal whose pane the session is in, from `env`, or None."""
    if env.get("TMUX"):
        return "tmux"
    if env.get("WEZTERM_PANE"):
        return "wezterm"
    if env.get("WT_SESSION"):
        return "windows-terminal"
    return None


def executable(name, env):
    """The path of `name` where it is found, else `name` itself (a dry run prints it either way)."""
    found = shutil.which(name)
    if not found and name == "wezterm" and env.get("WEZTERM_EXECUTABLE_DIR"):
        candidate = Path(env["WEZTERM_EXECUTABLE_DIR"]) / (name + (".exe" if os.name == "nt" else ""))
        found = str(candidate) if candidate.exists() else None
    return found or name


def command(kind, live, cwd, env):
    """The argument list that splits the session's pane and runs `live` in the new one."""
    if kind == "tmux":
        args = ["split-window", "-d", "-h", "-l", f"{PANE_SHARE}%", "-c", str(cwd)]
        if env.get("TMUX_PANE"):
            args += ["-t", env["TMUX_PANE"]]
        return [executable("tmux", env), *args, join(live)]
    if kind == "wezterm":
        return [executable("wezterm", env), "cli", "split-pane", "--right", "--percent", str(PANE_SHARE),
                "--cwd", str(cwd), "--", *live]
    return [executable("wt", env), "-w", "0", "split-pane", "-V", "-s", f"{PANE_SHARE / 100:g}", "-d", str(cwd), *live]


def split(script, cwd, extra=(), dry_run=False, env=None, out=None):
    """Open the live view in a pane beside the session, or print what to run; the exit code, always 0."""
    env = os.environ if env is None else env
    out = out or sys.stdout
    live = live_command(script, extra)
    kind = splitter(env)
    if kind is None:
        out.write(HINT.format(command=join(live_command(script, extra, "python3"))) + "\n")
        return 0
    argv = command(kind, live, cwd, env)
    if dry_run:
        out.write(join(argv) + "\n")
        return 0
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=RUN_TIMEOUT, check=False)
        failure = (done.stderr or "").strip().splitlines()[-1:] if done.returncode else []
        if done.returncode and not failure:
            failure = [f"exit {done.returncode}"]
    except (OSError, subprocess.SubprocessError) as e:
        failure = [str(e)]
    if failure:
        print(f"kbmon: {kind} did not open the pane: {failure[0]}", file=sys.stderr)
        out.write(HINT.format(command=join(live_command(script, extra, "python3"))).split("\n", 1)[1] + "\n")
    return 0
