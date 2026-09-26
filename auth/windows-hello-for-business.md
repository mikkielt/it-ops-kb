---
topic: auth/windows-hello-for-business
priority: P1
applies_to: "Windows 10/11, Windows Server 2016+ domain controllers (cloud Kerberos trust: Server 2016 KB4534307+, 2019 KB4534321+, 2022, 2025); Microsoft Entra ID"
retrieved_utc: 2026-09-26
sources: [S-pnjd7ogq, S-ui2zukwr, S-do5bf4ea, S-qi55sa4p, S-vymmambu, S-htlj43pv, S-kdtltdvz, S-u2hfxeqe]
status: partial
files: [auth/passportforwork-csp.csv]
---

# Windows Hello for Business (WHfB)

## Summary
- Three **deployment models** (cloud-only, hybrid, on-premises) and three **trust types** (cloud Kerberos, key, certificate) that define how a client authenticates to on-premises Active Directory; trust type doesn't apply to cloud-only and doesn't affect authentication to Microsoft Entra ID, which always uses a key. [DOC S-pnjd7ogq]
- **Cloud Kerberos trust is the Microsoft-recommended hybrid trust type**: no PKI to deploy or maintain, no key sync delay between Entra ID and AD, and it reuses the same Microsoft Entra Kerberos infrastructure as on-premises FIDO2 security key sign-in. [DOC S-pnjd7ogq]
- Provisioning is a single policy toggle (`UsePassportForWork`) plus per-trust-type settings, configured via Intune settings catalog / custom CSP profile or Group Policy (Group Policy wins over Intune when both apply). [DOC S-ui2zukwr]
- `dsregcmd /status` and the **User Device Registration** admin log (`Applications and Services Logs > Microsoft > Windows`) are the primary places to check WHfB prerequisite and provisioning state on a client; see `entra/dsregcmd.md` for the field reference (this article does not repeat those fields). [DOC S-ui2zukwr]
- Status: partial — this article does not cover certificate trust's AD FS/PKI configuration steps or biometrics enrollment UX in depth (out of scope for this pass); see Reference for links to the dedicated deployment guides.

## Facts
### Deployment models and trust types
- **Cloud-only**: organizations with only cloud identities; devices are Microsoft Entra joined or registered; no trust type applies, no certificates needed. [DOC S-pnjd7ogq]
- **Hybrid**: identities synchronized from AD to Microsoft Entra ID; supports Microsoft Entra joined, Microsoft Entra hybrid joined, or Microsoft Entra registered devices; SSO to both on-premises and cloud resources. [DOC S-pnjd7ogq]
- **On-premises**: no cloud identities or Entra-registered apps; domain-joined devices only; device registration is handled by AD FS, not Entra ID; its main use case is Enhanced Security Administrative Environments ("Red Forests"); migrating from on-premises to hybrid requires a full redeployment. [DOC S-pnjd7ogq]
- **Cloud Kerberos trust**: the client requests a TGT from Microsoft Entra ID via Microsoft Entra Kerberos; on-premises DCs still issue Kerberos service tickets and do authorization; no PKI required. [DOC S-pnjd7ogq]
- **Key trust**: the client authenticates to on-premises AD using a device-bound key created during provisioning; requires certificates on domain controllers (not on the client). [DOC S-pnjd7ogq]
- **Certificate trust**: the client is issued an authentication certificate, requested using the device-bound key; requires an enterprise PKI, a certificate registration authority (AD FS acts as the CRA), and — in a federated environment — Device Writeback enabled in Microsoft Entra Connect. [DOC S-pnjd7ogq]
- Key trust and certificate trust both use certificate-authentication-based Kerberos to request on-premises TGTs; only certificate trust needs end-user certificates. [DOC S-pnjd7ogq]
- Authentication-to-Entra-ID requirements by model: cloud-only can use cloud or federated auth; hybrid cloud Kerberos trust and hybrid key trust support Password Hash Sync (PHS), Pass-through Authentication (PTA), or federated (AD FS/non-Microsoft); hybrid certificate trust does **not** support PHS or PTA — AD must be federated with Entra ID via AD FS. [DOC S-pnjd7ogq]
- No direct migration path from certificate trust to cloud Kerberos trust: the Windows Hello container must be deleted (`certutil.exe -deletehellocontainer` in the user context) and WHfB re-provisioned. [DOC S-ui2zukwr]
- Migrating key trust to cloud Kerberos trust: set up Microsoft Entra Kerberos, enable cloud Kerberos trust by policy, then (Entra joined only) sign out/in; Entra hybrid joined devices must do the first sign-in with new credentials while having line of sight to a DC. [DOC S-ui2zukwr]

