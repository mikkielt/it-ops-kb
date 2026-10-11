---
topic: arch/heartbeat-dead-man-monitors
priority: P3
applies_to: "Dead-man heartbeat monitors (Healthchecks) for agents that must report on a schedule"
retrieved_utc: 2026-10-11
sources: [S-fgzitvvz, S-agjtc4hy, S-mwxrr7ac]
status: partial
---

# Dead-man heartbeat monitors on a second provider

## Summary
A heartbeat monitor stays silent while pings arrive on time and alerts when one is missing, so it reports the failure of the thing that would otherwise have to report its own death. Healthchecks documents the model in detail and is open source. Putting the monitor at a second provider is a design rule derived here, not a vendor statement.

## Facts
- Healthchecks listens for HTTP requests ("pings") from cron jobs and scheduled tasks, keeps silent while they arrive on time and raises an alert when one does not; its docs call this a dead man's switch. [DOC S-fgzitvvz]
- A check is New, Up, Late, Down or Paused; it is Late when the signal is due, and Down once the configured Grace Time has also passed, which is when the integrations (email, webhook, SMS, Slack, PagerDuty and others) are notified. [DOC S-fgzitvvz]
- A simple schedule has a Period and a Grace Time; a cron schedule takes an expression and the server's time zone; an OnCalendar schedule matches a systemd timer, with several expressions allowed. [DOC S-agjtc4hy]
- A check has a unique ping URL, by UUID or by project ping key plus slug; appending `/start`, `/fail` or `/<exitcode>` sends start and failure signals; the UUIDs and ping keys are to be treated as secrets because anyone who has one can send signals. [DOC S-fgzitvvz]
- A slug ping can auto-provision a check that does not exist, an option the project enables. [DOC S-fgzitvvz]
- Filtering rules can require HTTP POST for pings and decide what happens when a paused check is pinged; "stay paused" makes the pause sticky until resumed. [DOC S-agjtc4hy]
- The reliability tips advise a request time limit (`curl -m 10`) and retries (`curl --retry 5`) on the ping so that a stuck or failed request neither blocks the job nor raises a false alert. [DOC S-mwxrr7ac]
- Healthchecks states it is the wrong tool for probing website uptime by HTTP requests, for application metrics and for log aggregation. [DOC S-fgzitvvz]
- A host or an agent that has failed, lost its network or been blocked cannot send an alert about it, so the receiving monitor must not share the failure domain (provider account, network, DNS, identity) of the estate it watches; the agent pings after each completed pull-and-apply cycle, with Period equal to its interval and a Grace Time larger than its jitter. [DER S-fgzitvvz, S-agjtc4hy: a missing ping is the alarm, schedule and Grace Time are the tuning]
- Other providers' heartbeat features (Cronitor, Better Stack, UptimeRobot, Alertmanager's Watchdog) were not read, so no vendor comparison or second-provider recommendation rests on a source here. [UNK: logged in `_gaps.md`]

## Reference
| concept | Healthchecks term | source |
|---|---|---|
| expected interval | Period (simple schedule) | S-agjtc4hy |
| tolerance | Grace Time | S-fgzitvvz |
| success / start / failure | ping URL, `/start`, `/fail` | S-fgzitvvz |
| alert targets | integrations | S-fgzitvvz |

## Examples
- SNIPPET: ping after a successful cycle, with a time limit and retries; context: curl, placeholder ping URL; checked: no [DOC S-mwxrr7ac: `curl -m 10`, `curl --retry 5`; S-fgzitvvz: ping URL]
```
curl -fsS -m 10 --retry 5 https://hc.corp.example.com/ping/00000000-0000-0000-0000-000000000000
```
