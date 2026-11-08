---
topic: agents/policy-as-code
priority: P3
applies_to: "Open Policy Agent v1.21.2 and v1.21.3 (Rego, bundles, bundle signing and configuration, REST API); Cedar docs at commit 3a37098e (2026-09-25); Amazon Verified Permissions (Cedar 4.7); Policy in Amazon Bedrock AgentCore (GA 2026-03-03); Azure Policy effects, remediation and Policy as Code workflow (Learn, 2026-10)"
retrieved_utc: 2026-11-08
sources: [S-tcvnt2sk, S-iq6vp7q2, S-hvug6eux, S-fnw2pa3v, S-qbgkkkgs, S-lyw4ziag, S-ksyczslf, S-fd4vxmr2, S-gbndonu5, S-mflbdcpq, S-o6ybh6w2, S-tlwezbfd, S-3wgje3ri, S-sfwmzlty, S-dyazlyh5, S-nfmfjmf4, S-y5rp4spd, S-xgmsiz27, S-yzbv3f7p, S-gca2wrxp, S-prq2x4xt, S-ady4i6kn, S-o43a4uum, S-nvgcf3ru, S-777jjbr6, S-mz4pgiw4, S-xrw6ar44, S-iqk7tct2, S-rv5ikahl, S-jyby5slx, S-rjjydcbh]
status: partial
---

# Policy-as-code and policy-based access control for agents (OPA/Rego, Cedar, Azure Policy)

## Summary
Policy-as-code moves an authorization or governance rule out of the code that enforces it and into a declarative policy evaluated by an engine. Open Policy Agent (OPA) answers a query by evaluating its JSON input against Rego policies and data, and it pulls policy as signed, versioned bundles from a server. Cedar's authorizer evaluates a principal-action-resource-context request against `permit` and `forbid` policies: access is denied by default, and one satisfied `forbid` overrides every `permit`. Amazon Verified Permissions runs Cedar as a managed service with policy stores, schema validation and token-based authorization calls. Policy in Amazon Bedrock AgentCore applies Cedar to agent tool calls at a gateway. Azure Policy works one layer lower, on the Azure resources an automation creates: it denies, audits or modifies a create or update request, blocks deletes with `denyAction`, and remediates existing resources through a managed identity. Its definitions can live in source control under a Policy as Code workflow.

## Facts

### Open Policy Agent and Rego
- OPA separates policy decisions from their enforcement: the calling software queries OPA with structured data such as JSON as input, and OPA produces the decision by evaluating that input against policies and data. [DOC S-tcvnt2sk]
- An OPA decision is not limited to allow or deny: a policy can return arbitrary structured data as output, like the input it takes. [DOC S-tcvnt2sk]
- Rego's `default` keyword gives a rule a fallback value that applies when every rule of that name is undefined; a rule with no default and no matching body produces no value at all (undefined). [DOC S-fnw2pa3v]
- OPA's Data API takes a query as `POST /v1/data/{path}` with the input in the body; a path that is undefined still returns HTTP 200, but the response carries no `result` property. [DOC S-hvug6eux]
- So the caller that enforces an OPA decision has to treat a missing `result` as a refusal, or the policy has to declare `default allow := false`: otherwise an undefined decision answers 200 and an enforcement point that checks only the status code fails open. [DER S-hvug6eux, S-fnw2pa3v: undefined path returns 200 without result; default supplies a value when all rules are undefined]
- Bundles let OPA download policy and data from a remote HTTP server instead of having them pushed through the REST API; loaded policy is enforced immediately, and by default the REST API refuses to change policy and data that came from a bundle. [DOC S-o43a4uum]
- A bundle is a gzipped tarball of policy and data files built with `opa build`, which can also sign it; data files are placed in the `data` document by their directory path inside the tarball. [DOC S-o43a4uum]
- OPA polls for bundles between `min_delay_seconds` and `max_delay_seconds`, sends the last `Etag` in `If-None-Match` so the server can answer 304 Not Modified, and can use HTTP long polling (`long_polling_timeout_seconds`), falling back to periodic polling when the server does not support it. [DOC S-o43a4uum]
- With `persist: true` OPA writes each activated bundle to disk and starts from the most recently activated one when the bundle server cannot be reached. [DOC S-o43a4uum]
- A signed bundle carries a `.signatures.json` file of JWTs listing the files and their hashes; remote bundles take their verification keys from the configuration's `keys` section, and a bundle that holds signatures fails verification when no verification key is configured at all. [DOC S-o43a4uum]
- `opa eval` and `opa test` do not verify bundle signatures, so signature checking protects a running OPA that downloads bundles, not the pre-production commands. [DOC S-o43a4uum]
- OPA can also download bundles stored as images in OCI-compatible registries, with one bundle layer per image. [DOC S-o43a4uum]
- OPA's decision logs record each policy query with the policy queried, its input and the bundle metadata, for auditing and offline debugging; with decision logging on, API responses include a `decision_id`. [DOC S-qbgkkkgs]
- Rego policies are unit-tested with `opa test`, whose test rules replace the input with `with input as {...}` and report PASS or FAIL per test. [DOC S-lyw4ziag]
- `opa test` runs every rule whose name starts with `test_` in the Rego files it is given, loading the files of a directory argument; a `_test` package suffix is good practice but not required, and a rule prefixed `todo_` is reported as `SKIPPED`. [DOC S-lyw4ziag]
- OPA is a graduated project of the Cloud Native Computing Foundation, and its repository at v1.21.3 is licensed under the Apache License, Version 2.0. [DOC S-rv5ikahl, S-jyby5slx]

