---
topic: arch/twelve-factor-readiness
priority: P1
applies_to: [twelve-factor, kubernetes, python]
retrieved_utc: 2026-09-24
sources: [S1718, S1719, S1720, S1721, S1722, S1723, S1724, S1725, S1726, S1727, S1728, S1729]
status: complete
---

# Twelve-factor readiness for a workstation/site/CI/isolated instance

## Summary
A tool with distinct instance kinds (workstation, scheduled-job host, CI, isolated dev) can get several
twelve-factor practices cheaply (env config, stdout logs, stateless processes, disposability) by
mapping them directly onto those kinds. Kubernetes-specific practices (CronJob semantics,
Secrets-as-files) are not directly applicable when there is no always-on service and no cluster, but
the same reasoning (files over env vars for secrets, explicit deadlines on scheduled work) transfers
to a Windows Task Scheduler host standing in for a CronJob. `tzdata` on Windows is a real, documented
gap: `zoneinfo` needs the `tzdata` PyPI package there.

## Facts
- Factor III (Config): strict separation of config from code, config stored in environment variables,
  varying between deploys without a code change. [DOC S1718]
- Factor IV (Backing services): every backing service (SQL Server, AdminService, Graph) is an
  attached resource, swappable via config with no code change. [DOC S1719]
- Factor VI (Processes): the app executes as stateless processes; any persisted state goes to a
  backing service (SQL Server here). [DOC S1722]
- Factor IX (Disposability): favour fast startup and graceful shutdown; processes should be
  disposable, robust against sudden death. [DOC S1721]
- Factor X (Dev/prod parity): keep development, staging and production as similar as possible. [DOC S1723]
- Factor XI (Logs): a process never manages its own log files; it writes its event stream,
  unbuffered, to stdout, and log routing/storage is an external concern. [DOC S1720]
- Factor XII (Admin processes): one-off admin/management tasks (e.g. DB migrations, ad hoc scripts)
  run in an identical environment against the same codebase/config as the long-running process. [DOC S1724]
- Kubernetes official Secrets guidance describes both env-var and volume-mount injection as valid,
  with the same "protect it after you read it" obligation on the application either way — it does not
  officially declare env vars unsafe, but does flag that when only one container in a multi-container
  Pod needs a Secret, the *other* containers must not receive it via either mechanism. [DOC S1725][DOC S1729]
- CronJob `.spec.concurrencyPolicy`: `Allow` (default, concurrent runs permitted), `Forbid` (skip a
  new run if the previous Job hasn't finished — `startingDeadlineSeconds` is still evaluated after
  the prior Job completes), `Replace` (new Job replaces the running one). [DOC S1726]
- CronJob `.spec.startingDeadlineSeconds`: deadline in seconds for starting a Job that missed its
  schedule; if exceeded, that occurrence is skipped and counted failed; unset means no deadline. [DOC S1726]
- `activeDeadlineSeconds` is a Job-level (not CronJob-level) field bounding how long a running Job may
  execute before being terminated. [DOC S1727]
- Kubernetes docs do not discuss liveness/readiness probes for batch Jobs/CronJobs — these probes are
  for long-running services, not finite workloads, which instead rely on Job success/failure status.
  [DOC S1726]
- `zoneinfo` looks first in directories on `TZPATH` (POSIX has well-known default locations, e.g.
  `/usr/share/zoneinfo`; Windows has none by default), then falls back to the `tzdata` PyPI package;
  if neither has the key, it raises `ZoneInfoNotFoundError`. Python docs explicitly recommend
  depending on the `tzdata` package for cross-platform projects, "including notably Windows". [DOC S1728]
- `TZPATH` can be set via the `PYTHONTZPATH` environment variable or `reset_tzpath()` at runtime, in
  addition to compile-time `--with-tzpath` (POSIX only). [DOC S1728]

## Reference
- A tool's instance-kind config values (kind, roles) read from environment/config file matches
  Factor III directly.
- A Windows Scheduled Task job standing in for a scheduled-host kind is the on-prem analogue of a
  CronJob: it needs an explicit "skip if still running" policy and a hard runtime ceiling, the same
  two guarantees `concurrencyPolicy: Forbid` + `activeDeadlineSeconds` give a CronJob.

## Examples
- A single-writer sync job can use a database application lock (e.g. SQL Server's `sp_getapplock`) as
  its concurrency guard — functionally the single-writer effect `concurrencyPolicy: Forbid` gives a
  CronJob, achieved at the database layer instead of the scheduler layer, which is the right layer
  when there is no Kubernetes.
- A Python tool's dependency list should include `tzdata` unconditionally (not just conditioned on
  Windows) whenever any of its target hosts may run Windows, since `zoneinfo` would otherwise silently
  have no timezone database there. [DER S1728: tzdata must ship as a normal dependency, not a
  Windows-only extra, because zoneinfo's Windows gap is unconditional]

## Derivations
- A tool whose rule is "every wait/poll names its end states and a ceiling" is applying the same idea
  as `activeDeadlineSeconds` + `startingDeadlineSeconds`: a scheduled job needs both "how late can it
  start" and "how long can it run" bounds even without Kubernetes, because a Windows Scheduled Task has
  no native equivalent of either — the job itself must enforce both in code.
  [DER S1726,S1727: CronJob's two deadline concepts are must-haves for any scheduler, K8s or not]
- Secrets-as-files (not env vars) is the safer default per general engineering practice (visible in
  process listings, manifests, logs, and inherited by child processes), which is *already* stronger
  than what Kubernetes docs mandate (K8s treats both as equally valid): a local rule of "secrets are
  never put on argv, in the environment of child processes, or in output" is a stricter rule that
  happens to agree with the volume-mount pattern's motivation, not something K8s docs themselves state
  as required. [DER S1725,S1729: K8s docs are neutral on env-vs-file; a stricter no-env-var stance is
  a local policy choice, not sourced from Kubernetes]

## Conflicts
- None: Kubernetes docs neither require nor forbid env-var secrets, so a stricter no-argv/no-env-var
  local secrets policy is not in conflict with them — it simply goes further. [DOC S1725]
