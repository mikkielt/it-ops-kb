---
topic: python/stdlib-unicode-normalization
priority: P3
applies_to: "CPython 3 stdlib: unicodedata.normalize, unicodedata.is_normalized, str.casefold"
retrieved_utc: 2026-10-27
sources: [S-dbbduccf, S-lyf4dv2j]
status: partial
---

# stdlib Unicode normalization and casefolding (matching words that differ only in spelling form)

## Summary
Two strings that look the same can differ in code points: a letter with a combining accent against its one-code-point
form, or `ß` against `ss`. The stdlib has two tools for matching them: `unicodedata.normalize` puts text in one of
four normal forms, and `str.casefold` removes case distinctions more aggressively than `lower`. A word index and the
query that searches it have to apply the same two steps to match.

## Facts
- `unicodedata.normalize(form, unistr)` returns the normal form of a string; the valid values of `form` are `'NFC'`, `'NFKC'`, `'NFD'` and `'NFKD'`. [DOC S-dbbduccf]
- `unicodedata.is_normalized(form, unistr)` says whether a string is already in the given form, with the same four values. [DOC S-dbbduccf]
- NFKC first applies the compatibility decomposition and then the canonical composition. [DOC S-dbbduccf]
- The page warns that two normalized strings that look the same to a reader may not compare equal if one has combining characters and the other does not. [DOC S-dbbduccf]
- `str.casefold()` returns a casefolded copy that may be used for caseless matching; it is similar to lowercasing but more aggressive, as it is meant to remove all case distinctions. [DOC S-lyf4dv2j]
- The German `ß` is already lowercase, so `'straße'.lower()` stays `'straße'` while `'straße'.casefold()` is `'strasse'`. [DOC S-lyf4dv2j]
- The casefolding algorithm is the one in section 3.13.3 "Default Case Folding" of the Unicode Standard, and `str.casefold` exists since Python 3.3. [DOC S-lyf4dv2j]
- A matcher that wants a decomposed `Könige` and `Straße` to meet `Könige` and `strasse` therefore normalizes both the indexed text and the query to one form (NFC) and compares casefolded words, because `lower` alone leaves `ß`. [DER S-dbbduccf, S-lyf4dv2j: normalize makes the code points equal, casefold removes the case distinctions that `lower` keeps]
- Whether `casefold` can return text that is no longer in NFC, and whether letters such as Polish `ł` split into a base letter and a combining mark under NFD, are not stated on either page; the pages were read for them on 2026-10-27. [UNK: the Unicode character database was not read]

## Reference
- unicodedata: https://docs.python.org/3/library/unicodedata.html
- str.casefold: https://docs.python.org/3/library/stdtypes.html

## Examples
- SNIPPET: compare two spellings after one normalization and a casefold; context: Python 3.3 or later; checked: no [DER S-dbbduccf, S-lyf4dv2j: calls named on the two pages]
```python
import unicodedata

def fold(text):
    return unicodedata.normalize("NFC", text).casefold()

fold("Straße") == fold("strasse")
```
