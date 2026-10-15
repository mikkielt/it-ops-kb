---
topic: arch/puppet-agent-run-noop-reporting
priority: P3
applies_to: "Puppet 8.x (Puppet Core 8.22.0 docs; source at commit e227c27, in-tree version 8.11.0): the agent run and its order, run settings, noop mode, run reports, exit codes"
retrieved_utc: 2026-10-15
sources: [S-rg67vl44, S-5tsldiae, S-z6kl5grq, S-uqxc7z4f, S-cttzm2qq, S-w5xtdsyr, S-4dquzyfj, S-fhswdmzt, S-e7vpuvbk, S-wwls72e7, S-xsvufwtx]
status: partial
---

# Puppet agent run, noop mode and reporting

## Summary
The Puppet agent fetches a node's configuration from a primary server and applies it. One run is: authenticate with a certificate, learn the environment, sync plugins, send facts and receive a compiled catalog, apply the catalog resource by resource, then send a report. `noop` (no-operation) mode does the same run but takes no action: each out-of-sync resource is reported as a change Puppet *would* have made, and no refresh events are sent. The setting and the per-resource metaparameter interact: an explicit resource value wins. Everything here is Puppet 8; the open-source repository and the commercial Puppet Core documentation describe the same agent.

## Facts
- Puppet describes itself as an automated administrative engine for Linux, Unix and Windows systems. [DOC S-rg67vl44]
- The pinned source tree (commit `e227c27`) carries version 8.11.0 in `lib/puppet/version.rb`, while the Puppet Core 8 documentation pages read the same day are stamped 8.22.0, so the pinned configuration reference can lag the current documentation. [CODE S-5tsldiae: lib/puppet/version.rb#PUPPETVERSION]
- The agent's job is to retrieve the machine's configuration from a remote server and apply it; it needs a certificate signed by a certificate authority the server trusts and keeps connecting until it receives one. [DOC S-z6kl5grq]
- Order of one agent run: download the CA bundle (and the CRL when revocation is enabled), load or create the private key and submit a certificate request, download the signed certificate, request the node object, sync plugins, request a catalog while submitting facts, apply the catalog (making file source requests as needed), then submit the report. [DOC S-uqxc7z4f]
- The agent requests the node object with `GET /puppet/v3/node/<NAME>`; an environment in the node object replaces the one in the agent's config file, and when the request fails or the node has none the agent keeps its own. [DOC S-uqxc7z4f]
- When pluginsync is enabled the agent fetches plugins from the `plugins` file server mount that scans the `lib` directory of every module (`GET /puppet/v3/file_metadatas/plugins`, then `file_content` for each changed file), before the catalog request. [DOC S-uqxc7z4f]
- The catalog request is `POST /puppet/v3/catalog/<NAME>` with all of the node's facts encoded as JSON in the post data. [DOC S-uqxc7z4f]
- Plugin sync and catalog compilation resolve deployed code independently, so a code deployment that activates between them can make one run evaluate facts against the previous plugin code and compile against the newer manifests. [DOC S-uqxc7z4f]
- A `file` resource's `content` goes into the catalog, but a `source` puts only a reference there and can cost extra HTTPS requests during apply; with the static compiler the file metadata is embedded in the catalog instead. [DOC S-uqxc7z4f]
- If reporting is enabled on the agent, it ends the run with `PUT /puppet/v3/report/<NAME>` carrying the report object in YAML format. [DOC S-uqxc7z4f]
- `runinterval` is how often the agent applies the catalog; it defaults to `30m`, and a value of 0 means "run continuously", not "never run". [DOC S-cttzm2qq]
- `splay` defaults to `false`; enabled, the agent sleeps a random time up to `splaylimit` before its first run after each (re)start, and `splaylimit` defaults to `$runinterval`. [DOC S-cttzm2qq]
- `runtimeout` is the longest an agent run may take: a run that exceeds it is aborted, 0 disables the timeout, and the default is `1h`. [DOC S-cttzm2qq]
- `onetime` (default `false`) performs one configuration run and exits instead of spawning a long-running daemon, which suits interactive use and cron. [DOC S-cttzm2qq]
- `puppet agent --test` bundles `onetime`, `verbose`, `no-daemonize`, `no-usecacheonfailure`, `detailed-exitcodes`, `no-splay` and `show_diff`. [DOC S-z6kl5grq]
- `--detailed-exitcodes` works only with `--test` or `--onetime`; the exit codes are 0 (no changes or failures), 1 (run failed or was not attempted because another run was in progress), 2 (changes made), 4 (some resources failed) and 6 (changes and failures). [DOC S-z6kl5grq]
- `puppet agent --disable [MESSAGE]` puts a lock file in place so the agent does nothing until `--enable` removes it; the same lock file protects a running agent so that no more than one `puppet agent` process works at a time, and `--enable` keeps the normal schedule, so the next run may be half an hour away. [DOC S-z6kl5grq]
- The lock settings: `agent_catalog_run_lockfile` (default `$statedir/agent_catalog_run.lock`) holds the pid of the process running a catalog, and `agent_disabled_lockfile` (default `$statedir/agent_disabled.lock`) holds a JSON object with the state of an administrative disable. [DOC S-cttzm2qq]
- `usecacheonfailure` (default `true`) makes the agent use its cached configuration when the remote one will not compile; `use_cached_catalog` (default `false`) skips compiling a new catalog and, because the primary server is not contacted, uploads no facts at the start of the run. [DOC S-cttzm2qq]
- The `noop` setting applies to `puppet agent` and `puppet apply`: Puppet still checks whether each resource is in sync, but takes no action on an attribute that is not in its desired state and reports the changes it would have made, in the report sent to the primary server or on the console in the foreground. [DOC S-cttzm2qq]
- Simulated changes send no refresh events to subscribing or notified resources, although Puppet logs that a refresh event would have been sent. [DOC S-cttzm2qq]
- The `noop` metaparameter applies noop mode to one resource; the global `noop` setting does not override it, so a resource with `noop => false` is changed when needed even in a noop run, and a resource with `noop => true` is only simulated in a normal run. [DOC S-w5xtdsyr]
- In noop mode a resource that receives a refresh event does not refresh and Puppet logs what would have happened, and it does not send refresh events to subscribed resources, so the log shows what would have happened further down a subscription chain. [DOC S-4dquzyfj]
- A report holds metadata about the node, environment, Puppet version and catalog, the status of every resource, the events taken during the run, log messages and metrics such as duration and counts of resources per state. [DOC S-fhswdmzt]
- An agent sends its report to the primary server by default; the agent's `report` setting (default `true`) turns reporting off, and `report_server` (default `$server`) and `report_port` (default `$serverport`) name where it goes. [DOC S-cttzm2qq]
- The `reports` setting lists the report processors the primary server (or `puppet apply`) runs; its default is `store`, several are comma-separated, and `none` turns reports off. [DOC S-cttzm2qq]
- The built-in report processors are `http` (POSTs the YAML report to `reporturl`), `log` (sends the logs to the local log destinations) and `store` (writes each host's YAML report under `reportdir`; files pile up about one every half hour per node, and it is the only default processor). [DOC S-e7vpuvbk]
- The agent keeps its last run in `lastrunreport` (default `$statedir/last_run_report.yaml`) and a summary in `lastrunfile` (default `$publicdir/last_run_summary.yaml`). [DOC S-cttzm2qq]
- The report object records `noop` (whether the run started in noop mode, taken from the `noop` setting) and `noop_pending`, which is true when any resource status carries an event whose status is `noop`. [CODE S-wwls72e7: lib/puppet/transaction/report.rb#noop_pending]
- A report's status is `failed` when the transaction did not complete or any resource failed or failed to restart, `changed` when the change total is above zero, otherwise `unchanged`. [CODE S-wwls72e7: lib/puppet/transaction/report.rb#compute_status]
- `compute_status` takes only the resource metrics and the change total, so `noop_pending` is a separate field: a consumer that wants to know a noop run found drift reads it (or the `noop` events), not the status. [DER S-wwls72e7: compute_status arguments; noop_pending set in finalize_report]
- A resource status sets `out_of_sync` when it receives an event whose status is not `audit`, and `corrective_change` when any event is corrective; the report's `corrective_change` is true when any resource status has one, noop corrective changes included. [CODE S-xsvufwtx: lib/puppet/resource/status.rb#out_of_sync]
- How it fits: a read-only drift check on a Puppet node is one noop run followed by reading `noop_pending` (or the noop events) from `last_run_report.yaml` or from the report the primary server received; enforcement is the same run without noop, so the check needs no second tool but does need the node's own agent, its certificate and a primary server. [DER S-cttzm2qq, S-wwls72e7, S-uqxc7z4f: noop semantics; report fields; run order]
- This kb found no Puppet source stating the exit code of a `--noop --detailed-exitcodes` run; the man page lists the codes without a noop case. [UNK: logged in `_gaps.md`]

## Reference
| need | where | source |
|---|---|---|
| order of a run | agent-server HTTPS page | S-uqxc7z4f |
| run settings (`runinterval`, `splay`, `runtimeout`, `noop`, `report`, `reports`) | configuration reference | S-cttzm2qq |
| per-resource noop and `audit` | metaparameter reference | S-w5xtdsyr |
| agent flags and exit codes | `puppet agent` man page | S-z6kl5grq |
| built-in report processors | report reference | S-e7vpuvbk |
| report fields | `lib/puppet/transaction/report.rb`, `lib/puppet/resource/status.rb` | S-wwls72e7, S-xsvufwtx |
- `arch/puppet-language-resources-types.md`, `arch/puppet-modules-facts-hiera.md`, `arch/puppet-windows-nodes.md` — the rest of the Puppet area.
- `prior-art/drift-detection.md` — Puppet noop beside Ansible check mode and DSC what-if; `dsc/what-if.md` for the DSC form.

## Examples
- SNIPPET: one foreground run that only simulates; context: Puppet 8 agent, run as the node's administrator, no changes are made; checked: no [DOC S-z6kl5grq: `--test`, `--noop` flags as the man page lists them]
```
puppet agent --test --noop
```
- SNIPPET: an agent configuration that runs every two hours with a random start delay; context: `puppet.conf` `[agent]` section; checked: no [DOC S-cttzm2qq: `runinterval`, `splay` as the configuration reference defines them]
```
[agent]
runinterval = 2h
splay = true
```
