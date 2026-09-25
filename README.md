# it-ops-kb

A knowledge base of facts from official sources for Windows endpoint management and the AI agents that operate it. It is written to be read offline, by people and by retrieval tools.

Domains: Microsoft DSC v3, ConfigMgr (MECM), Intune, Autopilot, Entra ID, Active Directory, Microsoft Graph, Group Policy, Defender, logs, SQL Server, Power BI, GitLab CI, Ansible, Windows security baselines, identity and authorization, privacy and pseudonymization (Presidio), the Model Context Protocol, Claude Code, and AI agents (evaluation, limits and errors, caching, A2A, Copilot Studio, authorization).

## Layout

- `<domain>/<topic>.md` is one topic. `priority` (P0-P3) is the research order it was gathered in, not importance.
  - Its front matter has `topic`, `priority`, `applies_to`, `retrieved_utc`, `sources` and `status`.
  - Its body has four sections: Summary, Facts, Reference and Examples.
  - Large tables sit beside it as `.csv` or `.yaml`.
- `_sources.csv` lists every source: `id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by`. `superseded_by` is empty unless a newer row replaced this one (for example a pinned commit url whose upstream file changed); it then names that row's id.
- `_artifacts.csv` lists every pinned structured artifact, such as JSON schemas, DSC manifests, Graph CSDL, the MCP `schema.ts`, the A2A `.proto`, baseline exports and semantic-convention registries. Each row gives its sha256. Each artifact has a Markdown digest beside it.
- `_answers.md` holds answers to research questions, each with evidence.
- `_gaps.md` records what could not be confirmed, and where it was looked for.
- `_conflicts.md` records where sources disagree, with both sides linked.
- `_coverage.csv` is the coverage index, also rendered below.
- `_fetch_state.csv` records, per source, when `fetch.py --diff` last checked and fetched it, when it last changed, and the hashes compared. Text snapshots of the last fetch sit in `_cache/snapshots/` (not committed).
- `_tools/` holds stdlib-only Python tools.
- `AGENTS.md` holds instructions for AI agents (setup, including the shared documentation MCP servers in `.mcp.json`); `.claude/skills/` holds the shared Claude Code skills `/kb-setup`, `/kb-lookup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic` and `/kb-verify`.

## Fact tags

Every fact ends in exactly one tag with source ids from `_sources.csv`:

- `DOC`: stated by an official document.
- `DER`: derived from DOC facts, with the derivation shown.
- `COMMUNITY`: a non-official source. It is never the only evidence for a DOC fact.
- `UNK`: not confirmed.

A fact tagged `UNK` or `COMMUNITY` is a lead to verify, not a basis to build on.

Source ids come in two forms, both valid everywhere:
- legacy `S` + a number (`S100` ... `S2204`): existing rows, kept forever and never renumbered;
- hash ids `S-` + 8 characters (`S-k3f7q2zd`) for every new source: derived from the url by `python3 _tools/kbid.py url <URL>`, so two people adding the same url get the same id and parallel work merges without clashes.

Answers in `_answers.md` are headed `## <ID>. <question>`. New research answers use `QK-<slug>` (`## QK-dataverse-onprem-sync. ...`); `python3 _tools/kbid.py answer "<question>"` suggests one. An id never appears twice.

Examples use placeholder names only:
- hosts `PL-LT-00123` and `PL-SRV-0042`;
- domain `corp.example.com`;
- tenant `00000000-0000-0000-0000-000000000000`;
- user `jan.kowalski`.

## Tools

