---
topic: gitlab/multi-repository-layouts
priority: P3
applies_to: "git v2.55.0 documentation (gitsubmodules, git-submodule, protocol.* configuration, git-sparse-checkout, partial clone design notes, git-clone, contrib git-subtree); GitLab CI/CD submodules and forks (gitlab-org/gitlab @9f1632e2); GitHub forks; a local probe with git 2.50.1 (Apple Git-155) on macOS"
retrieved_utc: 2026-10-19
sources: [S-tzjw5vut, S-vvarw4uu, S-umm7t5f4, S-dcbs6vpj, S-kzv2kznr, S-zflhytlw, S-53fmero7, S-bhnnr3li, S-6mfmfuft, S-thoitei2, S-gt67rjc2, S1591, S-y5k6dlda, S-hvg7hx3q, S-dhea6atb, S-k2jlpd4u, S-lu3mudsw, S-7ozb4qou, S-hvhro6n5, S-p6qwirq5, S-nhku2azk, S-pmhgjvef, S-hvuk3dqt]
status: partial
---

# Knowledge kept in several repositories: submodules, subtrees, sparse checkout, partial clone and forks

## Summary
Git gives one way to hold another repository inside a checkout with its own access rules: a submodule, a gitlink to a commit plus a `.gitmodules` url that each reader clones with their own credentials. A subtree copies the other project's files and history into the superproject, so whoever reads the superproject reads them; sparse checkout and partial clone only trim what is checked out or downloaded and grant no access of their own. A superproject clone succeeds when a submodule's repository is unreachable, and only the submodule step fails, which is the property a team without read access needs. Forks carry visibility rules: a GitLab fork may be more restrictive than its upstream, while a GitHub fork of a public repository stays public.

