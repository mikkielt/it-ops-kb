---
topic: gitlab/multi-repository-layouts
priority: P3
applies_to: "git v2.55.0 documentation (gitsubmodules, git-submodule, protocol.* configuration, git-sparse-checkout, partial clone design notes, git-clone, contrib git-subtree); GitLab CI/CD submodules and forks (gitlab-org/gitlab @9f1632e2); GitHub forks; a local probe with git 2.50.1 (Apple Git-155) on macOS"
retrieved_utc: 2026-10-19
sources: [S-tzjw5vut, S-vvarw4uu, S-umm7t5f4, S-hvg7hx3q, S-dhea6atb, S-k2jlpd4u, S-lu3mudsw, S-7ozb4qou, S-hvhro6n5, S-p6qwirq5, S-nhku2azk, S-pmhgjvef, S-hvuk3dqt]
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
- Not run: the same steps on Windows or Linux, with a forge that answers an authentication failure (HTTP 401 or 403, or an SSH refusal) instead of a missing path, and with other git versions. [UNK: the probe used local paths only]
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
- A shared public root plus private team roots maps to one repository per root: the public repository pins each team root as a submodule or names it in a pointer file; a reader without access to a team's repository still clones the public root, and only that root is missing. [DER S-tzjw5vut, S-vvarw4uu: per-submodule access and a clone that does not recurse by default; the probe above saw it for a missing local path only]
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
