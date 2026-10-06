# Leaderboard submissions

One entry per upload: what was submitted, what was checked before it, and the
outcome. Local results are on public dev tasks, re-scored in the Docker
sandbox with `scripts/verify_reference.py`.

| # | Date (UTC) | Agent | sha256 (zip) | Checked before upload | Outcome |
|---|---|---|---|---|---|
| 1 | 2026-09-30 21:23 | v1: single agent, edit_file, 4 min | `c7dc85c6` | validator and compiler; 3-task GPU run (0 of 3 resolved, every edit_file call malformed) | Notebook Threw Exception |
| 2 | 2026-10-01 01:03 | v4-rules: run_command edits with helper, anti-loop rules, T 0.6 | `9ec6aa1b` | validator and compiler; 10-task GPU run, 4 of 10 resolved, no exceptions | Notebook Threw Exception, within about 4 minutes |
| 3 | 2026-10-02 | v5: v4-rules agent, configs matched to a scored submission (all four eval_config keys, 4.5 min, thinking_budget present, no root description) | `ed4706a5` | validator, compiler and structure check; GPU run of these exact files on 4 dev tasks: no exceptions, all within the cap, 3 of 4 resolved (requests_6644, rich_3006, rich_3454; fastapi_14430 empty patch) | Public score 0.08 (about 5 of about 60 tasks) |
| 4 | 2026-10-03 | v6: v5 plus the sx_find ranker, reproduce at most once, no git stash/checkout/reset | `f42e1b5c` | validator, compiler and structure check; GPU run of these exact files on 5 random dev tasks: 4 of 5 resolved, no exceptions | Public score 0.08 |
| 5 | 2026-10-04 00:00 | v9: investigator sub-agent, edit/search helpers shipped as a skill, 4.5 min | `04b4d0b6` | validator, compiler and structure check; GPU run of these exact files on the same 5 tasks: 4 of 5 resolved, no exceptions | Public score 0.08 |
| 6 | 2026-10-05 21:27 | v11: v10 method (features, hints, python3 -c checks), plain helper install, no skill, 4.5 min | `a6814a0c` | validator, compiler and structure check; GPU run of these exact files on 5 gate + 5 feature tasks: 7 of 10 (v9 also 7 of 10), no exceptions | Error, no score (cause not reported) |
| 7 | 2026-10-06 22:27 | v12: v11 + reasoning on (include_thoughts true, budget 1024), 4.0 min per task | `bcdb4933` | validator, compiler and structure check; GPU run of these exact files on 27 dev + 10 feature tasks: 19 of 37 (v11 also 19), no turn-cap runs, mean 209 s per task | pending |

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

## v7, v8 and v9 candidates (checked 3 October)

v6 scored 0.08 on the public leaderboard, the same as v5, although it
resolved one more of the five gate tasks. A five-task gate can't separate
agents that differ by one task in twenty, so a gate result now shows only
that a candidate runs cleanly. It doesn't show that the candidate will score
higher.

Same five tasks, patches re-scored locally in Docker:

| Task | v7 | v8 | v9 |
|---|---|---|---|
| fastapi_14786 | resolved | resolved | resolved (47 s) |
| fastapi_14297 | not resolved | resolved | resolved (50 s) |
| fastapi_14616 | not run | crash: context window exceeded | 58 calls, no patch |
| rich_3905 | not run | resolved | resolved |
| rich_3043 | not run | resolved | resolved |

- v7 (100 turns, 5.5 minutes): more budget bought more repetition. Dropped.
- v8 (v6 plus a read-only investigator sub-agent): the crash came from the
  investigator. Its read_file calls arrived with malformed keys
  (`"start_line\""`), so no line range applied and each call returned the
  full 150 lines. Its context grew from 2,102 to 27,635 tokens. Compaction
  doesn't run inside an agent tool, so the window overflowed and the task's
  patch was lost. An exception loses that task only, not the run.
- v9 (v8 with the helpers shipped as a skill, prompt 5.7 KB instead of
  8.5 KB): no errors, and faster on the easy tasks. The overflow above can
  still happen. Skills haven't been tested on the real scorer.
  data/v9.zip, sha256 04b4d0b68266.

