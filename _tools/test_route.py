"""The route a pack prints (`python3 _tools/tests.py -k TestRoute`).

TestRoute   kbfacts.pack and pack_many: a weak, a none and a check-flagged good pack print `route:`, `kb has:` and
            `kb lacks:` after the coverage, check:, freshness: and none-sentence lines and before the first article; a
            clean good pack prints none of them; `has` and `lacks` are the question's own words in question order;
            a none whose only missing words are language or format names routes split and prints its facts and source
            footer with no none sentence, as a weak pack would; route_of names each flagged case; a several-part pack starts with one overall route line.
TestRouteEvalSet   every lookup_eval.csv row expected good, read on HEAD (no stored pack text): a clean good pack
            prints no route, kb has or kb lacks line, a flagged one prints `route: split`, and every good pack routed
            split has a check: line or a word nowhere in the kb, so a rule that demotes clean goods fails; the
            check on one pack is planted-failure tested.
TestRouteEvalEndToEnd   route_eval_end_to_end: every lookup_eval.csv question, some planted several-part joins of
            them ("(1) a covered one (2) an off-kb one") and the near misses above, through kbfacts.pack, the kb: hook
            in process (kb_hook.answer, as `kb_hook.py --test` prints it) and kb_ask.plan with the prompts its run
            would send (no model): the hook lets every routed pack through, no prompt names `kb has: -` or
            `kb lacks: -` as a part, every part of a several-part split reaches the reader or the researcher, and a
            pack that routes split carries no none sentence; each check is planted-failure tested.
"""
import collections, re

import kb_ask
import kb_hook
import kbfacts
import rag

OTHER_NONE_Q = "How do I configure VMware Horizon instant clones?"
OTHER_CLEAN_Q = "Does deleting an Entra device also delete its BitLocker recovery keys?"
NEAR_MISS_Q = ("Show T-SQL that takes an exclusive session-owned application lock without waiting, fails if it is held, "
               "and releases it.")  # none, and t-sql is the only word nowhere in the kb
NONE_Q = "How do I run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances?"
WEAK_Q = "email attachment size"
FLAGGED_Q = "How do I integrate ServiceNow with Intune?"  # good, its check: line names ServiceNow
SPREAD_Q = "Which Graph API migrates mailboxes, calendars and contacts between tenants?"  # good, spread check: line
CLEAN_Q = "What is the default Windows LAPS password length?"
FRESH_NONE_Q = "What is the latest Intune ServiceNow connector version 9.9.9?"  # freshness: line, then none sentence

ROUTE_LINES = ("route: ", "kb has: ", "kb lacks: ")
PRELUDE = ("coverage: ", "check: ", "freshness: ", "The kb does not cover this.")


def route_block(text):
    """(lines before the route block, the three route lines, the lines after) of a pack's text."""
    lines = text.splitlines()
    at = next(n for n, ln in enumerate(lines) if ln.startswith("route: "))
    return lines[:at], lines[at:at + 3], lines[at + 3:]


def assert_placed(res):
    before, block, after = route_block(res["text"])
    assert before and all(ln.startswith(PRELUDE) for ln in before), before
    assert before[0].startswith("coverage: "), before
    assert [ln.startswith(p) for ln, p in zip(block, ROUTE_LINES)] == [True] * 3, block
    assert block[0] == f"route: {res['route']}", block
    assert after[:1] in ([""], []), "the block ends before the first article: " + repr(after[:2])
    assert not any(ln.startswith(ROUTE_LINES) for ln in after), "the block prints once"


