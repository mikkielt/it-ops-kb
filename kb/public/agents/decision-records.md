---
topic: agents/decision-records
priority: P3
applies_to: "architecture decision records (ADRs) and decision logs as the vendors and the ADR community describe them: Nygard 2011, MADR 4.0.0, AWS Prescriptive Guidance, Azure Well-Architected Framework, Google Cloud Architecture Center, the UK GDS ADR framework, adr-tools README at commit b3279ba (retrieved 2026-10-01)"
retrieved_utc: 2026-10-01
sources: [S-neg7qqfq, S-2u3gjgpw, S-cs7vd6kx, S-jqks66nz, S-ebr4i7g5, S-gb6pcwtm, S-efm54uef, S-l52pzhgp, S-6ek6kqhq, S-lrsbmzgx]
status: partial
---

# Decision records: ADR practice, status lifecycle and who decides

## Summary
An architecture decision record (ADR) is a short document that records one significant decision with its context, the options considered and its consequences; the collection of them is the decision log. Michael Nygard's 2011 post popularised the format (title, context, decision, status, consequences), and every later source reads the same core: a record is numbered, kept in the open beside the work, and not rewritten once accepted. A change of mind is a new record that supersedes the old one, and each keeps its link to the other. The status vocabulary is small and not identical across sources (`proposed`, `accepted`, `superseded` everywhere; `rejected` and `deprecated` in some). On who decides, the sources differ in kind: AWS has the team accept an ADR its owner proposed, MADR lists decision-makers, consulted and informed people in the record itself, and the UK government framework assigns the decision to a body by the decision's scope. No source in this kb defines a status for a record whose context has changed but which nothing has replaced yet; they all handle that through review. The status table is in `decision-records.csv`.

