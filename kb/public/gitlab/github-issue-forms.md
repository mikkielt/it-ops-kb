---
topic: gitlab/github-issue-forms
priority: P3
applies_to: "GitHub issue forms (YAML files in .github/ISSUE_TEMPLATE; the form schema is a public preview feature) as documented in the github/docs source at be38ec5d, the github/issue-parser README at a52c1e09, and the GitHub CLI manual pages for gh issue create and gh issue view read 2026-10-23"
retrieved_utc: 2026-10-23
sources: [S-bgmri6cn, S-xkr7mklg, S-2bdzulia, S-ojcsnr2p, S-dwvfa6nv, S-4ophb6ze, S-fsrm2uki, S-see2fysn, S-otwixj3z, S-4kq7imwd, S-wahjf6r7]
status: partial
---

# GitHub issue forms: YAML syntax, field ids and labels, the rendered body, and writing and reading an issue with gh

## Summary
An issue form is a YAML file in `.github/ISSUE_TEMPLATE` whose `body` array lists the inputs a person fills in; GitHub turns the answers into Markdown and puts them in the issue body, one `### <label>` heading per input, an empty text input or text area as `_No response_`. The form's `labels`, `title` and `assignees` apply to issues created through that template, so an issue made from a body file with `gh issue create --body-file` is a plain issue: the body can copy the form's headings, but the labels have to be given with `--label`. `gh issue view <number|url> --json body` returns the body text for a tool that reads it back. The form schema is still marked public preview, and the page set does not document the rendered layout: the layout comes from GitHub's own issue-parser README.

## Facts
### The file and its top-level keys
- An issue form is a YAML file in the `.github/ISSUE_TEMPLATE` folder, named `FORM-NAME.yml`; "when a contributor fills out an issue form, their responses for each input are converted to markdown and added to the body of an issue", and the contributor can edit the issue afterwards. Issue forms are not supported for pull requests. [DOC S-bgmri6cn, S-2bdzulia]
- Every form begins with `name`, `description` and `body` (required: a unique name, the text shown in the template chooser, and the array of inputs); `assignees`, `labels`, `title`, `type` and `projects` are optional. `labels` and `assignees` take an array or a comma-delimited string. [DOC S-bgmri6cn]
- `labels` are "automatically added to issues created with this template"; a label that does not already exist in the repository is not added. `title` is a default title pre-filled in the form. [DOC S-bgmri6cn]
- The `name` must be more than 3 characters, or the template is not shown when an issue is created. [DOC S-2bdzulia]
- Markdown and YAML templates can live side by side in one repository; to give a YAML form the file name a Markdown template already has, the Markdown file must be deleted in the same commit. [DOC S-bgmri6cn]
- The template chooser is shaped by `.github/ISSUE_TEMPLATE/config.yml` (`blank_issues_enabled`), applied once the file is merged into the default branch; templates are listed alphanumerically with YAML files before Markdown ones, so a numeric filename prefix (`01-`, `02-`) sets the order. [DOC S-2bdzulia]

### Inputs, ids and labels
- A `body` element has a `type` (`markdown`, `textarea`, `input`, `dropdown`, `checkboxes`, and `upload` where available), an optional `id`, `attributes` (required) and `validations` (optional). [DOC S-xkr7mklg]
- `id` is optional and not allowed on a `markdown` element; it may use only alphanumeric characters, `-` and `_`, must be unique in the form, and "is the canonical identifier for the field in URL query parameter prefills". [DOC S-xkr7mklg, S-dwvfa6nv]
- A `markdown` element is shown in the form for context and is "not submitted", so it never appears in the issue body. A `#` in its YAML text starts a YAML comment unless the text is quoted. [DOC S-xkr7mklg]
- `textarea`, `input`, `dropdown` and `checkboxes` need a `label` attribute (the brief description shown in the form); `description` is optional. A textarea's `render` value formats the submitted text into a code block of that language, and then the field no longer takes file attachments or Markdown editing. [DOC S-xkr7mklg]
- A `dropdown` needs a non-empty `options` array of distinct strings, takes `multiple` (default false) and a `default` index; with a default set, "None" or "n/a" cannot be an option. A `checkboxes` input needs `options`, each with a `label`. [DOC S-xkr7mklg, S-see2fysn]
- `validations.required` prevents form submission until an element is completed and works "only for public repositories"; a textarea or input also takes `min_length`, a non-negative integer that prevents submission until the response is that long. [DOC S-xkr7mklg, S-4ophb6ze, S-fsrm2uki]