## Facts
### Submodules
- A submodule is a repository embedded in another (the superproject) with its own history; the superproject records it as a `gitlink` tree entry holding the commit it expects, plus a `.gitmodules` entry mapping the submodule's name to its path and url. [DOC S-tzjw5vut]
- The gitsubmodules page names access control as one use: restricting user access to submodules can implement read and write policies for different users, and avoiding the fetch of submodules a user does not need reduces the transfer. [DOC S-tzjw5vut]
- Cloning or pulling a superproject does not check its submodules out by default; `git clone --recurse-submodules`, `git submodule update --init` or `submodule.recurse` brings them in. [DOC S-tzjw5vut]
- A submodule is active when `submodule.<name>.active` is true, else when its path matches the `submodule.active` pathspec, else when `submodule.<name>.url` is set, in that order; an `active = false` or an excluded path wins over a url. [DOC S-tzjw5vut]
- `git submodule update` checks out the commit the superproject records, on a detached `HEAD`, by default; `--remote` instead uses the submodule's remote-tracking branch (`submodule.<name>.branch`, else the remote `HEAD`) and fetches it first unless `--no-fetch`. [DOC S-vvarw4uu]
- `submodule.<name>.update = none` leaves a submodule out of `git submodule update`; the value is not allowed on the command line. [DOC S-vvarw4uu]
- A submodule url that starts with `./` or `../` is relative to the superproject's default remote, so a repository next to `bar.git` is `../foo.git`; with no default remote the superproject is its own upstream and the working directory is used. [DOC S-vvarw4uu]
- `git submodule update --filter=<filter-spec>` applies a partial clone filter to the submodules it clones. [DOC S-vvarw4uu]
- The `file` protocol (any local path or `file://` url) has the default policy `user`: usable when `GIT_PROTOCOL_FROM_USER` is unset or 1, and not by commands that clone without user input, such as recursive submodule initialisation. [DOC S-umm7t5f4]
- In a probe on 2026-10-19 (git 2.50.1, Apple Git-155, macOS), `git submodule add ../team.git kb/team` with a local bare repository failed with `fatal: clone of ... failed` under the default policy and succeeded with `git -c protocol.file.allow=always`. [DER S-umm7t5f4: one run of a shell script against throwaway repositories, git 2.50.1 on macOS, as the protocol page's `user` policy predicts]
- In the same probe (git 2.50.1, macOS, 2026-10-19), with the submodule's repository moved away, `git clone` of the superproject exited 0 and `git status` worked, while `git submodule update --init` and `git clone --recurse-submodules` exited 1 (`Failed to clone 'kb/team' a second time, aborting`), the latter leaving the superproject checked out. [DER S-tzjw5vut, S-vvarw4uu: one run of a shell script; a moved-away bare repository stood for a repository the reader cannot read]
- `git submodule status` prints the SHA-1 of the checked-out commit, the submodule path and the `git describe` output, with the SHA-1 prefixed by `-` when the submodule is not initialised, `+` when its checked-out commit differs from the superproject's index, and `U` on merge conflicts; `--cached` prints the SHA-1 the superproject records instead, and `--recursive` descends into nested submodules. [DOC S-vvarw4uu]
- In a probe on 2026-10-19 (git 2.50.1, macOS), `git submodule status` exited 0 in each state and printed one line a submodule: ` <40 hex> kb/team (v1)` for an initialised submodule at the recorded commit (a leading space, a describe suffix), `+<40 hex> kb/team (v1-1-g<7 hex>)` after a new commit inside it, and `-<40 hex> kb/team` with no suffix when it was not initialised, before the first `update` and after `deinit`; `--cached` and `--recursive` printed the same lines, and a path that is no submodule exited 1 with `error: pathspec 'kb/missing' did not match any file(s) known to git`. [DER S-vvarw4uu: two runs of a shell script against throwaway repositories; a leading `-` and exit 0 are how a tool sees a root that is pinned but not cloned]
- `.gitmodules` is a git config file with one subsection per submodule, named by the submodule's name (its path unless `--name` was given); `path` and `url` are required keys, `branch` and `update` optional, a path must not end with `/` and must be unique. [DOC S-bhnnr3li]
- `git config --get-regexp` is a deprecated mode: git 2.55 documents `git config get --all --show-names --regexp <name-regexp>` as its replacement, and `--show-names` adds the keys to the values `get` prints. [DOC S-kzv2kznr]
- In the probe (git 2.50.1, macOS), `git config --file .gitmodules --get-regexp path` and `git config get --file .gitmodules --all --show-names --regexp path` both exited 0 and printed one `submodule.kb/team.path kb/team` line a match, the key and the value split by one space (the name keeps its `/`); `--list` printed `key=value`, `--get submodule.kb/team.url` printed the value alone and exited 1 with no output for a missing key, and `--name-only --get-regexp` printed the keys alone. [DER S-kzv2kznr, S-bhnnr3li: one run of a shell script; a url that holds a space or newline was not tried]
- Git asks for an HTTP username or password in this order: the program in `GIT_ASKPASS`, else the one in `core.askPass`, else `SSH_ASKPASS`, else the terminal; the page states this order for the case without any credential helper defined. [DOC S-53fmero7, S-zflhytlw]
- A false `GIT_TERMINAL_PROMPT` makes git not prompt on the terminal, for example when asking for HTTP authentication; `GIT_ASKPASS` names the program git calls for passwords and passphrases instead, which answers on its standard output. [DOC S-dcbs6vpj]
- Git Credential Manager (GCM) has `GCM_INTERACTIVE` (environment) and `credential.interactive` (git config): `0` or `false` stops it showing GUI or terminal prompts and an error is returned when interaction was needed, which the page recommends for build servers so a run fails instead of hanging; both default to enabled, and the page gives the environment variable for Windows (`SET`) and macOS or Linux (`export`). [DOC S-6mfmfuft, S-thoitei2]
- The GCM environment and configuration pages at commit e66693fa do not mention `GIT_TERMINAL_PROMPT`; whether GCM honours it is not stated. [UNK: S-6mfmfuft, S-thoitei2 searched for the variable name, no hit]
- In a probe on 2026-10-19 (git 2.50.1, macOS, no `credential.helper` and no global config, a local HTTP stand-in answering `401` with `WWW-Authenticate: Basic`), with `GIT_TERMINAL_PROMPT=0` `git clone` exited 128 and showed `fatal: could not read Username for 'http://127.0.0.1:<n>': terminal prompts disabled`; `git submodule update --init` exited 1 after trying the clone twice (`Failed to clone 'kb/team'. Retry scheduled`, then `Failed to clone 'kb/team' a second time, aborting`) and left the submodule uninitialised, `git submodule status` still exit 0 with a `-` line. [DER S-dcbs6vpj, S-vvarw4uu: one run of a shell script; the denial came from a stand-in, not a forge]
- In the same probe (git 2.50.1) a run with no `GIT_TERMINAL_PROMPT` but no controlling terminal also failed at once with the same exit codes, the message ending `Device not configured` instead of `terminal prompts disabled`, and `GIT_ASKPASS=/usr/bin/false` added `error: unable to read askpass response from '/usr/bin/false'` before it. [DER S-dcbs6vpj: a process started in its own session with stdin closed; a run with a terminal attached was not tried]
- In the same probe the stand-in answering `403` gave `fatal: unable to access 'http://127.0.0.1:<n>/team.git/': The requested URL returned error: 403`, with no prompt and no username line: `git clone` exited 128 and `git submodule update --init` exited 1 after the same two attempts. [DER S-vvarw4uu: one run against a stand-in]
- In the probe (git 2.50.1) a stand-in `GIT_SSH_COMMAND` that printed OpenSSH's text and exited 255 gave `git@forge.example.com: Permission denied (publickey).` and `fatal: Could not read from remote repository.`, and `git submodule update --init` exited 1 after two attempts, with or without a path argument. [DER S-dcbs6vpj, S-vvarw4uu: a script stood in for ssh; no sshd and no forge was involved]
- Not run: the same steps on Windows or Linux, against a real forge's 401, 403 or SSH refusal, with GCM or a credential helper present, with an SSH agent or `BatchMode`, and with other git versions. [UNK: the probes used local paths, a stand-in HTTP endpoint and a stand-in ssh command on git 2.50.1]
- Windows limits a path to `MAX_PATH`, 260 characters including the terminating null, unless long paths are enabled (`LongPathsEnabled` set to 1 and an application that declares itself long-path aware); the page names cloning a git repository with long file names into a folder with a long name as a way to meet the limit. [DOC S1591]
- Git for Windows' `core.longpaths` lifts the limit for builtin commands and is off by default (`gitlab/git-test-repositories.md`). [DOC S-y5k6dlda]
- The Windows file system treats names as case-insensitive by default and can flag one directory case-sensitive: `fsutil.exe file setCaseSensitiveInfo <path> enable` needs an elevated prompt and an empty directory, and directories created below inherit the flag; the page also says that `core.ignorecase false` on a case-insensitive file system can give confusing errors, false conflicts or duplicate files. [DOC S-gt67rjc2]
- `core.ignoreCase` is set by `git clone` and `git init` for filesystems that are not case sensitive, such as APFS, HFS+, FAT and NTFS, and the page warns that changing it may give unexpected behaviour. [DOC S-zflhytlw]
- In a probe on 2026-10-19 (git 2.50.1, macOS default volume), `mkdir team` after `mkdir Team` in one directory raised `FileExistsError`, and `git submodule add` put the submodule's git directory at `.git/modules/kb/team` with `kb/team/.git` holding `gitdir: ../../.git/modules/kb/team`, so the name `kb/team` is a nested directory path there. [DER S-zflhytlw, S-vvarw4uu: one run of a shell script on a case-insensitive volume]
- A root's cost in path length on Windows is the clone's own path plus `kb/<name>` or `_cache/roots/<name>` plus the deepest file inside the root, and in a submodule also `.git/modules/<name>` plus the objects below it; two root names that differ only by case collide on NTFS and on a default macOS volume, so a root name is lowercase and unique when read without case. [DER S1591, S-gt67rjc2, S-zflhytlw: a sum of the documented limit and the case rules; no Windows run]
- Claude Code keys a repository's trust on the git repository root, and that trust does not cover a git repository nested inside it, such as a submodule. [DOC S-pmhgjvef]
- Claude Code 2.1.295 (2026-10-08) fixed adding or refreshing a plugin marketplace whose repository has large submodules: only the submodules that hold plugin files are fetched. [DOC S-hvuk3dqt]

### Submodules in GitLab CI/CD
- GitLab warns that relative submodule urls may resolve incorrectly in forking workflows and recommends absolute urls for a project expected to have forks; a submodule on another server always takes the full url. [DOC S-7ozb4qou]
- Cloning a submodule with `CI_JOB_TOKEN` needs the Reporter, Developer, Maintainer or Owner role on the submodule's project and the job token access configured in that project. [DOC S-7ozb4qou]
- `GIT_SUBMODULE_STRATEGY` is `none` (no submodules), `normal` (top level, as `git submodule sync` and `update --init`) or `recursive`; `GIT_SUBMODULE_PATHS` names or `:(exclude)`s paths, and `GIT_SUBMODULE_UPDATE_FLAGS` passes flags such as `--jobs 4`. [DOC S-hvhro6n5]
- A submodule on another GitLab instance cannot be cloned with the current instance's `CI_JOB_TOKEN`; the job uses a personal, deploy or project access token of that instance with `read_repository`, through url rewriting or a credential helper, and on a shell executor a `git config --global` credential persists between jobs. [DOC S-7ozb4qou]

### Subtrees, sparse checkout and partial clone
- `git subtree` (in git's `contrib/`) includes a subproject in a subdirectory, optionally with its whole history, with no `.gitmodules` or gitlinks; `split` extracts a subdirectory's history as a standalone project and `--squash` imports one commit instead of the history. [DOC S-lu3mudsw]
- A subtree's files are ordinary files of the superproject, so anyone who can read the superproject reads them; a subtree cannot keep a team's content from readers of the repository that holds it. [DER S-lu3mudsw: no gitlink or separate repository]
- `git sparse-checkout` reduces the working tree to a subset of tracked files, chosen by directories in cone mode (the default; non-cone mode is deprecated); its page marks the command experimental. [DOC S-hvg7hx3q]
- Partial clone (`git clone --filter=blob:none`, or `blob:limit=<size>`) skips objects at clone time and fetches them on demand from a promisor remote, so it needs the user online with the promisor reachable; it limits blobs and trees within the commits fetched, unlike shallow or single-branch clones. [DOC S-dhea6atb, S-k2jlpd4u]
- Sparse checkout and partial clone trim what one clone holds, not what a reader may read: every object stays reachable from the one repository, so they are no access control between teams. [DER S-hvg7hx3q, S-dhea6atb: both act on a clone of a single repository]

### Forks and visibility
- A GitLab fork's visibility must be at least as restrictive as both the upstream project's and the namespace's; a fork does not follow when the upstream later becomes more restrictive. [DOC S-p6qwirq5]
- A GitHub fork's visibility follows its upstream: forks of public repositories are public, forks of private ones private, and a fork's visibility cannot be changed by itself. [DOC S-nhku2azk]
- So a team's private knowledge next to a public upstream is a private fork on GitLab, but on GitHub a separate private repository (not a fork) that pulls from the upstream. [DER S-p6qwirq5, S-nhku2azk]

### How it fits
- A shared public root plus private team roots maps to one repository per root: the public repository pins each team root as a submodule or names it in a pointer file; a reader without access to a team's repository still clones the public root, and only that root is missing. [DER S-tzjw5vut, S-vvarw4uu: per-submodule access and a clone that does not recurse by default; the probes above saw it for a missing local path, a stand-in HTTP 401 and 403 and a stand-in ssh refusal, on macOS only]
- A pointer that names a branch (`submodule.<name>.branch` with `update --remote`) follows the team's latest work, and a recorded gitlink pins a commit that only a superproject commit moves; offline use needs the submodule already cloned, since a partial clone fetches missing objects on demand. [DER S-vvarw4uu, S-dhea6atb]
- On Windows a submodule keeps its git directory under the superproject's `.git/modules/<name>/`, so deep paths also meet Git for Windows' path-length limit described in `gitlab/git-test-repositories.md` (`core.longpaths`). [DER S-tzjw5vut]

## Reference
| Need | Command or setting | Source |
|---|---|---|
| add a submodule | `git submodule add <url> <path>` | S-vvarw4uu |
| clone with submodules | `git clone --recurse-submodules <url>` | S-tzjw5vut |
| follow a branch | `git submodule set-branch -b <branch> <path>`, `update --remote` | S-vvarw4uu |
| leave one out | `submodule.<name>.update = none` or `active = false` | S-vvarw4uu, S-tzjw5vut |
| local path submodule in a test | `git -c protocol.file.allow=always submodule update --init` | S-umm7t5f4 |
| CI submodules | `GIT_SUBMODULE_STRATEGY`, `GIT_SUBMODULE_PATHS` | S-hvhro6n5 |
| fail at once, no prompt | `GIT_TERMINAL_PROMPT=0` (and `GCM_INTERACTIVE=0` with GCM) | S-dcbs6vpj, S-6mfmfuft |
| read pinned state | `git submodule status [--cached]`, `git config get --all --show-names --regexp <re>` (was `--get-regexp`) | S-vvarw4uu, S-kzv2kznr |
| trim a clone | `git clone --filter=blob:none --sparse`, `git sparse-checkout set <dir>` | S-k2jlpd4u, S-hvg7hx3q |

See also `gitlab/git-test-repositories.md` (throwaway repositories, gitfiles, Windows path length), `gitlab/multi-project-pipelines.md` (job token allowlist), `gitlab/deploy-keys-and-tokens.md` (read-only access for a machine) and `gitlab/commit-signing-and-provenance.md` (bot identities).

## Examples
- SNIPPET: a superproject that pins a team root as a submodule and a reader who has no access to it; context: git 2.38 or later, placeholders for the urls; checked: no [DER S-vvarw4uu, S-tzjw5vut: commands from the git-submodule and gitsubmodules pages]
```bash
git submodule add -b main https://git.corp.example.com/team-a/kb-team-a.git kb/team-a
git commit -m "Add team-a root as a submodule"
# a reader without access: the superproject clone works, the submodule step fails
git clone https://git.corp.example.com/kb/it-ops-kb.git
git -C it-ops-kb submodule update --init kb/team-a || echo "team-a root unavailable"
```
