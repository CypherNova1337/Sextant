# Leaderboard submissions

One entry per upload: what was submitted, what was checked before it, and the
outcome. Local results are on public dev tasks, re-scored in the Docker
sandbox with `scripts/verify_reference.py`.

| # | Date (UTC) | Agent | sha256 (zip) | Checked before upload | Outcome |
|---|---|---|---|---|---|
| 1 | 2026-09-30 21:23 | v1: single agent, edit_file, 4 min | `c7dc85c6` | validator and compiler; 3-task GPU run (0 of 3 resolved, every edit_file call malformed) | Notebook Threw Exception |
| 2 | 2026-10-01 01:03 | v4-rules: run_command edits with helper, anti-loop rules, T 0.6 | `9ec6aa1b` | validator and compiler; 10-task GPU run, 4 of 10 resolved, no exceptions | Notebook Threw Exception, within about 4 minutes |
| 3 | 2026-10-02 | v5: v4-rules agent, configs matched to a scored submission (all four eval_config keys, 4.5 min, thinking_budget present, no root description) | `ed4706a5` | validator, compiler and structure check; GPU run of these exact files on 4 dev tasks: no exceptions, all within the cap, 3 of 4 resolved (requests_6644, rich_3006, rich_3454; fastapi_14430 empty patch) | Public score 0.08 (about 5 of about 60 tasks) |

## Notes on the two failures

Both failed during the scorer's start-up: the second within about four
minutes of upload, while loading the model alone takes about 7.5 minutes.
The scorer's script is not public and our runs never fail at that stage, so
the cause is inferred, not observed. Compared with a submission that scored
0.10, both of ours left `max_tool_calls` out of `eval_config.yaml`; v5
removes that and every other configuration difference from it.

## Decision rule, fixed before submission 3

- If submission 3 scores: keep it as the baseline and move to agent quality.
  Bisecting the three configuration differences is optional.
- If submission 3 fails: the next submission is the control
  (`experiments/control`, sha256 `7798e491`), not another hypothesis. It is
  identical to submission 3 except that its prompt makes the agent submit an
  empty patch immediately, so it scores about 0.00.
  - Control scores: start-up works with this configuration, so the prompt is
    implicated. Bisect the prompt.
  - Control fails: the configuration, account or upload path is at fault. Ask
    the hosts before spending another submission.

## What submission 3 showed

It passed the scorer's start-up, where submissions 1 and 2 failed, and was
still running after five hours. One of the three configuration changes it
made therefore removed the start-up failure: all four `eval_config.yaml`
keys, a `thinking_budget` in `sampling.yaml`, and no `description` on the
root agent. Which of the three it was is not known. All later submissions
keep all three, and the build script enforces the first.

## Submission 3 score in context

Public leaderboard on 2 October, 1,411 teams: 0.24 (1 team), 0.15 to 0.17
(18), 0.12 to 0.13 (254), 0.10 (269), 0.08 (267), 0.06 or less (602). Scores
move in steps of one task, about 0.017. Locally the same agent resolved 4 of
10 and 3 of 4 dev tasks, but those tasks were chosen for small reference
patches, so they overstate the hidden-set rate; later local comparisons use a
random sample of the dev split instead.

## v6 candidate (checked 3 October)

GPU run of the exact v5 and v6 files on five dev tasks drawn at random
(seeded hash), all with reference fixes confirmed in the local Docker
sandbox first, patches re-scored locally:

| Task | v5 | v6 |
|---|---|---|
| fastapi_14786 | resolved | resolved |
| fastapi_14297 | resolved | resolved |
| fastapi_14616 | 60-turn limit, no patch (50 file reads) | 60-turn limit, no patch (one command 19 times) |
| rich_3905 | resolved | resolved |
| rich_3043 | time limit, no patch (one edit attempted 19 times) | resolved in 139 s |

v6 resolved 4 of 5, v5 3 of 5, on the same tasks; v6 used its ranker on all
five; no exceptions; every task inside the cap. Both versions reached the
60-turn limit on fastapi_14616 well before the time limit, so the turn limit
binds; raising it is the next single change. Five tasks is a small sample.
