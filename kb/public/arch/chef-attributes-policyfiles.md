---
topic: arch/chef-attributes-policyfiles
priority: P3
applies_to: "Chef Infra Client 19 (docs.chef.io Chef Infra Client 19 pages): attribute types, sources, precedence, deep merge and persistence; Policyfile.rb, Policyfile.lock.json and the chef CLI commands that build and push a lock"
retrieved_utc: 2026-10-15
sources: [S-hacsn2hl, S-kfuw3ueg, S-6rblahwp, S-ohmkm4e7, S-ajlt32j5, S-fypqy7jh, S-zskepmir]
status: partial
---

# Chef attributes (precedence, merge) and Policyfiles (what a lock pins)

## Summary
Chef Infra Client applies six attribute types from up to five source locations, which makes up to 15 competing values; the last applied wins, and an attribute that a role or environment sets over a cookbook default is overridden unless the cookbook uses the `force_` forms. Hashes merge key by key (deep merge); arrays merge only within one precedence level and are otherwise replaced; scalars are replaced. Only normal attributes persist between runs. A Policyfile pins the run list, the exact cookbook versions with a content hash and their sources, and the attributes into one `Policyfile.lock.json` that is pushed to a policy group of nodes; it replaces roles, environments and run-time dependency solving, not every Berkshelf use.

## Facts
- Chef Infra Client uses six attribute types (`default`, `force_default`, `normal`, `override`, `force_override`, `automatic`) gathered from up to five locations, giving up to 15 competing values in a run. [DOC S-hacsn2hl]
- Application order, last one wins: `default` (cookbook attribute file, recipe, environment, role), `force_default` (attribute file, recipe), `normal` (a JSON file passed with `chef-client -j`, attribute file, recipe), `override` (attribute file, recipe, role, environment), `force_override` (attribute file, recipe), `automatic` (Ohai). [DOC S-kfuw3ueg]
- For `default` the order is environment, then role; for `override` it is role, then environment, so a role's override applies first and an environment's override sits on top. [DOC S-kfuw3ueg]
- A `default` set in a cookbook is replaced by any value a role or environment sets; `force_default` (or the `default!` form) in the cookbook keeps it above them, and `force_override` or `override!` does the same for override. [DOC S-kfuw3ueg]
- `default` is reset at the start of every run and has the lowest precedence, and the documentation advises using it as often as possible in cookbooks; `override` is also reset every run and should be used in cookbooks only when required. [DOC S-hacsn2hl]
- `normal` persists in the node object and ranks above `default`; `automatic` is Ohai data collected at the start of every run, cannot be modified and always has the highest precedence. [DOC S-hacsn2hl]
- Attributes come from JSON files passed with `-j`, Ohai, attribute files and recipes of cookbooks, environments, roles and Policyfiles; the node object from the previous run is pulled and every attribute except normal is reset before they are rebuilt and applied by precedence. [DOC S-6rblahwp]
- Attribute files of cookbooks are evaluated in run-list order, including cookbooks that arrive as dependencies. [DOC S-6rblahwp]
- Attributes set with `chef-client -j` have normal precedence and persist between runs; every other kind is rebuilt each run from Ohai, cookbooks, roles, environments and Policyfiles, and the result is saved to the server at the end of the run. [DOC S-ohmkm4e7]
- Deep merge layers attributes across cookbooks, recipes, roles and environments: a role that sets only `prefork.startservers` leaves the other `prefork` keys of the baseline role in place. [DOC S-ajlt32j5]
- Merge logic: a hash value is merged; an array value is merged when the precedence levels are the same and replaced when they differ; any other value type (string, integer) is replaced. [DOC S-ajlt32j5]
- `node.rm_default`, `rm_normal` and `rm_override` remove one precedence level of a key and return its computed value, `node.rm` removes the key at every level, and a `!` write (`node.default!`) clears the key at that level before writing. [DOC S-kfuw3ueg]
- The `_unless` variants (`default_unless`, `normal_unless`) set a value only when the attribute has none; the documentation warns this can leave nodes out of step with updated cookbooks and be hard to debug. [DOC S-6rblahwp]
- Attribute saving to the server can be limited in `client.rb` with `blocked_automatic_attributes`, `blocked_default_attributes`, `blocked_normal_attributes`, `blocked_override_attributes` (and `allowed_*` forms), each type separately; the default `nil` saves everything. [DOC S-ohmkm4e7]
- The blacklist and whitelist setting names were deprecated in 16.3 for blocklist and allowlist, and the page says the old names reached end of life in 18.4.12 (it also says they work through 17.x). [DOC S-ohmkm4e7]
- A Policyfile is an immutable collection of cookbooks, cookbook dependencies and attributes in one document uploaded to Chef Infra Server and associated with a group of nodes. [DOC S-fypqy7jh]
- `Policyfile.rb` requires `name` and `run_list`; it may set `default_source` (`:supermarket`, `:chef_server`, `:chef_repo`, `:artifactory`), `cookbook` entries with version constraints and alternate sources (path, git, GitHub), `named_run_list`, `include_policy` and `default` / `override` attributes. [DOC S-fypqy7jh]
- When a cookbook exists in more than one source the Policyfile states which one is preferred with `preferred_for`, so a private cookbook named like a public one is not pulled from the wrong source. [DOC S-fypqy7jh]
- `include_policy` merges another policy lock into this one: its run list comes first, its solved cookbooks must appear as they are, and a conflicting attribute or cookbook raises an error. [DOC S-fypqy7jh]
- Policyfile attributes are only `default` and `override`, and attribute hoisting defines values per policy group, for example `default['prod']['attribute']`. [DOC S-fypqy7jh]
- `chef install` resolves the Policyfile into a compatible cookbook set, caches it and writes `Policyfile.lock.json`; the lock records the cookbook versions, a hash of cookbook content, the source of every cookbook and the attributes. [DOC S-fypqy7jh]
- A lock is associated with one policy group, that is, with the nodes that use that revision of the policy. [DOC S-fypqy7jh]
- `chef update` re-reads `Policyfile.rb`, re-resolves dependencies and pulls in cookbook updates that satisfy the constraints, and its `--attributes` option (default false) also updates the attributes. [DOC S-fypqy7jh]
- `chef push POLICY_GROUP POLICY_FILE` uploads the lock and its cookbooks to the server for a policy group; `chef export` writes a chef-zero-compatible repository (or an archive with `-a`) that a node can apply with `chef-client -z`, and `chef push-archive` publishes an archive. [DOC S-fypqy7jh]
- The cookbook set is computed on the workstation and written to the lock, so each run of a policy-managed node uses the pre-computed file for its policy name and group instead of re-evaluating run list, roles, environment and metadata dependencies every run. [DOC S-fypqy7jh]
- A node is attached to a policy with `policy_name` and `policy_group` in `client.rb` or the first-boot JSON, or with `knife bootstrap --policy-name` and `--policy-group`, or `knife node policy set`; in a Kitchen `chef_zero` converge there is no server, so the policy group is set to `local`. [DOC S-fypqy7jh]
- The documentation says a Policyfile replaces roles and environments (versioned automatically, applied when promoted) and the environment-cookbook pattern, but not all Berkshelf scenarios. [DOC S-fypqy7jh]
- A node's rebuilt node object holds the attributes set in Policyfiles or cookbooks, and during the attribute step all attributes from attribute files, Policyfiles and Ohai load before precedence is applied. [DOC S-zskepmir]
- Where Policyfile `default` and `override` attributes sit in the 15-level precedence table is not stated: the precedence page names roles and environments but never mentions Policyfiles. [UNK]
- How it fits: for drift or compliance reasoning, a lock is the artefact to compare (`chef diff` of two revisions), because it fixes cookbook versions by content hash; a node on a policy cannot silently pick up a newer cookbook version the way a run-list node with open constraints can. [DER S-fypqy7jh: lock content hash, per-group association, pre-computed solution]
- How it fits: attributes feed `default` from a cookbook, so a node-specific override should be written at `override` or in the policy, and a secret should never be in an attribute: all saved attributes reach the server and are searchable, so sensitive keys need the blocklist settings or a secret store resolved at run time, not a role file in a repository. [DER S-ohmkm4e7, S-6rblahwp: attributes saved to the server and indexed; kb frame: secrets never in repositories]

