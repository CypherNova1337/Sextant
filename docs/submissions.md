# Leaderboard submissions

One entry per upload: what was submitted, what was checked before it, and the
outcome. Local results are on public dev tasks, re-scored in the Docker
sandbox with `scripts/verify_reference.py`.

| # | Date (UTC) | Agent | sha256 (zip) | Checked before upload | Outcome |
|---|---|---|---|---|---|
| 1 | 2026-09-30 21:23 | v1: single agent, edit_file, 4 min | `c7dc85c6` | validator and compiler; 3-task GPU run (0 of 3 resolved, every edit_file call malformed) | Notebook Threw Exception |
| 2 | 2026-10-01 01:03 | v4-rules: run_command edits with helper, anti-loop rules, T 0.6 | `9ec6aa1b` | validator and compiler; 10-task GPU run, 4 of 10 resolved, no exceptions | Notebook Threw Exception, within about 4 minutes |
| 3 | pending | v5: v4-rules agent, configs matched to a scored submission (all four eval_config keys, 4.5 min, thinking_budget present, no root description) | `ed4706a5` | validator, compiler and structure check; GPU run of these exact files on 4 dev tasks: no exceptions, all within the cap, 3 of 4 resolved (requests_6644, rich_3006, rich_3454; fastapi_14430 empty patch) | |

## Notes on the two failures

Both failed during the scorer's start-up: the second within about four
minutes of upload, while loading the model alone takes about 7.5 minutes.
The scorer's script is not public and our runs never fail at that stage, so
the cause is inferred, not observed. Compared with a submission that scored
0.10, both of ours left `max_tool_calls` out of `eval_config.yaml`; v5
removes that and every other configuration difference from it.
