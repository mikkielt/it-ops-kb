---
topic: arch/chef-windows-nodes
priority: P3
applies_to: "Chef Infra Client 19 on Windows (docs.chef.io Chef Infra Client 19 pages; source at chef/chef commit 9322fa4): install, elevation, scheduling, bootstrap and the Windows-specific resources"
retrieved_utc: 2026-10-15
sources: [S-3x3s2jec, S-ejunjyza, S-mqmjglrs, S-yz335vyz, S-arkeshhj, S-xw5o3wsc, S-6guysc4r, S-oh6erfbm, S-xgkshne3, S-zskepmir, S-yddwaulv, S-z5kgh6p7, S-ddprubpp, S-og5svrch, S-qdnvehti]
status: partial
---

# Chef Infra Client on Windows nodes

## Summary
Chef Infra Client on Windows is installed by bootstrap over WinRM, by the MSI, or by an existing deployment tool such as System Center. It has no daemon mode: the MSI can register a scheduled task, and a run without administrator rights only warns unless the fatal check is on. The documentation lists more than 40 Windows-specific resources (package, service, feature, registry, DSC, PowerShell, scheduled task and others) and says the common file, directory, service, user and group resources work the same as on Unix. Each Windows resource has its own limits: `windows_package` matches on the installer's DisplayName, `windows_service` rejects `:reload`, and `dsc_resource` cannot use composite DSC resources.

