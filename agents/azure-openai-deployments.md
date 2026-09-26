---
topic: agents/azure-openai-deployments
priority: P2
applies_to: "Azure OpenAI in Microsoft Foundry Models: deployment types, quota/rate limits, provisioned throughput (PTU), API versions, auth and networking; docs current 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-psa4dspu, S-u75x3q42, S-wxhjirsk, S-pntdruql, S-joexcals, S-mw5epkyz, S-4mutzurm, S-uk5qyhwi, S-dymizpwc, S-vfwdpj2p]
status: partial
files: [agents/azure-openai-deployment-types.csv]
---

# Azure OpenAI deployment types, quota, and provisioned throughput

Does not repeat `agents/foundry-agent-service.md` (the Agent Runtime, toolboxes, threads/runs, agent RBAC
roles) or `agents/content-safety-prompt-shields.md` (Content Safety and Prompt Shields as a standalone
service). This article covers the model-deployment layer underneath Foundry agents: deployment type
choice and data residency, the TPM/RPM quota model, 429 behavior and rate-limit headers, provisioned
throughput (PTU) sizing and spillover, API version lifecycle, and Entra auth / private endpoints for the
inference data plane. Full deployment-type comparison table: `agents/azure-openai-deployment-types.csv`.

## Summary
- Nine deployment types (SKUs) group into three categories: **standard** (pay-per-token), **provisioned**
  (reserved PTU capacity), and **batch** (50% discount, 24-hour async, no real-time SLA); a **Developer**
  type exists only for fine-tuned model evaluation (24-hour lifetime, no SLA, no residency guarantee).
  Full table: `agents/azure-openai-deployment-types.csv`. [DOC S-psa4dspu]
- Start with **Global Standard** unless a specific reason (data residency, reserved throughput, batch
  cost) requires another type; new models launch on Global first, then Data Zone, then geography-based
  types last with no guaranteed date. [DOC S-psa4dspu]
- Quota is TPM (tokens-per-minute) assigned per subscription, per region, per model, **per deployment
  type**; RPM is derived from TPM by a per-model ratio (e.g. older chat models: 1 unit = 6 RPM / 1,000
  TPM; o1/o3/o4-mini family: 1 unit = 1 RPM / 1,000-10,000 TPM depending on model). [DOC S-u75x3q42]
- Every response carries rate-limit headers (`x-ratelimit-limit-requests`, `x-ratelimit-limit-tokens`,
  `x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`,
  `x-ratelimit-reset-tokens`); a 429 additionally carries `retry-after-ms`. [DOC S-u75x3q42]
- Provisioned (PTU) deployments have per-model minimum sizes and scale increments that differ for
  Global/Data-Zone-Provisioned vs. Regional-Provisioned (regional minimums/increments are larger); a
  deployment returns 429 once **PTU deployment utilization = PTUs consumed / PTUs deployed** exceeds
  100%, tracked as a leaky-bucket metric in Azure Monitor. [DOC S-wxhjirsk, S-pntdruql]
- Data residency is identical in structure across deployment "shapes": data at rest always stays in the
  resource's Azure geography; inferencing data for **Global** types may be processed in any Azure region,
  for **Data Zone** types only within the Microsoft-specified zone (US, EU, or APAC), and for **Standard /
  Regional Provisioned** types only within the resource's own Azure geography. [DOC S-psa4dspu]
- Default content filter: medium-severity threshold on hate/fairness, violence, sexual, and self-harm
  categories, applied to both prompts and completions; all customers can raise/lower the threshold
  (low/medium/high) separately for prompts and completions, but turning filtering fully off or to
  annotate-only requires Limited Access approval. [DOC S-uk5qyhwi, S-dymizpwc]
- The v1 GA data-plane API (opt-in since August 2025) removes the monthly `api-version` string for GA
  inference/authoring calls (`latest` and `preview` values only) and lets the stock OpenAI client library
  work against Azure with minimal code change; the last-generation GA API version is `2024-10-21`. [DOC
  S-4mutzurm]

## Facts

