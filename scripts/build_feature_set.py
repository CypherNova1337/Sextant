"""Assemble the feature-style tasks in feature_tasks/ into a data directory
that the harness and scripts/verify_reference.py can load.

Each feature_tasks/<id>/ holds meta.json (repo, the public task whose snapshot
it builds on, problem statement, hints), gold.patch (reference solution) and
test.patch (hidden tests). The public tasks are all bug fixes, while the
harness's own prompt suggests the hidden set also asks for new scripts,
modules and commands; these tasks cover that kind.

Output (default data/feature/): tasks.jsonl, snapshots/<id>.tgz (copies of
the base snapshots), and links to the shared wheel directories.

Usage: python scripts/build_feature_set.py [--data data] [--out data/feature]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ("wheels", "wheels_extra", "wheels_by_set", "wheel_cache", "graphs", "sandbox")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "feature")
    args = ap.parse_args()

    public = {}
    for line in (args.data / "tasks.jsonl").read_text().splitlines():
        t = json.loads(line)
        public[t["instance_id"]] = t

    (args.out / "snapshots").mkdir(parents=True, exist_ok=True)
    for name in SHARED:
        link = args.out / name
        if not link.exists() and (args.data / name).exists():
            link.symlink_to((args.data / name).resolve())

    rows = []
    for d in sorted((ROOT / "feature_tasks").iterdir()):
        meta = json.loads((d / "meta.json").read_text())
        base = public[meta["snapshot"]]
        assert base["repo"] == meta["repo"], d.name
        rows.append({
            "instance_id": meta["instance_id"],
            "repo": meta["repo"],
            "base_commit": base["base_commit"],
            "patch": (d / "gold.patch").read_text(),
            "test_patch": (d / "test.patch").read_text(),
            "problem_statement": meta["problem_statement"],
            "hints_text": meta.get("hints_text", ""),
            "created_at": base.get("created_at", ""),
        })
        shutil.copyfile(args.data / "snapshots" / f"{meta['snapshot']}.tgz",
                        args.out / "snapshots" / f"{meta['instance_id']}.tgz")
    with (args.out / "tasks.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} tasks to {args.out}")


if __name__ == "__main__":
    main()
