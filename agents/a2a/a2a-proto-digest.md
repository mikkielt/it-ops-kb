---
topic: agents/a2a/a2a-proto-digest
priority: P2
applies_to: "A2A protocol spec v1.0.0 (proto, commit 43e0c874d3baba68ed84b98678d7f2268438e69f)"
retrieved_utc: 2026-09-25
sources: [S2120, S2121, S2122]
status: complete
---

## Summary

`a2a.proto` is the normative definition of the Agent2Agent (A2A) protocol; JSON artifacts are generated, non-normative build outputs [DOC S2120]. The file is pinned here at commit `43e0c874d3baba68ed84b98678d7f2268438e69f` of `github.com/a2aproject/A2A`, path `specification/a2a.proto`, 812 lines, sha256 `945df6e34001b2bfd0fd62d9484b63094dfad9d78705e41e2873441c419ae2d1` [DOC S2121,S2122]. Saved locally as `kb/agents/a2a/a2a.proto`.

## Facts

- The proto is the single source of truth; the spec text and generated JSON Schema are derived from it and must not be hand-edited independently [DOC S2120].
- Repository licence is Apache-2.0 [DOC S2121].
- Governance: the repository is described as an open source project under the Linux Foundation, contributed by Google [DOC S2121].
- To re-verify the pin: `git ls-remote https://github.com/a2aproject/A2A.git HEAD` should still resolve `main` past this commit; fetch `specification/a2a.proto` at the pinned sha and recompute sha256 to compare against the digest above [DER S2121,S2122].

## Reference

| field | value |
|---|---|
| repo | github.com/a2aproject/A2A |
| pinned commit | 43e0c874d3baba68ed84b98678d7f2268438e69f |
| file path | specification/a2a.proto |
| lines | 812 |
| sha256 | 945df6e34001b2bfd0fd62d9484b63094dfad9d78705e41e2873441c419ae2d1 |
| licence | Apache-2.0 |

## Examples

Not applicable (protocol artifact, no worked example).