### The rendered body
- The issue-parser README states that issues from issue forms "use a structured Markdown format": each response sits under a `###` heading holding the input's label, followed by the answer. A parser matches a heading to a field `id` only when it is given the template; without it the heading text is the key. [DOC S-otwixj3z]
- An empty response is rendered by input type: `_No response_` for `input` and `textarea`, `None` for `dropdown`; a `checkboxes` input is rendered as `- [x]` and `- [ ]` list items, a multiple dropdown as a comma-separated line, and empty lines of a textarea answer are kept. [DOC S-otwixj3z]
- The README names the cases a parser omits: a heading that is not level three, an empty heading, and a heading with no value. So a body edited by hand ("heavily modified by the user") may not parse. [DOC S-otwixj3z]
- GitHub's docs pages for the form syntax do not show the rendered body; the layout above is the one GitHub's own parser reads, not a promise in the form schema, which the docs call public preview and subject to change. [DER S-bgmri6cn, S-xkr7mklg, S-otwixj3z: the pages read for a rendered-body section found none]

### Creating the issue from the web, a URL and gh
- A URL query opens the new-issue page filled in: `template=<file>` picks a template stored in an `ISSUE_TEMPLATE` directory, and a form's custom fields can be filled with their `id` as the parameter; an invalid URL or a missing permission returns `404 Not Found`, a URL over the server limit `414 URI Too Long`, and a query parameter such as `labels` needs the permission to add that label. [DOC S-ojcsnr2p, S-xkr7mklg]
- `gh issue create` takes `--title`, `-b/--body`, `-F/--body-file <file>` (`-` reads standard input), `-l/--label`, `-a/--assignee`, `-p/--project`, `-w/--web` and `--template <name>`, "template name to use as starting body text"; without a title or body it prompts. The `--attach` flag appends uploaded files to the body, and paths in a `--body-file` are relative to its directory, falling back to the working directory. [DOC S-4kq7imwd]
- `gh issue view {<number> | <url>}` displays an issue; `--json <fields>` prints chosen fields and `--jq` filters them. The field list includes `body`, `title`, `labels`, `url`, `number`, `state`, `author`, `createdAt` and `comments`. [DOC S-wahjf6r7]
- So an agent can write a body file in the form's layout, and the person who files it runs `gh issue create --title ... --body-file FILE --label ...` or pastes the file into the web form; the maintainer reads it back with `gh issue view <url> --json body --jq .body`. [DER S-4kq7imwd, S-wahjf6r7, S-otwixj3z: the flags and the field list; nothing in the pages says a CLI-created issue gets the form's labels]
- A `--body-file` issue is not created "with this template", so the form's `labels`, `title` and `assignees` do not apply on the documented reading; the labels are passed with `--label`. [DER S-bgmri6cn, S-4kq7imwd: `labels` apply to issues created with the template; `gh` has its own `--label`]
- The pages read do not say whether `gh issue create --template` fills a YAML issue form, whether the web form accepts a pasted body in a Markdown-only blank issue with the form's labels, or the maximum length of an issue body (the "maximum is 65536 characters" error text appears in third-party bug reports, not in the docs read). [UNK]

## Reference
| Need | Where | Source |
|---|---|---|
| form file | `.github/ISSUE_TEMPLATE/<name>.yml` with `name`, `description`, `body` | S-bgmri6cn |
| default labels | top-level `labels: [..]`, applied for issues created with the template | S-bgmri6cn |
| field ids | `id:` on an input, alphanumeric, `-`, `_`, unique | S-xkr7mklg, S-dwvfa6nv |
| answer in the body | `### <label>` then the answer; `_No response_` or `None` when empty | S-otwixj3z |
| create from a file | `gh issue create --title T --body-file FILE --label L` | S-4kq7imwd |
| read the body back | `gh issue view <url> --json body --jq .body` | S-wahjf6r7 |

See also `gitlab/automated-merge-requests.md` (`gh pr create`, `gh pr view`, `gh auth status`), `gitlab/github-branch-rules-and-auto-merge.md` and `agents/doc-change-detection.md` (reading GitHub issues through the REST API).

## Examples
- SNIPPET: a minimal issue form with a title field, a text area and a dropdown; context: GitHub issue forms (public preview schema), file `.github/ISSUE_TEMPLATE/example-report.yml`, placeholder names only; checked: no [DER S-bgmri6cn, S-xkr7mklg, S-dwvfa6nv: required top-level keys, element keys, id and option rules]
```yaml
name: Example report
description: A finding for the maintainers
labels: ["example-label"]
body:
  - type: input
    id: story-title
    attributes:
      label: Story title
    validations:
      required: true
  - type: textarea
    id: premise
    attributes:
      label: Premise or repro
      description: What happened and how to see it again.
  - type: dropdown
    id: scope
    attributes:
      label: Clone scope
      options:
        - me
        - team
        - org
```
- SNIPPET: the body that form produces when the person leaves the text area empty; context: GitHub issue-parser README layout, answers are placeholders; checked: no [DER S-otwixj3z: heading per label, `_No response_` for an empty text area]
```markdown
### Story title

Example finding

### Premise or repro

_No response_

### Clone scope

team
```
