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

The unlocated pairs are listed, not guessed: `python3 _tools/factdiff.py anchors --unlocated`. They are facts that condense a whole section or table, derivations, probe results (a page's headers, not its text) and facts whose page is client-rendered.

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

## Snapshots of copy sources

`python3 _tools/factdiff.py snapshot --dry-run` over the public root: 792 live `copy` sources are cited; 758 would be kept, 30 returned no text (404, 403, 429, 202, timeouts) and 4 are JSON API answers or pages over the 500 KB cap (the NVD CVE API answer alone is 6.2 MB and changes daily). The 758 files hold 11.4 MB of text, about 2.4 MB compressed; the repository's tracked files were 16 MB with a 45 MB `.git` before them. Learn pages under MIT or CC BY mirrors are 6.9 MB of it. Committed so far: the `entra` domain's 49 sources (0.6 MB); the bulk waits for the maintainer's decision on the size.

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
