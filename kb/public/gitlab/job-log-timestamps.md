---
topic: gitlab/job-log-timestamps
priority: P3
applies_to: "GitLab CI job logs and GitLab Runner feature flag FF_TIMESTAMPS; docs at gitlab-org/gitlab master @a128b3dc and gitlab-org/gitlab-runner main @49138a48 (VERSION 19.5.0)"
retrieved_utc: 2026-10-10
sources: [S-fn452qtu, S-5qytzl6u, S-crjqbibt, S-k3j6wjbx, S-yfgczc7d, S-4pm7parz]
status: complete
---

# GitLab CI job log timestamps and FF_TIMESTAMPS

## Summary
GitLab job logs carry a timestamp on every line by default: the runner prefixes each log line with a UTC time in
ISO 8601 form. The runner feature flag `FF_TIMESTAMPS` controls it; it defaults to `true`, so a job needs the flag only
to turn timestamps off (`false`) or to state them explicitly (`true`). The flag is a plain CI/CD variable, set in
`.gitlab-ci.yml`, in the runner's `environment` or under `[runners.feature_flags]` in the runner's `config.toml`. The
job logs page asks for GitLab Runner 18.7 or later. On the wire the runner writes a fixed header before each message:
`YYYY-mm-ddTHH:MM:SS.UUUUUUZ`, a space, a two-digit hex stream id, the stream type (`O` or `E`) and a line flag.