## Facts
- Nygard's 2011 post proposes keeping a collection of records for "architecturally significant" decisions: those that affect structure, non-functional characteristics, dependencies, interfaces or construction techniques. [DOC S-neg7qqfq]
- In Nygard's format one record describes one decision and the forces behind it, as a short text file in the project repository (his example path is `doc/arch/adr-NNN.md`) in a light markup language such as Markdown; records are numbered sequentially and monotonically, and a number is never reused. [DOC S-neg7qqfq]
- Nygard's record has five parts: a Title (a short noun phrase), a Context (the forces at play, in value-neutral language), a Decision (full sentences in active voice, "We will ..."), a Status, and the Consequences, which must list all of them, positive, negative and neutral; the whole record should be one or two pages. [DOC S-neg7qqfq]
- Nygard's Status is "proposed" while the stakeholders have not agreed and "accepted" once they have; if a later ADR changes or reverses it, the old one may be marked "deprecated" or "superseded" with a reference to its replacement. [DOC S-neg7qqfq]
- A reversed decision is kept, not deleted: Nygard marks it superseded because it is still relevant to know that it was the decision, even though it no longer is. [DOC S-neg7qqfq]
- Nygard's reason for the practice: a newcomer who does not know the rationale can only accept a decision blindly or change it blindly, and a record makes the time to change an old decision visible from changes in the project's context. [DOC S-neg7qqfq]
- The adr GitHub organization defines an architectural decision as a justified design choice that addresses an architecturally significant requirement, an ADR as the record of one such decision and its rationale, and the collection of ADRs of a project as its decision log; it adds that ADR use can extend to design and other decisions ("any decision record"). [DOC S-2u3gjgpw]
- The MADR 4.0.0 template carries optional front matter: `status`, `date` (the day the decision was last updated), `decision-makers` (everyone involved in the decision), `consulted` (people whose opinions are sought, with two-way communication) and `informed` (people kept up to date, with one-way communication). [DOC S-cs7vd6kx]
- The MADR `status` placeholder lists `proposed`, `rejected`, `accepted`, `deprecated`, an open ellipsis and `superseded by ADR-0123`, so the superseding record's id is part of the status value and the vocabulary is open-ended. [DOC S-cs7vd6kx]
- MADR's body sections are Context and Problem Statement, an optional Decision Drivers, Considered Options, Decision Outcome ("Chosen option ... because ..."), optional Consequences (good and bad), an optional Confirmation, the Pros and Cons of the Options and a More Information section. [DOC S-cs7vd6kx]
- MADR's Confirmation section says how compliance with the decision can be checked (a design or code review, or a test with a library such as ArchUnit); its More Information section may state when and how the decision should be revisited. [DOC S-cs7vd6kx]
- AWS Prescriptive Guidance defines an ADR as a document of a choice about a significant aspect of the planned software architecture, with its context and consequences; ADRs have states and so follow a lifecycle, and the collection is the decision log. [DOC S-jqks66nz]
- AWS: once the team accepts an ADR it is immutable; if new insights call for a different decision, the team proposes a new ADR, and on acceptance the new one supersedes the old. [DOC S-jqks66nz]
- AWS names what deserves an ADR: every architecturally significant decision, covering structure, non-functional requirements, dependencies, interfaces and construction techniques (attributed to Richards and Ford 2020). [DOC S-jqks66nz]
- AWS wants at least the context, the decision and the consequences in each ADR, and stresses the reason for the decision over how it was implemented, because understanding the why helps others adopt it and stops architects who were not part of it from overruling it later. [DOC S-jqks66nz]
- AWS ownership: every team member can create an ADR, the team should define ownership, the author owns it and keeps it current, and when its content changes before acceptance the owner approves the change. [DOC S-jqks66nz]
- AWS process: the owner presents the ADR in the Proposed state; the team, owner included, reviews it and decides to accept, to rework it (it stays Proposed, with assigned actions) or to reject it (the owner records the reason and sets Rejected). On approval the owner adds a timestamp, a version and the list of stakeholders and sets Accepted. [DOC S-jqks66nz]
- AWS treats ADRs as immutable after acceptance or rejection: a change needs a new ADR with its own review and approval, and when that is approved the owner sets the old ADR to Superseded. [DOC S-jqks66nz]
- AWS expects code review to apply the log: a reviewer who finds a change that violates an ADR asks the author to update the change and shares a link to the ADR. [DOC S-jqks66nz]
- AWS best practices: each ADR has a change history with an owner per change, the superseded ADR stays in the log, and ADRs are stored where every project member can reach them, in a Git repository (easy to version) or on a wiki (easy to reach). [DOC S-ebr4i7g5]
- AWS best practices also advise letting each team member own ADRs so that decisions are adopted faster than ones imposed from above, regular review meetings (a greenfield project's ADRs stabilise in two or three sprints), and handling legacy code that does not match an ADR by gradual updates or explicit technical-debt tasks. [DOC S-ebr4i7g5]
- The AWS example ADR has the sections Title, Status (Accepted), Date, Context, Decision, Consequences, Compliance and Notes, where Notes holds the author, a version and a changelog. [DOC S-gb6pcwtm]
- The Azure Well-Architected Framework says an ADR records key decisions including the alternatives ruled out, only for choices that affect the system's structure or key quality attributes or are hard to reverse, and that each entry carries context, justification and implications. [DOC S-efm54uef]
- Azure: the ADR is an append-only log. Accepted records are not edited; a changed decision gets a new record that supersedes the original, and the two are linked, which keeps the history of why the direction shifted. [DOC S-efm54uef]
- Azure's record anatomy is a problem statement with context, the options considered, the decision outcome with its trade-offs and a confidence level, and a status such as Proposed, Accepted or Superseded; a recorded low confidence helps a later reconsideration. [DOC S-efm54uef]
- Azure advises starting the ADR at the start of a workload and keeping it for its lifespan, building it retroactively for a brownfield workload from known past decisions where data exists, and storing the log openly with the workload documentation; a decision never recorded tends to be forgotten, causing repeated debates or changes that contradict the original intent. [DOC S-efm54uef]
- Azure: one decision that unfolds in phases (short, mid, long term) is logged as separate records; every record states its context and rationale, since without them stakeholders cannot judge whether it still applies; and a record stays short and stands alone, with a link to supplemental design material instead of being a design guide. [DOC S-efm54uef]
- The Google Cloud Architecture Center describes an ADR as the key options, the main requirements that drive a decision and the decision itself, often kept in a Markdown file near the code it concerns; it advises writing one when no existing basis for a decision exists, when a solution is not documented where the team can reach it, or when two or more engineering options exist. [DOC S-l52pzhgp]
- Google's example outline has the authors and team, the context and problem, the functional and non-functional requirements, the critical user journeys affected, the key options, and the decision with the reasons; a timestamp per decision is optional. [DOC S-l52pzhgp]
- Google lets the team revisit an ADR as it learns more: when it adjusts a decision, it should include the previous decision and why it changed, so the record shows how the architecture evolved; it also allows a wiki or shared document in place of source control, or a mirror of key decisions to one. [DOC S-l52pzhgp]
- The UK government ADR framework's template has the fields title, date, status, context, decision, consequences, stakeholders consulted and links to supporting documents. [DOC S-6ek6kqhq]
- The UK framework aims to let teams decide for themselves without unnecessary approval overhead and gives rules for escalating decisions with wider strategic or technical impact; it recommends adoption at every level and mandates it only for cross-government and cross-public-sector decisions. [DOC S-6ek6kqhq]
- The UK framework ties the decision-maker to the decision's scope: the head or lead of a team for a decision local to one team; a programme architecture forum for one affecting several teams or shared services of a programme; a departmental architecture board for one affecting several programmes or setting a precedent; the Technical Design Council for one affecting several departments. Each level has its own escalation criteria. [DOC S-6ek6kqhq]
- The UK framework's steps are: fix the scope and decision level, engage the stakeholders, record the decision in an agreed template, submit it to the appropriate decision-making body for review and approval, share the approved record, and review and update it regularly as its context or consequences change. [DOC S-6ek6kqhq]
- The adr-tools command line manages ADRs as numbered Markdown files; `adr new -s 9 <title>` creates a record flagged as superseding ADR 9 and changes the status of ADR 9 to say it is superseded by the new one, so the supersede link is kept in both records. [DOC S-lrsbmzgx]
- Across the sources the status vocabulary is: Nygard `proposed`, `accepted`, `deprecated`, `superseded`; AWS Proposed, Accepted, Rejected, Superseded; Azure Proposed, Accepted, Superseded (given as examples); MADR `proposed`, `rejected`, `accepted`, `deprecated`, `superseded by ADR-NNNN` and an open list; the UK framework has a `status` field and lists no values; adr-tools changes the old record's status to say it is superseded. `proposed`, `accepted` and `superseded` are common to all that list values. [DER S-neg7qqfq, S-jqks66nz, S-efm54uef, S-cs7vd6kx, S-6ek6kqhq, S-lrsbmzgx: the status lists compared; `decision-records.csv`]
- In the pages read, no source defines a status for a record whose context has changed but which nothing has replaced; each leaves that to review: Nygard says the time to change a decision shows in the context, Azure records a confidence level for later reconsideration, MADR's More Information may set a revisit condition, and the UK framework asks for regular review. Nygard's `deprecated` is the nearest listed status. [DER S-neg7qqfq, S-efm54uef, S-cs7vd6kx, S-6ek6kqhq: absence of such a status in these pages, read 2026-10-01]
- Who decides, by source: AWS has the whole team, the owner included, decide on a Proposed ADR and the owner record the outcome; MADR lists decision-makers, consulted and informed people as separate fields of one record; the UK framework picks the deciding body by scope. [DER S-jqks66nz, S-cs7vd6kx, S-6ek6kqhq: the three descriptions of who decides compared]
- Reading the sources together for a store of decisions kept as data: the id is never reused (Nygard); a change is a new record that links to the old one and sets the old one's status (AWS, Azure, adr-tools); a record carries who decided, who was consulted and who was informed (MADR) and a date and a version (AWS, UK); the context and rationale are stored with the decision (all). This is a design reading, not a vendor rule. [DER S-neg7qqfq, S-jqks66nz, S-efm54uef, S-cs7vd6kx, S-lrsbmzgx: the practices listed there, combined]

## Reference
| Source | Statuses it names | Who decides |
|---|---|---|
| Nygard 2011 (S-neg7qqfq) | proposed, accepted, deprecated, superseded | project stakeholders agree |
| AWS (S-jqks66nz) | Proposed, Accepted, Rejected, Superseded | the team reviews; the owner records the outcome |
| Azure WAF (S-efm54uef) | Proposed, Accepted, Superseded | not stated |
| MADR 4.0.0 (S-cs7vd6kx) | proposed, rejected, accepted, deprecated, superseded by ADR-NNNN | `decision-makers`, `consulted`, `informed` fields |
| UK GDS (S-6ek6kqhq) | a `status` field, no values listed | decision body by scope, four levels |
| Google Cloud (S-l52pzhgp) | none named | not stated (the outline names the authors and the team) |

The per-element table (statuses, who decides, fields) is `decision-records.csv`. Related articles: `agents/agent-planning-and-done.md` (definition of done and a goal's end state), `agents/agent-rbac.md` (who may do what), `agents/mcp-server-lifecycle.md` (deprecation of an interface, a different lifecycle).

## Examples
- SNIPPET: the front matter of a MADR 4.0.0 record, filled with placeholders; context: MADR 4.0.0 template, all keys optional; checked: no [DER S-cs7vd6kx: keys and their meanings from the template]
```yaml
status: "accepted"
date: 2026-10-01
decision-makers: jan.kowalski
consulted: PL-SRV-0042 owners
informed: service desk
```
