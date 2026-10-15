---
topic: agents/agent-sandboxes
priority: P3
applies_to: "Docker Sandboxes and the sbx CLI (docs.docker.com, read 2026-10-15); Kubernetes agent-sandbox v1.0.6 (Sandbox CRD agents.x-k8s.io/v1beta1); gVisor (runsc, gvisor.dev docs read 2026-10-15) and GKE Sandbox; Windows containers with Hyper-V isolation (Windows Server 2016 to 2025); Windows Sandbox and its CLI (Windows 11 24H2)"
retrieved_utc: 2026-10-15
sources: [S-pdqpy37l, S-4kmihytd, S-qfhwf42v, S-5hrbuirw, S-6rab4vhg, S-caegbfbq, S-bk6r64wx, S-eu4rwlo5, S-5jhx5xwe, S-bnpfuvpa, S-q7wv7okn, S-boekjhxx, S-4mp7uube, S-5hntws7z, S-3uzebbx5, S-woxmpwse, S-hlmmxoye, S-nuzkw2aa]
status: partial
---

# Sandboxes for coding agents beyond plain Docker (Docker Sandboxes, Kubernetes agent-sandbox, gVisor, Windows isolation)

## Summary
A plain container shares the host kernel, so four stronger boundaries are used to host a coding agent that runs code it wrote. Docker Sandboxes (the `sbx` CLI) run each agent in a microVM with its own Linux kernel and its own Docker Engine; only the workspace, a shared skills store, an SSH agent socket and policy-allowed outbound TCP cross the boundary, and a host-side proxy injects credentials so their values never enter the VM. The Kubernetes agent-sandbox project (SIG Apps) adds a `Sandbox` CRD and controller for one stateful pod with a stable identity, plus templates, claims and warm pools; it does not isolate anything itself but runs the pod under a sandbox runtime such as gVisor or Kata Containers chosen by `RuntimeClass`. gVisor is an application kernel in user space: its Sentry receives every system call the application makes, through a platform (systrap by default, or KVM), never passes them to the host kernel, and leaves file access to a separate Gofer; it lacks, among others, enforced in-sandbox resource limits, block-device filesystems, full iptables, KVM inside the sandbox and, by default, io_uring. On Windows, a Hyper-V isolated container gets its own kernel in a utility VM instead of sharing the host's, and Windows Sandbox is a disposable VM with its own kernel whose 24H2 CLI (`wsb`, an early preview) can start it, share a folder and run a command, but returns no output of that command.

## Facts

