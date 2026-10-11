---
topic: arch/cloudflare-tunnel-replicas-ssh-access
priority: P3
applies_to: "cloudflared tunnel replicas and Cloudflare Access / Cloudflare One for an SSH admin path"
retrieved_utc: 2026-10-11
sources: [S-cs6tyx3d, S-dbxfjxtf]
status: partial
---

# cloudflared tunnel replicas and an SSH admin path through Cloudflare

## Summary
A `cloudflared` process keeps four outbound-only connections to Cloudflare; extra instances of the same tunnel are replicas and give failover, not load steering. For SSH, Cloudflare One documents four routes that need no inbound port; the lightest needs only a tunnel on the server and Access.

## Facts
- A running tunnel makes four outbound-only connections from the origin to four different Cloudflare servers across at least two data centres, so one failed connection, server or data centre leaves the resource reachable. [DOC S-cs6tyx3d]
- Replicas are further `cloudflared` instances for the same tunnel; each opens four new connections, all point to the same tunnel, and when one host goes down the others keep serving. [DOC S-cs6tyx3d]
- Replicas do not support traffic steering (round-robin, hash): a request goes to the geographically closest replica, Cloudflare retries other replicas if that fails, and which one is used is not guaranteed. [DOC S-cs6tyx3d]
- The page lists three uses for replicas: more points of availability for one tunnel, failover nodes in the network, and changing a tunnel's configuration without downtime. [DOC S-cs6tyx3d]
- Load Balancers are the option for traffic steering; a typical setup creates one tunnel per data centre and one pool per tunnel, and private hostname routes are not compatible with Load Balancing, so replicas are the high-availability answer for them. [DOC S-cs6tyx3d]
- With Cloudflare One an SSH server can be offered over the internet without opening inbound ports, by four methods: client-side `cloudflared`, Access for Infrastructure, self-managed SSH keys and a browser-rendered terminal. [DOC S-dbxfjxtf]
- SSH with client-side `cloudflared` needs `cloudflared` on server and client plus Access, no Cloudflare One Client, about 15 to 30 minutes of setup, and uses the native terminal with identity-based authentication. [DOC S-dbxfjxtf]
- Access for Infrastructure needs a tunnel, the Cloudflare One Client or Cloudflare WAN on the client side, Gateway and Access, and gives SSH certificates with short-lived credentials, Access policies and command logging. [DOC S-dbxfjxtf]
- The browser-rendered SSH terminal needs only a tunnel on the server and Access and no SSH client or Cloudflare One Client; the page names it for quick administrative tasks. [DOC S-dbxfjxtf]
- Self-managed SSH keys keep the existing key infrastructure with network-level policy, needing a tunnel, a client on-ramp and Gateway but no client-side `cloudflared`. [DOC S-dbxfjxtf]
- Two `cloudflared` replicas of one tunnel on two hosts, each with only outbound access, give an admin path that survives the loss of one host; the SSH daemon stays bound to loopback or the tunnel's private network and the firewall opens no inbound SSH port. [DER S-cs6tyx3d, S-dbxfjxtf: replica failover, no inbound ports]
- The Access policy syntax, the token or credentials a replica uses to join the tunnel, and the plan limits are not covered by the two pages read. [UNK: logged in `_gaps.md`]

## Reference
| method | server side | client side | source |
|---|---|---|---|
| client-side cloudflared | tunnel, Access | cloudflared | S-dbxfjxtf |
| Access for Infrastructure | tunnel, Gateway, Access | Cloudflare One Client or WAN | S-dbxfjxtf |
| self-managed keys | tunnel, Gateway | client on-ramp | S-dbxfjxtf |
| browser terminal | tunnel, Access | browser | S-dbxfjxtf |

## Examples
No fixture data required (mechanism-only facts).
