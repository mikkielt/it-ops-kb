---
topic: arch/incus-test-bed
priority: P3
applies_to: "Incus system containers and virtual machines as a Linux test bed: images, launch, exec, snapshot"
retrieved_utc: 2026-10-11
sources: [S-ffguw2vw, S-65ttwu4c, S-24r24rv2, S-jccjrysc]
status: partial
---

# Incus machine containers and VMs as a test bed

## Summary
Incus creates system containers and virtual machines from an image on a remote image server with one command (`incus launch`), runs commands in them with `incus exec`, and rolls them back with instance snapshots. That is the loop a configuration agent needs for a throwaway host: launch, apply, snapshot, apply again, restore.

## Facts
- `incus launch|init <image_server>:<image_name> <instance_name> [flags]` creates an instance: `init` only creates it, `launch` creates and starts it. [DOC S-ffguw2vw]
- A system container is `incus launch images:debian/12 NAME`; a virtual machine is the same with `--vm`, and `--device root,size=30GiB` sets a bigger root disk. [DOC S-ffguw2vw]
- Common flags are `--config` (for example `limits.cpu=1`, `limits.memory=192MiB`), `--device`, `--profile`, `--network`, `--storage` and `--target` (cluster member); a YAML configuration can be piped in on standard input. [DOC S-ffguw2vw]
- An application (OCI) container needs an OCI registry added as a remote first, then `incus launch oci-docker:hello-world --ephemeral --console` style names. [DOC S-ffguw2vw]
- The VM images of the `images` remote are pre-configured to start the Incus agent that makes `incus exec`, `incus file` and `incus info` work; other VMs need the agent installed by hand, and host and guest clocks must be reasonably in sync because the agent uses TLS certificates. [DOC S-ffguw2vw]
- `/etc/incus-agent.yml` in a Linux guest can turn agent features (`exec`, `files`, `guestapi`, `mounts`, `port-forward`, `metrics`, `state`) off; a missing or empty file enables all. [DOC S-ffguw2vw]
- Remote image servers that speak the simplestreams format are pure image servers, added with `incus remote add NAME URL --protocol=simplestreams`; an image name without a remote uses the default remote, shown by `incus remote get-default`. [DOC S-24r24rv2]
- `incus exec INSTANCE -- COMMAND` runs one command; it is interactive (a pseudo-terminal) when attached to a terminal and non-interactive (separate stdin, stdout, stderr pipes) from a script, with `--force-interactive` and `--force-noninteractive` to override. [DOC S-jccjrysc]
- Incus does not read `/etc/passwd` or `/etc/group` inside the instance, so `--user`, `--group` and `--cwd` take numeric ids and absolute paths; `--env NAME=VALUE` passes a variable to one exec and the instance option `environment.NAME` sets it for all. [DOC S-jccjrysc]
- `incus snapshot create INSTANCE [NAME]` saves the instance at a point in time and `incus snapshot restore INSTANCE SNAPSHOT` returns to it; snapshots live in the instance's storage pool, `--stateful` also captures a VM's running state, and `snapshots.schedule` takes snapshots on a schedule. [DOC S-65ttwu4c]
- A snapshot's configuration cannot be edited except its expiry date, and `incus snapshot delete INSTANCE NAME` removes one. [DOC S-65ttwu4c]
- Custom storage volumes attached to an instance are not part of its snapshot or backup. [DOC S-65ttwu4c]
- A test loop for an agent that applies host configuration is: `incus launch` the family's image, `incus exec` the agent's apply, `incus snapshot create`, apply a changed revision, `incus exec` the check, `incus snapshot restore` to retry; a container shares the host kernel, so settings that need their own kernel (audit lock, kernel modules, WireGuard, nftables hooks) need `--vm`. [DER S-ffguw2vw, S-jccjrysc, S-65ttwu4c: launch, exec, snapshot, restore; `--vm` gives a separate kernel]
- Which `images:` remote names exist for Ubuntu, AlmaLinux and Alpine (the pages show only `debian/12`) and how an image is pinned by fingerprint are not in the pages read. [UNK: logged in `_gaps.md`]

## Reference
| step | command | source |
|---|---|---|
| create and start | `incus launch images:debian/12 NAME [--vm]` | S-ffguw2vw |
| run | `incus exec NAME -- CMD` | S-jccjrysc |
| save | `incus snapshot create NAME [SNAP]` | S-65ttwu4c |
| roll back | `incus snapshot restore NAME SNAP` | S-65ttwu4c |

## Examples
- SNIPPET: throwaway Debian VM, snapshot before an apply, restore after; context: Incus with the default `images` remote; checked: no [DOC S-ffguw2vw, S-jccjrysc, S-65ttwu4c: launch, exec, snapshot commands as documented]
```
incus launch images:debian/12 PL-SRV-0042 --vm
incus snapshot create PL-SRV-0042 clean
incus exec PL-SRV-0042 -- /bin/sh -c 'echo apply step here'
incus snapshot restore PL-SRV-0042 clean
```
