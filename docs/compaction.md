# History compaction in the scorer, and v17

## What the scorer does

The scorer runs every task with ADK token-threshold compaction:
`EventsCompactionConfig(compaction_interval=5, overlap_size=2,
token_threshold=14336, event_retention_size=5)`. Before each model call, ADK's
`CompactionRequestProcessor` reads the prompt size of the latest model call.
Once it reaches 14,336 tokens, every event except the last 5 is replaced by
one summary written by the same model (`LlmEventSummarizer`), and the summary
is inserted as a model message.

What the summarizer sees and what it drops:

- It sees text parts only: the task message and the agent's reasoning
  (thought parts carry text, so they are included).
- It drops every function call and function response: the files read, the
  search results, the edits made and their results.
- The task message itself is one of the compacted events. After the first
  compaction the agent no longer has the problem statement, only the
  summary's version of it. A mock run (below) confirms this.

## How often it happens (v13 A/B, 27 dev tasks, Kaggle 4xL4 traces)

| | v13 | Budget-Fit reference | v14 |
|---|---|---|---|
| tasks with at least one compaction | 22 / 27 | 20 / 27 | 25 / 27 |
| compactions | 29 | 28 | 34 |
| median call of the first compaction | 15 | 16 | 14 |
| reads of a file already read before the compaction | 70 of 76 | 58 of 68 | 57 |
| resolved, tasks with a compaction | 12 / 22 | 8 / 20 | |
| resolved, tasks without | 4 / 5 | 7 / 7 | |

(The last two rows are confounded: easy tasks finish before the threshold.)

- The first prompt is about 5,400 tokens (v13): system prompt about 1,600,
  tool declarations and template about 2,000, task message 1,300 to 2,500 (it
  includes a three-level directory tree).
- Each call then adds about 630 tokens: 262 of the model's own output
  (reasoning is sent back on every later call) and 369 of tool output.
- `read_file` is 67% of the tool output. Whole-file reads and reads of more
  than 80 lines average 3,900 to 4,700 characters; reads of 40 lines or fewer
  average about 1,000.
- A failing `run_command` returns its output twice (`error_message` repeats
  stderr, and `details` holds stdout and stderr again). `2>&1 | tail -25`
  makes the exit code 0 and returns the output once.
- A compaction step takes 28 s (median) against 3.3 s for a normal step: about
  25 s of summarizing per compaction, roughly 25 to 30 s per task on average,
  or about an hour over 120 hidden tasks.
- `read_file` returns the lines without line numbers; the agent sometimes
  spends several calls guessing line numbers (rich_3063).

## The session state the harness provides

`swegemma/harness/agent_runner.py` creates each task's session with
`state={"problem_description": task.problem_statement}` and adds `hints` when
the task has hint text. ADK renders `{name?}` placeholders in the instruction
from session state on every model call (`inject_session_state`; the `?` makes
a missing key render as empty). An instruction ending in
`{problem_description?}` therefore carries the exact problem statement on
every call, including every call after a compaction.

Checked with `scripts/check_instruction.py`: the submission compiled with
`compile_submission`, ADK's `Runner` with the scorer's compaction settings,
and a scripted model whose reported prompt size crosses the threshold four
times. For v17 every agent request had the problem statement in its system
instruction (exit 0 with `--expect-task`); for v13b none did. After the first
compaction the original task message was gone from the request contents for
both.

## v17

`experiments/v17` = v13b with five prompt changes:

1. **Task kept after compaction:** the prompt ends with `## The Task`
   `{problem_description?}` and `## Hints (may be empty)` `{hints?}`. Costs the
   problem statement's length once more per call (median 418 characters,
   90th percentile 1,891, largest 10,095 in the dev set; no dev task has
   hints). The cost grows with the statement: after a compaction the
   instruction still carries it, so a very long statement leaves little room
   below the threshold and compactions come more often. At the dev set's
   largest (about 2,500 tokens) the room after a compaction drops from about
   7,300 to 4,800 tokens; a statement of 6,000 tokens or more would bring a
   compaction every few calls, bounded by the 8-minute cap.
2. **Call counting:** the agent starts its reasoning for each step with the
   call number (`Call 7`), and the edit-by-12 and no-exploration-from-20 rules
   refer to those numbers. Reasoning stays in the context, and the last 5
   events survive a compaction, so the count does too. In v13, 12 of 27 tasks
   had no edit by call 12 (3 resolved) against 13 of 15 resolved for the rest.
3. **Broken `edit_file` calls:** on the first "mandatory input parameters"
   error the agent switches to a single-argument `run_command` that writes the
   old and new text with quoted heredocs and replaces it with one `python3 -c`
   line (v16's rule). Checked through the scorer's exact exec wrapping
   (`timeout -k 5s N /bin/bash -c <quoted>`) on a file with backslashes,
   quotes, f-string braces and a docstring: `matches 1`, file as expected,
   compiles; a second run prints `matches 0` and changes nothing.
4. **Smaller outputs:** find line numbers with `grep -n`, read about 60 lines
   around them, end test and script runs with `2>&1 | tail -25`, searches with
   `| head -30`.
5. **Summaries explained:** the prompt says older messages get summarized,
   the task stays, and the agent should continue rather than restart.

The three code-graph tools stay declared, as in every configuration we have
tested. Dropping them would save about 1,700 characters of declarations per
call, but the task message advertises them whenever graph data exists, and a
call to an undeclared tool raises in ADK; the harness then keeps no patch for
that task, not even a submitted one (forum 745028). With the tools declared
and the "do not use" line, our runs made 0 graph-tool calls in about 7,500.

Sampling and budgets are v13b's: temperature 0.2, thinking budget 4,096,
240 s command timeout, 28 calls, 8 minutes, 80 turns.

Package: `data/v17.zip`, built with `scripts/build_submission.py`. Not yet run
on a GPU.

## What to measure on the GPU run

`scripts/analyze_run.py` now reports compactions per run, the median call of
the first compaction and re-reads after a compaction, next to resolved
counts, first-edit calls, edit failures and mean seconds per task. v17 should
show fewer compactions, a later first compaction, fewer tasks without an edit
by call 12, and no more seconds per task than v13 (257 s mean).
