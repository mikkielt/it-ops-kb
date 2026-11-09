---
topic: ad/domain-controller-count
priority: P3
applies_to: "Active Directory Domain Services: how many domain controllers a domain needs (Windows Server docs updated 2025-09)"
retrieved_utc: 2026-11-09
sources: [S-qussxgad, S-v6ttgkow, S-lzy377vk]
status: complete
---

# How many domain controllers a domain should have

## Summary
- Microsoft's Windows Server documentation says a production domain should always contain at least two domain controllers; the minimum does not change with domain size.
- Beyond two, the number comes from capacity (n) plus fault tolerance (n + 1 or more), and from sites; the page gives no per-user ratio.
- Do not put all domain controllers of a domain on one hypervisor host: that equals having one domain controller.

## Facts
- A production domain should always contain at least two domain controllers. [DOC S-v6ttgkow]
- Running all domain controllers of a forest or domain on the same hypervisor host is a single point of failure, "no different from using only one domain controller"; the page recommends multiple domain controllers on multiple platforms for redundancy and fault tolerance. [DOC S-v6ttgkow]
- Capacity planning first finds the capacity needed (n), then adds fault tolerance with n + 1, n + 2 or n + x; example: if two domain controllers are needed, plan for three so one can fail. [DOC S-qussxgad]
- Growth and fault tolerance are planned together: if one domain controller carries today's load but load doubles within a year, start with three; if budget does not allow, start with two and add a third after three or six months. [DOC S-qussxgad]
- Capacity planning is continuous, based on the daily peak busy period measured over 30-minute or one-hour intervals, and covers a hardware lifecycle of three to five years. [DOC S-qussxgad]
- Upper bound: Microsoft recommends at most 1,200 domain controllers per domain, so that SYSVOL can be recovered reliably after a disaster. [DOC S-lzy377vk]
- The pages read give no figure of domain controllers per number of users or computers for a small domain; the count that follows from them is two as a floor, plus what peak load and site layout add. [DER S-v6ttgkow, S-qussxgad: floor from the production rule, growth from n + 1]
- How it fits (small domain, one office): two domain controllers on separate hosts, a third when peak load needs two; roles are placed per `fsmo-roles.md`. [DER S-v6ttgkow, S-qussxgad: two as a floor, one more where capacity needs two]

## Reference
| Rule | Value | Source |
|---|---|---|
| Minimum for a production domain | 2 | S-v6ttgkow |
| Fault tolerance planning | n + 1 (or n + 2, n + x) | S-qussxgad |
| Recommended maximum per domain | 1,200 | S-lzy377vk |

## Examples
- None.
