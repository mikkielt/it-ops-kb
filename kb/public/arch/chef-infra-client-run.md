---
topic: arch/chef-infra-client-run
priority: P3
applies_to: "Chef Infra Client 19 (docs.chef.io Chef Infra Client 19 pages; source at chef/chef commit 9322fa4): the run and its order, the run list, why-run, scheduling, licensing and status"
retrieved_utc: 2026-10-15
sources: [S-kj2xytgs, S-zskepmir, S-yddwaulv, S-z5kgh6p7, S-ddprubpp, S-og5svrch, S-ljusqk46, S-qdnvehti, S-d6oc2jt7]
status: partial
---

# Chef Infra Client run, run list and why-run

## Summary
Chef Infra Client is the agent on each managed node. A run reads its configuration and Ohai data, authenticates to Chef Infra Server, rebuilds the node object, expands the run list, syncs cookbooks, resets attributes, compiles every recipe into a resource collection and only then converges, so a resource's code is read before any resource acts. The node object is saved back only when the converge succeeds. The run list is an ordered list of roles and recipes; a Policyfile replaces it with a locked one. `--why-run` does everything except map resources to providers and change the system. Chef Infra Client 19 needs a licence key or an official distribution. On Windows the agent has no daemon mode: a scheduled task or a service wrapper triggers each run.