```
python _tools/rag.py topics [DOMAIN]                   # domains -> articles (title, priority, status), subdirectories, data files
python _tools/rag.py search "pim activation latency" -k 8 [-d auth]   # BM25 over heading-aware chunks of .md and .csv rows
python _tools/rag.py search "pim activation latency" -u      # same, plus each cited source id's origin url
python _tools/rag.py src S1824 S-k3f7q2zd              # resolve source ids (legacy or hash); shows "superseded by" when set
python _tools/kbid.py url https://example.com/page     # the id for a new source's url (says if the url already has one)
python _tools/kbid.py answer "question text"           # suggest a QK-<slug> id for _answers.md
python _tools/kbid.py check                            # hash ids: collisions, ids that do not match their url (check.py runs it too)
python _tools/rag.py show agents/agent-rbac.md:139 -n 30
python _tools/check.py                                 # unique and valid source ids, superseded_by, answer ids, known citations, artifacts, front matter
python _tools/fetch.py --offline                       # check local artifacts against their sha256
python _tools/fetch.py --verify                        # re-download pinned sources and compare sha256
python _tools/fetch.py --refresh                       # rewrite local copies of pinned sources
python _tools/fetch.py --diff --topic auth/kerberos     # re-fetch a topic's sources; summary of what changed since the last fetch
python _tools/fetch.py --diff --dir dsc --full --json   # same for a directory, with unified text diffs, as JSON
python _tools/fetch.py --diff --older-than 30           # only sources not fetched in 30 days (also --file PATH, --source S123)
python _tools/fetch.py --status --file auth/kerberos.md # offline: last fetch and change dates
python _tools/stress_test.py                           # robustness tests of the tools on throwaway kb copies (~10 s; --scale N, -k NAME)
python _tools/tests.py                                 # CI: docs cohesion + leak scan (reviewed exceptions in _tools/tests_allowlist.txt)
```

- `rag.py` builds no index file; a query takes about 0.1 s. `search` skips the root-level index files (`README.md`, `_answers.md`, `_gaps.md`, `_conflicts.md`, `_coverage.csv`, ...); `--index` includes them. `--json` gives machine output, and each hit carries `path`, `line`, `heading`, `text` and the source ids it cites. With `-u`/`--urls`, each hit also carries `urls`, mapping those source ids to their origin url in `_sources.csv`.
- `fetch.py --diff` exits 0 when nothing changed, 1 when a source changed and 2 when a fetch or the selection failed, as `diff` does. `--max-lines N` caps each diff, `--no-save` compares without moving the baseline, `--delay` sets the per-host pause (default 1.1 s). HTML is reduced to its main text first, so page chrome does not count as a change.
- Only pinned URLs carry `artifact_sha256`: raw files at a commit or tag, and release downloads. For live pages, the hash taken at retrieval sits in `version_or_date`.

## Contributing

- Add a source row first. Its id comes from `python3 _tools/kbid.py url <URL>`; never invent or hand-type an id, and never take "the next number". If the url already has a row (legacy or hash id), reuse that id. `check.py` rejects a hash id that does not match its url.
- When a pinned source is replaced (its upstream changed), add a new row for the new url, set the old row's `superseded_by` to the new id, and re-point the citations of the facts you re-verified. Never delete or reuse an id.
- Write the fact with its tag, then run `python _tools/check.py`.
- Save structured data as a pinned artifact, with a row in `_artifacts.csv` and a digest.
- Record disagreements in `_conflicts.md` and failed lookups in `_gaps.md`.

## Licensing

Each source's licence is recorded in `_sources.csv`.
- Verbatim copies appear only where the licence permits it, for example MIT, Apache-2.0 or CC BY 4.0 (most Microsoft Learn prose), and keep their attribution.
- Everything else is summarized in our own words, with quotes of at most 25 words.
- CIS Benchmark and ISO texts are never copied; only their ids are referenced.

## Coverage

