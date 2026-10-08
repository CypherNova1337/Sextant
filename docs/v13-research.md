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