### Deployment types and data residency
- Standard deployments choose one of three data-processing locations: **global** (any Azure region),
  **data zone** (US/EU/APAC), or **Azure geography** (the resource's own region); provisioned deployments
  offer the same three except there is no "geography" option distinct from Regional Provisioned. [DOC
  S-psa4dspu]
- SKU names used in code/ARM/Bicep: `GlobalStandard`, `GlobalProvisionedManaged`, `GlobalBatch`,
  `DataZoneStandard`, `DataZoneProvisionedManaged`, `DataZoneBatch`, `Standard`, `ProvisionedManaged`
  (Regional Provisioned), `DeveloperTier`. [DOC S-psa4dspu]
- All deployment types live in the same Azure OpenAI / Foundry resource; there is no need to create a
  separate resource per deployment type. [DOC S-psa4dspu]
- EU Data Zone follows the Azure EU Data Boundary and can include EFTA countries (e.g. Norway,
  Switzerland) in addition to EU member states; Microsoft can add regions to a data zone without prior
  notice. [DOC S-psa4dspu]
- With Global Standard and Data Zone Standard, if the primary region has an outage, all traffic initially
  routed there is affected (no automatic cross-region failover implied by the deployment type itself).
  [DOC S-psa4dspu]
- **Instant access (preview)**: some models can be called by name with no deployment created at all; this
  is not a deployment type and has its own availability rules. [DOC S-psa4dspu]
- Azure Policy can block a specific deployment-type SKU account-wide via a policy rule on
  `Microsoft.CognitiveServices/accounts/deployments` matching `sku.name`. [DOC S-psa4dspu]
- Troubleshooting: "deployment type unavailable" = model doesn't support that SKU in the region; "quota
  exceeded" = TPM limit reached for the subscription/region/model/deployment-type; "provisioned capacity
  unavailable" = no PTU capacity in that region -- try another region or Global Provisioned. [DOC
  S-psa4dspu]

### Quota, rate limits, and 429 behavior
- Quota is assigned to a subscription per region, per model, per deployment type, in TPM; creating a
  deployment consumes TPM from that pool, and TPM can be moved between deployments of the same model
  (in increments of 1,000) up to the pool's total. [DOC S-u75x3q42]
- RPM is not set independently: it is derived from the assigned TPM using a per-model capacity-unit
  ratio, e.g. older chat models = 1 unit -> 6 RPM / 1,000 TPM; o1 & o1-preview = 1 unit -> 1 RPM / 6,000
  TPM; o3, o4-mini = 1 unit -> 1 RPM / 1,000 TPM; o3-mini, o1-mini, o3-pro = 1 unit -> 1 RPM / 10,000 TPM.
  [DOC S-u75x3q42]
- TPM allocation is unrelated to a model's max input-token limit; changing TPM does not change how many
  tokens a single request can contain. [DOC S-u75x3q42]
- Global Batch and Data Zone Batch carry a **separate enqueued-token quota** from online (standard/
  provisioned) traffic, so batch load never displaces online-deployment quota; enabling **dynamic quota**
  on batch deployments lets them opportunistically use extra capacity beyond the configured enqueued-token
  limit rather than fail the job. [DOC S-psa4dspu]
- Rate-limit response headers on every call: `x-ratelimit-limit-requests`, `x-ratelimit-limit-tokens`,
  `x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests` (seconds
  until the request window resets), `x-ratelimit-reset-tokens` (seconds until the token window resets);
  `retry-after-ms` appears only on 429 responses and gives the recommended wait in milliseconds. [DOC
  S-u75x3q42]
- The rate-limit token estimate for a request includes the requested `max_tokens`, not just tokens
  actually generated, so an oversized `max_tokens` can trigger a 429 even when the real response is short;
  setting `best_of` above 1 multiplies the token count charged against the rate limit per increment. [DOC
  S-u75x3q42]
- Four distinct 429 causes require different handling: (1) **rate limit exceeded** -- TPM/RPM quota used
  up, fix by rebalancing TPM or requesting a quota increase; (2) **system capacity throttling** -- backend
  is capacity-constrained, usually transient, retry with `retry-after-ms`; (3) **temporary rate limit
  adjustment** -- the shared pool for Standard/pay-as-you-go temporarily lowers the deployment's effective
  limit under high demand (visible as `x-ratelimit-limit-tokens` in the response being lower than the
  configured TPM) and typically resolves within hours; (4) **token budget exceeded by request
  parameters** -- an oversized `max_tokens` consumes rate-limit budget even though billed usage is low.
  [DOC S-u75x3q42]
- Standard (pay-as-you-go) deployments share a resource pool across tenants in a region; occasional 429s
  are expected, protective behavior, not a service defect -- Provisioned Throughput is the documented fix
  for workloads that cannot tolerate this. [DOC S-u75x3q42]
- Quota increase requests are processed in the order received; priority is given to subscriptions
  actively consuming their existing allocation, and requests that don't meet that condition can be
  denied. [DOC S-u75x3q42]

