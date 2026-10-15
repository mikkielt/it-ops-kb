---
topic: gitlab/multi-project-pipelines
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2 and @56c82a97, retrieved 2026-10-15): downstream pipelines, the `trigger` keyword, pipeline trigger API, CI/CD job token allowlist and fine-grained permissions; Free, Premium and Ultimate on GitLab.com, Self-Managed and Dedicated"
retrieved_utc: 2026-10-15
sources: [S-pt32lcdt, S447, S-xz7iisq3, S-7zthwzzb, S-5pu4zmds]
status: complete
---

# GitLab multi-project pipelines: trigger jobs, variables, mirrored status and job token scope

## Summary
A job with the `trigger` keyword starts a pipeline in another project (a multi-project pipeline) or in the same
project (a child pipeline). By default the trigger job succeeds as soon as the downstream pipeline is created;
`trigger:strategy: mirror` (GitLab 18.2+) makes it wait and take the downstream pipeline's status, which is what an
upstream pipeline that coordinates work in other repositories needs. Variables reach the downstream pipeline from the
trigger job's and the top-level `variables`, `inputs` pass typed values, and `trigger:forward` controls whether
pipeline variables go too. A job can also start a downstream pipeline through the pipeline trigger API with its
`CI_JOB_TOKEN`. What one project's job token may do in another project is set on the target project: its job token
allowlist (only itself by default), optional fine-grained permissions per allowlist entry (GA 18.3), and two push
settings for job-token Git pushes. The token never carries more than the rights of the user who started the job.

## Facts
### Downstream pipelines and trigger jobs
- Downstream pipelines (parent-child and multi-project) are documented for Free, Premium and Ultimate on GitLab.com,
  Self-Managed and Dedicated. [DOC S-pt32lcdt]
- A downstream pipeline is one that another pipeline triggered; it runs independently of and concurrently with the
  upstream pipeline. A child pipeline runs in the same project, a multi-project pipeline in a different one.
  [DOC S-pt32lcdt]
- A pipeline hierarchy holds up to 1000 downstream pipelines by default; administrators can change the limit.
  [DOC S-pt32lcdt]
- The user who triggers the upstream pipeline must have permission to start pipelines in the downstream project, or
  the downstream pipeline fails to start. [DOC S-pt32lcdt]
- The upstream pipeline has little control over a multi-project pipeline, but chooses its ref and passes CI/CD
  variables to it; the downstream pipeline shows in the downstream project's pipeline list and has no nesting limit.
  [DOC S-pt32lcdt]
- A multi-project pipeline affects the status of the ref in the project it runs in, not the triggering pipeline's
  ref, unless the trigger job uses `trigger:strategy`. [DOC S-pt32lcdt]
- `interruptible` in the upstream project does not cancel a multi-project pipeline when a new upstream pipeline runs
  for the same ref; a new pipeline for the same ref in the downstream project can cancel it. [DOC S-pt32lcdt]
- The upstream project's pipelines page always shows the downstream project's name and the downstream pipeline's
  status, so a public project triggering a private one can expose both. [DOC S-pt32lcdt]
- `trigger: <path>` or `trigger:project` names the downstream project by full path (CI/CD variables allowed, job-only
  variables not); without `trigger:branch` the pipeline runs for the default branch, and `branch` takes a branch or tag
  name. [DOC S447]
- A trigger job starts `pending` while GitLab creates the downstream pipeline and then shows `passed`, or `failed` if
  creation failed; trigger jobs use no runner, so a long `pending` usually means the pipeline could not be created.
  [DOC S-pt32lcdt]
- Trigger jobs take only `allow_failure`, `extends`, `needs` (not `needs:project`), `only`/`except`, `parallel`,
  `rules`, `stage`, `trigger`, `variables`, `when` (`on_success`, `on_failure`, `always` or `manual`),
  `resource_group` and `environment`. [DOC S447]
- A `when: manual` trigger job cannot be started through the API, and no variables can be entered before running a
  manual trigger job. [DOC S447]
- In every job of a downstream pipeline started with `trigger`, `CI_PIPELINE_SOURCE` is `pipeline` for a
  multi-project pipeline and `parent_pipeline` for a child pipeline, so downstream `rules` can select on it.
  [DOC S-pt32lcdt]
- With `environment` on a trigger job, a downstream deployment project can deploy for the upstream project and the
  upstream project shows the environment and deployment. [DOC S-pt32lcdt]

### Mirroring the downstream status
- `trigger:strategy` makes the trigger job wait for the downstream pipeline to finish before it is marked success
  (the default marks it success once the pipeline is created), so execution becomes linear. [DOC S447]