## Reference
| need | where | source |
|---|---|---|
| the six types and their persistence | Attribute Types | S-hacsn2hl |
| precedence order, `force_`, `!`, removal | Attribute Precedence | S-kfuw3ueg |
| sources, files, `_unless` | Attribute Sources | S-6rblahwp |
| persistence, blocklists | Attribute Persistence | S-ohmkm4e7 |
| deep merge and array logic | Attribute Arrays | S-ajlt32j5 |
| Policyfile.rb, lock, chef CLI | About Policyfiles | S-fypqy7jh |
- `arch/chef-infra-client-run.md` — when attributes reset and load in a run; `arch/chef-cookbooks-recipes-resources.md` — cookbook layout; `arch/chef-windows-nodes.md` — Windows nodes.
- `prior-art/drift-detection.md` — Chef InSpec beside Puppet noop.

## Examples
- SNIPPET: a Policyfile that pins a cookbook from a private path, a public cookbook with a constraint and a per-group attribute; context: Chef Workstation, names are placeholders; checked: no [DOC S-fypqy7jh: `name`, `run_list`, `default_source`, `cookbook`, attribute hoisting]
```
name 'example-app'
run_list 'example_app::default'
default_source :supermarket
cookbook 'example_app', path: 'cookbooks/example_app'
cookbook 'example_dependency', '~> 2.1'
default['prod']['example_app']['port'] = 8443
```