### Docker Sandboxes (sbx)
- Docker Sandboxes run AI coding agents in isolated environments either on the user's machine (local sandboxes) or on Docker-managed cloud compute (cloud sandboxes), both managed with the `sbx` CLI. [DOC S-pdqpy37l]
- The `sbx` CLI and local sandbox compute are free, commercial work included; cloud compute is a pay-as-you-go subscription, and organization-wide network, filesystem and MCP policies for local sandboxes are a separate paid subscription. [DOC S-pdqpy37l]
- Supported agents in local sandboxes are Claude Code, Codex, Copilot, Cursor, Devin, Docker Agent, Droid, Gemini, Kiro and OpenCode, plus `Shell`, an agent-less sandbox. [DOC S-caegbfbq]
- `sbx` needs neither Docker Desktop nor Docker Engine; on Windows it needs Windows 11 on 64-bit Intel or AMD, and local sandboxes need the Windows Hypervisor Platform feature (`Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -All`). [DOC S-6rab4vhg]
- On macOS it needs Sonoma 14 or later on Apple silicon; on Linux, Ubuntu 24.04 or later on 64-bit Intel, AMD or Arm, and for local sandboxes KVM turned on with the user in the `kvm` group; inside a VM or VDI the environment must support nested virtualization. [DOC S-6rab4vhg]
- Each sandbox runs in a lightweight microVM with its own Linux kernel; processes inside are invisible to the host and to other sandboxes, and `sbx rm` deletes the VM and everything in it. [DOC S-5hrbuirw]
- The agent runs as a non-root user with sudo inside the VM: the docs name the hypervisor boundary, not privilege separation inside the VM, as the isolation control. [DOC S-5hrbuirw]
- The security model names five layers: hypervisor (a separate kernel per sandbox), network (outbound TCP proxied through the host under a deny-by-default policy), Docker Engine (one engine per sandbox with no path to the host daemon), workspace and credential isolation. [DOC S-qfhwf42v]
- What crosses into the VM is the workspace directory, credentials injected as headers by the host-side proxy (their values never enter the VM), policy-allowed outbound TCP, a shared agent skills store and MCP gateway traffic; outside these the agent cannot reach the host filesystem, the host Docker daemon or the host network directly. [DOC S-qfhwf42v]
- Sandboxes cannot talk to each other over the network; outbound UDP is blocked unless the experimental UDP feature is on and policy allows it, and ICMP is blocked. [DOC S-qfhwf42v]
- Three workspace layouts exist: mountless (no host workspace; files stay in the sandbox), direct mount (the host directory read-write at the same absolute path, the `sbx run` default being the current directory), and a third layout that mounts the repository read-only at `/run/sandbox/source` while the agent works in its own copy inside the VM. [DOC S-4kmihytd]
- In direct mode the agent edits files that run implicitly during development (Git hooks, CI configuration, IDE tasks, AI project settings, Makefiles, `package.json` scripts); the docs say to review changes before running them and to check `.git/` hooks separately, since `git diff` does not show them. [DOC S-qfhwf42v]
- An authenticated request leaves the microVM carrying a sentinel value; the host proxy checks network policy, then swaps the sentinel for the real credential, which stays on the host throughout. [DOC S-4kmihytd]
- Only the forward proxy (HTTP and HTTPS) injects credentials; other TCP goes through a transparent proxy that enforces the same policy, and DNS goes through the sandbox's own resolver, which enforces it too. [DOC S-5hrbuirw]
- The host-side proxy follows the host's routing and OS system proxy by default; chaining to an upstream proxy is experimental and carries only HTTP and HTTPS, so the sandbox's traffic meets the same egress controls as other host applications. [DOC S-4kmihytd]
- Each sandbox keeps its own Docker daemon state, image cache and packages, which persist across stops and restarts until `sbx rm`; sandboxes share no images or layers. [DOC S-4kmihytd]
- MCP servers are reached through a host-side MCP gateway; local stdio MCP servers run on the host, not in the VM, and a server that starts a host process or container uses host permissions, so the docs say to treat local MCP servers as trusted host integrations. [DOC S-qfhwf42v]
- When `SSH_AUTH_SOCK` is set on the host, the SSH agent socket is forwarded into the microVM: processes inside can request signatures, while the private keys stay on the host. [DOC S-qfhwf42v]
- Processes in a local sandbox can write text to the host clipboard but cannot read existing clipboard text. [DOC S-5hrbuirw]
- The default network allowlist includes broad wildcards (the page names `*.googleapis.com`), and kits run their install commands as root inside the sandbox, with kit sources limited by default to Docker Hub. [DOC S-qfhwf42v]
- A shared agent skills store mounted read-write lets one sandbox change instructions or scripts an agent later uses in another, so participating sandboxes share one trust boundary; the pages disagree on whether that mount is read-only or read-write by default (see `_conflicts.md`). [DOC S-qfhwf42v]
- The Docker Sandboxes pages read state no GA, beta or preview label for the product; only single features (UDP egress, upstream proxy) are called experimental. [UNK]

