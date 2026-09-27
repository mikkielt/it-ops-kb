---
topic: mecm/rbac
priority: P0
applies_to: "ConfigMgr current branch 2603"
retrieved_utc: 2026-09-26
sources: [S-wkltnypi, S-2z2zfj3l, S-sxtmngif, S-bprslswi, S1520, S-aaryifxi, S-hmjlvsck, S-qa267hnk, S1218, S-lef2ok5a, S-5v5lco6w, S-bjflxpet, S-z2hvjsvn, S-pl6uxpad, S-p2yatbfh]
status: partial
files: [mecm/rbac-permissions.csv]
---

# RBAC for CMPivot, client notification, Run Scripts and reads

## Summary
The relevant permissions sit on the **Collection** object class: Run CMPivot, Notify Resource, Run Script, Read and Read Resource. Script authoring and approval sit on **SMS Scripts** (Create, Approve).
Built-in roles holding each permission are documented only per feature page, and pages disagree on Notify Resource. No official full role-by-permission matrix was found; the RBA Viewer tool reads it from a live site.
The documented `GrantedOperations` bit table does not list Notify Resource, Run Script or Run CMPivot. Table: `mecm/rbac-permissions.csv`.

## Facts
- Run CMPivot is on Collection. 2107+ also needs Read on Inventory Reports. [DOC S-2z2zfj3l]
- The Security Administrator built-in role gained Run CMPivot, SMS Script Read and Inventory Report Read in 1906. [DOC S-sxtmngif]
- Run Scripts is a superset of Run CMPivot. [DOC S-sxtmngif]
- Notify Resource is on Collection (SMS_Collection) and is needed for all client notification actions (1810+). [DOC S-hmjlvsck,S-lef2ok5a]
- Built-in roles with Notify Resource are Full Administrator and Operations Administrator per the client notification section of S-hmjlvsck. S-lef2ok5a (1810) and the client-diagnostics section of S-hmjlvsck say Full Administrator and Infrastructure Administrator. [DOC S-hmjlvsck,S-lef2ok5a] (see conflicts)
- Run Script is on Collection. Built-in roles: Full Administrator, Infrastructure Administrator, Operations Administrator. [DOC S-hmjlvsck]
- Create on SMS Scripts is needed to import or author scripts, and Approve on SMS Scripts to approve or deny them. [DOC S1520]
- Microsoft's recommended Script Runners, Authors and Approvers roles are custom roles that you create by copying a role. They are not built in. [DOC S1520]
- Read Resource, Modify Resource and Delete Resource on a collection containing the device govern reading, setting and removing device custom properties via the AdminService. [DOC S-wkltnypi]
- Tenant-attach features need Read (plus Read Resource and Notify Resource for timeline, and Run CMPivot or Run Script for those features) on the Collection, plus an Intune role. [DOC S-bprslswi,S-aaryifxi,S-pl6uxpad]
- With Intune RBAC (2207+), the Intune permissions "Cloud attached devices\Run CMPivot query" and "\Run script" control cloud-console actions. [DOC S-5v5lco6w]
- Built-in role descriptions: Operations Administrator has all permissions except managing security. Read-only Analyst can view all objects. Full Administrator has all permissions. [DOC S1218]
- Built-in roles cannot be modified, other than adding administrative users to them. You copy one to create a custom role. [DOC S1218]
- `SMS_ARoleOperation.GrantedOperations` is a bit mask with 30 documented positions (0–29). The documented labels do not include Notify Resource, Run Script or Run CMPivot. [DOC S-z2hvjsvn]
- The bit positions for Notify Resource, Run Script and Run CMPivot are not documented. [UNK]
- The SQL security views v_SecuredObject, v_Roles, v_Admins, V_CategoryPermissions and v_SecuredScopePermissions expose permissions as decimal bit fields. In the 28-bit table in S-bjflxpet, Collection object key = 1. [DOC S-bjflxpet]

## Reference
See `mecm/rbac-permissions.csv` (21 rows: action, permission, object class, built-in roles, version note, source).

## Examples
Checking whether `jan.kowalski` may send a client operation to `PL-LT-00123` in collection `PS100123` (WMI route, SDK method `IsClientOperationAllowed(Type, TargetCollectionID, TargetResourceIDs[])`, S-qa267hnk). The Type number must come from `mecm/client-operation-types.csv`, where most values are UNK.
