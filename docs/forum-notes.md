# Competition forum: what bears on Sextant (read 6 October)

## Thinking has been off in every submission we made

adk_submission maps `include_thoughts: false` to `enable_thinking: false`
(resolvers/generation.py, apply_thinking_config_to_model), so the model
generates no reasoning at all, whatever `thinking_budget` says (thread 745059).
Every Sextant submission since v5 set `include_thoughts: false`. That explains
why each turn produced only about 40 tokens.

With `include_thoughts: true` and a positive budget, the bridge sends
`thinking_token_budget`, which vLLM accepts only when the server runs with
`--reasoning-config`. The scorer's server has it (thread 744807), and our
notebook's VllmServer adds it automatically for the gemma4 reasoning parser.
Thoughts are now kept between tool calls (fix in the current wheelhouse, thread
744354).

Our own earlier test (v4-think: thinking on, budget 1024, against v4-rules,
thinking off, 10 tasks): 4 against 3 resolved, about half the tool calls
(19 against 36 per task) and almost no repeated commands (1% against 25%).

## Other host statements and community findings

- Hidden tasks are run sequentially. The scorer reads only the four
  eval_config keys. Passing 12 hours currently errors the whole submission;
  a fix scoring unfinished tasks as 0 was planned but is unconfirmed (743063).
- The 12 hours cover all ~120 hidden tasks, public and private halves together.
- The hidden set comes from private repositories, not the four public ones
  (744951).
- Infrastructure failures (GPU outages, "system error", queue problems) have
  ended many submissions with no score; the hosts reran some (743683, 744807).
- Loops of identical commands are widespread (745774: one command 69 times);
  others report that prompt rules don't stop them and that the closed registries
  rule out callbacks.
- Local scores don't predict the leaderboard for other teams either: local
  0.18 to 0.32 against leaderboard 0.03 to 0.12 (744319).
- Calling an undeclared tool ends the task and discards the patch (745028);
  run_skill_script with a list argument crashes the task the same way.
- Edits to existing test files make test_patch fail to apply, so the task fails
  even with a correct fix (744825).
