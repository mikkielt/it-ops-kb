---
topic: arch/puppet-language-resources-types
priority: P3
applies_to: "Puppet 8.x manifest language (Puppet Core 8.22.0 docs; reference files at commit e227c27): resource declarations, titles and namevars, ordering and relationships, metaparameters, classes, built-in and removed resource types"
retrieved_utc: 2026-10-15
sources: [S-3nlx3lke, S-4dquzyfj, S-kletprvx, S-w5xtdsyr, S-ef4b5npw, S-2xntzgfj, S-cttzm2qq, S-se4kjnw2]
status: partial
---

# Puppet manifest language: resources, types, ordering and classes

## Summary
A Puppet manifest declares resources (a type, a title, attributes); the agent compares each resource's actual state with the declared one and changes only what differs. Unrelated resources are applied in manifest order; explicit relationships (`before`, `require`, `notify`, `subscribe`, chaining arrows) override that order and also carry refresh events. Classes group resources and are singletons per compilation. Since Puppet 6.0 several built-in types live in modules, some of them bundled in the `puppet-agent` package. A resource Puppet is no longer told about is left alone, never removed.

## Facts
- A resource declaration has at least a resource type, a title and a set of attributes (`<TYPE> { '<TITLE>': <ATTRIBUTE> => <VALUE> }`); the title and attributes are the resource body, and one declaration may hold several bodies of the same type separated by semicolons. [DOC S-3nlx3lke]
- Applying a resource means reading its actual state, comparing it with the desired state, changing the system if necessary and logging the change in the agent's log and in the run report. [DOC S-3nlx3lke]
- Puppet does nothing with a resource that is not in the catalog: removing a `package` resource from a manifest does not uninstall the package, which needs `ensure => absent`. [DOC S-3nlx3lke]
- A resource must be unique: Puppet identifies duplicates by title and by the namevar (usually `name`), and a repeated title or name within one resource type fails catalog compilation. [DOC S-3nlx3lke]
- The title identifies the resource to Puppet and the namevar identifies it to the target system; the namevar defaults to the title, and a type with several namevars states how the title maps to them (for `package` the `provider` attribute takes part in uniqueness). [DOC S-3nlx3lke]
- An attribute without a default is required; most resource types have `ensure` for the basic state (file present, service running, package installed), and its accepted values vary by type. [DOC S-3nlx3lke]
- A property corresponds to something measurable on the target system, while a parameter only changes how Puppet manages the resource. [DOC S-3nlx3lke]
- Defined types are lightweight resource types written in the Puppet language; custom resource types are written in Ruby and have the capabilities of built-in types. [DOC S-3nlx3lke]
- Unrelated resources are applied in the order they are written in the manifest; the language documentation says the `ordering` setting customises this order. [DOC S-3nlx3lke]
- The `ordering` setting is not defined in the configuration reference or in `lib/puppet/defaults.rb` at the pinned commit, where the word occurs only in the deferred-function setting; the two sources disagree and the conflict is recorded. [DER S-cttzm2qq, S-se4kjnw2: searched both for `ordering`]
- An explicit relationship overrides the default manifest order, and a relationship may be declared before the resource it names has been declared. [DOC S-4dquzyfj]
- Refresh: a resource that changes sends a refresh event to the resources that subscribe to it (`notify`, `subscribe`, or the `~>` chaining arrow); the built-in types that can refresh are `service`, `exec` and `package`, a resource refreshes at most once per run however many events it gets, and a class or defined resource passes a received refresh event to everything it contains. [DOC S-4dquzyfj]
- Automatic relationships (`autorequire`, `autonotify`, `autobefore`, `autosubscribe`) order some types against others without being stated, and an explicit relationship wins where it conflicts with an automatic one. [DOC S-4dquzyfj]
- A relationship to a resource that is never declared fails compilation; a resource whose prerequisite failed is skipped (and so are resources depending on it) while unrelated resources are still applied; a dependency cycle compiles but cannot be applied. [DOC S-4dquzyfj]
- The metaparameters in the reference at the pinned commit are `alias`, `audit`, `before`, `loglevel`, `noop`, `notify`, `require`, `schedule`, `stage`, `subscribe` and `tag`. [DOC S-w5xtdsyr]
- `audit` marks unmanaged attributes (or `all`) whose change since the previous run is logged next to the actions Puppet took; a managed and audited attribute edited by hand logs an audit notice in two consecutive runs, the edit and then the revert. [DOC S-w5xtdsyr]
- `schedule` names a `schedule` resource that governs when Puppet may manage the resource; the schedule can be declared anywhere in the manifests as long as it ends up in the compiled catalog. [DOC S-w5xtdsyr]
- `stage` works only on classes declared with the resource-like syntax (not on ordinary resources or on `include`); all classes are in the `main` stage unless a `stage` resource is declared and ordered against `main`. [DOC S-w5xtdsyr]
- Classes are singletons: a class's resources are evaluated once per compilation however often it is declared. [DOC S-kletprvx]
- Class declarations are include-like (`include`, `require`, `contain`; flexible and idempotent) or resource-like (needed to pass parameters without Hiera), and the two styles must not be mixed for one class because that can fail compilation. [DOC S-kletprvx]
- With an include-like declaration each parameter is looked up in the external data source as `<class name>::<parameter name>`, then falls back to the parameter's default, then fails compilation if neither exists. [DOC S-kletprvx]
- `include` only adds a class to the catalog and does not make it contained by the class that includes it; `contain` is the function for containment. [DOC S-kletprvx]
- The Core 8 resource-types section has pages for `exec`, `file`, `filebucket`, `group`, `notify`, `package`, `resources`, `schedule`, `service`, `stage`, `tidy` and `user`. [DOC S-2xntzgfj]
- Puppet 6.0 removed a set of built-in types into modules; `augeas`, `cron`, `host`, `mount`, `scheduled_task`, `selboolean`, `selmodule`, `ssh_authorized_key`, `sshkey`, `yumrepo`, `zfs`, `zone` and `zpool` are supported modules that the `puppet-agent` package also carries. [DOC S-ef4b5npw]
- `k5login`, `mailalias` and `maillist` are maintained modules that are not repackaged in the agent and must be installed separately; `computer`, `interface`, `macauthorization`, `mcx`, the Nagios types, `router` and `vlan` were deprecated in 6.0.0 and are no longer updated. [DOC S-ef4b5npw]
- A provider implements a type on a kind of system and Puppet picks a default one; the `provider` attribute overrides it, and a provider may support only some of a type's features (for example `ensure => purged` needs the `purgeable` feature). [DOC S-ef4b5npw]
- The `service` type's `enable` property accepts `true`, `false`, `manual`, `mask` and `delayed` (it requires the `enableable` feature), and leaving it out leaves the boot behaviour to the operating system. [DOC S-ef4b5npw]
- How it fits: because an omitted resource is ignored and not removed, a Puppet catalog is a statement of what to enforce, not a full inventory; drift in anything the catalog does not name is invisible to a noop run. [DER S-3nlx3lke, S-cttzm2qq: unmanaged resources are not touched; noop checks only catalog resources]

## Reference
| need | where | source |
|---|---|---|
| resource syntax, uniqueness, titles | resources page | S-3nlx3lke |
| ordering, refresh, automatic relationships | relationships page | S-4dquzyfj |
| metaparameters | metaparameter reference | S-w5xtdsyr |
| class declaration styles | declaring classes page | S-kletprvx |
| built-in and moved types | type reference, Puppet 6.0 type changes | S-ef4b5npw |
- `arch/puppet-agent-run-noop-reporting.md` — what the agent does with the catalog and noop; `arch/puppet-modules-facts-hiera.md` — where classes and types live and how parameters get data; `arch/puppet-windows-nodes.md` — the Windows-specific types.

## Examples
- SNIPPET: package, file and service in a chain where a config change restarts the service; context: Puppet 8, resource names are placeholders; checked: no [DOC S-4dquzyfj: chaining arrows `->` and `~>` as the relationships page defines them]
```
Package['ntp'] -> File['/etc/ntp.conf'] ~> Service['ntpd']
```
