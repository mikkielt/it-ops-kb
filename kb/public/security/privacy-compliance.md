---
topic: security/privacy-compliance
priority: P2
applies_to: "GDPR; EDPB WP248 rev.01; UODO; NIS2 (Directive + Polish KSC amendment); DORA; EU AI Act, as of 2026-09-24"
retrieved_utc: 2026-09-27
sources: [S870, S1542, S-xvc5ligo, S1550, S-5jbvhlmx, S1552, S1553, S1554, S1555, S1556, S1557, S1558, S1559, S-qzdkyvqx, S-tzbutlvs, S-k2bxn62w, S-nzqme6xu, S-twztbg3z, S-zg4p62eo, S-k3lipqns]
status: complete
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
- The UODO list (in Polish) has 12 criteria built on WP248: evaluation or scoring, automated decisions, systematic
  monitoring, special-category data, biometrics, genetic data, large scale, matching of datasets, data subjects
  dependent on those assessing them, innovative technology, processing that blocks a right or service, and location
  data; meeting two usually requires a DPIA, and sometimes one is enough. Under systematic monitoring it names
  workplaces that monitor IT systems, e-mail, software used and access cards, with the example of systems that
  monitor employees' working time and the flow of information in their tools (e-mail, Internet), marked as
  systematic monitoring plus vulnerable data subjects. [DOC S-k3lipqns]
- So device-log collection that tracks what employees run and do on their workstations matches UODO's own
  workplace-monitoring example, which already combines two criteria; a Polish deployment should expect a DPIA.
  [DER S-k3lipqns: the tool's device-log flow compared with criterion 3's example]
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
- Member States had to transpose NIS2 by 2024-10-17; on 2025-05-07 the Commission sent reasoned opinions to 19
  Member States, Poland among them, for failing to notify full transposition, giving them two months to respond
  before a possible referral to the Court of Justice. The Commission's Poland page still gives that reasoned
  opinion as the transposition status (read 2026-09-27). [DOC S-k2bxn62w, S-nzqme6xu]
- NIS2 essential/important entity status depends on sector (Annexes I/II of the Directive) and size thresholds
  (broadly, medium-or-larger enterprises in listed sectors, with some entities in scope regardless of size); the
  Directive does not decide a given operator's status. [DOC S1552]
- DORA (Regulation (EU) 2022/2554) applies to financial entities and their critical ICT third-party providers; it
  is noted here only as a conditional check — it applies only if the operating organisation is itself a financial
  entity in DORA's scope. [DOC S1555]
- NIST AI 600-1 (the Generative AI profile) lists Data Privacy among the risks unique to or made worse by generative AI: leakage and unauthorized use, disclosure or de-anonymization of PII or other sensitive data. It notes that models may leak, generate or correctly infer sensitive information about individuals, including PII that was neither in the training data nor disclosed by the user, by combining information from separate sources. [DOC S1542]
- The EU AI Act (Regulation (EU) 2024/1689) entered into force 2024-08-01, with staggered application dates:
  prohibited practices and AI-literacy obligations from 2025-02-02; governance rules and obligations for
  general-purpose AI models from 2025-08-02; and (originally) most other obligations, including Annex III
  high-risk systems, from 2026-08-02. [DOC S1556][DOC S1557]
- The Commission proposed the "Digital Omnibus on AI" on 2025-11-19; its press release of 2026-05-07 welcomes the
  political agreement "reached today" between Parliament and Council, with high-risk rules for Annex III areas from
  2027-12-02 and for AI in products from 2028-08-02, a new ban on AI that generates non-consensual intimate content
  or CSAM, SME privileges extended to small mid-caps and stronger AI Office powers. [DOC S-tzbutlvs]
- A law-firm alert dates the provisional agreement 2026-05-06 and a Council confirmation 2026-05-13; the
  Commission release dates the agreement 2026-05-07, and the Council's own page could not be read (browser check).
  [COMMUNITY S1558]
- As adopted, application of the high-risk obligations (Chapter III, Sections 1-3) for systems classified under
  Art. 6(2) and Annex III is deferred to 2027-12-02, and for systems under Art. 6(1) and Annex I (AI in regulated
  products) to 2028-08-02. [DOC S-qzdkyvqx]
- The Digital Omnibus on AI, Regulation (EU) 2026/1744 of 2026-07-08, was published in the Official Journal
  2026-07-24 and entered into force on the third day after publication (2026-07-27), six days before the original
  2026-08-02 high-risk deadline it amends; EUR-Lex lists a consolidated AI Act version dated 2026-07-27.
  [DOC S-qzdkyvqx]
- A Cloud Security Alliance research note reads the enacted omnibus the same way (Annex III to 2027-12-02, Annex I to 2028-08-02) and adds that Article 50 transparency duties stayed on the 2026-08-02 schedule, and that the final text differs from the May 2026 provisional agreement: narrower high-risk scope for machinery-embedded AI, a softer AI-literacy mandate, wider EU AI Office supervision and simpler registration for self-assessed systems. [COMMUNITY S1559]
- The Commission's guidelines on the AI system definition (C(2025) 5053, non-binding) make the capability to infer
  the indispensable condition and, quoting Recital 12, exclude "systems that are based on the rules defined solely
  by natural persons to automatically execute operations"; basic data processing that follows predefined,
  explicit instructions without learning, reasoning or modelling (e.g. database queries) is outside the
  definition. [DOC S-twztbg3z]
- So in an IT-operations assistant the deterministic parts (the CLI/MCP tools, the tier enforcement layer that
  executes confirmed actions) are rule-based software, while the model that interprets device data and proposes
  actions is the component that makes the whole an AI system; whether that system is high-risk under Annex III
  (e.g. employment, critical infrastructure) is a per-deployment question, not decided here. [DER S-twztbg3z:
  the definition's inference test and Recital 12 exclusion applied to the tool's parts]
- Controller and processor for an internal shared service: EDPB Guidelines 07/2020 (v2.0, 2021-07-07) say it is
  usually the organisation, not a department, that is the controller; a processor must be a **separate entity**,
  so a department cannot be a processor to another department of the same entity, and staff processing under
  the controller's direct authority are not processors, while another company in the same group can be one.
  [DOC S-zg4p62eo]
- So an internal NER/pseudonymisation endpoint run by one team for others in the same legal entity adds no
  processor relationship; one run by a separate group company, or an external AI provider, is a processor and
  needs an Art. 28 contract. [DER S-zg4p62eo, S870: separate-entity test applied to a shared service; Art. 28 GDPR]

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
