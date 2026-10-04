# Scoring environment: what differs from our local runs

Checked 4 October, after three different agents (v5, v6, v9) all scored 0.08.

## Tested, and not the cause

- **Slim image.** The scoring image is built on python:3.13-slim; our local
  image used the full python:3.13. A slim stand-in (docker/Dockerfile.slim)
  re-scores v9's gate patches the same way (4 of 5).
- **Helpers.** In the slim image, with pytest and unittest discovery disabled
  as the harness can do, the skill install, sx_find, sx_edit and the patch
  all work.

## Differences that remain

- **GPU gate sandbox.** Our Kaggle GPU runs used the plain-process sandbox,
  where the agent sees the host's packages and pytest always works. The scorer
  uses Docker (the code mentions gVisor), 2 CPUs, 4 GB, no network. Whether
  pytest is disabled there depends on `enable_sandbox_testing`, which defaults
  to on; the built-in prompt changes its instruction 3 when it is off.
- **Scoring image.** gcr.io/kaggle-playground-170215/swebench-sandbox:v1
  ("SDG" image) is private; it adds protobuf-compiler and pigz, and private
  wheels we cannot see.

## Clues about the hidden tasks (from the harness code)

- The built-in first prompt tells the agent to identify "all requested
  script paths, CLI subcommands, or Python modules", and says failing
  imports mean the problem is in /workspace. That reads like tasks that ask
  for new files, scripts or subcommands, not only bug fixes.
- `difficulty.py` counts mocks including `fake_gfile`, and the image ships
  protoc: Google-style code is likely among the private repos.
- Splits are keyed by `repo_hash`, and snapshots are a base plus incremental
  patches, so several hidden tasks probably share one repository.
- Optional `hints_text` is placed in session state as `hints`; public tasks
  never have it, so our prompts ignore it.
- Protected paths at scoring: any `.py` under a `tests`, `test` or `testing`
  directory, `test_*.py`, `*_test.py`, `.pth` files and the usual config files.
