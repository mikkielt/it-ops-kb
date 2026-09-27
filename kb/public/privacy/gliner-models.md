---
topic: privacy/gliner-models
priority: P0
applies_to: "HF model repos at the pinned shas in gliner-models.csv"
retrieved_utc: 2026-09-27
sources: [S855, S856, S857, S858, S859, S860, S-zw4luelo, S-dcu4qhyp]
status: complete
---
# GLiNER PII model cards

## Summary
- `urchade/gliner_multi_pii-v1`: Apache-2.0; en, fr, de, es, pt, it.
- `knowledgator/gliner-pii-base-v1.0`: Apache-2.0; en (a `multilingual` tag, but the language list is en only).
- `nvidia/gliner-PII`: NVIDIA Open Model License Agreement; en; built on `urchade/gliner_large-v2.1`.
- All three are open-vocabulary: labels are passed at inference time. None is gated. Details are in `gliner-models.csv`.

## Facts
- urchade/gliner_multi_pii-v1: card `license: apache-2.0`, languages en/fr/de/es/pt/it, dataset `urchade/synthetic-pii-ner-mistral-v1`, last modified 2024-04-20. [DOC S855]
- Its card lists example PII types, including person, organization, phone number, email, ip address, username, serial number and license plate number. [DOC S856]
- knowledgator/gliner-pii-base-v1.0: `license: apache-2.0`, language en, last modified 2025-09-27. The card claims "60+ predefined PII categories" and zero-shot use. [DOC S857, S858]
- The knowledgator card's label list includes name, email address, phone number, ip address, url, username, password, account number, ssn and passport number. [DOC S858]
- nvidia/gliner-PII: `license: other`, `license_name: nvidia-open-model-license`, language en, last modified 2025-12-07. It is based on `urchade/gliner_large-v2.1`, covers "55+ categories", and the card says it is ready for commercial and non-commercial use. [DOC S859, S860]
- The nvidia card does not list all 55+ labels (its example uses `email`, `phone_number`, `user_name`). [DOC S860]
- The full nvidia label list is not published: the model card says 55+ categories, and its training dataset card (`nvidia/Nemotron-PII`, CC BY 4.0, 100,000 synthetic English records per the card) says only "55+ PII/PHI categories" with examples (names, SSNs, MRNs, addresses, phones, emails, account numbers); the labels exist only inside the dataset's `spans` data. [DOC S860, S-dcu4qhyp]
- NVIDIA Open Model License Agreement (last modified 2025-10-24): models are commercially usable, derivative models may be created and distributed, and NVIDIA claims no ownership of outputs. The licence is perpetual, worldwide, royalty-free but revocable: it ends if you sue claiming the model infringes copyright or patents, or if you bypass a guardrail without a substantially similar one. [DOC S-zw4luelo]
- Redistribution requires a copy of the agreement and a Notice file reading "Licensed by NVIDIA Corporation under the NVIDIA Open Model License"; use must follow NVIDIA's Trustworthy AI terms; NVIDIA may update the agreement for legal or regulatory reasons, and you then comply or stop using the model. [DOC S-zw4luelo]
- None of the three cards mentions hostnames, device names or GUIDs as labels. [DER S856,S858,S860: absent from the listed labels]

## Reference
See `gliner-models.csv` (columns: model_id, hf_sha, last_modified, licence, licence_link, languages, base_model, labels_documented, label_examples, gated, source_ids).

## Examples
Not applicable.
