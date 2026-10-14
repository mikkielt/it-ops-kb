---
topic: windows/dhcp-failover
priority: P2
applies_to: "Windows Server DHCP Server role (IPv4 scopes); DhcpServer PowerShell module"
retrieved_utc: 2026-10-12
sources: [S-45mj3bt5, S-xl2d4tuq, S-x2hxgchj]
status: complete
---

# DHCP failover between two Windows Server DHCP servers

## Summary
- DHCP failover lets two Windows Server DHCP servers share IPv4 scopes and their active leases, so either can serve the same subnet; a failover relationship always has exactly two servers, and only DHCPv4 scopes qualify.
- Two modes: **load balance** (the default; both servers answer, 50:50 unless set otherwise) and **hot standby** (an active server answers, the standby takes over only when the active one is unavailable, with 5% of free addresses reserved by default).
- The **maximum client lead time (MCLT)** is the lease length the surviving server grants during an outage and the wait before it takes over the whole address pool; its default is 1 hour.
- Create a relationship with `Add-DhcpServerv4Failover` (load balance by default; `-ServerRole` and `-ReservePercent` select hot standby), run on the server that already holds the scopes; the scopes are created on the partner as part of the command.
- Scope changes are not replicated automatically: replicate them by hand, from the server whose settings you want to keep.
- Failover traffic uses TCP 647, and the two servers' clocks must stay within one minute.

