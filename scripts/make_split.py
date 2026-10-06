"""Write the fixed dev / held-out split of the public tasks.

Held-out tasks are never used for prompt, scaffold or adapter iteration; they
exist only to estimate generalisation. The split is stratified by repository
(about 30% of each repository held out, rounded to nearest) and ordered by
sha256(SEED + instance_id), a total order that does not depend on any random
number generator or on the order of tasks.jsonl.

Usage: python scripts/make_split.py [TASKS_JSONL]
"""

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

SEED = "sextant-split-v1"
HELD_OUT_FRACTION = 0.3
ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    tasks_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "tasks.jsonl"
    by_repo = defaultdict(list)
    for line in tasks_path.read_text().splitlines():
        task = json.loads(line)
        by_repo[task["repo"]].append(task["instance_id"])

    held_out, dev = [], []
    for repo in sorted(by_repo):
        ids = sorted(by_repo[repo], key=lambda i: (hashlib.sha256((SEED + i).encode()).hexdigest(), i))
        n = round(len(ids) * HELD_OUT_FRACTION)
        held_out += ids[:n]
        dev += ids[n:]

    out = ROOT / "splits"
    out.mkdir(exist_ok=True)
    (out / "held_out.txt").write_text("\n".join(sorted(held_out)) + "\n")
    (out / "dev.txt").write_text("\n".join(sorted(dev)) + "\n")
    print(f"dev {len(dev)}, held out {len(held_out)}")
    for repo in sorted(by_repo):
        short = set(by_repo[repo])
        print(f"  {repo}: {len(short & set(dev))} dev, {len(short & set(held_out))} held out")


if __name__ == "__main__":
    main()
