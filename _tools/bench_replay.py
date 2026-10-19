"""The scripted stand-in for `claude` in `benchmarks.py multi run --replay` (stdlib only).

`python3 bench_replay.py ROLE [--usage JSON] [--cost USD] [--question Q]... [--budget N] [--area A] [--holder H] [--plant P]`
runs one agent's role in the current directory (the agent's clone, or the worktree `backlog.py dispatch` made for a code
item) and makes no model call: a `lookup` agent runs `rag.py pack` on each question; a `research` agent claims the key
`research:replay:HOLDER` (with a `claim` event), runs `coord.py dedup` on its area, commits one planted `_gaps.md` entry,
runs `kbgit.py sync --push`, then releases its claim (with a `release` event); a `code` agent writes the planted files of
its item's touches, runs the item's check and commits them with the item's `KB-Work` trailer. `--plant lost-claim` makes a
research agent end with its claim held and `--plant land-stop` makes a code agent leave its change uncommitted, so the
item cannot land, and `--plant dup-research` makes a research agent skip `coord.py dedup`: it claims the key
`research:TOPIC:replay-planted-term` (a claim a shared store refuses to the second agent, which goes on), adds the planted fact
for that term to an article, commits and syncs it, and holds its claim a few seconds before the release: two such agents
write one fact: the faults `benchmarks.py multi check` finds. `--plant leak-output` (a lookup agent), `leak-commit` and
`leak-event` (research agents) make an agent write the canary of another agent, which the file named by the variable
MULTI_LEAK_CANARY_FILE holds, to its result text, to the planted `_gaps.md` entry it commits and syncs, or to a coord event it posts.
The roles `bare-lookup`, `bare-research` and `bare-code` stand in for the bare twins of `multi run --bare`, which have no kb
tooling: `bare-lookup` runs nothing, `bare-research` writes NOTES.md in the current directory (the sandbox of the twin), and
`bare-code [--title T] [--touch PATH]... [--check JSON]` writes the planted files of the touches, runs the check and commits them with
plain git, with no `KB-Work` trailer.
It prints one stream-json result
event with the planted `--usage` (the four token counts and the turns) and `--cost`, and the commands it ran as `steps`;
the exit is 1 and the event an error when a command failed. The harness (bench_multi.py) reads the event as it reads a
session's and lands the code item itself. This module imports nothing of the project: it runs from the checkout that
started the benchmark, in the sandbox's clones.
"""
import argparse, json, os, re, shlex, subprocess, sys, time
from pathlib import Path

ITEM_DIR = "kb/_self/backlog"  # bench_multi.ITEM_DIR
CLAIM_TTL = 3600  # seconds a replayed research agent's claim lasts
PLANTS = ("lost-claim", "land-stop", "dup-research", "leak-output", "leak-commit", "leak-event")  # bench_multi.PLANTS' names
LEAK_ENV = "MULTI_LEAK_CANARY_FILE"  # bench_multi.LEAK_ENV: the file that holds the canary of another agent
PLANT_TERM = "replay-planted-term"  # the research term of --plant dup-research
PLANT_HOLD = 5  # seconds a dup-research agent holds its claim at least, so another agent's fact lands inside it
GAP = ("\n## replay-{agent}\n\n- **A planted entry that a replayed research agent commits and syncs.** Nothing was tried; the entry "
       "exists to be pushed to the sandbox's bare. [UNK] (topic: {topic}){note}\n")
PLANT_FACT = ("- A planted fact about {term}: two replayed research agents that skip the dedup claim of one research term write this "
              "one fact each. [UNK]")
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


def coord_event(kind, key, holder, steps, *extra):
    run([sys.executable, tool("coord.py"), "post", "--kind", kind, "--field", f"key={key}", "--field", f"holder={holder}", *extra], steps,
        f"coord.py post --kind {kind} {key}")


