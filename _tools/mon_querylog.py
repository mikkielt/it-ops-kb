"""kbmon's querylog panel (kb/_self/monitoring.md): the spool's waiting rows by kind, the local store's entries not yet
delivered, the last distill and apply outcome, and today's usage rows with their tokens and cost in USD.

The panel reads the query log home of this copy of the tools (`ql_base.places`) through the structured readers of
`ql_report` and writes nothing. It carries counts, kinds, outcomes, times and commit hashes: no question, prompt or reply
text of the spool or the store. Cost is priced as `backlog.py cost` prices it (`bl_cost.price_usd`, at
`bench_core.PRICE`); a model the table has no price for adds nothing and is named. Imports `mon_base`, `ql_base` and
`ql_report`; `bl_cost` only when it prices. `alerts(data)` is the panel's judgement of its data (a refused delivery), which
`mon_view.judged` adds to the snapshot's `alerts`.
"""
import ql_base
import ql_report

REFRESH_S = 30  # seconds the live view serves the last result: the spool and the store are read whole
SHOWN_KINDS = 4  # spool kinds the text row names, most rows first, before it counts the rest
HASH_CHARS = 7


def tokens(models):
    """The tokens of {model: counts}: uncached input, cache writes, cache reads and output."""
    return sum(c[k] for c in models.values() for k in ("in", "cw", "cr", "out"))


def priced(models):
    """(USD rounded to cents' tenth, [models without a price]) of {model: counts}."""
    if not models:
        return 0.0, []
    import bl_cost
    usd, unpriced = bl_cost.price_usd(models)
    return round(usd, 4), unpriced


def delivery_of(outcome, qdir):
    """The `last_delivery` of the log's apply outcome: {outcome, why, when}, or None when the log has none. `why` is the
    failed gate and its first error line (`bl_land.last_push_failure`) of a push that delivered nothing, else empty."""
    if outcome is None:
        return None
    why = ""
    if outcome["outcome"] in ("refused", "fetch-failed"):
        import bl_land
        why = bl_land.last_push_failure(qdir / "store") or ""
    return {"outcome": outcome["outcome"], "why": why, "when": outcome["when"]}


def collect(ctx):
    qdir, cfg = ql_base.places()
    outcomes = ql_report.last_outcomes(qdir)
    models = ql_report.usage_today(qdir)
    usd, unpriced = priced(models["models"])
    waiting = ql_report.undelivered(qdir, cfg)
    return {"mode": ql_base.read_mode(cfg), "disabled": (qdir / ql_base.DISABLED_NAME).exists(),
            "spool": ql_report.spool_state(qdir / "spool"),
            "undelivered": waiting["entries"], "undelivered_runs": waiting["runs"],
            "undelivered_since": waiting["since"], "delivery_ref": waiting["ref"],
            "last_distill": outcomes["distill"], "last_delivery": delivery_of(outcomes["apply"], qdir),
            "last_pushed": ql_report.last_pushed(qdir),
            "usage_today": {"rows": models["rows"], "tokens": tokens(models["models"]), "usd": usd, "unpriced": unpriced}}


def when(text):
    """`2026-10-18T10:20:30Z` as `2026-10-18 10:20`."""
    return str(text)[:16].replace("T", " ") if text else "-"


def spool_row(data):
    spool = data.get("spool") or {}
    kinds = sorted((spool.get("by_kind") or {}).items(), key=lambda kn: (-kn[1], kn[0]))
    shown = " · ".join(f"{k} {n}" for k, n in kinds[:SHOWN_KINDS]) + (f" · +{len(kinds) - SHOWN_KINDS} more" if len(kinds) > SHOWN_KINDS else "")
    bad = f" · {spool['unreadable']} unreadable" if spool.get("unreadable") else ""
    return f"spool     {spool.get('rows', 0)} rows in {spool.get('files', 0)} files" + (f" · {shown}" if shown else "") + bad


def delivery_rows(data):
    """The delivery row: a refused push is a `!!` row, a fetch that failed or an origin ref that cannot be read a `! `
    row, any other outcome a plain one."""
    last, pushed = data.get("last_delivery"), data.get("last_pushed")
    n = data.get("undelivered", 0)
    since = data.get("undelivered_since")
    if last and last.get("outcome") == "refused":
        return ["!!delivery  REFUSED " + (last.get("why") or "no gate named") + (f" · since {when(since)}" if since else "")
                + f" · undelivered {n}"]
    row = f"delivery  undelivered {n}"
    row += f" · last pushed {pushed['commit'][:HASH_CHARS]} {when(pushed['when'])}" if pushed else " · nothing pushed yet"
    if last:
        row += f" · apply {last['outcome']}"
    flag = "! " if (last and last.get("outcome") == "fetch-failed") or (n and data.get("delivery_ref") is False) else ""
    return [flag + row if flag else row]


def alerts(data):
    """The alerts of the panel's data: one `delivery` alert (id `querylog.delivery`) while the log's last apply outcome is a
    refused run or a failed gate. A fetch that failed is a `! ` row only, and a later push that delivered clears it (the
    outcome is then `pushed`). `since` is the `HH:MM` (UTC) of the log's last write."""
    last = data.get("last_delivery")
    if not isinstance(last, dict) or last.get("outcome") != "refused":
        return []
    since = str(last.get("when") or "")[11:16]
    return [{"kind": "delivery", "id": "querylog.delivery", "panel": "querylog",
             "message": "query-log delivery REFUSED: " + (last.get("why") or "no gate named"), "since": since}]


def lines(data):
    """The body rows: the spool, the delivery (a refused one is a `!!` row), the distill outcome and today's usage."""
    mode = data.get("mode", "?")
    rows = [spool_row(data)] + delivery_rows(data)
    distill = data.get("last_distill")
    rows.append("distill   " + (distill["outcome"] + "".join(f" · {k} {distill[k]}" for k in ("entries", "dropped", "waiting")
                                                              if k in distill) if distill else "no run in the log")
                + (f" · mode {mode}" + (" · DISABLED" if data.get("disabled") else "")))
    u = data.get("usage_today") or {}
    row = f"today     {u.get('rows', 0)} usage rows · {u.get('tokens', 0)} tokens · ${u.get('usd', 0):.2f}"
    if u.get("unpriced"):
        row += f" · no price for {', '.join(u['unpriced'])}"
    return rows + [row]