class TestRoute:
    def test_none_routes_web_after_the_none_sentence(self):
        res = kbfacts.pack(NONE_Q)
        assert res["verdict"] == "none" and res["route"] == "web"
        assert_placed(res)
        before, block, after = route_block(res["text"])
        assert before[-1].startswith("The kb does not cover this."), before
        assert after[1].startswith("## "), "the first article follows the route lines"
        # the question's own words, not stems: `Kubernetes`, `Cluster`, `instances`
        assert block[1].startswith("kb has: ") and "Kubernetes" in block[1] and "instances" in block[1], block
        assert block[2].startswith("kb lacks: ") and "Autoscaler" in block[2] and "EKS" in block[2], block

    def test_near_miss_none_routes_split_not_web(self):
        res = kbfacts.pack(NEAR_MISS_Q)
        assert res["verdict"] == "none" and res["missing"] == ["t-sql"], (res["verdict"], res["missing"])
        assert res["route"] == "split", res["route"]
        assert_placed(res)
        assert "route: split" in res["text"].splitlines() and "route: web" not in res["text"].splitlines()
        # the Kubernetes question is none with 4 of 6 key words matched, autoscaler and eks nowhere: not a near miss
        off = kbfacts.pack(NONE_Q)
        assert off["missing"] == ["autoscaler", "eks"] and len(off["matched"]) == 4, (off["missing"], off["matched"])
        assert off["route"] == "web"

    def test_near_miss_none_prints_what_a_weak_pack_would(self):
        # the h2_applock question: the reader answers the sp_getapplock part, so no sentence forbids the hits, every
        # picked line of the article prints (not the none pack's first two) and the source footer stays
        res = kbfacts.pack(NEAR_MISS_Q)
        lines = res["text"].splitlines()
        assert kbfacts.NONE_SENTENCE not in lines and "Do not answer from the hits" not in res["text"], lines[:3]
        assert res["paths"][0] == "public/sqlserver/sp-getapplock.md", res["paths"]
        facts = [ln for ln in lines if ln.startswith("- public/sqlserver/sp-getapplock.md:")]
        code = [ln for ln in lines if ln.startswith("  ") and not ln.startswith("  ->")]  # the picked snippet's code
        assert len(facts) > 2 and any("@LockTimeout = 0" in ln for ln in code), code
        assert any("sp_releaseapplock" in ln for ln in code), code
        assert res["sources"] == ["S467"] and "sources:" in lines, res["sources"]
        assert any(ln.startswith("  -> S467  https://") for ln in lines), lines[-3:]
        # a none that routes web keeps its none behaviour: the sentence, two lines of one article, no footer
        off = kbfacts.pack(NONE_Q)
        off_lines = off["text"].splitlines()
        assert kbfacts.NONE_SENTENCE in off_lines and off["sources"] == [] and "sources:" not in off_lines
        assert sum(1 for ln in off_lines if ln.startswith("## ")) <= 1
        assert sum(1 for ln in off_lines if ln.startswith("- ")) <= 2

    def test_pack_prints_snippet_code(self):
        # a picked SNIPPET: bullet brings the fenced block below it, indented under the bullet, and the budget counts it
        res = kbfacts.pack(NEAR_MISS_Q)
        lines = res["text"].splitlines()
        at = next(i for i, ln in enumerate(lines) if ".md:44 SNIPPET:" in ln)
        assert "sp_getapplock" in lines[at + 2] and "@LockTimeout = 0" in lines[at + 3], lines[at:at + 8]
        assert "sp_releaseapplock" in lines[at + 6] and not lines[at + 7].strip(), lines[at:at + 8]
        assert len("\n".join(lines)) < int(1200 * 3.5) + 600
        # a pack that picks no snippet prints no indented code
        good = kbfacts.pack(CLEAN_Q)["text"].splitlines()
        assert not [ln for ln in good if ln.startswith("  ") and not ln.startswith(("  ->", "  (+"))], good

    def test_several_parts_with_a_near_miss_route_split(self):
        res = kbfacts.pack_many([NEAR_MISS_Q, NONE_Q])
        assert res["route"] == "split" and res["text"].splitlines()[0] == "route: split"
        assert kbfacts.pack_many([NONE_Q, OTHER_NONE_Q])["route"] == "web"

    def test_weak_routes_split(self):
        res = kbfacts.pack(WEAK_Q)
        assert res["verdict"] == "weak" and res["route"] == "split", (res["verdict"], res["route"])
        assert_placed(res)
        assert route_block(res["text"])[1][1:] == ["kb has: email, attachment", "kb lacks: size"]

    def test_check_flagged_good_routes_split_after_the_check_line(self):
        for q, kind in ((FLAGGED_Q, "never mentions ServiceNow"), (SPREAD_Q, "no single fact holds half")):
            res = kbfacts.pack(q)
            assert res["verdict"] == "good" and res["route"] == "split", (q, res["verdict"], res["route"])
            assert_placed(res)
            before = route_block(res["text"])[0]
            assert before[1].startswith("check: ") and kind in before[1], before
            assert res["text"].splitlines()[1].startswith("check: "), "check: stays on the second line"
        assert route_block(kbfacts.pack(FLAGGED_Q)["text"])[1][2] == "kb lacks: ServiceNow"

    def test_freshness_line_comes_before_the_route_lines(self):
        res = kbfacts.pack(FRESH_NONE_Q)
        assert res["route"], res["verdict"]
        assert_placed(res)
        before = route_block(res["text"])[0]
        assert any(ln.startswith("freshness: ") for ln in before), before
        if res["verdict"] == "none":
            assert before[-1].startswith("The kb does not cover this."), "the none sentence comes last"

    def test_clean_good_prints_no_route(self):
        res = kbfacts.pack(CLEAN_Q)
        assert res["verdict"] == "good" and res["route"] is None
        assert not any(ln.startswith(ROUTE_LINES) for ln in res["text"].splitlines()), res["text"][:300]
        assert res["text"].splitlines()[1] == "", "the clean good pack goes from coverage to the first article"
        # has and lacks are still returned to callers
        assert "LAPS" in res["has"] and isinstance(res["lacks"], list)

    def test_route_of_names_each_flagged_case(self):
        assert kbfacts.route_of("none", [], None, []) == "web"
        assert kbfacts.route_of("none", [], None, ["t-sql"]) == "split", "a near miss: only a language name is missing"
        assert kbfacts.route_of("none", [], None, ["t-sql", "json", "powershell"]) == "split"
        assert kbfacts.route_of("none", [], None, ["t-sql", "eks"]) == "web", "one other missing word: not a near miss"
        assert kbfacts.route_of("none", [], None, ["autoscaler", "eks"]) == "web"
        assert kbfacts.route_of("none", ["servicenow"], None, []) == "web", "no missing word: web, not a near miss"
        assert kbfacts.route_of("weak", [], None, []) == "split"
        assert kbfacts.route_of("good", ["servicenow"], None, []) == "split"
        assert kbfacts.route_of("good", [], (1, 6), []) == "split"
        assert kbfacts.route_of("good", [], None, ["eks"]) == "split", "a word nowhere in the kb flags a good pack"
        assert kbfacts.route_of("good", [], None, []) is None, "a clean good pack routes nowhere"

    def test_own_words_keep_question_order_and_spelling(self):
        stems = {kbfacts.stem(w) for w in ("passwords", "length", "windows")}
        assert kbfacts.own_words("What is the Windows LAPS length of passwords, Windows again?", stems) == \
            ["Windows", "length", "passwords"]
        assert kbfacts.own_words("What is the of?", stems) == []

    def test_several_parts_start_with_one_overall_route_line(self):
        def first(parts):
            res = kbfacts.pack_many(parts)
            lines = res["text"].splitlines()
            return res, lines[0], sum(ln.startswith("route: ") for ln in lines) - 1
        res, top, _ = first([NONE_Q, OTHER_NONE_Q])
        assert res["route"] == "web" and top == "route: web" and res["text"].splitlines()[1].startswith("# Q1: ")
        res, top, _ = first([NONE_Q, CLEAN_Q])
        assert res["route"] == "split" and top == "route: split", "not every part routes web"
        res, top, parts_route = first([CLEAN_Q, WEAK_Q])
        assert res["route"] == "split" and top == "route: split" and parts_route >= 1
        res, top, _ = first([CLEAN_Q, OTHER_CLEAN_Q])
        assert res["route"] is None and top.startswith("# Q1: "), "clean good parts print no route line"
        assert not any(ln.startswith(ROUTE_LINES) for ln in res["text"].splitlines())

    def test_a_single_question_prints_exactly_the_packs_text(self):
        for q in (CLEAN_Q, WEAK_Q, NONE_Q):
            assert kbfacts.pack_many([q])["text"] == kbfacts.pack(q)["text"], q


