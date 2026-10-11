# Fact diff: anchors, calibration and a dry run

Measurements behind `_tools/factdiff.py` and the cut-offs in `_tools/factdiff.toml`. **Setup:** the public root with 2,655 sources, 10,042 fact units and 13,049 fact-source pairs (DOC, CODE, DER and COMMUNITY parts); every cited source fetched once by its provider's raw form (`_tools/providers.csv`); stdlib Python only, no model. Re-run each section with the command it names and replace the section when a new measurement supersedes it.

## Anchor backfill

`python3 _tools/factdiff.py anchor` over every source (2,496 fetched, from the cache of one pass taking about 45 minutes at one request per 1.1 s per host; the matching itself about 100 s).

| status | pairs |
|---|---|
| located | 6,303 (48%; 56% of the pairs whose source returned text) |
| unlocated: no-match | 4,856 |
| unlocated: not-text (zip, tar, xlsx, PDF, binaries) | 1,788 |
| unlocated: fetch-error (DNS, timeouts, 403, 429, 202) | 90 |
| unlocated: gone (404) | 12 |

By tag kind, share located of the pairs with text: DOC 59%, COMMUNITY 56%, CODE 47%, DER 29% (a derivation rarely has one backing sentence). By provider: code.claude.com 76%, raw GitHub 70%, gitlab.com 68%, Learn 56%, modelcontextprotocol.io 47%, docs.gitlab.com 36%, github.com pages 28%, the generic long tail 33%. Quotes (25 words at most, `copy` and `quote` sources only) are kept on 6,236 located anchors; a quote that looks like an address, a home path, a token, a private network or a GUID is left out.

