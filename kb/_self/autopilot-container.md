# Autopilot in a container: plan

Planned, not built: nothing on this page exists yet as code, an image or a setting, and every command below is a plan to be run for the first time at the stage that names it. The page says how the autopilot's sprint runner (`kb/_self/tools.md`, The autopilot runner) would run in a Docker container on the operator's Mac instead of as the operator or as a separate OS user, what that isolates, what it does not, and how to roll it out with the stages of `kb/_self/autopilot-test.md`. It makes no choice for the operator: each recommendation is marked, and the operator-only gates are in section 11.

Placeholders only: `SP-xxxxxxxx` is a sprint, `ST-xxxxxxxx` an item, `git.corp.example.com` the integration remote's host, `model-api.example.com` the model API's host (the real list comes from Claude Code's own network documentation when the allow-list is written), `PL-LT-00123` the Mac, `jan.kowalski` the operator, `sha256:<digest>` and `<version>` a pin a person fills in from a build they have read. Line numbers are those of the tree when this page was written; the symbol named beside each is the stable reference.

**The shape in one paragraph.** One container, `kb-autopilot`, holds a fresh clone of the integration project in a named volume, the pinned toolchain of section 2 and up to two runners (`bl_base.MAX_RUNNERS`, `_tools/bl_base.py:379`). The manager session, the operator's own clone and `/loop` stay on the host. The manager reaches the runner only through `docker exec` and the integration remote: the container holds the deploy key of section 4, mounts nothing of the operator's, and can reach only the hosts of section 5. Two runners share one container on purpose (section 7): the host's lock files assume one process table and one `/tmp`.

## 1. Why a container instead of a separate OS user

The runner is an agent that can edit code and then run it, so the text rules (permission lists, the edit guard, refusals inside the tools) are defence in depth, and the real boundary is what the process can reach (`kb/_self/autopilot-test.md:5`). Today's reach is the operator's: the runner child inherits the manager's user, home and network, minus the environment variables `child_env` drops (`_tools/autopilot.py:203-212`, names at `:106-113`), and with an ssh command that offers the runner's deploy key alone (`runner_ssh_command`, `:190-200`). Two ways to narrow it:

| | a separate OS user | a container |
|---|---|---|
| Files of the operator's home | isolated by Unix permissions, if the home is `0700` and no ACL or group opens it; a mistake in one `chmod` undoes it | not mounted at all; absent, not merely unreadable |
| The operator's ssh agent, keychain, tokens | the agent socket is the operator's: another user cannot use it, but the new user's own login keychain and home hold whatever is put there | none present; the only credentials are the files of section 4 |
| Network | none: the user has the host's whole network, GitHub and the public home included | a user-defined network with an allow-list (section 5): the public home is unreachable by topology, not by the worktree's failing push url (`block_public_push`, `_tools/autopilot.py:214-222`) alone |
| Processes | separate uid, same process table: the operator's `ps` shows them; a runaway still loads the host | own process table, `--pids-limit`, `--memory`, `--cpus`: the load is capped (section 6) |
| Resources | no per-user cap short of `ulimit` | cgroup caps through Docker |
| What the runner can write | the new user's home and any path the host's permissions open | the clone volume, `/tmp` and the home volume: nothing else (section 3) |
| Setup | needs the administrator's password to create the user; a person must do it | needs Docker; the image is built from text kept in the repository |
| Reproducible and disposable | state accumulates in the home | remove the container and the volumes and the next start is from nothing |
| macOS file-event and disk cost | worktrees and test copies churn the host's file system (the observed fseventsd growth) | churn stays inside Docker's VM when volumes are used (section 9); the VM adds its own memory and disk |
| Kernel | shared, as it is | shared with a Linux VM's kernel, not the Mac's; an escape from the container reaches the VM and, through Docker Desktop's integrations, possibly more (see below) |

**What a container does not isolate.** These limits hold whatever the image:

- **A volume it can write.** The clone volume is the runner's to rewrite: the whole working tree, `.git`, the worktrees, `_cache/`. A bad edit lands there, and from there reaches the integration remote through the lane the kb already uses. The container bounds where the runner writes, not what it writes; the guards of `_tools/kb_hook.py:453-496` and the gate classes still apply as before (`kb/_self/backlog.md:355-364`, Enforced today and Not enforced).
- **The network it is allowed.** Whatever the allow-list names is reachable by every process in the container, the agent's shell commands included. Allowed hosts are the exfiltration paths.
- **The model credential it must hold.** `claude` needs a key or token (`MODEL_AUTH_PREFIXES`, `_tools/autopilot.py:113`) and the agent's own processes run as the same user with the same environment, so a prompt-injected agent can use or send it. The credential's scope and spend limit are the boundary, not the container.
- **The deploy key it must hold.** The key is a file the runner's user reads. Its scope on the forge is the boundary (`kb/_self/autopilot-test.md:15`): it may push `main` and `code/*`, which are protected for it, and it is never on GitHub; on a GitLab plan without push rules it can also push any branch name that is not protected (`kb/_self/autopilot-test.md:28-32`, the limits after the pre-run checklist).
- **A kernel or Docker daemon escape.** A container shares its VM's kernel; a kernel bug or a mounted `docker.sock` ends the isolation. The plan mounts no socket, runs as an unprivileged user and drops capabilities, which lowers the odds and does not remove the class.
- **Docker Desktop's VM and its cost.** On macOS the container runs in a VM that has its own memory, swap and disk image and its own file-sharing layer (live docs, not in the kb: https://docs.docker.com/desktop/settings-and-maintenance/settings/, read 2026-10-03). The VM's memory and disk are a second budget to size and a second thing that can fill.
- **The model's own behaviour.** A container does not stop an agent from landing a bad change inside what it may write; the review of the digest and of `git log origin/main` stays the check after the fact (`kb/_self/backlog.md:364`).

## 2. The image

The image holds what the runner executes and nothing of the host: a Debian base, Python 3 (the tools are standard library only), git, an ssh client, `procps` (the tools call `ps`: `bl_base.pid_alive`, `_tools/bl_base.py:391-400`, and `tests.pid_alive`, `_tools/tests.py:242-251`), the `claude` CLI, `glab`, and a non-root user. `lsof` is not needed: `live_processes` reads `/proc` where it exists (`_tools/bl_land.py:370-395`), and the Linux image has it. No Node, compiler, Docker client, cloud CLI or the operator's dotfiles beyond what the `claude` CLI needs to run.

Every input is pinned: the base by digest, packages by an apt snapshot date, the CLI and `glab` by version and checksum. The pins are placeholders here; a person reads the real digests and checksums from the sources at build time and the implementing change commits the filled file. Suggested home when built: `container/autopilot/Dockerfile` (a code-lane path; not under `_tools/`). Network is needed only at build time (package index, the CLI's and `glab`'s release hosts); the running container does not need them.

```dockerfile
# syntax=docker/dockerfile:1
# Autopilot runner image: planned text, every <placeholder> filled by a person from a read source.
FROM debian:bookworm-slim@sha256:<digest>

ARG APT_SNAPSHOT=<YYYYMMDDTHHMMSSZ>
ARG CLAUDE_VERSION=<version>
ARG CLAUDE_SHA256=<digest>
ARG GLAB_VERSION=<version>
ARG GLAB_SHA256=<digest>

# Packages from a dated snapshot of the distribution archive, so a rebuild gives the same files.
RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ bookworm main\n' "$APT_SNAPSHOT" \
      > /etc/apt/sources.list \
 && rm -f /etc/apt/sources.list.d/* \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends \
      python3=<version> git=<version> openssh-client=<version> procps=<version> ca-certificates=<version> curl=<version> \
 && rm -rf /var/lib/apt/lists/*

# The claude CLI at one version, verified against a checksum read from the release's own listing.
# The install method (native binary or the package manager) is confirmed against Claude Code's docs when this is built.
RUN curl -fsSL "<release-url-of-claude-${CLAUDE_VERSION}>" -o /usr/local/bin/claude \
 && echo "${CLAUDE_SHA256}  /usr/local/bin/claude" | sha256sum -c - \
 && chmod 0755 /usr/local/bin/claude

RUN curl -fsSL "<release-url-of-glab-${GLAB_VERSION}>" -o /tmp/glab.tgz \
 && echo "${GLAB_SHA256}  /tmp/glab.tgz" | sha256sum -c - \
 && tar -xzf /tmp/glab.tgz -C /usr/local/bin --strip-components=1 bin/glab \
 && rm /tmp/glab.tgz

# No curl after the build: the running container does not fetch anything.
RUN apt-get purge -y curl && apt-get autoremove -y

# One unprivileged user; the home and the clone are volumes made at start, owned by it.
RUN useradd --uid 10001 --create-home --home-dir /home/<user> --shell /bin/bash runner \
 && mkdir -p /work && chown runner:runner /work

# ssh that gives up: a hung connection must not hold a runner (section 7).
COPY --chown=root:root ssh_config /etc/ssh/ssh_config.d/50-runner.conf
COPY --chown=root:root entrypoint.sh /usr/local/bin/entrypoint.sh

USER runner
WORKDIR /work
ENV HOME=/home/<user> \
    KB_HOST_LOCK_DIR=/tmp \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1 \
    CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1
# The entrypoint reads the secret files (section 4), clones the project into /work on first start, then waits.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
```

The `ssh_config` file holds `ConnectTimeout 20`, `ServerAliveInterval 15`, `ServerAliveCountMax 4` and `BatchMode yes`, for the integration remote's host only. The key itself comes from the runner: `child_env` gives the child `GIT_SSH_COMMAND` with `-F /etc/ssh/ssh_config` (the system config alone, which on Debian includes `ssh_config.d/*.conf`, so these timeouts apply and no `~/.ssh/config` does), `IdentitiesOnly yes`, no agent and `-i` the key `KB_RUNNER_DEPLOY_KEY` names (`runner_ssh_command`, `_tools/autopilot.py:190-200`). Why: `prepare_worktree` and `reset_worktree` fetch through `bl_base.git`, which has no time bound (`_tools/bl_base.py:298-302`, `_tools/autopilot.py:232`, `:283`); only the fetches and pushes of `land` and `sync --push` are bounded (`_tools/kg_lock.py:72-95`, 120 s by default). The overnight 40-minute wait on a hung `git fetch` ssh child was that kind of wait; a bound in ssh itself covers the unbounded callers.

Notes on the text above, each to check when built:

- `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` strips credentials from every subprocess the CLI starts, and makes every command in a Linux session run sandboxed (`kb/public/claude/ci-and-headless.md:65`, DOC). Its effect on `git`, `glab` and the tools must be proved at Stage 1: if a sandboxed command cannot reach the secret files or `/tmp` locks, the variable is dropped and the limits above carry the boundary.
- The entrypoint script and `ssh_config` are two more small files kept beside the Dockerfile; their text is not on this page.
- `HOME` on the image is a path, not a store: section 3 mounts the volume over it.

## 3. Mounts

Nothing of the host is mounted except single secret files. In particular, never: the operator's home, the ssh agent socket, the main checkout, `docker.sock`, a directory of another clone.

| mount | what | mode | why |
|---|---|---|---|
| named volume `ap-clone` at `/work` | a fresh clone of the integration project only, made inside the container at first start from the integration remote with the deploy key (`--single-branch`); holds `.git`, `.claude/worktrees/runner-SP`, the workers' worktrees and `_cache/autopilot/` | writable | the runner's one place to work; a fresh clone holds no `_cache/` or `_private/` of the operator's (`kb/_self/hosting.md:144`) |
| named volume `ap-home` at `/home/<user>` | the CLI's config and sessions, the git config, the pre-seeded workspace trust entry, the `glab` config the entrypoint writes | writable | `claude` writes its home; the trust entry must exist (see below) |
| `tmpfs` at `/tmp` | the host lock and runner records (`kb-main.lock`, `kb-tests.lock`, `kb-runner.<pid>.json`), pytest's scratch | writable, size-capped, counted in the memory limit | a stop clears it, so no lock record survives its process (sections 7, 8) |
| file `runner_deploy_key` | the deploy key | read-only, a single file at `/run/secrets/runner_deploy_key`, `0400`, owned by uid 10001 | section 4 |
| file `forge_token` | the forge token for `glab` | read-only, single file | section 4 |
| file `model_auth` | the model credential | read-only, single file | section 4 |
| the image's root file system | everything else | read-only (`--read-only`) | a runner cannot alter the tools baked into the image or add a binary outside the volumes |

**What is read-only, and what cannot be.** The image, the secret files, `ssh_config` and the proxy's configuration (section 5) are read-only. The tools (`_tools/`) and the kb root are not: they are the clone's files, the runner edits them as items require, and the child runs the worktree's own `_tools/` (`python3 _tools/backlog.py ...` in `.claude/worktrees/runner-SP`). A read-only trusted copy of the tools for the supervising `autopilot.py` process would need a root other than its own file's place (`ROOT`, `_tools/autopilot.py:88`), which the command does not take; it is a later code change and an `agents-rule` gate (section 11). Until then the edit guard decides what the child may rewrite of the tools: `_tools/kb_hook.py`, `_tools/kbpy`, `.githooks/`, the settings, hooks, plugin files and the files of the `agents-rule` and `push` classes are denied to a headless run, and the rest of `_tools/` is not (`_tools/kb_hook.py:315`, `:433-440`, `_tools/bl_authority.py:75-90`).

**Why a named volume and not a bind mount.** Docker's own documentation: volumes are managed by Docker, and bind mounts depend on the host's directory structure and OS (live docs, not in the kb: https://docs.docker.com/engine/storage/volumes/, read 2026-10-03). On a Mac the practical reason is section 9: a bind mount puts the runner's churn on the host file system. The cost is that the host cannot browse the clone; reading it is `docker exec` or a `docker cp`.

**Workspace trust and the plugin.** Until the workspace is trusted, the project's allow rules in `.claude/settings.json` are not used and every command waits for a prompt (`kb/_self/backlog.md:296`, live docs cited there). A headless `-p` run has no one to answer. The trust entry for `/work/...` and the approvals of the project's MCP servers are written into the config in `ap-home` by a one-time interactive `claude` session as the first step of Stage 1 (below) or by seeding the file; which of the two the CLI honours is not confirmed here (the list at the end).

## 4. Credentials

Three secrets, all passed as files at start, none baked into an image, none in an `ENV` line, none in `docker run -e`, none printed.

| secret | what it is | how it arrives | what reads it |
|---|---|---|---|
| deploy key | the runner's own key `kb-runner` on the integration project: `main` and `code/*` are protected for it, other unprotected branch names are not bounded on a plan without push rules, and it is never on GitHub (`kb/_self/autopilot-test.md:15`, pre-run checklist step 1); its private half lives outside every clone | a read-only single-file mount at `/run/secrets/runner_deploy_key`, with `KB_RUNNER_DEPLOY_KEY=/run/secrets/runner_deploy_key` in the runner's environment (a path, not the key); without it the runner looks at `~/.config/it-ops-kb/runner_deploy_key`, and with no file there `GIT_SSH_COMMAND` offers no key, so a push fails instead of using another identity (`runner_ssh_command`, `_tools/autopilot.py:190-200`) | `git` and `ssh` of the runner's child, through `GIT_SSH_COMMAND`; `child_env` drops `GIT_SSH`, so nothing overrides it |
| forge token | the project token `glab` needs for `glab api` reads and the merge of a `code/<id>` merge request (`_tools/bl_land.py:517`, `:910-911`) | read-only single file; the entrypoint writes `glab`'s config in the tmpfs or `ap-home` from it, since `child_env` drops `GITLAB_TOKEN`, `GLAB_TOKEN` and `GITLAB_ACCESS_TOKEN` (`_tools/autopilot.py:106-108`) | `glab` |
| model credential | `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | read-only single file; the entrypoint exports it into the runner process only (`exec env VAR=... python3 ...` from the file's content), so it is not in the container's configured environment | the `claude` child |

**Never in `docker inspect`.** A value set with `-e` or an `ENV` line is part of the container's configuration, which anyone with access to the Docker API reads. The plan never uses them for a secret; Docker's Compose documentation advises the same, naming exposure by environment variables as the risk and file-based secrets, bind-mounted as single files at `/run/secrets/<name>`, as the alternative (live docs, not in the kb: https://docs.docker.com/compose/how-tos/use-secrets/, read 2026-10-03). Swarm secrets are held in an in-memory file system (https://docs.docker.com/engine/swarm/secrets/, same date) but need Swarm mode, which one container does not justify. A plain `docker run` form of a read-only single-file mount gives the same file with no Swarm; the file is the host's, so it lives in a directory outside every clone, `0400`, and the operator keeps it out of backups and the repository. The `/proc/<pid>/environ` of the runner and its child still holds the model credential for processes of the same user: that is the limit in section 1, and the reason it is a dedicated credential.

**The Claude auth path.** `child_env` keeps `CLAUDE_` and `ANTHROPIC_` names although they match the credential pattern, because the child needs them to authenticate (`_tools/autopilot.py:110-113`). The model credential must therefore be in the environment of `python3 _tools/autopilot.py runner start`, which is why the entrypoint exports it for that process. Which credential: an API key or a subscription token. The kb's fact: a shared, organisation-wide secret should use an API key, since an OAuth token from `claude setup-token` is tied to the individual who ran it (`kb/public/claude/ci-and-headless.md:47`, DOC S1801). Recommendation (section 11): a dedicated API key for the runner, in a workspace of its own with the lowest limits the console allows (whether the console offers a spend limit is not confirmed here).

**The Bedrock token stays stripped.** `AWS_BEARER_TOKEN_BEDROCK` matches `CREDENTIAL_RE` (`token`, `_tools/autopilot.py:110`) and does not start with `CLAUDE_` or `ANTHROPIC_`, so `child_env` drops it: the runner's child never holds it, in a container as on the host. `AWS_SECRET_ACCESS_KEY` is dropped the same way (`secret`); `AWS_ACCESS_KEY_ID` matches nothing and passes, so a static-key Bedrock setup would be half-stripped and fail. `CLAUDE_CODE_USE_BEDROCK` keeps its `CLAUDE_` prefix and passes (`kb/public/claude/settings-and-scopes.md:34`, DOC S-inpjf36q). So: a container run on Bedrock does not work today and the plan does not make it work. The way model auth reaches the container is the direct API of the previous paragraph. Letting the child hold a Bedrock token would be an edit of `_tools/autopilot.py`, an `agents-rule` file (`_tools/bl_authority.py:27-40`), so the operator's gate (section 11), not a plan step.

**Public home credentials: none.** The container's clone is made with the integration remote only, and `kb.publishRemote` is never set in it. `block_public_push` then does nothing, by design (`_tools/autopilot.py:218-220`, `_tools/kbpublic.py:96-98`), and there is no public remote to push to; `kbgit.py publish` is denied by the settings in any case (`.claude/settings.json:156`). A clone without a publish remote has no public home (`kb/_self/git.md:71`).

## 5. Network

Allowed, by name, and nothing else:

| host | for | when |
|---|---|---|
| `git.corp.example.com` (the integration remote: fetch, push, and the forge's API for `glab`) | `git fetch`, `sync --push`, the `code/<id>` push, `glab api`, `glab mr merge` | always |
| `model-api.example.com` (the model API's host, plus any further host Claude Code needs to run: take the list from its network documentation when writing the allow-list) | the model | always |
| package index, the CLI's and `glab`'s release hosts | image build | build time only; never from the running container |

Denied, whatever else changes: GitHub and the public home (the publish remote's host), every other forge host, a registry, `docker.sock`'s network. Telemetry and error reporting are switched off in the image (`DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING`, `kb/public/claude/settings-and-scopes.md:36`, DOC S-a2zimsvk), so the allow-list need not carry their hosts; whether the CLI runs with them blocked and no other switch is checked at Stage 1.

**Two ways to enforce an allow-list.**

- **An internal network and an egress proxy.** Create a user-defined network with `--internal` for the runner: Docker documents that containers on it talk to each other but not to external networks, with no default route and firewall rules blocking outside traffic (live docs, not in the kb: https://docs.docker.com/reference/cli/docker/network/create/, read 2026-10-03). A second container, the proxy, is attached to that network and to an ordinary one; it forwards `CONNECT` only to the allow-listed hostnames and ports, and the runner's `HTTPS_PROXY` points at it. Enforcement is topology: a process that ignores the proxy has no route. The proxy does the name resolution, so the runner needs no external DNS. Ssh to the forge goes through the proxy with a `ProxyCommand` that issues `CONNECT` for port 22 of the forge's host (the proxy must allow that one pair; many default to port 443 only), or the remote is HTTPS with a token. Cost: one more container and its configuration, to be kept read-only and pinned like the image.
- **Firewall rules.** Allow only the addresses of the two hosts in rules in the Linux VM that Docker runs in (for example the chain Docker leaves for operator rules) or inside the container's network namespace by an init step with `NET_ADMIN`. Names are not addresses: the model API sits behind addresses that change, so the rules need a refresh job and break when it lags; on Docker Desktop the VM is not a place an operator edits by hand, and `NET_ADMIN` inside the runner container lets its own processes edit the same rules.

**Recommendation (section 11):** the internal network plus the egress proxy. It enforces by hostname, needs no capability in the runner container and no access to the VM, and a mistake fails closed (no route). The firewall form is the fallback on a Linux host where the operator owns the rules.

## 6. Resource limits

The overnight host (the observed incident on the operator's Mac, not a measurement of this plan): load average above 40, swap 19.5 of 20 GB used, and `fseventsd` at 7.3 GB and growing with file churn (many worktrees, many test copies). Two causes sit under that: more processes than cores (two runners, each with up to four workers, each running tests with several pytest workers: `kb/_self/tools.md:122`, `_tools/tests.py:412`), and unbounded memory, which swap then hid until it ran out.

Suggested values, all **to be measured** at Stage 1 and Stage 3 and fixed from the peak that `docker stats` shows over a whole run, not trusted from here:

| limit | suggested | reasoning |
|---|---|---|
| `--cpus` | 4 | caps the container's CPU time at four cores whatever its process count; the host keeps the rest. The runnable count may still read high inside the VM: the cap protects the Mac, not the load figure |
| `--memory` and `--memory-swap` | 10g, both equal | with the two equal, the container has no swap (live docs, not in the kb: https://docs.docker.com/engine/containers/resource_constraints/, read 2026-10-03), so an overrun is an OOM kill of this container, a failed run with cause `error`, instead of the host's swap filling. 10g is a first guess: a headless `claude` child, up to four workers' `claude`, git and pytest workers, plus the `/tmp` tmpfs |
| `--pids-limit` | 1024 | a fork-bomb and runaway-test cap, well above the few hundred processes two runners and their workers hold. The flag is not documented on the page above (it said nothing of it); that it exists in the Docker Engine in use is checked at Stage 0 |
| `/tmp` tmpfs `size=` | 3g, inside the memory limit | pytest scratch and the kb copies that tests make; capped so churn cannot grow without bound |
| `KB_TEST_WORKERS` | 2 | `tests.py` shares the CPUs among the runs live on the host (`_tools/tests.py:412`); one container sees four, so two workers per run keeps two runs from asking for more than the cap |
| the Docker Desktop VM's memory | the container limit plus 4 GiB | the VM runs the Docker engine, the proxy and page cache; the setting defaults to half of the Mac's memory and swap defaults to 1 GB (live docs, https://docs.docker.com/desktop/settings-and-maintenance/settings/, read 2026-10-03) |

Keep `KB_RUNNER_DEADLINE_S` and `KB_RUNNER_MAX_TURNS` at their defaults (`DEADLINE_S` six hours, `MAX_TURNS` 500, `_tools/autopilot.py:122-123`): they bound a run's time and turns, and the container limits bound its memory and processes. A stopped container is the last bound.

## 7. Tick and runner mapping

The manager session, its clone and `/loop 15m /kb-autopilot` stay on the host and are unchanged (`.claude/skills/kb-autopilot/SKILL.md:9`). Its commands that touch a runner become `docker exec` into the container. A small wrapper script kept in the repository would do the translation; it does not exist, and writing it edits files the guard protects only if it lives under `_tools/` (a gate, section 11).

| the autopilot's command | in the container |
|---|---|
| `python3 _tools/autopilot.py runner start SP [--landed K]` (SKILL step 5.3, in the background) | start the container once (`docker run` of section 3, `--init`, `sleep infinity`), then `docker exec -d kb-autopilot ... python3 _tools/autopilot.py runner start SP`; the runner, its worktree `.claude/worktrees/runner-SP` and its `_cache/autopilot/SP/` are then in the container's clone |
| `python3 _tools/autopilot.py status`, `runner-status SP` | `docker exec kb-autopilot ...` the same command, printed by the host. It must not be read from the host: a status.json that says `running` while no live record exists is listed as `ended error` (`_tools/autopilot.py` docstring, `status`), and the host sees no record of a runner whose process lives in the VM |
| `python3 _tools/autopilot.py runner reset SP` | `docker exec`: the same stash of uncommitted files and `stale/SP-STAMP` branch, now in the volume (`_tools/autopilot.py:267-300`) |
| stop a runner (`kill N`, SIGTERM) | `docker exec` of `kill N` for the pid the exec'd `status` prints: the runner ends the child's whole tree and writes `error` / `runner ended by SIGTERM` (`ends_on_signals`, `_tools/autopilot.py:431-454`). `docker stop kb-autopilot` is the stop of everything: SIGTERM to PID 1, then SIGKILL after Docker's timeout; the runners do not get to write their status, so `status` lists them `ended error` afterwards |
| `python3 _tools/backlog.py bounds stop --sprint SP` (SKILL step 5) | reads `_cache/autopilot/SP/runs.jsonl` of the clone it runs in (`_tools/bl_base.py:426-470`): run it by `docker exec` too, or the host's clone has no run history and no-progress is never seen. Unsolved by the code today: it needs the wrapper |
| `python3 _tools/backlog.py procs --record N` (SKILL step 5.4) | not used for a container runner (see below) |
| container start, status, stop, reset of the container itself | `docker start`, `docker ps`, `docker stop`, and for a clean slate `docker rm` plus removing the two volumes |

**What `backlog.py procs` and the live-process check of `land` see.** The host's `procs` lists processes whose working directory lies in a checkout of the host clone (`_tools/bl_procs.py:1-23`, `unsupported` at `:47-54`): the container's processes run in the VM's process table, in the container's own clone, so the host never lists them. Inside the container (`docker exec`) both work on `/proc`: `procs` lists the container's processes and `live_processes` of `land` reads `/proc/<pid>/cwd` (`_tools/bl_land.py:381-395`); `ps` is in the image for the liveness checks. Two consequences. First, `procs --end` there ends only an owned orphan, and it calls a process an orphan when its parent is pid 1 or less, gone, or named `init`, `systemd` or `launchd` (`_tools/bl_procs.py:230-234`). A runner started by `docker exec -d` has a parent outside the container's process table and is expected to read as parent 0, so, if it had been recorded with `procs --record`, `procs --end` would end a healthy runner after its grace: this is why a container runner is not recorded, and the check of this expectation is a Stage 1 item. Second, an orphan the container's PID 1 adopts is reaped only when PID 1 is an init: the plan runs with `--init`.

**The locks, which stop serialising across containers.** The host main lock `kb-main.lock` and the test lock `kb-tests.lock` are exclusive-create files in `KB_HOST_LOCK_DIR`, default `/tmp` (`_tools/kg_lock.py:21`, `:141-160`; `_tools/tests.py:229-239`), and the runners' records `kb-runner.<pid>.json` are in the same directory (`_tools/bl_base.py:382-388`). A container has its own `/tmp` and its own process table, so:

- Inside one container the locks work as on a host: two runners, one `/tmp`, one pid space. That is the reason the plan keeps both runners in the one container.
- Between the container and the host's manager they do nothing: the manager's `kbgit.py sync --push` (each tick syncs) and a runner's `land` in the container each hold a lock the other cannot see. Nothing is corrupted by this: both rebase on the integration `main` as fetched and push, and the forge refuses a push that is not a fast-forward of `main` (and, with the protection of the checklist's step 1, a force-push), so the losing side fails with a rejected push (exit 1) and is retried, the same outcome as a lost race today. What is lost is the queue: a tick can find its sync rejected while a land is mid-push.
- `MAX_RUNNERS` (two runners per host) is no longer enforced across containers: a second container would count its own two. One container only.
- A lock directory shared between the host and the container, or between two containers, by a bind mount is the obvious replacement and is not safe: the holder's liveness is a `ps -p PID` in the asker's own process table (`_tools/tests.py:242-251`, used by `kg_lock`), and a pid from another namespace is "not running" there, so a live lock would be judged stale and cleared. It would need the host's process table (`--pid=host`), which on Docker Desktop is the VM's and not the Mac's, and which removes the process isolation this plan is for.
- What could replace them is a lock the forge keeps: a create-only ref on the integration remote that a pusher takes before it moves `main` and deletes after, so one holder exists across every clone and container. It is a change to `kg_lock.py`, a `push`-class file (`_tools/bl_authority.py:27-30`), and a gate (section 11); it is not needed to start. Recommendation: first stages run one runner and have the manager not run `sync --push` while the runner lands (read from `status`), accept retries after that, and file the remote lock if the rejected pushes are more than a nuisance.

## 8. Worktree removal by land, with the container as the only writer

Everything the runner and its workers write is in the container's volume, by one user, so the uid and ownership problems of a bind mount (files owned by the host user in one place and by a numeric uid in another) do not arise. The worktrees are `.claude/worktrees/runner-SP` (the runner's, `_tools/autopilot.py:140-141`) and the workers' `agent-*` under the clone's `.claude/worktrees/` (`_tools/bl_land.py:363-365`).

- **Who removes a finished worker's worktree.** The same code as on the host: `backlog.py land`, run by the runner's orchestrating child inside the container, calls `release_worker_worktree` (`_tools/bl_land.py:417-467`), which runs `git worktree remove`, never `--force`, since the agent's shell may not (`.claude/settings.json:160` denies it). It removes only a clean worktree under the `.claude/worktrees/` of the clone it runs in (the toplevel of that directory, so the runner's own linked worktree counts) on the item's `work/<id>` branch that is locked by a Claude Code agent (a lock reason starting `claude agent`) or unlocked and named `agent-*` or by the item id, never the one `land` runs in, and unlocks a locked one first. Branches follow: `delete_landed_branch` (`:470-486`).
- **Locked worktrees after a stop.** A container that is stopped or killed leaves worktrees locked by agents that no longer exist. `land` treats the lock's reason, not a pid, so it unlocks and removes them on the next pass (the prefix check, `:363`, `:426-428`).
- **Stray processes.** `live_processes` refuses a worktree whose directory has a live process and names each pid (`:370-414`). After a container restart there is none, which removes the case where a ghost from an earlier session blocks a removal. While running, a worker's leftover background process is found by `/proc` as on any Linux host.
- **A runner worktree that is dirty or diverged.** `runner reset SP` inside the container: stash, a `stale/SP-STAMP` branch, remove, then the next `runner start` makes it afresh at the integration `main` (`_tools/autopilot.py:267-300`).
- **Closing a sprint.** `backlog.py close` removes `_cache/autopilot/SP` of the clone it runs in (`_tools/bl_land.py:795-801`, `prune_runner_cache`); closing from the host's clone would not remove the container's cache, so the close of a container-run sprint is also a `docker exec` or the volume is cleaned by the wrapper's reset. Unconfirmed in the code: that the manager's close step runs in the clone that holds the cache.
- **Where the worker worktrees go.** A worker's `isolation: "worktree"` branches from the `HEAD` of the checkout the orchestrator runs in (`.claude/settings.json:5-7`, `.claude/skills/kb-sprint/SKILL.md:48`); the code that removes them expects them under the main clone's `.claude/worktrees/`. That the Agent tool, run from the runner worktree inside the container, puts them there is the host's behaviour and is not confirmed for the container (the list at the end).

## 9. macOS: Docker Desktop, Colima or a Linux VM

| | Docker Desktop | Colima | a Linux VM or host |
|---|---|---|---|
| what it is | Docker's own VM and app; file sharing is VirtioFS by default, gRPC FUSE the alternative; VM memory, swap, CPU and disk limits are settings (live docs, https://docs.docker.com/desktop/settings-and-maintenance/settings/, read 2026-10-03) | a command-line VM runner for Docker on macOS: not read in this research, not in the kb, so nothing about it is claimed here | the engine on a Linux machine the operator owns (a VM on the Mac, or another box) |
| file-event cost of a bind mount | the Mac's file system is shared into the VM; writes to a bind-mounted directory are writes on the Mac's volume, so the Mac's `fseventsd` sees them. Docker's documentation says VirtioFS cut file-system operation time by up to 98% and says nothing of host file-event cost: that is not documented and is measured at Stage 1 | not claimed | none on the Mac: no Mac file system under the work |
| memory and disk | the VM takes its memory and a disk image up to the set limit, and Resource Saver can stop the VM when idle (which stops runners) | not claimed | the machine's own |
| fits this plan | yes, with named volumes | to be checked if chosen | the cleanest: it removes the Mac's file events and the VM layer |

**Recommendation (section 11): named volumes, not bind mounts, for the clone and the home.** A named volume lives in the VM's disk, so the runner's churn (worktrees, test copies, `.git` writes) never touches the Mac's `fseventsd`. Expected, not proved: the growth observed on the host came from churn on the Mac's own file system, and removing that churn is what Stage 1 measures by reading `fseventsd`'s resident size before and after a run (`kb/_self/autopilot-test.md:17`, pre-run checklist step 3). The trade-offs: the host cannot open the clone in an editor or a file browser; reading it is `docker exec` or `docker cp`; the volume is inside the VM's disk image, so it counts against the disk limit and is lost with a reset of Docker Desktop (the integration remote holds everything landed; an unpushed commit in the volume is the only loss, and `status` lists a runner's worktree so that nothing is left unlanded unnoticed); and a Mac's backups do not hold it.

Set the VM's resources deliberately: memory as in section 6, a disk limit above the clone, the tests' copies and the images, and Resource Saver off for the unattended run so the VM does not stop between ticks. The VM is a second place that fills: its disk usage is read in the settings or with `docker system df`, and a `docker system prune` is the operator's.

## 10. Staged rollout

The stages are those of `kb/_self/autopilot-test.md` (Test plan, `:36-91`), numbered and named as there. Its pre-run checklist row 2 (`:16`) asks for the container; this plan is what makes that row true. The order: a container check first (Stage C below, outside the numbered stages), then Stage 0 to Stage 8 with the runner in the container, each with the additions below, then Stage 9, which repeats Stages 1 to 3 on a container rebuilt from nothing. Every stage keeps its own command, expected result and abort condition; the lines below only add. A stage's abort is the plan's abort: stop the container (`docker stop`), record the failure, go no further.

**Stage C. The container itself, before Stage 0.** Run once; nothing here starts a runner.

- `docker run` of the image with the limits of section 6 and the mounts of section 3, then `docker exec kb-autopilot id`: expect uid 10001, no `docker` binary, no `sudo`. Abort on uid 0.
- `docker inspect kb-autopilot` shows no secret value: search the output for the first and last characters of each secret; expected none. Abort on any hit.
- From inside: `ls /host`, `ls /Users`, `echo "$SSH_AUTH_SOCK"`, `ssh-add -l`: expect no such directory, an empty value, and no agent. A write to `/usr/local/bin` fails (read-only root).
- Network: from inside, a fetch of the integration remote works (`git ls-remote origin HEAD` prints a commit id, `kb/_self/backlog.md:291`); a connection to the public home's host, to GitHub and to any host off the list is refused by the proxy, and a connection that bypasses the proxy has no route. Abort if one off-list host answers.
- `docker stats` once idle for the baseline of section 6; `fseventsd`'s resident size noted from Activity Monitor.

**Stage 0. Dry look at a tick.** The three read-only commands run by `docker exec`. Added: `autopilot.py status` prints its sections or `autopilot idle: ...` from inside; the host's own `status` prints `autopilot idle` or lists no container runner (the host cannot see it, section 7), which is expected, not a fault. Check that the Engine accepts the `--pids-limit` of section 6 (`docker inspect` shows it). Abort if `status` exits 1 inside the container.

**Stage 1. One runner, watched.** `docker exec -d kb-autopilot ...` the `runner start SP-xxxxxxxx --landed 1` of the stage, then `runner-status` by `docker exec`. Added, in this order: (1) the workspace trust and plugin approvals exist in `ap-home` before the start, or the child waits on a prompt: expect the stream's first events to be the sprint's own, not a trust question; (2) the model credential reaches the child: the stream starts and a result is produced (an authentication error in `.stderr` is an abort); (3) `glab auth status` inside names the forge host; (4) the child's environment holds none of the dropped names: `python3 _tools/tests.py -n 1 -k runner_child_holds_no_credentials` passes in the container, and `AWS_BEARER_TOKEN_BEDROCK` set in a probe environment does not reach a probe child (the existing test's pattern); (5) `procs`, run by `docker exec` before and after the start, lists the runner and its child, and does not call the runner an orphan: if it does, the expectation of section 7 holds and the rule stays not to record it; (6) `docker stats` peak is written down for section 6, and `fseventsd`'s size is read again. Expected exit and cause as the stage says. Abort on exit 1 or 2 as the stage says, on an OOM kill of the container (`docker inspect` `OOMKilled`), and on any off-list network attempt in the proxy's log.

**Stage 2. Headless guards.** Run the stage's table in the runner's worktree inside the container, with the two variables set as the runner sets them. Added attempts, each expected refused: a write outside the project, such as `/home/<user>/x` by the Edit tool, denied by the guard (`_tools/kb_hook.py:453-496`); `git push` to a branch other than `main` or `code/*` with the deploy key refused by the forge; a push to a second remote added by hand (`git remote add public ...`) fails on the network, not only on the worktree's push url; reading `/run/secrets/runner_deploy_key` as the child works (the known limit, section 1) and is recorded as such, not as a pass; a `curl` to an off-list host fails. Abort if any is not refused, except the recorded read.

**Stage 3. Land and worker worktrees.** Run by the runner inside the container. Added: after the stage's expected lines, `git worktree list` inside shows only the clone and `runner-SP`; stop the container with `docker stop` during a worker (not a land), start it, run `land` for that item and expect `land: removed the finished worker's worktree ...` for the worker whose lock is left over (section 8); `ls /tmp/kb-*` shows no stale lock record after the restart. Abort on `land stopped at step ...` on the second pass, as the stage says, and on a lock wait that outlives `KB_MAIN_LOCK_MAX_WAIT_S` (`_tools/kg_lock.py:26-27`).

**Stage 4. No-progress stop.** Two runs end without landing. Added: the tick's `bounds stop` is read from the container's `runs.jsonl` (the wrapper, or `docker exec`), not the host's: expect `bounds: stop no-progress: 2 consecutive runs landed nothing` from the container's clone, and no third `runner start`. Abort if the host's `bounds stop`, run by hand against the host clone, says `go` for a sprint the container's history stops: it is the gap of section 7 and means the wrapper is missing, not that the stage passed.

**Stage 5. Bounds.** No container change: `bounds` reads the clone's backlog, so run it in the container. Abort as the stage says.

**Stage 6. Stall remedies.** `stalled` by `docker exec`. Added: a claimed item left by a stopped container (Stage 3's) is listed with its signal and remedy, and `procs` there shows no process of it. Abort as the stage says.

**Stage 7. Digest and notifications.** The digest and PushNotification are the manager's, on the host. Added: a container stop (`docker stop`) mid-run produces `ended error` in `status` read through `docker exec`, and no notification (an error is not notified); expect none. Abort on any notification the stage does not allow.

**Stage 8. Operator gates.** The `answer ... --by autopilot --record` attempt for a `secrets`, `push` and `agents-rule` gate, run inside the container and from the host: expect exit 2 and the item unchanged in both (`_tools/bl_authority.py:21`). Added gates the plan creates in practice (the credential, push and network questions of section 11) are stated on this page, not filed as gates, and the operator answers them before Stage C. Abort if any carries an autopilot answer.

**Stage 9. Run inside the container.** Remove the container and both volumes, build the image again from the pinned file, start from nothing (`docker rm`, `docker volume rm`, a fresh clone by the entrypoint), repeat Stages 1 to 3 with the additions above. Pass when the second run's results equal the first's and no credential, volume or host path outside the plan appears. This is the stage that proves the container is disposable.

**What each stage must record**, beside the log of `kb/_self/autopilot-test.md:95-98`: the image digest in use, `docker stats` peak and `OOMKilled`, the proxy's log lines for refused hosts, and `fseventsd`'s resident size before and after.

## 11. Operator-only gates

Each is a decision only the operator makes; this page states it with options and a recommendation, and creates no backlog gate. Their classes are `secrets`, `push` and `agents-rule` (`_tools/bl_authority.py:21`), which the autopilot never answers (`AUTOPILOT_REFUSED`).

| gate | question | options | recommendation |
|---|---|---|---|
| credentials: the forge | which key and token does the container hold, and with what scope? | (a) the runner's own deploy key (main and `code/*` only) and a project token limited to what `glab api` reads and `glab mr merge` of its own `code/<id>` requests needs; (b) the operator's own key and token; (c) a key that can also push any branch | (a), the checklist's step 1 (`kb/_self/autopilot-test.md:15`): never (b) or (c). The token's smallest scope that lets `backlog.py land` and `merge` work is found at Stage 1, not assumed here |
| credentials: the model | which model credential does the container hold? | (a) a dedicated API key in its own workspace; (b) a subscription token from `claude setup-token`; (c) Bedrock, which needs `autopilot.py` changed to let the token through | (a), since an organisation-wide secret should be an API key (`kb/public/claude/ci-and-headless.md:47`); (b) only for a trial; (c) not without its own gate because it edits an `agents-rule` file |
| push | what may the container push? | (a) the integration `main` through `kbgit.py sync --push` and `code/*` branches only, as a headless run already does (`kb/_self/git.md:7`, `kb/_self/backlog.md:357`); (b) also other branches; (c) nothing: it commits and the manager pushes | (a), with branch protection on the forge enforcing it, since the headless refusal is code the agent can step around (`kb/_self/autopilot-test.md:5`). The public home: never |
| agents-rule | what may the container's runner edit? | (a) as a headless run today: not the guard paths, settings, hooks, plugin, `agents-rule` and `push` files (the `bl_` modules, `tests.py` and `conftest.py` are `agents-rule`) and no new `_tools/test_*.py`; the rest of `_tools/` and the kb allowed; (b) (a) plus a read-only trusted copy of the supervising tools (a code change); (c) content only: a read-only clone except `kb/` and `kb/_self/backlog/` | (a) to start, and (b) filed as a later change; (c) is stricter than the sprints' items need (most touch `_tools/`), so it would end most of them as operator-present only. The wrapper and any edit of `autopilot.py` for the container are `agents-rule` and `push` work: operator-present, not a headless item |
| network allow-list | which hosts, which ports, which enforcement? | (a) the integration remote's host (ssh and https) and the model API's host, through an egress proxy on an internal network; (b) (a) with firewall rules instead; (c) the host's open network | (a); the contents are exactly the two rows of section 5, and any addition is the operator's, one host at a time with its reason |
| image registry and trust | where does the image come from, and who vouches for it? | (a) built on the Mac from the pinned file and kept in the local engine; (b) built by a CI job and pushed to the project's own registry, pulled by digest; (c) a public image | (a) to start (no registry credential in the container's reach, nothing pulled at run time); (b) when a second machine runs it; never (c). The digests and checksums in the file are read from their sources by a person, never pasted from this page |

The gates above close before Stage C: the container is built and started only with the operator's answers in hand.

## What this plan could not confirm from the code or the docs read

- That `docker exec -d` gives the runner a parent that `bl_procs.orphaned` reads as gone (parent 0 or 1): expected from how Docker places an exec'd process, not read; Stage 1, item 5, settles it.
- Where Claude Code's Agent tool puts a worker's `isolation: "worktree"` when the session runs in `.claude/worktrees/runner-SP` inside a container, and that `release_worker_worktree` finds it there (`_tools/bl_land.py:432-433`).
- Whether a headless `claude -p` honours a pre-seeded workspace trust entry in its home, or needs an interactive acceptance first; and whether the project's MCP approvals live in the same file.
- How `glab` takes its token from a file or a config the entrypoint writes (its documentation was not read), and the smallest token scope `backlog.py land` and `merge` need.
- The effect of `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` on `git`, `glab` and the tools inside a headless run (the kb states the variable; its effect on this runner is not observed).
- The full list of hosts a headless `claude` contacts when telemetry and error reporting are off; Claude Code's network documentation was not read for this page.
- The install method and checksum source of the `claude` CLI for a pinned build; the kb shows the install script used in a CI job (`kb/public/claude/ci-and-headless.md:54`), which is not a pin.
- Docker Desktop's file-event behaviour on the Mac for bind mounts and volumes (the documentation read does not say), Colima's behaviour (not read), and whether the Engine's `--pids-limit` is available in the version in use.
- That the manager's `backlog.py close` and `bounds stop` can be pointed at the container's clone: they read the clone they run in, and the wrapper that would run them there does not exist.
- How the first sprint of a container run behaves when the manager's clone and the container's clone have each started a sprint: the plan assumes the forge's rejection is the only arbiter.
