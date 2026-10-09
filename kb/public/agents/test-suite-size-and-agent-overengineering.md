---
topic: agents/test-suite-size-and-agent-overengineering
priority: P3
applies_to: "keeping a test suite small and fast, deciding which tests to delete, running a slow full suite less often than per merge, and keeping a coding agent from over-engineering it: GitLab testing guide, pipelines page and quarantine handbook (master), Software Engineering at Google (2020), Google SRE book (2017), Bazel test encyclopedia, Microsoft Learn DevOps (2022), Anthropic prompting guidance for Claude Opus 4.5 to Opus 5 and Sonnet 5.5, Claude Code best practices (retrieved 2026-10-10)"
retrieved_utc: 2026-10-10
sources: [S-zec4acor, S-pf2bzwco, S-xpnhjuy4, S-topmk5kh, S-3dlofilm, S-wxn7kar4, S-claarsij, S-flv3lmzn, S-3jc54vsg, S-xxsfmdk5, S-krlfjqxg, S-o3v6ozch, S-bmz46flb, S-ocdzembr, S-nxhqpwaf, S-f65kifg4, S-jg2qnt5d]
status: partial
---

# What keeps a test suite small, and a coding agent from over-engineering it

## Summary
Tests are cheap to add and costly to keep: every one is run, read and repaired for as long as it exists. The engineering guides of GitLab, Google and Microsoft answer with a shape (most tests small and low-level, few end to end), with numeric budgets per test, with deleting tests that do not earn their cost (GitLab sets a deadline after which a quarantined test is deleted), and with running only a fast, reliable subset per merge while the slow full suite runs after the merge or on a schedule. For an AI coding agent, Anthropic's prompting guidance says its models add tests, files and abstractions nobody asked for unless told not to, and gives the wording that stops it. None of these sources says monitoring can take the place of regression tests; they treat tests before release and checks in production as two halves.

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

### Which tests to delete
- GitLab's quarantine handbook treats a quarantine as temporary: "tests must be fixed, removed, or moved to a lower test level." [DOC S-jg2qnt5d]
- For a flaky or broken test, GitLab's handbook gives the owner four choices: fix it at once if the cause is clear, delete it "if it's low-value or redundant", convert it to a lower level if it can be tested more reliably there, or quarantine it when the fix will take longer than the response time. [DOC S-jg2qnt5d]
- GitLab's quarantine marks a test to be skipped in CI while it stays in the codebase; the quarantine types include `:stale`, a test outdated by feature changes, and `:broken`, a test failing through test code or framework changes. [DOC S-f65kifg4]
- GitLab's handbook gives a quarantine a deadline: fast quarantine 3 days at most, long-term quarantine 3 months at most, a deletion merge request a week before the end, and the test removed from the codebase after 3 months. [DOC S-jg2qnt5d]
- The same handbook says the deletion merge request "requires manual approval by the owning team", described as a semi-automatic process, not a fully automatic one, although its lifecycle table says the test is automatically deleted after 3 months. [DOC S-jg2qnt5d]
- GitLab's handbook: a test quarantined 3 or more times is a candidate for permanent removal, and its owning team considers alternative testing approaches. [DOC S-jg2qnt5d]
- GitLab's handbook allows a test back out of quarantine only when it passed more than 100 local runs with the root cause fixed, or when it was removed or replaced by better coverage. [DOC S-jg2qnt5d]
- Software Engineering at Google on a test nobody understands: removing it has no effect but a possible hole in coverage, and in the worst case such obscure tests "just end up getting deleted"; that deletion "indicates that the test has been providing zero value" for perhaps its whole life. [DOC S-ocdzembr]