## Facts
- Chef Infra Client is installed on Windows by bootstrapping from a workstation with `knife bootstrap` over WinRM, by running the MSI on the node, or by an existing process such as System Center. [DOC S-3x3s2jec]
- `knife bootstrap` opens an SSH or WinRM connection and runs the bootstrap script; on Windows a batch file derived from the `windows-chef-client-msi.erb` template starts `chef-client` with a `first-boot.json` file. [DOC S-zskepmir]
- A node can also be bootstrapped by an unattended install from the node itself, which needs neither SSH nor WinRM. [DOC S-zskepmir]
- `knife windows` talks to Windows nodes over WinRM with NTLM or Kerberos authentication, and WinRM needs the HTTP or HTTPS ports the target is configured for. [DOC S-3x3s2jec]
- The default bootstrap installs the MSI with `msiexec /qn /i <path>`; the `ADDLOCAL` options are `ChefClientFeature`, `ChefSchTaskFeature` (configure the client as a scheduled task) and `ChefPSModuleFeature` (the `chef` PowerShell module). [DOC S-3x3s2jec]
- The scheduled task can also be created after install with `SCHTASKS.EXE`; the documentation's example runs every 30 minutes as `System`, and the default log file after enabling it is `c:\chef\chef-client.log`. [DOC S-3x3s2jec]
- Supported Windows versions in the page's table are x64 Windows 10 and 11 and Server 2016, 2019 and 2022; the recommended minimum RAM during a run is 512 MB and nodes need HTTPS access to the server. [DOC S-3x3s2jec]
- The same page names two install locations, `C:\opscode` and `C:\hab`, with the main configuration file at `C:\chef\client.rb`. [DOC S-3x3s2jec]
- The 19.3.15 release notes say Habitat-related paths follow `SYSTEMDRIVE` (for example `D:\hab`) while Omnibus-related paths stay hardcoded to `C:\opscode`. [DOC S-qdnvehti]
- Which Chef Infra Client 19 distribution installs under which of the two roots is not stated on the pages read. [UNK]
- 19.3.15 fixed an issue where Chef Infra Client 19 could not be installed on a Windows drive other than `C:`, and Windows supports a direct upgrade to 19.3.15 from every earlier 19.x. [DOC S-qdnvehti]
- Running without elevation can fail silently on Windows: the run looks successful but the changes were not made, so the client should run as administrator (an account in the Administrators group is not enough: log in as the administrator account or use a run-as). [DOC S-3x3s2jec]
- The source checks administrator privileges on Windows after building the node and before setting up the run context, and only logs a warning that unexpected resource failures may follow; with `fatal_windows_admin_check` on (`-A` / `--fatal-windows-admin-check`) it raises `WindowsNotAdmin`. [CODE S-z5kgh6p7: lib/chef/client.rb#L929-L941]
- The `fatal_windows_admin_check` setting defaults to false. [CODE S-og5svrch: chef-config/lib/chef-config/config.rb#L963]
- Directories used by Chef products on Windows cannot have spaces, a short top-level directory such as `C:\chef` avoids path length errors, and `http_proxy` / `https_proxy` must be lowercase system variables. [DOC S-3x3s2jec]
- The PATH needs `C:\opscode\chef\bin` and `C:\opscode\chef\embedded\bin` (the page says the installer adds them). [DOC S-3x3s2jec]
- A set `interval` on Windows is a fatal error in the source (`Chef::Application.fatal!` with a Windows-specific message), so `-i` / `--interval` cannot drive repeated runs there. [CODE S-ddprubpp: lib/chef/application/client.rb#L162-L168]
- The documentation states `--daemonize` is a UNIX and Linux option and points Windows to the service recipe of the `chef-client` cookbook, which installs a service with the Windows Service Wrapper. [DOC S-yddwaulv]
- In knife on Windows a quoted string needs single quotes at `cmd.exe` and triple single quotes in PowerShell; `Import-Module chef` (installed with the MSI feature, not enabled by default) removes the triple quotes. [DOC S-zskepmir]
- The Chef Infra Language has Windows helpers since 15.8: `windows_server_core?`, `windows_workstation?`, `windows_server?`, `windows_nt_version` and `powershell_version`. [DOC S-ejunjyza]
- The Windows-specific resources the documentation lists include `cab_package`, `chocolatey_*` (config, feature, package, source), `dsc_resource`, `dsc_script`, `msu_package`, `powershell_package`, `powershell_script`, `registry_key`, `windows_ad_join`, `windows_audit_policy`, `windows_certificate`, `windows_defender`, `windows_dns_record`, `windows_env`, `windows_feature`, `windows_firewall_rule`, `windows_package`, `windows_path`, `windows_security_policy`, `windows_service`, `windows_task`, `windows_user_privilege` and `chef_client_scheduled_task`. [DOC S-3x3s2jec]
- `cookbook_file`, `directory`, `execute`, `file`, `group`, `http_request`, `link`, `mount`, `package`, `remote_directory`, `remote_file`, `ruby_block`, `service`, `template` and `user` work the same as on Unix; the file-based ones add `inherits`, `mode` (octal) and `rights` (ACLs). [DOC S-3x3s2jec]
- `windows_package` installs MSI, NSIS, Inno Setup, Wise, InstallShield and custom installers, and its default action is `:install`; `:remove` is the other action. [DOC S-mqmjglrs]
- For idempotence of `:install`, and for `:remove` with no `source`, `package_name` must equal the installer's display name, as in Add/Remove Programs or the `DisplayName` value under the registry's `Uninstall` keys; several installed versions of one display name are all removed unless `version` is given. [DOC S-mqmjglrs]
- `windows_package` accepts return codes `0` and `3010` (success with a reboot necessary) by default, has a 600-second default timeout, and its `checksum` (SHA-256) avoids a repeated download; the `package` resource is advised where cross-platform recipes are wanted. [DOC S-mqmjglrs]
- `windows_service` defaults to `:nothing`; its actions include `:create`, `:configure`, `:configure_startup`, `:delete`, `:enable`, `:disable`, `:start`, `:stop` and `:restart`, and `:reload` is not supported on Windows and raises an error. [DOC S-yz335vyz]
- `windows_service` runs as `localsystem` by default, starts `:automatic` (with `delayed_start` available for automatic only), and `binary_path_name` is required for `:create` and `:configure`. [DOC S-yz335vyz]
- `windows_feature` defaults to the DISM installer (`install_method :windows_feature_dism`; PowerShell is the other method), with `:install` as the default action, a 600-second timeout and `management_tools` valid only for the PowerShell method. [DOC S-xgkshne3]
- The same feature can carry different names per method (`DHCPServer` for DISM, `DHCP` for PowerShell), so `feature_name` must match the method. [DOC S-xgkshne3]
- `powershell_script` writes the code to a temporary file and runs it, which the documentation says is by nature not idempotent, so `not_if` / `only_if` must guard it; `interpreter` is `powershell` or `pwsh` (PowerShell Core, since 16.6) and `timeout` defaults to 3600 seconds. [DOC S-arkeshhj]
- `powershell_script` guards are evaluated by the 64-bit PowerShell by default (`guard_interpreter :powershell_script`), and `elevated true` runs the script under a batch login, which needs `user` and `password` and the "Log on as a batch job" right. [DOC S-arkeshhj]
- `registry_key` creates and deletes keys and values, with value types `:binary`, `:string`, `:multi_string`, `:expand_string`, `:dword`, `:dword_big_endian` and `:qword`; `:multi_string` must be an array, `architecture` defaults to the machine's, and `:delete_key` with `recursive` cannot be undone by the client. [DOC S-6guysc4r]
- In a double-quoted Ruby string a registry path needs doubled backslashes; a single-quoted string takes single backslashes. [DOC S-6guysc4r]
- Language helpers `registry_key_exists?`, `registry_value_exists?`, `registry_data_exists?`, `registry_get_values`, `registry_get_subkeys` and `registry_has_subkeys?` test the registry in guards. [DOC S-6guysc4r]
- `dsc_resource` runs any binary- or script-based DSC resource through PowerShell with WMF 5.0 or higher, but composite DSC resources cannot be used; `reboot_action` defaults to `:nothing` and may be `:reboot_now` or `:request_reboot`. [DOC S-xw5o3wsc]
- The `reboot` resource is supported on Windows, macOS and Linux with actions `:reboot_now`, `:request_reboot` (end of run), `:cancel` and the default `:nothing`; notifications to it should be immediate. [DOC S-oh6erfbm]
- How it fits: on Windows the unattended path is the scheduled task running as `System`, so the account that applies cookbooks is a local administrator-level identity on every node; the client key and the licence key stay on the node and never belong in a cookbook, and a `powershell_script` that needs another user takes a `password` property, which the resource marks sensitive. [DER S-3x3s2jec, S-arkeshhj: scheduled task as System; `password` sets `sensitive`; kb frame: secrets never in repositories or argv]
- How it fits: where a stack has chosen DSC v3 as its declared source of truth, Chef can still carry DSC resources through `dsc_resource`, but composite resources are excluded, so a Chef-over-DSC arrangement is limited to binary and script resources; see `dsc/what-if.md` for DSC's own read-only check. [DER S-xw5o3wsc: composite resources not usable; kb frame: DSC v3 as source of truth]

## Reference
| need | where | source |
|---|---|---|
| install paths, MSI features, scheduled task, elevation, proxies | Chef for Windows | S-3x3s2jec |
| Windows helpers in recipes | Chef Infra Language: Windows | S-ejunjyza |
| bootstrap stages, knife quoting | About Run-lists | S-zskepmir |
| options (interval, daemonize) | chef-client reference | S-yddwaulv |
| administrator check, interval handling, defaults | `lib/chef/client.rb`, `lib/chef/application/client.rb`, `chef-config/lib/chef-config/config.rb` | S-z5kgh6p7, S-ddprubpp, S-og5svrch |
| resources | `windows_package`, `windows_service`, `windows_feature`, `powershell_script`, `registry_key`, `dsc_resource`, `reboot` pages | S-mqmjglrs, S-yz335vyz, S-xgkshne3, S-arkeshhj, S-6guysc4r, S-xw5o3wsc, S-oh6erfbm |
| install-path release note | Chef Infra Client release notes | S-qdnvehti |
- `arch/chef-infra-client-run.md`, `arch/chef-cookbooks-recipes-resources.md`, `arch/chef-attributes-policyfiles.md` — the rest of the Chef area.
- `arch/puppet-windows-nodes.md` — the same questions for Puppet; `ansible/dsc3-module.md` and `dsc/what-if.md` — the DSC side.

## Examples
- SNIPPET: install an MSI that is already on a share and register the scheduled task at install; context: Chef Infra Client 19 MSI, run in an elevated prompt, path is a placeholder; checked: no [DOC S-3x3s2jec: `msiexec /qn /i`, `ADDLOCAL`]
```
msiexec /qn /i \\PL-SRV-0042\packages\chef-client.msi ADDLOCAL="ChefClientFeature,ChefSchTaskFeature"
```
- SNIPPET: a Windows service that is configured but left stopped until notified; context: Chef Infra Client 19, service name is a placeholder; checked: no [DOC S-yz335vyz: `:configure_startup`, `startup_type`, `delayed_start`]
```
windows_service 'ExampleApp' do
  startup_type :automatic
  delayed_start true
  action :configure_startup
end
```
