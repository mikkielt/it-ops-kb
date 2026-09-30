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
"""
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
        assert len(facts) > 2 and any("SNIPPET:" in ln and "@LockTimeout" in ln for ln in facts), facts
        assert res["sources"] == ["S467"] and "sources:" in lines, res["sources"]
        assert any(ln.startswith("  -> S467  https://") for ln in lines), lines[-3:]
        # a none that routes web keeps its none behaviour: the sentence, two lines of one article, no footer
        off = kbfacts.pack(NONE_Q)
        off_lines = off["text"].splitlines()
        assert kbfacts.NONE_SENTENCE in off_lines and off["sources"] == [] and "sources:" not in off_lines
        assert sum(1 for ln in off_lines if ln.startswith("## ")) <= 1
        assert sum(1 for ln in off_lines if ln.startswith("- ")) <= 2

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