The pass also spent the unauthenticated api.github.com allowance (60 requests an hour) on the 43 `api.github.com` sources, so research run at the same time got `403 rate limit exceeded` there (git over https, `git ls-remote`, is not limited). The unlocated pairs are listed, not guessed: `python3 _tools/factdiff.py anchors --unlocated`. They are facts that condense a whole section or table, derivations, probe results (a page's headers, not its text) and facts whose page is client-rendered.

### Anchor thresholds

A labelled sample: 72 fact-source pairs drawn at random, 12 per band of cover (the share of the fact's term weight the best window holds), each read and marked as the right backing passage (a partial one counted as right, since it holds the fact's claim) or a wrong one.

| cover | right | wrong | pairs in the kb |
|---|---|---|---|
| 0.30-0.40 | 9 | 3 | 1,744 |
| 0.40-0.45 | 11 | 1 | 885 |
| 0.45-0.50 | 11 | 1 | 765 |
| 0.50-0.55 | 10 | 2 | 733 |
| 0.55-0.65 | 12 | 0 | 1,275 |
| 0.65 and more | 11 | 1 | 2,495 |

Precision is flat at about 92% from 0.40 up (55 of 60) and falls to 75% below it, so `min_cover` is 0.40, with `min_shared` 3 terms, windows of up to 3 units and a cover cost of 0.05 per extra unit. The wrong ones were an image tag (now skipped as a unit), two derivations whose words sit in a related sentence, and a fact about a different service limit on the same page. A wrong anchor can only re-date a fact whose true passage was not checked; it can never change a fact.

### Second look at data rows, 2026-10-10

`python3 _tools/factdiff.py anchors --breakdown` lists the pairs whose source returned text by provider host and tag kind. Before the change 5,098 pairs were no-match (of 11,696 with text); 1,838 of the 5,105 on the document cache were CSV rows (`column=value; ...`), scored with their column names, source columns and source ids as if page text, so a row that cites several sources held at most a fraction of its weight on any one page (`security/settings-crosswalk.csv` alone: 709 no-match against 123 located). DER pairs were 21% located and `learn.microsoft.com` held 2,836 no-match.

The rule now gives a row the plain rule leaves unlocated a second look: scored on its values alone, a term the page lacks counted 1/sources, accepted where the window holds at least 0.35 of its own term weight (`row_min_density`; a blob of unrelated sentences holds any row's terms) and the row's first two cells are found in it or its headings to 0.75 (`row_min_identity`). A second look for Markdown facts that cite several sources (the page's missing terms counted 1/sources, a density cut of 0.4 and at least 0.3 of the fact's terms on the page) was tried and left out: 5 of 20 and then 5 of 12 hand-checked anchors were wrong, pages that merely share a topic.

| measure | before | after |
|---|---|---|
| sources the pass started with (2,527 cached documents), pairs with text | 11,707 | 11,707 |
| located | 6,602 (56.4%) | 6,795 (58.0%) |
| all 3,017 sources of the root now (490 cited since the start, fetched in the same pass), pairs with text | 13,365 | 13,365 |
| located | 7,324 (54.8%) | 7,518 (56.3%) |
| located by the plain rule that the new one loses | | 0 |

Both columns are the same documents, the rules run over them by `factdiff.py anchor --max-age 30` (after) and the committed rule at `HEAD` of the item's base (before). The sprint-start value was 6,588 of 11,676 (56.4%); the pairs of the 490 newer sources locate at a lower share, so the whole-root share is 56.3%.

**Precision.** A fresh sample: 60 of the 194 pairs located only by the new rule (drawn with `random.Random(99).shuffle`, the first 60), each read against its window and marked as the right backing passage (a partial one counted as right, as in "Anchor thresholds") or a wrong one: 58 right, 2 wrong, 96.7% (the wrong ones: a class declaration that lists a property but not the row's value, and a table of configuration properties that holds only the row's property name). Earlier samples tuned the cut-offs and are not counted: the second look without the density and identity cuts was right in 13 of 20 rows; with density 0.25, identity 0.5 and the Markdown look it was 52 of 60; with density 0.35 and identity 0.5, 49 of 60 on the larger source set, whose wrong ones were a module description (3), page titles (2) and URL lines (2).

`python3 _tools/factdiff.py snapshot --dry-run` over the public root: 792 live `copy` sources are cited; 758 would be kept, 30 returned no text (404, 403, 429, 202, timeouts) and 4 are JSON API answers or pages over the 500 KB cap (the NVD CVE API answer alone is 6.2 MB and changes daily). The 758 files hold 11.4 MB of text, about 2.4 MB compressed; the repository's tracked files were 16 MB with a 45 MB `.git` before them. Learn pages under MIT or CC BY mirrors are 6.9 MB of it.

**Committed (2026-09-28), `python3 _tools/factdiff.py snapshot`:** 755 snapshots (706 added to the `entra` domain's 49), 11.5 MB with their headers (7.1 MB of it Learn pages), 3.2 MB as a gzip tarball. Three pages were left out for a private key header, which the leak test and secret scanners flag: the SOPS print view (a sample RSA key) and two MSAL Python references (the bare PEM marker); `wants_snapshot` now keeps only their hash. The commit's objects packed to 3.3 MB (`git pack-objects --revs` over the commit alone), the push size; loose in `.git` before a `git gc` they took 5.3 MB. The secret scan's hits in the rest are vendor sample values (AWS's example key id, T-SQL and ldap3 password placeholders, a Kubernetes sample secret), allowlisted in `_tools/tests_allowlist.txt`; published author and contact e-mails (two papers, two project pages), sample private addresses and home paths stay, since the placeholder rules do not apply to vendor text.

## Calibration

The cut-offs of `_tools/factdiff.toml` other than the anchor's, each from real history or live hosts.

**Passage edited or gone (`modified_min`).** `python3 _tools/factdiff.py calibrate history` on consecutive versions of changed pages in two public Microsoft documentation repositories (blobless clones from the census cache). difflib aligns the units of the old and new version: a unit paired one to one with an edited unit is a positive (its similarity to the edit), a deleted unit that appears nowhere in the new version is a negative (its best similarity to any new unit).

| repository, pages | units | kept word for word | edited / removed | best cut | balanced accuracy |
|---|---|---|---|---|---|
| `MicrosoftDocs/memdocs` (Intune, Autopilot; since 2025-09-01), 146 page versions | 28,104 | 99.1% | 91 / 34 | 0.75 | 0.789 |
| `MicrosoftDocs/entra-docs` (since 2026-02-01), 150 page versions | 22,242 | 98.9% | 118 / 29 | 0.65 | 0.893 |

`modified_min` is 0.70, between the two best cuts. The ground truth is approximate (difflib can pair two unrelated sentences, or split an edit into a delete and an insert), and the cut only decides how a changed passage is presented for review, never whether a fact is re-dated. The share kept word for word is the headline: an edit to a Learn page leaves about 99% of its sentences as they were, so most facts on a changed page are re-dated with no model.

**Page replaced (`zombie_max`).** The same samples, page level: simhash similarity of a page to its next version (same page) against another changed page of the same repository (other page). memdocs: same page 0.859 at the 5th percentile, other page 0.594 at the 95th, best cut 0.75 (balanced accuracy 0.993); entra-docs: 0.875 and 0.656, best cut 0.80 (0.983). `zombie_max` is 0.75; a page under it whose anchors are still found is an edit, not a replacement.

**Soft 404 (`soft404_min`).** `python3 _tools/factdiff.py calibrate soft404 --hosts 200`: for each of the 173 hosts of the public sources (api.github.com left out for its rate limit), a real page and two made-up sibling urls. 153 hosts answered the made-up url with 404, 9 with 200 and 11 with another code (403, 401, 400, 202, errors). On the 8 hosts that answered 200 to both made-up urls, the two made-up pages had Jaccard similarity 1.0 every time; the real page against the made-up one was 0.0 on 3 hosts and 1.0 on 5, whose pages are client-rendered shells with the same text whatever the url. `soft404_min` is 0.8: any cut in (0, 1] separates the decidable hosts, and a shell host is never declared dead because the rule needs the page's previous version to have differed from the made-up page.

**Known dead links.** The census logs hold 14 sources that answered 404; 13 were since superseded by a person. `detect_source` called each gone (hard 404) on 2026-09-28. For the 8 Learn ones, the facts now citing their successors were searched for as if the old page had just died (redirect, sitemap additions, then Learn search by the old page's title, the anchor's quote and the fact's words, hub pages left out): of 28 facts with an anchor on the successor, 10 were found word for word on the right successor page and none on a wrong page; 18 went to review with the best candidate page. The first attempt, searching by the fact's words only, found 1 of 28.

## Dry run on the entra domain

The `entra` domain: 86 cited sources (69 Learn pages, 17 raw files pinned at a commit in `MicrosoftDocs/entra-docs`), 160 fact-source pairs on Learn pages mapped to that repository.

**Live, `python3 _tools/factdiff.py detect --dir entra --sitemaps`** (the day of the anchor baseline): 86 sources in 2 min 53 s, one request per 1.1 s per host; the 17 pinned files needed no request, all 69 Learn pages answered `304 Not Modified` to their stored ETag on the markdown form, and the Learn sitemap of the `entra` product was recorded as the next run's baseline. `factdiff.py apply --dry-run` would confirm all 69 (each page's `updated_at` is no later than its source's last confirmation) and re-date 2 articles whose sources were then all confirmed; `review` had nothing to show. No model was called and no page text was read by one.

**Replay over eight months of real edits.** To see resolution on changed pages, the anchors were placed on each page's text as it stood in `MicrosoftDocs/entra-docs` on 2026-02-01 and resolved against today's text, as a detect run after that interval would (the provider search and sitemap steps off; a replay script over `factdiff.py`'s functions, not committed). 43 sources had both versions (14 were added after February, 3 are not in that repository); 11 did not change.

| outcome | facts | model? |
|---|---|---|
| source unchanged: all its facts dated | 35 | no |
| verbatim: the anchor's passage word for word on the changed page | 82 | no |
| modified: a similar passage (similarity 0.85-1.00; one was only "does not" becoming "doesn't") | 7 | reads 2 passages |
| not-found on the page (in a live run the search for other pages comes next) | 5 | reads 2 passages |
| unanchored: no passage located in the February text (most facts were written from later text) | 31 | reads the fact and the best new passage |

117 of 160 facts (73%) were settled with no model. The 43 review items, each the fact with its old and new passage, came to 24,212 characters, about 6k tokens; reading the changed pages instead (old and new version) would be 750,943 characters, about 190k tokens: 31 times more. The not-found items were real changes: an agent-identity licensing sentence that moved from "included with P2 while in preview" to "will require a Microsoft Agent 365 license", and a Conditional Access template list reworded.

## Census baseline: what phase 2 had to read, 2026-09-26

The census's reading cost was never stated before it read. `census.py summary LOG` now prints the queue block (`census.reading_queue`, no network and no model: the rows whose bucket is not `OK`, whose note is not `blocked` and that have no outcome yet, the kb lines naming them as `rag.py src --cited` lists them, the characters a model would read and the tokens at characters / 4). The committed log of the 2026-09-26 census holds its phase-2 outcomes, so its queue is empty; the baseline is that log as phase 1 left it (the commit `df9030ac7`, "census 2026-09-26 phase 1 verdicts", `git cat-file blob df9030ac7:_census/2026-09-26.csv`), measured on 2026-10-10 against the kb's sources and the document cache of that day:

| measure | 2026-09-26 census, phase 2 queue |
|---|---|
| rows to read | 367 (the phase-2 commit names the same count of undecided sources) |
| kb lines naming them | 3273 |
| read as fact diff review passages | 0 rows (the census ran no fact diff first, so no review item existed) |
| read as whole documents | 367 rows, 9,739,477 characters, 2,434,869 tokens |
| of those, not cached | 84 rows, counted as 0 characters: the figure is a lower bound |

The five hosts with most characters: `graph.microsoft.com` 1 row, 1,838,888 characters; `code.claude.com` 16 rows, 1,314,200; `raw.githubusercontent.com` 26 rows, 941,298; `www.gnu.org` 1 row, 776,035; `api.github.com` 9 rows, 496,047. Later census work is measured against this: the same command on a later census log reads the same queue with review passages in place of whole documents where a fact diff ran first.

## Detect wall time: Learn pages decided by git history, 2026-10-10

`factdiff.py detect` decides a `learn.microsoft.com` page that `census.learn_source` maps (`census.LEARN_MAP`) to a file of a public docs repository by that file's commits since the stored baseline day, with no request to Learn, and asks Learn for every other source. Two full runs of the same command on the same day, each from a fresh clone of the repository in a scratch directory with a cold `_cache` (no clone cache, no document cache) and the committed `_fetch_state.csv` as the baseline:

```
python3 _tools/factdiff.py detect --sitemaps
```

| run | tree | started (UTC) | wall time | exit | result line |
|---|---|---|---|---|---|
| before | commit before the change | 19:08:33 | 31 min 21 s | 1 | `unchanged=819 changed=320 new=222 moved=796 gone=8 soft-404=19 replaced=12 error=34 pinned=783`; facts `verbatim=3080 modified=117 not-found=18 unanchored=3465 dead=1742` |
| after | the change | 19:41:27 | 32 min 29 s | 1 | `unchanged=819 changed=325 new=222 moved=797 gone=8 soft-404=20 replaced=12 error=27 pinned=783`; facts `verbatim=3077 modified=109 not-found=18 unanchored=3464 dead=1744` |

Both runs read 3,013 sources on 191 hosts. Exit 1 is facts to review, no failure. The difference of 68 s is inside the run-to-run spread: 16 sources outside Learn (github.com, platform.claude.com and others) differ between the logs, 15 by an error in one of the runs and 1 by a soft 404, which is the network, not the change.

**Why the wall time did not fall.** 1,388 of the sources are on `learn.microsoft.com`, at one request per 1.1 s per host about 25 minutes of the run. `LEARN_MAP` has five entries, and 140 of those sources map to one (entra-docs 55, windowsserverdocs 37, microsoft-graph-docs-contrib 30, sql-docs 16, PowerShell-Docs-DSC 2). Of the 140, 98 were decided by git history in the after run (signal `git`), 108 s of requests; of the other 42, 31 have no file at the mapped path at the repository's HEAD (23 answered `unchanged` by version id, 8 a redirect: for example `entra/msal/...` pages are not files of entra-docs), 10 had a commit since their baseline day and 1 had no baseline. The five repositories were cloned in about 25 s (the two large ones, shallow since 2026-01-01, 22 s and 24 s), once and in parallel. The other 1,248 Learn sources have no map entry: the most common first path segments are `intune` 134, `api` 80, `windows` 75, `azure` 70, `identity` 36, `configmgr` 35, `security` 32 and `powershell` 31. 729 of the Learn sources answer a redirect at every run (`moved`, signal `redirect`), each one request.

**Verdicts agree.** Of the 98 decided by git, 97 were `unchanged` (version id) before and 1 was `changed` (version id) with no commit of its file since the baseline day; the log's other differences are the 16 above, none a Learn source. The 24 github.com pages with signal `git` in both logs are the clone-cache signal of the github.com wiki and repository-home rows, unchanged by this work.

**What a request costs now.** The per-source cost of the git route is one `ls-tree` and one `git log --since` in the clone: the verdicts of all 140 mapped sources took 3.3 s in the warm clones, against about 154 s of requests at one per 1.1 s. The route's reach is the map's: more entries in `LEARN_MAP` move more sources off the 1.1 s per request path, and a docset with no public repository (intune: `MicrosoftDocs/memdocs` is archived) stays on it.

## Haiku 5.5 on the census's judging steps, 2026-10-11

Two census steps are one model call with no tools: the batch judge of fact diff review items (`census.py judge`, step `judge`) and the phase-4 checker's passage judgments (`census.py sample --brief`, step `check`). Haiku 5.5 (`claude-haiku-5-5`) was measured against the model each step ran on, `claude-sonnet-5-5` for the judge and `claude-opus-5-5` (the model the census sessions run on) for the checker, and became the default of both: `census.STEP_MODELS`. `factdiff.py review --judge` keeps `factdiff.JUDGE_MODEL`.

**Labelled set.** Built by `census.labelled_set` from the committed 2026-09-26 census log and its history, with no model: the label is the recorded outcome, not either model's reading.

| label | what it is | count |
|---|---|---|
| changed | a line the commits `df9030ac7..ece4bf732` (phase 1 verdicts to the readers' edits) rewrote whose old claim cites a source the log records `updated`, with the passage of that source's cached current text it best matches (cover 0.30 at least) | 48 |
| unchanged | a fact of a source the log records `confirmed` whose claim stands word for word in its file at `df9030ac7` and at HEAD, so no phase-4 fix or later audit rewrote it: 48 with the anchor's passage found word for word in the current text, 48 with the best match | 96 |

The set is split by the parity of the first byte of the sha256 of the source id (a source's facts stay in one half) before any prompt was read against it: `tune` 19 changed and 56 unchanged facts, `held` 29 and 40; for the checker one unit is a source with up to 4 of its facts, `tune` 12 sources changed and 38 unchanged, `held` 19 and 26. The held-out half was judged once per model (`compare` refuses a second run without `--again`); the tune half was run for a pilot, and the set's definition changed once after the first pilot: the first unchanged items were best matches only, and every model judged every checker source not supported, so the check had no variance; the draw now takes the word-for-word and the best-match items in equal numbers. The prompts and schema were not edited after that. Limits: the passages are those of the cached documents of 2026-10-11, not of the census day; the models see no old passage (`old: -`), which a production review item carries; a rewritten claim and a best-match passage are often only lexically close, so both models answer `not enough information` for most unchanged facts that are a synthesis of a page (the false rejects below), which the labels do not call errors of the page; `agreed in phase 4` is not recorded per source (the commits give counts only), so `unchanged` is "confirmed and never rewritten since", a proxy that cannot see a checker's silent agreement.

**Run.** Prompt and schema as the steps use them: `factdiff.judge_prompt` and `JUDGE_SCHEMA` for the judge; `census.CHECK_TASK`, the checker's rules for passages alone, and the same schema for the checker; batches of 20 units; `claude -p --tools "" --effort medium --output-format json --json-schema --max-budget-usd` with hooks, plugins and MCP off, in an empty directory, 4 calls at a time; effort `medium` is the Claude Code default of Haiku 5.5, Sonnet 5.5 and Opus 5.5 and was passed to all three. Each result's `modelUsage` named the model asked for. A `supported` verdict counts only when its sentence is in the passage, as in `census.py judge`; a unit with no verdict counts as not supported (none occurred).

```
python3 _tools/census.py compare kb/public/_census/2026-09-26.csv --step judge --model claude-haiku-5-5 --half held --from df9030ac7 --to ece4bf732 --dry-run
python3 _tools/census.py compare kb/public/_census/2026-09-26.csv --step judge --model claude-haiku-5-5 --half held --from df9030ac7 --to ece4bf732 --max-budget-usd 0.10
python3 _tools/census.py compare kb/public/_census/2026-09-26.csv --step judge --model claude-haiku-5-5 --decide
```

The same with `--model claude-sonnet-5-5` for the judge's baseline, and `--step check` with `claude-haiku-5-5` and `claude-opus-5-5` (`--max-budget-usd 0.20`, the dry run's cap per call 0.19); `claude-sonnet-5-5` also ran on the check as a reference. Each paid run followed its `--dry-run`; the estimates were 0.005 USD (Haiku) and 0.10 (Sonnet) for the judge's held-out half and 0.15 for the Opus check.

**Held-out half, judged once.** False confirms are changed units judged supported (the error that dates a stale fact); false rejects are unchanged units not judged supported. Tokens: cache-write plus cache-read plus uncached input, then output.

| step | model | units (changed / unchanged) | agreement | false confirms | false rejects | tokens in / out | total_cost_usd | wall time (4 calls at a time) |
|---|---|---|---|---|---|---|---|---|
| judge | claude-sonnet-5-5 (baseline) | 69 (29 / 40) | 41 of 69, 59.4% | 3 of 29 | 25 | 25,928 / 4,706 | 0.1338 | 9.5 s |
| judge | claude-haiku-5-5 | 69 (29 / 40) | 46 of 69, 66.7% | 3 of 29 | 20 | 29,030 / 15,665 | 0.0128 | 22.1 s |
| check | claude-opus-5-5 (baseline) | 45 (19 / 26) | 19 of 45, 42.2% | 3 of 19 | 23 | 21,961 / 4,957 | 0.2494 | 23.9 s |
| check | claude-haiku-5-5 | 45 (19 / 26) | 21 of 45, 46.7% | 3 of 19 | 21 | 23,717 / 17,705 | 0.0130 | 30.8 s |
| check | claude-sonnet-5-5 (reference) | 45 (19 / 26) | 22 of 45, 48.9% | 3 of 19 | 20 | 21,385 / 3,703 | 0.1099 | 10.4 s |

**Bars.** `census.py compare ... --decide` prints, for the judge: false confirms 3 against 3 (met), agreement +7.2 points against Sonnet 5.5 (met), default `claude-haiku-5-5`; for the checker: 3 against 3 (met), +4.4 points against Opus 5.5 (met), default `claude-haiku-5-5`. Haiku 5.5 held both bars on both steps at about a tenth of the judge's spend and a nineteenth of the checker's. It was slower: thinking cannot be turned off, and it wrote 3 to 5 times the output tokens of the others, so the wall time was 2.3 times Sonnet 5.5's on the judge and 1.3 times Opus 5.5's on the checker. The sets are small: a gap of 3 false confirms in 29 or in 19 units is inside the noise, and the agreement gaps are 5 and 2 units, so the result says that Haiku 5.5 lost nothing the set can see, not that the models are equal. The tune-half pilots (two sets, the same models) gave 0 to 2 false confirms for every model and 28 to 48% agreement.

**Spend.** All paid runs of the item, pilots, a two-batch diagnostic of raw replies and the held-out half: 1.35 USD, each call under its `--max-budget-usd` cap; no call failed.

**Not measured.** The checker opens a page when a passage does not settle a fact; that tool use was not part of the call, so Haiku 5.5 is the default of the passage judgments only, and a read of a page stays with the orchestrator's model. The `factdiff.py review --judge` entry point and `kb-census`'s skill text are unchanged by this measurement.