### Running the full suite less often than per merge
- Software Engineering at Google asks why not run every test on presubmit and answers "it's too expensive"; removing the demand that presubmit be exhaustive lets the tests be restricted to certain scopes or selected by a model that predicts their likelihood of detecting a failure. [DOC S-bmz46flb]
- Its rule for presubmit: "only fast, reliable ones"; some loss of coverage is accepted, so issues that slip by must be caught on post-submit, with some rollbacks accepted, and on post-submit longer times and some instability are acceptable. [DOC S-bmz46flb]
- Google limits presubmit tests typically to those of the project where the change is made, runs small tests (unit tests) on presubmit in most teams, and keeps unreliable tests off it. [DOC S-bmz46flb]
- Google's test platform asks each team for a fast subset of tests, often the project's unit tests, as the presubmit; the book says a change that passes it has "a very high likelihood (95%+)" of passing the rest of the tests. [DOC S-bmz46flb]
- After submission Google runs "all potentially affected tests, including larger and slower tests" asynchronously; a team's Build Cop finds the offending change and prefers a rollback to a fix going forward, and the average wait to submit is around 11 minutes. [DOC S-bmz46flb]
- Google's Takeout team moved end-to-end tests that could not run on presubmit from "after nightly deploy" to a post-submit CI that runs every two hours, which cut the set of changes to search for a culprit 12 times. [DOC S-bmz46flb]
- Software Engineering at Google: some teams remove flaky tests from presubmit temporarily while the flakiness is investigated; it also says a CI should keep quick, reliable tests on presubmit and slower, less deterministic ones on post-submit. [DOC S-bmz46flb]
- GitLab's own project runs three pipeline tiers on a merge request by approval state: the lower the tier, the faster the pipeline, and the higher, "the more confidence the pipeline should give us by running more tests". [DOC S-nxhqpwaf]
- GitLab: before a merge request is approved its pipeline runs a predictive set of RSpec and Jest tests "that are likely to fail for the merge request changes"; once approved the pipeline holds the full suites, "to ensure that all tests have been run before a merge request is merged". [DOC S-nxhqpwaf]
- GitLab selects those tests from the changed files: a `detect-tests` job in the prepare stage writes the test files to run, using dynamic mappings and a static mapping file for cases that cannot be mapped dynamically. [DOC S-nxhqpwaf]
- GitLab runs the full RSpec suite regardless of the prediction when a label asks for it, when the merge request is approved with backend changes, or is created by automation or in a security mirror, or changes a CI configuration file. [DOC S-nxhqpwaf]
- GitLab adds an `rspec fail-fast` job in parallel for the tests directly related to the change; it is a no-op over 10 related test files, so that it does not run as long as the ordinary jobs. [DOC S-nxhqpwaf]
- GitLab's merge train runs no tests: its `pre-merge-checks` job requires the latest pipeline to be a merged results pipeline, a tier-3 (full) pipeline and at most 16 hours old (72 for stable branches). [DOC S-nxhqpwaf]
- GitLab runs the suite beyond merge requests on `master` commits and on scheduled `maintenance` (every even-numbered hour), `nightly` and `weekly` pipelines; nightly runs add other PostgreSQL versions, and its guideline is that one back-compatible and one forward-compatible version of a dependency "should be running in nightly scheduled pipelines". [DOC S-nxhqpwaf]
- GitLab: tests with a single database run in nightly scheduled pipelines and in merge requests that touch database-related files. [DOC S-nxhqpwaf]
- GitLab's nightly pipeline has a job ceiling: the page notes 1946 out of 2000 jobs per pipeline used, and that new job families could make it fail. [DOC S-nxhqpwaf]
- How often a full suite should run when it is not run per merge (every few hours, nightly, weekly), and how a nightly failure is traced to one merge, is not stated as a rule by any source read here: Google gives its own cadences (a two-hour post-submit CI for one team), GitLab its own schedule (every second hour, nightly, weekly). [UNK]

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