### Kubernetes agent-sandbox (Sandbox CRD)
- agent-sandbox, a Kubernetes SIG Apps project, develops a `Sandbox` custom resource and controller for isolated, stateful, singleton workloads, naming AI agent runtimes and reinforcement learning as fits; its latest release read is v1.0.6 and the README's example uses `apiVersion: agents.x-k8s.io/v1beta1`. [DOC S-bk6r64wx]
- A `Sandbox` manages one stateful pod with a stable hostname and network identity, optional persistent storage that survives restarts, and lifecycle management (creation, scheduled deletion, pausing and resuming). [DOC S-bk6r64wx]
- Its extensions add `SandboxTemplate` (reusable templates), `SandboxClaim` (a sandbox taken from a warm pool without its configuration details) and `SandboxWarmPool` (pre-warmed sandboxes allocated quickly). [DOC S-bk6r64wx]
- The project calls itself a sandbox orchestrator: it delegates container isolation to sandbox runtimes such as gVisor or Kata Containers by running pods configured with a `RuntimeClass`. [DOC S-bk6r64wx]
- The threat model treats sandbox pods as untrusted and the controller and router as trusted, and names five trust boundaries: user to API (RBAC), control plane to workloads, cross-tenant, workload to node or host kernel, and workload to control plane. [DOC S-eu4rwlo5]
- Against container escape the threat model recommends a secure runtime through `RuntimeClass` in the pod template, adds that agent-sandbox implements no isolation itself, and lets administrators enforce it with a `SandboxTemplate` that sets `runtimeClassName`. [DOC S-eu4rwlo5]
- With a `SandboxTemplate`, the default managed NetworkPolicy mode allows ingress only from the Sandbox Router and egress only to the public internet (RFC 1918 networks and cloud metadata endpoints blocked); it also blocks sidecar ports unless the template allows them. [DOC S-eu4rwlo5]
- Pods made from a `SandboxTemplate` get `automountServiceAccountToken` defaulted to `false`; for a bare `Sandbox` the threat model leaves it to admission control such as `ValidatingAdmissionPolicy`. [DOC S-eu4rwlo5]
- The optional Sandbox Router is an HTTP reverse proxy that routes SDK and external traffic to sandbox pods by header (`X-Sandbox-ID`), for runtimes such as gVisor and Kata Containers where pod port-forwarding is unavailable; Go and Python SDKs (`k8s-agent-sandbox` on PyPI) drive the API. [DOC S-bk6r64wx]
- Deleting the CRDs cascade-deletes every custom resource of those types in all namespaces; the README pins an install to a release manifest for production and GitOps. [DOC S-bk6r64wx]

### gVisor: how system calls are intercepted
- gVisor is an application kernel written in Go that runs in user space and implements a Linux-like interface; its OCI runtime `runsc` works with Docker and Kubernetes. [DOC S-5jhx5xwe]
- gVisor intercepts the application's system calls and acts as the guest kernel without virtualized hardware; the docs set it apart from syscall filters such as seccomp-bpf and from VMs, at the cost of reduced compatibility and higher per-system-call overhead. [DOC S-5jhx5xwe]
- Each sandbox has its own Sentry, the kernel that runs the containers and services their system calls, signals, memory management and threading; it does not pass system calls through to the host kernel and cannot open files itself. [DOC S-5jhx5xwe]
- Each container has its own Gofer, a host process that mediates file system access for the Sentry over 9P on a socket or shared memory, while the Sentry runs in a restricted seccomp container without file system access. [DOC S-5jhx5xwe]
- A platform redirects each system call to the Sentry: systrap (the default since mid-2023) uses seccomp's `SECCOMP_RET_TRAP`, so the kernel sends `SIGSYS` to the thread and gVisor handles the call; KVM lets the Sentry act as guest OS and VMM and runs best on bare metal; ptrace (`PTRACE_SYSEMU`) is no longer supported and expected to be removed. [DOC S-bnpfuvpa]
- systrap is the better choice inside a VM or on a machine without virtualization support, and often outperforms KVM in a nested VM. [DOC S-bnpfuvpa]
- gVisor may perform poorly for system-call-heavy workloads, and machine-level virtualization is the one that struggles with high density. [DOC S-5jhx5xwe]
- gVisor releases run the regression tests of the Python, Java, Node.js, PHP and Go runtimes, so most programs in those languages work. [DOC S-q7wv7okn]