### OPA bundle manifest, signing and configuration
- A bundle's `.manifest` may carry a `revision` (for example a Git commit hash) and `roots`, the path prefixes of `data` the bundle owns; a manifest with no `roots` defaults to `[""]`, so all data and policy must come from that bundle. [DOC S-o43a4uum]
- OPA checks a scoped bundle when it loads it: the roots of one manifest must not overlap (not checked across bundles), each policy's `package` and all data must lie under the roots, and a failure is reported through the Status API. [DOC S-o43a4uum]
- A new snapshot bundle erases and overwrites the policy and data under its manifest's roots and leaves what other roots hold intact. [DOC S-o43a4uum]
- A bundle is fetched as `GET` of the service url followed by the bundle's `resource`, which defaults to `bundles/<name>` for the bundle's key in the configuration. [DOC S-o43a4uum]
- A bundle service should set an `Etag` on bundle responses; OPA sends it back in `If-None-Match`, and the service may answer `304 Not Modified` when the bundle is unchanged. [DOC S-o43a4uum]
- `.signatures.json` is a JSON object whose `signatures` array holds JWTs; OPA currently supports one signature per bundle. [DOC S-o43a4uum]
- The JWT payload must list `files`, each with `name` (a path in the bundle), `hash` and `algorithm`; `scope`, `iat` and `iss` are optional claims. [DOC S-o43a4uum]
- The documented file hash algorithms are MD5, SHA-1, SHA-224, SHA-256, SHA-384, SHA-512, SHA-512-224 and a last entry printed as `SHA-512-25`. [DOC S-o43a4uum]
- The hashing code at the same tag names that last algorithm `SHA-512-256`, beside `SHA-512-224`. [CODE S-iqk7tct2: v1/bundle/hash.go#walk, HashingAlgorithm]
- A file that is not JSON or YAML is hashed over its bytes; a JSON or YAML file is parsed, the fields of every object are ordered alphabetically, and the result is hashed, so whitespace does not change the hash. [DOC S-o43a4uum]
- The code decides "structured" by the file's base name, not its extension: only `data.json`, `data.yaml`, `.signatures.json` and `.manifest` are parsed before hashing, so any other `.json` file in a bundle is hashed over its bytes. [CODE S-rjjydcbh: v1/bundle/bundle.go#IsStructuredDoc]
- The hasher writes an object as `{`, each key JSON-encoded in sorted order, `:` and the value's encoding, with `,` between members and `}` at the end, an array as `[`, its elements and `]`, and every other value through Go's JSON encoder with HTML escaping off and the trailing newline removed. [CODE S-iqk7tct2: v1/bundle/hash.go#walk, HashingAlgorithm]
- Verification checks the JWT signature with the configured key, that the payload and the bundle hold the same set of files, and each file's hash; any failure leaves the previous bundle active and reports an activation failure in the Status API and the logs. [DOC S-o43a4uum]
- The key is chosen by `keyid` from the command line, else from the bundle's `signing` configuration, else from the JWT header's `kid`; a payload `scope` must equal the configured scope exactly, and `iat` and `iss` play no part in verification. [DOC S-o43a4uum]
- Any `bundles[_].signing` block, even an empty one, enforces verification. Top-level `keys` without one verify only bundles that carry `.signatures.json`, so an unsigned bundle still activates, with a warning logged at startup. [DOC S-o43a4uum, S-mz4pgiw4]
- Delta bundles cannot be signed: a bundle configured to verify signatures rejects them unless `bundles[_].signing.allow_unsigned_delta_bundles` is set, and activated delta bundles are not persisted. [DOC S-o43a4uum, S-mz4pgiw4]
- A `keys` entry has `key` (described as a PEM public key), `private_key`, `algorithm` (default `RS256`) and `scope`, and a scope in the bundle's `signing` block takes precedence over the key's. [DOC S-mz4pgiw4]
- The supported signing algorithms are ES256, ES384, ES512, HS256, HS384, HS512, PS256, PS384, PS512 and RS256 to RS512, HMAC with SHA-256 being `HS256`. [DOC S-mz4pgiw4]
- For HS256, HS384 and HS512 the verifier uses the configured key string's bytes as the HMAC secret; for the other algorithms it parses the key as a PEM block. [CODE S-xrw6ar44: v1/bundle/verify.go#parseVerificationKey]
- A service authenticates OPA's bundle requests with `services[_].credentials.bearer.token`, or `token_path` naming a file that holds the token, and an optional `scheme`. [DOC S-mz4pgiw4]
- `opa run` replaces `${NAME}` references in its configuration file with the environment variable's value, leaving a reference to an undefined variable unreplaced; other commands do not substitute. [DOC S-mz4pgiw4]
- `opa run --set-file KEY=PATH` sets a configuration value from a file's contents, such as a bearer token kept in a secrets file. [DOC S-mz4pgiw4]
- OPA masks secrets given in a service's `credentials` field from the `/v1/config` API, but a credential placed in custom configuration outside that field is returned to callers. [DOC S-mz4pgiw4]
- `persistence_directory` defaults to `$PWD/.opa`, and a persisted bundle is written by default to `./.opa/bundles/<bundle-name>/bundle.tar.gz`; `bundles[_].size_limit_bytes` caps each file in a bundle at 1073741824 bytes by default. [DOC S-mz4pgiw4, S-o43a4uum]

### Cedar policies
- A Cedar authorization request has four parts, principal, action, resource and context (PARC), and asks whether that principal may take that action on that resource in that context. [DOC S-ksyczslf]
- A Cedar policy has an effect (`permit` or `forbid`), a scope naming principal, action and resource (all three mandatory, unconstrained when written bare), and optional `when` and `unless` conditions over attributes of the principal, resource and context. [DOC S-fd4vxmr2]
- A policy matches only when the request matches its scope, every `when` condition is true and every `unless` condition is false; a `when` that reads an attribute the principal lacks does not match. [DOC S-fd4vxmr2]
- A policy with a scope and no conditions serves role-based access control; conditions over attributes make it attribute-based. [DOC S-fd4vxmr2]
- The authorizer combines policies by three rules: any satisfied `forbid` gives Deny, else any satisfied `permit` gives Allow, else Deny. The answer lists the determining policies and any that raised errors. [DOC S-ksyczslf]
- Cedar states the resulting properties as default deny, forbid overrides permit, and skip on error: a policy whose evaluation errors is left out of the decision rather than turning it into Deny. [DOC S-ksyczslf]
- A `forbid` alone allows nothing; access always needs a separate `permit`. [DOC S-fd4vxmr2]
- Validation checks policies against a schema of entity types, attributes, parent relationships and actions; once validated, policies cannot raise most evaluation errors on requests that fit the schema, a property Cedar states it has proved. [DOC S-gbndonu5]
- A schema change can make earlier-validated policies raise errors, and erroring policies are left out of the decision, so Cedar recommends reviewing policies after any schema change. [DOC S-gbndonu5]
- A policy template holds `?principal` and `?resource` placeholders; a template-linked policy fills them and stays linked, so a later change to the template applies to every linked policy. [DOC S-mflbdcpq]
- Skip on error means a `forbid` guardrail whose condition errors (a missing context attribute, a type mismatch) silently drops out and no longer denies, so a guardrail needs schema validation and `has` checks before reading optional attributes. [DER S-ksyczslf, S-gbndonu5: erroring policies are skipped; validation rules out most evaluation errors for schema-conformant requests]

### Amazon Verified Permissions and AgentCore Policy
- Amazon Verified Permissions is a managed authorization service for custom applications that writes its policies in Cedar and currently uses Cedar version 4.7. [DOC S-o6ybh6w2]
- Verified Permissions only authorizes: it assumes the principal was already authenticated elsewhere (OpenID Connect, Amazon Cognito or another provider), and policies can be managed in the console, through its API or as infrastructure as code such as CloudFormation. [DOC S-o6ybh6w2]
- A policy store holds policies and policy templates and can hold a schema; with policy validation on, a policy whose entity types, common types or actions do not fit the schema is rejected when added. [DOC S-tlwezbfd]
- AWS recommends one policy store per application, or per tenant for a multi-tenant application; every authorization request names a policy store, and stores created through the API or SDK have deletion protection off by default, unlike those made in the console. [DOC S-tlwezbfd]
- `IsAuthorized` takes principal, action, resource, context and entities and evaluates every policy in the store that applies to the request's entities. [DOC S-3wgje3ri]
- `IsAuthorizedWithToken` builds the principal from the claims of an ID or access token issued by the store's identity source, such as an OIDC provider like Amazon Cognito; the request cannot add principal data of its own. [DOC S-3wgje3ri]
- `BatchIsAuthorized` and `BatchIsAuthorizedWithToken` return decisions for up to 30 requests in one call: the first for one principal or one resource, the token form for one principal. [DOC S-3wgje3ri]
- So, beyond Cedar itself, Verified Permissions adds hosted storage of policies per application or tenant, validation against the schema when a policy is written, JWT-based principals from an identity source, batch decisions and API or CloudFormation management. Cedar's own evaluation rules are unchanged. [DER S-o6ybh6w2, S-tlwezbfd, S-3wgje3ri: features listed on the service pages; the authorizer is Cedar 4.7]
- Policy in Amazon Bedrock AgentCore stores Cedar policies in a policy engine attached to an AgentCore Gateway, which intercepts each agent tool call and evaluates it against the policies before the tool is reached. [DOC S-sfwmzlty]
- AgentCore Policy decides on the user's identity and on the tool's input parameters, can translate natural-language rules into Cedar policies and validate them, and logs each enforcement decision to CloudWatch. [DOC S-sfwmzlty]
- Policy in Amazon Bedrock AgentCore became generally available on 2026-03-03, in thirteen AWS Regions. [DOC S-dyazlyh5]

### Azure Policy on resources an automation creates
- Each Azure Policy definition has one effect: `addToNetworkGroup`, `append`, `audit`, `auditIfNotExists`, `deny`, `denyAction`, `deployIfNotExists`, `disabled`, `manual`, `modify` or `mutate`. [DOC S-nfmfjmf4]
- On a create or update request in a Resource Manager mode, Azure Policy evaluates effects before the request reaches the resource provider, in this order: `disabled`, then `append` and `modify`, `deny`, `audit`, `manual`, `auditIfNotExists`, and `denyAction` last. [DOC S-nfmfjmf4]
- `auditIfNotExists` and `deployIfNotExists` evaluate after the resource provider returns success. [DOC S-nfmfjmf4]
- Assignments at different scopes are evaluated independently and their result is cumulative most restrictive: one `deny` blocks a resource whatever other assignments allow. [DOC S-nfmfjmf4]
- `deny` fails a matching create or update with 403 Forbidden before it reaches the resource provider; existing resources that match are marked non-compliant, not removed. [DOC S-y5rp4spd]
- `audit` lets the request through, writes a `Microsoft.Authorization/policies/audit/action` warning event to the activity log and marks the resource non-compliant. [DOC S-xgmsiz27]
- `modify` adds, replaces or removes tags, sets a VM or scale set's `identity.type`, or changes modifiable alias properties on the request itself; existing resources are only marked non-compliant until a remediation task fixes them. [DOC S-gca2wrxp]
- `modify` skips a nested property when its parent is absent from the request payload, and its `conflictEffect` (default `deny`) decides what happens when an alias is not modifiable in the request's API version. [DOC S-gca2wrxp]
- `denyAction` blocks `DELETE` requests (the only supported action) with 403. Policy assignments, locks, deny assignments, deployment stacks and subscriptions are exempt, and subscription deletion and cascade deletion of child resources are not blocked. [DOC S-yzbv3f7p]
- Remediation tasks apply a `deployIfNotExists` template or `modify` operations to existing non-compliant resources, using the assignment's managed identity (system- or user-assigned, one per assignment); evaluation itself runs as the caller that made the request. [DOC S-prq2x4xt]
- A custom definition lists the roles remediation needs in `roleDefinitionIds`; the portal grants them to the managed identity automatically, but an assignment created through an SDK needs the roles granted by hand or remediation fails. [DOC S-prq2x4xt]
- A remediation task remediates 500 resources by default and up to 50,000, 10 in parallel by default (1 to 30), with a failure threshold of 100% by default. [DOC S-prq2x4xt]
- For Kubernetes (`Microsoft.Kubernetes.Data` mode), `deny` and `audit` carry an OPA Gatekeeper v3 constraint template whose Rego logic runs in the cluster. [DOC S-y5rp4spd]
- Microsoft's Azure Policy as Code workflow keeps definitions, initiatives, assignments and exemptions as JSON in source control (GitHub or Azure DevOps), deploys changes automatically, and recommends a central pipeline whose identity alone may write policy resources. [DOC S-ady4i6kn]
- The workflow tests a changed definition with an assignment in `enforcementMode` disabled, which audits without blocking. It then checks compliance, grants the managed identity its roles, tests remediation, and enables enforcement one environment at a time. [DOC S-ady4i6kn]
- Microsoft also recommends evaluating policy after any deployment to a test scope and failing deployment pipelines that create non-compliant resources. [DOC S-ady4i6kn]

### How it fits an agent that calls tools
- The engines sit at two layers. OPA, Cedar, Verified Permissions and AgentCore Policy decide whether an agent may make a call, at a gateway or an MCP server's own check; Azure Policy decides whether Azure accepts the resource the call creates, changes or deletes, whoever made it. [DER S-tcvnt2sk, S-ksyczslf, S-sfwmzlty, S-nfmfjmf4: decision engines take a principal/action/resource request; Azure Policy evaluates Resource Manager requests]
- An agent's Azure automation is governed by Azure Policy like any other caller: a `deny` or `denyAction` 403 is a policy refusal the agent should report, not retry, and a resource it creates under an `audit` assignment is created but shows as non-compliant. [DER S-y5rp4spd, S-yzbv3f7p, S-xgmsiz27: deny and denyAction return 403; audit lets the request through]
- Both decision engines suit a tiered confirm gate: a Cedar `forbid` on higher-tier tools unless the context carries a confirmation, or a Rego rule with `default allow := false`, keeps the tier table in reviewed policy files rather than in the server's code. [DER S-ksyczslf, S-fnw2pa3v: forbid overrides permit; default supplies the fallback value]
- No page of the OPA docs (v1.21.2), the Cedar docs or the AgentCore Policy page, read 2026-10-15, describes OPA or Cedar placed in front of an MCP server's tools outside AgentCore Gateway; two other projects' documentation does (the next two facts), read 2026-10-21. [UNK: looked in the OPA docs at v1.21.2, the Cedar docs and the AgentCore Policy page, 2026-10-15]
- Dapr's MCP access control page says MCP transports route every tool call through one HTTP endpoint with the tool name inside the JSON-RPC body (`params.name`), so path-based access control rules give no per-tool control, and recommends layering an OPA middleware on the MCP server's inbound pipeline that reads the body, extracts the tool name and applies a Rego policy keyed by caller App ID and tool name. [DOC S-nvgcf3ru]
- A bundle server written without OPA's own tooling must hash a `data.json` or `.manifest` file as OPA does: compact JSON with sorted keys (Python's `json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` is close), not the file's bytes, or a correctly signed bundle fails verification; how Go's encoder writes numbers can still differ from another language's, so numeric data is safest checked against `opa build --signing-key` output. [DER S-o43a4uum, S-iqk7tct2, S-rjjydcbh: structured files, chosen by base name, are hashed after sorting keys; primitives go through Go's JSON encoder]
- An HS256-signed bundle needs only a shared secret on both sides, an HMAC a standard library can compute, but the secret then verifies and signs alike, so whoever can read OPA's configuration can sign bundles; RS256 or ES256 keep signing apart from verification. [DER S-mz4pgiw4, S-xrw6ar44: HMAC algorithms take the key string as the secret; the other families use PEM keys]
- A `${NAME}` reference to a key or token works only under `opa run` and stays literal when the variable is unset, so a deployment must set it before start; a file named by `token_path` or `--set-file` keeps the token out of the configuration and the environment. [DER S-mz4pgiw4: substitution only with opa run, none for an undefined variable; token_path and --set-file read files]
- Stacklok's ToolHive documentation describes Cedar policies evaluated on every request to an MCP server, denying anything not explicitly permitted: the principal is `Client::<client_id>` taken from the access token's `sub` claim, an action is such as `Action::"call_tool"`, and a resource is such as `Tool::"weather"`. [DOC S-777jjbr6]

