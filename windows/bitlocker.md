---
topic: windows/bitlocker
priority: P2
applies_to: "Windows 10 1703+/11, BitLocker CSP; Intune endpoint security disk encryption and device configuration Endpoint protection policies"
retrieved_utc: 2026-09-26
sources: [S-pfrwongj, S-cqv5zeve, S-sr7tk6jz, S-jdytzqlj, S-dwu7auzi, S-prkgx2hs, S-kszikunl, S-c4224tvs, S-mld6grwd, S-a7iwz7je, S-wzeeikuf, S-pi5lmjbg, S-77cduhcg, S-2cojjewu, S-7qrbvran, S531]
status: partial
files: [windows/bitlocker.csv]
---

# BitLocker CSP, Intune silent encryption, and troubleshooting

## Summary
- Intune manages BitLocker through the BitLocker CSP (`./Device/Vendor/MSFT/BitLocker/...`); full node list, formats, allowed values, defaults in `windows/bitlocker.csv`. [DOC S-pfrwongj]
- Standard encryption lets the user interact; silent encryption enables BitLocker with no user interaction or admin rights, using specific CSP settings. [DOC S-cqv5zeve]
- Settings Catalog lacks the TPM startup-authentication controls needed for reliable silent BitLocker, so endpoint security (Disk encryption) or device configuration (Endpoint protection) policies must be used instead. [DOC S-cqv5zeve]
- Silent-encryption failures show as event IDs and status-node bitmasks; common causes are missing/locked TPM, WinRE not configured, legacy BIOS, or Secure Boot off. [DOC S-sr7tk6jz]
- Automatic encryption (Entra join triggers it) differs from silent encryption (Intune suppresses UI via the CSP); each has its own prerequisites. [DOC S-jdytzqlj]

## Facts

### Silent encryption
- To manage BitLocker with the CSP beyond `RequireDeviceEncryption`, users need a Windows 10/11 Enterprise E3/E5 (in Microsoft 365 F3/E3/E5) or Enterprise A3/A5 (in Microsoft 365 A3/A5) licence. [DOC S-pfrwongj]
- Settings are enforced only when encryption starts; a settings change doesn't restart encryption on an already-encrypting or already-encrypted drive. [DOC S-pfrwongj]
- Required CSP settings for silent encryption: `RequireDeviceEncryption=1`, `AllowWarningForOtherDiskEncryption=0`; add `AllowStandardUserEncryption=1` when the signed-in user is a standard (non-admin) user. [DOC S-cqv5zeve, S-sr7tk6jz]
- For silent encryption, every TPM startup-authentication option under `SystemDrivesRequireStartupAuthentication` (PIN, key, PIN+key) must be Disallowed or not Required -- a required PIN/key blocks silent enablement because it needs user interaction. [DOC S-cqv5zeve]
- Silent-encryption device requirements: Microsoft Entra joined or hybrid joined; TPM 1.2 or later, unlocked; native UEFI BIOS; Secure Boot enabled; WinRE configured and available. [DOC S-cqv5zeve]
- OS version for silent encryption: Windows 10 1803+/Windows 11 when end users sign in as Administrators; Windows 10 1809+/Windows 11 when end users sign in as Standard Users. [DOC S-cqv5zeve]
- When BitLocker enables silently, the system automatically uses full disk encryption on non-modern-standby devices and used-space-only encryption on modern-standby devices; the type can't be customized for silent scenarios. [DOC S-cqv5zeve]
- Intune enforces silent BitLocker for Autopilot devices with standard-user profiles when `RequireDeviceEncryption=1`, `AllowStandardUserEncryption=1` and `AllowWarningForOtherDiskEncryption=0` are all set together. [DOC S-sr7tk6jz]
- Silent-encryption prerequisites (troubleshooting doc): TPM 1.2 or 2.0 unlocked; WinRE enabled; system drive >= 350 MB formatted FAT32 for UEFI (NTFS for BIOS) and an NTFS OS drive; UEFI BIOS required for TPM 2.0 devices; device connected to Entra ID or hybrid Azure services. [DOC S-jdytzqlj]
- Automatic encryption (triggered by Entra join, no endpoint protection policy needed) requires Windows 10 1703+, Modern Standby support and HSTI compliance; it is distinct from silent encryption, which suppresses UI purely via BitLocker CSP settings. [DOC S-jdytzqlj]
- Windows 10 1809+ lets an endpoint protection policy enforce silent Device Encryption even on devices that aren't HSTI-compliant (an update to the BitLocker Policy CSP). [DOC S-sr7tk6jz]
- Intune's three enforcement types: Automatic (Entra join, 1703+), Silent (endpoint protection policy, 1803+), Interactive (endpoint policy on Windows versions older than 1803). [DOC S-sr7tk6jz]

