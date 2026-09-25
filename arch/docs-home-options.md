---
topic: arch/docs-home-options
priority: P1
applies_to: [gitlab-pages, mkdocs]
retrieved_utc: 2026-09-24
sources: [S1730, S1731, S1732, S1733]
status: complete
---

# Docs home hosting options

## Summary
GitLab Pages can publish a strict-built MkDocs site from a subdirectory of an existing code
repository, or from a dedicated repository; both are supported patterns. Self-managed Pages access
control is opt-in (disabled by default) and, once enabled, gates private-site viewers through GitLab
OAuth.

## Facts
- `mkdocs build --strict` (short form `-s`) turns every logged warning into a build failure, instead
  of the default behaviour of only printing warnings. [DOC S1732]
- GitLab Pages access control is disabled by default on self-managed instances; enabling it requires
  admin configuration (`/etc/gitlab/gitlab.rb` + reconfigure), after which an unauthenticated request
  to a private Pages site is redirected to GitLab for OAuth login, with the resulting token persisted
  in a signed cookie. [DOC S1731]
- GitLab Pages can be built and published from any project via `.gitlab-ci.yml`, including one where
  the docs source lives in a subdirectory (e.g. `docs/`) of a repository that also holds application
  code — the Pages job's `artifacts.paths` just needs to point at the built `public/` directory,
  wherever in the repo the source came from. [DOC S1730][DOC S1733]
- A dedicated docs repository is equally supported; GitLab Pages has no requirement that the
  publishing project be docs-only. [DOC S1730]

## Reference
```yaml
pages:
  stage: docs
  script:
    - mkdocs build --strict --site-dir public
  artifacts:
    paths: [public]
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## Examples
- A project's docs home could be an in-repo `docs/` subdirectory built to Pages on `main`, or a
  separate dedicated docs repository — both are equally valid per GitLab docs; the choice is a team
  decision, not a platform constraint. [DOC S1730]

## Derivations
- A team that wants code repositories to hold only code, generated reference and a short README, with
  explanations living in a strict-built docs home, can satisfy that either way GitLab supports: an
  in-repo `docs/` subdirectory or a separate repo. When the docs home must cover *two or more* code
  repositories with one audience-split site, a separate dedicated docs repository avoids picking one
  code repo as the "primary" home and needing to source pages from the others — this favours a
  dedicated repo, though GitLab does not require it. [DER S1730,S1733: a multi-repo docs home is
  simpler as its own repo, not because GitLab needs it to be]
