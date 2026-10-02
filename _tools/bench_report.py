"""The benchmarks' report tables: the results file's rows as the generated tables of kb/_self/reports/benchmarks.md,
and the check of the numbers in README.md against them (stdlib only).

benchmarks.py's `report` command calls these; this module imports no sibling (kb/_self/code.md, Layout and Imports).
"""
import re

# numbers in README.md that are not measurements (names, versions of models, licences, rules, placeholders)
NOT_MEASURED = [r"Haiku 4\.5", r"Sonnet 5", r"Opus 5\.5", r"Apache-2\.0", r"CC BY 4\.0", r"\b25 words", r"PL-LT-00123",
                r"census-YYYY-MM-DD", r"BM25", r"\b1-2 tool calls", r"Python 3\.\d+"]

# ---------------------------------------------------------------------------------------------------- report tables

NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers(text):
    return [float(m.replace(",", "")) for m in NUM.findall(str(text))]


def num(v):
    """The value as one number: itself, or the mean of the numbers a historical cell holds (`$0.043 / $0.051`, a
    range `9-12 s`); None when it holds none, or several of different kinds (`2/2`)."""
    s = str(v).strip()
    if not s or re.search(r"\d+ ?(/|of) ?\d+", s):  # a count of a total (`2/2`, `11 of 14`) has no one value
        return None
    try:
        return float(s)
    except ValueError:
        pass
    s = re.sub(r"\([^)]*\)", " ", s)  # `22,038 (all 4)`: the words in brackets qualify the number
    s = re.sub(r"(\d[\d,]*(?:\.\d+)?)k\b", lambda m: str(float(m.group(1).replace(",", "")) * 1000), s)
    ns = [abs(n) for n in numbers(re.sub(r"(\d)-(\d)", r"\1 \2", s))]
    return sum(ns) / len(ns) if ns else None


FORMATS = {"cost": "${:.3f}", "cost_est": "${:.3f}", "wall_s": "{:.0f} s", "api_s": "{:.0f} s", "input": "{:,.0f}",
           "out": "{:,.0f}", "turns": "g1", "tool_calls": "g1", "files_read": "g1", "requests": "g1", "start_ctx": "{:,.0f}",
           "effective_input": "{:,.0f}", "chars_per_s": "{:,.0f}", "median_us": "{:.1f} us", "size_mb": "{:.1f} MB",
           "input_per_entry": "{:,.0f}", "out_per_entry": "{:,.0f}", "cost_per_fact": "${:.3f}",
           "ms": "{:.1f} ms", "s": "{:.2f} s", "time": "{:.2f} s", "pct": "{:.1f}%", "ratio": "{:.2f}x"}


def fmt(metric, v):
    """A value as the tables show it: numbers from a run with the metric's format, anything else as written."""
    s = str(v)
    try:
        x = float(s)
    except ValueError:
        return s
    kind = metric if metric in FORMATS else metric.rsplit("_", 1)[-1]
    f = FORMATS.get(kind)
    if f == "g1":
        return f"{round(x, 1):g}"
    if f:
        return f.format(x)
    return f"{x:,.0f}" if x == int(x) and abs(x) >= 1000 else (f"{x:g}")


def change(a, b):
    x, y = num(a), num(b)
    if x is None or y is None or x == 0:
        return ""
    return f" ({(y - x) / x * 100:+.0f}%)"


ARMED = ("navigation",)  # the scenarios whose record holds one set of rows per arm (bench_core.ARMED, tested equal)


def records(rows, scenario):
    """The scenario's records in date order (history first when a date ties): [(record, first row)]; an ARMED
    scenario's record appears once per arm, as (record, first row of that arm), so each arm's commit shows."""
    seen = {}
    for r in rows:
        if r["scenario"] == scenario:
            seen.setdefault((r["record"], r["arm"] if scenario in ARMED else ""), r)
    order = list(seen)
    return sorted(((k[0], r) for k, r in seen.items()),
                  key=lambda kv: (kv[1]["date"], kv[0] == kv[1]["date"], order.index((kv[0], kv[1]["arm"] if scenario in ARMED else ""))))


def table(rows, scenario, metrics, cases=None, arms=None):
    """A Markdown table: one line per case and arm, a column per metric; each cell holds every record's value in date
    order, `->` between them, and the change of the last from the one before."""
    order = list(dict.fromkeys(rec for rec, _ in records(rows, scenario)))
    cells, keys = {}, []
    for r in rows:
        if r["scenario"] != scenario or r["metric"] not in metrics:
            continue
        if (cases and r["case"] not in cases) or (arms and r["arm"] not in arms):
            continue
        k = (r["case"], r["arm"])
        if k not in keys:
            keys.append(k)
        cells.setdefault((k, r["metric"]), {})[r["record"]] = r["value"]
    out = ["| case | arm | " + " | ".join(metrics) + " |", "|---|---|" + "---|" * len(metrics)]
    for k in keys:
        line = []
        for m in metrics:
            vals = [(rec, cells.get((k, m), {}).get(rec)) for rec in order]
            vals = [(rec, v) for rec, v in vals if v not in (None, "")]
            text = " -> ".join(fmt(m, v) for _, v in vals)
            if len(vals) >= 2:
                text += change(vals[-2][1], vals[-1][1])
            line.append(text or "-")
        out.append(f"| {k[0] or '-'} | {k[1] or '-'} | " + " | ".join(line) + " |")
    return "\n".join(out)


