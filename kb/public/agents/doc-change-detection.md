---
topic: agents/doc-change-detection
priority: P3
applies_to: "Microsoft Learn page metadata, markdown endpoint, sitemaps, MicrosoftDocs redirection files and source-file history (probed 2026-09-27 and 2026-10-10); GitHub REST API date fields, conditional requests and rate limits, GitHub Discussions (GraphQL) and GitHub wikis (docs at github/docs main be38ec5d, probes 2026-10-10); Memento (RFC 7089); Internet Archive Wayback Availability and CDX APIs; soft-404 detection (WWW 2004); docs MCP server capabilities; reference rot studies; urlwatch 2.29, changedetection.io 0.60.7, htmldate 1.10.0, trafilatura 2.2.0; FEVER and AIS"
retrieved_utc: 2026-10-10
sources: [S-g3ciqhyh, S-2r7j5aw2, S-zlvv4mum, S2188, S-o6lmrcgh, S-7tff4woa, S-2biiolic, S-wze42rd7, S-oqvrq2wq, S-stitrqhm, S-u67guolg, S-uymc3nwh, S-5lkuonr6, S-mm23ncwl, S-y23orbo7, S-may2otwt, S-ghhbd6g6, S-7jumyiid, S-zb3jd525, S-lldnrkhv, S-ecrpwvoh, S-v3vc7a3l, S-xv7jeuvk, S-ybuoluc4, S-xpbhjzu7, S-rgpijsmb, S-pcy7cqea, S2196, S2177, S-2dckbgu5, S-km6slvii, S-s6xjctzu, S-oo5kmppv, S-znp63ln6, S-xc4ibwg4, S-vh33l6f5, S-qvogwadn, S2176, S-lylm4eqz, S-7ivxsp4z, S-ffzntayk, S-7n65j7bo, S2180, S2181, S-uq2hafxi, S-shha3est, S-wcrrjfwh, S-a6bblnnl, S-gceoq2qq, S-yvdwutca, S-niqtbnmc, S-hgu2bdgi, S-wkj4aa2g]
status: complete
---

# Detecting documentation source changes: version signals, redirects, archives, soft 404s

## Summary
Signals a tool can read, without a model, to tell whether a cited documentation page changed, moved or
died. A Microsoft Learn page carries a per-page `git_commit_id`, `updated_at` and a stable `document_id`
in its HTML `<head>` and in the YAML front matter of its markdown form (`?accept=text/markdown`), and it
answers conditional requests with `304`. Learn sitemaps are split per product and locale, but their
`lastmod` did not match the page's own `updated_at` in the probe below. Moved pages are recorded in each
docs repository's `.openpublishing.redirection*.json` and served as `301`, sometimes to an anchor on another
page. Old text comes from the public MicrosoftDocs repository at the page's commit, or from web archives
through Memento (RFC 7089) and the Wayback CDX API. A page that answers `200` with error content (a soft
404) is caught by fetching a random sibling URL and comparing the two. For a source on GitHub, an
issue's or repository's `updated_at` (or `pushed_at`) and the `since` filter date the last change, a wiki is
its own Git repository (`<repo>.wiki.git`) whose history dates each page, and an unauthenticated `304` still
counts against the 60 requests an hour. Design context: `kb/_self/tools.md`,
"fact diff", and `kb/_self/reports/fact-diff.md`.

