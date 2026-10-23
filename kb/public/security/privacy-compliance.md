---
topic: security/privacy-compliance
priority: P2
applies_to: "GDPR; EDPB WP248 rev.01; UODO; NIS2 (Directive + Polish KSC amendment); DORA; EU AI Act, as of 2026-09-24"
retrieved_utc: 2026-09-27
sources: [S870, S1542, S-xvc5ligo, S1550, S-5jbvhlmx, S1552, S1553, S1555, S1556, S1557, S1558, S1559, S-qzdkyvqx, S-tzbutlvs, S-k2bxn62w, S-nzqme6xu, S-twztbg3z, S-zg4p62eo, S-k3lipqns, S-rebms33k, S-nnq2ftfq, S-etw2ppgz, S-sxwkpb6d, S-7ddlgwua]
status: complete
---

# Privacy and compliance facts (GDPR, NIS2, DORA, EU AI Act)

## Summary
Facts only, per a common decision rule (pseudonymization is for the model only, humans see real data under RBAC).
Covers GDPR Arts. 5/25/32/35 and the EDPB nine DPIA criteria applied to a device-management tool's data flows;
UODO's DPIA list; NIS2 Art. 21(2)(a)-(j) and the Polish KSC amendment status as of 2026-09-24; a DORA
conditional note; and the EU AI Act classification/timeline including the 2026 Digital Omnibus deferral.

## Facts
- GDPR Art. 5 sets the processing principles; the EDPB Guidelines 01/2025 name fairness (Art. 5(1)(a)), purpose limitation (b), data minimisation (c), accuracy (d) and confidentiality (f) among them and refer to Art. 5(2) for demonstrating compliance with the principles. [DOC S-rebms33k]
- The full list of Art. 5 principles (lawfulness/fairness/transparency, purpose limitation, data minimisation, accuracy, storage limitation, integrity/confidentiality, accountability) was read from the Regulation's EUR-Lex text (S870) on 2026-09-26 and is not re-confirmed on 2026-10-23: EUR-Lex answers this host with an empty bot-challenge page. [UNK: logged in `_gaps.md`]
- GDPR Art. 25(1): the EDPB Guidelines 01/2025 say pseudonymisation may be used as one of several technical and organisational measures to implement data-protection principles under Art. 25(1), in particular data minimisation and confidentiality, and apply data protection by default under Art. 25(2) in their examples. [DOC S-rebms33k]
- GDPR Art. 32(1): the EDPB Guidelines 01/2025 say pseudonymisation may be used as one of several measures contributing to a level of security appropriate to the risk, in accordance with Art. 32(1), and that it helps meet obligations such as those under Art. 25 or 32. [DOC S-rebms33k]
- That Art. 32 names encryption as a further example and requires a process for regularly testing and evaluating the measures was read from the Regulation's EUR-Lex text (S870) on 2026-09-26 and is not re-confirmed on 2026-10-23: EUR-Lex answers this host with an empty bot-challenge page. [UNK: logged in `_gaps.md`]
- GDPR Art. 35(1) requires a DPIA where processing is "likely to result in a high risk to the rights and freedoms of natural persons"; Art. 35(3) gives examples that include a systematic and extensive evaluation of personal aspects based on automated processing, including profiling, and processing on a large scale of special categories of data, as WP248 quotes them. [DOC S-xvc5ligo]
- The GDPR (Regulation (EU) 2016/679) entered into force on 2016-05-24 and applies since 2018-05-25. [DOC S-7ddlgwua]
- The WP29 Guidelines on DPIA (WP248 rev.01, adopted 2017-04-04, last revised 2017-10-04) set nine criteria;
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
  at the SQL layer) [DER S-xvc5ligo,S-rebms33k]; systematic monitoring of workstation state across an estate over time can
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
  emergency communication. [UNK: read from the Directive's EUR-Lex text (S1552) on 2026-09-26, not re-confirmed on 2026-10-23 because EUR-Lex answers this host with an empty bot-challenge page and the Commission's NIS2 page lists no Art. 21(2) measure; logged in `_gaps.md`]
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
- NIS2 (Directive (EU) 2022/2555) replaced the NIS1 Directive and came into force in January 2023; Member States had until 2024-10-17 to transpose it, and NIS1 was repealed from 2024-10-18. [DOC S-sxwkpb6d]
- Member States had to transpose NIS2 by 2024-10-17; on 2025-05-07 the Commission sent reasoned opinions to 19
  Member States, Poland among them, for failing to notify full transposition, giving them two months to respond
  before a possible referral to the Court of Justice. The Commission's Poland page still gives that reasoned
  opinion as the transposition status (read 2026-10-21). [DOC S-k2bxn62w, S-nzqme6xu]
- NIS2 essential/important entity status depends on sector (Annexes I/II of the Directive) and size thresholds
  (broadly, medium-or-larger enterprises in listed sectors, with some entities in scope regardless of size); the
  Directive does not decide a given operator's status. [UNK: read from the Directive's EUR-Lex text (S1552) on 2026-09-26, not re-confirmed on 2026-10-23 because EUR-Lex answers this host with an empty bot-challenge page; logged in `_gaps.md`]
