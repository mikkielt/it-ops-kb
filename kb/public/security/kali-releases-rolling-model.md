---
topic: security/kali-releases-rolling-model
priority: P3
applies_to: "Kali Linux release cadence and version names, the kali-rolling and kali-last-snapshot branches, how kali-dev feeds them, the Debian relation and update policy, and what the 2026.2 release changed"
retrieved_utc: 2026-10-15
sources: [S-2p6jllwx, S-5455keob, S-srhdbl23, S-4fzpivdx, S-nc74uv2o, S-a3rz5fyq, S-esfl6hqk, S-o6curntz]
status: partial
---

# Kali Linux releases and the rolling model

## Summary
Kali is a Debian-testing derivative that is a rolling distribution: `kali-rolling` is updated continuously and a numbered release (`2026.2`) is a dated image refresh of it, about four a year. A second complete branch, `kali-last-snapshot`, is frozen at each release for hosts that want updates only at release time. Package sources and metapackages are in `security/kali-apt-sources-metapackages.md`, images and verification in `security/kali-images-verification-builds.md`, the default account and VMs in `security/kali-default-account-vm-containers.md`. Read from kali.org on 2026-10-15; the newest release listed there is 2026.2.

## Facts
- Kali 2.0 (11 August 2015) was the release that made Kali a rolling distribution, and 2016.1 (21 January 2016) was the first "Kali Rolling" release; releases since are numbered `<year>.<n>`. [DOC S-2p6jllwx]
- The page lists 2026.2 as the newest release (29 June 2026, kernel 6.19, Xfce 4.20.7), then 2026.1 (24 March 2026, kernel 6.18) and 2025.4 (12 December 2025, kernel 6.16). [DOC S-2p6jllwx]
- A letter suffix marks a point fix of the same release: 2025.1c (28 April 2025) differs from 2025.1 only by a `kali-archive-keyring` that holds the new Automatic Archive Signing Key, and 2023.2a fixed a UEFI issue in the base images. [DOC S-2p6jllwx]
- The project says Kali releases four times a year on a loose quarterly schedule, and that a user on `kali-last-snapshot` receives no updates until the next release. [DOC S-nc74uv2o]
- `kali-rolling` is the default branch and is continuously updated; it pulls from `kali-dev` once packages are verified, and a package bug can still slip in because of bugs in Debian testing. [DOC S-5455keob]
- `kali-last-snapshot` is a complete branch that is frozen: at each release `kali-rolling` is merged into it, so its users get all updates between versioned releases (2020.3 to 2020.4) at once. [DOC S-5455keob]
- `kali-experimental` (work-in-progress packages) and `kali-bleeding-edge` (packages auto-updated from upstream git, "potential to be very unstable") are partial branches: they do not hold a complete distribution and are meant to be added to `kali-rolling`. [DOC S-5455keob]
- `kali-dev` is Debian testing with the Kali packages from `kali-dev-only` force-injected (Kali wins over Debian); it is public on every mirror, is not for end users and regularly breaks. [DOC S-5455keob]
- A tool copies packages from `kali-dev` to `kali-rolling` only once they are verified installable; the page states these checks include no functional testing. [DOC S-5455keob]
- The chain of branches is `debian-experimental` → `debian-unstable` → `debian-testing` → `kali-dev` → `kali-rolling` → `kali-last-snapshot`; `kali-rolling-only` holds Kali packages that need to reach `kali-rolling` quickly. [DOC S-5455keob]
- Kali has used Debian testing as the starter for `kali-rolling` since January 2016, and Debian stable's "point release" is the counterpart of `kali-last-snapshot`. [DOC S-5455keob]
- The distribution is based on Debian Testing: most packages are imported as-is from Debian, and some newer ones come from Debian Unstable or Experimental. [DOC S-srhdbl23]
- A package Kali has forked is kept in a Git repository with a `debian` branch, and Kali packaging follows Debian Policy with the aim of contributing packages back to Debian. [DOC S-srhdbl23]
- Security updates for imported packages arrive at essentially the same time as in Debian; packages Kali added are supported on a best-effort basis by the Kali team. [DOC S-4fzpivdx]
- The update guidance is to check every few days or weeks, to make sure the tools work before an engagement and not to update during one; the update is `apt update` then `apt full-upgrade -y`. [DOC S-nc74uv2o]
- Kali 2026.2 (29 June 2026) moved the default APT configuration to `/etc/apt/sources.list.d/kali.sources`, left existing systems unchanged, dropped graphics firmware from pre-built VM images and from installs detected as VMs, and brought GNOME 50 and KDE Plasma 6.6. [DOC S-a3rz5fyq]
- The 2026.2 post says the polkit and xrdp updates need a reboot (otherwise GUI applications started as root fail), and that for Hyper-V Enhanced Session Mode the fix is to toggle it again in `kali-tweaks`. [DOC S-a3rz5fyq]
- Kali 2026.2 ships kernel 6.19 to avoid breaking NVIDIA DKMS drivers; the 7.0 kernel is in `kali-experimental` and is also stated as available in `kali-rolling`. [DOC S-a3rz5fyq]
- The 2026.2 post announces a consistency pass over all image build scripts for 2026.3, and warns that CI pipelines or workflows may need tweaking; it also notes weekly automated builds with newer packages, not QA'd like release images. [DOC S-a3rz5fyq]
- At commit `e86f126b` the `kali-meta` changelog's newest entry is version `2026.3.9`, uploaded to `kali-dev` on 14 September 2026: the metapackages already carry the 2026.3 series although the release page lists 2026.2 as newest. [CODE S-esfl6hqk: debian/changelog#L1-L5]
- An agent that manages a Kali host should treat `kali-rolling` as moving state: pin by image or release date for repeatability, `kali-last-snapshot` for slower change, and `full-upgrade` as a change that can need a reboot. [DER S-5455keob, S-nc74uv2o, S-a3rz5fyq: branches, update steps, reboot note]
- Whether a 2026.3 image release is published, and the kernel `kali-rolling` installs by default today, were not read. [UNK: logged in `_gaps.md`]

## Reference
| branch | kind | use |
|---|---|---|
| `kali-rolling` | complete | default; continuously updated |
| `kali-last-snapshot` | complete | frozen at each release |
| `kali-experimental` | partial | work in progress; add to rolling |
| `kali-bleeding-edge` | partial | auto-updated from upstream git |
| `kali-dev`, `kali-dev-only`, `kali-rolling-only`, `kali-debian-picks` | development | not for end users |

Related: `security/kali-apt-sources-metapackages.md`, `security/kali-images-verification-builds.md`, `security/kali-default-account-vm-containers.md`, `security/linux-patching-and-pins.md`.

## Examples
- SNIPPET: switch a host to the frozen branch and apply it; context: Kali with the deb822 `kali.sources` file, as a sudo user; checked: no [DER S-o6curntz, S-nc74uv2o: the docs' sed one-liner and update commands]
```
sudo sed -i 's/^Suites: .*/Suites: kali-last-snapshot/' /etc/apt/sources.list.d/kali.sources
sudo apt update
sudo apt full-upgrade -y
```