| Topic | Priority | Status | Files | Sources |
|---|---|---|---|---|
| `ad/computer-attributes` | P1 | complete | `ad/computer-attributes.md`, `ad/computer-attributes.csv` | 9 |
| `ad/ldap-paging-filters` | P1 | complete | `ad/ldap-paging-filters.md` | 5 |
| `agents/agent-caching` | P1 | complete | `agents/agent-caching.md` | 8 |
| `agents/agent-dispatch-and-shared-services` | P1 | partial | `agents/agent-dispatch-and-shared-services.md` | 9 |
| `agents/agent-error-catalogue` | P1 | partial | `agents/agent-error-catalogue.md`, `agents/agent-error-catalogue.csv` | 11 |
| `agents/agent-evaluation` | P1 | partial | `agents/agent-evaluation.md` | 16 |
| `agents/agent-overuse-patterns` | P1 | partial | `agents/agent-overuse-patterns.md`, `agents/agent-overuse-patterns.csv` | 29 |
| `agents/agent-rbac` | P1 | complete | `agents/agent-rbac.md` | 10 |
| `agents/api-tokens-issue-and-store` | P1 | complete | `agents/api-tokens-issue-and-store.md`, `agents/api-tokens.csv`, `agents/secret-storage-options.csv` | 9 |
| `agents/copilot-studio-inventory` | P1 | complete | `agents/copilot-studio-inventory.md`, `agents/copilot-studio-feature-map.csv` | 26 |
| `agents/docs-maintenance-agents` | P1 | partial | `agents/docs-maintenance-agents.md` | 16 |
| `agents/eval-question-baseline` | P1 | partial | `agents/eval-question-baseline.md`, `agents/eval-question-baseline.csv` | 4 |
| `agents/headless-agent-runtimes` | P1 | partial | `agents/headless-agent-runtimes.md` | 10 |
| `agents/instruction-and-context-limits` | P1 | partial | `agents/instruction-and-context-limits.md`, `agents/instruction-and-context-limits.csv` | 25 |
| `agents/mcp-stress-testing` | P1 | partial | `agents/mcp-stress-testing.md` | 10 |
| `agents/own-chatbot-architecture` | P1 | complete | `agents/own-chatbot-architecture.md` | 10 |
| `agents/shared-ner-service` | P1 | partial | `agents/shared-ner-service.md` | 26 |
| `agents/subagents-vs-deterministic-tools` | P1 | complete | `agents/subagents-vs-deterministic-tools.md` | 25 |
| `agents/a2a-protocol` | P2 | partial | `agents/a2a-protocol.md`, `agents/a2a/a2a-proto-digest.md`, `agents/a2a/a2a.proto` | 10 |
| `agents/agent-cost-governance` | P2 | complete | `agents/agent-cost-governance.md` | 4 |
| `agents/anthropic-materials` | P2 | partial | `agents/anthropic-materials.md`, `agents/anthropic-materials.csv` | 23 |
| `agents/doc-lookup-sources` | P2 | partial | `agents/doc-lookup-sources.md`, `agents/doc-lookup-sources.csv` | 22 |
| `agents/genai-telemetry` | P2 | complete | `agents/genai-telemetry.md` | 5 |
| `agents/mcp-server-lifecycle` | P2 | partial | `agents/mcp-server-lifecycle.md` | 3 |
| `agents/prompt-injection-design-patterns` | P2 | complete | `agents/prompt-injection-design-patterns.md` | 6 |
| `ansible/dsc3-module` | P3 | complete | `ansible/dsc3-module.md` | 5 |
| `ansible/windows-ssh` | P3 | complete | `ansible/windows-ssh.md` | 1 |
| `arch/docs-home-options` | P1 | complete | `arch/docs-home-options.md` | 4 |
| `arch/gitlab-ci-components` | P1 | complete | `arch/gitlab-ci-components.md` | 10 |
| `arch/k8s-gmsa-windows` | P1 | complete | `arch/k8s-gmsa-windows.md` | 4 |
| `arch/kerberos-linux-containers` | P1 | complete | `arch/kerberos-linux-containers.md` | 5 |
| `arch/python-single-package-extras` | P1 | complete | `arch/python-single-package-extras.md` | 5 |
| `arch/sql-auth-containers` | P1 | complete | `arch/sql-auth-containers.md` | 4 |
| `arch/texts-catalogue-formats` | P1 | complete | `arch/texts-catalogue-formats.md` | 9 |
| `arch/twelve-factor-readiness` | P1 | complete | `arch/twelve-factor-readiness.md` | 12 |
| `arch/workload-identity-onprem-k8s` | P1 | complete | `arch/workload-identity-onprem-k8s.md` | 3 |
| `auth/configmgr-rbac-auth` | P0 | partial | `auth/configmgr-rbac-auth.md` | 6 |
| `auth/flows` | P0 | partial | `auth/flows.md`, `auth/flows.csv` | 26 |
| `auth/gitlab-ci-identity` | P0 | partial | `auth/gitlab-ci-identity.md` | 2 |
| `auth/gmsa-dmsa` | P0 | partial | `auth/gmsa-dmsa.md` | 1 |
| `auth/kerberos` | P0 | complete | `auth/kerberos.md` | 8 |
| `auth/ldap-smb-signing` | P0 | partial | `auth/ldap-smb-signing.md` | 7 |
| `auth/msal-public-client` | P0 | partial | `auth/msal-public-client.md` | 6 |
| `auth/ntlm-deprecation` | P0 | complete | `auth/ntlm-deprecation.md` | 5 |
| `auth/permissions-matrix` | P0 | partial | `auth/permissions-matrix.csv` | 16 |
| `auth/sql-authz` | P0 | partial | `auth/sql-authz.md` | 2 |
| `auth/workload-identity` | P0 | partial | `auth/workload-identity.md` | 4 |
| `auth/ad-jit-membership` | P1 | complete | `auth/ad-jit-membership.md` | 2 |
| `auth/audit-events` | P1 | complete | `auth/audit-events.md`, `auth/audit-events.csv` | 19 |
| `auth/entra-intune-rbac` | P1 | partial | `auth/entra-intune-rbac.md` | 5 |
| `auth/group-claims` | P1 | partial | `auth/group-claims.md` | 2 |
| `auth/key-management-options` | P1 | partial | `auth/key-management-options.md` | 11 |
| `auth/propagation-latency` | P1 | partial | `auth/propagation-latency.md`, `auth/propagation-latency.csv` | 6 |
| `auth/revocation` | P1 | partial | `auth/revocation.md` | 12 |
| `auth/role-source-options` | P1 | partial | `auth/role-source-options.md` | 3 |
| `auth/token-lifetimes-cae` | P1 | partial | `auth/token-lifetimes-cae.md` | 3 |
| `auth/delegation-kcd-obo` | P2 | partial | `auth/delegation-kcd-obo.md` | 5 |
| `auth/enterprise-access-model` | P2 | partial | `auth/enterprise-access-model.md` | 5 |
| `auth/threats` | P2 | partial | `auth/threats.md`, `auth/threats.csv` | 3 |
| `auth/transport-crypto` | P2 | partial | `auth/transport-crypto.md` | 7 |
| `autopilot/device-identity` | P1 | partial | `autopilot/device-identity.md` | 11 |
| `autopilot/lifecycle` | P1 | complete | `autopilot/lifecycle.md` | 6 |
| `claude/data-retention` | P1 | partial | `claude/data-retention.md` | 3 |
| `claude/elicitation` | P1 | complete | `claude/elicitation.md` | 4 |
| `claude/hooks` | P1 | complete | `claude/hooks.md` | 2 |
| `claude/managed-mcp` | P1 | complete | `claude/managed-mcp.md` | 2 |
| `claude/otel-monitoring` | P1 | complete | `claude/otel-monitoring.md` | 4 |
| `claude/permissions-mcp` | P1 | complete | `claude/permissions-mcp.md` | 4 |
| `claude/tool-output-limits` | P1 | complete | `claude/tool-output-limits.md` | 3 |
| `defender/machine-resource` | P1 | partial | `defender/machine-resource.md`, `defender/machine-properties.csv` | 8 |
| `defender/permissions-limits` | P1 | complete | `defender/permissions-limits.md` | 6 |
| `dsc/cli-reference` | P0 | complete | `dsc/cli-reference.md`, `dsc/cli/` | 9 |
| `dsc/directives` | P0 | complete | `dsc/directives.md` | 10 |
| `dsc/functions` | P0 | complete | `dsc/functions.md`, `dsc/functions-3.3.0.csv` | 7 |
| `dsc/manifests-diff` | P0 | complete | `dsc/manifests-diff.md`, `dsc/manifests-diff.csv`, `dsc/manifests/`, `dsc/zip-extras/` | 7 |
| `dsc/mcp-server` | P0 | complete | `dsc/mcp-server.md` | 10 |
| `dsc/open-bugs-windows` | P0 | complete | `dsc/open-bugs-windows.md`, `dsc/open-bugs.csv` | 1 |
| `dsc/releases-feature-matrix` | P0 | complete | `dsc/releases-feature-matrix.md` | 24 |
| `dsc/schemas` | P0 | complete | `dsc/schemas.md`, `dsc/schemas/` | 14 |
| `dsc/secrets` | P0 | complete | `dsc/secrets.md` | 9 |
| `dsc/settings-and-paths` | P0 | complete | `dsc/settings-and-paths.md` | 7 |
| `dsc/what-if` | P0 | complete | `dsc/what-if.md` | 11 |
| `entra/bitlocker-key-deletion` | P1 | complete | `entra/bitlocker-key-deletion.md` | 4 |
| `entra/device-identity` | P1 | complete | `entra/device-identity.md` | 6 |
| `entra/dsregcmd` | P1 | partial | `entra/dsregcmd.md`, `entra/dsregcmd-fields.csv` | 2 |
| `entra/hybrid-deviceid-objectguid` | P1 | partial | `entra/hybrid-deviceid-objectguid.md` | 7 |
| `entra/stale-devices` | P1 | complete | `entra/stale-devices.md` | 3 |
| `gitlab/codeowners` | P0 | complete | `gitlab/codeowners.md` | 3 |
| `gitlab/mr-approvals` | P0 | complete | `gitlab/mr-approvals.md` | 7 |
| `gitlab/pipelines-rules` | P0 | complete | `gitlab/pipelines-rules.md` | 5 |
| `gitlab/protected-branches-tags` | P0 | complete | `gitlab/protected-branches-tags.md` | 3 |
| `gitlab/variables` | P0 | complete | `gitlab/variables.md` | 2 |
| `gpo/dsc-group-policy-adapter` | P2 | partial | `gpo/dsc-group-policy-adapter.md` | 1 |
| `gpo/gpo-export` | P2 | complete | `gpo/gpo-export.md` | 4 |
| `graph/csdl-device` | P1 | complete | `graph/csdl-device.md`, `graph/csdl-device.properties.csv`, `graph/csdl/device.v1.0.xml`, `graph/csdl/device.beta.xml` | 5 |
| `graph/csdl-managedDevice` | P1 | complete | `graph/csdl-managedDevice.md`, `graph/csdl-managedDevice.properties.csv`, `graph/csdl/managedDevice.v1.0.xml`, `graph/csdl/managedDevice.beta.xml` | 4 |
| `graph/csdl-windowsAutopilotDeviceIdentity` | P1 | complete | `graph/csdl-windowsAutopilotDeviceIdentity.md`, `graph/csdl-windowsAutopilotDeviceIdentity.properties.csv`, `graph/csdl/windowsAutopilotDeviceIdentity.v1.0.xml`, `graph/csdl/windowsAutopilotDeviceIdentity.beta.xml` | 4 |
| `graph/delta-query` | P1 | complete | `graph/delta-query.md` | 6 |
| `graph/permissions` | P1 | complete | `graph/permissions.md`, `graph/permissions.csv`, `graph/permission-ids.csv` | 14 |
| `graph/throttling` | P1 | partial | `graph/throttling.md` | 5 |
| `graph/tcm-apis` | P3 | complete | `graph/tcm-apis.md`, `graph/tcm-csdl-v1.0.xml`, `graph/tcm-csdl-beta.xml` | 18 |
| `intune/co-management` | P1 | complete | `intune/co-management.md` | 5 |
| `intune/collect-diagnostics` | P1 | complete | `intune/collect-diagnostics.md`, `intune/collect-diagnostics.csv` | 1 |
| `intune/device-query` | P1 | complete | `intune/device-query.md` | 4 |
| `intune/ime-logs` | P1 | complete | `intune/ime-logs.md` | 1 |
| `intune/mdmdiagnosticstool` | P1 | partial | `intune/mdmdiagnosticstool.md` | 3 |
| `intune/remediations` | P1 | partial | `intune/remediations.md` | 3 |
| `intune/tenant-attach` | P1 | complete | `intune/tenant-attach.md` | 5 |
| `logs/ecs-log-fields` | P1 | complete | `logs/ecs-log-fields.md`, `logs/ecs-log.yml` | 2 |
| `logs/otel-log-data-model` | P1 | complete | `logs/otel-log-data-model.md` | 1 |
| `logs/otel-log-semconv` | P1 | complete | `logs/otel-log-semconv.md`, `logs/otel-semconv-log-registry.yaml`, `logs/otel-semconv-code-registry.yaml` | 5 |
| `logs/sources` | P1 | partial | `logs/sources.md`, `logs/sources.csv` | 16 |
| `logs/otel-collector-receivers` | P3 | complete | `logs/otel-collector-receivers.md`, `logs/otel-filelogreceiver.config.csv`, `logs/otel-windowseventlogreceiver.config.csv`, `logs/otel-filelogreceiver.metadata.yaml`, `logs/otel-windowseventlogreceiver.metadata.yaml` | 5 |
| `mcp/authorization` | P1 | complete | `mcp/authorization.md` | 3 |
| `mcp/deprecations` | P1 | complete | `mcp/deprecations.md` | 3 |
| `mcp/elicitation` | P1 | complete | `mcp/elicitation.md` | 6 |
| `mcp/python-sdk` | P1 | complete | `mcp/python-sdk.md` | 18 |
| `mcp/security-best-practices` | P1 | complete | `mcp/security-best-practices.md` | 2 |
| `mcp/spec-overview` | P1 | complete | `mcp/spec-overview.md`, `mcp/schema/2026-07-28/README.md`, `mcp/schema/2026-07-28/schema.ts`, `mcp/schema/2026-07-28/schema.json` | 7 |
| `mcp/tasks-extension` | P1 | complete | `mcp/tasks-extension.md` | 5 |
| `mcp/tools` | P1 | complete | `mcp/tools.md` | 7 |
| `mcp/transports-stdio` | P1 | complete | `mcp/transports-stdio.md` | 6 |
| `mecm/adminservice` | P0 | partial | `mecm/adminservice.md`, `mecm/adminservice-routes.csv` | 21 |
| `mecm/application-model` | P0 | complete | `mecm/application-model.md` | 4 |
| `mecm/baselines` | P0 | partial | `mecm/baselines.md` | 6 |
| `mecm/client-notification` | P0 | partial | `mecm/client-notification.md`, `mecm/client-operation-types.csv` | 12 |
| `mecm/client-settings` | P0 | partial | `mecm/client-settings.md` | 2 |
| `mecm/cmpivot` | P0 | partial | `mecm/cmpivot.md`, `mecm/cmpivot-entities.csv` | 12 |
| `mecm/compliance-script-ci` | P0 | partial | `mecm/compliance-script-ci.md` | 7 |
| `mecm/log-files` | P0 | complete | `mecm/log-files.md`, `mecm/log-files.csv` | 3 |
| `mecm/logging` | P0 | partial | `mecm/logging.md` | 5 |
| `mecm/rbac` | P0 | partial | `mecm/rbac.md`, `mecm/rbac-permissions.csv` | 15 |
| `mecm/run-scripts` | P0 | partial | `mecm/run-scripts.md` | 13 |
| `mecm/sql-views-compliance` | P0 | partial | `mecm/sql-views-compliance.md`, `mecm/sql-views-compliance.csv` | 9 |
| `mecm/versions-lifecycle` | P0 | complete | `mecm/versions-lifecycle.md` | 5 |
| `mecm/collect-client-logs` | P2 | partial | `mecm/collect-client-logs.md` | 6 |
| `powerbi/configmgr-views` | P2 | partial | `powerbi/configmgr-views.md` | 2 |
| `powerbi/on-prem-gateway-sql` | P2 | complete | `powerbi/on-prem-gateway-sql.md` | 8 |
| `powerbi/row-level-security` | P2 | complete | `powerbi/row-level-security.md` | 2 |
| `powerbi/scheduled-refresh` | P2 | complete | `powerbi/scheduled-refresh.md` | 4 |
| `prior-art/device-identity-correlation` | P2 | partial | `prior-art/device-identity-correlation.md` | 4 |
| `prior-art/drift-detection` | P2 | partial | `prior-art/drift-detection.md` | 3 |
| `prior-art/layered-settings-resolution` | P2 | complete | `prior-art/layered-settings-resolution.md` | 2 |
| `prior-art/log-collection-normalization` | P2 | partial | `prior-art/log-collection-normalization.md` | 2 |
| `prior-art/mcp-microsoft-endpoint-mgmt` | P2 | partial | `prior-art/mcp-microsoft-endpoint-mgmt.md` | 1 |
| `prior-art/pseudonymization-tokenization` | P2 | complete | `prior-art/pseudonymization-tokenization.md` | 3 |
| `prior-art/secret-vault-encryption` | P2 | complete | `prior-art/secret-vault-encryption.md` | 5 |
| `prior-art/tiered-approval-ops` | P2 | partial | `prior-art/tiered-approval-ops.md` | 4 |
| `privacy/gdpr-pseudonymisation` | P0 | partial | `privacy/gdpr-pseudonymisation.md` | 6 |
| `privacy/gliner-models` | P0 | partial | `privacy/gliner-models.md`, `privacy/gliner-models.csv` | 6 |
| `privacy/nist-sp800-38g` | P0 | complete | `privacy/nist-sp800-38g.md` | 5 |
| `privacy/presidio` | P0 | complete | `privacy/presidio.md` | 12 |
| `privacy/presidio-entities` | P0 | complete | `privacy/presidio-entities.md`, `privacy/presidio-entities.csv` | 14 |
| `privacy/presidio-evaluator` | P0 | complete | `privacy/presidio-evaluator.md` | 4 |
| `privacy/presidio-operators-deanonymize` | P0 | complete | `privacy/presidio-operators-deanonymize.md` | 13 |
| `privacy/presidio-recognizer-yaml` | P0 | complete | `privacy/presidio-recognizer-yaml.md`, `privacy/presidio-recognizer-registry.schema.json`, `privacy/presidio-example_recognizers.yaml` | 7 |
| `privacy/spacy-model-licence` | P0 | complete | `privacy/spacy-model-licence.md` | 4 |
| `reuse/device-identity-correlation` | P2 | complete | `reuse/device-identity-correlation.md` | 6 |
| `reuse/drift-detection` | P2 | complete | `reuse/drift-detection.md` | 5 |
| `reuse/layered-settings-resolution` | P2 | complete | `reuse/layered-settings-resolution.md` | 3 |
| `reuse/log-collection-normalization` | P2 | complete | `reuse/log-collection-normalization.md` | 3 |
| `reuse/mcp-microsoft-endpoint-mgmt` | P2 | complete | `reuse/mcp-microsoft-endpoint-mgmt.md` | 1 |
| `reuse/pseudonymization-tokenization` | P2 | complete | `reuse/pseudonymization-tokenization.md` | 4 |
| `reuse/secret-vault-encryption` | P2 | complete | `reuse/secret-vault-encryption.md` | 11 |
| `reuse/tiered-approval-ops` | P2 | complete | `reuse/tiered-approval-ops.md` | 6 |
| `security/baselines-catalog` | P0 | partial | `security/baselines-catalog.csv`, `security/baselines-catalog.md` | 20 |
| `security/dsc-coverage` | P0 | complete | `security/dsc-coverage.md` | 12 |
| `security/first-baseline-candidates` | P0 | partial | `security/first-baseline-candidates.md` | 11 |
| `security/policy-precedence` | P0 | partial | `security/policy-precedence.md` | 6 |
| `security/settings-crosswalk` | P0 | partial | `security/settings-crosswalk.md`, `security/settings-crosswalk.csv`, `security/artifacts/disa/`, `security/artifacts/microsoft/`, `security/artifacts/osconfig/` | 18 |
| `security/logging-monitoring` | P1 | partial | `security/logging-monitoring.md` | 9 |
| `security/management-plane-hardening` | P1 | partial | `security/management-plane-hardening.md` | 12 |
| `security/script-and-code-signing` | P1 | partial | `security/script-and-code-signing.md` | 7 |
| `security/supply-chain` | P1 | partial | `security/supply-chain.md` | 12 |
| `security/ai-agent-guidelines` | P2 | partial | `security/ai-agent-guidelines.md` | 16 |
| `security/framework-control-map` | P2 | partial | `security/framework-control-map.csv`, `security/framework-control-map.md` | 5 |
| `security/privacy-compliance` | P2 | partial | `security/privacy-compliance.md` | 13 |
| `security/threat-model-inputs` | P2 | complete | `security/threat-model-inputs.md`, `security/artifacts/mitre/attack-subset.csv`, `security/artifacts/mitre/attack-subset.md` | 12 |
| `sqlserver/insert-only-audit` | P0 | partial | `sqlserver/insert-only-audit.md` | 4 |
| `sqlserver/linux-container` | P0 | partial | `sqlserver/linux-container.md`, `sqlserver/mssql-server-tags.json` | 8 |
| `sqlserver/sp-getapplock` | P0 | complete | `sqlserver/sp-getapplock.md` | 1 |
| `sqlserver/temporal-tables` | P0 | complete | `sqlserver/temporal-tables.md` | 7 |
| `standards/owasp` | P2 | partial | `standards/owasp.md`, `standards/owasp.csv` | 6 |
| `windows/execution-policy-signing` | P0 | complete | `windows/execution-policy-signing.md` | 9 |
| `windows/gitlab-runner-windows` | P0 | partial | `windows/gitlab-runner-windows.md` | 11 |
| `windows/gmsa` | P0 | partial | `windows/gmsa.md` | 6 |
| `windows/openssh-server` | P0 | complete | `windows/openssh-server.md` | 3 |
| `windows/smart-app-control` | P1 | partial | `windows/smart-app-control.md` | 7 |
