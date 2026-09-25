---
topic: prior-art/layered-settings-resolution
priority: P2
applies_to: "config precedence (flags > env > file > defaults), unknown-key refusal"
retrieved_utc: 2026-09-25
sources: [S1022, S1023]
status: complete
---

## Summary
pydantic-settings and dynaconf are the two established Python libraries for layered configuration
with defined source precedence. pydantic-settings is built directly on Pydantic's model validation,
so it rejects unknown keys the same way any Pydantic model does (`extra="forbid"`); dynaconf's own
README (fetched this session) advertises layered sources (files, env vars, Vault, Redis) and
multi-environment merging but its README does not itself state an unknown-key-refusal default.

## Facts
- pydantic-settings' `BaseSettings` resolves each field from, in order of precedence, ​keyword
  arguments passed to the class initialiser, environment variables, a `.env`/secrets file, and the
  field's declared default — later "settings sources" in that list are lower priority; this order and
  the mechanism (a `settings_customise_sources` hook to reorder/add sources) is stated in the
  project's own README. [DOC S1022]
- Because `BaseSettings` is a Pydantic `BaseModel` subclass, giving it `model_config = SettingsConfigDict(extra="forbid")`
  makes an unrecognised key in any source (env var mapped to an unknown field, or an unknown key in a
  loaded file) raise a validation error rather than being silently accepted; this is Pydantic's
  general "forbid extra fields" behaviour applied to settings, not a settings-specific feature. [DER S1022]
- dynaconf's README states it provides "Configuration Management for Python," supporting multiple
  file formats (TOML/YAML/JSON/INI/.env), environment-variable overrides, multiple environments
  (`development`/`production`/etc.), and external providers (Vault, Redis) as settings sources merged
  in a defined order; dynaconf is MIT licensed. [DOC S1023]
- dynaconf's fetched README does not state an unknown-key-refusal default (dynaconf's design instead
  merges any recognised key from any source into a single settings object); whether dynaconf supports
  strict/refuse-unknown-key validation was not confirmed from the README alone this session. [UNK]

## Reference
| project | precedence order (highest first) | unknown-key refusal | licence | language |
|---|---|---|---|---|
| pydantic-settings | init kwargs > env vars > dotenv/secrets file > field defaults (reorderable via a hook) | yes, via Pydantic `extra="forbid"` | MIT | Python |
| dynaconf | layered: env vars > active-environment file section > default file section > external providers (exact merge order documented on its own docs site, not fully re-derived here) | not confirmed in README | MIT | Python |

## Examples
No fixture data required.
