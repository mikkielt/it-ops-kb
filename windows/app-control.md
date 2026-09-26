---
topic: windows/app-control
priority: P2
applies_to: "Windows 10/11 clients, Windows Server 2016+ (feature availability varies by version; CiTool.exe requires Windows 11 22H2+ or Windows Server 2025)"
retrieved_utc: 2026-09-26
sources: [S-whvei7wr, S-k6lcrjix, S-bdcygezh, S-fq54pkea, S-wk4roik4, S-vawypjoe, S-ickvylma, S-frmf22fa, S-salso3t6, S2202, S-oartdvpr]
status: complete
---

# App Control for Business (WDAC) policy rules and AppLocker comparison

## Summary
- App Control for Business (formerly Device Guard / configurable code integrity) is a Windows code-integrity feature that decides which drivers and apps can run, based on signer, file attributes, path, ISG reputation or managed-installer origin. Smart App Control (`windows/smart-app-control.md`) is built entirely on it. [DOC S-frmf22fa]
- A policy XML has *policy rule options* (numbered switches such as audit mode, UMCI, managed installer, ISG) and *file rule levels* (Hash, Publisher, FilePath, etc.) that decide which files are trusted. The full policy rule option table (number, name, meaning, valid in supplemental policy, notes) is in `windows/app-control.csv`. [DOC S-whvei7wr]
- Since Windows 10 1903 / Windows Server 2022, multiple policies can run side by side: several base policies (intersection - a file must pass all of them) plus supplemental policies that expand one base policy (union - allowed by base OR supplemental). [DOC S-k6lcrjix]
- `CiTool.exe` (Windows 11 22H2+ / Windows Server 2025) manages policies and tokens locally: `--update-policy/-up`, `--remove-policy/-rp`, `--list-policies/-lp`, `--refresh/-r`, token commands, `--device-id/-id`. [DOC S-bdcygezh]
- Managed installer and ISG are both heuristic, origin-based trust mechanisms layered on top of explicit allow/deny rules; explicit rules always win over both. [DOC S-vawypjoe, S-ickvylma]
- AppLocker (Windows 7+) is a defense-in-depth control, not a Microsoft-defensible security feature; Microsoft recommends App Control where robust protection is required, and AppLocker for mixed-OS fleets, per-user/group rules on shared devices, or as a complement to App Control. AppLocker also underlies App Control's managed-installer and ISG mechanisms. [DOC S-frmf22fa, S-fq54pkea]