def leaked():
    """The canary of another agent that a --plant leak-* agent writes where it must not."""
    path = os.environ.get(LEAK_ENV)
    if not path:
        raise Failed(f"a leak plant needs {LEAK_ENV}: the file of the canary to write")
    return Path(path).read_text(encoding="utf-8").strip()


def plant_article():
    """(topic, path) of the first article of kb/public with at least four bullets under `## Facts`, the topic as the dedup key
    names it (`public/domain/slug`)."""
    for path in sorted(Path("kb/public").glob("*/*.md")):
        if not path.name.startswith("_") and len(fact_bullets(path.read_text(encoding="utf-8").splitlines())) >= 4:
            return f"public/{path.parent.name}/{path.stem}", path
    raise Failed("no article of kb/public has four bullets under ## Facts")


def fact_bullets(lines):
    """The indexes of the bullet lines under `## Facts`."""
    out, inside = [], False
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            inside = ln.strip() == "## Facts"
        elif inside and ln.startswith("- "):
            out.append(i)
    return out


def dup_research(a, steps):
    """--plant dup-research: no `coord.py dedup`. The agent claims the planted term's key and goes on when the store refuses it
    (another agent holds it), writes the planted fact into the article (after the first bullet of `## Facts` for an odd
    agent, after the last for an even one, so two agents' commits merge), commits and syncs it, and keeps a claim it got
    PLANT_HOLD seconds, then releases it."""
    topic, path = plant_article()
    key, token, begun = f"research:{topic}:{PLANT_TERM}", "", time.time()
    try:
        token = json.loads(run([sys.executable, tool("coord.py"), "claim", key, "--ttl", str(CLAIM_TTL), "--holder", a.holder], steps,
                               f"coord.py claim {key} --holder {a.holder}"))["token"]
        coord_event("claim", key, a.holder, steps)
    except Failed:
        pass  # a shared store holds it for another agent: the agent does not look, and writes the fact
    lines = path.read_text(encoding="utf-8").splitlines()
    bullets = fact_bullets(lines)
    at = bullets[0] if int(re.sub(r"\D", "", a.holder) or 0) % 2 else bullets[-1]
    lines.insert(at + 1, PLANT_FACT.format(term=PLANT_TERM))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    run(["git", "add", str(path)], steps)
    run(["git", "commit", "-q", "-m", f"docs(kb): replayed research fact of {a.holder} on {PLANT_TERM}"], steps)
    sync_push(steps)
    if token:
        time.sleep(max(0.0, PLANT_HOLD - (time.time() - begun)))
        run([sys.executable, tool("coord.py"), "release", key, "--token", token], steps, f"coord.py release {key}")
        coord_event("release", key, a.holder, steps)


def sync_push(steps):
    """`kbgit.py sync --push`, again up to twice when another agent's push moves the bare's main in the same moment."""
    last = ""
    for _ in range(3):
        try:
            run([sys.executable, tool("kbgit.py"), "sync", "--push"], steps, "kbgit.py sync --push")
            return
        except Failed as e:
            last = str(e)
            steps.pop()
    raise Failed(last)