### Policy types and RBAC
- Two Intune policy types configure BitLocker: Endpoint security > Disk encryption (BitLocker profile and Personal Data Encryption profile, recommended), and Device configuration > Endpoint protection profile (Windows Encryption section). [DOC S-cqv5zeve]
- Personal Data Encryption (PDE) encrypts files (not whole volumes), works alongside BitLocker, needs Windows Hello for Business sign-in to release keys, and requires Windows 11 22H2+. [DOC S-cqv5zeve]
- Managing BitLocker in Intune (viewing/rotating keys) needs an RBAC role with **Remote tasks > Rotate BitLockerKeys (preview)** set to Yes; included in the built-in Help Desk Operator and Endpoint Security Administrator roles. [DOC S-cqv5zeve]

### Recovery keys and rotation
- Recovery key rotation (Intune device action **BitLocker key rotation**) needs Windows 10 1909+ or Windows 11, and for Entra joined/hybrid joined devices needs: Client-driven recovery password rotation enabled, Save BitLocker recovery information to Entra ID = Enabled, Store recovery information in Entra ID before enabling BitLocker = Required. [DOC S-cqv5zeve]
- Key rotation via `RotateRecoveryPasswords` (Exec) is supported only for these enrollment types: windowsAzureADJoin, windowsBulkAzureDomainJoin, windowsAzureADJoinUsingDeviceAuth, windowsCoManagement. [DOC S-pfrwongj]
- Microsoft Entra ID supports a maximum of 200 BitLocker recovery keys per device; past that limit, silent encryption fails because the recovery-key backup fails before encryption starts. [DOC S-cqv5zeve]
- Viewing a recovery key in the Intune admin center generates an audit log entry under the `KeyManagement` activity category (see also `entra/bitlocker-key-deletion.md`). [DOC S-cqv5zeve]
- Deleting the Intune object for an Entra-joined, BitLocker-protected device triggers a device sync that removes the OS-volume key protectors, leaving BitLocker suspended on that volume. [DOC S-cqv5zeve]
- Required permission to view BitLocker recovery keys in Entra ID: `microsoft.directory/bitlockerKeys/key/read`, included in Cloud Device Administrator, Helpdesk Administrator and Global Administrator. [DOC S-cqv5zeve]
- Tenant-attached (ConfigMgr) BitLocker key viewing needs ConfigMgr 2107+ with rollup KB11121541 (for Entra-joined device support), Intune RBAC permission to view keys, and an on-prem user with a Configuration Manager collection role plus Read BitLocker Recovery Key permission. [DOC S-cqv5zeve]