## Facts
### Microsoft Learn page version signals
- A Learn page's HTML `<head>` has `<meta>` tags `ms.date`, `document_id`, `document_version_independent_id`, `updated_at`, `git_commit_id` and `depot_name`; on the probed ConfigMgr page `ms.date` was 2025-11-11, `updated_at` 2026-08-31T17:37:00Z and `depot_name` `MSDN.memdocs`. [DOC S-7jumyiid]
- `ms.date` is not a change signal for small edits: Microsoft's contributor guidance says to update it for major content, "but not for fixes like clarification, formatting, grammar, or spelling". [DOC S-ecrpwvoh]
- The same page returned a strong `ETag` and a `Last-Modified` header with `cache-control: public, max-age=600`; the ETag was the same across repeated requests (including one with a cache-busting query that reached a new edge request id), and `If-None-Match` or `If-Modified-Since` with those values returned `304`. [DOC S-7jumyiid]
- The draft note that Learn sends no usable ETag is therefore not true for this page. Wayback captures of the same page show the ETag also changing across Learn site builds with no content change: captures of 2025-12-12 and 2025-12-28 carry the same `Last-Modified` (2025-12-11) but different `x-buildversion` values and different ETags. So a changed ETag means the rendered HTML changed, not necessarily the content; `updated_at` or `git_commit_id` is the content signal. [DER S-qvogwadn: archived response headers of captures compared]
- Adding `?accept=text/markdown` to a Learn URL, or sending `Accept: text/markdown`, returned `content-type: text/markdown` with the same ETag: a YAML front matter block (`title`, `ms.date`, `document_id`, `updated_at`, `git_commit_id`, `original_content_git_url`, `gitcommit`, ...) followed by the article body, several times smaller than the HTML page. [DOC S-7jumyiid]
- The documented ways to get a Learn page as Markdown are the Learn MCP server's fetch tool, which "fetches and converts a page into markdown" [DOC S2176], and the Learn CLI's `mslearn fetch <url>`, which returns "Markdown-friendly output" [DOC S-lylm4eqz]. No Learn page read on 2026-09-27 documents the `?accept=text/markdown` query or header form, and `learn.microsoft.com/en-us/llms.txt` returns 404, so that form is observed behaviour, not a published interface. [DER S2176, S-lylm4eqz: documented routes compared with the probed form]
- In the markdown front matter, `original_content_git_url` and `gitcommit` name the source file in a private `-pr` repository (`MicrosoftDocs/memdocs-pr`, `MicrosoftDocs/entra-docs-pr`) at branch `live` and at the commit in `git_commit_id`. [DOC S-7jumyiid, S-ybuoluc4]
- The public mirror repositories hold those commits: the Entra device-identity page's `git_commit_id` resolves in `MicrosoftDocs/entra-docs` and its file is readable at that commit, and the ConfigMgr page's commit resolves in the archived `MicrosoftDocs/memdocs`. [DOC S-xpbhjzu7, S-rgpijsmb]
- So the old text of a Learn page can be fetched from the public mirror at a stored `git_commit_id`, without keeping a local copy, as long as the mirror is public and still receives commits; `memdocs` was archived on 2026-09-02, so later ConfigMgr and Intune commits cannot be found there. [DER S-xpbhjzu7, S-rgpijsmb, S2196: commit lookups plus the archive date]
- `microsoft_docs_fetch` (the Learn MCP server) returns the article as markdown without the front matter, so it carries no `updated_at` or `git_commit_id`; a change check needs a plain HTTP request for those. [DER S2177: the fetches made for this article returned bare markdown]

### Learn page to source file and its git history
- For the Entra "device identity" page on 2026-10-10, the markdown front matter's `original_content_git_url` was `https://github.com/MicrosoftDocs/entra-docs-pr/blob/live/docs/identity/devices/overview.md` and its `source_path` was `docs/identity/devices/overview.md`; the HTML head also held `original_content_git_url_template="{repo}/blob/{branch}/docs/identity/devices/overview.md"`. So the url is the private repository, the branch `live` and the page's `source_path`. [DER S-ybuoluc4: the front matter and head of one page, read 2026-10-10]
- On the same page the HTML head's `github_feedback_content_git_url` was `https://github.com/MicrosoftDocs/entra-docs/blob/main/docs/identity/devices/overview.md`: the public repository (no `-pr`), branch `main`, the same repository path. A tool takes the public file's url from that tag and need not rewrite `-pr` by hand. [DER S-ybuoluc4: the head of one page, read 2026-10-10]
- The commits endpoint of GitHub's REST API takes a `path` parameter ("Only commits containing this file path will be returned") and `since` and `until` timestamps, so the history of one source file is one request. [DOC S-o6lmrcgh]
- For that page, `GET /repos/MicrosoftDocs/entra-docs/commits?path=docs/identity/devices/overview.md&per_page=3` on 2026-10-10 returned `95d306db` first: the page's own `git_commit_id`, with committer date 2026-06-15T16:45:09Z. The page's `updated_at` was 2026-06-15T17:40:00Z, 55 minutes later, and its `ms.date` 2025-06-27. [DER S-stitrqhm, S-ybuoluc4: one page compared on 2026-10-10]
- Two of the file's three newest commits had subjects that start `[BULK UPDATE]`, one of them naming a metadata move (author, `ms.author`, `ms.service`); the commit that set `git_commit_id` and `updated_at` was one of these. So the file's commit date and the page's `updated_at` moved together on a bulk commit, and neither shows by itself whether the article text changed; a diff of the text between two stored commits does. [DER S-stitrqhm, S-ybuoluc4: commit subjects of one file read 2026-10-10; the diffs were not read]
- So the git side adds, to the head's `updated_at` and `git_commit_id` that cost no API request, the list of commits that touched the file and the text at each (at one unauthenticated request per page, against the limit in the GitHub section below); on this page it dated the change no better than `updated_at` did. A file in the archived `memdocs` repository has no commits after 2026-09-02. [DER S-stitrqhm, S-ybuoluc4, S2196]

