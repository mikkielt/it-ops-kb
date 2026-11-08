---
topic: python/extension-api-versioning
priority: P3
applies_to: "Semantic Versioning 2.0.0, the PyPA version specifiers specification (PEP 440 as maintained on packaging.python.org), and Python 3.12 for the removal of distutils; a Python tool that publishes a versioned extension API and checks a plugin's declared version range"
retrieved_utc: 2026-11-08
sources: [S-f67thrzd, S-piurzx4u, S-ecm3ywfi]
status: partial
---

# Versioning an extension API: semantic versions and PEP 440 version ranges

## Summary
A tool that lets other groups plug code into it needs two things the plugin author can read: a version number that says what changed, and a range syntax a plugin uses to say which versions it works with. Semantic Versioning 2.0.0 gives the first: MAJOR for incompatible changes, MINOR for compatible additions and for any deprecation, PATCH for bug fixes, with major version zero meaning "anything may change". The PyPA version specifiers specification gives the second: comma-joined clauses such as `>=0.1, <0.3` or `~=1.4`, compared segment by segment with zero padding. The two agree on `MAJOR.MINOR.PATCH`, so a release number written that way can be read by either. This article records what the two documents state and, as `DER`, what that implies for a loader that holds a lower and an upper bound on `MAJOR.MINOR`; whether the standard library can parse a specifier is open.

## Facts
- Semantic Versioning: given `MAJOR.MINOR.PATCH`, increment MAJOR for incompatible API changes, MINOR for backwards-compatible functionality and PATCH for backwards-compatible bug fixes. [DOC S-f67thrzd]
- Software using Semantic Versioning must declare a public API, in the code or in documentation alone, and it "should be precise and comprehensive"; the numbering rules apply to that API, not to the private code. [DOC S-f67thrzd]
- Major version zero (`0.y.z`) is for initial development: "Anything may change at any time" and the public API should not be considered stable. Version 1.0.0 defines the public API, and the numbering rules for MAJOR, MINOR and PATCH bind from there. [DOC S-f67thrzd]
- Once a version is released its contents must not be modified; any change is released as a new version. [DOC S-f67thrzd]
- MINOR must be incremented when new backwards-compatible functionality enters the public API and when any public API functionality is marked deprecated; it may carry patch-level changes, and PATCH resets to 0. MAJOR must be incremented for any backwards-incompatible change to the public API, and MINOR and PATCH reset to 0. [DOC S-f67thrzd]
- To deprecate part of a public API, Semantic Versioning's FAQ asks for two things: update the documentation, and issue a new minor release with the deprecation in place; before the functionality is removed in a new major release "there should be at least one minor release that contains the deprecation". [DOC S-f67thrzd]
- Version elements compare numerically, so `1.9.0` is followed by `1.10.0`; a pre-release (`1.0.0-alpha`) has lower precedence than its normal version, and build metadata after a plus sign is ignored for precedence. [DOC S-f67thrzd]
- The PyPA specification says the `Major.Minor.Patch` aspects of semantic versioning (clauses 1 to 8 of the 2.0.0 text) are fully compatible with its own version scheme and that following them is encouraged, while semantic versions with a hyphen (pre-release) or a plus sign (build) are not permitted in the public version field. [DOC S-piurzx4u]
- A version's release segment is compared one numeric component at a time, and when two segments have different numbers of components the shorter one is padded with zeros; so `0.1` and `0.1.0` are the same release for `>=`, `<=`, `==` and `~=`. [DOC S-piurzx4u]
- A version specifier is a series of clauses separated by commas, and the comma means logical and: a candidate must match every clause. The operators are `~=` (compatible release), `==`, `!=`, `<=` and `>=` (inclusive ordered), `<` and `>` (exclusive ordered) and `===` (arbitrary equality); whitespace around an operator and a comma is optional. [DOC S-piurzx4u]
- The compatible release clause `~= V.N` is approximately `>= V.N, == V.*`, so `~=2.2` means `>=2.2, ==2.*` and `~=1.4.5` means `>=1.4.5, ==1.4.*`; it must not be used with a single segment such as `~=1`, and a trailing zero widens the prefix that must match (`~=2.2.0` is `>=2.2.0, ==2.2.*`). [DOC S-piurzx4u]
- The example list in the specification reads `~=3.1.2` as 3.1.2 or later but not 3.2.0 or later, and `== 3.1` as specifically 3.1 or 3.1.0, excluding pre-releases, post-releases, developmental releases and any 3.1.x maintenance release. [DOC S-piurzx4u]
- The exclusive ordered comparison `<V` must not allow a pre-release of `V` unless `V` is itself a pre-release, and `>V` must not allow a post-release of `V` unless `V` is one; the inclusive operators `>=` and `<=` compare by position in the version order. [DOC S-piurzx4u]
- Python 3.12 removed the `distutils` package from the standard library (PEP 632), and its release notes name the third-party Setuptools as the way to keep `distutils` available. [DOC S-ecm3ywfi]
- So for a plugin that declares `>=0.1, <0.3` against an API at `0.2.4`, a loader may compare numbers, never strings (`0.10` is later than `0.9`); with `0.y.z` the minor number is the compatibility boundary, because semantic versioning promises nothing within major zero, so an upper bound at the next minor is the narrowest range that still takes every release of the line the plugin was written for. [DER S-f67thrzd, S-piurzx4u: major zero is unstable; numeric segment comparison; `<V` excludes pre-releases of `V`]
- So a loader that keeps a plugin's declared range as two bounds on `MAJOR.MINOR` (lower inclusive, upper exclusive) needs only integer comparison of the first two release components; the three-component form with zero padding gives the same answer for a release number `MAJOR.MINOR.PATCH` and does not need the `~=` operator's prefix rule. [DER S-piurzx4u: zero padding of release segments and the ordered operators]
- Whether the Python standard library has any module that parses a PEP 440 version specifier or compares versions is not stated in the pages read (the specification page, the `importlib.metadata` page and the 3.12 release notes), so a tool that may use only the standard library compares release numbers itself until a page says otherwise. [UNK: not read; logged in `_gaps.md`]

## Reference
- Related: `python/imports-and-modules.md` (entry points, `import_module`, how a loader finds a plugin named `module:attr`), `python/version-lifecycle.md` (CPython's own release cycle), `python/uv-projects.md` (dependency ranges in a project file), `gitlab/git-trailers-and-hooks.md` (git tags that mark a release).
- SNIPPET: compare a `MAJOR.MINOR.PATCH` string with a lower and an upper bound on its first two components, with no third-party package; context: Python 3.11+, standard library only; checked: syntax [DER S-piurzx4u: numeric, zero-padded release segments compared one component at a time]
```python
import re

def release(text):
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", text.strip())
    if not match:
        raise ValueError(f"not MAJOR.MINOR[.PATCH]: {text!r}")
    return tuple(int(part or 0) for part in match.groups())

def within(version, lower, upper):
    return release(lower)[:2] <= release(version)[:2] < release(upper)[:2]
```

## Examples
- A plugin written against API `0.2.0` declares `>=0.2, <0.3`: API `0.2.7` (a bug fix) loads, `0.3.0` is refused because major zero allows a break in any minor release.
- After API `1.0.0`, a deprecated entry stays through at least one `1.y.0` release, and its removal waits for `2.0.0`.
