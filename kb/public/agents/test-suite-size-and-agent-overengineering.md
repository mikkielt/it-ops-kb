---
topic: agents/test-suite-size-and-agent-overengineering
priority: P3
applies_to: "keeping a test suite small and fast, and keeping a coding agent from over-engineering it: GitLab testing guide (master), Software Engineering at Google (2020), Google SRE book (2017), Bazel test encyclopedia, Microsoft Learn DevOps (2022), Anthropic prompting guidance for Claude Opus 4.5 to Opus 5 and Sonnet 5.5, Claude Code best practices (retrieved 2026-10-06)"
retrieved_utc: 2026-10-06
sources: [S-zec4acor, S-pf2bzwco, S-xpnhjuy4, S-topmk5kh, S-3dlofilm, S-wxn7kar4, S-claarsij, S-flv3lmzn, S-3jc54vsg, S-xxsfmdk5, S-krlfjqxg, S-o3v6ozch]
status: partial
---

# What keeps a test suite small, and a coding agent from over-engineering it

## Summary
Tests are cheap to add and costly to keep: every one is run, read and repaired for as long as it exists. The engineering guides of GitLab, Google and Microsoft answer with a shape (most tests small and low-level, few end to end), with numeric budgets per test, and with deleting tests that do not earn their cost. For an AI coding agent, Anthropic's prompting guidance says its models add tests, files and abstractions nobody asked for unless told not to, and gives the wording that stops it. None of these sources says monitoring can take the place of regression tests; they treat tests before release and checks in production as two halves.

## Facts

### Why suites grow, and what a test costs
- GitLab's testing guide warns that "It's very easy to add tests, but a lot harder to remove or improve tests", and asks contributors not to introduce too many slow and duplicated tests. [DOC S-zec4acor]
- GitLab counts among a test's costs the time to run it every time the suite runs and the time to fix it when it breaks although the code under test is right, besides the time to write it. [DOC S-zec4acor]
- GitLab: when unit and integration tests give confidence in the low-level components, system tests should not repeat their thorough testing. [DOC S-zec4acor]
- GitLab: a higher-level spec stubs an expensive external operation that a unit test already verifies; its example is a spec that triggered a real Go compilation and added about 3 minutes to each run. [DOC S-pf2bzwco]
- GitLab: a slow shared example is paid once per file that includes it, so one that takes 30 seconds and is included in 10 spec files costs 300 seconds of CI time. [DOC S-pf2bzwco]
- Software Engineering at Google: "The slower a test suite, the less frequently it will be run, and the less benefit it provides." [DOC S-xpnhjuy4]
- Software Engineering at Google: parallel runs and faster hardware hide slow tests only for a while, since such tricks "are eventually swamped by a large number of individually slow test cases"; its remedy is to set performance goals and refactor slow or marginal tests. [DOC S-xpnhjuy4]

### The shape: few large tests
- GitLab: "Most of our tests should be at the unit level, with fewer tests as we move up each layer"; end-to-end tests are the most expensive to run and maintain and should be the smallest share. [DOC S-zec4acor]
- Software Engineering at Google gives its mix as about 80% narrow unit tests, 15% medium-scoped integration tests and 5% end-to-end tests. [DOC S-xpnhjuy4]
- A 2015 post on the Google Testing Blog gives a 70/20/10 split of unit, integration and end-to-end tests, and says a tenth of a second is slow for a unit test. [DOC S-topmk5kh]
- Software Engineering at Google defines a small test by what it may not do: it may not access the network or the disk. [DOC S-xpnhjuy4]
- Microsoft's shift-left guidance states the same preference as a principle: use lighter unit tests wherever they can produce the same results as heavier functional tests. [DOC S-wxn7kar4]

### Budgets a tool or a team enforces
- Bazel gives every test a size, and a timeout that follows from it unless one is set: 60 seconds for a small test, 300 for medium, 900 for large and 3600 for enormous; the limit is for a whole test target to run to completion, not for each test method. [DOC S-3dlofilm]
- Bazel's guidance is to set each timeout as tight as it can be without causing flakiness. [DOC S-3dlofilm]
- Microsoft's test taxonomy sets time budgets per level: an L0 unit test averages under 60 milliseconds per assembly, an L1 test under 400 milliseconds, and no L1 test may exceed 2 seconds. [DOC S-wxn7kar4]
- Microsoft's account of moving one product's tests to that taxonomy: new unit tests replaced some of the legacy end-to-end tests, "but many were simply deleted, based on team analysis of their usefulness." [DOC S-wxn7kar4]
- Google's SRE book ties the amount of testing to the system's reliability requirements: a life-critical or revenue-critical system needs far more than a non-production script with a short shelf life. [DOC S-flv3lmzn]
- Google's SRE book: "Instead of repeating the ambiguous refrain \"We need more tests,\" set explicit goals and deadlines." [DOC S-flv3lmzn]
- Google's SRE book: with a build system that knows dependencies, tests run only for changed code instead of at every submit, which makes them cheaper and faster. [DOC S-flv3lmzn]

