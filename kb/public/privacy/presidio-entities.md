---
topic: privacy/presidio-entities
priority: P0
applies_to: "Presidio main @ e9895a5; since-version from tags 2.2.355-2.2.364"
retrieved_utc: 2026-09-26
sources: [S809, S810, S811, S812, S813, S814, S815, S816, S817, S818, S819, S820, S843, S844]
status: complete
---
# Presidio supported entities

## Summary
- `presidio-entities.csv` beside this file lists 100 rows. Each row is an entity, its recognizer class, country (ISO code or `global`), languages, whether it is enabled by default, the first release that contains the class, and the source file.
- 17 rows are global (including the 5 spaCy NER rows) and the rest are country-specific (18 countries). Most country recognizers are **disabled by default**.
- NER entities (`PERSON`, `LOCATION`, `NRP`, `DATE_TIME`, `ORGANIZATION`) come from `SpacyRecognizer` through the NLP engine. `ORGANIZATION` is in `labels_to_ignore` in the default NLP config.

## Facts
- The docs page lists global entities CREDIT_CARD, CRYPTO, DATE_TIME, EMAIL_ADDRESS, IBAN_CODE, IP_ADDRESS, MAC_ADDRESS, NRP, LOCATION, PERSON, PHONE_NUMBER, MEDICAL_LICENSE, URL, UUID, plus per-country tables. [DOC S810]
- `default_recognizers.yaml` sets `supported_languages: [en]` and `global_regex_flags: 26`. It marks recognizers with `enabled: false` and `country_code`. [CODE S809: presidio_analyzer/conf/default_recognizers.yaml#L1-L20]
- `SpacyRecognizer.ENTITIES = ["DATE_TIME","NRP","LOCATION","PERSON","ORGANIZATION"]`. [CODE S844: predefined_recognizers/nlp_engine_recognizers/spacy_recognizer.py#SpacyRecognizer.ENTITIES]
- The default NLP config maps spaCy labels PER/PERSON→PERSON, NORP→NRP, FAC/LOC/GPE/LOCATION→LOCATION, ORG→ORGANIZATION, DATE/TIME→DATE_TIME, and ignores ORGANIZATION, CARDINAL, EVENT, LANGUAGE, LAW, MONEY, ORDINAL, PERCENT, PRODUCT and others. [CODE S843: presidio_analyzer/conf/default.yaml#ner_model_configuration]
- `MAC_ADDRESS` (`MacAddressRecognizer`) first appears in 2.2.361. [CODE S817: presidio_analyzer/predefined_recognizers/__init__.py#MacAddressRecognizer]
- `UUID`, `CA_POSTAL_CODE`, `PH_PASSPORT`, the US healthcare-admin identifiers, and nine `ZA_*` recognizers are in no release yet (only on `main`). [DER S820,S809: class name absent from 2.2.364 `__init__.py` but present on main]
- On `main` the recognizers enabled by default are 10 global pattern recognizers (CREDIT_CARD, CRYPTO, DATE_TIME, EMAIL_ADDRESS, IBAN_CODE, IP_ADDRESS, MAC_ADDRESS, PHONE_NUMBER, URL, UUID), plus ES/IT/PL/UK_NHS/US legacy ones. Non-`en` ones only run when the analyzer runs that language. [CODE S809: presidio_analyzer/conf/default_recognizers.yaml#recognizers]
- There is no recognizer for hostnames, Windows computer names, UPNs (other than as EMAIL_ADDRESS), AD SIDs, or serial numbers. [DER S809,S810: none listed in either]

## Reference
- `presidio-entities.csv` columns: `entity,recognizer,country,languages,enabled_by_default,since_version,type,source_file`.
- `since_version`: the first tag among 2.2.355-2.2.364 whose `predefined_recognizers/__init__.py` names the class (S811-S820). `<=2.2.355` means it was already present in the oldest tag checked. `unreleased (main e9895a5)` means it is not in 2.2.364.
- `(configured per instance)` rows (`HuggingFaceNerRecognizer`, `BasicLangExtractRecognizer`) have entities set in configuration. Both are disabled by default.

## Examples
`EMAIL_ADDRESS` matches `jan.kowalski@corp.example.com`. `IP_ADDRESS` matches `10.0.0.5`. `PL-LT-00123` matches no built-in entity. This is derived from the lists above and was not run.
