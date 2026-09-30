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

## Local verification

`scripts/verify_reference.py` runs the official verification phase on public
tasks with no patch (expected to fail) and with the reference patch (expected
to pass). It uses the Docker sandbox; the plain-process sandbox is not
faithful, because its environment inherits the host's installed packages.

The image is built offline from `docker/Dockerfile.local`, a stand-in for the
competition's `Dockerfile.public`. The build context needs the competition's
`docker/` shims and `wheels/`, plus a `tools/` directory holding wheels for
the image's Python tools (`pip download -d tools --python-version 3.13
--only-binary=:all: pytest pytest-timeout==2.1.0 typer pdm-backend setuptools
wheel poetry-core hatchling flit-core editables`).

Known local limits: the harness unpacks every small wheel from `wheels/` into
the sandbox, so public `requests` tasks import the wheel's `requests` rather
than the repository's; and `wheels/` lacks `typing_inspection`, so fastapi
tests fail to collect. Neither affects the hidden set.