- `strategy: mirror` (introduced in GitLab 18.2) mirrors the downstream pipeline's status exactly; `strategy: depend`
  is no longer recommended, because the trigger job's status does not always match the downstream pipeline's.
  [DOC S447]
- Under `depend` the trigger job shows running while the downstream pipeline waits for a manual action, and a
  downstream failure in an `allow_failure: true` job still counts as success. [DOC S447]
- Under either strategy, optional manual jobs downstream do not affect the status, blocking manual jobs must run
  before the trigger job passes or fails, and later upstream stages wait for the trigger job by default. [DOC S447]
- A parent pipeline auto-cancels when a child job fails only if both pipelines set
  `workflow:auto_cancel:on_job_failure` and the trigger job uses `strategy: mirror`. [DOC S-pt32lcdt]
- The reverse direction: `needs:pipeline: <project path>` copies the latest default-branch pipeline status of an
  upstream project into a job; adding `job` turns it into an artifact fetch (`needs:pipeline:job`) that no longer
  mirrors the status. [DOC S447]
- Retrying a trigger job (**Run again**) creates a new downstream pipeline that replaces the old one in the graph.
  [DOC S-pt32lcdt]

### Passing variables and inputs
- Variables defined in the trigger job and top-level default `variables` are passed to the downstream pipeline,
  where they count as pipeline variables for precedence; `inherit:variables: false` stops default variables from
  being passed. [DOC S-pt32lcdt]
- `trigger:inputs` (GitLab 17.11+) passes inputs to a multi-project pipeline whose configuration declares
  `spec:inputs`. [DOC S447]
- The downstream pipelines page recommends inputs over variables for pipeline configuration, citing type checking,
  validation through options, descriptions and default values. [DOC S-pt32lcdt]
- A predefined variable reaches the downstream pipeline only copied into a trigger-job variable (for example
  `UPSTREAM_BRANCH: $CI_COMMIT_REF_NAME`); job-only variables are not available in trigger jobs, and variables from
  the runner's `config.toml` are never passed. [DOC S447]
- A masked variable passed this way to a multi-project pipeline loses its masking, so it can appear unmasked in the
  downstream project's job logs; the docs say not to do it. [DOC S-pt32lcdt]
- When upstream and downstream define a variable with the same name, the upstream value takes precedence.
  [DOC S-pt32lcdt]
- `trigger:forward`: `yaml_variables` (default `true`) passes the trigger job's and default variables;
  `pipeline_variables` (default `false`) also passes pipeline variables, from manual runs, schedules and dotenv of
  `needs` jobs. Forwarded variables are not forwarded again by a nested trigger unless it also uses `forward`.
  [DOC S447]
- Variables forwarded with `trigger:forward` are trigger variables, which have the highest precedence.
  [DOC S-pt32lcdt]
- A downstream job fetches an upstream job's artifacts with `needs:project` (Premium and Ultimate); it needs the
  downstream project on the upstream project's job token allowlist and at least Reporter in the upstream project for
  the triggering user, which the allowlist does not grant. [DOC S-pt32lcdt]

### Starting a downstream pipeline through the API
- `POST /projects/:id/trigger/pipeline` takes a trigger token or a CI/CD job token, a required `ref`, and optional
  `variables` and `inputs` maps. [DOC S-xz7iisq3]
- Called with a CI/CD job token, the endpoint creates a multi-project pipeline: the calling job is linked to it as
  upstream and shows on the pipeline graph; called with a trigger token from a job, it is not linked. [DOC S-xz7iisq3]
- A job token authenticates REST calls by the `JOB-TOKEN` header (recommended), a `token` form field, `job_token`
  data or a query string (not recommended); job tokens cannot authenticate GraphQL requests. [DOC S-7zthwzzb]
- Of the Pipelines API, a job token reaches only `PUT /projects/:id/pipelines/:pipeline_id/metadata`, and of the
  trigger API only `POST /projects/:id/trigger/pipeline`. [DOC S-7zthwzzb]

### Job token scope: what one project's job may do in another
- `CI_JOB_TOKEN` is generated per job, valid only while the job runs, masked in job logs, and has the access level of
  the user who triggered the pipeline over fewer resources than a personal access token. [DOC S-7zthwzzb]
- To use a job token against another project (the target), the job's project or group must by default be on the
  target project's job token allowlist; a project's allowlist holds only itself by default. [DOC S-7zthwzzb]
- The allowlist adds no permissions: the user who triggers the job must be a member of the target project and have
  the rights for the action. [DOC S-7zthwzzb]
- A group entry on the allowlist (GitLab 17.0+) covers every project in the group and its subgroups, matched each
  time a token is used, so later projects are included. [DOC S-7zthwzzb]
