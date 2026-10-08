"""The benchmarks' harness: a run is priced by the pinned model it reports (bench_core.PRICE), its effective input weights
cache reads by that model's own read ratio, and a tiered price records the tier the run's tokens fall in."""
import bench_core as bc


def req(model, uncached, write, read, out):
    return {"model": model, "usage": {"input_tokens": uncached, "cache_creation_input_tokens": write,
                                      "cache_read_input_tokens": read, "output_tokens": out}}


def test_bench_price_sonnet_55_run_weights_cache_reads_by_its_own_ratio():
    s = bc.usage_sum([req("claude-sonnet-5-5", 100, 1000, 10000, 500)], "sonnet", "2.1.284")
    assert s["model"] == "claude-sonnet-5-5" and s["tier"] == ""
    assert s["effective"] == 100 + 2 * 1000 + 0.05 * 10000  # the old fixed 0.1 gives 3100
    assert round(bc.est_cost(s), 6) == round((100 * 2 + 1000 * 2.5 + 10000 * 0.10 + 500 * 10) / 1e6, 6)
    opus = bc.usage_sum([req("claude-opus-5-5", 0, 0, 10000, 0)], "opus")
    haiku = bc.usage_sum([req("claude-haiku-4-5-20251001", 0, 0, 10000, 0)], "haiku")
    assert (opus["effective"], haiku["effective"]) == (500, 1000)


def test_bench_price_tier_is_recorded_and_alias_follows_the_run():
    run = [req("claude-haiku-5-5", 100, 1000, 10000, 500), req("claude-haiku-5-5", 100, 0, 150000, 500)]
    s = bc.usage_sum(run, "haiku")
    assert s["tier"] == ">100k" and bc.usage_sum(run[:1], "haiku")["tier"] == "<=100k"
    first, second = (100 * 0.10 + 1000 * 0.125 + 10000 * 0.01 + 500 * 0.50), (100 * 0.50 + 150000 * 0.05 + 500 * 2.50)
    assert round(bc.est_cost(s), 6) == round((first + second) / 1e6, 6)
    # the transcript's model wins over the alias; with none reported the alias names its model on the Claude Code version
    assert bc.resolve_model("sonnet", "claude-sonnet-5-5") == "claude-sonnet-5-5"
    assert bc.resolve_model("sonnet", "", "2.1.283") == "claude-sonnet-5"
    assert bc.resolve_model("sonnet", "", "2.1.284") == "claude-sonnet-5-5"
