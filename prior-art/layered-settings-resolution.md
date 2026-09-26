---
topic: prior-art/layered-settings-resolution
priority: P2
applies_to: "config precedence (flags > env > file > defaults), unknown-key refusal"
retrieved_utc: 2026-09-26
sources: [S1022, S1023, S-ovuvyg6h]
status: complete
---

## Summary
pydantic-settings and dynaconf are the two established Python libraries for layered configuration
with defined source precedence. pydantic-settings is built directly on Pydantic's model validation,
and its default `extra='forbid'` rejects unmatched dotenv entries, though environment variables that match no field are ignored; dynaconf's own
README (fetched this session) advertises layered sources (files, env vars, Vault, Redis) and
multi-environment merging but its README does not itself state an unknown-key-refusal default.

## Facts
- pydantic-settings' `BaseSettings` takes a field's value from, in descending priority: CLI arguments
  (only when `cli_parse_args` is enabled), keyword arguments to the class initialiser, environment
  variables, a dotenv (`.env`) file, the secrets directory, and finally the field's default. Overriding
  `settings_customise_sources` changes this: the order of the returned sources sets the priority (first is
  highest), and sources can be added or removed. This is in the project's documentation, not its README. [DOC S-ovuvyg6h]
- Unknown keys are refused only in part: the settings `extra` default is `'forbid'`, so an unmatched
  dotenv entry raises a `ValidationError`, but an environment variable that matches no field is ignored
  even with `extra='forbid'` (a misspelled name silently leaves the default in place); inside a nested
  model with `extra='forbid'`, an unknown key in a variable that matches the field's nested prefix can raise. [DOC S-ovuvyg6h]
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
| pydantic-settings | CLI args (if enabled) > init kwargs > env vars > dotenv > secrets dir > field defaults (reorderable via a hook) | partly: unmatched dotenv entries raise under the default `extra='forbid'`; unknown env vars are ignored | MIT | Python |
| dynaconf | layered: env vars > active-environment file section > default file section > external providers (exact merge order documented on its own docs site, not fully re-derived here) | not confirmed in README | MIT | Python |

## Examples
No fixture data required.