### Troubleshooting: events and status
- `Status/DeviceEncryptionStatus` is a Get-only bitmask; 0 = compliant, and each set bit maps to a specific enforcement failure (e.g. bit 2 = OS volume unprotected, bit 8 = recovery key backup failed, bit 12 = WinRE not configured, bit 13 = no TPM available, bit 14 = TPM not ready, bit 15 = network unavailable for recovery backup). Full bit table in `windows/bitlocker.csv`. [DOC S-pfrwongj]
- Event ID 853 ("compatible TPM Security Device cannot be found") means no TPM chip or TPM disabled in BIOS; resolve by enabling TPM in BIOS and confirming TPM.msc shows Ready (2.0) or Initialized (1.2). [DOC S-sr7tk6jz]
- Event ID 853 (bootable media detected) halts provisioning if removable bootable media (CD/DVD) is present; remove it and restart. [DOC S-sr7tk6jz]
- Event ID 854 ("WinRE is not configured") is resolved by checking disk partitions with `diskpart.exe`/`list volume`, checking status with `reagentc.exe /info`, enabling with `reagentc.exe /enable`, and confirming the Windows Boot Loader's `recoverysequence` GUID with `bcdedit.exe /enum all`. [DOC S-sr7tk6jz]
- Event ID 851 ("contact manufacturer for BIOS upgrade") means legacy BIOS; silent BitLocker requires UEFI (check via `msinfo32` BIOS Mode); a Legacy-only device can't have Device Encryption managed by Intune. [DOC S-sr7tk6jz]
- "UEFI variable 'SecureBoot' could not be read" means Secure Boot is off; silent BitLocker needs PCR 7 (Secure Boot) in the TPM's PCR validation profile -- check with `manage-bde.exe -protectors -get %systemdrive%` or `Confirm-SecureBootUEFI`. [DOC S-sr7tk6jz]
- Event IDs 846/778/851 with error `0x80072f9a` on Windows 10 1809 (when "Allow standard users to enable encryption during Microsoft Entra join" is set) mean the signed-in user can't read the enrollment certificate's private key; fixed by update KB4497934 (May 21, 2019). [DOC S-sr7tk6jz]
- "Conflicting Group Policy settings for recovery options on operating system drives" occurs when AD DS backup of recovery info is Required while recovery-password generation is disallowed; resolve by fixing the conflicting GPOs. [DOC S-sr7tk6jz]
- Normal operation logs Event ID 796 and Event ID 845 in Applications and Services Logs > Microsoft > Windows > BitLocker-API > Management/Operations. [DOC S-sr7tk6jz]
- On-device policy settings can be checked under registry keys `HKLM\SOFTWARE\Microsoft\PolicyManager\current\device\BitLocker` and `...\current\device`. [DOC S-sr7tk6jz]
- The Intune encryption report (Devices > Monitor > Encryption report) flags six common failure patterns: not-ready/not-encrypted (missing TPM), ready-but-not-encrypted (non-silent policy, user hasn't acted), not-ready-won't-encrypt-silently (TPM not ready), ready-but-not-silently-encrypted (WinRE disabled or standard user without "Allow standard users to enable encryption during Autopilot"), error-but-encrypted (encryption-method mismatch, e.g. policy wants XTS-AES128 but device is XTS-AES256), and encrypted-but-profile-error (device encrypted by another means, e.g. manually or by MBAM/ConfigMgr before enrollment). [DOC S-jdytzqlj]
- Decrypting and re-encrypting through Intune's own policy is the fix for an encryption-method mismatch (Scenario 5). [DOC S-jdytzqlj]

### Graph recovery key retrieval
- `GET /informationProtection/bitlocker/recoveryKeys/{id}` (v1.0) omits the `key` property by default; adding `$select=key` returns it and triggers a Microsoft Entra audit log entry for the operation. [DOC S-dwu7auzi]
- Least-privileged permission for this call is delegated/application `BitlockerKey.ReadBasic.All`; the higher-privileged alternative is `BitlockerKey.Read.All` (same pair already recorded at `graph/permissions.csv:12`; not repeated here). [DOC S-dwu7auzi]
- For delegated calls the signed-in user must either be the device's registered owner or hold one of these Entra roles: Cloud device administrator, Helpdesk administrator, Intune service administrator, Security administrator, Security reader, Global reader. [DOC S-dwu7auzi]
- Request headers: `Authorization` (required) and `User-Agent` (required); `ocp-client-name` and `ocp-client-version` are optional debugging headers, not enforced by the API. [DOC S-dwu7auzi]
- The list operation supports `$filter=deviceId eq '{deviceId}'` to find a device's recovery keys (also used in `entra/bitlocker-key-deletion.md`). [DOC S531]

### PowerShell BitLocker module and manage-bde
- `Get-BitLockerVolume [-MountPoint <String[]>]`: with no mount point, returns every volume; exposes `VolumeType`, `EncryptionMethod`, `VolumeStatus`, `EncryptionPercentage`, `KeyProtector`, `ProtectionStatus`, `LockStatus`. [DOC S-wzeeikuf]
- `Enable-BitLocker -MountPoint <String[]>` needs exactly one key-protector switch (e.g. `-TpmProtector`, `-RecoveryPasswordProtector`); `-EncryptionMethod` accepts `Aes128`, `Aes256`, `XtsAes128`, `XtsAes256` (default XTS-AES-128 if omitted); `-UsedSpaceOnly` encrypts only used space instead of the whole drive; `-SkipHardwareTest` skips the pre-encryption hardware compatibility dry run. [DOC S-prkgx2hs]
- `Add-BitLockerKeyProtector -MountPoint <String[]> -RecoveryPasswordProtector [-RecoveryPassword <String>]`: without an explicit password, generates a random 48-digit recovery password stored in the returned volume object's `KeyProtector.RecoveryPassword`; adding a protector never merges with an existing one -- it's always an additional protector. [DOC S-kszikunl]
- `Backup-BitLockerKeyProtector -MountPoint <String[]> -KeyProtectorId <String>` saves a recovery-password key protector to AD DS by protector ID (from `(Get-BitLockerVolume).KeyProtector`). [DOC S-mld6grwd]
- `BackupToAAD-BitLockerKeyProtector -MountPoint <String[]> -KeyProtectorId <String>` saves a recovery-password key protector to Microsoft Entra ID by protector ID; same parameter shape as the AD DS cmdlet. [DOC S-c4224tvs]
- `Suspend-BitLocker -MountPoint <String[]> [-RebootCount <Int32>]`: makes the encryption key available in the clear (data stays encrypted) without removing protectors; `-RebootCount 0` suspends indefinitely until `Resume-BitLocker` runs; omitting the parameter defaults to 1 (protection resumes after the next restart). Accepted range is 0-15. [DOC S-a7iwz7je]
- `manage-bde -status [<drive>] [-protectionaserrorlevel]` reports size, conversion status, percentage encrypted, encryption method, protection/lock status, identification field and key protectors; `-protectionaserrorlevel` returns exit code 0 if protected, 1 if not (for batch scripts). [DOC S-77cduhcg]
- `manage-bde -protectors -get <drive>` lists each key protector's type and ID; `-protectors -adbackup <drive> -id <keyprotectorID>` backs up recovery information to AD DS for one protector (the `-id` parameter is required); `-protectors -aadbackup <drive> -id <keyprotectorID>` does the same to Microsoft Entra ID. [DOC S-pi5lmjbg]

### Windows editions, licensing, and 24H2 change
- BitLocker management is supported on Windows Pro, Enterprise, Pro Education/SE and Education; but the BitLocker management license entitlement itself is granted only by Windows Enterprise E3/E5 or Education A3/A5 -- Windows Pro/Pro Education/SE has no entitlement (matches the CSP page's own licence note in `windows/bitlocker.csv`). [DOC S-2cojjewu]
- Device encryption (the automatic, no-policy BitLocker mode) historically required a device to meet either Modern Standby or HSTI security requirements and have no externally accessible DMA ports. [DOC S-7qrbvran]
- Starting in Windows 11, version 24H2, the Modern Standby/HSTI and DMA-interface prerequisites for device encryption are removed, so more devices are eligible for automatic and manual device encryption; this change doesn't apply to Windows IoT editions. [DOC S-7qrbvran]

## Reference
- Recovery key storage, deletion via device removal, and Graph least-privileged permissions for reading `bitlockerKeys`: `entra/bitlocker-key-deletion.md`, `graph/permissions.md` (`BitlockerKey.ReadBasic.All` / `.Read.All`).
- Intune compliance policy settings that check BitLocker/encryption presence (Require BitLocker, Encryption of data storage on a device): `intune/compliance-policies.md`, `intune/compliance-policies.csv`.
- `windows/bitlocker.csv`: full CSP node table (node, format, values, default, notes).
- `intune/remote-actions.md`: the Graph `rotateBitLockerKeys` (beta) remote action that rotates the recovery key on demand.

## Examples
- Silent-encryption OMA-URI set (device configuration Endpoint protection, non-HSTI-compliant Modern-Standby-incapable device), pushed to `PL-LT-00123`:
  - `./Device/Vendor/MSFT/BitLocker/RequireDeviceEncryption` (int) = `1`
  - `./Device/Vendor/MSFT/BitLocker/AllowWarningForOtherDiskEncryption` (int) = `0`
  - `./Device/Vendor/MSFT/BitLocker/AllowStandardUserEncryption` (int) = `1` (standard-user Autopilot scenario)
- Check silent-encryption prerequisites on `PL-LT-00123` from an elevated prompt: `reagentc.exe /info` (WinRE), `manage-bde.exe -protectors -get %systemdrive%` (confirm PCR 7 present), `msinfo32` (BIOS Mode = UEFI, Secure Boot State = On).
- After deploying a policy that requires XTS-AES256 to a device previously encrypted with XTS-AES128, decrypt and let the policy re-encrypt: `manage-bde -off c:` then wait for policy resync (Scenario 5 in the encryption report).
- Retrieve a recovery key's value for device `PL-LT-00123` via Graph, using `Invoke-MgGraphRequest` with the debugging headers:
  ```powershell
  Connect-MgGraph -Scopes "BitlockerKey.ReadBasic.All"
  $headers = @{ "ocp-client-name" = "kb-example-client"; "ocp-client-version" = "1.0" }
  # First, find the key id for the device:
  Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/informationProtection/bitlocker/recoveryKeys?`$filter=deviceId eq '00000000-0000-0000-0000-000000000001'" -Headers $headers
  # Then, with BitlockerKey.Read.All consented, fetch the key value (generates a KeyManagement audit entry):
  Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/informationProtection/bitlocker/recoveryKeys/{keyId}?`$select=key" -Headers $headers
  ```
