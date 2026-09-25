---
topic: privacy/spacy-model-licence
priority: P0
applies_to: "en_core_web_lg 3.8.0 (GitHub) / 3.7.1 (Hugging Face)"
retrieved_utc: 2026-09-23
sources: [S850, S851, S852, S833]
status: complete
---
# spaCy en_core_web_lg licence

## Summary
- `en_core_web_lg` is licensed **MIT** by Explosion. Both the GitHub release 3.8.0 and the Hugging Face card (3.7.1) say so.
- 3.8.0 (2024-09-30) is the newest GitHub release. It requires spaCy `>=3.8.0,<3.9.0` and is 382 MB. Its NER labels include PERSON, ORG, GPE, LOC, FAC, NORP, DATE and TIME.

## Facts
- GitHub release `en_core_web_lg-3.8.0` (2024-09-30): License `MIT`, author Explosion, spaCy `>=3.8.0,<3.9.0`, size 382 MB. [DOC S850]
- It lists training sources OntoNotes 5, ClearNLP conversion, WordNet 3.0, and Explosion Vectors. [DOC S850]
- NER labels: CARDINAL, DATE, EVENT, FAC, GPE, LANGUAGE, LAW, LOC, MONEY, NORP, ORDINAL, ORG, PERCENT, PERSON, PRODUCT, QUANTITY, TIME, WORK_OF_ART. NER scores: P 85.21, R 85.87, F 85.54. [DOC S850]
- Published checksums: wheel sha256 `293e9547a655b25499198ab15a525b05b9407a75f10255e405e8c3854329ab63`, tar.gz `7a3c89f3243950000a102c5f124277bbbde2dec467d548eee28b23bd1938ed62`. [DOC S850]
- Hugging Face `spacy/en_core_web_lg`: `license: mit`, last modified 2023-11-21 (sha 557bf75). The repo contains `LICENSE` and `LICENSES_SOURCES` files. [DOC S851]
- The spacy.io models page builds its model details on the client side, and the static HTML has no licence text. [DOC S852]
- The Presidio sample installs the model with `python -m spacy download en_core_web_lg`. [DOC S833]
- The licence terms of the training-data sources (in `LICENSES_SOURCES`) were not read. [UNK]

## Reference
| Source | Version | Licence |
|---|---|---|
| GitHub explosion/spacy-models release | 3.8.0 | MIT |
| Hugging Face spacy/en_core_web_lg | 3.7.1 (2023-11) | MIT |

## Examples
Not applicable.