### Learn site search endpoint
- `learn.microsoft.com/api/search?search=<query>&locale=en-us&$top=<n>` answered `200 application/json` without authentication; each result carries `title`, `url`, `description`, `lastUpdatedDate`, `breadcrumbs`, `category` and `products`, and the response has `count` and `nextLink`. [DOC S-7ivxsp4z]
- For the Entra page "Manage devices in Microsoft Entra ID", the search result's `lastUpdatedDate` (2026-08-25T07:33) was the page's own `updated_at` from its markdown form. [DOC S-7ivxsp4z, S-7n65j7bo]
- So one search request returns the content date of up to `$top` pages at once, a cheaper batch signal than fetching each page, and it also finds pages a moved passage may have gone to. [DER S-7ivxsp4z, S-7n65j7bo: one page compared; a larger sample would confirm]
- The documented Learn Platform API (`learn.microsoft.com/api/v1`) is an authenticated catalog of training content (modules, learning paths, certifications, exams) and states it does not output documentation, so the site search endpoint above is undocumented and may change without notice. [DOC S-ffzntayk]

### Sitemaps
- `learn.microsoft.com/robots.txt` names `https://learn.microsoft.com/_sitemaps/sitemapindex.xml`; the index listed several thousand sitemap files split by product and locale (for example `intune_en-us_1.xml`), each with a `lastmod` date. [DOC S-zb3jd525]
- A product sitemap lists each page URL with a day-precision `lastmod` and `hreflang` alternates for other locales. [DOC S-lldnrkhv]
- For the probed ConfigMgr page the sitemap `lastmod` was 2026-01-14 while the page's `updated_at` was 2026-08-31 and its `ms.date` 2025-11-11: none of the three agreed. [DOC S-lldnrkhv, S-7jumyiid]
- Sitemap `lastmod` is therefore usable to find added and removed URLs, but not as a per-page change signal on Learn; `updated_at` or `git_commit_id` from the page itself is the reliable one. [DER S-lldnrkhv, S-7jumyiid: one page compared; a larger sample would confirm]

### Redirects on Learn
- A docs repository records moved or deleted articles in `.openpublishing.redirection.json` at its root, as a `redirections` array of entries with `source_path` (repository path of the old `.md`), `redirect_url` (public URL, may end in `#section` or point to another site) and `redirect_document_id`. [DOC S-ecrpwvoh]
- `redirect_document_id: true` keeps the old page's document id (and its page views and rankings) on the target, meant for a rename; `false` (the default) is for a pointer to a different article that covers only part of the old content. [DOC S-ecrpwvoh]
- So `redirect_document_id` tells a fact-diff tool whether a redirect is a rename (the facts should be found on the target) or a partial merge (the facts may be gone or split). [DER S-ecrpwvoh]
- Some repositories split the file per product: `memdocs` has `.openpublishing.redirection.autopilot.json`, `.configmgr.json`, `.intune.json`, `.external.json` and `.legacy.json`. [DOC S-pcy7cqea]
- The `entra-docs` file at the pinned commit holds several hundred entries; most use `source_path_from_root` instead of `source_path`, and a few redirect to an anchor on another docset (for example a licensing page to a Microsoft 365 admin page with `#manage-group-based-licensing-errors`). [DOC S-xv7jeuvk]
- Redirects can chain (A to B, later B to C); the Learn Authoring Pack's sort command exists partly because of this "daisy chaining", so a tool must follow chains rather than read one hop. [DOC S-v3vc7a3l]
- Learn serves a redirected page as `301` to the target, keeping the anchor when there is one, and a nonexistent path under a docset as a real `404`, not a soft 404. [DER S-xv7jeuvk: two Entra paths from this file and one made-up path, requested 2026-09-27]