def good_pack_problems(res):
    """What is wrong with a `good` pack of the eval set, as a list of strings (empty: fine). A clean good pack (no
    check: line, no word nowhere in the kb) prints no route, kb has or kb lacks line; a flagged one routes split and
    prints the block once. A route without a check: line or a missing word is a demoted clean good."""
    lines = res["text"].splitlines()
    checked = any(ln.startswith("check: ") for ln in lines)
    flagged = checked or bool(res["missing"])
    routed = [ln for ln in lines if ln.startswith(ROUTE_LINES)]
    out = []
    if flagged:
        if res["route"] != "split" or lines.count("route: split") != 1:
            out.append(f"flagged (check: {checked}, missing {res['missing']}) but route {res['route']!r}")
        if len(routed) != 3:
            out.append(f"flagged but {len(routed)} route lines")
    else:
        if res["route"] is not None or routed:
            out.append(f"clean good but route {res['route']!r} and {len(routed)} route lines")
    return out


class TestRouteEvalSet:
    def test_clean_good_packs_keep_their_text_and_flagged_ones_route_split(self):
        cases = [(root, c) for root, c in rag.eval_cases() if c["expect_verdict"] == "good"]
        assert cases, "the eval set has no row expected good"
        bad, clean, flagged = [], 0, 0
        for root, c in cases:
            res = kbfacts.pack(c["question"])
            if res["verdict"] != "good":  # the verdict itself is `rag.py eval`'s check
                continue
            problems = good_pack_problems(res)
            bad += [f"{c['id']}: {p}" for p in problems]
            if res["route"]:
                flagged += 1
            else:
                clean += 1
        assert not bad, "\n".join(bad)
        assert clean > flagged, f"most good packs are clean, got {clean} clean and {flagged} flagged"

    def test_the_check_names_a_demoted_clean_good_and_a_missed_flag(self):
        clean = kbfacts.pack(CLEAN_Q)
        assert good_pack_problems(clean) == []
        flagged = kbfacts.pack(FLAGGED_Q)
        assert good_pack_problems(flagged) == []
        # planted: a clean good pack that a rule demoted to split, with its route lines printed
        demoted = dict(clean, route="split", text=clean["text"].replace(
            "\n\n", "\nroute: split\nkb has: LAPS\nkb lacks: -\n\n", 1))
        assert any("clean good but route" in p for p in good_pack_problems(demoted)), good_pack_problems(demoted)
        # planted: a flagged good pack that lost its route
        lost = dict(flagged, route=None, text="\n".join(ln for ln in flagged["text"].splitlines()
                                                          if not ln.startswith(ROUTE_LINES)))
        assert any("flagged" in p for p in good_pack_problems(lost)), good_pack_problems(lost)
        # planted: a word nowhere in the kb on an otherwise clean good pack must route it
        assert good_pack_problems(dict(clean, missing=["eks"])), "a missing word flags a good pack"