## Facts
- `FF_TIMESTAMPS` has default value `true`, is not marked deprecated and has no removal version; when it is disabled, timestamps are not added to the beginning of each log trace line. [DOC S-fn452qtu]
- The runner source names the flag in `helpers/featureflags/flags.go`: the constant `UseTimestamps` of package `featureflags` is the string `"FF_TIMESTAMPS"`, and its entry in the flag list has default `true`, `Deprecated: false` and the description the docs repeat; the build reads the flag by that constant (below). [CODE S-4pm7parz: helpers/featureflags/flags.go#L39, helpers/featureflags/flags.go#L338-L343]
- A runner feature flag is toggled through an environment variable of the same name: `"true"` or `1` activates it, `"false"` or `0` deactivates it. [DOC S-fn452qtu]
- In pipeline configuration a flag is set as a CI/CD variable under `variables:`, globally for every job or inside one job. [DOC S-fn452qtu]
- For every job a runner runs, a flag can be set in the `environment` array of the `[[runners]]` section of the runner configuration (for example `environment = ["FEATURE_FLAG_NAME=1"]`). [DOC S-fn452qtu]
- Under `[runners.feature_flags]` in the runner configuration a flag is set so that no job can override its value; some flags are usable only there. [DOC S-fn452qtu]
- By default, job logs include timestamps in ISO 8601 format for each line; the page recommends them for finding performance problems and bottlenecks and for measuring how long build steps take. [DOC S-5qytzl6u]
- The job logs page marks the timestamps feature for the Free, Premium and Ultimate tiers on GitLab.com, GitLab Self-Managed and GitLab Dedicated. [DOC S-5qytzl6u]
- Timestamps were introduced in GitLab 17.1 behind the feature flag `parse_ci_job_timestamps` (off by default); that flag was removed in 17.2, and the feature is generally available in GitLab 18.9. [DOC S-5qytzl6u]
- With timestamps on, the page says a job log uses approximately 10% more storage space. [DOC S-5qytzl6u]
- The documented way to control timestamps is the `FF_TIMESTAMPS` CI/CD variable: `false` disables them, `true` enables them explicitly; the prerequisite is GitLab Runner 18.7 or later. [DOC S-5qytzl6u]
- The job logs page's example is `variables:` with `FF_TIMESTAMPS: false` at the top of `.gitlab-ci.yml`. [DOC S-5qytzl6u]
- The runner passes the flag to its build logger as the `Timestamping` option, taken from the `UseTimestamps` feature flag of the build; the runner source defines that flag as the constant `UseTimestamps` = `"FF_TIMESTAMPS"`. [CODE S-k3j6wjbx: common/build.go#L1658; CODE S-4pm7parz: helpers/featureflags/flags.go#L39]
- The runner's log header is `<date> <stream id><stream type><append flag><message>`; the code's layout string is `YYYY-mm-ddTHH:MM:SS.123456Z ` (UTC, six fractional digits, `Z`, one trailing space). [CODE S-crjqbibt: common/buildlogger/internal/timestamper/timestamper.go#L26-L51]
- The precision is microseconds: the code divides the nanosecond value by 1000, although the source comment calls the date "RFC3339 Nano". [CODE S-crjqbibt: common/buildlogger/internal/timestamper/timestamper.go#L23-L24]
- The stream id is two lowercase hex digits; the stream type is `O` for stdout or `E` for stderr; the append flag is a space for a complete line or `+` for a line that continues the previous one. [CODE S-crjqbibt: common/buildlogger/internal/timestamper/timestamper.go#L9-L16]
- A new log line starts at each `\n`, and also on a write that holds `\r` without `\n` (progress bars); the next line after such a flush, or after the 8 KiB internal buffer overflows, gets the `+` flag. [CODE S-crjqbibt: common/buildlogger/internal/timestamper/timestamper.go#L21-L66]
- The runner's log writer chain adds the timestamper only when timestamping is on; with the flag off, the line-splitting header is not written for the job's own output. [CODE S-yfgczc7d: common/buildlogger/build_logger.go#L212-L216]
- A job that needs to turn timestamps off for one pipeline sets `FF_TIMESTAMPS: false` in `variables:`; a runner administrator who needs it fixed for all jobs sets `FF_TIMESTAMPS = false` under `[runners.feature_flags]`, which a job cannot override. [DER S-5qytzl6u, S-fn452qtu: variable form, and the `[runners.feature_flags]` override rule]
- A tool that parses a raw job trace should expect the header above on every line and strip the date, stream id, type and flag before matching job output; the format is from runner source (implementation, not a documented promise), so a parser should tolerate its absence when the flag is off. [DER S-crjqbibt, S-yfgczc7d, S-fn452qtu: header layout, and the off behaviour]

## Reference
| Item | Value | Source |
|---|---|---|
| Flag | `FF_TIMESTAMPS`, default `true` | S-fn452qtu |
| Disable | `false` or `0` | S-fn452qtu |
| Flag constant in the runner source | `featureflags.UseTimestamps` = `"FF_TIMESTAMPS"`, `helpers/featureflags/flags.go` | S-4pm7parz |
| Documented control | `FF_TIMESTAMPS` CI/CD variable, runner 18.7 or later | S-5qytzl6u |
| Feature GA | GitLab 18.9 (introduced 17.1, flag `parse_ci_job_timestamps` removed 17.2) | S-5qytzl6u |
| Storage cost | about 10% more log space | S-5qytzl6u |
| Date format | ISO 8601, UTC, microseconds, `Z` | S-5qytzl6u, S-crjqbibt |
| Header | `<date> <2 hex stream id><O or E><space or +><message>` | S-crjqbibt |
| Enforced for all jobs | `[runners.feature_flags]` | S-fn452qtu |

Related: `gitlab/variables.md` (CI/CD variables); `windows/gitlab-runner-windows.md` (a self-managed runner on Windows);
`arch/gitlab-ci-components.md` (the pipeline configuration the variable sits in).

## Examples
- SNIPPET: turn job log timestamps off for a whole pipeline; context: GitLab Runner 18.7 or later, any tier; checked: no [DOC S-5qytzl6u: FF_TIMESTAMPS variable example]
```yaml
variables:
  FF_TIMESTAMPS: false

job:
  script:
    - echo "no timestamps in this job's log"
```
- SNIPPET: set the flag for every job of one runner so that no job can override it; context: GitLab Runner config.toml; checked: syntax [DOC S-fn452qtu: `[runners.feature_flags]` section]
```toml
[[runners]]
  name = "example-runner"
  executor = "docker"
  [runners.feature_flags]
    FF_TIMESTAMPS = false
```
- SNIPPET: one line of a raw job trace as the runner writes it; context: runner source at the pinned commit, flag on; checked: no [CODE S-crjqbibt: timestamper.go#L26-L51]
```text
2026-10-08T09:15:30.123456Z 00O Running with gitlab-runner
```
