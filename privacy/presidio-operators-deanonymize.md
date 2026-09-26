---
topic: privacy/presidio-operators-deanonymize
priority: P0
applies_to: "presidio-anonymizer main @ e9895a5 (2.2.364 for released behaviour)"
retrieved_utc: 2026-09-26
sources: [S827, S828, S829, S830, S831, S832, S833, S834, S835, S836, S841, S845, S800]
status: complete
---
# Presidio anonymizer operators, custom operators, DeanonymizeEngine, REST limits

## Summary
- Built-in anonymize operators: `replace`, `redact`, `hash`, `mask`, `encrypt`, `custom`, `keep`, `surrogate_ahds`. Built-in deanonymize operators: `decrypt` and `deanonymize_keep`.
- `custom` takes a Python callable in `params["lambda"]` that must return `str`. The REST `/anonymize` endpoint rejects it with HTTP 400 "Custom type anonymizer is not supported".
- For reversible placeholders, the documented pattern is a user-written `Operator` subclass that holds an `entity_mapping` dict, paired with a matching deanonymize operator added through `DeanonymizeEngine.add_deanonymizer`.

## Facts
- The operators table lists replace (`new_value`, default `<ENTITY_TYPE>`), redact, hash (`hash_type` sha256/sha512, `salt`), mask (`chars_to_mask`, `masking_char`, `from_end`), encrypt (`key`), custom (`lambda`), surrogate_ahds, keep, and decrypt. [DOC S827]
- If no operator map or `DEFAULT` key is given, the default operator is `replace` with `<ENTITY_TYPE>`. [DOC S827]
- From 2.2.361 on, `hash` uses a random salt per entity by default. The same value only hashes the same when a `salt` is supplied (at least 128 bits, enforced). [DOC S827]
- `Custom.operate` calls `params["lambda"](text)` and raises `InvalidParamError` if the result is not `str`. `validate` only checks that it is callable and does not call it, to avoid side effects in stateful lambdas (issue #2024). [DOC S829]
- REST `/anonymize` raises `BadRequest("Custom type anonymizer is not supported")` if any operator's name is `custom`. [DOC S830]
- REST routes: `/health`, `POST /anonymize`, `POST /deanonymize`, `GET /anonymizers`, `GET /deanonymizers`. [DOC S830]
- New operators subclass `Operator` and implement `operate`, `validate`, `operator_name` and `operator_type` (Anonymize or Deanonymize). They are registered with `AnonymizerEngine.add_anonymizer` or `DeanonymizeEngine.add_deanonymizer`. [DOC S828]
- `DeanonymizeEngine.deanonymize(text, entities: List[OperatorResult], operators: Dict[str, OperatorConfig])` runs only Deanonymize-type operators. It also has `get_deanonymizers`, `add_deanonymizer` and `remove_deanonymizer`. [DOC S831]
- The engine injects `params["entity_type"]` before calling an operator. [DOC S832]
- The pseudonymization sample shows `InstanceCounterAnonymizer`, which produces `<{entity_type}_{index}>` and keeps a caller-held `entity_mapping`, and `InstanceCounterDeanonymizer`, which reverses it. The sample warns that it is not thread-safe. [DOC S833]
- The FAQ says pseudonymization is not built in; it points to a custom-lambda sample. [DOC S841]
- `encrypt`/`decrypt` use AES in CBC mode. The key must be 128, 192 or 256 bits (str or bytes). [DOC S835, S836]
- `BatchDeanonymizeEngine` (`deanonymize_list`, `deanonymize_dict`) exists in the 2.2.364 package tree. [DOC S845, S834]
- Presidio keeps no state between calls: "Presidio does not store or maintain stateful sessions". [DOC S827]
- Overlaps: with a full overlap, the higher score wins. When one entity contains another, the larger span wins. With a partial overlap, both are replaced and the results concatenated. [DOC S827]

## Reference
| Operator | Type | Reversible via built-in | REST |
|---|---|---|---|
| replace | Anonymize | no | yes |
| redact | Anonymize | no | yes |
| hash | Anonymize | no | yes |
| mask | Anonymize | no | yes |
| encrypt | Anonymize | yes (`decrypt`) | yes |
| keep | Anonymize | yes (`deanonymize_keep`) | yes |
| custom | Anonymize | no | **no (400)** |
| surrogate_ahds | Anonymize | no | not checked |
| decrypt | Deanonymize | n/a | yes |

## Examples
Placeholder style from the sample, applied to fixture data: `jan.kowalski logged on to PL-LT-00123` becomes `<PERSON_0> logged on to <HOST_0>`, and the mapping is `{"PERSON": {"jan.kowalski": "<PERSON_0>"}, "HOST": {...}}`. HOST needs a custom recognizer.
