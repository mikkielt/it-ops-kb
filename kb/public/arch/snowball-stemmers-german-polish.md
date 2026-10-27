---
topic: arch/snowball-stemmers-german-polish
priority: P3
applies_to: "Snowball stemming algorithms for German and Polish (snowballstem.org, Snowball 3.x)"
retrieved_utc: 2026-10-27
sources: [S-k2zlxtqe, S-fxygye2y, S-clmrkdlz, S-h5kd4vwq]
status: partial
---

# Snowball stemmers and stop words for German and Polish (data a language profile can start from)

## Summary
Snowball publishes suffix-stripping stemmers as written algorithms, and a German stop word list; for Polish it
publishes the stemmer. A search tool that stems and drops stop words by language can write its per-language rules from
these pages, which are under the 3-clause BSD licence. A Polish stop word list is not among them.

## Facts
- Snowball has a Polish stemming algorithm page, which holds the algorithm, its Snowball source and a sample vocabulary with the stemmed forms. [DOC S-fxygye2y]
- The German algorithm page says its umlaut removal is a natural step of stemming, because the umlaut is a regular feature of German plural formation, and that this leads to certain false conflations. [DOC S-k2zlxtqe]
- Snowball 3.0.0 merged the former `german2` variant into the standard German algorithm, so it handles the ASCII transliterations of umlauts. [DOC S-k2zlxtqe]
- The German page says Swiss German always writes `ss` for `ß` and that the 1996 spelling reform replaced `ß` with `ss` in some words. [DOC S-k2zlxtqe]
- The Polish algorithm page lists the extra letters of the Polish alphabet as ą, ć, ę, ł, ń, ó, ś, ź and ż, and calls Polish a heavily inflected language with several patterns for nouns and verbs. [DOC S-fxygye2y]
- The Polish algorithm changed in Snowball 3.1.0: after a noun, adjective or verb suffix is removed, an apostrophe at the end of the stem is removed too. [DOC S-fxygye2y]
- The German stop word list is a plain text file in which a vertical bar starts a comment and each stop word is at the start of a line, with an English gloss after the bar (`und | and`). [DOC S-clmrkdlz]
- The Snowball site says all its software is covered by the 3-clause BSD licence, except where noted; anyone given the software must be told of the licence. [DOC S-h5kd4vwq]
- A language profile for German and Polish can therefore take its German stop words and both stemmers' suffix rules from Snowball, and has to find a Polish stop list elsewhere. [DER S-clmrkdlz, S-fxygye2y, S-h5kd4vwq: stop list and stemmer pages, licence page]
- A Polish stop word list under the `algorithms/polish/` path of the site, like the German `stop.txt`, returned HTTP 404 on 2026-10-27; no other source of one was read. [UNK: the Snowball repository and other Polish lists were not searched]

## Reference
- Algorithms: https://snowballstem.org/algorithms/
- German stemmer: https://snowballstem.org/algorithms/german/stemmer.html
- Polish stemmer: https://snowballstem.org/algorithms/polish/stemmer.html
- German stop list: https://snowballstem.org/algorithms/german/stop.txt
- Licence: https://snowballstem.org/license.html

## Examples