### Web archives: Memento and the Wayback Machine
- RFC 7089 (Informational, December 2013) defines Memento: an Original Resource (URI-R), a Memento that holds its state at a time T (URI-M), a TimeGate that negotiates on datetime (URI-G) and a TimeMap that lists a resource's Mementos (URI-T). [DOC S-2dckbgu5]
- A client asks a TimeGate for a past state with the `Accept-Datetime` request header; a Memento states its time in the `Memento-Datetime` response header. [DOC S-2dckbgu5]
- The Internet Archive states that the Wayback Machine is "fully compliant with the Memento Protocol"; a request to `web.archive.org/web/<timestamp>/<url>` answered `302` to the nearest capture, which carried `Memento-Datetime` and a `Link` header with `original` and `timemap` relations. [DOC S-km6slvii]
- The Wayback Availability JSON API (`archive.org/wayback/available?url=...&timestamp=YYYYMMDDhhmmss`) returns only the single closest snapshot, or an empty `archived_snapshots` object when the URL is "not archived or currently not accessible". [DOC S-km6slvii]
- For a Learn page with several 2025-2026 captures, the Availability API returned an empty `archived_snapshots`, while the TimeGate and the CDX API found them. [DOC S-oo5kmppv, S-znp63ln6]
- The Availability API's empty answer does not prove a page was never archived; the CDX API or the TimeGate is the check to trust. [DER S-oo5kmppv, S-znp63ln6, S-km6slvii: "not accessible" is one of the documented reasons for an empty result]
- The CDX Server API (`web.archive.org/cdx/search/cdx`) lists captures with `urlkey`, `timestamp`, `original`, `mimetype`, `statuscode`, `digest` and `length`; it takes `output=json`, `fl=` (field list), `from=`/`to=` (timestamp range), `filter=` (regex per field, `!` negates), `matchType=` (`exact`, `prefix`, `host`, `domain`) and `collapse=` (for example `collapse=digest`, which collapses only adjacent duplicates). [DOC S-s6xjctzu]
- A CDX query answered `504 Gateway Time-out` once and succeeded on retry. [DOC S-znp63ln6]
- CDX `digest` values let a tool list only the captures whose content changed (`collapse=digest`) before reading any archived text. [DER S-s6xjctzu]

### Dead pages and soft 404s
- Bar-Yossef, Broder, Kumar and Tomkins (WWW 2004) define a page as dead when its URL is malformed, its host is down or nonexistent, or it does not exist on the host, and note that servers answering "soft 404s" hide the last case. [DOC S-xc4ibwg4]
- Their soft-404 test fetches the page and a sibling URL made of the page's parent plus 25 random characters: if the random URL gets a hard error the server does not do soft 404s; if both redirect to the same place, or return identical or nearly identical content (checked by shingling), the page is declared a soft 404. [DOC S-xc4ibwg4]
- The paper notes one case the test cannot settle: a dead domain's home page bought or parked by a new owner. [DOC S-xc4ibwg4]
- Google Search treats a `2xx` response whose content "suggests an error", such as an empty page or an error message, as a soft 404 in Search Console. [DOC S-vh33l6f5]
- Google treats `301` as a strong signal that the redirect target should be processed, `308` as equivalent to `301`, and `304` as "the content is the same as last time it was crawled". [DOC S-vh33l6f5]