## Facts
- To configure DHCP failover between two Windows Server DHCP servers, run `Add-DhcpServerv4Failover` (or the DHCP console's Configure Failover wizard) as an administrator on the server that holds the scopes, naming the partner server, a relationship name and the scope IDs; load balance is the default mode, and `-ServerRole` or `-ReservePercent` selects hot standby. [DOC S-xl2d4tuq, S-x2hxgchj]
- DHCP failover shares scope information, including all active leases, between two Microsoft DHCP servers over a **failover relationship**; the implementation follows the IETF DHCP failover protocol draft. [DOC S-45mj3bt5]
- A failover relationship is always between exactly two DHCP servers, but one server can have many relationships, each with a different partner; one server supports up to 31 failover relationships. [DOC S-45mj3bt5, S-xl2d4tuq]
- Failover supports DHCPv4 scopes only; DHCPv6 scopes cannot be failover-enabled. [DOC S-45mj3bt5]
- Both partners must run at least Windows Server 2016 on the overview page, while the management page lists at least Windows Server 2012 as the prerequisite; the pages differ. [DOC S-45mj3bt5, S-xl2d4tuq]
- Failover can be configured and changed without pausing, stopping or restarting the DHCP Server service; clients must be able to reach both partners, directly or through relay agents. [DOC S-45mj3bt5]
- **Hot standby:** the active server leases addresses and configuration for the scope; the standby issues leases only when the active server is unavailable. A server is active or standby per relationship, and by default the server used to create the relationship is the active one. [DOC S-45mj3bt5]
- In hot standby a percentage of the active server's free addresses is reserved for the standby; the default reserve is 5%. The reserve serves new leases while the active server is silent. [DOC S-45mj3bt5, S-x2hxgchj]
- A client that renews with a standby that cannot reach the active server keeps its address and receives a temporary lease for the MCLT, not the full scope lease time. [DOC S-45mj3bt5]
- When the standby has used up its reserve before the MCLT expires it stops issuing new leases and only renews; after the MCLT expires, it may use the whole pool for new leases, though in the communications-interrupted state it still does not use the entire pool. [DOC S-45mj3bt5]
- **Load balance** is the default mode: both servers serve a subnet at the same time and the default split is 50:50, configurable from 0% to 100%. The split hashes the client MAC address (RFC 3074) into buckets, one range of hash values per server. [DOC S-45mj3bt5, S-xl2d4tuq]
- In load balance mode, a server that loses its partner serves all clients; renewals from the partner's clients get the same address for the MCLT, new clients get leases from its own free pool and then the partner's pool, and in the partner-down state it takes 100% of the pool after the MCLT. [DOC S-45mj3bt5]
- Load balance suits two servers at the same site; hot standby suits a central standby backing a local server at a remote site. [DOC S-45mj3bt5]
- You can switch a relationship between the two modes, but one scope uses only one mode at a time; one server may use both modes for different scopes through several relationships. [DOC S-45mj3bt5]
- `Add-DhcpServerv4Failover` creates the relationship on both servers, and the `-ScopeId` values on the local server are set up identically on the partner; `-Name`, `-PartnerServer` and `-ScopeId` are mandatory. [DOC S-x2hxgchj]
- Mode follows the parameters: `-LoadBalancePercent` (default 50) belongs to the LoadBalance parameter set, which is the default, and `-ReservePercent` (default 5) and `-ServerRole` (`Active` or `Standby`) to the HotStandby set. [DOC S-x2hxgchj]
- `-ServerRole` is the role of the **local** server (the one in `-ComputerName`), with default `Active`, so the partner is then the standby; the example with `-ServerRole Standby` makes the local server the standby. [DOC S-x2hxgchj]
- The management page reads `-ServerRole Standby` the other way: its hot-standby example runs `Add-DhcpServerv4Failover -ComputerName dhcp1 ... -PartnerServer dhcp2 -ServerRole Standby` and says dhcp2, the partner, is the standby and dhcp1, the `-ComputerName` server, is the active one; the cmdlet reference's example 2 makes the local server the standby, so the pages disagree on which server `-ServerRole Standby` makes the standby, and the kb has not run it. [DOC S-x2hxgchj, S-xl2d4tuq]
- `-MaxClientLeadTime` defaults to 1 hour; `-AutoStateTransition` (default `False`) turns on the automatic move from COMMUNICATION INTERRUPTED to PARTNER DOWN when the `-StateSwitchInterval` timer expires, and giving `-StateSwitchInterval` sets it to `True`. [DOC S-x2hxgchj]
- `-SharedSecret` turns on message digest authentication; by default the cmdlet asks for confirmation because the secret may travel in plain text for remote management, and `-Force` suppresses that prompt. Without a secret authentication is off. [DOC S-x2hxgchj]
- The console wizard has message authentication enabled by default; clearing it means no shared secret is set. [DOC S-xl2d4tuq]
- Creation constraints: the scope must exist on the local server, must not already be failover-enabled and must not already exist on the partner (delete it there first); a scope that exists on both servers, as in a split scope, cannot be failover-enabled. [DOC S-xl2d4tuq]
- Relationships are viewed with `Get-DhcpServerv4Failover` (Mode, State, ServerRole, ReservePercent, MaxClientLeadTime, ScopeId, EnableAuth), edited with `Set-DhcpServerv4Failover` (for example `-LoadBalancePercent 70`) and deleted with `Remove-DhcpServerv4Failover`. [DOC S-xl2d4tuq]
- Deleting a relationship that still has scopes removes those scopes from the partner; they remain on the server where it was deleted. Removing the last scope from a relationship in the console does not delete the relationship. [DOC S-xl2d4tuq]
- Changes to a failover-enabled scope must be replicated manually; replication copies settings from the initiating server to the partner and overwrites the partner's, so start it from the server whose settings you want; with different operating system versions modify and start replication on the newer one. [DOC S-45mj3bt5]
- The related cmdlets listed for `Add-DhcpServerv4Failover` are `Add-DhcpServerv4FailoverScope`, `Remove-DhcpServerv4FailoverScope`, `Get-DhcpServerv4Failover`, `Set-DhcpServerv4Failover`, `Remove-DhcpServerv4Failover` and `Invoke-DhcpServerv4FailoverReplication`. [DOC S-x2hxgchj]
- Failover messages use TCP port 647; installing the DHCP Server role adds the inbound and outbound rules `Microsoft-Windows-DHCP-Failover-TCP-In` and `-Out` to Windows Firewall. [DOC S-45mj3bt5]
- Clocks must be synchronized: setup halts with a critical error when the servers differ by more than one minute, and a message whose timestamp is more than a minute off logs a critical event. [DOC S-45mj3bt5]
- With a cluster as partner, use the cluster's name or IP address, not a node's, or the primary enters communications interrupted when the service moves; a shared secret must be replicated to all cluster nodes. [DOC S-45mj3bt5]
- Both servers must use the same DNS credentials for dynamic updates made on behalf of clients, because a DNS name is owned by the server that created it. [DOC S-45mj3bt5]
- Clients must reach both servers: with relay agents give at least two helper addresses (one per server) when the servers are on another subnet; duplicate relay messages from a VRRP/HSRP pair can cause inconsistent lease durations. [DOC S-45mj3bt5]
- With policy-based assignment, load-balance address distribution is done per IP address range of the scope. [DOC S-45mj3bt5]
- Agent handling: creation, replication and deletion change two servers at once (deletion removes scopes from the partner), so show the plan first (`-WhatIf` is a supported parameter) and give the shared secret by a secret reference, not on a command line. [DER S-x2hxgchj, S-xl2d4tuq]

## Reference
| Setting | Parameter | Default | Source |
|---|---|---|---|
| Relationship name | `-Name` | none, mandatory | S-x2hxgchj |
| Partner | `-PartnerServer` | none, mandatory | S-x2hxgchj |
| Scopes | `-ScopeId` (list) | none, mandatory | S-x2hxgchj |
| Load balance share of the local server | `-LoadBalancePercent` | 50 | S-x2hxgchj |
| Hot standby reserve | `-ReservePercent` | 5 | S-x2hxgchj |
| Local server's role in hot standby | `-ServerRole` Active, Standby | Active | S-x2hxgchj |
| Maximum client lead time | `-MaxClientLeadTime` | 1 hour | S-x2hxgchj |
| Auto state transition | `-AutoStateTransition` | False | S-x2hxgchj |
| Interrupted to partner-down timer | `-StateSwitchInterval` | not set | S-x2hxgchj |
| Message authentication | `-SharedSecret` | off | S-x2hxgchj |
| Failover port | TCP 647 | | S-45mj3bt5 |
| Relationships per server | up to 31 | | S-xl2d4tuq |
| Clock skew limit | 1 minute | | S-45mj3bt5 |

## Examples
- Load balance (default, 50:50) for two scopes, authentication on, run on the server that holds the scopes: `Add-DhcpServerv4Failover -ComputerName "PL-SRV-0042.corp.example.com" -Name "site1-failover" -PartnerServer "PL-SRV-0043.corp.example.com" -ScopeId 192.0.2.0,198.51.100.0 -SharedSecret $secret`. [DOC S-xl2d4tuq, S-x2hxgchj]
- 70:30 load balance with a 2-hour MCLT and automatic partner-down after 2 hours: add `-LoadBalancePercent 70 -MaxClientLeadTime 2:00:00 -AutoStateTransition $True -StateSwitchInterval 2:00:00`. [DOC S-x2hxgchj]
- Hot standby with a 10% reserve, the partner as standby (the local server stays `Active`): `Add-DhcpServerv4Failover -ComputerName "PL-SRV-0042.corp.example.com" -Name "site1-standby" -PartnerServer "PL-SRV-0043.corp.example.com" -ScopeId 192.0.2.0 -ReservePercent 10`. [DOC S-x2hxgchj]
- Change an existing relationship to 70%: `Set-DhcpServerv4Failover -Name "site1-failover" -LoadBalancePercent 70`; list with `Get-DhcpServerv4Failover`; delete with `Remove-DhcpServerv4Failover -Name "site1-failover"`. [DOC S-xl2d4tuq]