def records_table(rows, scenario):
    out = ["| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |", "|---|---|---|---|---|---|---|"]
    for rec, first in records(rows, scenario):
        mine = [r for r in rows if r["scenario"] == scenario and r["record"] == rec
                and (scenario not in ARMED or r["arm"] == first["arm"])]
        counts = [r["runs"] for r in mine if r["runs"] and r["case"] != "all paid runs"]
        runs = [max(sorted(set(counts), key=float), key=counts.count)] if counts else []  # the most common; ties: the smallest
        total = [float(r["value"]) for r in mine if r["metric"] == "spend_usd" and _isnum(r["value"])]
        spend = total[0] if total else sum(float(r["value"]) * float(r["runs"] or 1) for r in mine
                                           if r["metric"] in ("cost", "cost_est") and _isnum(r["value"]))
        label = f"{rec} ({first['arm']})" if scenario in ARMED and first["arm"] else rec
        out.append(f"| {label} | {first['date'] or '-'} | {first['commit'] or '-'} | {first['claude_code'] or '-'} | "
                   f"{first['kb_topics'] or '-'} | {', '.join(runs) or '-'} | {('$%.2f' % spend) if spend else '-'} |")
    return "\n".join(out)


def _isnum(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


BLOCK = re.compile(r"(<!-- bench:(table|records|spend)((?: [^\n]*?)?) -->\n)(.*?)(<!-- /bench -->)", re.S)
OPT = re.compile(r"(\w+)=(.*?)(?= \w+=|$)")


def spend_table(rows):
    """Each scenario's spend per record: paid runs, input and output tokens, dollars (its `all paid runs` rows)."""
    got = {}
    for r in rows:
        if r["case"] == "all paid runs":
            got.setdefault((r["scenario"], r["record"], r["arm"]), {"runs": r["runs"]})[r["metric"]] = r["value"]
    merged = {}  # an ARMED scenario's record holds one spend per arm: their sum
    for (scen, rec, _), v in sorted(got.items()):
        m = merged.setdefault((scen, rec), {"runs": 0})
        m["runs"] += int(v["runs"] or 0)
        for k in ("spend_input_tokens", "spend_output_tokens", "spend_usd"):
            m[k] = m.get(k, 0) + float(v.get(k, 0))
    out = ["| scenario | record | paid runs | input tokens | output tokens | spend |", "|---|---|---|---|---|---|"]
    tot = [0, 0.0, 0.0, 0.0]
    for (scen, rec), v in sorted(merged.items()):
        inp, outp, usd = (v.get(k, 0) for k in ("spend_input_tokens", "spend_output_tokens", "spend_usd"))
        tot = [tot[0] + v["runs"], tot[1] + inp, tot[2] + outp, tot[3] + usd]
        out.append(f"| {scen} | {rec} | {v['runs']} | {inp:,.0f} | {outp:,.0f} | ${usd:.2f} |")
    out.append(f"| all | | {tot[0]} | {tot[1]:,.0f} | {tot[2]:,.0f} | ${tot[3]:.2f} |")
    return "\n".join(out)


def render(text, rows):
    """The report text with every generated block rewritten from `rows`."""
    def one(m):
        kind, rest = m.group(2), m.group(3).strip()
        scen, _, rest = rest.partition(" ")
        opts = dict(OPT.findall(rest))
        if kind == "spend":
            body = spend_table(rows)
        elif kind == "records":
            body = records_table(rows, scen)
        else:
            split = lambda k: opts[k].split(",") if k in opts else None  # noqa: E731
            body = table(rows, scen, split("metrics"), split("cases"), split("arms"))
        return m.group(1) + body + "\n" + m.group(5)
    return BLOCK.sub(one, text)


def readme_misses(text, rows):
    """Numbers in `text` (README.md) that match no row of the results file at the precision and unit written: a
    value, a Claude Code version, a kb size, a run count or a number inside a row's text."""
    for pat in NOT_MEASURED:
        text = re.sub(pat, " ", text)
    text = re.sub(r"`[^`]*`|\(https?://[^)]*\)|kb/_self/\S+", " ", text)  # code, links and paths hold no measurements
    pool = []
    for r in rows:
        for k in ("value", "claude_code", "kb_topics", "runs", "note"):
            pool += numbers(r[k]) if k != "value" or not _isnum(r[k]) else [float(r[k])]
    pool = sorted(set(pool))
    versions = {r["claude_code"] for r in rows}
    misses = []
    for m in re.finditer(r"(\$?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)*)(k|M\b|x| ?%)?", text):
        raw, unit = m.group(2), (m.group(3) or "").strip()
        if raw.count(".") > 1:
            if raw not in versions:
                misses.append(m.group(0))
            continue
        if raw in ("0", "1", "2") and not unit and not m.group(1):
            continue  # counting words written as digits ("1-2 tool calls")
        n = float(raw.replace(",", ""))
        dec = len(raw.split(".")[1]) if "." in raw else 0
        tol = 0.5 * 10 ** -dec + 1e-9
        scale = {"k": 1000, "M": 1000000}.get(unit, 1)
        if not any(abs(v / scale - n) <= tol or abs(v - n) <= tol for v in pool):
            misses.append(m.group(0))
    return misses