### GitHub repositories, issues and discussions: date fields, conditional requests, limits
- The REST API's repository objects carry `created_at`, `updated_at` and `pushed_at` (date-times, nullable on the repository and minimal-repository schemas), and the OpenAPI description gives them no description, so the API documents no rule for what moves either date. [DOC S-o6lmrcgh]
- For `MicrosoftDocs/entra-docs` on 2026-10-10: the newest commit's committer date was 2026-10-09T22:33:00Z, `pushed_at` 22:35:40Z and `updated_at` 22:35:45Z, and the response's `last-modified` header was `Fri, 09 Oct 2026 22:35:45 GMT`, the same instant as `updated_at`. So on that repository `pushed_at` came 2 min 40 s after the newest commit's date and `updated_at` 5 s after `pushed_at`; one repository, so what else moves either date was not tested. [DER S-oqvrq2wq, S-u67guolg: one repository read twice in a few minutes]
- The issues list takes `sort` (`created`, `updated` or `comments`), `direction` and `since` ("Only show results that were last updated after the given time"), and an issue has `created_at`, `updated_at` and a nullable `closed_at`; the list also returns pull requests, told apart by their `pull_request` key. [DOC S-o6lmrcgh]
- So `GET /repos/{owner}/{repo}/issues?state=all&sort=updated&since=<stored time>` lists in one request every issue and pull request that changed after a stored time. [DER S-o6lmrcgh: the parameters read together]
- In the `gitextensions/gitextensions` issues on 2026-10-10, one closed issue had `closed_at` 2026-10-09T15:41:21Z and `updated_at` 2026-10-09T22:21:07Z, so `updated_at` moved after the close: it follows later activity on the issue, not only the close. [DER S-uymc3nwh: one issue, three read]
- The OpenAPI description (815 paths) has no path with `discussion` in it, so Discussions have no REST endpoint there. [DER S-o6lmrcgh: the path list searched on 2026-10-10]
- GitHub documents Discussions through GraphQL, and says that API is available to authenticated users, OAuth apps and GitHub Apps, with a token scope that depends on repository visibility. [DOC S-7tff4woa]
- GraphQL's `Discussion` has `createdAt` and `updatedAt` ("the date and time when the object was last updated"), and `Repository.discussions` orders by `UPDATED_AT` descending unless told otherwise. [DOC S-7tff4woa]
- An unauthenticated `GET /rate_limit` on 2026-10-10 reported `core` 60 per hour, `search` 10, `code_search` 60 and `graphql` limit 0, so an unauthenticated tool has no budget for the Discussions API. [DER S-5lkuonr6, S-7tff4woa: one read]
- Unauthenticated requests share a primary limit of 60 per hour, tied to the originating IP address, not to a user or an application; 5,000 per hour with a personal access token. [DOC S-zlvv4mum, S2188]
- Most endpoints return an `etag` and many a `last-modified` header; a conditional `GET` with `if-none-match` or `if-modified-since` answers `304`, and a `304` does not count against the primary rate limit only when "correctly authorized with an `Authorization` header". [DOC S-g3ciqhyh]
- A `304` counts against the GitHub REST API's unauthenticated rate limit: on 2026-10-10 a conditional request for `GET /repos/MicrosoftDocs/entra-docs` with the weak ETag of its `200` in `If-None-Match` returned `304`, and so did one with `If-Modified-Since`; the rate limit of 60 requests an hour was charged for each (`x-ratelimit-used` went 2, 3, 4, remaining 58, 57, 56), as the page's `Authorization` condition says. [DER S-oqvrq2wq, S-g3ciqhyh: three consecutive responses from one IP address, which also carries other traffic]
- Calling `GET /rate_limit` does not count against the primary limit, though it can count against a secondary one. [DOC S-2r7j5aw2]
- A `304` still carried the `x-ratelimit-*` headers, and `git clone` and `git ls-remote` of two wiki repositories did not move the `core` counter in the same session: `GET /rate_limit` showed 7 used after seven API calls and three git operations. [DER S-oqvrq2wq, S-5lkuonr6: the counter read after the git operations]
- If a response has an `x-poll-interval` header, the docs say to wait at least that many seconds before polling the endpoint again; the same parameters every time keep the `etag` stable. [DOC S-g3ciqhyh]
- So a census that reads GitHub sources unauthenticated has 60 requests an hour for all of them, whether the answer is `200` or `304`; one `GET /repos/{owner}/{repo}/issues?since=` or `.../commits?path=` serves a whole repository or file, and a token is what makes a `304` free. [DER S-2r7j5aw2, S-g3ciqhyh, S-oqvrq2wq: the limit and the charge observed]

