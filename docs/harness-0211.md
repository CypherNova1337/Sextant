# The 9 October harness (swegemma 0.2.11, adk_submission 0.2.13)

The competition wheelhouse moved to version 30 on 9 October (14:43 UTC);
adk_submission 0.2.13 is dated 8 October. Past wheelhouse updates changed how
submissions were scored (forum 744807), and a team that compiled the same
bundle with both versions saw the new behaviour in what reaches vLLM (747914),
so we treat it as the scorer's harness from now on. Our first v17 test
notebook failed on it because `swegemma.models.discovery` no longer exists.

Local tools now use it: `data/wheelhouse` holds both versions, the venv has
the new ones, and `scripts/build_submission.py` and
`scripts/make_eval_notebook.py` read the declared model with
`adk_submission.discovery.discover_declared_models`.

## What changed for an agent

- **Tool errors reach the model.** A `ToolErrorPlugin` turns a call to an
  undeclared tool, and any exception raised inside a tool, into an error
  result the model can read. Before, the task ended and its patch was lost
  (745028). An exception in the agent loop now still keeps the submitted or
  working-tree patch.
- **The task message lists declared tools only.** The "Code Intelligence
  Tools" section appears only for declared graph tools, and the `read_file`
  limits only when `read_file` is declared.
- **Smaller directory tree in the task message.** Breadth-first, at most 200
  lines, without `docs`, `docs_src`, `tests`, `test_data`, `examples`,
  `benchmarks`, `assets`, `imgs`, `questions`, `site` and hidden paths. On
  fastapi the old tree was about 5,500 characters, mostly `docs_src`.
- **Test and runner config files are stripped from patches**: from the
  submitted patch, from the working-tree fallback and again before
  verification. Protected: `conftest.py`, `pytest.ini`, `pyproject.toml`,
  `tox.ini`, `setup.cfg`, `sitecustomize.py`, `*.pth`, `test_*.py`,
  `*_test.py`, any `.py` under a `tests`/`test`/`testing` directory, and the
  task's own test files. A change to `pyproject.toml`, such as a new console
  script, can no longer reach the hidden tests.
- **The test-file reset before the hidden tests now works.** It checks out
  only tracked files, so a missing path no longer makes the whole reset fail.
- **`include_thoughts` no longer switches reasoning.** Reasoning is on when
  `thinking_budget` is above 0 (or a level is set); the runner's default
  budget of 4,096 applies when none is given. `include_thoughts: false` now
  keeps reasoning on and drops the thought parts from the session, so earlier
  reasoning is not sent back to the model. `thinking_budget: 0` turns
  reasoning off.

Unchanged: `swegemma/config.py`, `swegemma/evaluate.py`, the tools' output
formats, and ADK (1.36.1), including the compaction code.

## What it means for us

- v17 no longer declares the three code-graph tools: a stray call is now
  harmless, and dropping them removes about 1,700 characters of declarations
  and the 600-character "Code Intelligence Tools" section from every call.
  Checked locally: v17's task message has no such section, and a scripted
  call to `search_similar_code` came back to the model as "Tool not found".
- All our versions keep `include_thoughts: true` with a 4,096 budget, so
  their reasoning is unchanged. A version with `include_thoughts: false` and
  a budget would keep reasoning but grow its context much more slowly (our
  reasoning is 42% of context growth); whether losing earlier reasoning costs
  more than fewer compactions save is untested.
- Earlier local results came from the old harness. Re-scored with the new
  verification (`runs/h0211/`): v13 16 of 27 and the reference 15, unchanged;
  v14 13 instead of 12, because its rich_3006 patch had edited
  tests/test_repr.py and that edit is now stripped. v17's GPU test runs the
  new harness end to end, so the agent side (shorter directory tree, tool
  errors) differs from those runs too.
