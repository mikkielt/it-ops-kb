---
topic: arch/puppet-windows-nodes
priority: P3
applies_to: "Puppet 8.x agent on Windows (Puppet Core 8.22.0 docs; type reference at commit e227c27): agent service, default paths, path and line-ending rules, and the Windows behaviour and limits of exec, file, package, service, user and group"
retrieved_utc: 2026-10-15
sources: [S-dk5ixeab, S-i7ihql2k, S-wgecldol, S-eutggisu, S-hrrqkjbi, S-syu6rsv6, S-6gagioik, S-cttzm2qq, S-ef4b5npw, S-b4kil6ln]
status: partial
---

# Puppet on Windows nodes

## Summary
The Puppet installer sets the agent up as a Windows service that runs a catalog every 30 minutes. Core Puppet has built-in `file`, `exec`, `package`, `service`, `user` and `group` types that work on Windows, each with limits: no shell provider, MSI or EXE installers only, local accounts only, `mode` translated to approximate ACLs. Registry, ACL, reboot, DISM and PowerShell exec support are separate Forge modules, and `scheduled_task` ships as a module inside the agent package. Paths, slashes and line endings need care.

## Facts
- The Puppet installer configures the agent to run as a Windows service and starts it; the service defaults to a configuration run every 30 minutes, set with `runinterval` in `puppet.conf`. [DOC S-dk5ixeab]
- After a `runinterval` change the next run still happens on the previous schedule and later runs follow the new one. [DOC S-dk5ixeab]
- The service defaults to starting automatically; the `PUPPET_AGENT_STARTUP_MODE` MSI property sets this at install, and afterwards the Service Control Manager or `sc.exe` can; `sc config puppet start= demand` needs the space after `start=` and works from `cmd.exe`, not PowerShell. [DOC S-dk5ixeab]
- Flags for the service's runs are added to the `sc start puppet` call, for example `--debug --logdest eventlog` to change what is written to the Event Log. [DOC S-dk5ixeab]
- On Windows the defaults are `C:\ProgramData\PuppetLabs\code` for `codedir`, `C:\ProgramData\PuppetLabs\puppet\etc` for `confdir`, `...\puppet\var\log` for `logdir`, `...\puppet\cache` for `vardir`, `...\puppet\var\run` for `rundir` and `...\puppet\public` for `publicdir`. [DOC S-cttzm2qq]
- Where Puppet itself interprets a path, or the path is meant for the primary server, forward slashes are used; paths passed directly to a Windows program take backslashes. [DOC S-i7ihql2k]
- Template paths and `puppet:///` URLs take forward slashes; a `file` path or title, a `package` `source`, a local `source` and an `exec` command accept either, though some executables such as `cmd.exe` need backslashes. [DOC S-i7ihql2k]
- Paths inside the `command` of a `scheduled_task`, inside `install_options` of a `package`, and in resources for PowerShell DSC must use backslashes, and DSC resources are advised to use single-quoted strings. [DOC S-i7ihql2k]
- Windows uses CRLF line endings and Puppet usually does not convert them: `content` and `source` are written in binary mode with the endings present in the text, so `\r\n` must be part of `content` to get CRLF. [DOC S-i7ihql2k]
- Types that edit part of a system file (`host`, for `%windir%\system32\drivers\etc\hosts`) work in text mode and translate between Windows and Unix line endings. [DOC S-i7ihql2k]
- The Core 8 documentation lists these Windows modules as the important optional resource types: `puppetlabs/acl`, `puppetlabs/registry`, `puppetlabs/reboot`, `puppetlabs/dism` (enable and disable Windows features) and `puppetlabs/powershell` (an exec provider that runs PowerShell directly). [DOC S-wgecldol]
- Plugins from the Forge may not have the same quality assurance and test coverage as the core resource types. [DOC S-wgecldol]
- `exec` on Windows runs binaries (exe, com, bat) and logs output and exit status; for idempotence one of `creates`, `onlyif` or `unless` should be given. [DOC S-hrrqkjbi]
- A command without an extension is resolved through the `PATHEXT` environment variable. [DOC S-hrrqkjbi]
- Windows has no shell provider for `exec`, so a shell built-in such as `echo` needs a full `cmd.exe /c ...` command, and a path inside such a `cmd.exe` command must use backslashes or `cmd.exe` returns an error. [DOC S-hrrqkjbi]
- Puppet uses the `GetExitCodeProcess` API and reports a large positive exit code where `cmd.exe` shows a negative one; a negative code is converted by subtracting it from 4294967296, and Microsoft's advice is to avoid negative or very large exit codes. [DOC S-hrrqkjbi]
- A PowerShell script run through the default `exec` provider needs the `remotesigned` execution policy on the `powershell.exe` call. [DOC S-hrrqkjbi]
- For `file`, Puppet needs the privileges to create symbolic links and to back up and restore files; when Puppet runs as a service its account must be in the local Administrators group, and an interactive run needs an elevated prompt. [DOC S-eutggisu]
- NTFS is case-insensitive but case-preserving while Puppet is case-sensitive, so one file name must be capitalised the same way everywhere in a manifest or Puppet treats the spellings as different files. [DOC S-eutggisu]
- `mode` on Windows is translated to roughly equivalent access controls (read, write, execute as `FILE_GENERIC_READ`, `FILE_GENERIC_WRITE`, `FILE_GENERIC_EXECUTE`; the Everyone SID for "other"), which cannot express complex access rules; fine-grained control uses the `puppetlabs/acl` module with `mode` left out. [DOC S-eutggisu]
- Managing permissions with `mode` always gives the owner `FULL_CONTROL` and marks the security descriptor protected, which stops the file inheriting more permissive entries from its directory; the group cannot exceed the owner and others cannot exceed either, so `0640` and `0755` work and `0460` does not. [DOC S-eutggisu]
- A `file` `source` on Windows can be a Puppet URL, a local path, a UNC path or a mapped-drive path. [DOC S-eutggisu]
- The `windows` package provider installs and removes MSI packages and EXE installers, and a Chocolatey provider is available from the Forge. [DOC S-syu6rsv6]
- With the `windows` provider the `source` attribute is required, can be a local file, a mapped drive, or (for MSI) a UNC path, and cannot be a Puppet URL; a `file` resource can copy the package first. [DOC S-syu6rsv6]
- The package title must match the `DisplayName` property in the registry (as shown in Programs and Features), or Puppet assumes the package is not installed; `puppet resource package` lists the names. [DOC S-syu6rsv6]
- `ensure => latest` does not work on Windows because there is no central package repository, so versions and upgrades are handled by setting an explicit version. [DOC S-syu6rsv6]
- `install_options` takes MSI `property=value` strings or executable flags, one string per item, split on every space; file paths inside it need backslashes. [DOC S-syu6rsv6]
- The `windows` service provider uses the Service Control Manager: it can start, stop, enable and disable services, and its documentation says control of service groups (dependencies) and running a service as a specific user are not supported, while its feature list includes `manages_logon_credentials`, `delayed_startable` and `manual_startable`. [DOC S-ef4b5npw]
- `user` and `group` manage local accounts only: no resource can describe a domain user or group, although a local group's `members` can list domain accounts. [DOC S-6gagioik]
- By default a managed user is added to the listed groups and left in others; `membership => inclusive` on the user, or `auth_membership` on a group, removes the extras. [DOC S-6gagioik]
- On Windows `gid` cannot be used on a user and passwords must be given in cleartext because Windows has no API for setting a password hash; a user's `uid` and a group's `gid` are read-only and hold the account's SID. [DOC S-6gagioik]
- Account names are case-sensitive in manifests and case-insensitive on Windows; Puppet compares names in canonical SID form, and `autorequire` can miss a match when a domain and a local account share a name (`Domain\Bob`, `LOCAL\Bob`). [DOC S-6gagioik]
- The `scheduled_task` type is one of those moved out of core in 6.0 and bundled in the `puppet-agent` package. [DOC S-ef4b5npw]
- Windows external facts live in `C:\ProgramData\PuppetLabs\facter\facts.d\`. [DOC S-b4kil6ln]
- How it fits: manifests that set a user password hold it in cleartext, so a manifest in a repository would carry a secret; the kb's rule that secrets never sit in code or argv means the value has to come from a store resolved at run time, outside the manifest text. [DER S-6gagioik: passwords must be cleartext on Windows; kb frame: secrets never in repositories]
- How it fits: Puppet enforces through its own agent service, which needs an administrator-level account on every node, and it brings its own catalog model; a stack that has already chosen DSC v3 as its declared source of truth keeps DSC for read-only drift and treats Puppet noop as prior art, as `reuse/drift-detection.md` concludes. [DER S-dk5ixeab, S-eutggisu: agent service with Administrators membership; `reuse/drift-detection.md` verdict]

## Reference
| need | where | source |
|---|---|---|
| agent service and run interval | Running Puppet agent as a service | S-dk5ixeab |
| default directories | configuration reference | S-cttzm2qq |
| slashes and line endings | Files and paths on Windows | S-i7ihql2k |
| optional Windows types | Optional resource types for Windows | S-wgecldol |
| exec, file, package, user and group | the four "Using ... on Windows" pages | S-hrrqkjbi, S-eutggisu, S-syu6rsv6, S-6gagioik |
| service provider, moved types | type reference | S-ef4b5npw |
- `arch/puppet-agent-run-noop-reporting.md`, `arch/puppet-language-resources-types.md`, `arch/puppet-modules-facts-hiera.md` — the rest of the Puppet area.
- `ansible/dsc3-module.md` and `dsc/what-if.md` — the DSC side of the same Windows configuration.

## Examples
- SNIPPET: set the agent service to manual start from a command prompt; context: Windows agent, run in `cmd.exe` as an administrator; checked: no [DOC S-dk5ixeab: `sc config puppet start= demand`]
```
sc config puppet start= demand
```
- SNIPPET: install an MSI from a mapped share; context: Windows agent, the share path is a placeholder; checked: no [DOC S-syu6rsv6: `windows` provider, required `source`, package title equal to the DisplayName]
```
package { 'Example Tool':
  ensure => installed,
  source => '\\\\pl-srv-0042\\packages\\example-tool.msi',
}
```
