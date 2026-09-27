# doc2query: document expansion for pack

Document expansion for `pack`: a model writes a few questions each fact answers, and the questions' words are indexed with the fact. A question worded differently from the fact ("required keyword" vs "needs at least one") can then still find it.

- **Deterministic retrieval:** the model runs only when facts are written. `pack` stays deterministic.
- **Filtering (Doc2Query--):** a generated question is kept only if `pack` without expansion already puts it in its fact's article. That drops hallucinated questions.
- **Expansion words:** they rank the fact at weight 1.0 (`EXPANSION_WEIGHT` in `kbfacts.py`, chosen in the pilot), but never count as key words for the coverage verdict.
- **Switch:** `KB_DOC2QUERY=0` turns expansion off.

Background: `kb/_self/reports/token-usage.md`, "Retrieval quality", and Doc2Query-- (<https://arxiv.org/abs/2301.03266>): filtered expansion, up to 16% more effective, a third smaller index.

## Files (per root, in `_retrieval/doc2query/`: `kb/public/_retrieval/doc2query/` for public)

Every command works on one root: `python3 _tools/doc2query.py --root <name> <command>` (default public); `stale` and `prune` cover every root.

- `arms.json`: the latest round's pilot and control articles (`doc2query.py split`: stratified by domain, articles with 8 or more facts). `arms-seed7.json` is round 1; round 2 used `--seed 29 --exclude arms-seed7.json`.
- `expansions.csv`: `key,question`. The key is `kbfacts.fact_key(text)`, sha256 of the whitespace-collapsed fact text, so it survives line moves and changes with the text. `doc2query.py stale` lists orphaned keys (exit 1; `tests.py` fails on them), and `doc2query.py prune` removes them.
- One article: `doc2query.py batch --path <domain>/<slug> --out facts.json`, then generation and `ingest`, as in the protocol below.
- `offkb_questions.txt`: 20 near-domain questions the kb does not cover. Expansion must not make them `good`.

## Protocol
1. `python3 _tools/doc2query.py split` chooses the arms.
2. `python3 _tools/doc2query.py batch pilot --out pilot.json` gives the facts to expand.
3. Generation: a small model writes 3 questions per fact (keyword-style, full question, other words), with no invented details. Output: `[{key, questions}]`.
4. `python3 _tools/doc2query.py ingest generated.json` filters the questions and appends the kept ones to `expansions.csv`.
5. Blind test: a separate model that never sees the generated questions writes one paraphrased question per fact for a sample of both arms. Output: `[{key, question}]`.
6. `python3 _tools/doc2query.py evaluate test.json` reports, per arm and with expansion off and on: the fact's line in the pack, its article, the verdicts, the eval set and the off-kb verdicts.

**Adopt only if:**
- the pilot arm gains line recall with expansion on;
- the control arm is unchanged;
- the eval set stays at 100%;
- off-kb `good` does not rise;
- the mean pack size does not grow.

## Results
See `kb/_self/reports/token-usage.md`, "doc2query".
- **Round 1:** pilot 90% -> 97.5%, with the weight tuned on the test set.
- **Round 2 (fresh arms):** no change, 95% both ways.

The whole kb is not expanded. Expand an article when real lookups show paraphrase misses in it.