- Adding an entry needs Maintainer or Owner on the target project (and a role in an internal or private allowed
  project); the allowlist holds at most 200 groups and 200 projects, counted separately. It is set under **Settings >
  CI/CD > Job token permissions** or with the GraphQL API. [DOC S-7zthwzzb]
- Without the allowlist, a job token from any project can fetch artifacts, use the container and package registries,
  read releases, deployments and environments, and access the repository of a public or internal project; setting
  each feature to **Only project members** limits these to the allowlist. [DOC S-7zthwzzb]
- On Self-Managed and Dedicated a project can turn the allowlist off (**All groups and projects**) unless the instance
  setting **Enable and enforce job token allowlist for all projects** is on; the docs call that a security risk, for
  testing only. [DOC S-7zthwzzb]
- Fine-grained permissions (experiment 17.10, beta 18.0, generally available 18.3, all tiers) limit an allowlist
  entry to named REST endpoints, such as `READ_PIPELINES` for listing pipelines or trigger jobs and `ADMIN_PIPELINES`
  for pipeline metadata. [DOC S-5pu4zmds]
- **Allow Git push requests to the repository** (off by default, GA 18.4) lets only job tokens from the project's own
  pipelines push; such a push triggers no pipeline. [DOC S-7zthwzzb]
- **Allow cross-project Git push requests from allowlisted projects** (GA 19.1) also needs the push setting above, the
  allowlist on, the source on it with `admin_repositories` or default permissions, and Developer for the user who
  started the pipeline. [DOC S-7zthwzzb]
- The **Authentication log** (GitLab 17.6+) lists which other projects authenticated to this project with a job token;
  it shows up to 100 events, with the full log as a CSV download, and new events can take up to 5 minutes to appear.
  [DOC S-7zthwzzb]
- Since GitLab 19.0 job tokens use the JWT format by default; a top-level group can switch back to the legacy format
  until GitLab 20.0. [DOC S-7zthwzzb]

### How it fits
- An agent pipeline in project A that must start and wait on work in project B uses a trigger job with
  `trigger:project` and `strategy: mirror`, so A's later stages run only if B's pipeline succeeds and B's failure
  fails A; without a strategy A only learns that B's pipeline was created. [DER S447, S-pt32lcdt: default trigger
  status, the `mirror` strategy and multi-project status rules]
- Coordination across repositories is set on the target side: a trigger job needs the triggering user's pipeline
  rights in B, an API call with A's job token needs A on B's allowlist, and an artifact fetch needs B on A's
  allowlist, so each pair of projects gets the narrowest entry (a fine-grained one where an endpoint is listed) rather
  than an instance-wide opening. [DER S-pt32lcdt, S-7zthwzzb, S-5pu4zmds: who must have which right, and the
  allowlist direction]
- Secrets for the downstream project stay as its own CI/CD variables: a masked upstream variable passed through
  `variables` loses its masking downstream. [DER S-pt32lcdt: the masked-variable warning]

## Reference
| Mechanism | Starts downstream | Status back upstream | Rights needed | Source |
|---|---|---|---|---|
| `trigger:project` job | yes, default branch or `branch` | only with `strategy: mirror` (or `depend`) | triggering user can run pipelines in B | S447, S-pt32lcdt |
| `POST /projects/:id/trigger/pipeline` with `CI_JOB_TOKEN` | yes, given `ref` | job is linked as upstream; no status mirroring documented | A on B's job token allowlist; user's rights in B | S-xz7iisq3, S-7zthwzzb |
| `needs:pipeline` | no | copies B's latest default-branch status into a job | not stated on the page | S447 |
| `needs:project` artifacts | no | no | B on A's allowlist; Reporter in A (Premium, Ultimate) | S-pt32lcdt |

Related: `gitlab/automated-merge-requests.md` (job-token pushes to the own project and a commit's pipeline status);
`gitlab/variables.md` (protected, masked and hidden variables); `gitlab/pipelines-rules.md` (`rules:` and
`CI_PIPELINE_SOURCE`); `gitlab/package-registries.md` (job tokens across projects for packages);
`agents/api-tokens.csv` (the job token beside other credential kinds); `claude/cross-session-messaging.md` and
`claude/large-codebases.md` (coordinating Claude Code sessions across repositories).

## Examples
- SNIPPET: start a pipeline in another project, pass variables and wait for its result; context: GitLab 18.2 or later, any tier, the triggering user can run pipelines in the downstream project; checked: syntax [DOC S447: `trigger:project`, `trigger:branch`, `trigger:strategy` examples; DOC S-pt32lcdt: passing a predefined variable]
```yaml
deploy-downstream:
  stage: deploy
  variables:
    UPSTREAM_BRANCH: $CI_COMMIT_REF_NAME
  trigger:
    project: my-group/deployment-project
    branch: main
    strategy: mirror
```