# ---------------------------------------------------------------- the eval questions end to end (no model)

# a `-` named as a part to answer or research, alone or in the `; ` list of parts
DASH_PART = re.compile(r"(?:kb (?:has|lacks): |; )-(?=[.;]|\s*$)", re.I | re.M)
MISSING_WORD_Q = "What is the default Windows LAPS password length for frobnicated devices?"  # good, routed by a word


def hook_problems(res, out):
    """What is wrong with the kb: hook's answer `out` for the pack `res` of the same question (empty: fine): a routed pack
    is let through with its route in the context, a clean good pack is blocked (answered), any other goes through."""
    blocked = isinstance(out, dict) and out.get("decision") == "block"
    context = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")
    if res["route"]:
        if blocked or not context:
            return [f"routed {res['route']} ({res['verdict']}) but the hook {'blocks it' if blocked else 'adds nothing'}"]
        if f"route: {res['route']}" not in context:
            return [f"routed {res['route']} but the hook's context has no route line"]
        return []
    if res["verdict"] == "good" and not blocked:
        return ["clean good but the hook does not answer it"]
    return []


def runs_of(q, p):
    """{run: its input} kb_ask.run would send for plan `p` (no model): a web plan to the researcher, a split plan with
    both sides to the reader and the researcher, any other to the reader whole."""
    if p["kind"] == "web":
        return {"researcher": kb_ask.web_prompt(q, p)}
    if p["kind"] == "split" and p["has"] and p["lacks"]:
        return {"reader": kb_ask.split_prompt(q, p), "researcher": kb_ask.web_prompt(q, p)}
    return {"reader": kb_ask.prompt(q, p["text"])}


