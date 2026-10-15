---
topic: arch/puppet-modules-facts-hiera
priority: P3
applies_to: "Puppet 8.x (Puppet Core 8.22.0 docs): module directory layout, facts (core, custom, external, trusted), Hiera lookup and automatic class parameter lookup"
retrieved_utc: 2026-10-15
sources: [S-v2maahna, S-4wyybawt, S-xzxlvtze, S-b4kil6ln, S-qskusgjk, S-gllyiwia, S-42nnv5q2, S-cttzm2qq, S-uqxc7z4f]
status: partial
---

# Puppet modules, facts and Hiera

## Summary
A module is a fixed directory layout Puppet scans for classes, defined types, facts, custom types and providers, functions, tasks and plans. Facts reach manifests as the `$facts` hash (self-reported by the node) beside `$trusted` (taken from the node's certificate). Class parameters get their data from Hiera by the key `<class>::<parameter>`; Hiera searches a global, an environment and a module layer in that order and, unless told otherwise, the first value found wins.

## Facts
- A module's directories are `manifests/`, `files/`, `templates/`, `lib/`, `facts.d/`, `functions/`, `types/`, `data/`, `examples/`, `locales/`, `plans/`, `tasks/`, `spec/` and `readmes/`; the page says not all are required. [DOC S-v2maahna]
- A module name matches `[a-z][a-z0-9_]*`: lowercase letters, digits and underscores, starting with a letter, with no `::` because modules cannot be nested. [DOC S-v2maahna]
- Each manifest in `manifests/` holds one class or defined type; `init.pp` is the module's main class, referred to by the module name alone and named the same as the module, and `manifests/implementation/my_defined_type.pp` is named `my_module::implementation::my_defined_type`. [DOC S-v2maahna]
- Files under `files/` are served at `puppet:///modules/<module>/<file>` and are readable with the `file` function; templates under `templates/` are rendered with `template('my_module/component.erb')` or `epp('my_module/component.epp')`. [DOC S-v2maahna]
- `lib/` holds plug-ins (custom facts under `facter/`, functions, types and providers under `puppet/`); it is used by the server and the agent and is synced to all agent nodes in the environment on each Puppet run. [DOC S-v2maahna]
- A module's `facts.d/` holds external facts, which are synced to agent nodes so they can submit those fact values to the server. [DOC S-v2maahna]
- Puppet collects facts with Facter before requesting a catalog or compiling one with `puppet apply`; manifests read them as `$facts['fact_name']`, and Puppet keeps Boolean, numeric and structured facts as their own types instead of converting them to strings. [DOC S-4wyybawt]
- The facts Puppet code can read are Facter's core facts plus custom and external facts present in modules; `facter -p` on the command line shows a node's values. [DOC S-4wyybawt]
- `number_of_facts_soft_limit` (default `10240`) is the soft limit on the total number of fact values, counting the child elements of arrays and hashes, not only top-level facts. [DOC S-cttzm2qq]
- An executable external fact on Unix always needs a shebang line (or it fails to run), and a script should return key-value pairs, JSON or YAML; Facter falls back to key-value parsing when the output is not YAML. [DOC S-b4kil6ln]
- On Windows, external fact executables must carry a known extension (`.com` and `.exe` binaries, `.ps1` PowerShell, and batch scripts), line endings may be LF or CRLF, and a batch file's encoding must be ANSI or UTF-8 without a BOM. [DOC S-b4kil6ln]
- External fact directories are `/opt/puppetlabs/facter/facts.d/`, `/etc/puppetlabs/facter/facts.d/` and `/etc/facter/facts.d/` on Unix, `C:\ProgramData\PuppetLabs\facter\facts.d\` on Windows, and `<HOME DIRECTORY>/.facter/facts.d/` for a non-root or non-Administrator user. [DOC S-b4kil6ln]
- Normal facts are self-reported by the node and nothing guarantees them; `$trusted` holds data from the node's certificate (the name `$trusted` is reserved, `$trusted['certname']` is the verified certificate name), and the page lists server facts as trusted values a client-side fact could otherwise overwrite. [DOC S-xzxlvtze]
- The `lookup` function returns the first value found and fails compilation when there is none, unless a merge behaviour is given or set in the data; it checks up to four layers: global, the current environment, the module (for keys of the form `<MODULE NAME>::<SOMETHING>`), and a module `default_hierarchy` if the earlier steps found nothing. [DOC S-qskusgjk]
- When no global `hiera.yaml` is configured, built-in Hiera defaults apply, and the default global file is installed at `/etc/puppetlabs/puppet/hiera.yaml`. [DOC S-qskusgjk]
- A `lookup` call can give a value type (a mismatch fails the lookup and the compilation), a merge behaviour that overrides the data's own, a default that is never merged with found values, and an `override` hash that is checked first and ignores merging. [DOC S-qskusgjk]
- A data source can set a merge behaviour for a key with the `lookup_options` metadata key, which `lookup` uses unless the call specifies one; the older `hiera()` call still works but is marked deprecated in favour of `lookup`. [DOC S-qskusgjk]
- The hierarchy in `hiera.yaml` is an ordered list of data sources searched in the order written, with higher-priority sources overriding lower ones, and most levels use variables to pick a source so different nodes get different data. [DOC S-42nnv5q2]
- Puppet fills a class's parameters in this order: values set explicitly in a resource-like declaration, then Hiera under the key `<CLASS NAME>::<PARAMETER NAME>`, then the parameter's default expression; a parameter with none of these fails compilation. [DOC S-gllyiwia]
- Automatic parameter lookup uses the `first` merge method and the page says that default cannot be changed, so a deep merge for a class parameter key needs `lookup_options`. [DOC S-gllyiwia]
- The class-parameters page names roles and profiles as the best way to keep a smaller amount of more meaningful data in Hiera. [DOC S-gllyiwia]
- How it fits: on a managed Windows fleet the same `$facts` and `$trusted` split matters for access decisions: a manifest or Hiera hierarchy level that trusts a self-reported fact (`$facts['hostname']`) for what a node may receive can be steered by the node, while one keyed on `$trusted['certname']` or a certificate extension cannot. [DER S-xzxlvtze, S-uqxc7z4f: facts are self-reported, trusted facts come from the certificate; facts are sent in the catalog request]

## Reference
| need | where | source |
|---|---|---|
| module tree and names | module structure page | S-v2maahna |
| facts in manifests, trusted and server facts | facts pages | S-4wyybawt, S-xzxlvtze |
| executable and structured external facts, directories | external facts page | S-b4kil6ln |
| lookup arguments, layers, merge | lookup page | S-qskusgjk |
| hierarchy and class parameter keys | hierarchy and class parameters pages | S-42nnv5q2, S-gllyiwia |
- `arch/puppet-agent-run-noop-reporting.md` — how facts and plugins travel in a run; `arch/puppet-language-resources-types.md` — class declaration styles; `arch/puppet-windows-nodes.md` — Windows paths.

## Examples
- SNIPPET: data for the `ntp` class's `servers` parameter in a node-level Hiera file; context: Puppet 8, node name is a placeholder; checked: no [DOC S-gllyiwia: key `ntp::servers` as the class-parameters page shows it]
```yaml
# nodes/pl-srv-0042.corp.example.com.yaml, under the environment's data directory
ntp::servers:
  - time.corp.example.com
```
