"""Validate an agent directory with the official harness and package it.

Usage: python scripts/build_submission.py [AGENT_DIR] [OUTPUT_ZIP]

The archive holds files only (no directory entries), with agent.yaml at its
root. Validation uses the competition's own adk_submission and swegemma
packages, so a directory that passes here compiles the same way at scoring.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import yaml
from adk_submission import ModelRegistry, compile_submission, validate_directory
from google.adk.models.lite_llm import LiteLlm
from swegemma.config import (
    ALLOWED_SUBMISSION_EXTENSIONS,
    MAX_SUBMISSION_SIZE_BYTES,
    build_submission_limits,
)
from swegemma.models.discovery import validate_single_declared_model

MODEL = "gemma-4-31b-it-qat-w4a16-ct"
ROOT = Path(__file__).resolve().parent.parent


# Stand-ins carrying the real tool signatures. Compiling only checks names and
# schemas; nothing is called.
def run_command(command: str) -> str: ...
def read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str: ...
def write_file(filepath: str, content: str) -> str: ...
def edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str: ...
def submit_patch() -> str: ...
def get_status() -> str: ...
def get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str: ...
def search_similar_code(query: str, k: int = 10) -> str: ...
def get_code_subgraph(nodes: list[str]) -> str: ...


TOOLS = {
    f.__name__: f
    for f in (run_command, read_file, write_file, edit_file, submit_patch, get_status,
              get_code_neighbors, search_similar_code, get_code_subgraph)
}


def validate(agent_dir: Path) -> None:
    limits, constraints = build_submission_limits()
    validate_directory(agent_dir, limits)
    declared = validate_single_declared_model(agent_dir)
    if declared != MODEL:
        raise SystemExit(f"declared model {declared!r}, expected {MODEL!r}")
    models = ModelRegistry()
    models.register(MODEL, LiteLlm(model=f"openai/{MODEL}", api_base="http://127.0.0.1:9/v1", api_key="EMPTY"))
    agent = compile_submission(agent_dir, TOOLS, models, limits=limits, generation_constraints=constraints)
    print(f"compiled: root agent {agent.name!r}, model {declared}")


EVAL_KEYS = {"timeout_seconds", "max_tool_calls", "max_time_minutes", "max_turns"}


def check_structure(agent_dir: Path) -> None:
    """Match the structure of submissions known to score.

    Two submissions failed during the scorer's start-up while passing every
    check above; both left keys out of eval_config.yaml. Every scored
    submission seen either omits the file or sets all four budget keys.
    """
    cfg = agent_dir / "eval_config.yaml"
    if cfg.exists():
        section = (yaml.safe_load(cfg.read_text()) or {}).get("evaluation") or {}
        missing = EVAL_KEYS - set(section)
        if missing:
            raise SystemExit(f"eval_config.yaml lacks {sorted(missing)}")
        bad = [k for k in EVAL_KEYS if isinstance(section[k], bool) or not isinstance(section[k], (int, float))]
        if bad:
            raise SystemExit(f"eval_config.yaml values must be numbers: {bad}")


def package(agent_dir: Path, out: Path) -> None:
    files = sorted(p for p in agent_dir.rglob("*") if p.is_file())
    bad = [p for p in files if p.suffix.lower() not in ALLOWED_SUBMISSION_EXTENSIONS]
    if bad:
        raise SystemExit(f"disallowed files: {bad}")
    total = sum(p.stat().st_size for p in files)
    if total >= MAX_SUBMISSION_SIZE_BYTES:
        raise SystemExit(f"unpacked size {total} exceeds the limit")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(agent_dir).as_posix())
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
    assert "agent.yaml" in names and not any(n.endswith("/") for n in names)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {out} ({out.stat().st_size:,} bytes, sha256 {digest[:12]})")
    for name in names:
        print(f"  {name}")


def main() -> None:
    agent_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "agent"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "submission.zip"
    validate(agent_dir)
    check_structure(agent_dir)
    package(agent_dir, out)


if __name__ == "__main__":
    main()
