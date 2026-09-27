---
topic: powerbi/row-level-security
priority: P2
applies_to: "Power BI service / Desktop, docs retrieved 2026-09-23"
retrieved_utc: 2026-09-26
sources: [S910, S908]
status: complete
---

# Power BI row-level security (RLS)

## Summary
RLS roles are DAX row filters defined in Power BI Desktop; members (users, security groups, mail-enabled/distribution groups)
are assigned in the service. RLS applies only to workspace Viewers (and to app/shared audiences), not to Admin, Member or
Contributor. Dynamic RLS uses `USERPRINCIPALNAME()` against a user-mapping table. Service principals cannot be role members.

## Facts
- RLS restricts data only for users with Viewer permissions; it does not apply to workspace Admin, Member or Contributor. [DOC S910]
- Viewers with Build permission are still filtered by RLS (for example in Analyze in Excel). [DOC S910]
- RLS supports Import and DirectQuery models (for example SQL Server); for Analysis Services live connections RLS is defined in the AS model. [DOC S910]
- Roles and DAX filters are defined in Power BI Desktop (Modeling > Manage roles); users cannot be assigned to roles in Desktop, only in the service. [DOC S910]
- A DAX role filter returns TRUE/FALSE per row; only TRUE rows are visible. [DOC S910]
- Role names cannot contain a comma. [DOC S910]
- In the service, `USERNAME()` and `USERPRINCIPALNAME()` both return the UPN; in Desktop `USERNAME()` returns `DOMAIN\user`. [DOC S910]
- Role members can be users, distribution groups, mail-enabled groups and Microsoft Entra security groups; Microsoft 365 groups are not supported. [DOC S910]
- Users with Contributor or higher see the Security option and can assign role members. [DOC S910]
- "Test as role" validates a role in the service; it does not work for DirectQuery models with SSO enabled, nor for paginated reports; it uses the tester's own identity for dynamic RLS. [DOC S910]
- Service principals cannot be added to an RLS role; RLS is not applied when a service principal is the effective identity. [DOC S910]
- Bidirectional security filtering is off by default and can be enabled on one relationship per table ("Apply security filter in both directions"). [DOC S910]
- `USERELATIONSHIP()` with RLS enabled may cause errors. [DOC S910]
- A user not assigned to any role on an RLS-enabled model typically sees no data. [DOC S910]
- With DirectQuery + Kerberos SSO to SQL Server, queries run as the Power BI user, so SQL Server permissions filter data at the source. [DOC S908]

## Reference
| DAX pattern [S910] | Use |
|---|---|
| `[Region] = "West"` | static |
| `[UserEmail] = USERPRINCIPALNAME()` | dynamic, per signed-in user via mapping table |
| `[AppRole] = CUSTOMDATA()` | embedded (app passes CustomData) |

## Examples
Role `SiteEngineers` on table `device` with filter `[owner_upn] = USERPRINCIPALNAME()`; members: Entra security group
`sg-device-viewers` (corp.example.com, example name). `jan.kowalski@corp.example.com` as Viewer sees only his rows.
