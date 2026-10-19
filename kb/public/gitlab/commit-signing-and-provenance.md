---
topic: gitlab/commit-signing-and-provenance
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27; protected branches and approval rules @56c82a97); SLSA v1.2; GitHub deploy keys and GitHub App installation tokens (docs.github.com, 2026-10-19)"
retrieved_utc: 2026-10-19
sources: [S-jut4uqct, S-hthqd5dx, S-gqe643np, S-gfhrhfsb, S-oroizj3k, S-ijtwicvp, S-lu25cylz, S-cfpw3yy4, S-yg2mm5c6, S-wyjdebjb, S444, S442, S440, S-mgxxzq3i, S-zsl52tpy, S-ucjfr2m7, S-hvhro6n5, S-l6ia2wz4, S-243c6khs, S-3466yhgq, S-6sw5hnns]
status: partial
---

# Provenance of agent commits: signed commits, push rules, bot accounts and SLSA

## Summary
GitLab verifies signatures on commits and tags made with an SSH key, a GPG key or an X.509 certificate, on every tier; X.509 only on Self-Managed and Dedicated. A commit is **Verified** when the key sits in the committer's GitLab profile (for X.509, when the certificate chains to the instance trust store) and the committer email is a verified email of that user; signing proves the committer, never the author. The Premium push rule **Reject unsigned commits** rejects unsigned commits sent with `git push`, but lets in the commits GitLab itself creates through the UI or the API, so unsigned commits can still reach the history. An agent's account (a project or group access token's bot user, or a service account) is a user with a role: protected branch and approval rules apply to it as to anyone, and an account allowed to push to a protected branch skips merge request approval rules. SLSA v1.2 asks a build platform for provenance that exists (Build L1), is signed and made by the platform (L2) and cannot be forged by the build steps (L3); its Source track adds source provenance and, at Source L4, review by two trusted persons, who are humans. GitLab Runner writes an SLSA provenance statement on every tier, with no signature described; GitLab's own signed SLSA L3 attestations are an Ultimate, GitLab.com-only experiment for public projects.

## Facts
### Signed and verified commits
- The signed commits page is Free, Premium and Ultimate on GitLab.com, Self-Managed and Dedicated; GitLab verifies signatures on commits and tags made with an SSH key, a GPG key or an X.509 certificate. [DOC S-jut4uqct]
- A signed commit carries a signature made with a private key; a verified one has a signature GitLab can check against a public key stored in a user's profile. Signing verifies only the committer's identity, not the author's. [DOC S-jut4uqct]
- Signed commits show a **Verified** or **Unverified** badge in the commit lists of a project or merge request, and unsigned commits show no badge. [DOC S-jut4uqct]
- `GET /projects/:id/repository/commits/:sha/signature` returns a commit's signature with `signature_type` (`PGP`, `SSH` or `X509`) and `verification_status`, and answers `404` for an unsigned commit. [DOC S-ijtwicvp]
- A failed GPG or X.509 verification is reported as `UNVERIFIED`, `SAME_USER_DIFFERENT_EMAIL`, `OTHER_USER` (valid signature, but the key belongs to another user than the committer), `UNVERIFIED_KEY`, `UNKNOWN_KEY` or `MULTIPLE_SIGNATURES`. [DOC S-jut4uqct]
- When the committer email of a verified commit is no longer a verified email of the signing user, GitLab shows an orange **Verified** badge with a warning sign; generally available in GitLab 19.1. [DOC S-jut4uqct]
- GPG: GitLab marks a commit verified when the committer's public key is uploaded to their GitLab account, an email in the key matches a verified email of the committer and the committer email matches it; GitLab checks against its own keyring and never asks a public key server. [DOC S-hthqd5dx]
- Revoking a GPG key marks the past and future commits signed with it unverified; removing the key leaves past commits verified and only future ones unverified. [DOC S-hthqd5dx]
- SSH: the signing key must be in the committer's GitLab account with the usage type **Authentication & Signing** or **Signing**, and the committer email must be a verified email of the account, else the commit is **Unverified**; signing needs Git 2.34.0 and OpenSSH 8.1 or later (8.7 is broken), with ED25519, ED25519_SK, RSA, ECDSA or ECDSA_SK keys. [DOC S-gqe643np]
- Revoking an SSH signing key marks earlier commits **Unverified**, while deleting it leaves earlier commits as they were; SSH signatures can also be checked locally with an allowed signers file (`gpg.ssh.allowedSignersFile`, entries with `namespaces="git"`) and `git log --show-signature`. [DOC S-gqe643np]
- X.509 (Free, Premium, Ultimate; Self-Managed and Dedicated only): GitLab trusts a certificate that chains to a root in its own certificate store, whose email matches a verified email, and whose validity covers a signing time no earlier than the commit time; a background worker checks revocation lists daily, and GitLab.com shows no **Verified** badge because only Self-Managed can upload a custom CA. [DOC S-gfhrhfsb]
- X.509 certificates without `authorityKeyIdentifier`, `subjectKeyIdentifier` and `crlDistributionPoints` show **Unverified**, as do most with Extended Key Usage values beyond the Key Usage `Digital Signature` unless `emailProtection` is added to the EKU list. [DOC S-gfhrhfsb]
### Commits GitLab creates
- GitLab signs the commits it creates, such as web UI commits, with a key configured on the instance; the signature stays with a commit copied to another project, which shows **Verified** only when its instance has that key. [DOC S-jut4uqct]
- Signing of GitLab UI commits (Free, Premium, Ultimate; Self-Managed and Dedicated) puts GitLab's instance address in the `Committer` field and the user in `Author`; its feature flag `gitaly_gpg_signing` has been on by default since 17.0, while the page still says the feature is not ready for production use. [DOC S-oroizj3k]
- On GitLab.com the **Sign web-based commits** setting (generally available in 18.10; group Owner or project Maintainer or Owner) signs every commit made through the Web Editor, the Web IDE and merge requests with the instance key. [DOC S-oroizj3k]
- Commits created through the REST API count as web commits; with commit signing on, an API commit whose `author_name` and `author_email` differ from the calling user is rejected. [DOC S-oroizj3k]
- Rebasing a merge request from the GitLab UI leaves earlier signed commits unsigned, because GitLab cannot sign the rewritten commits; the page's workaround is a local rebase and push. [DOC S-oroizj3k]
### Push rules
- **Reject unsigned commits** (Premium, Ultimate) rejects commits pushed from outside GitLab with `git push` that lack a valid GPG, SSH or X.509 signature, and rejects invalid or corrupt signatures, but allows unsigned commits created through the GitLab UI or API (Web IDE, merge request actions, API calls), so unsigned commits can still appear in the history. [DOC S-lu25cylz]
- With **Reject unsigned commits** set, users cannot commit through the Web IDE by default; an administrator allows it by disabling the feature flag `reject_unsigned_commits_by_gitlab`. [DOC S-lu25cylz]
- Open: whether **Reject unsigned commits** needs a signature GitLab can verify against the pushing user's keys, or accepts any valid signature, is not stated on the push rules or signed commits pages. [UNK: the rule's text says only "a valid cryptographic signature"]
- The user rules of a push rule check commits, not tags: **Reject unverified users** (the committer email must be a verified or private commit email of the user), **Reject inconsistent user name**, **Check whether the commit author is a GitLab user** (author and committer emails must be verified emails of a GitLab user) and **Commit author's email** (a regular expression); bot users of project or group tokens commit only when their generated email suffix is allowed. [DOC S-lu25cylz]
- **Reject inconsistent user name** catches misconfigured Git settings but does not prevent impersonation; the page points to **Reject unsigned commits** for cryptographic identity verification. [DOC S-lu25cylz]
- For commits signed by GitLab, whose committer is an instance address that belongs to no user, three user rules check the author email instead, and **Reject unverified users** is skipped for such commits arriving by a Git push, such as mirroring (changed in 19.3). [DOC S-lu25cylz]
- The DCO push rule requires a `Signed-off-by:` trailer in every commit message and rejects commits without it; the trailer is text, not a cryptographic signature. [DOC S-lu25cylz]
### Bot users and service accounts
- Creating a project access token creates a bot user with the token's role and scope, a project member that cannot be removed or added to other groups or projects, non-billable, whose contributions are attributed to it and move to a ghost user when it is removed; its username is `project_{project_id}_bot_{random_string}` and its email `project_{project_id}_bot_{random_string}@noreply.{host}`. [DOC S-cfpw3yy4]
- Service accounts (all tiers; Free since 18.11) are user accounts for non-human entities that authenticate with a personal access token for Git, registries and the API; they use no seat, are always external users, cannot sign in through the UI and appear as service accounts in membership lists. [DOC S-yg2mm5c6]
- A service account's SSH keys are managed only through the user SSH and GPG keys API, not the UI; GitLab gives it a generated no-reply email with a `service_account_` prefix, and a custom email needs confirmation unless the top-level group has a matching verified domain. [DOC S-yg2mm5c6]
- An administrator adds keys to any user with `POST /users/:id/keys` (`usage_type` `auth`, `signing` or `auth_and_signing`, default `auth_and_signing`) and `POST /users/:id/gpg_keys`. [DOC S-wyjdebjb]
- Open: whether a service account's generated no-reply email counts as a verified email for signature verification and the **Reject unverified users** rule is not stated on the service account or signed commits pages. [UNK: neither page says]
### GitHub machine identities
- A GitHub deploy key is an SSH key attached to one repository, not to a personal account; it is read-only by default, may be given write access (then acting like an admin member or collaborator), has no expiry date and stays active when the user who added it leaves. [DOC S-3466yhgq]
- For access across repositories or organizations GitHub recommends a GitHub App: its installation access tokens are decoupled from any user, scoped to one or more repositories with fine-grained permissions, and have their own rate limits. [DOC S-3466yhgq]
- An installation access token expires after 1 hour, and API requests made with it are attributed to the app, not to a person. [DOC S-6sw5hnns]
- A deploy key fits one machine reading one repository, such as a pointer to a team's knowledge repository; a GitHub App installation fits an agent that writes to several, since each token is short-lived and its actions carry the app's name. [DER S-3466yhgq, S-6sw5hnns]

