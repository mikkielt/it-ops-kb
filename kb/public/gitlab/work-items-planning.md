---
topic: gitlab/work-items-planning
priority: P3
applies_to: "GitLab 19.x planning docs (gitlab-org/gitlab master @56c82a97, VERSION 19.5.0-pre): work items, child and linked items, status, weight, epics, iterations, milestones, scoped labels, health status; GitLab handbook issue triage (content-sites/handbook main @0f00de8e); read 2026-09-28"
retrieved_utc: 2026-09-28
sources: [S-cl4h4f7i, S-v2ztgtdn, S-evjlv5hf, S-il7kjbdz, S-nonpog4d, S-tyuv57qu, S-v53altt3, S-ntqzc5fg, S-kl7x7kl6, S-t7fbkn25, S-25zwwcdx]
status: complete
---

# GitLab planning: work items, hierarchy, dependencies, iterations, priority and severity

## Summary
GitLab plans work as work items: epics, issues, tasks, objectives and key results, and test cases, shown in one **Work items** list since 18.10. The hierarchy is epic, then issue, then task. Epics nest up to 7 levels deep, but nested epics are Ultimate only. Items link as **relates to**, **blocks** or **is blocked by**; the blocking links are Premium. Configurable statuses (GA in 18.4, Premium) sort into five categories, and only **Done** and **Canceled** close an item. Weight, iterations and scoped labels are Premium; health status is Ultimate; milestones are in every tier. Iterations are time boxes, usually 1 to 3 weeks, grouped in cadences that can schedule themselves and roll unfinished issues over. GitLab's own handbook uses `priority::1` to `priority::4` for scheduling importance. It uses `severity::1` (blocker) to `severity::4` (low) for a bug's impact, and each severity carries a resolution target.