### gVisor: unsupported workloads and features
- gVisor implements only a subset of the Linux syscall ABI, and does not implement every system call, `/proc` file or `/sys` file; its docs say the only real way to know whether a workload runs is to try it. [DOC S-q7wv7okn]
- In-sandbox cgroups account for CPU and memory but do not enforce limits; a host cgroup can limit the whole sandbox, but not processes competing inside it. [DOC S-q7wv7okn]
- Block-device filesystems (fat32, ext3, ext4) cannot be mounted inside the sandbox; a host can mount them and expose the result. [DOC S-q7wv7okn]
- iptables is only partly supported (enough to run Docker in gVisor), device files for custom hardware are not supported apart from NVIDIA GPUs and TPUs, io_uring is off by default and limited to basic I/O when on, nftables is similarly limited, and KVM cannot be used from inside the sandbox. [DOC S-q7wv7okn]
- In GKE Sandbox, gVisor-sandboxed pods do not support privileged containers, raw block volumes, port forwarding (`kubectl port-forward`), hostPath storage or sysctl settings, and apply CPU and memory limits only for Guaranteed or Burstable pods with limits on every container. [DOC S-boekjhxx]
- In GKE Sandbox, neither gVisor nor microVM sandboxes support seccomp, AppArmor, SELinux, the No New Privileges flag, bidirectional mount propagation or the `procMount` security context; services outside the boundary, CSI drivers included, need protecting on their own. [DOC S-boekjhxx]

### Windows: Hyper-V isolated containers
- Windows containers run in process isolation (sharing the host kernel, with per-container file system, registry, network port, process and thread ID and Object Manager namespaces) or Hyper-V isolation, in which each container runs in an optimized VM and effectively gets its own kernel. [DOC S-4mp7uube]
- Both modes use the same images and are managed the same way; Docker selects one with `--isolation=hyperv` or `--isolation=process`, Windows Server defaults to process isolation and Windows 10 Pro and Enterprise to Hyper-V isolation. [DOC S-4mp7uube]
- A process in a Hyper-V isolated container is not visible on the host; the host sees only the `vmwp` worker process of the VM that holds the container. [DOC S-4mp7uube]
- Mapped files or volumes, named pipes, mapped ports, a shared network namespace and host device visibility pierce the boundary and must be asked for deliberately; shared memory, shared synchronization objects and shared process namespaces are not supported. [DOC S-4mp7uube]

### Windows Sandbox as an agent host
- Windows Sandbox is a disposable VM with its own kernel; each launch is fresh, closing it deletes all state, and only one instance runs at a time. [DOC S-woxmpwse]
- From Windows 11 24H2 the Microsoft Store version of Windows Sandbox adds an early version of command-line support, called a preview on the versions page. [DOC S-3uzebbx5]
- The `wsb` CLI has `start` (returns the sandbox id; `--config` takes the configuration as a string), `list`, `exec`, `stop`, `share` (a host folder, writable only with `--allow-write`), `connect` (a remote desktop session) and `ip`; `--raw` formats output as JSON. [DOC S-5hntws7z]
- `wsb exec` runs a command and returns its exit code, but there is no process I/O support, so the command's output cannot be read back; `--run-as` is `System` or `ExistingLogin`, and `ExistingLogin` needs an active session opened with `connect`. [DOC S-5hntws7z]
- Networking is on by default and a writable mapped folder's changes persist on the host, where apps inside the sandbox can compromise them. [DOC S-hlmmxoye]

### How it fits
- The four options sit at different boundaries: Docker Sandboxes and Windows Sandbox give the agent its own kernel in a VM, a Hyper-V isolated container gives each container its own kernel in a utility VM, gVisor keeps the host kernel but puts a user-space kernel in front of it, and agent-sandbox orchestrates pods and inherits whichever of these its `RuntimeClass` names. [DER S-5hrbuirw, S-4mp7uube, S-woxmpwse, S-5jhx5xwe, S-bk6r64wx: each page's stated isolation mechanism]
- Docker Sandboxes' credential path is the same design as Anthropic's secure-deployment guide: a proxy outside the boundary injects the credential, so the agent never holds it, which meets this kb's rule that secrets stay out of a child process's environment. [DER S-4kmihytd, S-nuzkw2aa: sentinel swapped at the host proxy; proxy-injected credentials never reach the agent]
- In every option the shared workspace is the remaining path to the host: Docker Sandboxes' direct mount, a Windows container's mapped volume and a writable Windows Sandbox folder all carry the agent's writes out, so the read-only repository layout, a read-only mapping or review before running changed files is what keeps a prompt-injected edit off the host. [DER S-qfhwf42v, S-4mp7uube, S-hlmmxoye: each names mapped folders as the boundary's crossing]
- Windows Sandbox's CLI is a poor fit for an agent loop that reads command output, since `wsb exec` returns only the exit code: output has to come back through a shared folder, and only one sandbox runs per host, so parallel agents need separate machines. [DER S-5hntws7z, S-woxmpwse: no process I/O; one instance at a time]
- A gVisor-backed agent sandbox on Kubernetes cannot rely on in-pod cgroups to stop one runaway process from starving others in the same sandbox, so the per-pod resource limits that agent-sandbox's threat model asks for are the control. [DER S-q7wv7okn, S-eu4rwlo5: limits not enforced inside the sandbox; resources.limits in the pod template]

