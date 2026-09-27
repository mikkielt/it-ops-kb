---
topic: arch/texts-catalogue-formats
priority: P1
applies_to: [fluent, gettext, powershell, power-bi]
retrieved_utc: 2026-09-26
sources: [S1709, S1710, S1711, S1712, S1713, S1714, S1715, S1716, S1717]
status: complete
---

# Text/label catalogue formats across consumers

## Summary
Fluent has an official, actively maintained Python runtime (`fluent.runtime` 0.4.0) but no official
PowerShell or Power BI runtime — those would need a custom reader or a different format. PowerShell's
native mechanism is `.psd1` files read by `Import-LocalizedData`. Power BI's only official
human-facing "translation" surface is Analysis Services tabular model metadata translations
(object names/descriptions), edited as `cultures/` files in TMDL — it does not consume arbitrary
label catalogues at report-render time. gettext (.po/.mo) has first-class Python stdlib support and
is the closest thing to a format with tooling on more than one of the four consumers.

## Facts
- `fluent.runtime` (PyPI) is the official Python implementation of Fluent, currently at 0.4.0,
  installed via `pip install fluent.runtime`, providing a `Localization`/`FluentBundle` API and
  supporting Fluent spec 1.0. [DOC S1709][DOC S1710]
- Fluent (FTL) syntax supports terms (`-term-name`), attributes (`.tooltip`), message references, and
  selector expressions for plurals/gender — features a real, multi-consumer label catalogue would want.
  [DOC S1711]
- No official PowerShell or Power BI Fluent runtime was found in official documentation or package
  search; Fluent's maintained runtimes are Python (`fluent.runtime`) and Rust (`fluent-rs`). [UNK]
- PowerShell's built-in internationalization mechanism is `Import-LocalizedData`, which reads a
  `.psd1` data file — produced from `ConvertFrom-StringData` or written directly as a hashtable —
  stored in a culture-named subdirectory next to the script (e.g. `de-DE/<script-name>.psd1`); when no file
  matches `$PSUICulture` it tries the language-only subdirectory (e.g. `de`), and failing that the variable
  keeps the script's default (Data-section) strings. [DOC S1712][DOC S1713]
- The translated `.psd1` files hold key/value strings that `ConvertFrom-StringData` turns into hash tables.
  [DOC S1712]
- PowerShell's documented localization path reads only these `.psd1` files; no built-in FTL or .po/.mo reader
  is documented. [DER S1712, S1713: the internationalization docs describe `.psd1` + `Import-LocalizedData` only]
- Python's standard library `gettext` module consumes compiled `.mo` files (compiled from `.po`),
  giving Python first-class gettext support without a third-party package. [DOC S1717]
- gettext's canonical `.po`/`.mo` format and tooling (`msgfmt`, `msgmerge`, plural-forms) is documented
  in the GNU gettext manual; PowerShell has no native `.po`/`.mo` reader in official docs. [DOC S1716]
- Analysis Services / Power BI Premium tabular models support "translations" as object-metadata-only strings
  (names and descriptions of tables and columns: `translatedCaption`, `translatedDescription`) per culture,
  shown by a client tool such as Excel when the connection specifies the culture; the feature is not meant
  for translated data values. [DOC S1714]
- TMDL view lets you create or edit semantic-model metadata that has no graphical interface in Power BI
  Desktop, translations among them, as TMDL scripts. [DOC S1715]
- Per-language translation files under a model's `cultures/` folder, and Translation Builder or Tabular
  Editor being needed before TMDL view. [UNK: not in S1715 as re-read 2026-09-27]

## Reference
- Python: `fluent.runtime.FluentLocalization(["en-US"], ["catalogue.ftl"], loader)`.
- PowerShell: `Import-LocalizedData -BindingVariable Strings` reading `en-US/catalogue.psd1`.
- Power BI: TMDL `cultures/en-US.tmdl` mapping object refs to translated `translatedCaption`.

## Examples
- A device-drift label like "compliant" would need: an FTL message `status-compliant = Compliant`
  for a Python CLI/MCP output; a `Strings.status_compliant = 'Compliant'` entry in a PowerShell
  `.psd1` for a baseline script's `Write-Verbose` text; and, only if Power BI report visuals show a
  translated table/column caption for a device's status field, a `cultures/en-US.tmdl` entry —
  Power BI has no hook for translating a computed measure's *value* text, only model metadata labels.

## Derivations
- A team keeping one catalogue as the single source of human-facing strings across a Python CLI, a
  PowerShell baseline script, and Power BI report metadata: because Fluent has no official
  non-Python consumer, holding FTL as the single source and generating per-consumer artifacts (a
  `.psd1` for PowerShell, a flat key/value table for Power BI metadata translations) is the only way
  to reach all consumers without asking PowerShell/Power BI to parse FTL themselves. A team that also
  wants to avoid committing generated accessor *code* can still do this, since a build step producing
  `.psd1`/CSV *data* (not code) keeps the generated files as data, not Python/PowerShell accessor
  functions. [DER S1710,S1712,S1714: no shared runtime across consumers forces FTL-as-source +
  data-only per-consumer build outputs]
- gettext is not obviously better than Fluent for a multi-consumer estate: it also lacks a
  PowerShell/Power BI runtime, and Fluent's terms/selectors give richer plural/gender handling than
  .po's plural-forms string — so gettext would only win if PowerShell tooling for .po existed, which
  official docs do not show. [DER S1716,S1717,S1712: neither format has cross-consumer native
  support, so runtime parity is not the deciding factor]

## Gaps
- Whether Power BI "field parameters" or a bound SQL/CSV table (rather than metadata translations)
  is realistically usable to localize report text was not confirmed against official docs within the
  fetch budget. [UNK]