## Facts
- A Chef Infra Client run, started with the `chef-client` command, follows these stages in order: get configuration data, authenticate to the server, get and rebuild the node object, expand the run list, synchronize cookbooks, reset node attributes, compile the resource collection, converge, update the node object and process handlers, then the compliance phase. [DOC S-zskepmir]
- Configuration data comes from `client.rb` on the node and from Ohai; the node name is the `node_name` setting or, when Ohai supplies it, usually the node's FQDN. [DOC S-zskepmir]
- The node authenticates to Chef Infra Server with an RSA private key and the server API; on a node's first run the `chef-validator` generates the key. [DOC S-zskepmir]
- A node object holds the Ohai data, the attributes from Policyfiles or cookbooks and the run list; the first run builds it from the default run list, and later runs rebuild it with the run list of the previous run. [DOC S-zskepmir]
- The run list is expanded into the complete list of recipes in the exact order they will be applied. [DOC S-zskepmir]
- Cookbook synchronisation requests the files the run list needs (recipes, templates, resources, providers, attributes, libraries), compares them with the files from previous runs and downloads only new or modified ones. [DOC S-zskepmir]
- All attributes of the rebuilt node object are reset before the run: attribute files load by cookbook order, `default.rb` first and then the other files in lexical order, and files of cookbooks named as dependencies in `metadata.rb` load too. [DOC S-zskepmir]
- The compile phase loads libraries first, then attributes, then custom resources, and finally every recipe in the order of the expanded run list; it builds the resource collection without changing the node. [DOC S-zskepmir]
- Converge runs each resource in run-list order and then in the order the resource is listed in its recipe; each resource carries an action that configures one part of the system, and this execution phase is called convergence. [DOC S-zskepmir]
- When every action completed and the run finished successfully the node object is saved to the server, available for search; the resource collection is always checked for exception and report handlers. [DOC S-zskepmir]
- In the source at the pinned commit `Chef::Client#run` takes the run lock, runs Ohai, registers the node (unless in legacy solo mode), loads and builds the node, does the Windows administrator check, sets up the run context, loads the required recipe, then converges and saves the node. [CODE S-z5kgh6p7: lib/chef/client.rb#L241-L330]
- `converge_and_save` calls `converge` and then `save_updated_node`, so a converge that raises skips the node save. [CODE S-z5kgh6p7: lib/chef/client.rb#L900-L903]
- A reboot requested by a resource is the last step of the run, after the run is reported complete. [CODE S-z5kgh6p7: lib/chef/client.rb#L310]
- After the run the compliance phase executes a Chef InSpec run from within the client, with tests taken from a legacy audit cookbook or a current InSpec profile, and then sends or saves the report. [DOC S-zskepmir]
- A run list is an ordered list of roles and recipes, specific to the node, stored in its node object and maintained with knife or Chef Automate; a recipe that appears more than once runs only once. [DOC S-zskepmir]
- Run list items are written `role[NAME]` or `recipe[COOKBOOK::RECIPE]`, both quoted, comma separated; the cookbook form `COOKBOOK::RECIPE` and the bare cookbook name (its default recipe) are also accepted. [DOC S-zskepmir]
- An empty run list is the quick test of whether a failing run is caused by the recipes: if the failure persists, check `client.rb` and the permissions of the user on the server and on the node. [DOC S-zskepmir]
- `knife node run_list add` places an item after or before another item with `--after` and `--before`; `knife node run_list set` replaces the whole list. [DOC S-zskepmir]
- On `knife bootstrap`, the first Chef Infra Client run has an empty run list by default and `--run-list` adds one to the bootstrap. [DOC S-zskepmir]
- `-o` / `--override-runlist` replaces the run list for one run without clearing the cookbooks cached on the node and without persisting node data at the end of the run; `-r` / `--runlist` replaces it permanently. [DOC S-yddwaulv]
- `-n` / `--named-run-list` selects the named run list of a Policyfile. [DOC S-yddwaulv]
- `--once` makes a single run and cancels the interval and splay options. [DOC S-yddwaulv]
- `-W` / `--why-run` runs everything up to the point where configuration would occur (configuration data, authentication, node object, run list, cookbook files, attribute reset, resource collection) but does not map resources to providers or change any part of the system. [DOC S-yddwaulv]
- why-run is not a replacement for testing cookbooks on an environment that mirrors production; it assumes a service with no status command would not be running, and assumes `not_if` and `only_if` conditions are safe to run. [DOC S-yddwaulv]
- A second Chef Infra Client waits for the run lock file by default without limit; `--run-lock-timeout SECONDS` limits the wait, and `0` makes the second client exit immediately. [DOC S-yddwaulv]
- `--interval` sets the seconds between runs (default value 1800) and `--splay` adds a random number between zero and the splay value to the interval, to spread load on the server. [DOC S-yddwaulv]
- In the source, an interval of 1800 is set only when `daemonize` is on; `once` clears interval and splay; and a set interval is a fatal error on Windows (`Chef::Application.fatal!` with a Windows-specific message) and on a non-forked run elsewhere. [CODE S-ddprubpp: lib/chef/application/client.rb#L148-L168]
- The `-d` / `--daemonize` option works only on UNIX and Linux; for Windows the documentation points to the `chef-client::service` recipe of the `chef-client` cookbook, which installs a service with the Windows Service Wrapper. [DOC S-yddwaulv]
- Chef Infra Client 19 needs a licence key when it is downloaded from unofficial sources (the public Ruby gem) or used in runtime installations, and no key from the customer portal, the Habitat package, the migration tool or the native installer; the EULA must be accepted on the first run. [DOC S-ljusqk46]
- The licence key is set with the `CHEF_LICENSE_KEY` environment variable, the `--chef-license-key` option or an interactive dialog, and is validated against Progress Chef's licensing service; EULA acceptance options are `accept`, `accept-silent` and `accept-no-persist`. [DOC S-ljusqk46]
- The Chef Infra Client overview lists Agentless mode, which runs Infra Client on a target node over SSH without Infra Client installed on it. [DOC S-kj2xytgs]
- The latest Chef Infra Client entry in the release notes read on 2026-10-15 is 19.3.15 of 2026-05-22. [DOC S-qdnvehti]
- The Chef documentation home page announces that Chef Infra Server is deprecated and reaches end of life on 2026-11-30, with Chef 360 Platform named as the replacement. [DOC S-d6oc2jt7]
- The `interval` setting itself defaults to `nil` in the configuration, so no repeat happens unless `daemonize` supplies 1800 or the interval is set. [CODE S-og5svrch: chef-config/lib/chef-config/config.rb#L487]
- How it fits: a run reads and compiles the whole run list before the first resource acts, and the node object is saved only after a successful converge; for drift checks the useful split is that `--why-run` stops short of provider mapping, so a resource whose provider cannot be chosen until an earlier resource installs it is reported by assumption, not by observation. [DER S-yddwaulv, S-zskepmir, S-z5kgh6p7: why-run stops before provider mapping; node saved after converge]
- How it fits: a Windows node has no daemon, so unattended runs need a scheduled task (the MSI feature or a `chef_client_scheduled_task` resource, see `arch/chef-windows-nodes.md`) or the cookbook's service wrapper; the licence key and the validator or client key are secrets, so they belong in the node's protected store, not in a cookbook or on a command line. [DER S-yddwaulv, S-ddprubpp, S-ljusqk46: no daemonize on Windows; licence key env or option; kb frame: secrets never in argv or repositories]

## Reference
| need | where | source |
|---|---|---|
| the run, stage by stage, and run-list syntax | About Run-lists | S-zskepmir |
| overview, components, Agentless | Chef Infra Client | S-kj2xytgs |
| options: why-run, interval, splay, override run list, run lock | chef-client reference | S-yddwaulv |
| run order in code, interval handling, config defaults | `lib/chef/client.rb`, `lib/chef/application/client.rb`, `chef-config/lib/chef-config/config.rb` | S-z5kgh6p7, S-ddprubpp, S-og5svrch |
| licensing | Apply a license in Chef Infra Client | S-ljusqk46 |
| versions and notices | release notes, documentation home | S-qdnvehti, S-d6oc2jt7 |
- `arch/chef-cookbooks-recipes-resources.md` — what a resource and a recipe are; `arch/chef-attributes-policyfiles.md` — attribute precedence and Policyfile locks; `arch/chef-windows-nodes.md` — Windows install, scheduling and resources.
- `prior-art/drift-detection.md` — Chef InSpec (the read-only compliance phase) beside Puppet noop and DSC.

## Examples
- SNIPPET: a one-shot run that only reports what would change, using a named run list of a Policyfile; context: Chef Infra Client 19 on a node, run in an elevated shell on Windows; checked: no [DOC S-yddwaulv: `--once`, `--why-run`, `--named-run-list`]
```
chef-client --once --why-run --named-run-list update_app
```