- What keeps a test suite small is three things stated by the sources, each with its limit: a size limit and a time budget per test (Bazel's timeouts, Microsoft's per-level times), a test to delete when it is flaky past a deadline, redundant or unexplained (GitLab's quarantine ends in deletion after 3 months), and a runner that refuses growth. No source read states a budget for the number of tests in a suite; a count ceiling is a design choice of the team that sets it. [DER S-3dlofilm, S-wxn7kar4, S-jg2qnt5d: per-test limits and deadline deletion are stated; a cap on test count is not]
- A test is a candidate for deletion by what it costs and what it still shows: GitLab asks of a failing test whether it is low-value or redundant, or whether a lower level tests it more reliably, and Google treats a test nobody can explain as one that may never have provided value. A suite held under a ceiling can use those questions as its rule: each test that keeps failing or cannot be explained is fixed, moved down a level or deleted within a stated time, never left skipped. [DER S-jg2qnt5d, S-ocdzembr: the delete, convert and fix choices, applied to a ceiling]
- A regression that only a slow full suite finds is caught by four layers kept together: a fast subset that gates the merge (Google's presubmit, GitLab's predictive tier), a selection that adds the tests the change can affect (GitLab's `detect-tests`, Google's affected-test calculation), a full run after the merge that is allowed to be slow and flaky (post-submit, `master` commits, scheduled `maintenance` runs) with a named person who rolls back the culprit, and a periodic broader run (nightly or weekly) for combinations too many for each merge. The sources show each layer at their scale; none states a cadence for a small repository, so the interval is the operator's choice. [DER S-bmz46flb, S-nxhqpwaf: presubmit, selection, post-submit and scheduled runs as the same pattern in two organisations]
- The price of the pattern is stated by Google and GitLab alike: a failure found after the merge costs a rollback, and a merge train that runs no tests must still check that a full pipeline of recent age exists. A repository that skips the full suite per merge therefore needs the post-merge run to name its culprit (the commit range since the last green run) before it can be trusted. [DER S-bmz46flb, S-nxhqpwaf: rollbacks accepted, the 16-hour freshness check]

## Reference
| Limit | Value | Enforced by | Source |
|---|---|---|---|
| Bazel timeout of a small / medium / large / enormous test | 60 / 300 / 900 / 3600 s | Bazel (time limit per test target) | S-3dlofilm |
| Microsoft L0 unit test, average per assembly | under 60 ms | team rule | S-wxn7kar4 |
| Microsoft L1 unit test, average per assembly; any single L1 test | under 400 ms; at most 2 s | team rule | S-wxn7kar4 |
| Google Testing Blog: a slow unit test | a tenth of a second | guidance | S-topmk5kh |
| Mix of unit / integration / end-to-end tests | 80 / 15 / 5 (book), 70 / 20 / 10 (blog) | guidance | S-xpnhjuy4, S-topmk5kh |
| GitLab fast quarantine / long-term quarantine of a test | 3 days / 3 months at most, then deletion | process (a deletion merge request needs the owning team's approval) | S-jg2qnt5d |
| GitLab test quarantined this many times | 3 or more: candidate for permanent removal | process | S-jg2qnt5d |
| GitLab `rspec fail-fast` job | no-op over 10 related test files | CI variable `RSPEC_FAIL_FAST_TEST_FILE_COUNT_THRESHOLD` | S-nxhqpwaf |
| GitLab merge train: age of the full pipeline | at most 16 hours (72 for stable branches) | `pre-merge-checks` job | S-nxhqpwaf |

Related topics: `agents/agent-planning-and-done.md` (definition of done, end-to-end checks before a task counts as done), `agents/agent-evaluation.md` (regression suites for agents), `gitlab/git-test-repositories.md` (cheap throwaway repositories in tests).

## Examples
- SNIPPET: three lines for an agent's instruction file that bound what it may add to a test suite; context: a repository whose test runner enforces a cap, any current Claude model; checked: no [DER S-xxsfmdk5, S-o3v6ozch: the second line is Anthropic's own wording, the others apply the pruning test to this kb's rule]
```text
A test is written only for a command's main path, a gate's planted failure, a machine-read format, or a leak guard.
Don't add features, tests, files, docs or refactors that weren't asked for.
The suite has a ceiling the runner enforces: a new test replaces one.
```
