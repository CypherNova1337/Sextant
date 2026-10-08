# v13: research behind it (8 October)

## The leaderboard (public, 8 October, 1,989 teams)

Scores move in steps of one task out of about 58 public tasks and are shown
truncated: 0.24 = 14 tasks (1 team), 0.18 = 11 (4), 0.17 = 10 (32),
0.15 = 9 (85), 0.13 = 8 (244), 0.12 = 7 (380), 0.08 = 5 (315, us, rank 1301).
Identical submissions move by about two tasks between runs.

## What the best public agents do

"Gemma 4 Agent: Budget-Fit Single Agent" by Wilmer E. Henao (verracodeguacas,
Apache 2.0) scored 0.18; "Calibrated Single Agent" (lavinwins, 0.17) uses the
same settings, so the 36 teams at 0.17 to 0.18 largely share one design:

- one agent, all nine tools declared, built-in edit_file and write_file
- reasoning on: include_thoughts true, thinking_budget 4096; temperature 0.2,
  top_p 0.95, max_output_tokens 8192
- eval_config: timeout_seconds 240, max_tool_calls 28, max_time_minutes 8,
  max_turns 80; a scored run finished inside 12 hours
- prompt: edit a source file by the 12th call; no new exploration after the
  20th; targeted tests only; never touch tests

Its author's measurements (129 local runs): only about half of the fixes the
model eventually finds are in the file after 4 minutes; runs with no edit by
call 12 fail 87% of the time. experiments/budgetfit-ref holds that bundle
unchanged, as a control.

The 0.13 "planner then coder" bundle (hsiaosuan) used reasoning off, low
temperature, edit_file, a 5-minute cap and a 60-second command timeout.

## What the scorer's code shows

- `timeout_seconds` is the default timeout for every scorer command: setup,
  the agent's commands, and the hidden-test run, which runs whole test files.
  A short value can fail a correct patch when the test files are slow.
- The reset of test and config files before the hidden tests is a no-op
  (checkout aborts on missing paths), so edits to existing test or config
  files survive; a test_patch that touches an edited test file then fails to
  apply.
- Typing out our helpers cost about 42 s and 1,300 output tokens at the start
  of every v12 task (17% of a 4-minute task).

## Why v11 and v12 have no score

Kaggle reports "A system error. Please try resubmitting" for both (refs
56862128 and 56892091), the platform's generic message. Many teams reported
the same on 6 and 7 October after runs of about 15 hours, including bundles
with 4- to 5-minute caps (forum threads 746480, 743683; another team's
notebook records a system error on 7 October too). With per-task scorer
overhead of about 0.5 minutes, v12's worst case is about 9 hours.

## v13

experiments/v13 is the Budget-Fit bundle with one added prompt section built
from our traces: no git stash/checkout/reset/clean/commit; no edits to
packaging or test config; exact names and registration for new features;
several identifiers per git grep; a fallback when edit_file fails.

## Controlled ablations on all 129 public tasks (forum thread 746250)

One team ran single-change experiments on all 129 public tasks (faster GPUs
than Kaggle's; 50 tool calls, 80 turns unless stated):

| Change | Resolved / 129 |
|---|---|
| reference: temperature 0.2, thinking 4096, thoughts included | 48 |
| temperature 0.0 / 0.4 / 1.0 | 47 / 51 / 51 |
| thinking budget 2048 / 6144 | 50 / 48 |
| thinking disabled | 23 |
| thought summaries disabled | 35 |
| active time cap 6 / 10 / 15 / 20 / 60 min | 37 / 46 / 54 / 49 / 51 |
| 25 tool calls instead of 50 (15-min cap) | 36 instead of 50 |
| graph tools added | 50 instead of 55 |
| analyzer sub-agent added | 51 instead of 50 |
| the same configuration run again | 48 instead of 55 |

Reasoning off roughly halves the resolved count: every Sextant submission that
scored (v5, v6, v9) ran with reasoning off. A 2048-token budget matches 4096
while making each call cheaper. Time per task is the main lever, and the
12-hour total is what limits it. Repeat runs differ by about 7 tasks in 129,
so small differences need large samples. Their Kaggle 4xL4 calibration: 8.68 s
per model call with thinking on; about 5.5 minutes per task fits 120 tasks in
12 hours.

## v14 (staged, not yet run)

v13 plus: thinking_budget 2048, temperature 0.4, a ranked-search command
(files ordered by how many task identifiers they mention), and `timeout 60`
in front of the agent's own test and script runs, which keeps them short
without lowering timeout_seconds (that value also limits the hidden-test run).
