---
topic: reuse/layered-settings-resolution
priority: P2
applies_to: "layered settings resolution: flags > env vars > config file > built-in defaults, unknown-key refusal"
retrieved_utc: 2026-09-26
sources: [S1022, S1023, S-ovuvyg6h]
status: complete
---

## Summary
`pydantic-settings` is a direct `dependency` fit and the clear leverage candidate in this whole reuse
pass: it already implements this precedence order, and its default `extra='forbid'` refuses unmatched
dotenv entries, though unknown environment variables are ignored and need a custom check. Where `pydantic` is already a pinned dependency, `pydantic-settings` is a
natural, low-risk addition. `dynaconf` is a `no`: it does not natively refuse unknown keys and adds
provider surface (Vault, Redis) that a simple three-source precedence does not need, which simplicity
rules argue against.

## Facts
- `pydantic-settings`' `BaseSettings` takes a field's value in descending priority: CLI args (when
  `cli_parse_args` is enabled) > init kwargs > env vars > dotenv file > secrets directory > field default,
  and overriding `settings_customise_sources` reorders, adds or removes sources (first returned is
  highest). [DOC S-ovuvyg6h]
- That order has the same shape as a `flags > env vars > config file > built-in defaults` precedence:
  map parsed CLI flags to init kwargs (or enable its CLI source) and add a config-file source via the
  hook. [DER S-ovuvyg6h: the documented priority list and hook, mapped onto the target order]
- Unknown-key refusal is partial: the default `extra='forbid'` makes an unmatched dotenv entry raise a
  `ValidationError`, but an env var that matches no field is ignored even with `extra='forbid'`, so a
  misspelled variable silently leaves the default. [DOC S-ovuvyg6h]
- So an "unknown keys are refused" requirement needs custom code for environment variables (e.g.
  comparing prefixed names in the environment with the field names), in addition to any
  nearest-key-name message. [DER S-ovuvyg6h: follows from the env-var behaviour above]
- `dynaconf` (MIT) supports layered sources (TOML/YAML/JSON/INI/PY settings files loaded in the given
  order, env vars with dotenv support overriding them, optional per-environment layers, and Vault/Redis
  as settings and secrets storage), but its own README
  does not state an unknown-key-refusal default -- unconfirmed whether it supports strict/refuse-unknown
  validation at all from the README alone. [DOC S1023]
- `dynaconf`'s external-provider surface (Vault, Redis as settings sources) is unneeded by a simple
  three-source precedence (flags/env/file/defaults) and would be a new dependency surface that
  simplicity-first design ("widening halts") argues against when `pydantic-settings` alone already
  covers the precedence requirement. [DER S1023]

## Reference
| project | precedence order | unknown-key refusal | licence | reuse verdict |
|---|---|---|---|---|
| pydantic-settings | CLI (if enabled) > init kwargs > env > dotenv > secrets > defaults (reorderable) | partly: dotenv yes via default `extra='forbid'`, unknown env vars ignored | MIT | dependency |
| dynaconf | layered, env > per-environment file section > default file section > providers | not confirmed | MIT | no (unneeded surface; refusal unconfirmed) |

## Examples
No fixture data required.
