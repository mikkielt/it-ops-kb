---
topic: entra/device-identity
priority: P1
applies_to: "Microsoft Entra ID (docs ms.date 06/27/2025), Graph v1.0"
retrieved_utc: 2026-09-26
sources: [S504, S540, S541, S542, S543, S544]
status: complete
---

# Entra device identity: join types and trustType

## Summary
- Three ways to get a device identity: Entra registration, Entra join, Entra hybrid join. [S540]
- Graph `device.trustType`: `Workplace` (registered), `AzureAd` (joined), `ServerAd` (hybrid joined). [S504]
- `dsregcmd /status` shows the state as AzureAdJoined / DomainJoined / EnterpriseJoined flags; registered state appears as WorkplaceJoined under User state. [S544]

## Facts
- A device identity is obtained by Microsoft Entra registration, Microsoft Entra join, or Microsoft Entra hybrid join; all three can coexist in one organization. [DOC S540]
- Entra hybrid join is described as an interim step on the road to Entra join. [DOC S540]
- Registered: device signed in with a local or Microsoft account; ownership user or organization; Windows 10+, macOS, iOS, Android, some Linux. [DOC S541]
- Joined: organizational account required to sign in; organization owned; all Windows 10/11 except Home; provisioning by OOBE, bulk enrollment or Autopilot. [DOC S542]
- Hybrid joined: joined to on-premises AD and Entra ID; Windows 10/11 except Home and Windows Server 2016/2019/2022; autojoin via Entra Connect or AD FS; needs periodic line of sight to domain controllers. [DOC S543]
- `trustType` values: `Workplace` (bring your own personal devices), `AzureAd` (cloud-only joined), `ServerAd` (on-premises domain joined devices joined to Entra ID). [DOC S504]
- dsregcmd state table: AzureAdJoined YES + DomainJoined NO = Entra joined; AzureAdJoined YES + DomainJoined YES = hybrid joined; DomainJoined only = domain joined; EnterpriseJoined YES + DomainJoined YES = on-premises DRS joined. [DOC S544]
- Mapping of dsregcmd states to `trustType`: joined -> `AzureAd`, hybrid joined -> `ServerAd`, registered -> `Workplace`. [DER S504,S544: same join type names in both docs]

## Reference
| Join type | trustType | dsregcmd | Ownership | Source |
|---|---|---|---|---|
| Entra registered | Workplace | WorkplaceJoined: YES (User state) | user or org | S504, S541, S544 |
| Entra joined | AzureAd | AzureAdJoined YES, DomainJoined NO | org | S504, S542, S544 |
| Entra hybrid joined | ServerAd | AzureAdJoined YES, DomainJoined YES | org | S504, S543, S544 |

- `entra/conditional-access-devices.md`: the Filter for devices `trustType`/`profileType` properties and the "Require Microsoft Entra hybrid joined device" grant control key off the join types and `trustType` values documented here.

## Examples
- `GET /v1.0/devices?$filter=trustType eq 'ServerAd'&$count=true` with header `ConsistencyLevel: eventual`.
