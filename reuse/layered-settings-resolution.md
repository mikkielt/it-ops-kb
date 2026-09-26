---
topic: reuse/layered-settings-resolution
priority: P2
applies_to: "layered settings resolution: flags > env vars > config file > built-in defaults, unknown-key refusal"
retrieved_utc: 2026-09-26
sources: [S1022, S1023]
status: complete
---

## Summary
`pydantic-settings` is a direct `dependency` fit and the clear leverage candidate in this whole reuse
pass: it already implements this precedence order and gives unknown-key refusal nearly for free via
Pydantic's `extra="forbid"`. Where `pydantic` is already a pinned dependency, `pydantic-settings` is a
natural, low-risk addition. `dynaconf` is a `no`: it does not natively refuse unknown keys and adds
provider surface (Vault, Redis) that a simple three-source precedence does not need, which simplicity
rules argue against.

## Facts
- `pydantic-settings`' `BaseSettings` resolves each field in order of precedence: init kwargs > env
  vars > `.env`/secrets file > field default, with a `settings_customise_sources` hook to reorder or
  add sources -- this is the same shape as a `flags > env vars > config file > built-in defaults`
  precedence (map init kwargs to parsed CLI flags, and add a config-file source via the hook). MIT
  licensed. [DOC S1022]
- Because `BaseSettings` is a Pydantic `BaseModel`, `model_config = SettingsConfigDict(extra="forbid")`
  makes any unrecognised key raise a validation error rather than being silently accepted -- this is
  general Pydantic "forbid extra fields" behaviour applied to settings, not a settings-specific
  feature, and covers an "unknown keys are refused" requirement; only the "message names the nearest
  real key" part (fuzzy-match suggestion) needs custom code (~20-30 lines), not the refusal itself.
  [DER S1022]
- `dynaconf` (MIT) supports layered sources (TOML/YAML/JSON/INI/.env files, env vars, multiple
  environments, and external providers like Vault/Redis merged in a defined order), but its own README
  does not state an unknown-key-refusal default -- unconfirmed whether it supports strict/refuse-unknown
  validation at all from the README alone. [DOC S1023]
- `dynaconf`'s external-provider surface (Vault, Redis as settings sources) is unneeded by a simple
  three-source precedence (flags/env/file/defaults) and would be a new dependency surface that
  simplicity-first design ("widening halts") argues against when `pydantic-settings` alone already
  covers the stated requirement. [DER S1023]

## Reference
| project | precedence order | unknown-key refusal | licence | reuse verdict |
|---|---|---|---|---|
| pydantic-settings | init kwargs > env > file > defaults (reorderable) | yes, via `extra="forbid"` | MIT | dependency |
| dynaconf | layered, env > per-environment file section > default file section > providers | not confirmed | MIT | no (unneeded surface; refusal unconfirmed) |

## Examples
No fixture data required.
