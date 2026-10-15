---
topic: arch/chef-cookbooks-recipes-resources
priority: P3
applies_to: "Chef Infra Client 19 (docs.chef.io Chef Infra Client 19 pages): cookbook layout, recipes, resource syntax, default actions, common properties, guards and notifications"
retrieved_utc: 2026-10-15
sources: [S-u7h6xkoa, S-y6y7akrz, S-ttgsowye, S-gwzouzk5, S-kqb3kad4, S-k62unlt6, S-fhqrcrzk, S-xgkshne3, S-yz335vyz, S-oh6erfbm, S-zskepmir]
status: complete
---

# Chef cookbooks, recipes and resources

## Summary
A cookbook is the unit of distribution: recipes, attribute files, custom resources, files, templates, libraries, Ohai plugins and `metadata.rb`. A recipe is a Ruby file that is mostly resource declarations; resources are applied in the order written. Every resource has a type, a name, properties and an action, and every action has a default, but the default differs by type (`:install` for `package`, `:create` for `file`, `:run` for `execute`, `:nothing` for `service` and `reboot`). Guards (`only_if`, `not_if`) make a resource idempotent, and notifications run a resource when another changes, by default at the end of the run.

## Facts
- A cookbook is the fundamental unit of configuration and policy distribution; it holds recipes, attribute values, custom resources, files and templates, custom Ohai plugins and `metadata.rb`. [DOC S-u7h6xkoa]
- The cookbook directories are `recipes/`, `attributes/`, `files/`, `libraries/`, `resources/` (custom resources), `templates/` and `ohai/`, plus `metadata.rb` for the cookbook name, description and version. [DOC S-u7h6xkoa]
- A recipe is Ruby, mostly a collection of resources, must be stored in a cookbook, must be on a run list before Chef Infra Client can use it and always executes in the order the run list gives. [DOC S-u7h6xkoa]
- Running the same recipe repeatedly yields the same system state, and when nothing changed on the system or in the recipe Chef Infra Client changes nothing. [DOC S-u7h6xkoa]
- `include_recipe` inserts the included recipe's resources at the point of the call in the same order, and a recipe included more than once, or also named in the run list, is processed only at its first appearance. [DOC S-y6y7akrz]
- JSON and YAML recipes define resources without Ruby; the documentation states significant limitations compared with Ruby recipes and advises Ruby for dynamic logic, node attributes or resource relationships. [DOC S-y6y7akrz]
- The `environment` property of `execute` and script resources changes only the environment of the child process, not that of Chef Infra Client. [DOC S-y6y7akrz]
- A resource is a Ruby block with a type, a name, properties and an action: `type 'name' do ... action :x end`; most properties have defaults, and some properties (notifications, guards) exist on all resources. [DOC S-ttgsowye]
- Every action has a default, so `package 'tar'` installs the latest package with the default `:install` action and the package name defaults to the resource name. [DOC S-ttgsowye]
- The `file` resource's default action is `:create`. [DOC S-kqb3kad4]
- The `execute` resource's default action is `:run`. [DOC S-k62unlt6]
- The `service` resource's default action is `:nothing`. [DOC S-fhqrcrzk]
- The `windows_service` resource's default action is `:nothing`. [DOC S-yz335vyz]
- The `reboot` resource's default action is `:nothing`. [DOC S-oh6erfbm]
- The `windows_feature` resource's default action is `:install`. [DOC S-xgkshne3]
- `:nothing` is the one action every resource has: the resource acts only when notified, immediately or queued to the end of the run. [DOC S-gwzouzk5]
- Common properties for every resource: `compile_time` (default false; true runs the resource while the collection is built), `ignore_failure` (default false; `:quiet` hides the stack trace), `retries` (default 0), `retry_delay` (default 2 seconds) and `sensitive` (default false; keeps data out of logs). [DOC S-gwzouzk5]
- A guard is evaluated during the execution phase: a string is run as a shell command and applies when it returns 0, a Ruby block applies when it returns true; in a `powershell_script` a string guard runs as PowerShell and may also return true. [DOC S-gwzouzk5]
- `not_if` prevents a resource from executing when its condition is true and `only_if` allows it only when the condition is true; the string form takes `:user`, `:group`, `:environment`, `:cwd` and `:timeout`. [DOC S-gwzouzk5]
- A guard on an `execute` resource inherits the resource's environment, such as `cwd`. [DOC S-gwzouzk5]
- Notification timers: `:delayed` (default, queued to the end of the run), `:immediate` / `:immediately` (run at once, for each resource notified) and `:before` (run the notified action before the resource that notifies, added in 12.6). [DOC S-gwzouzk5]
- `notifies :action, 'resource[name]', :timer` raises an error when the named resource does not exist, while `subscribes` of the same form does not fail when the watched resource is missing. [DOC S-gwzouzk5]
- A lazily evaluated property (`lazy { ... }`) is computed when the resource runs, not when the recipe is compiled. [DOC S-gwzouzk5]
- The `reboot` documentation says notifications to it should be immediate only: delayed notifications produce unintuitive and probably undesired results. [DOC S-oh6erfbm]
- How it fits: because guards and `:nothing` resources are evaluated at converge time while recipe Ruby runs at compile time, a check or approval step belongs in a guard or a notification, not in bare Ruby in the recipe; a `--why-run` shows the planned resources, not the effect of delayed notifications. [DER S-gwzouzk5, S-zskepmir: compile versus converge phase; guards in the execution phase]
- How it fits: an agent that edits a cookbook should state the action explicitly where the default is `:nothing` (`service`, `reboot`), because a block without an action does nothing there, while the same shape on a `file` creates it. [DER S-ttgsowye, S-fhqrcrzk, S-oh6erfbm, S-kqb3kad4: default actions differ by resource]

## Reference
| need | where | source |
|---|---|---|
| cookbook layout, generate cookbook | About Cookbooks | S-u7h6xkoa |
| recipes, `include_recipe`, YAML and JSON recipes | About Recipes | S-y6y7akrz |
| resource syntax and default actions | About Resources | S-ttgsowye |
| guards, notifications, common properties | Common Resource Functionality | S-gwzouzk5 |
| per-resource defaults | the `file`, `execute`, `service`, `windows_feature`, `windows_service`, `reboot` pages | S-kqb3kad4, S-k62unlt6, S-fhqrcrzk, S-xgkshne3, S-yz335vyz, S-oh6erfbm |
- `arch/chef-infra-client-run.md` — when recipes are compiled and resources converged; `arch/chef-attributes-policyfiles.md` — attributes and what a Policyfile locks; `arch/chef-windows-nodes.md` — the Windows resources.

## Examples
- SNIPPET: a service that restarts when its configuration file changes, with the default delayed timer; context: Chef Infra Client 19, `windows_service` and `template` resources, names are placeholders; checked: no [DOC S-gwzouzk5: `notifies` syntax with a timer]
```
template 'C:\ProgramData\example\app.conf' do
  source 'app.conf.erb'
  notifies :restart, 'windows_service[ExampleApp]', :delayed
end

windows_service 'ExampleApp' do
  action :nothing
end
```
