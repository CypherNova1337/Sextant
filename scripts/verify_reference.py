"""Check public tasks with the official verifier, without a model.

For each task id, runs the competition's own verification phase twice in the
Docker sandbox (image swebench-sandbox:latest):
  - with no patch: the task's tests are expected to fail (fail-to-pass);
  - with the reference patch: they are expected to pass.
A task that behaves otherwise has a local-environment problem, which must be
understood before any agent result on it is trusted.

Usage:
  python scripts/verify_reference.py [--data DIR] [--out FILE] TASK_ID [TASK_ID ...]
Writes one JSON line per task to --out (default runs/reference/verify.jsonl).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from adk_eval_core.tracing.trace import SessionTrace
from adk_submission import ModelRegistry
from swegemma.config import EvalConfig
from swegemma.evaluate import Evaluator
from swegemma.models import load_tasks

ROOT = Path(__file__).resolve().parent.parent


def with_newline(patch: str) -> str:
    # Patches in tasks.jsonl lack their final newline.
    return patch if patch.endswith("\n") else patch + "\n"


def make_evaluator(data: Path, results: Path, patch: str | None) -> Evaluator:
    config = EvalConfig(
        tasks_path=data / "tasks.jsonl",
        snapshots_dir=data / "snapshots",
        results_dir=results,
        submission_dir=ROOT / "agent",
        models=ModelRegistry(),
        sandbox="docker",
        wheels_dir=data / "wheels",
        skip_agent_patch=patch is None,
        verbose=False,
    )
    evaluator = Evaluator(config)
    if patch is not None:
        async def fixed_patch(*args, **kwargs):
            return patch, None, SessionTrace()
        evaluator._run_agent_sandbox = fixed_patch
    return evaluator


def run_once(data: Path, results: Path, task, patch: str | None) -> dict:
    evaluator = make_evaluator(data, results, patch)
    start = time.time()
    result = asyncio.run(evaluator.evaluate_task(task=task, task_index=1, total_tasks=1))
    return {
        "resolved": bool(result.resolved),
        "exit_code": result.test_exit_code,
        "error": result.error,
        "seconds": round(time.time() - start, 1),
        "tail": (result.test_output or "")[-600:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "reference" / "verify.jsonl")
    parser.add_argument("task_ids", nargs="+")
    args = parser.parse_args()

    tasks = {t.instance_id: t for t in load_tasks(args.data / "tasks.jsonl")}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for tid in args.task_ids:
        task = tasks[tid]
        results = args.out.parent / tid
        base = run_once(args.data, results / "base", task, None)
        gold = run_once(args.data, results / "gold", task, with_newline(task.patch))
        row = {
            "id": tid,
            "fails_without_fix": not base["resolved"],
            "passes_with_fix": gold["resolved"],
            "ok": (not base["resolved"]) and gold["resolved"],
            "base": base,
            "gold": gold,
        }
        with args.out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{tid}: ok={row['ok']} fails_without_fix={row['fails_without_fix']} "
              f"passes_with_fix={row['passes_with_fix']} "
              f"({base['seconds']}s + {gold['seconds']}s) {gold['error'] or ''}")


if __name__ == "__main__":
    main()