## Feature-task check of v9 and v10 (4 October)

Ten feature tasks (feature_tasks/: new scripts, modules, options, methods),
reference fixes confirmed in the slim sandbox. GPU run of both agents,
patches re-scored locally:

- v9: 8 of 10 (empty patches on requests_status_props, a time-out, and
  rich_filesize_parse, after 57 calls).
- v10: 8 of 10 (cidict_union lacked the reflected `__ror__`; filesize_parse
  accepted a negative size).

The agent handles explicit feature tasks on these repositories as well as it
handles their bug fixes. Feature tasks alone don't explain the 0.08.

What does: submission 3 took 8 to 9 hours on about 120 tasks with a
4.5-minute cap, which means an average of at least 4 minutes per task with
setup and verification included. So nearly every hidden task ran the agent to
or close to the cap. Locally the same agent finishes most tasks in 1 to 3
minutes. Either the hidden tasks are much harder for the model (unfamiliar
private code it has never seen, unlike rich, requests and fastapi, which it
knows from training), or the scoring sandbox is slower per command. Both cut
the number of useful calls per task.

## Why v9 and v10 waste turns (traces, 5 October)

Classifying every tool call in the saved GPU traces:

- In v9 and v10 the model repeatedly typed the skill installer as a shell
  command (`run_skill_script skill_name=...` inside run_command), which
  always fails: 94 of v10's 265 calls on the feature tasks, 125 of v9's 290,
  and 54 of v9's 184 on the gate tasks. Submission 5 (v9) carried this.
- read_file arguments arrive mangled (line numbers glued into the path), and
  the model then repeats the identical failing call: 21 times in a row on
  fastapi_14616.
- v6, which installs the helpers with a single plain run_command, failed 2 to
  8% of its calls.

With the 60-turn cap binding (each model turn takes 1 to 2 seconds), those
failures cost tasks directly. v11 is v10's method with v6's install command,
no skill, and file reading through `sed -n` instead of read_file.
data/v11.zip, sha256 a6814a0c40a8.

## v11 check (5 October)

GPU run of the exact v11 files on the five gate tasks and five feature tasks,
patches re-scored in the slim sandbox: 7 of 10. On the same ten tasks v9
also resolved 7. v11 newly solved requests_status_props and lost rich_3043
(60-turn cap, no patch). No crashes. data/v11.zip, sha256 a6814a0c40a8.

## v6 vs v11 on 37 tasks (6 October)

All 27 dev tasks with confirmed reference fixes plus the 10 feature tasks,
one GPU run of both agents, patches re-scored in the slim sandbox:

| Set | v6 (scored 0.08) | v11 |
|---|---|---|
| dev, 27 bug fixes | 8 (30%) | 11 (41%) |
| feature, 10 | 9 | 8 |
| total | 17 | 19 |

v11 alone: fastapi_14372, fastapi_14458, requests_7315, rich_3006. v6 alone:
ft_requests_cidict_union, rich_3278. Both crash-free. About a third of all
runs ended at the 60-turn cap with no patch (v6 11, v11 12), mostly after
loops of one identical command (up to 34 in a row). On the broader dev set
both agents resolve far fewer tasks than on the five-task gate, which had
over-stated them.

## v12: reasoning on (6 October)

v11 with `include_thoughts: true`, `thinking_budget: 1024` and a 4.0-minute
cap. Same 37 tasks, patches re-scored in the slim sandbox:

| Set | v11 | v12 |
|---|---|---|
| dev, 27 | 11 | 10 |
| feature, 10 | 8 | 9 |
| total | 19 | 19 |

v12 alone: ft_requests_cidict_union, rich_3043. v11 alone: fastapi_14301,
requests_7315 (v12 edited tests/test_adapters.py, so the hidden test patch
failed to apply). The behaviour changed far more than the score: 19.6 tool
calls per task against about 37, no run at the 60-turn cap (v11: 12), but 18
of 37 runs reached the 4-minute cap. Mean agent time 209 s; with about 90 s of
scorer overhead per task (from submission 3's 8 to 9 hours), 120 tasks take
about 10 hours, inside the 12-hour limit.
data/v12.zip, sha256 bcdb4933a9a3.
