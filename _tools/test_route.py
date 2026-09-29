"""The route a pack prints (`python3 _tools/tests.py -k TestRoute`).

TestRoute   kbfacts.pack and pack_many: a weak, a none and a check-flagged good pack print `route:`, `kb has:` and
            `kb lacks:` after the coverage, check:, freshness: and none-sentence lines and before the first article; a
            clean good pack prints none of them; `has` and `lacks` are the question's own words in question order;
            a none whose only missing words are language or format names routes split; route_of names each flagged case; a several-part pack starts with one overall route line.
"""
import kbfacts

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