### Protected branches and approvals for automation
- Users and groups allowed to push to a protected branch need no merge request to merge their branches, so they skip merge request approval rules, Code Owners included. [DOC S444]
- In Premium and Ultimate, individual users and groups can be added to **Allowed to merge** and **Allowed to push and merge**; Free sets them by role only. [DOC S444]
- To approve, a user must be a direct member of the project, its group or a parent group, a group shared with them, or a group added as approvers; a Developer approves only as a named approver or as a code owner of the changed files. [DOC S442]
- Open: none of the approval pages read says whether bot users or service accounts are refused as approvers; a project bot is a direct project member, which meets the eligibility rule as written. [UNK: the approval rules and settings pages name neither]
### SLSA build and source provenance
- SLSA v1.2 Build L1 (**Provenance Exists**): the build MUST produce provenance that names the output by cryptographic digest and says how it was produced, in a format the consumer accepts; the SLSA Provenance format is recommended, and another format must carry the same information. [DOC S-mgxxzq3i]
- Build L2 (**Provenance is Authentic**): consumers MUST be able to check the provenance's signature, made with a key only the generating platform component holds, and the provenance MUST come from the control plane, not a tenant, except the output names and digests and fields L2 does not require. [DOC S-mgxxzq3i]
- Build L3 (**Provenance is Unforgeable**): signing secrets sit in a secret store reachable only by the build service account and never by the user-defined build steps; every field is generated or verified by the platform, and external parameters are fully listed. [DOC S-mgxxzq3i]
- Build L2 and L3 need a hosted build platform, not a workstation, and L3 isolated builds: a build MUST NOT reach platform secrets such as the provenance signing key, or influence a build that overlaps it in time. [DOC S-mgxxzq3i]
- The producer MUST distribute provenance to the artifact's consumers, and may leave that to a package ecosystem that can. [DOC S-mgxxzq3i]
- SLSA Provenance is an in-toto predicate of type `https://slsa.dev/provenance/v1`; Build L1 requires `buildDefinition` (`buildType`, `externalParameters`) and `runDetails` (`builder.id`), and `externalParameters` MUST be complete at Build L3. [DOC S-zsl52tpy]
- The SLSA v1.2 Source track has four levels: L1 version controlled; L2 continuous, immutable, retained history with a source provenance attestation for each revision (when, who, which controls); L3 technical controls the source control system enforces on named references; L4 two-party review. [DOC S-ucjfr2m7]
- The Source track's roles separate a **trusted person** (a human the organization authorizes to propose and approve changes) from a **trusted robot** (automation authorized in defined contexts, whose identity and code cannot be unilaterally influenced). [DOC S-ucjfr2m7]
- Source L4 two-party review: changes to protected branches MUST be agreed by two or more trusted persons before submission (uploader and reviewer, or two reviewers), covering the final revision; an organization MAY give a trusted robot a perpetual exception, such as import bots or Dependabot. [DOC S-ucjfr2m7]
- A source control system states a revision's level in a source verification summary attestation (Source VSA), whose `verifiedLevels` takes one of `SLSA_SOURCE_LEVEL_0` to `SLSA_SOURCE_LEVEL_3` as listed; a revision with no VSA is Source Level 0. [DOC S-ucjfr2m7]
### GitLab CI provenance
- Runner artifact provenance metadata is switched on with the variable `RUNNER_GENERATE_ARTIFACTS_METADATA: "true"` (global or per job) and is written as a plain-text `{ARTIFACT_NAME}-metadata.json` (default `artifacts-metadata.json`) stored with the artifact. [DOC S-hvhro6n5]
- The file is an in-toto v0.1 Statement with an SLSA 1.0 provenance predicate: `subject` names and `sha256` of the artifacts, `buildType` the runner's `PROVENANCE.md` at its version, `builder.id` the runner's page, `externalParameters` the variable names with empty values (to protect secrets) plus `source` (project URL) and `entryPoint` (job name), and `resolvedDependencies[0]` the project URL with the commit revision. [DOC S-hvhro6n5]
- GitLab's SLSA level 3 attestations (Ultimate, GitLab.com, Experiment, flag `slsa_provenance_statement` off by default) need a public project, so nothing leaks to Rekor, a job in the `build` stage, and `ATTEST_BUILD_ARTIFACTS: true` (artifacts of 100 MB at most) or `ATTEST_CONTAINER_IMAGES: true` with `IMAGE_DIGEST`; results are listed under **Build > Attestations** and in the Attestations API. [DOC S-l6ia2wz4]
- An attested artifact or container is checked with `glab attestation verify <file-or-container> -p <group>/<project>`. [DOC S-l6ia2wz4]
- GitLab publishes the `buildType` of its attestations: external parameters `source`, `entryPoint` and `variables`, the values of `CI_PIPELINE_ID`, `CI_PIPELINE_URL`, `CI_JOB_ID`, `CI_JOB_URL`, `CI_JOB_NAME`, `CI_PROJECT_ID` and `CI_PROJECT_NAME`. [DOC S-243c6khs]
### How it fits
- An agent's own commits show **Verified** only when its account holds the signing key and commits with a verified email of that account: for a service account an administrator adds the key through `POST /users/:id/keys` with `usage_type` `signing`, since the UI cannot. Whether its generated email counts is open, above. [DER S-gqe643np, S-yg2mm5c6, S-wyjdebjb: SSH verification conditions and the API-only key management of service accounts]
- **Reject unsigned commits** alone does not prove who wrote a change: an agent committing through the REST API lands commits the rule exempts, unsigned or signed with the instance key under the instance committer, so provenance is read per commit from `verification_status` and the key or certificate the signature API names. [DER S-lu25cylz, S-oroizj3k, S-ijtwicvp: the rule's exemption for UI and API commits, the instance committer and the signature API fields]
- What limits an agent account's pushes and merges is its role and the protected branch lists, as for any user: one that must not merge unreviewed work is left out of **Allowed to push and merge** on protected branches (pushers skip approval rules), given a role below **Allowed to merge** or, in Premium, left out of the user lists, and **Prevent approval by merge request creator** (on by default) keeps it from approving its own merge request. [DER S444, S440: the protected branch push bypass and the creator approval setting]
- At SLSA Source L4 an agent counts at most as a trusted robot, never a trusted person, so a change an agent uploads needs two different human reviewers unless the organization grants that robot an exception. [DER S-ucjfr2m7: the role definitions and the two accepted reviewer combinations]
- The runner's provenance file has no signature on the page that defines it and is written during the build, so on its own it meets Build L1's Provenance Exists but gives a consumer no signature to check as Build L2 requires. [DER S-hvhro6n5, S-mgxxzq3i: the metadata section and the L2 authenticity requirement]

## Reference
| Mechanism | Tier | Offering | Source |
|---|---|---|---|
| GPG and SSH signed commits | Free, Premium, Ultimate | all | S-hthqd5dx, S-gqe643np |
| X.509 signed commits | Free, Premium, Ultimate | Self-Managed, Dedicated | S-gfhrhfsb |
| Signing of GitLab UI commits (instance key) | Free, Premium, Ultimate | Self-Managed, Dedicated; GitLab.com setting GA 18.10 | S-oroizj3k |
| Push rule **Reject unsigned commits** | Premium, Ultimate | all | S-lu25cylz |
| Service accounts | Free, Premium, Ultimate | all | S-yg2mm5c6 |
| Runner artifact provenance metadata (no signature described) | every tier | all | S-hvhro6n5 |
| SLSA L3 provenance attestations | Ultimate, Experiment | GitLab.com, public projects | S-l6ia2wz4 |

See also `gitlab/multi-repository-layouts.md` (submodules and forks for knowledge kept in several repositories), `gitlab/protected-branches-tags.md` (push and merge lists, push rules), `gitlab/mr-approvals.md` (approval settings), `gitlab/deploy-keys-and-tokens.md` (deploy keys and group access tokens), `gitlab/git-trailers-and-hooks.md` (commit trailers such as `Co-Authored-By`) and `security/supply-chain.md` (SLSA levels and GitLab's attestation tiers for a Python package).

## Examples
- SNIPPET: make Git sign an agent's commits with an SSH key; context: Git 2.34.0 or later, OpenSSH 8.1 or later, the public key added to the agent's GitLab account with usage type Signing; checked: no [DER S-gqe643np: the configuration steps of the SSH signing page]
```bash
git config gpg.format ssh
git config user.signingkey ~/.ssh/agent_signing.pub
git config commit.gpgsign true
git config user.email "jan.kowalski@corp.example.com"
```
- SNIPPET: read a commit's signature type and verification status; context: GitLab 19.x, a token that can read the project, `<project_id>` and `<sha>` filled in; an unsigned commit answers `404`; checked: no [DER S-ijtwicvp: endpoint and fields from the commits API]
```bash
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --url "https://gitlab.corp.example.com/api/v4/projects/<project_id>/repository/commits/<sha>/signature"
```