### Provisioned throughput (PTU)
- Regional Provisioned minimum PTU deployment and scale increment are per model/version and are
  substantially larger than Global/Data-Zone-Provisioned minimums for the same model (the sizing table is
  published per model-version pair and changes as new models launch). Example values observed for current
  models: `gpt-5.2` = 50 PTU minimum / 50 PTU increment (Regional); other recent models range from 25 to
  100 PTU minimum regionally. [DOC S-wxhjirsk]
- PTU quota is granted to a subscription regionally per offer type (Global, Data Zone, Regional) and caps
  total PTUs deployable in that region across all models/versions of that offer type; PTU quota and any
  reservation must match the region and shape (Global/Data Zone/Regional) intended for use. [DOC
  S-pntdruql, S-wxhjirsk]
- Throughput per PTU is expressed as **input TPM per PTU**, which varies enormously by model (from
  roughly 600 to tens of thousands of input TPM per PTU depending on model), plus an **output-to-input
  ratio** that weights output tokens more heavily than input tokens (e.g. 8x for gpt-5.1/gpt-5.2 family,
  4x for gpt-4.1 family) when computing utilization. [DOC S-wxhjirsk]
- Cached tokens are deducted 100% from PTU utilization, so repeated prompt-prefix tokens (prompt caching)
  don't consume PTU capacity. [DOC S-wxhjirsk]
- PTU deployment utilization = PTUs consumed in the period / PTUs deployed in the period; the deployment
  returns 429 on new calls once utilization exceeds 100%; utilization is exposed as the
  **Provisioned-managed utilization V2** metric in Azure Monitor and modeled as a leaky-bucket algorithm
  (usage adds to the bucket, capacity drains it based on deployed PTU count). [DOC S-pntdruql]