def instructions(text):
    """A prompt without its pack: what it tells the run to answer or research."""
    return text.split("<kb_evidence>")[0]


def plan_problems(q, p, results):
    """What is wrong with the runs of plan `p` for question `q` (empty: fine); `results` are the packs of its parts
    (kbfacts.pack_many(p["parts"])["results"]). No side reads `-` as a part and no prompt names one; in a split of two
    runs every part reaches its run (a clean good part and a split part's kb has words the reader, a web part and a split
    part's kb lacks words the researcher; a web part's kb has words never the reader); a part that routes split carries
    no none sentence."""
    out = []
    for side in ("has", "lacks"):
        if kb_ask.NONE_WORD in p[side]:
            out.append(f"'kb {side}: -' read as a part")
    runs = runs_of(q, p)
    for name, text in runs.items():
        dash = DASH_PART.search(instructions(text))
        if dash:
            out.append(f"the {name}'s prompt names a '-' part: {dash.group(0)!r}")
    for r in results:
        if r["route"] == "split" and (kbfacts.NONE_SENTENCE in r["text"] or "Do not answer from the hits" in r["text"]):
            out.append(f"a pack routed split carries the none sentence: {r['text'][:80]!r}")
    if len(runs) < 2:
        return out  # one run gets the whole question, every part with it
    reader, researcher = instructions(runs["reader"]), instructions(runs["researcher"])
    several = len(p["parts"]) > 1
    for n, (part, r) in enumerate(zip(p["parts"], results), start=1):
        has, lacks = kb_ask.has_lacks(r["text"])
        if r["route"] is None:
            if part not in p["has"] or part not in reader:
                out.append(f"part {n} (good) does not reach the reader")
        elif r["route"] == "web":
            if several and (part not in p["lacks"] or part not in researcher):
                out.append(f"part {n} (web) does not reach the researcher")
            if several and any(h in p["has"] for h in has):
                out.append(f"part {n} (web) gives its kb has words to the reader")
        else:
            if not has and not lacks:
                out.append(f"part {n} (split) has neither side")
            if any(h not in p["has"] or h not in reader for h in has):
                out.append(f"part {n} (split): its kb has words do not reach the reader")
            if any(x not in p["lacks"] or x not in researcher for x in lacks):
                out.append(f"part {n} (split): its kb lacks words do not reach the researcher")
    return out


def planted_joins(cases):
    """Several-part questions made of eval questions: a covered (clean good) one beside an off-kb (web) one, a weak or
    flagged (split) one beside both, and a near miss beside an off-kb one, numbered as a person would ask them."""
    by = collections.defaultdict(list)
    for q in cases:
        res = kbfacts.pack(q)
        kind = res["route"] or ("good" if res["verdict"] == "good" else "unrouted")
        if len(by[kind]) < 2 and len(kb_ask.split_parts(q)) == 1:
            by[kind].append(q)
    good, web, split = by["good"], by["web"], by["split"]
    assert len(good) == len(web) == len(split) == 2, {k: len(v) for k, v in by.items()}
    groups = [(good[0], web[0]), (web[1], good[1]), (good[0], split[0], web[1]), (split[1], web[0]),
              (good[1], split[1]), (NEAR_MISS_Q, web[0])]
    return [" ".join(f"({n}) {q}" for n, q in enumerate(g, start=1)) for g in groups], [len(g) for g in groups]