### Cloud Kerberos trust deployment
- Deploying Microsoft Entra Kerberos creates an `AzureADKerberos` computer object in the on-premises AD domain (`CN=AzureADKerberos,OU=Domain Controllers,<domain-DN>`); it appears as a read-only domain controller (RODC) object but isn't tied to a physical server and is used only by Microsoft Entra ID to issue TGTs for that AD domain. [DOC S-ui2zukwr]
- The same RODC-style restrictions apply to the `AzureADKerberos` object: members of privileged built-in security groups can't use cloud Kerberos trust, and Microsoft explicitly recommends against relaxing the object's default Password Replication Policy to unblock them (attack-vector risk from Entra ID into AD). [DOC S-ui2zukwr]
- Microsoft Entra Kerberos is set up with the `AzureADHybridAuthenticationManagement` PowerShell module (the same module used for on-premises passwordless FIDO2 security key sign-in); if that's already deployed, no redeployment is needed for WHfB. [DOC S-ui2zukwr] [DOC S-u2hfxeqe]
- Adequate **read-write domain controllers** are required in every AD site where users authenticate with WHfB cloud Kerberos trust — not all DCs need the minimum OS/patch level, only enough to handle the cloud-Kerberos-trust device load. [DOC S-ui2zukwr]
- If `UseCertificateForOnPremAuth` is enabled, certificate trust takes precedence over cloud Kerberos trust; that policy must be left not configured on devices meant to use cloud Kerberos trust. [DOC S-ui2zukwr]
- Cloud Kerberos trust minimum client versions: Windows 10 21H2 with KB5010415+, Windows 11 21H2 with KB5010414+ (all later supported versions qualify without an extra KB). [DOC S-pnjd7ogq]
- Cloud Kerberos trust minimum domain-controller OS: Windows Server 2016 with KB4534307+, Windows Server 2019 with KB4534321+, Windows Server 2022, Windows Server 2025 (all support it natively); minimum domain/forest functional level for any WHfB deployment model is Windows Server 2008 R2. [DOC S-pnjd7ogq]
- Cloud Kerberos trust's provisioning prerequisite check on Microsoft Entra hybrid joined devices looks for a **partial TGT**, confirming Microsoft Entra Kerberos is set up for the user's domain/tenant; states are Yes / No / Not Tested (Not Tested = policy not enforced, or device is Entra joined — the check is skipped entirely on Entra joined devices, and sign-in still works there without SSO to on-prem resources if Entra Kerberos isn't provisioned). [DOC S-ui2zukwr]
- After enrollment with cloud Kerberos trust, the WHfB gesture works **immediately** for sign-in; on a hybrid joined device the first PIN use still needs line-of-sight to a DC, after which cached sign-in works for subsequent unlocks without connectivity; in mixed line-of-sight conditions (DC reachable, Entra ID not) the DC may require a freshly refreshed PRT before it permits authentication. [DOC S-ui2zukwr]
- Microsoft Entra Connect synchronizes the user's WHfB public key from Microsoft Entra ID to Active Directory after enrollment (all trust types that need AD to know the key). [DOC S-ui2zukwr]
- Cloud Kerberos trust unsupported scenarios: RDP/VDI with supplied credentials (works with Remote Credential Guard, or with a certificate enrolled into the WHfB container for that purpose); *Run as*; and first sign-in on a hybrid joined device without prior DC connectivity. [DOC S-ui2zukwr]
- Cloud Kerberos trust works against a Read-Only Domain Controller (RODC) that doesn't cache the authenticating user's credentials (per Password Replication Policy); if the RODC does cache them, cloud Kerberos trust authentication can fail — mitigate by also deploying KDC certificates to the RODCs so authentication falls back to key trust. [DOC S-vymmambu]
- Cloud Kerberos trust doesn't work in a pure on-premises AD environment (no Entra ID) and doesn't require every DC to be fully patched to the prerequisite level — only enough to carry the cloud-Kerberos-trust load. [DOC S-vymmambu]

### Policy configuration (Intune and GPO)
- Minimum cloud Kerberos trust policy via Intune settings catalog (category **Windows Hello for Business**): `Use Windows Hello For Business` = true, `Use Cloud Trust For On Prem Auth` = Enabled, `Use Security Device` = true (recommended, not strictly required); if the tenant-wide WHfB policy is already enabled and suits the deployment, only `Use Cloud Trust For On Prem Auth` needs to be set. [DOC S-ui2zukwr]
- Equivalent custom Intune profile via `PassportForWork` CSP OMA-URIs (bool, value `True`): `./Device/Vendor/MSFT/PassportForWork/{TenantId}/Policies/UsePassportForWork`, `.../UseCloudTrustForOnPremAuth`, `.../RequireSecurityDevice`. [DOC S-ui2zukwr] [DOC S-qi55sa4p]
- Equivalent GPO path `Computer Configuration\Administrative Templates\Windows Components\Windows Hello for Business`: `Use Windows Hello for Business` = Enabled, `Use cloud Kerberos trust for on-premises authentication` = Enabled (computer-only setting, no user-node equivalent), `Use a hardware security device` = Enabled; GPO settings for WHfB ship in `Passport.admx`/`Passport.adml`, which may need copying from a client that supports cloud Kerberos trust into the Central Store. [DOC S-ui2zukwr]
- `Use Windows Hello for Business` can be deployed as a computer or user GPO node: computer node makes every signed-in user attempt enrollment; user node scopes it to targeted users; if both are deployed, the user setting takes precedence. Recommended rollout technique is security-group filtering on a domain-linked GPO for a phased rollout. [DOC S-ui2zukwr]
- If WHfB is configured through both Group Policy and Intune, **Group Policy settings take precedence and the conflicting Intune settings are ignored**. [DOC S-ui2zukwr]
- Since Windows 10 1607, a device has exactly one PIN shared by WHfB; `PassportForWork` CSP PIN-complexity settings take precedence over any complexity rules set via Exchange ActiveSync or the DeviceLock CSP. [DOC S-qi55sa4p]
- Full `PassportForWork` CSP node reference (nodes, OMA-URI, type, default, description): `auth/passportforwork-csp.csv`. [DOC S-qi55sa4p]

### Enrollment / provisioning flow and MFA
- Provisioning begins right after sign-in once prerequisite checks pass (for cloud Kerberos trust, that includes the partial-TGT check on hybrid joined devices). [DOC S-ui2zukwr]
- User flow: optional biometric gesture setup (skippable) -> confirm using Windows Hello with the org account -> MFA challenge (provisioning blocks until MFA succeeds, fails, or times out; failure/timeout prompts a retry) -> PIN creation and validation against the configured PIN-complexity policy -> asymmetric key-pair generation (preferably in the TPM, or mandatory if `RequireSecurityDevice` is set) and public-key registration with the identity provider. [DOC S-ui2zukwr]
- Certificate trust adds a step after key registration: Windows requests a certificate using the same key pair from the AD FS registration authority, which verifies the key matches the registered one, signs the request with its enrollment-agent certificate, and forwards it to the CA. [DOC S-do5bf4ea]
- Known deployment issue: AD FS on **Windows Server 2019** fails certificate-trust device authentication due to an invalid incoming-scope check, blocking WHfB provisioning; identified by event ID 362 ("User has successfully authenticated to the enterprise STS: No") under `Microsoft-Windows-User Device Registration`, and by AD FS/Admin event ID 1021 (client forbidden for scope `ugs`). Fixed in Windows Server 1903+; on 2019, remediate by adding the `ugs` scope manually in the AD FS management console (Services > Scope Descriptions). [DOC S-kdtltdvz]
- Event ID 300 (`Microsoft-Windows-User Device Registration/Admin` log, source "Microsoft Azure Device Registration Service") is logged when the NGC (WHfB) key is successfully created and registered with Microsoft Entra ID; message includes the Key ID, UPN, attestation level (e.g. `ATT_SOFT`), and server request ID — a normal condition needing no action. [DOC S-kdtltdvz]

### Multi-factor unlock (trusted signal unlock)
- Trusted signal unlock extends WHfB with a required additional "trust signal" factor (e.g. a known network or companion device) layered on top of the PIN/biometric gesture, for organizations where a device-bound credential plus PIN alone isn't sufficient assurance. [DOC S-htlj43pv]
- Configured with **First unlock factor credential providers**, **Second unlock factor credential providers**, and **signal rules for the Trusted Signal Credential Provider**; enabled via GPO `Computer Configuration > Administrative Templates > Windows Components > Windows Hello for Business > Configure device unlock factors`. [DOC S-htlj43pv]
- Microsoft recommends disabling all non-Microsoft credential providers when using trusted signal unlock, since a user without the required factors otherwise falls back to password or smart card sign-in. [DOC S-htlj43pv]
- Trusted signal unlock events are logged under `Applications and Services Logs\Microsoft\Windows\HelloForBusiness`, category "Device Unlock": 3520 unlock attempt initiated, 5520 unlock policy not configured, 6520 warning, 7520 error, 8520 success. [DOC S-htlj43pv]

## Reference
- `entra/dsregcmd.md` and `entra/dsregcmd-fields.csv` — `NgcSet`/`NgcKeyId`/`CanReset` (User state) and PRT fields (`AzureAdPrt`, `AzureAdPrtUpdateTime`, `AzureAdPrtExpiryTime`) referenced above for checking WHfB and cloud Kerberos trust prerequisite state; not repeated here.
- `auth/kerberos.md` — on-premises Kerberos hardening (Protected Users, RC4/AES deprecation, NTLM deprecation) that interacts with any AD authentication a WHfB trust type ultimately performs; back-link added there.
- `auth/passportforwork-csp.csv` — full `PassportForWork` CSP node table (this directory).
- Deployment guides not fully expanded in this pass: hybrid key trust, hybrid/on-premises certificate trust (`S-do5bf4ea`), cloud-only — same policy/enrollment shape as summarized above, differing mainly in PKI/AD FS steps.

## Examples
- Custom Intune OMA-URI profile enabling cloud Kerberos trust for tenant `00000000-0000-0000-0000-000000000000`:
  - `./Device/Vendor/MSFT/PassportForWork/00000000-0000-0000-0000-000000000000/Policies/UsePassportForWork` = `true` (bool)
  - `./Device/Vendor/MSFT/PassportForWork/00000000-0000-0000-0000-000000000000/Policies/UseCloudTrustForOnPremAuth` = `true` (bool)
  - `./Device/Vendor/MSFT/PassportForWork/00000000-0000-0000-0000-000000000000/Policies/RequireSecurityDevice` = `true` (bool)
- On `PL-LT-00123`, checking provisioning state: `dsregcmd /status` and Event Viewer `Applications and Services Logs > Microsoft > Windows > User Device Registration > Admin`, looking for event ID 300 (key registered) or ID 362 (STS authentication failure, certificate trust only).
