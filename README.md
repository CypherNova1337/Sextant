# Sextant

An autonomous coding agent built on Gemma 4, post-trained to read a bug report,
navigate an unfamiliar Python repository, and emit a unified diff that makes the
failing tests pass. Entry for the Gemma 4 Developer Agent Competition on Kaggle.

## Setup after cloning

```sh
git config user.name  "CypherNova1337"
git config user.email "131998711+CypherNova1337@users.noreply.github.com"
git config core.hooksPath .githooks
```

The hooks refuse commits and pushes with the wrong author identity or with
attribution in messages or changes. To sweep every tracked file by hand:

```sh
python3 .githooks/attribution.py tree
```

Competition data goes in `data/` (ignored by git).

## Layout

- `agent/` — the submission source: `agent.yaml`, prompts, sampling and
  per-task budgets. Packaged into `submission.zip` by the build script.
- `splits/` — the fixed dev / held-out split of the 129 public tasks. Held-out
  tasks are never used for iteration.
- `scripts/build_submission.py` — validates `agent/` with the competition's
  own validator and compiler, then writes a files-only `submission.zip`.
- `scripts/make_split.py` — regenerates `splits/` deterministically.
- `scripts/make_eval_notebook.py` — generates a private Kaggle notebook that
  serves the competition model and runs the official evaluator on dev tasks.

The official harness (`swegemma`, `adk-submission`, `adk-eval-core`) is in
the `metric/gemma-4-developer-agent-wheelhouse` Kaggle dataset and needs
Python 3.12 or later:

```sh
python3.13 -m venv .venv
.venv/bin/pip install <wheelhouse>/{swegemma,adk_submission,adk_eval_core,google_adk,google_genai}-*.whl \
    litellm networkx pandas pyyaml docker cachetools python-dotenv rich numpy safetensors pytest
.venv/bin/python scripts/build_submission.py
```