- **Spillover** (preview/GA per model) is an optional capability that routes traffic exceeding a
  provisioned deployment's capacity to a fallback (e.g. a paired standard deployment) instead of returning
  429; for some long-context models (`gpt-5.4`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`), requests over
  128K prompt tokens are always routed to spillover deployments if configured, else they error. [DOC
  S-wxhjirsk]
- Recommended PTU sizing workflow: use the Foundry portal's PTU/capacity calculator against historical
  token usage or estimated call shapes (input tokens, output tokens, RPM), then validate with a real
  traffic benchmark; PTU quota increase requests are typically approved within about two business days.
  [DOC S-wxhjirsk]

### API versions and content filtering
- Last-generation (versioned) GA data-plane API: `2024-10-21`, replacing the earlier `2024-06-01`; new
  versioned preview releases historically shipped on a roughly monthly cadence. [DOC S-4mutzurm]
- The next-generation **v1 API** (opt-in from August 2025) drops the monthly `api-version` for GA
  capabilities: pass no `api-version` (routes to `latest` GA) or `api-version=preview` for the
  version-less, always-current preview surface; individual preview features gate on request headers
  (e.g. historically `aoai-evals: preview`) or on an `alpha`/`preview` path segment instead. [DOC
  S-4mutzurm]
- v1 lets the stock `openai` client library (`OpenAI()` instead of `AzureOpenAI()`) call Azure OpenAI by
  setting `base_url` to `https://<resource>.openai.azure.com/openai/v1`, including with Microsoft Entra
  ID token auth and automatic token refresh, with minimal code differences from calling OpenAI directly.
  [DOC S-4mutzurm]
- Default content filter: an ensemble of multi-class classifiers scores four harm categories (hate and
  fairness, violence, sexual, self-harm) at four severities (safe, low, medium, high) for both prompts and
  completions; the default threshold filters at **medium and high**, leaving low/safe unfiltered. [DOC
  S-uk5qyhwi, S-dymizpwc]
- Prompt Shields (jailbreak detection) and the protected-material text/code classifiers are separate,
  binary, on-by-default classifiers that all customers can toggle off per deployment; some scenarios must
  keep them on to remain covered by the Customer Copyright Commitment. [DOC S-uk5qyhwi]
- Configurable filter thresholds are "low/medium/high", "medium/high", or "high" (all self-service, set
  separately for prompts vs. completions); "no filters" and "annotate only" both require Limited Access
  approval via the Modified Content Filters review form. `gpt-image-1` does not support content-filter
  configuration at all -- only the fixed default applies. [DOC S-uk5qyhwi]
- Content filter configurations are created at the resource level and then associated with one or more
  deployments; they are not per-deployment-type. [DOC S-uk5qyhwi]

### Authentication and networking
- Microsoft Entra ID (RBAC) authentication for the data-plane inference API requires a **custom
  subdomain** on the resource; without one, only key-based auth is available. [DOC S-joexcals]
- **Cognitive Services OpenAI User** (role id `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`) is the least-
  privileged built-in role for calling the inference API with Entra auth (chat completions, embeddings,
  etc.); **Cognitive Services OpenAI Contributor** additionally allows calling data-plane management
  operations such as On Your Data's public ingestion API. Assign at resource, resource-group,
  subscription, or management-group scope. [DOC S-joexcals, S-vfwdpj2p]
- Managed identity is the recommended non-interactive auth path for Azure-hosted callers: `Default
  AzureCredential` picks up a system-assigned identity automatically, or a user-assigned identity's
  client ID via `AZURE_CLIENT_ID` / `ManagedIdentityCredential(client_id=...)` when more than one identity
  is attached to the host. [DOC S-joexcals]
- Private connectivity uses a standard Azure Private Link private endpoint plus a private DNS zone for
  `privatelink.openai.azure.com` (or the account's equivalent); on-premises/local clients reach it either
  through a VM in the same VNet or a Point-to-Site VPN gateway with Entra ID authentication configured.
  [DOC S-mw5epkyz]

## Reference
| Type | SKU code | Data location | Billing | Notes | Source |
|---|---|---|---|---|---|
| Global Standard | `GlobalStandard` | any Azure region | pay-per-token | highest default quota; start here | S-psa4dspu |
| Global Provisioned | `GlobalProvisionedManaged` | any Azure region | reserved PTU | lowest, most consistent latency | S-psa4dspu |
| Global Batch | `GlobalBatch` | any Azure region | 50% off, separate quota | 24h target, no real-time SLA | S-psa4dspu |
| Data Zone Standard | `DataZoneStandard` | US/EU/APAC zone | pay-per-token | higher quota than geography types | S-psa4dspu |
| Data Zone Provisioned | `DataZoneProvisionedManaged` | US/EU/APAC zone | reserved PTU | zone compliance + predictable throughput | S-psa4dspu |
| Data Zone Batch | `DataZoneBatch` | US/EU/APAC zone | 50% off | zone-scoped Global Batch | S-psa4dspu |
| Standard | `Standard` | resource's Azure geography | pay-per-token | low/med volume, bursty | S-psa4dspu |
| Regional Provisioned | `ProvisionedManaged` | resource's Azure geography | reserved PTU | larger PTU minimums than global/zone | S-psa4dspu |
| Developer | `DeveloperTier` | any region, no residency guarantee | pay-per-token | fine-tune eval only, 24h lifetime | S-psa4dspu |

Full comparison and per-model PTU sizing columns: `agents/azure-openai-deployment-types.csv`.

- Related: `agents/foundry-agent-service.md` (the agent runtime and toolboxes built on top of these
  deployments -- see its Reference table for agent-level limits, not repeated here); back-linked from
  that article's Reference section. `agents/content-safety-prompt-shields.md` (Content Safety /Prompt
  Shields as a standalone moderation service, distinct from the built-in default content filter described
  here).

## Examples
- Assign the least-privilege inference role to a user-assigned managed identity at the resource scope
  (Azure CLI; placeholder subscription/resource-group/resource names):
  ```bash
  az role assignment create \
      --assignee "<managed-identity-object-id>" \
      --role "Cognitive Services OpenAI User" \
      --scope "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-PL-SRV-0042/providers/Microsoft.CognitiveServices/accounts/aoai-PL-SRV-0042"
  ```
- Call the v1 GA inference endpoint with the stock OpenAI Python client and Entra ID token auth (adapted
  from the documented pattern; placeholder endpoint and deployment name):
  ```python
  from openai import OpenAI
  from azure.identity import DefaultAzureCredential, get_bearer_token_provider

  token_provider = get_bearer_token_provider(
      DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
  )
  client = OpenAI(
      base_url="https://aoai-pl-srv-0042.openai.azure.com/openai/v1",
      api_key=token_provider,
  )
  response = client.responses.create(model="gpt-4.1-mini-deployment", input="ping")
  ```
- Detect and back off on a 429 using the documented rate-limit headers (Python, `requests`):
  ```python
  import time
  import requests

  resp = requests.post(url, headers=headers, json=payload)
  if resp.status_code == 429:
      wait_ms = int(resp.headers.get("retry-after-ms", "1000"))
      time.sleep(wait_ms / 1000)
  else:
      remaining_tokens = resp.headers.get("x-ratelimit-remaining-tokens")
  ```

Open UNKs: exact current TPM/RPM default values are model- and region-specific and change frequently
(see the live `quotas-limits` page rather than a pinned number here); the full PTU minimum/increment table
per model-version is large and volatile -- only representative examples are captured above, not a
complete `[UNK]` list. `status: partial` reflects that volatility, not a missing fact.