- DORA (Regulation (EU) 2022/2554) entered into force on 2023-01-16 and applies from 2025-01-17 to more than 20 different types of financial entities, and ESMA lists an oversight framework for ICT third-party providers designated as critical by the ESAs; it is noted here only as a conditional check: it applies only if the operating organisation is itself a financial entity in DORA's scope. [DOC S-etw2ppgz]
- NIST AI 600-1 (the Generative AI profile) lists Data Privacy among the risks unique to or made worse by generative AI: leakage and unauthorized use, disclosure or de-anonymization of PII or other sensitive data. It notes that models may leak, generate or correctly infer sensitive information about individuals, including PII that was neither in the training data nor disclosed by the user, by combining information from separate sources. [DOC S1542]
- The EU AI Act (Regulation (EU) 2024/1689) entered into force 2024-08-01, with staggered application dates:
  prohibited practices and AI-literacy obligations from 2025-02-02; governance rules and obligations for
  general-purpose AI models from 2025-08-02; and (originally) most other obligations, including Annex III
  high-risk systems, from 2026-08-02. [DOC S-nnq2ftfq, S1557]
- The Commission proposed the "Digital Omnibus on AI" on 2025-11-19; its press release of 2026-05-07 welcomes the
  political agreement "reached today" between Parliament and Council, with high-risk rules for Annex III areas from
  2027-12-02 and for AI in products from 2028-08-02, a new ban on AI that generates non-consensual intimate content
  or CSAM, SME privileges extended to small mid-caps and stronger AI Office powers. [DOC S-tzbutlvs]
- A law-firm alert dates the provisional agreement 2026-05-06 and a Council confirmation 2026-05-13; the
  Commission release dates the agreement 2026-05-07, and the Council's own page could not be read (browser check).
  [COMMUNITY S1558]
- The AI Act's rules for high-risk AI systems in Annex III apply from 2027-12-02, and for high-risk AI embedded in regulated products covered by Annex I from 2028-08-02, following the Digital Omnibus on AI. [DOC S-nnq2ftfq, S1557]
- The Digital Omnibus on AI entered into force on 2026-07-27, before the original 2026-08-02 date for most AI Act rules. [DER S1557, S-nnq2ftfq: the entry into force on the Commission page against the 2026-08-02 date of the timeline]
- Regulation (EU) 2026/1744 of 2026-07-08, its publication in the Official Journal on 2026-07-24, the entry into force on the third day after publication, the Chapter III Sections 1-3 and Art. 6(1)/6(2) wording of the deferral and the consolidated AI Act version of 2026-07-27 that EUR-Lex lists were read from the EUR-Lex texts (S-qzdkyvqx, S1556) on 2026-09-26 and are not re-confirmed on 2026-10-23: EUR-Lex answers this host with an empty bot-challenge page and no readable official page states them. [UNK: logged in `_gaps.md`]
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
- Controller and processor for an internal shared service: EDPB Guidelines 07/2020 (v2.0 adopted 2021-07-07; current v2.1, 2022-09-20, minor corrections) say it is
  usually the organisation, not a department, that is the controller; a processor must be a **separate entity**,
  so a department cannot be a processor to another department of the same entity, and staff processing under
  the controller's direct authority are not processors, while another company in the same group can be one.
  [DOC S-zg4p62eo]
- So an internal NER/pseudonymisation endpoint run by one team for others in the same legal entity adds no
  processor relationship; one run by a separate group company, or an external AI provider, is a processor and
  needs an Art. 28 contract. [DER S-zg4p62eo: separate-entity test applied to a shared service; Art. 28 GDPR]

## Reference

| Instrument | Date | Status as of 2026-09-24 | Source |
|---|---|---|---|
| GDPR | in force 2016-05-24, applies since 2018-05-25 | in force | S-7ddlgwua |
| WP29 WP248 rev.01 | adopted 2017-04-04, revised 2017-10-04 | current guidance | S-xvc5ligo |
| NIS2 Directive | in force January 2023 | transposition deadline 2024-10-17; national transposition ongoing | S-sxwkpb6d |
| Poland KSC amendment | Dz.U. 2026 poz. 252 | in force 2026-04-03; registration per ministerial schedule; Chapter 3 obligations by 2027-04-03 | S1553 |
| DORA | in force 2023-01-16 | applies from 2025-01-17 (financial entities only) | S-etw2ppgz |
| EU AI Act | in force 2024-08-01 | staggered application; high-risk deferred to 2027-12-02 / 2028-08-02 by the Digital Omnibus on AI, in force 2026-07-27 | S-nnq2ftfq, S1557 |

## Examples
Device logs for `PL-LT-00123`, linked to `jan.kowalski`, illustrate the employee-identifier criterion; no real
hostnames or user names are used.
