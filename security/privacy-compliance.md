---
topic: security/privacy-compliance
priority: P2
applies_to: "GDPR; EDPB WP248 rev.01; UODO; NIS2 (Directive + Polish KSC amendment); DORA; EU AI Act, as of 2026-09-24"
retrieved_utc: 2026-09-26
sources: [S870, S1542, S-xvc5ligo, S1550, S-5jbvhlmx, S1552, S1553, S1554, S1555, S1556, S1557, S1558, S1559, S-qzdkyvqx]
status: partial
---

# Privacy and compliance facts (GDPR, NIS2, DORA, EU AI Act)

## Summary
Facts only, per a common decision rule (pseudonymization is for the model only, humans see real data under RBAC).
Covers GDPR Arts. 5/25/32/35 and the EDPB nine DPIA criteria applied to a device-management tool's data flows;
UODO's DPIA list; NIS2 Art. 21(2)(a)-(j) and the Polish KSC amendment status as of 2026-09-24; a DORA
conditional note; and the EU AI Act classification/timeline including the 2026 Digital Omnibus deferral.

## Facts
- GDPR Art. 5 sets the processing principles (lawfulness/fairness/transparency, purpose limitation, data
  minimisation, accuracy, storage limitation, integrity/confidentiality, accountability). [DOC S870]
- GDPR Art. 25 requires data protection by design and by default, including pseudonymisation as an example
  technical measure. [DOC S870]
- GDPR Art. 32 requires security measures appropriate to risk, naming pseudonymisation and encryption as examples,
  and a process for regularly testing/evaluating those measures. [DOC S870]
- GDPR Art. 35 requires a DPIA where processing is "likely to result in a high risk to the rights and freedoms of
  natural persons," and lists automated/profiling processing and large-scale processing of special-category data
  as examples that trigger it. [DOC S870]
- The WP29 Guidelines on DPIA (WP248 rev.01, adopted 2017-04-04, last revised 2017-10-04, endorsed by the EDPB 2018-05-25) set nine criteria;
  meeting two or more usually means a DPIA is required: (1) evaluation or scoring, (2) automated decision-making
  with legal or similarly significant effect, (3) systematic monitoring, (4) sensitive data or data of a highly
  personal nature, (5) data processed on a large scale, (6) matching or combining datasets, (7) data concerning
  vulnerable data subjects, (8) innovative use or application of new technological/organisational solutions,
  (9) processing that in itself "prevents data subjects from exercising a right or using a service or a contract."
  WP248 names employees among vulnerable data subjects (criterion 7). [DOC S-xvc5ligo]
- Applied to a device-management tool that ingests workstation logs (facts only, no verdict): device logs carry
  employee-linked identifiers (criterion 4, sensitive/highly personal in an employment-monitoring context)
  [DER S-xvc5ligo: device+user linkage is personal data about an identifiable employee]; pseudonymized data sent to
  an AI provider involves a processor outside the originating system (criterion 6 if combined with other datasets
  at the SQL layer) [DER S-xvc5ligo,S870]; systematic monitoring of workstation state across an estate over time can
  meet criterion 3 [DER S-xvc5ligo]. Whether two or more criteria are met in any actual deployment is a per-deployment
  question, not decided here.
- UODO (Urzad Ochrony Danych Osobowych) is Poland's supervisory authority under GDPR; it publishes a list of
  processing operations subject to mandatory DPIA under Art. 35(4), in Polish: an annex to the UODO President's
  communication of 2019-06-17, published in Monitor Polski on 2019-07-08 (M.P. 2019 poz. 666). [DOC S1550, S-5jbvhlmx]
- NIS2 (Directive (EU) 2022/2555) Art. 21(2) lists risk-management measures (a) policies on risk analysis and
  information-system security, (b) incident handling, (c) business continuity/crisis management, (d) supply-chain
  security including supplier relationships, (e) security in acquisition/development/maintenance including
  vulnerability handling and disclosure, (f) policies/procedures for effectiveness assessment, (g) basic cyber
  hygiene and training, (h) cryptography and encryption policies, (i) human-resources security/access
  control/asset management, (j) use of MFA/continuous authentication, secured voice/video/text and secured
  emergency communication. [DOC S1552]
- Poland transposes NIS2 through an amendment to the Act on the National Cybersecurity System (ustawa o krajowym
  systemie cyberbezpieczenstwa, UKSC/KSC). The Sejm adopted the amendment 2026-01-23, it was published as
  Dz.U. 2026 poz. 252, and it entered into force 2026-04-03. [DOC S1553]