## Reference

| Option | Boundary | Kernel | Credentials | Release status (as read) |
|---|---|---|---|---|
| Docker Sandboxes (`sbx`) | microVM per sandbox | own Linux kernel | host proxy swaps a sentinel | not labelled (UNK) |
| Kubernetes agent-sandbox | pod under a `RuntimeClass` runtime | that runtime's | not handled; token automount off via template | v1.0.6, API `v1beta1` |
| gVisor (`runsc`) | user-space application kernel | host kernel behind the Sentry | not handled | not stated on the pages read |
| Hyper-V isolated Windows container | utility VM per container | own Windows kernel | not handled | Windows Server 2016 to 2025 |
| Windows Sandbox (`wsb` CLI) | disposable VM | own Windows kernel | not handled | CLI early preview, Windows 11 24H2 |

- Related: `claude/agent-sdk.md` (Anthropic's secure-deployment guide: sandbox runtime, Docker, gVisor, microVMs, the credential proxy), `claude/ci-and-headless.md` (Claude Code's own Bash sandbox), `windows/windows-sandbox.md` (`.wsb` options and the WindowsSandbox policies), `windows/gitlab-runner-windows.md` (Hyper-V isolated containers on a CI runner), `agents/foundry-agent-service.md` (Hyper-V isolated code interpreter sessions).
- Docker Sandboxes: https://docs.docker.com/ai/sandboxes/; agent-sandbox: https://github.com/kubernetes-sigs/agent-sandbox; gVisor: https://gvisor.dev/docs/; Windows isolation modes: https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/hyperv-container

## Examples
- SNIPPET: a `Sandbox` for a coding agent under gVisor, without a service account token; context: agent-sandbox v1.0.6 installed and a `RuntimeClass` named `gvisor` on the cluster (the name is a placeholder), image a placeholder; checked: no [DER S-bk6r64wx, S-eu4rwlo5: Sandbox example from the README; runtimeClassName and automountServiceAccountToken from the threat model]

```yaml
apiVersion: agents.x-k8s.io/v1beta1
kind: Sandbox
metadata:
  name: coding-agent-pl-lt-00123
spec:
  podTemplate:
    spec:
      runtimeClassName: gvisor
      automountServiceAccountToken: false
      containers:
      - name: agent
        image: registry.corp.example.com/agents/coding-agent:1.0
        resources:
          limits:
            cpu: "2"
            memory: 4Gi
```

- SNIPPET: start a Windows Sandbox without networking, share a host folder read-only and run a script in it; context: Windows 11 24H2 with the Store version of Windows Sandbox, the id is the one `wsb start` prints, paths are placeholders; checked: no [DER S-5hntws7z, S-hlmmxoye: start, share and exec from the CLI page; the `Disable` value from the .wsb options, where the CLI page's own example writes `Disabled`]

```cmd
wsb start --config "<Configuration><Networking>Disable</Networking></Configuration>"
wsb share --id 00000000-0000-0000-0000-000000000000 -f C:\work\task -s C:\task
wsb exec --id 00000000-0000-0000-0000-000000000000 -c "powershell -File C:\task\run.ps1" -r System
```