### GitHub wikis
- A wiki is a Git repository: after the first page exists, `git clone https://github.com/OWNER/REPOSITORY.wiki.git` clones it, branches can be made, and only changes pushed to the default branch go live. [DOC S-2biiolic]
- "Every change you make is a commit": the wiki's history lists the user, the commit message and when the change was made, per page, and a SHA opens the page as it was. [DOC S-wze42rd7]
- For the `gitextensions/gitextensions` wiki on 2026-10-10, `git clone --bare --filter=blob:none` of its `.wiki.git` worked without credentials (git 2.50.1), and `git log -1 --format=%cI -- Home.md` gave 2026-03-19T23:14:43+01:00. The web page `/wiki` (the `Home` page) showed "edited this page" with `<relative-time datetime="2026-03-19T22:14:43Z">`, the same instant. [DER S-y23orbo7, S-mm23ncwl, S-wze42rd7: one page compared]
- The web page answered with a weak `etag` and `cache-control: max-age=0, private, must-revalidate`; its `etag` was not compared with the wiki's commits. [DER S-mm23ncwl: one response read]
- `git ls-remote https://github.com/rust-lang/rust.wiki.git` returned `HEAD` and `refs/heads/master` with one SHA in one call on 2026-10-10 and no credentials, so a wiki's change signal is that SHA, and the date of one page is the commit date of its file. [DER S-may2otwt, S-wze42rd7: a git call, not a REST API request]
- A wiki's file name is its page name (`Home.md` is `/wiki`, the Home page); the docs read do not state the mapping. [DER S-mm23ncwl, S-y23orbo7: one page]
- The REST repository object has `has_wiki` ("Whether the wiki is enabled") and the OpenAPI description has no wiki path, so the REST API gives no change signal for a wiki. [DOC S-o6lmrcgh]
- For `rust-lang/rust` the `.wiki.git` repository answered `ls-remote` and held a file `Doc-friends-of-the-tree.md`, while the page url `/wiki/Doc-friends-of-the-tree` answered `302` to the repository: a wiki repository that exists does not show that its web pages are served, and the cause was not found. [DER S-may2otwt, S-ghhbd6g6: one repository, one request each]

### Docs MCP servers and change feeds
- An MCP server that supports resources declares a `resources` capability with two optional sub-features, `listChanged` and `subscribe`; only `subscribe` lets a client follow updates of one resource. [DOC S-uq2hafxi]
- Asked to `initialize`, the Learn MCP server declared `logging`, `prompts`, `resources` and `tools` with `listChanged` only, and the Claude Code and MCP docs servers `tools` and `resources` with `listChanged` only; none declared `subscribe`. [DOC S2177, S2180, S2181]
- So none of the three documentation servers offers a per-page change feed; a change check has to poll the pages or their version signals. [DER S2177, S2180, S2181, S-uq2hafxi: declared capabilities read on 2026-09-28]

### Reference rot and content drift
- Klein et al. (PLoS ONE, 2014) name the combination of link rot and content drift "reference rot"; over a million web references in 3.5 million science, technology and medicine articles (1997-2012), one in five articles suffered from it, and seven in ten of those that cite web resources. [DOC S-shha3est]
- Jones et al. (PLoS ONE, 2016) found that for over 75% of web references with a representative archived snapshot, the live content had drifted from what it was when cited; representative snapshots existed for about 30% of references. [DOC S-wcrrjfwh]
- Jones et al. compared the text of snapshots with Simhash, Jaccard, Sørensen-Dice and cosine similarity, and used a high threshold to call two snapshots the same content; they dropped Spamsum because its input needs more than 4 KB of text, which about 70% of their comparisons lacked. [DOC S-wcrrjfwh]
- So a 200 answer on a cited URL says little: most references drift, and only text comparison (not the status code) shows it. [DER S-shha3est, S-wcrrjfwh]

