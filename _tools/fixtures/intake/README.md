# intake replay fixture

The state of the repository on 2026-09-29 (commit 2241f98b), reduced to what `test_intake.py`'s `intake_replay` tests
need, with the kb's placeholders in place of the author and of ids that name a session or a stored entry.

- `history.json`: the commits to re-create, oldest first. Each has `orig` (the original short sha, kept so a test can
  say which commit it means; the re-created commit has another id), `authored` and `committed` (the original dates),
  `message` (lines: the subject and the trailers as they were, bodies cut, `Claude-Session` lines left out), `files`
  (paths under `tree/` to copy in) and `touch` (paths to write a one-line placeholder to, which stand for the code and
  doc changes the commit made). The last commit has no `orig` and changes nothing: it is dated 2026-10-03, the day
  intake runs, because the stranded-findings detector counts days to HEAD's commit day and the findings of the review
  were one to two days old on 2026-09-29.
- `tree/kb/_querylog/findings/`: the findings files of four runs, cut to the records the tests read (the three the
  story names, a fixed-since gap and eval, and a gap a later run applied); `entry` ids are placeholders and
  `kb_commit` is zeros; the headers' counts match the records left. The first commit writes two of the four files
  (the second one's original commit carried a KB-Work line git does not read too, which the story does not list).
- `tree/kb/_self/backlog/`: three item files as the original commits wrote them: ST-rjxacpdh (draft), TK-if7de5pb
  (done) and BG-jam2lysj (draft, with touches). BG-jam2lysj's check is replaced by one that runs in a reduced tree
  (it was a run of `_tools/tests.py`).

The hosts in the findings (docs.github.com, www.anthropic.com) are the public ones the kb already names.