- KSC amendment transition: entities that already qualify as key or important on entry into force must meet the
  act's Chapter 3 obligations (security-management system) within 12 months (Art. 33(1)), key entities run their
  first audit within 24 months (Art. 33(2)), and they file for entry in the register of key and important entities
  on a schedule the digital-affairs minister announces in an official communication (Art. 33(3), 34(3)); an entity
  that qualifies later applies within 6 months of meeting the criteria (new Art. 7c). [DOC S1553]
- The implementation deadline is therefore 2027-04-03; the act sets no fixed calendar date for registration
  of entities that already qualify. [DER S1553: in force 2026-04-03 + 12 months (Art. 33(1)); registration dates come from the minister's schedule (Art. 34(3))]
- Poland missed the original NIS2 transposition deadline (2024-10-17); the European Commission opened an
  infringement procedure with a reasoned opinion dated 2025-05-07. [COMMUNITY S1554]
- NIS2 essential/important entity status depends on sector (Annexes I/II of the Directive) and size thresholds
  (broadly, medium-or-larger enterprises in listed sectors, with some entities in scope regardless of size); the
  Directive does not decide a given operator's status. [DOC S1552]
- DORA (Regulation (EU) 2022/2554) applies to financial entities and their critical ICT third-party providers; it
  is noted here only as a conditional check — it applies only if the operating organisation is itself a financial
  entity in DORA's scope. [DOC S1555]
- The EU AI Act (Regulation (EU) 2024/1689) entered into force 2024-08-01, with staggered application dates:
  prohibited practices and AI-literacy obligations from 2025-02-02; governance rules and obligations for
  general-purpose AI models from 2025-08-02; and (originally) most other obligations, including Annex III
  high-risk systems, from 2026-08-02. [DOC S1556][DOC S1557]
- The Commission tabled a "Digital Omnibus on AI" proposal on 2025-11-19 to adjust several AI Act deadlines;
  Council/Parliament/Commission negotiators reached a provisional agreement on 2026-05-06, confirmed by Member
  State representatives in the Council on 2026-05-13. [COMMUNITY S1558]
- As adopted, application of the high-risk obligations (Chapter III, Sections 1-3) for systems classified under
  Art. 6(2) and Annex III is deferred to 2027-12-02, and for systems under Art. 6(1) and Annex I (AI in regulated
  products) to 2028-08-02. [DOC S-qzdkyvqx]
- The Digital Omnibus on AI, Regulation (EU) 2026/1744 of 2026-07-08, was published in the Official Journal
  2026-07-24 and entered into force on the third day after publication (2026-07-27), six days before the original
  2026-08-02 high-risk deadline it amends; EUR-Lex lists a consolidated AI Act version dated 2026-07-27.
  [DOC S-qzdkyvqx]
- An internal IT-operations assistant built as MCP/CLI tooling is not itself a component the AI Act treats
  as "AI" for tier-≥2 confirmed actions it takes, when those are deterministic code with a tier enforcement
  layer; the pseudonymization/model-boundary component that interprets device data and proposes actions is the
  part that could be assessed as a GPAI-model-using system. Classification under Annex III (high-risk use cases:
  e.g. employment, critical infrastructure) is a per-deployment question, not checked here. [UNK]

## Reference

| Instrument | Date | Status as of 2026-09-24 | Source |
|---|---|---|---|
| GDPR | in force since 2018-05-25 | in force | S870 |
| WP29 WP248 rev.01 (EDPB-endorsed) | adopted 2017-04-04, revised 2017-10-04, endorsed 2018-05-25 | current guidance | S-xvc5ligo |
| NIS2 Directive | OJ 2022-12-27 | in force; national transposition ongoing | S1552 |
| Poland KSC amendment | Dz.U. 2026 poz. 252 | in force 2026-04-03; registration per ministerial schedule; Chapter 3 obligations by 2027-04-03 | S1553 |
| DORA | OJ 2022-12-27 | in force 2025-01-17 (financial entities only) | S1555 |
| EU AI Act | OJ 2024-07-12 | staggered application; high-risk deferred to 2027-12-02 / 2028-08-02 by Reg. (EU) 2026/1744 | S1556, S-qzdkyvqx |

## Examples
Device logs for `PL-LT-00123`, linked to `jan.kowalski`, illustrate the employee-identifier criterion; no real
hostnames or user names are used.
