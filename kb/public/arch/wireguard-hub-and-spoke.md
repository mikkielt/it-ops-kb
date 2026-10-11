---
topic: arch/wireguard-hub-and-spoke
priority: P3
applies_to: "WireGuard with wg-quick on Linux hosts: one hub, many spokes"
retrieved_utc: 2026-10-11
sources: [S-fqnfqney, S-lyyx35bw]
status: complete
---

# WireGuard hub-and-spoke: wg-quick, AllowedIPs at the hub, PersistentKeepalive

## Summary
A WireGuard interface is configured from one file per interface; `wg-quick` turns the file into an interface, addresses and routes, and derives the routes from the peers' `AllowedIPs`. At a hub each spoke is a `[Peer]` whose `AllowedIPs` names the addresses behind it; a spoke behind NAT sets `PersistentKeepalive` so the hub can always reach it.

## Facts
- `wg-quick up` adds the interface, sets its addresses, MTU and routes and optionally runs pre/post scripts; `wg-quick down` removes it; `wg-quick strip` prints the file with the wg-quick-only options removed, suitable for `wg(8)`. [DOC S-fqnfqney]
- The configuration file is named after the interface plus `.conf`; a bare interface name is looked up as `/etc/wireguard/INTERFACE.conf` first, then in distribution-specific paths. [DOC S-fqnfqney]
- wg-quick infers routes from the peers' allowed IPs and adds them to the routing table; when one of them is the default route (`0.0.0.0/0` or `::/0`) it uses `ip rule` to override the default gateway. [DOC S-fqnfqney]
- Interface keys handled by wg-quick are `Address`, `DNS`, `MTU`, `Table` (`auto` default, `off` creates no routes), `PreUp`, `PostUp`, `PreDown`, `PostDown` (run by bash, `%i` expands to the interface name) and `SaveConfig`, which rewrites the file from the live state on shutdown. [DOC S-fqnfqney]
- The man page's multi-peer server example lists, per `[Peer]`, the peer's tunnel address as `/32` together with any subnet behind it in `AllowedIPs`, and sets `ListenPort`. [DOC S-fqnfqney]
- `AllowedIPs` is a list of IP/CIDR from which incoming traffic for that peer is accepted and to which outgoing traffic for that peer is sent; `0.0.0.0/0` and `::/0` match all IPv4 or IPv6, and the key may be given several times. [DOC S-lyyx35bw]
- `PrivateKey` is required and `ListenPort` optional (random if absent); `PresharedKey` is optional and adds a symmetric layer for post-quantum resistance. [DOC S-lyyx35bw]
- A peer's `Endpoint` is updated automatically to the source address and port of the latest correctly authenticated packet from it. [DOC S-lyyx35bw]
- `PersistentKeepalive` is an interval of 1 to 65535 seconds for an authenticated empty packet that keeps a stateful firewall or NAT mapping valid; the page gives 25 seconds as the example for an interface behind NAT, and 0 or `off` (the default) disables it. [DOC S-lyyx35bw]
- `wg syncconf IFACE FILE` reads the live configuration and changes only what differs, without disrupting peer sessions; it is less efficient than `setconf`. [DOC S-lyyx35bw]
- In a hub-and-spoke layout the hub has one `[Peer]` per spoke with that spoke's tunnel `/32` (plus a LAN prefix if the hub must route to it) in `AllowedIPs`; each spoke has one `[Peer]` for the hub whose `AllowedIPs` is the tunnel subnet; a spoke behind NAT sets `PersistentKeepalive` on its hub peer, so the hub needs no `Endpoint` for it. [DER S-lyyx35bw, S-fqnfqney: AllowedIPs is both route and filter, Endpoint is learned, keepalive holds the NAT mapping]
- Traffic from one spoke to another goes through the hub only if the first spoke's hub-peer `AllowedIPs` covers the other spoke's address, which is why a spoke lists the whole tunnel subnet; the kernel forwarding switch on the hub is not covered by the pages read. [DER S-lyyx35bw: AllowedIPs decides where outgoing traffic goes]
- An idempotent apply on a host is `wg syncconf wg0 <(wg-quick strip wg0)`: `strip` yields a file `wg` accepts and `syncconf` touches only the differences. [DER S-fqnfqney, S-lyyx35bw: strip output is for wg(8); syncconf applies differences only]

## Reference
| key | where | meaning | source |
|---|---|---|---|
| `AllowedIPs` | `[Peer]` | route and source filter for that peer | S-lyyx35bw |
| `PersistentKeepalive` | `[Peer]` | seconds between empty packets (NAT) | S-lyyx35bw |
| `Endpoint` | `[Peer]` | learned from authenticated packets | S-lyyx35bw |
| `Address`, `Table`, `PostUp` | `[Interface]` | wg-quick only | S-fqnfqney |

## Examples
- SNIPPET: hub with two spokes, placeholder keys and documentation addresses; context: wg-quick, `/etc/wireguard/wg0.conf` on the hub; checked: no [DER S-fqnfqney, S-lyyx35bw: peer sections per man page example]
```
[Interface]
Address = 192.0.2.1/24
ListenPort = 51820
PrivateKey = <hub private key>

[Peer]
PublicKey = <spoke 1 public key>
AllowedIPs = 192.0.2.2/32

[Peer]
PublicKey = <spoke 2 public key>
AllowedIPs = 192.0.2.3/32
```