## Facts
### Policy rule options and file rule levels
- Policy rule options are set with the `Set-RuleOption` PowerShell cmdlet or the App Control Policy Wizard; deleting `3 Enabled:Audit Mode` switches a policy from audit to enforced. [DOC S-whvei7wr]
- File rule levels (from most to least specific, roughly): Hash, FileName, FilePath (Windows 10 1903+, user-mode binaries only, can't allow kernel drivers), SignedVersion, Publisher, FilePublisher, LeafCertificate, PcaCertificate, RootCertificate (not supported), WHQL, WHQLPublisher, WHQLFilePublisher. `New-CIPolicy -Level <primary> -Fallback <level(s)>` sets the primary level and fallback(s) for files that can't be trusted at the primary level. [DOC S-whvei7wr]
- Signer-based rules only work with RSA signatures up to 4096 bits; ECC/ECDSA-signed files show `VerificationError = 23` on the corresponding 3089 event and must instead be allowed by hash, file attribute, or another signer rule against an RSA signature. [DOC S-whvei7wr]
- `-SpecificFileNameLevel` picks an alternate resource-header attribute (FileDescription, InternalName, OriginalFileName [default], PackageFamilyName, ProductName, Filepath) for FileName/FilePublisher/WHQLFilePublisher rules. [DOC S-whvei7wr]
- FilePath rule wildcards: `*` (zero or more chars, Windows 10/11+ or Server 2022+) and `?` (single char, Windows 11+ or Server 2025+ only); on Windows 11 multiple wildcards can appear anywhere in a path, on other versions only one wildcard is allowed and it must be at the start or end. Macros `%OSDRIVE%`, `%WINDIR%`, `%SYSTEM32%` can combine with wildcards. [DOC S-whvei7wr]
- App Control performs a runtime user-writeability check on FilePath rules against a fixed list of admin SIDs; `18 Disabled:Runtime FilePath Rule Protection` turns this check off. Configuration Manager's "specified files and folders" rules are a one-time scan, not true App Control FilePath rules. [DOC S-whvei7wr]
- File rule precedence: explicit deny rules first, then explicit allow rules, then a managed-installer claim (if allowed by the policy), then ISG (if allowed by the policy). [DOC S-whvei7wr]
- `New-CIPolicy` produces up to 4 hash values per file (SHA1/SHA256 Authenticode, SHA1/SHA256 first-page hash) and, when it can't determine whether a file only runs user-mode or kernel-mode, up to 8 hash rules (separate UMCI and KMCI rules). [DOC S-whvei7wr]

### Multiple and supplemental policies
- Without the update released on or after 2024-04-09, a device is limited to 32 active policies; that update removes the limit, except Windows 11 21H2 which stays capped at 32. [DOC S-k6lcrjix]
- `New-CIPolicy -MultiplePolicyFormat` generates a unique PolicyID and sets the policy as a base policy; a base policy needs `Set-RuleOption -Option 17` to allow supplemental policies, and (if signed) supplemental signers added via `Add-SignerRule -Supplemental`. [DOC S-k6lcrjix]
- A supplemental policy is created by taking a new Multiple Policy Format policy and running `Set-CIPolicyIdInfo -SupplementsBasePolicyID <GUID>` (or `-BasePolicyToSupplementPath <path>`) plus `-PolicyId`/`-PolicyName`. [DOC S-k6lcrjix]
- When merging policies, the merged policy's type and PolicyID come from the leftmost/first policy passed to the merge, regardless of the other policies' types or GUIDs. [DOC S-k6lcrjix]
- Binary policy files must be named `{PolicyGUID}.cip` matching the `<PolicyID>` in the XML, and are deployed locally by copying them into `C:\Windows\System32\CodeIntegrity\CiPolicies\Active` and rebooting; the ApplicationControl CSP (used by Intune) also supports rebootless deployment. GP and WMI do not support multiple policies directly; use the ApplicationControl CSP via the MDM Bridge WMI Provider instead. [DOC S-k6lcrjix]
- When an MDM enrollment is removed, the ApplicationControl CSP removes every active policy on the device, not just the ones it deployed, because the system does not track which method deployed which policy. [DOC S-k6lcrjix]

### CiTool
- `CiTool.exe` ships in Windows images starting with Windows 11 22H2 and Windows Server 2025. [DOC S-bdcygezh]
- Policy commands: `--update-policy </path> (-up)`, `--remove-policy <GUID> (-rp)`, `--list-policies (-lp)`. Token commands: `--add-token <path> [--token-id ID] (-at)`, `--remove-token <ID> (-rt)`, `--list-tokens (-lt)`. Misc: `--device-id (-id)`, `--refresh (-r)`, `--help (-h)`. [DOC S-bdcygezh]
- `--list-policies` (`-lp`, add `-json` for JSON) reports per policy: Policy ID, Base Policy ID, Friendly Name, Version, Platform Policy (Microsoft-provided, e.g. vulnerable driver blocklist), Policy is Signed, Has File on Disk, Is Currently Enforced, Is Authorized (token authorization state, or mirrors Is Currently Enforced when no token is required). [DOC S-bdcygezh]
- Example to list only enforced policies: `(CiTool -lp -json | ConvertFrom-Json).Policies | Where-Object {$_.IsEnforced -eq "True"} | Select-Object -Property PolicyID,FriendlyName`. [DOC S-bdcygezh]

### Managed installer and ISG (both origin-based, both AppLocker-adjacent)
- Managed installer is an AppLocker `ManagedInstaller` rule collection: only .exe files can be a managed installer. It watches the trusted process (and children) writing files to disk and tags them with the kernel extended attribute `$KERNEL.SMARTLOCKER.ORIGINCLAIM`, the same EA ISG uses. Enable in policy with `13 Enabled:Managed Installer` (`Set-RuleOption -Option 13`). [DOC S-vawypjoe]
- Origin-claim trust propagates down the live process tree (installer -> files it writes -> child processes -> their children) but breaks when the original trusted process exits (later files become "child of a child" and are not authorized on their own) or when a process crosses a security-context boundary without passing the claim along. [DOC S-vawypjoe, S-ickvylma]
- Managed installer known limitations: doesn't support self-updating apps (updated files lack the origin EA), may miss files an installer extracts/downloads/generates and immediately runs, and never authorizes kernel drivers. [DOC S-vawypjoe]
- Configuration Manager auto-configures itself as a managed installer (and enables the needed AppLocker components) when one of its inbox App Control policies is deployed; otherwise use the `ManagedInstaller` `ccmsetup.exe` switch. `appidtel.exe start [-mionly]` configures the AppLocker Application Identity service and filter driver; `-mionly` skips ISG-only setup. [DOC S-vawypjoe]
- ISG is enabled in policy XML with `14 Enabled:Intelligent Security Graph Authorization`, usually paired with `15 Enabled:Invalidate EAs on Reboot` so cached reputation is re-checked after every reboot; not recommended for devices without regular internet access. App Control only queries the ISG for binaries not covered by an explicit allow/deny rule and not installed by a managed installer. [DOC S-ickvylma]
- ISG limitations: it is not recommended for business-critical apps (use explicit rules or a managed installer instead), it does not authorize packaged apps or kernel drivers, boot-critical binaries must never rely on it, and it can over-authorize files an ISG-trusted installer writes during a first run that also launches the app. Intune's built-in App Control policy can enable ISG trust but has no option to add explicit allow/deny rules; a custom policy via Intune's OMA-URI is needed for that. [DOC S-ickvylma]
- Diagnostic events 3090 (allowed by ISG/MI), 3091 (audit-mode would-block), 3092 (enforced-mode block) fire per active policy; enabling 3090 needs `reg add hklm\system\currentcontrolset\control\ci -v TestFlags -t REG_DWORD -d 0x300` plus a reboot. Advanced hunting action types: `AppControlCodeIntegrityOriginAllowed`/`OriginAudited`/`OriginBlocked`. Managed-installer 3091 volume can drive high Log Analytics ingestion cost. [DOC S-vawypjoe, S-wk4roik4]

### Events
- CodeIntegrity/Operational: 3076 = audit-mode block (would have blocked), 3077 = enforced block, 3089 = signature information (one event per file signature; unsigned files emit one with TotalSignatureCount 0; correlate with 3004/3033/3034/3076/3077 via Correlation ActivityID), 3099 = policy loaded (includes policy options), 3095/3096/3097/3100/3101/3102/3103/3105 = policy refresh lifecycle events. [DOC S-wk4roik4]
- 3033 (enforced)/3034 (audit) usually mean a revoked signature or an expired Lifetime-Signing-EKU certificate; option `20 Enabled:Revoked Expired As Unsigned` plus a non-cert-based rule (e.g. hash) works around it. 3004 typically means a kernel driver failed WHQL signature validation. [DOC S-wk4roik4]
- AppLocker/MSI and Script log (not present on Server Core): 8028 = audit-mode script/MSI block, 8029 = enforced-mode block (the script host, e.g. PowerShell Constrained Language Mode, may still allow a restricted run rather than fully block it), 8036 = COM object blocked, 8037 = script passed policy, 8038 = signature info correlated to 8028/8029, 8039/8040 = packaged app audit/enforced block. [DOC S-wk4roik4]

### AppLocker vs App Control for Business
- AppLocker rule collections: Executable, Windows Installer, Script, Packaged apps, DLL (plus a Managed Installer collection used only by App Control). By default AppLocker applies only to code in a user's context; Windows 10/11/Server 2016+ can extend enforcement to non-user processes (including SYSTEM) via rule collection extensions. [DOC S-fq54pkea]
- AppLocker requires the Application Identity service (`appidsvc`, runs as LocalServiceAndNoImpersonation); it is included with all Windows editions except Windows 10 1809 or earlier, but is not supported on Server Core. Authoring: Local Security Policy (single computer) or a GPO via GPMC (fleet); deployable via Group Policy or MDM. [DOC S-fq54pkea]
- Both technologies can rule on codesigning-certificate attributes, signed file metadata (name/version) or hash, and file path. App Control additionally rules on ISG reputation, managed-installer origin, and the launching process, and applies to the whole device (all users); AppLocker rules can target individual users/groups. [DOC S-frmf22fa]
- App Control meets Microsoft's security servicing criteria (MSRC will fix a bypass as a security vulnerability); AppLocker is defense-in-depth only and does not meet that bar. AppLocker keeps receiving security fixes but no new features; App Control keeps getting new capabilities. [DOC S-frmf22fa, S-fq54pkea]
- Choose AppLocker over App Control when the fleet mixes Windows 10-and-earlier with newer OS versions needing one policy, or when different users/groups on a shared device need different rules; AppLocker can also complement App Control (App Control enforced at the most restrictive practical level, AppLocker layered on top for per-user/group fine-tuning). [DOC S-frmf22fa]
- App Control policies can be created/applied on any Windows 10/11 client edition and Windows Server 2016+, and deployed via MDM (e.g. Intune), Configuration Manager, script, or Group Policy (GP deployment is limited to single-policy-format policies for Windows Server 2016/2019). [DOC S-frmf22fa]

### Deployment (Intune) and driver blocklist
- Intune's built-in App Control support (Endpoint Protection profile) can trust Windows components, third-party kernel drivers, Store-signed apps, and optionally ISG-reputable apps; it uses the pre-1903 single-policy-format DefaultWindows policy via the AppLocker CSP, which always forces a device restart. A newer Endpoint security > App Control for Business experience (public preview at the time of the page) creates multiple-policy-format files without a forced restart. [DOC S2202]
- Custom policies deploy through Intune custom OMA-URI at `./Vendor/MSFT/ApplicationControl/Policies/<Policy GUID>/Policy` (no braces around the GUID), data type Base64 (file), a 350,000-byte size limit, using the ApplicationControl CSP (Windows 10 1903+, supports multiple policies and rebootless updates). Pre-1903 systems instead use the AppLocker CSP at `./Vendor/MSFT/AppLocker/ApplicationLaunchRestrictions/<Grouping>/CodeIntegrity/Policy`, which forces a reboot during OOBE and cannot be deleted from the Intune console (deploy an audit-mode policy or delete via script instead). [DOC S2202]
- Due to a known issue, always activate new **signed** App Control base policies with a reboot on systems running memory integrity (HVCI); deploy those via script rather than MDM. This does not affect updates to already-active signed base policies, unsigned policy deployments, supplemental policies, or systems without memory integrity. [DOC S2202]
- To remove an OMA-URI-deployed policy on 1903+, first replace it with an "Allow All"-style policy (e.g. the `AllowAll.xml` example) so nothing is blocked, then delete it from Intune; the change fully takes effect after the next reboot. [DOC S2202]
- The Microsoft vulnerable driver blocklist has been enabled by default since the Windows 11 2022 update; it is also enforced (independent of its own on/off switch) whenever HVCI, Smart App Control, or S mode is active, except on Windows Server 2016. It updates quarterly, plus via monthly Windows updates. [DOC S-salso3t6]
- To force the latest blocklist immediately: download the App Control policy refresh tool and the blocklist binaries, rename the chosen (audit or enforced) file to `SiPolicy.p7b`, copy it to `%windir%\system32\CodeIntegrity`, then run the refresh tool; verify via a 3099 event in CodeIntegrity/Operational whose PolicyNameBuffer/PolicyIdBuffer match the blocklist policy's Name/ID. Already-running vulnerable drivers are only blocked after a reboot. [DOC S-salso3t6]
- Re-confirmed 2026-09-26: the AppLocker CSP's forced reboot is not limited to OOBE/first deployment — Microsoft Learn's own MDM deployment guidance states "Deploying policies via the AppLocker CSP will force a reboot during OOBE" for initial deployment *and* separately that "the AppLocker CSP will schedule a reboot when a policy is applied **or when a deletion occurs**" using the `CodeIntegrity/Policy` URI generally, and the ApplicationControl CSP overview confirms the (newer) ApplicationControl CSP "correctly detects the presence of the no-reboot option" — implying AppLocker CSP, unlike ApplicationControl CSP, always reboots regardless of OOBE. The "improved Intune App Control experience" (`intune/protect/endpoint-security-app-control-policy`) remains **public preview** with no GA date published on the fetched pages. [DOC S-oartdvpr]

## Reference
Related: `windows/smart-app-control.md` (Smart App Control is built on App Control for Business and reuses the same CiTool, ISG, and CodeIntegrity/Operational 3076/3077 events documented here).
Related: `defender/asr-and-antivirus.md` (Attack Surface Reduction rules and Defender Antivirus core settings; a separate, complementary Defender AV control layer, not part of App Control policy XML).

| Rule option # | Name | Valid in supplemental |
|---|---|---|
| 0 | Enabled:UMCI | No |
| 3 | Enabled:Audit Mode (default) | No |
| 6 | Enabled:Unsigned System Integrity Policy (default) | Yes |
| 13 | Enabled:Managed Installer | Yes |
| 14 | Enabled:Intelligent Security Graph Authorization | Yes |
| 17 | Enabled:Allow Supplemental Policies | No |
| 18 | Disabled:Runtime FilePath Rule Protection | Yes |
| 19 | Enabled:Dynamic Code Security | No |

Full table (all 21 options + the unnumbered Developer Mode option): `windows/app-control.csv`.

| Question | Answer | Source |
|---|---|---|
| Multiple base policies interact how | Intersection (must pass every base policy) | S-k6lcrjix |
| Base + supplemental interact how | Union (allowed by either) | S-k6lcrjix |
| 32-policy cap removed when | Windows security update on/after 2024-04-09 (not on Windows 11 21H2) | S-k6lcrjix |
| CiTool minimum OS | Windows 11 22H2 / Windows Server 2025 | S-bdcygezh |
| Audit block event (CodeIntegrity) | 3076 | S-wk4roik4 |
| Enforced block event (CodeIntegrity) | 3077 | S-wk4roik4 |
| Audit script block (AppLocker/MSI and Script) | 8028 | S-wk4roik4 |
| Enforced script block (AppLocker/MSI and Script) | 8029 | S-wk4roik4 |
| App Control meets MSRC security servicing bar | Yes | S-frmf22fa |
| AppLocker meets MSRC security servicing bar | No (defense-in-depth only) | S-frmf22fa |
| Intune custom policy OMA-URI (1903+) | `./Vendor/MSFT/ApplicationControl/Policies/<GUID>/Policy`, 350,000-byte limit | S2202 |

## Examples
Query which App Control policies are currently enforced on PL-LT-00123:
```powershell
(CiTool -lp -json | ConvertFrom-Json).Policies | Where-Object {$_.IsEnforced -eq "True"} |
    Select-Object -Property PolicyID,FriendlyName
```

Build a Multiple Policy Format base policy that allows supplemental policies, then create a supplemental policy for it:
```powershell
New-CIPolicy -MultiplePolicyFormat -ScanPath "C:\ReferenceApps" -UserPEs -FilePath ".\base.xml" `
    -Level FilePublisher -Fallback SignedVersion,Publisher,Hash
Set-RuleOption -FilePath ".\base.xml" -Option 17
Set-CIPolicyIdInfo -FilePath ".\base.xml" -PolicyName "corp-base" -ResetPolicyID

New-CIPolicy -MultiplePolicyFormat -ScanPath "C:\LineOfBusinessApps" -UserPEs -FilePath ".\supplemental.xml" `
    -Level Publisher -Fallback Hash
Set-CIPolicyIdInfo -FilePath ".\supplemental.xml" -BasePolicyToSupplementPath ".\base.xml" `
    -PolicyId "00000000-0000-0000-0000-000000000003" -PolicyName "corp-lob-supplemental"
```

Enable the managed installer option and turn Configuration Manager into a managed installer, then deploy the resulting binary to PL-LT-00123 with `CiTool`:
```powershell
Copy-Item "C:\Windows\schemas\CodeIntegrity\ExamplePolicies\DefaultWindows_Audit.xml" ".\policy.xml"
Set-CIPolicyIdInfo -FilePath ".\policy.xml" -PolicyName "corp-managed-installer" -ResetPolicyID
Set-RuleOption -FilePath ".\policy.xml" -Option 13
ConvertFrom-CIPolicy -XmlFilePath ".\policy.xml" -BinaryFilePath ".\{POLICY-GUID}.cip"
CiTool --update-policy ".\{POLICY-GUID}.cip"
```
