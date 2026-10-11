---
topic: security/linux-time-sync
priority: P3
applies_to: "chrony and systemd-timesyncd on Linux hosts"
retrieved_utc: 2026-10-11
sources: [S-fdtse7p7, S-hur3aczb, S-6uvypfv2, S-ycjp6jnv]
status: complete
---

# chrony and systemd-timesyncd

## Summary
Two time clients cover Linux hosts: `systemd-timesyncd`, an SNTP client with a few settings, and `chrony`, a full NTP client and server with NTS support. The CIS mapping asks for one daemon per host, configured with an authorised time server.

## Facts
- `systemd-timesyncd` implements SNTP only: it steps the clock for a large offset and slews it for a small one; use cases that need full NTP are not covered by it. [DOC S-hur3aczb]
- `timedatectl set-ntp` enables and starts, or disables and stops, the timesyncd service; `timedatectl timesync-status` shows its state. [DOC S-hur3aczb]
- `systemd-timesyncd` does not hold back other units until the clock is accurate; `systemd-time-wait-sync.service` does that for units ordered after `time-sync.target`. [DOC S-hur3aczb]
- The mtime of `/var/lib/systemd/timesync/clock` is updated on each successful synchronisation, and at start the daemon advances the system clock to it if the clock is earlier. [DOC S-hur3aczb]
- timesyncd reads `/etc/systemd/timesyncd.conf` and drop-ins in `/etc/systemd/timesyncd.conf.d/*.conf` (also the `/run` and `/usr/lib` equivalents), section `[Time]`. [DOC S-6uvypfv2]
- `NTP=` is a space-separated list of servers, combined with per-interface servers from systemd-networkd and contacted in turn until one answers; `FallbackNTP=` is used only when no other server is configured or learned. [DOC S-6uvypfv2]
- `PollIntervalMinSec=` defaults to 32 seconds and must not be below 16; `PollIntervalMaxSec=` defaults to 2048 seconds; `RootDistanceMaxSec=` makes timesyncd switch server when the current one is too far from its reference clock. [DOC S-6uvypfv2]
- chrony's manual example for a client with a permanent connection lists three servers with `iburst`, then `driftfile`, `makestep 1.0 3` and `rtcsync`; a variant uses `pool pool.ntp.org iburst` and another adds the `nts` option to each server. [DOC S-fdtse7p7]
- chrony's manual writes `server HOST nts` for a Network Time Security source, shows an `ntsdumpdir` directive, and uses `require trust` as a source option in its source-selection examples. [DOC S-fdtse7p7]
- The SSG control file for CIS Debian 12 (benchmark v1.1.0 mapping) has 2.3.1.1 "a single time synchronization daemon is in use", 2.3.2.1 and 2.3.2.2 for timesyncd (authorised time server, enabled and running) and 2.3.3.1 to 2.3.3.3 for chrony (authorised time server, running as user `_chrony`, enabled and running); all are Level 1 Server and Workstation. [CODE S-ycjp6jnv: controls/cis_debian12.yml#2.3]
- Pick one client per host family: timesyncd where an SNTP client and a short server list are enough (it needs only `NTP=`), chrony where NTS, many sources or serving time to others is needed; the CIS control then needs the other one absent or disabled. [DER S-hur3aczb, S-fdtse7p7, S-ycjp6jnv: SNTP-only scope, NTS in chrony, single-daemon control]

## Reference
| setting | timesyncd | chrony |
|---|---|---|
| servers | `NTP=`, `FallbackNTP=` | `server`, `pool` |
| config path | `/etc/systemd/timesyncd.conf(.d/)` | `chrony.conf` |
| first-sync step | built in (step for large offset) | `makestep` |
| NTS | not stated in the page read | `nts` option |

## Examples
- SNIPPET: a timesyncd drop-in naming two servers; context: systemd with timesyncd, placeholder host names; checked: no [DER S-6uvypfv2: `[Time]` section, `NTP=` list, drop-in directory]
```
# /etc/systemd/timesyncd.conf.d/10-site.conf
[Time]
NTP=ntp1.corp.example.com ntp2.corp.example.com
```
