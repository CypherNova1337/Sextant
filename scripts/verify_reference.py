"""Score patches on public tasks with the official verifier, without a model.

Runs the competition's own verification phase in the Docker sandbox (image
swebench-sandbox:latest, built from docker/Dockerfile.local).

Two modes:
  reference (default): for each task id, verify with no patch (the tests are
      expected to fail) and with the reference patch (expected to pass). A task
      that behaves otherwise has a local-environment problem, and agent results
      on it cannot be trusted.
  --patches RUN_SUMMARY: verify the agent patches recorded by an evaluation
      notebook (run_summary.json), since that notebook's own verdicts come from
      a sandbox that sees the host's installed packages.

Local environment corrections, so that a public task behaves as a private
hidden-set repository would:
  - the repository's own package is removed from the wheel set, so its tests
    import the repository's code rather than a released wheel;
  - wheels in data/wheels_extra (typing_inspection, which fastapi's pydantic
    needs and the public wheel set lacks) are added.

Usage:
  python scripts/verify_reference.py [--data DIR] [--out FILE] TASK_ID [...]
  python scripts/verify_reference.py --patches run_summary.json [--out FILE]
Writes one JSON line per task to --out.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import time
from pathlib import Path

from adk_eval_core.tracing.trace import SessionTrace
from adk_submission import ModelRegistry
from swegemma.config import EvalConfig
from swegemma.evaluate import Evaluator
from swegemma.models import load_tasks

ROOT = Path(__file__).resolve().parent.parent
OWN_DISTRIBUTION = {
    "fastapi/fastapi": "fastapi",
    "Textualize/rich": "rich",
    "psf/requests": "requests",
    "encode/httpx": "httpx",
}


def with_newline(patch: str) -> str:
    # Patches in tasks.jsonl lack their final newline.
    return patch if patch.endswith("\n") else patch + "\n"


def wheels_for(data: Path, repo: str) -> Path:
    """A per-repository wheel directory without the repository's own package."""
    own = OWN_DISTRIBUTION.get(repo, repo.rsplit("/", 1)[-1]).lower()
    target = data / "wheels_by_repo" / own
    if target.exists():
        return target
    target.mkdir(parents=True)
    sources = list((data / "wheels").glob("*.whl")) + list((data / "wheels_extra").glob("*.whl"))
    for wheel in sources:
        name = re.split(r"-", wheel.name, maxsplit=1)[0].lower().replace("_", "-")
        if name != own:
            shutil.copy2(wheel, target / wheel.name)
    return target


def make_evaluator(data: Path, results: Path, repo: str, patch: str | None) -> Evaluator:
    config = EvalConfig(
        tasks_path=data / "tasks.jsonl",
        snapshots_dir=data / "snapshots",
        results_dir=results,
        submission_dir=ROOT / "agent",
        models=ModelRegistry(),
        sandbox="docker",
        wheels_dir=wheels_for(data, repo),
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
    evaluator = make_evaluator(data, results, task.repo, patch)
    start = time.time()
    result = asyncio.run(evaluator.evaluate_task(task=task, task_index=1, total_tasks=1))
    return {
        "resolved": bool(result.resolved),
        "exit_code": result.test_exit_code,
        "error": result.error,
        "seconds": round(time.time() - start, 1),
        "tail": (result.test_output or "")[-600:],
    }


def append(out: Path, row: dict) -> None:
    with out.open("a") as f:
        f.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--patches", type=Path, help="run_summary.json from an evaluation notebook")
    parser.add_argument("task_ids", nargs="*")
    args = parser.parse_args()

    tasks = {t.instance_id: t for t in load_tasks(args.data / "tasks.jsonl")}
    default = "agent/verify.jsonl" if args.patches else "reference/verify.jsonl"
    out = args.out or ROOT / "runs" / default
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.patches:
        rows = json.loads(args.patches.read_text())["rows"]
        for r in rows:
            task, patch = tasks[r["id"]], r.get("patch") or ""
            if not patch.strip():
                result = {"resolved": False, "error": "empty patch"}
            else:
                result = run_once(args.data, out.parent / r["id"], task, patch)
            append(out, {"id": r["id"], **result})
            print(f"{r['id']}: resolved={result['resolved']} {result.get('error') or ''}")
        return

    for tid in args.task_ids:
        task = tasks[tid]
        results = out.parent / tid
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
        append(out, row)
        print(f"{tid}: ok={row['ok']} fails_without_fix={row['fails_without_fix']} "
              f"passes_with_fix={row['passes_with_fix']} "
              f"({base['seconds']}s + {gold['seconds']}s) {gold['error'] or ''}")


if __name__ == "__main__":
    main()