### What tests before release do not show
- Microsoft's shift-right guidance: "Regardless of pre-production test coverage, it's necessary to test compatibility in production." [DOC S-claarsij]
- Whether a defect that logs or monitoring would show needs a regression test as well is not answered by any source read here: they describe checks in production as an addition to tests before release, not as a replacement for them. [UNK]

### What a coding agent adds unasked
- Anthropic's prompting best practices say Claude Opus 4.5 and Opus 4.6 "have a tendency to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested." [DOC S-3jc54vsg]
- The sample prompt Anthropic gives against it sets the bar: "The right amount of complexity is the minimum needed for the current task." [DOC S-3jc54vsg]
- The same page says Claude "can sometimes focus too heavily on making tests pass at the expense of more general solutions", and its sample prompt tells the model: "Tests are there to verify correctness, not to define the solution." [DOC S-3jc54vsg]
- Anthropic's guide for Claude Sonnet 5.5 says the model "tends to add tests, documentation, and small supporting files" that fit the repository's conventions even when not asked, more so at higher effort. [DOC S-xxsfmdk5]
- That guide's line for a system prompt that stops it: "Don't add features, tests, files, docs or refactors that weren't asked for." [DOC S-xxsfmdk5]
- Anthropic's guide for Claude Opus 5 says the model can expand the scope of a task by adding steps that were not requested, and advises stating the scope explicitly for a narrow task. [DOC S-krlfjqxg]
- Claude Code's best practices ask for a check the agent can run itself: without one, "looks done" is the only signal and the person becomes the verification loop. [DOC S-o3v6ozch]
- Claude Code's best practices on the instruction file: a bloated `CLAUDE.md` makes Claude ignore instructions, and the test for each line is "Would removing this cause Claude to make mistakes?" [DOC S-o3v6ozch]

### How it fits
- A number a tool enforces holds where advice does not: Bazel limits the time a test target may run and Microsoft's taxonomy caps a test's time, while GitLab's guide can only ask contributors to take care, because adding a test is easy and removing one is hard. A suite therefore stays small when its runner refuses growth (a cap on tests and on run time) and an addition costs a removal. [DER S-3dlofilm, S-wxn7kar4, S-zec4acor: enforced limits against the add-is-easy, remove-is-hard asymmetry]
- For a coding agent the rule has to be written down, since the documented default of current Claude models is to add tests and supporting files unasked: name the kinds of test that are allowed, forbid the rest in one line, and keep that instruction short enough to survive the pruning test. A mechanical ceiling then catches what the instruction misses. [DER S-xxsfmdk5, S-3jc54vsg, S-o3v6ozch: the models' stated tendency, the stated counter-prompt and the instruction-file advice]
- The agent still needs a check it can run, and that check need not be a large suite: a few tests of the main paths give the verification signal, while tests written to make an agent's own change look done are the failure Anthropic describes as focusing on passing tests. [DER S-o3v6ozch, S-3jc54vsg: a runnable check as the signal, tests as verification and not the goal]
- The guides agree on fewer tests at the top, not on a count: the 80/15/5 and 70/20/10 mixes are ratios for large products, and the SRE book makes the amount depend on what a failure costs. A small internal tool sits at the low end of that scale. [DER S-xpnhjuy4, S-topmk5kh, S-flv3lmzn: ratios versus requirements-driven amount]

## Reference
| Limit | Value | Enforced by | Source |
|---|---|---|---|
| Bazel timeout of a small / medium / large / enormous test | 60 / 300 / 900 / 3600 s | Bazel (time limit per test target) | S-3dlofilm |
| Microsoft L0 unit test, average per assembly | under 60 ms | team rule | S-wxn7kar4 |
| Microsoft L1 unit test, average per assembly; any single L1 test | under 400 ms; at most 2 s | team rule | S-wxn7kar4 |
| Google Testing Blog: a slow unit test | a tenth of a second | guidance | S-topmk5kh |
| Mix of unit / integration / end-to-end tests | 80 / 15 / 5 (book), 70 / 20 / 10 (blog) | guidance | S-xpnhjuy4, S-topmk5kh |

Related topics: `agents/agent-planning-and-done.md` (definition of done, end-to-end checks before a task counts as done), `agents/agent-evaluation.md` (regression suites for agents), `gitlab/git-test-repositories.md` (cheap throwaway repositories in tests).

## Examples
- SNIPPET: three lines for an agent's instruction file that bound what it may add to a test suite; context: a repository whose test runner enforces a cap, any current Claude model; checked: no [DER S-xxsfmdk5, S-o3v6ozch: the second line is Anthropic's own wording, the others apply the pruning test to this kb's rule]
```text
A test is written only for a command's main path, a gate's planted failure, a machine-read format, or a leak guard.
Don't add features, tests, files, docs or refactors that weren't asked for.
The suite has a ceiling the runner enforces: a new test replaces one.
```