### Change monitors, extraction and date rules
- urlwatch runs two filter stages per job: `filter` on the downloaded page before diffing and `diff_filter` on the diff before reporting; built-in filters include `css`, `element-by-id`, `html2text`, `format-json`, `pretty-xml`, `grep`, `grepi` and `re.sub`. [DOC S-a6bblnnl]
- urlwatch applies `filter` only to new content: the old content keeps the filter of the time it was retrieved, so a changed filter shows up in the next diff as a content change. [DOC S-a6bblnnl]
- changedetection.io (Apache-2.0) offers filters such as "Trigger on text", "Remove text by selector", "Ignore text" and "Extract text" (regular expressions too), targets elements with XPath 1 and 2, CSS selectors, JSONPath or jq, and can parse JSON embedded in an HTML page. [DOC S-gceoq2qq]
- changedetection.io's optional AI rules evaluate each detected diff against a plain-English intent and send the diff and extracted text to a third-party AI provider the user chooses. [DOC S-gceoq2qq]
- htmldate finds a page's original and updated dates in three steps: markup in the header (`link` and `meta` elements, Open Graph), structural markers in the whole document (`abbr`, `time`, attributes), then heuristics on the text, in a `fast` or an `extensive` mode; it is Apache-2.0 from v1.8.0, GPLv3+ before. [DOC S-yvdwutca]
- htmldate's README reports, on 1,000 pages with identifiable dates, precision 0.924 and recall 0.927 in `fast` mode and 0.908 and 0.993 in `extensive` mode. [DOC S-yvdwutca]
- trafilatura (Apache-2.0 from v1.8.0) extracts a page's main text with common patterns and falls back on generic algorithms such as jusText and readability, to leave out recurring headers and footers. [DOC S-niqtbnmc]

### Claim checks
- FEVER (Thorne et al., NAACL 2018) holds 185,445 claims made by altering Wikipedia sentences, each labelled Supported, Refuted or NotEnoughInfo, with the evidence sentences recorded for the first two. [DOC S-hgu2bdgi]
- Attributable to Identified Sources (AIS, Rashkin et al.) is a human evaluation framework for whether generated statements about the external world are supported by their underlying sources, with a two-stage annotation pipeline. [DOC S-wkj4aa2g]
- So a fact whose backing passage changed can be re-checked as a claim against the new passage with FEVER's three labels, which tells a contradicted fact (fix it) from one the new page no longer states (a gap). [DER S-hgu2bdgi, S-wkj4aa2g]

## Reference
- Cheapest check first, per Learn source: a `HEAD` or conditional `GET` with the stored ETag (`304` means unchanged); else the `updated_at`/`git_commit_id` from the first few KB of the page or its markdown form; then a text hash. Site level: sitemap diff for added and removed URLs, redirection files for moves. [DER S-7jumyiid, S-lldnrkhv, S-ecrpwvoh]
- `agents/doc-lookup-sources.md`: the servers and APIs used to read current docs, and the licence terms that decide whether old text may be kept.
- `python/stdlib-urllib-errors.md`: how a name-resolution, connection or timeout failure and an HTTP `304` surface in Python's `urllib`, for a retry that must not take one for the other.
- `agents/docs-maintenance-agents.md`: products that regenerate documentation; this article covers detecting changes in sources someone else publishes.
- `_tools/fetch.py --diff`: the kb's current text-hash check; `_fetch_state.csv` holds its hashes.

## Examples
- SNIPPET: check whether a cited Learn page changed since the stored ETag, then read its version fields; context: curl 8, any shell, placeholder page path; checked: run (2026-09-27, macOS, against a real Learn page) [DER S-7jumyiid: headers and front matter observed on the probed page]
```bash
# 304 = unchanged since the stored ETag
curl -s -o /dev/null -w "%{http_code}\n" \
  -H 'If-None-Match: "<stored-etag>"' \
  "https://learn.microsoft.com/en-us/<docset>/<page>"

# Version fields from the markdown form's front matter
curl -s "https://learn.microsoft.com/en-us/<docset>/<page>?accept=text/markdown" \
  | grep -E '^(updated_at|git_commit_id|document_id):'
```