## Reference
| Engine | Policy language | Decision input | Distribution / storage | Default when nothing matches | Source |
|---|---|---|---|---|---|
| Open Policy Agent | Rego | arbitrary JSON `input` plus `data` | bundles over HTTP or OCI, signed with `.signatures.json`, polled or long-polled | undefined (no `result`) unless `default` is set | S-tcvnt2sk, S-iq6vp7q2, S-hvug6eux |
| Cedar (library) | Cedar | principal, action, resource, context, entities | the application's own store | Deny | S-ksyczslf, S-fd4vxmr2 |
| Amazon Verified Permissions | Cedar 4.7 | `IsAuthorized` / `IsAuthorizedWithToken` (JWT) | policy store per application or tenant, schema validation | Deny | S-o6ybh6w2, S-tlwezbfd, S-3wgje3ri |
| AgentCore Policy | Cedar (or natural language translated to Cedar) | agent tool call through AgentCore Gateway | policy engine attached to a gateway | Deny (Cedar) | S-sfwmzlty, S-dyazlyh5 |
| Azure Policy | JSON policy rule | Resource Manager create, update or delete request | definitions and assignments in Azure, kept as code in a repository | allowed (no matching `deny`) | S-nfmfjmf4, S-ady4i6kn |

- Related: `agents/agent-rbac.md` (MCP scopes, Claude Code tool rules, Entra Agent ID, Azure ABAC conditions), `agents/gitops-for-agents.md` (declarative, versioned agent configuration), `windows/azure-arc-servers.md` (Azure Machine Configuration, the guest-OS `auditIfNotExists`/`deployIfNotExists` policies), `security/ai-agent-guidelines.md` (tier and confirm controls).
- OPA docs: https://raw.githubusercontent.com/open-policy-agent/opa/v1.21.2/docs/docs/management-bundles/index.md; Cedar docs: https://raw.githubusercontent.com/cedar-policy/cedar-docs/3a37098eba6e02e716949cfc92b889b38db25602/docs/collections/_auth/authorization.md

## Examples
- SNIPPET: Rego rule that allows a low-tier tool call and denies everything else by default; context: OPA 1.x (Rego v1 syntax, `if` keyword), input `{"tool": ..., "tier": ...}` sent to `POST /v1/data/agent/tools/allow`; checked: no [DER S-fnw2pa3v, S-hvug6eux: default supplies the value when no rule matches; the Data API takes input at a path]

```rego
package agent.tools

default allow := false

allow if {
    input.tool == "get_device"
    input.tier < 2
}
```

- SNIPPET: Cedar policies that let a helpdesk agent group read a device and forbid any tier 2 or higher tool unless the request context carries a confirmation; context: Cedar 4.x, entity types `Agent`, `Group`, `Tool` and action `call` declared in a schema; checked: no [DER S-fd4vxmr2, S-ksyczslf: permit/forbid with scope and when/unless; forbid overrides permit, and the `has` test keeps a missing attribute from erroring the forbid away]

```cedar
permit (
  principal in Group::"helpdesk-agents",
  action == Action::"call",
  resource == Tool::"get_device"
);

forbid (
  principal,
  action == Action::"call",
  resource
)
when { resource.tier >= 2 }
unless { context has confirmed && context.confirmed };
```
