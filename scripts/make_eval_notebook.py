"""Generate a private Kaggle notebook that runs an agent on selected public tasks.

The notebook serves the competition model with vLLM, runs the official
swegemma Evaluator (agent phase and verification phase, subprocess sandbox)
on the given task ids, and writes per-task results, including each agent
patch, to /kaggle/working/run_summary.json. The in-notebook verdicts come from
the subprocess sandbox, which sees the host's installed packages; re-score the
patches locally with scripts/verify_reference.py --patches for a faithful result.

Usage:
  python scripts/make_eval_notebook.py OUT_DIR SLUG TASK_ID [...] [--agent DIR ...]
Several --agent directories are evaluated against one model server, task by
task, which saves the server start-up for every extra variant.
Then:
  kaggle kernels push -p OUT_DIR
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT / "agent"
HOST_IMAGE = "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"

SETUP = r'''
import glob, importlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

os.environ.update({
    "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    "TRANSFORMERS_NO_TF": "1",
    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
    "VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS": "1",
    "VLLM_ENGINE_READY_TIMEOUT_S": "1200",
    "VLLM_NO_USAGE_STATS": "1",
    "OTEL_SDK_DISABLED": "true",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
})
T0 = time.time()
print(subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout)

wheelhouse = Path(sorted(glob.glob("/kaggle/input/**/adk_submission-*.whl", recursive=True))[0]).parent
for pattern in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth", "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
    for pth in glob.glob(pattern):
        os.unlink(pth)
staged = Path("/tmp/wheelhouse"); staged.mkdir(exist_ok=True)
for w in wheelhouse.glob("*.whl"):
    if "cutlass" in w.name.lower():
        continue
    name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
    if not (staged / name).exists():
        os.symlink(w, staged / name)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall",
                *sorted(str(w) for w in staged.glob("*.whl"))], check=True)
importlib.invalidate_caches()
print(f"wheels installed in {time.time() - T0:.0f}s")
'''

AGENT = r'''
AGENTS = json.loads(__AGENT_JSON__)
TASK_IDS = json.loads(__TASK_JSON__)
AGENT_DIRS = {}
for name, files in AGENTS.items():
    d = Path("/kaggle/working/agents") / name
    shutil.rmtree(d, ignore_errors=True)
    for rel, text in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    AGENT_DIRS[name] = d
AGENT_DIR = next(iter(AGENT_DIRS.values()))
print(list(AGENT_DIRS), TASK_IDS)
'''

SERVE = r'''
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
from swegemma.models.discovery import validate_single_declared_model

litellm.drop_params = True
MODEL = "gemma-4-31b-it-qat-w4a16-ct"
model_path = Path(sorted(glob.glob(f"/kaggle/input/models/**/{MODEL}/*/config.json", recursive=True)
                         + glob.glob(f"/kaggle/input/**/{MODEL}/**/config.json", recursive=True))[0]).parent
declared = validate_single_declared_model(AGENT_DIR)
adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
gpus = torch.cuda.device_count()
server = VllmServer(VllmConfig(
    model=str(model_path), port=8000, host="127.0.0.1",
    tool_call_parser="gemma4", reasoning_parser="gemma4", max_model_len=32768,
    dtype="bfloat16", gpu_memory_utilization=0.80, enable_auto_tool_choice=True,
    enable_lora=True, max_loras=8, max_lora_rank=128,
    tensor_parallel_size=4 if gpus >= 4 else (2 if gpus >= 2 else 1),
    startup_timeout=60 * 20,
), adapter_manifest=adapters)
t = time.time(); server.start()
print(f"vLLM up in {time.time() - t:.0f}s on {gpus} GPUs; model {model_path}")
models = server.create_model_registry(aliases=[declared, MODEL], model_prefix="openai/", api_key="EMPTY")
'''

EVALUATE = r'''
import asyncio, concurrent.futures, yaml
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
from swegemma.models import load_tasks

def run_sync(fn, **kw):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(fn(**kw))).result()

data = Path(sorted(glob.glob("/kaggle/input/**/tasks.jsonl", recursive=True))[0]).parent
tasks = {t.instance_id: t for t in load_tasks(data / "tasks.jsonl")}
limits, constraints = build_submission_limits()

def make_evaluator(name, agent_dir):
    cfg_path = agent_dir / "eval_config.yaml"
    ev = (yaml.safe_load(cfg_path.read_text()) or {}).get("evaluation", {}) if cfg_path.exists() else {}
    return Evaluator(EvalConfig(
    tasks_path=data / "tasks.jsonl", snapshots_dir=data / "snapshots",
    results_dir=Path("/kaggle/working/results") / name, submission_dir=agent_dir, models=models,
    sandbox="subprocess",
    timeout_seconds=int(ev.get("timeout_seconds", 300)),
    max_time_minutes=float(ev.get("max_time_minutes", 60.0)),
    max_tool_calls=int(ev.get("max_tool_calls", 100)),
    max_turns=int(ev["max_turns"]) if "max_turns" in ev else None,
    limits=limits, generation_constraints=constraints, adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=5, overlap_size=2, token_threshold=14336, event_retention_size=5),
    graph_dir=str(data / "graphs"), embeddings_dir=str(data / "embeddings"),
    wheels_dir=data / "wheels", verbose=False,
    ))

evaluators = {name: make_evaluator(name, d) for name, d in AGENT_DIRS.items()}
rows = []
# Task-major order, so a run cut short still compares the variants on the same tasks.
for i, tid in enumerate(TASK_IDS, 1):
  for name, evaluator in evaluators.items():
    t = time.time()
    try:
        r = run_sync(evaluator.evaluate_task, task=tasks[tid], task_index=i, total_tasks=len(TASK_IDS))
        row = {"agent": name, "id": tid, "resolved": bool(r.resolved), "test_exit_code": r.test_exit_code,
               "patch_chars": len(r.agent_patch or ""), "tool_calls": r.tool_calls,
               "agent_seconds": r.duration_seconds, "error": getattr(r, "error", None),
               "patch": r.agent_patch or ""}
    except Exception as e:
        row = {"agent": name, "id": tid, "resolved": False, "error": f"{type(e).__name__}: {e}"}
    row["wall_seconds"] = round(time.time() - t, 1)
    rows.append(row)
    print(json.dumps(row, default=str))
    Path("/kaggle/working/run_summary.json").write_text(json.dumps(
        {"rows": rows, "elapsed_seconds": round(time.time() - T0, 1)}, indent=1, default=str))
print(f"resolved {sum(r['resolved'] for r in rows)}/{len(rows)}; total {time.time() - T0:.0f}s")
server.stop()
'''


def cell(src: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(keepends=True)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("slug")
    parser.add_argument("task_ids", nargs="+")
    parser.add_argument("--agent", action="append", type=Path,
                        help="agent directory; repeat to compare variants (default: agent/)")
    args = parser.parse_args()
    out, slug, task_ids = args.out, args.slug, args.task_ids
    agent_dirs = [d.resolve() for d in (args.agent or [AGENT_DIR])]
    held_out = set((ROOT / "splits" / "held_out.txt").read_text().split())
    if held_out & set(task_ids):
        raise SystemExit(f"held-out tasks requested: {sorted(held_out & set(task_ids))}")
    agents = {d.name: {p.relative_to(d).as_posix(): p.read_text()
                       for p in sorted(d.rglob("*")) if p.is_file()} for d in agent_dirs}
    if len(agents) != len(agent_dirs):
        raise SystemExit("agent directories need distinct names")
    agent_src = (AGENT.replace("__AGENT_JSON__", repr(json.dumps(agents)))
                 .replace("__TASK_JSON__", repr(json.dumps(task_ids))))
    nb = {"cells": [cell(SETUP), cell(agent_src), cell(SERVE), cell(EVALUATE)],
          "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    out.mkdir(parents=True, exist_ok=True)
    (out / "notebook.ipynb").write_text(json.dumps(nb, indent=1))
    user = "cyphernova1337"
    (out / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{user}/{slug}", "title": slug, "code_file": "notebook.ipynb",
        "language": "python", "kernel_type": "notebook", "is_private": True,
        "enable_gpu": True, "enable_tpu": False, "enable_internet": False,
        "machine_shape": "NvidiaL4",
        # The hosts' getting-started notebook runs on this image. Kaggle's default
        # image moved to Python 3.13, where the harness's cp312 wheels do not install.
        "docker_image": HOST_IMAGE,
        "docker_image_pinning_type": "original",
        "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
        "competition_sources": ["gemma-4-developer-agent"],
        "kernel_sources": [],
        "model_sources": ["google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"],
    }, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