## Facts
- Work item types: issues (tasks, features and bugs), epics (large initiatives across milestones and issues), tasks (small units of work), objectives and key results, and test cases; types can also be configured. [DOC S-cl4h4f7i]
- In GitLab 18.10 and later, **Plan > Work items** replaces the separate Issues and Epics list pages, and `/epics/:iid` and `/issues/:iid` URLs redirect to `/work_items/:iid` (the planning view went GA in 18.10). [DOC S-cl4h4f7i]
- The work items list filters by type, status, health status, iteration, label, milestone, parent, state and weight, among others, and sorts by created, updated, start and due date, title, status and weight. [DOC S-cl4h4f7i]
- Child items form the hierarchy: a child epic under a parent epic, an issue (a feature or bug) under an epic, and a task as a child of an issue. [DOC S-v2ztgtdn]
- An epic's Child items header shows the number of descendant work items and their total weight; task weights count in the issue weight. [DOC S-v2ztgtdn]
- Multi-level epic hierarchies are Ultimate: epics can nest child epics up to 7 levels deep, and a child epic may belong to another group. [DOC S-v2ztgtdn, S-tyuv57qu]
- An epic is the parent of one or more issues and, in Ultimate, of child epics; an epic may take issues from a different group hierarchy. [DOC S-tyuv57qu]
- Linked items are bi-directional relationships between work items, of three types: **Relates to** (a general relationship), **Blocks** (this item prevents progress on another) and **Is blocked by** (this item cannot proceed until another is resolved). [DOC S-evjlv5hf]
- Blocking links (tracking dependencies) are Premium and Ultimate; with them GitLab warns when an item with open blockers is closed. Linking epics is Ultimate. [DOC S-evjlv5hf]
- Work item status is Premium and Ultimate, GA in GitLab 18.4 (introduced in 18.2 behind `work_item_status_feature_flag`); statuses replace labels for managing a work item's lifecycle. [DOC S-il7kjbdz]
- The default statuses, which cannot be modified, are To do, In progress, Done, Won't do and Duplicate. [DOC S-il7kjbdz]
- Each status belongs to one of five categories: Triage (new or unprocessed), To do (ready to be started), In progress, Done and Canceled. Done and Canceled close the work item; every other category keeps it open. [DOC S-il7kjbdz]
- A lifecycle is a reusable set of statuses applied to a work item type, with default transition statuses such as the one applied when an item is marked duplicate, moved or promoted (GA in 18.6). [DOC S-il7kjbdz]
- Weight is Premium and Ultimate: a number representing a work item's estimated effort, value or complexity; lists sort by it, and a milestone page sums the weights of its items. Weights for epics came in 18.11. [DOC S-nonpog4d]
- An iteration (Premium and Ultimate, groups only) is a time box that groups issues for a period, usually 1 to 3 weeks; teams use iterations to track velocity and volatility. [DOC S-v53altt3]
- Iterations belong to iteration cadences, need both a start and an end date, and must not overlap within one cadence. [DOC S-v53altt3]
- A cadence can create iterations automatically every 1, 2, 3 or 4 weeks and roll incomplete issues over to the next iteration (**Enable roll over**). [DOC S-v53altt3]
- GitLab suggests milestones for program increments of 8 to 12 weeks and iterations for 2-week sprints, so one item can be tracked in two concurrent time boxes. [DOC S-v53altt3]
- Milestones (every tier) group issues, epics and merge requests toward a goal, with optional start and due dates, and can track a release: the due date is the release date and the title is the version. [DOC S-ntqzc5fg]
- A project milestone applies to that project's issues and merge requests only; a group milestone applies to any issue, epic or merge request in the group's projects. [DOC S-ntqzc5fg]
- Scoped labels (Premium and Ultimate) use `key::value`; an issue, merge request or epic cannot carry two scoped labels with the same key, and adding one replaces the other. `<scope>::*` filters by scope. [DOC S-kl7x7kl6]
- Health status (Ultimate) marks whether an issue is progressing as planned or needs attention, for review in stand-ups and status reports. [DOC S-t7fbkn25]
- GitLab's handbook defines four priority labels by scheduling intent: `priority::1` urgent (as soon as possible, regardless of team capacity, target within 30 days), `priority::2` high (next few releases, 60 to 90 days), `priority::3` medium (90 to 120 days), `priority::4` low (no timeline). [DOC S-25zwwcdx]
- The same page defines four severity labels for bugs by impact: `severity::1` blocker (a broken feature with no workaround, or any data loss), `severity::2` critical (unacceptably complex workaround), `severity::3` major (a workaround exists), `severity::4` low (inconvenient). [DOC S-25zwwcdx]
- Severity sets the bug resolution target: within 30 days for `severity::1`, the next release (60 days) for `severity::2`, the next 3 releases (about 90 days) for `severity::3`, and beyond that (more than a quarter) for `severity::4`. For availability bugs, `severity::1` and `severity::2` allow only `priority::1`. [DOC S-25zwwcdx]
- Triage in the handbook: a bug gets a type label and a severity label, and its severity comes with a note explaining the choice; an issue counts as completely triaged once it also has a milestone and, if it is a bug, a priority label. [DOC S-25zwwcdx]
- Severity and priority are separate axes in GitLab's process: severity states the impact of a bug, and priority states when it will be scheduled, set from impact, product direction and team capacity. [DER S-25zwwcdx: the two labels' definitions and the severity-to-priority tables]
- For a repository tracked without a GitLab plan (Free tier, or a tracker kept as files), the Free-tier parts are the epic/issue/task hierarchy, relates-to links and milestones. Blocking links, status, weight, iterations and scoped labels would each need Premium, so a file tracker has to carry its own `blocks`, status, priority and severity fields. [DER S-cl4h4f7i, S-evjlv5hf, S-il7kjbdz, S-nonpog4d, S-v53altt3, S-kl7x7kl6: tiers stated on each page]

## Reference
| Feature | Tier | Since |
|---|---|---|
| Work items list (all types) | Free | GA 18.10 |
| Epic > issue > task hierarchy | Free (nested epics Ultimate, 7 levels) | |
| Relates to | Free | |
| Blocks / is blocked by | Premium | |
| Status, lifecycles | Premium | GA 18.4 / 18.6 |
| Weight | Premium | epics 18.11 |
| Iterations, cadences, roll over | Premium (groups only) | |
| Milestones | Free | |
| Scoped labels | Premium | |
| Health status | Ultimate | |

| Severity (handbook) | General bug | Resolution target |
|---|---|---|
| `severity::1` blocker | broken, no workaround, or data loss | 30 days |
| `severity::2` critical | unacceptably complex workaround | next release (60 days) |
| `severity::3` major | workaround exists | next 3 releases (about 90 days) |
| `severity::4` low | inconvenient | beyond a quarter |

See also `agents/agent-planning-and-done.md` (Scrum's backlog, Sprint Goal and Definition of Done, and agent task lists), `gitlab/automated-merge-requests.md` (automation and merge requests).

## Examples
- A four-level plan in GitLab Free: an epic for the outcome, issues for features and bugs under it, tasks under each issue, and a milestone for the release. A blocker between two issues is only a **relates to** link with a note, since **blocks** needs Premium.
