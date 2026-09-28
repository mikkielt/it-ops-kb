---
topic: gitlab/hosted-runners-windows
priority: P3
applies_to: "GitLab.com hosted runners on Windows (beta), docs at gitlab-org/gitlab master @a128b3dc and the runner image repository at main @6c5f0fef, both 2026-09-28"
retrieved_utc: 2026-09-28
sources: [S-klcfyqim, S-lfuz2ssn, S-6kqbpp6w, S-pq764ux2, S-4ph3gylm]
status: complete
---

# GitLab.com hosted runners on Windows

## Summary
GitLab.com offers hosted Windows runners on every tier, Free included, as a beta: a fresh Windows Server 2022
virtual machine per job, selected by the tag `saas-windows-medium-amd64`, running the job's `script` in PowerShell
as an elevated administrator. There is no Docker executor, so `image` and `services` do not apply; the tools come
preinstalled in the VM image (Python 3 through Chocolatey, MinGit, Docker, glab and others). A Windows job counts
against the namespace's compute quota at cost factor 1, the same as a small Linux runner, and a Free namespace gets
400 compute minutes a month. Expect about five minutes to provision a VM.

## Facts
- Hosted runners on Windows are available on the Free, Premium and Ultimate tiers, on GitLab.com only, with status Beta. [DOC S-klcfyqim]
- They autoscale by launching virtual machines on Google Cloud Platform, through a GitLab autoscaling driver for the custom executor. [DOC S-klcfyqim]
- One machine type: runner tag `saas-windows-medium-amd64`, 2 vCPUs, 7.5 GB memory, 75 GB storage. [DOC S-klcfyqim]
- The Windows VMs do not use the Docker executor, so a job cannot set `image` or `services`; Windows 2022 is the one version, marked GA. [DOC S-klcfyqim]
- PowerShell is configured as the shell, so a job's `script` section must be PowerShell commands. [DOC S-klcfyqim]
- Jobs run as an elevated admin process; the runner creates a new VM for each job and discards it afterwards. [DOC S-klcfyqim]
- Known issues listed for the beta: average VM provisioning of about five minutes, occasional unavailability for maintenance, jobs pending longer than on Linux runners, and possible breaking changes. [DOC S-klcfyqim]
- Preinstalled software named by the docs includes Chocolatey, Git, Git LFS, GitLab Runner, Docker, Python3, Node.js, Go, Ruby, OpenJDK, .NET Core SDK 3.1, curl, jq, 7-Zip and the GitLab CLI (`glab`). [DOC S-klcfyqim]
- The image installs Python through the Chocolatey package `python3`, pinned to version 3.13.2 at this commit. [CODE S-6kqbpp6w: cookbooks/preinstalled-software/attributes/default.rb#L26-L33]
- Git comes as MinGit, the minimal Git for Windows distribution, unpacked from its release zip with only its `cmd` directory added to `PATH`. [CODE S-pq764ux2: cookbooks/gitlab-runner-dependencies/recipes/git.rb#L6-L25]
- The MinGit version is 2.51.2 and its root `C:\Git` at this commit. [CODE S-4ph3gylm: cookbooks/gitlab-runner-dependencies/attributes/default.rb#L8-L14]
- The image's GitLab Runner is v19.3.0, in `C:\GitLab-Runner`. [CODE S-4ph3gylm: cookbooks/gitlab-runner-dependencies/attributes/default.rb#L1-L6]
- Cost factor on GitLab.com: Windows `medium` is 1 (Beta), the same as Linux x86-64 `small`; macOS M1 `medium` is 6 and Linux `medium` 2. [DOC S-lfuz2ssn]
- Compute usage per job is job duration in seconds / 60 x cost factor; the duration excludes time in the `created` and `pending` statuses. [DOC S-lfuz2ssn]
- On GitLab.com the compute quota is on by default to limit usage on Free namespaces: a Free namespace receives 400 compute minutes per month, paid tiers more, and extra minutes can be bought. [DOC S-lfuz2ssn]
- A Free private project can run a Windows test job without buying anything, within the 400 monthly minutes it shares with its Linux jobs; the job needs the `saas-windows-medium-amd64` tag, PowerShell `script` lines and the preinstalled `python` rather than an `image:`. [DER S-klcfyqim, S-lfuz2ssn: tier list, cost factor 1, Free quota, no Docker executor, PowerShell shell]
- A test that runs `.githooks` shell scripts or needs `bash` on the hosted Windows image cannot assume one: MinGit is the minimal distribution and only its `cmd` directory is on `PATH`. [DER S-pq764ux2, S-4ph3gylm: MinGit install and the `PATH` entry above]

## Reference
| Item | Value | Source |
|---|---|---|
| Runner tag | `saas-windows-medium-amd64` | S-klcfyqim |
| Machine | 2 vCPU, 7.5 GB RAM, 75 GB disk | S-klcfyqim |
| OS | Windows 2022 (GA) | S-klcfyqim |
| Shell | PowerShell | S-klcfyqim |
| Tier, status | Free, Premium, Ultimate; Beta | S-klcfyqim |
| Cost factor | 1 | S-lfuz2ssn |
| Free quota | 400 compute minutes per month | S-lfuz2ssn |
| Python | Chocolatey `python3` 3.13.2 | S-6kqbpp6w |
| Git | MinGit 2.51.2, `C:\Git\cmd` on `PATH` | S-pq764ux2 |

Related: `windows/gitlab-runner-windows.md` (a self-managed runner on Windows: service account, shells,
`safe.directory`); `gitlab/pipelines-rules.md` (`rules:` and `changes:` to limit when a job runs);
`python/stdlib-windows-portability.md` (what the Python tools must do to pass on such a job).

## Examples
- SNIPPET: a Windows test job on GitLab.com hosted runners; context: GitLab.com, any tier, hosted Windows runner beta; checked: no [DOC S-klcfyqim: tag, PowerShell script, no image]
```yaml
windows-tests:
  stage: test
  tags: [saas-windows-medium-amd64]
  script:
    - python --version
    - python -m pip install --quiet uv
    - python _tools/tests.py
```