def end_to_end(q):
    """(the route label, the problems) of one question through the pack, the hook and the plan."""
    res = kbfacts.pack(q)
    problems = hook_problems(res, kb_hook.answer("kb: " + q))
    p = kb_ask.plan(q)
    results = kbfacts.pack_many(p["parts"])["results"]
    problems += plan_problems(q, p, results)
    label = f"{p['kind']}/{'+'.join(sorted(runs_of(q, p)))}" + ("/parts" if len(p["parts"]) > 1 else "")
    return label, problems


class TestRouteEvalEndToEnd:
    def test_route_eval_end_to_end(self):
        cases = [c["question"] for _, c in rag.eval_cases()]
        assert cases, "the eval set has no rows"
        joins, sizes = planted_joins(cases)
        for q, n in zip(joins, sizes):
            assert len(kb_ask.split_parts(q)) == n, ("a planted join splits into its parts", q)
        seen, bad = collections.Counter(), []
        for q in cases + joins + [NEAR_MISS_Q, MISSING_WORD_Q]:
            label, problems = end_to_end(q)
            seen[label] += 1
            bad += [f"[{label}] {q[:70]}: {x}" for x in problems]
        assert not bad, "\n".join(bad)
        want = ("good/reader", "split/reader+researcher", "web/researcher", "split/reader+researcher/parts")
        assert all(seen[w] for w in want), f"every route is exercised: {dict(seen)}"

    def test_route_eval_end_to_end_names_planted_defects(self):
        clean, routed = kbfacts.pack(CLEAN_Q), kbfacts.pack(FLAGGED_Q)
        assert hook_problems(clean, kb_hook.answer("kb: " + CLEAN_Q)) == []
        assert hook_problems(routed, kb_hook.answer("kb: " + FLAGGED_Q)) == []
        # planted: the hook blocks a routed good pack (BG-ed6ci57t), and lets a clean good one through
        assert hook_problems(routed, {"decision": "block", "reason": routed["text"]}), "a blocked routed pack"
        assert hook_problems(clean, {"hookSpecificOutput": {"additionalContext": "x"}}), "an unanswered clean good"
        q = f"(1) {CLEAN_Q} (2) {NONE_Q}"
        p = kb_ask.plan(q)
        results = kbfacts.pack_many(p["parts"])["results"]
        assert plan_problems(q, p, results) == [], plan_problems(q, p, results)
        # planted: a `-` side read as a part (BG-zrzme2li)
        dash = dict(p, lacks=p["lacks"] + ["-"])
        assert any("'kb lacks: -'" in x for x in plan_problems(q, dash, results)), plan_problems(q, dash, results)
        assert any("names a '-' part" in x for x in plan_problems(q, dash, results))
        # planted: the covered part reaches neither run (BG-ou6nahcx)
        lost = dict(p, has=[h for h in p["has"] if h != CLEAN_Q] or ["LAPS"])
        assert any("part 1 (good) does not reach the reader" in x for x in plan_problems(q, lost, results))
        # planted: the off-kb part's kb has words given to the reader
        web_has = kb_ask.has_lacks(results[1]["text"])[0]
        leak = dict(p, has=p["has"] + web_has)
        assert web_has and any("(web) gives its kb has words" in x for x in plan_problems(q, leak, results))
        # planted: a near-miss pack routed split that still carries the none sentence (BG-bxkqdtk6)
        near = kbfacts.pack(NEAR_MISS_Q)
        with_none = dict(near, text=near["text"].replace("\n", "\n" + kbfacts.NONE_SENTENCE + "\n", 1))
        pn = kb_ask.plan(NEAR_MISS_Q)
        assert plan_problems(NEAR_MISS_Q, pn, [near]) == []
        assert any("none sentence" in x for x in plan_problems(NEAR_MISS_Q, pn, [with_none]))