def research(a, steps):
    if a.plant == "dup-research":
        return dup_research(a, steps)
    canary = leaked() if a.plant in ("leak-commit", "leak-event") else ""
    key = f"research:replay:{a.holder}"
    token = json.loads(run([sys.executable, tool("coord.py"), "claim", key, "--ttl", str(CLAIM_TTL), "--holder", a.holder], steps,
                           f"coord.py claim {key} --holder {a.holder}"))["token"]
    coord_event("claim", key, a.holder, steps)
    if a.plant == "leak-event":
        coord_event("lesson", key, a.holder, steps, "--field", f"note={canary}")
    out = run([sys.executable, tool("coord.py"), "dedup", a.area, "--holder", a.holder], steps, f"coord.py dedup {a.area!r} --holder {a.holder}")
    topic = str(json.loads(out.strip().splitlines()[-1]).get("topic", "")).removeprefix("public/")
    if not (Path("kb/public") / (topic + ".md")).is_file():  # a gap names a topic the root has
        topic = next(f"{x.parent.name}/{x.stem}" for x in sorted(Path("kb/public").glob("*/*.md")) if not x.name.startswith("_"))
    with open(Path("kb/public/_gaps.md"), "a", encoding="utf-8", newline="\n") as f:
        f.write(GAP.format(agent=a.holder, topic=topic, note=f" The entry holds {canary}." if a.plant == "leak-commit" else ""))
    run(["git", "add", "kb/public/_gaps.md"], steps)
    run(["git", "commit", "-q", "-m", f"docs(kb): replayed research gap of {a.holder} on {a.area}"], steps)
    sync_push(steps)
    if a.plant != "lost-claim":
        run([sys.executable, tool("coord.py"), "release", key, "--token", token], steps, f"coord.py release {key}")
        coord_event("release", key, a.holder, steps)


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
    if a.plant == "land-stop":
        return
    run(["git", "add", "--", *item["touches"]], steps)
    run(["git", "commit", "-q", "-m", f"feat: {item['title']}\n\nKB-Work: {iid}"], steps)


def bare_lookup(a, steps):
    """A bare lookup twin: no command to run (it answers from the web, which a replay does not reach)."""


def bare_research(a, steps):
    """A bare research twin: its notes in NOTES.md of the current directory, a line for the area and no source url."""
    steps.append("write NOTES.md")
    Path("NOTES.md").write_text(f"- A planted note of a replayed bare research twin on {a.area}.\n", encoding="utf-8", newline="\n")


def bare_code(a, steps):
    """A bare code twin: the planted file of each touch, the check run and one plain `git commit` of the touches."""
    for touch in a.touch:
        if touch not in PLANTED_CODE:
            raise Failed(f"no planted change for {touch}")
        path = Path(touch)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PLANTED_CODE[touch], encoding="utf-8", newline="\n")
    if a.check:
        run(json.loads(a.check), steps, "item check: " + shlex.join(json.loads(a.check))[:80])
    run(["git", "add", "--", *a.touch], steps)
    run(["git", "commit", "-q", "-m", f"feat: {a.title}"], steps)


ROLES = {"lookup": lookup, "research": research, "code": code, "bare-lookup": bare_lookup, "bare-research": bare_research,
         "bare-code": bare_code}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("role", choices=list(ROLES))
    ap.add_argument("--usage", default="{}", help="json: input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, num_turns")
    ap.add_argument("--cost", type=float, default=0.0)
    ap.add_argument("--question", action="append", default=[])
    ap.add_argument("--budget", type=int, default=1200)
    ap.add_argument("--area", default="")
    ap.add_argument("--holder", default="agent")
    ap.add_argument("--title", default="a planted change", help="bare-code: the commit's subject")
    ap.add_argument("--touch", action="append", default=[], help="bare-code: a file to write")
    ap.add_argument("--check", default="", help="bare-code: the item's check, a json argv")
    ap.add_argument("--plant", choices=PLANTS, default="", help="a fault the role makes on purpose")
    a = ap.parse_args(argv)
    usage, steps, t, shown = json.loads(a.usage), [], time.time(), ""
    try:
        ROLES[a.role](a, steps)
        error, shown = "", " " + leaked() if a.plant == "leak-output" else ""
    except (Failed, OSError, KeyError, ValueError, StopIteration) as e:
        error = f"replay: {e}"
    turns = int(usage.pop("num_turns", 1))
    print(json.dumps({"type": "result", "subtype": "error_replay" if error else "success", "is_error": bool(error), "result": error or "replayed" + shown,
                      "duration_api_ms": int((time.time() - t) * 1000), "total_cost_usd": a.cost, "num_turns": turns, "usage": usage,
                      "steps": steps}))
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
