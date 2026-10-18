"""The scripted stand-in for `claude` in `benchmarks.py multi run --replay` (stdlib only).

`python3 bench_replay.py ROLE [--usage JSON] [--cost USD] [--question Q]... [--budget N] [--area A] [--holder H]` runs one
agent's role in the current directory (the agent's clone, or the worktree `backlog.py dispatch` made for a code item) and
makes no model call: a `lookup` agent runs `rag.py pack` on each question; a `research` agent runs `coord.py dedup` on its
area, commits one planted `_gaps.md` entry and runs `kbgit.py sync --push`; a `code` agent writes the planted files of its
item's touches, runs the item's check and commits them with the item's `KB-Work` trailer. It prints one stream-json result
event with the planted `--usage` (the four token counts and the turns) and `--cost`, and the commands it ran as `steps`;
the exit is 1 and the event an error when a command failed. The harness (bench_multi.py) reads the event as it reads a
session's and lands the code item itself. This module imports nothing of the project: it runs from the checkout that
started the benchmark, in the sandbox's clones.
"""
import argparse, json, shlex, subprocess, sys, time
from pathlib import Path

ITEM_DIR = "kb/_self/backlog"  # bench_multi.ITEM_DIR
GAP = ("\n## replay-{agent}\n\n- **A planted entry that a replayed research agent commits and syncs.** Nothing was tried; the entry "
       "exists to be pushed to the sandbox's bare. [UNK] (topic: {topic})\n")
PLANTED_CODE = {  # the file a replayed code agent writes for a touch of the planted items (kb/_self/reports/multi_bench.csv)
    "examples/multi-bench/slugify.py": '''"""A slugify helper for the multi-agent benchmark examples."""
import re
import unicodedata


def slugify(text):
    """Lowercase TEXT, turn accented letters into their base letters, put one hyphen for each run of other characters."""
    base = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
''',
    "examples/multi-bench/wordcount.py": '''"""A word counter for the multi-agent benchmark examples."""
import re


def count_words(text):
    """The number of times each lowercased word of TEXT occurs; a word is a run of letters and digits."""
    counts = {}
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        counts[word] = counts.get(word, 0) + 1
    return counts
''',
}


class Failed(Exception):
    pass


def run(argv, steps, label=None):
    """Run `argv` in the current directory, add its label to `steps`; Failed when it exits non-zero. Its stdout."""
    steps.append(label or shlex.join(argv))
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise Failed(f"{steps[-1]} exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
    return p.stdout


def tool(name):
    return str(Path("_tools") / name)


def lookup(a, steps):
    for q in a.question:
        run([sys.executable, tool("rag.py"), "pack", q, "--budget", str(a.budget)], steps, f"rag.py pack {q!r} --budget {a.budget}")


def research(a, steps):
    out = run([sys.executable, tool("coord.py"), "dedup", a.area, "--holder", a.holder], steps, f"coord.py dedup {a.area!r} --holder {a.holder}")
    topic = str(json.loads(out.strip().splitlines()[-1]).get("topic", "")).removeprefix("public/")
    if not (Path("kb/public") / (topic + ".md")).is_file():  # a gap names a topic the root has
        topic = next(f"{x.parent.name}/{x.stem}" for x in sorted(Path("kb/public").glob("*/*.md")) if not x.name.startswith("_"))
    with open(Path("kb/public/_gaps.md"), "a", encoding="utf-8", newline="\n") as f:
        f.write(GAP.format(agent=a.holder, topic=topic))
    run(["git", "add", "kb/public/_gaps.md"], steps)
    run(["git", "commit", "-q", "-m", f"docs(kb): replayed research gap of {a.holder} on {a.area}"], steps)
    last = ""
    for _ in range(3):  # another agent's push in the same moment moves the bare's main: sync again
        try:
            run([sys.executable, tool("kbgit.py"), "sync", "--push"], steps, "kbgit.py sync --push")
            return
        except Failed as e:
            last = str(e)
            steps.pop()
    raise Failed(last)


def code(a, steps):
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], steps).strip()
    iid = branch.removeprefix("work/")
    item = json.loads((Path(ITEM_DIR) / f"{iid}.json").read_text(encoding="utf-8"))
    for touch in item["touches"]:
        if touch not in PLANTED_CODE:
            raise Failed(f"no planted change for {touch}")
        path = Path(touch)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PLANTED_CODE[touch], encoding="utf-8", newline="\n")
    for chk in item.get("checks", []):
        run(chk["run"], steps, "item check: " + shlex.join(chk["run"])[:80])
    run(["git", "add", "--", *item["touches"]], steps)
    run(["git", "commit", "-q", "-m", f"feat: {item['title']}\n\nKB-Work: {iid}"], steps)


ROLES = {"lookup": lookup, "research": research, "code": code}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("role", choices=list(ROLES))
    ap.add_argument("--usage", default="{}", help="json: input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, num_turns")
    ap.add_argument("--cost", type=float, default=0.0)
    ap.add_argument("--question", action="append", default=[])
    ap.add_argument("--budget", type=int, default=1200)
    ap.add_argument("--area", default="")
    ap.add_argument("--holder", default="agent")
    a = ap.parse_args(argv)
    usage, steps, t = json.loads(a.usage), [], time.time()
    try:
        ROLES[a.role](a, steps)
        error = ""
    except (Failed, OSError, KeyError, ValueError, StopIteration) as e:
        error = f"replay: {e}"
    turns = int(usage.pop("num_turns", 1))
    print(json.dumps({"type": "result", "subtype": "error_replay" if error else "success", "is_error": bool(error), "result": error or "replayed",
                      "duration_api_ms": int((time.time() - t) * 1000), "total_cost_usd": a.cost, "num_turns": turns, "usage": usage,
                      "steps": steps}))
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
