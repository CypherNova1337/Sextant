"""Per-task failure breakdown for an evaluation notebook run.

For each agent and task: whether the re-scored patch resolved the task, how
the session ended, how many tool calls and seconds it used, when the first
source edit landed, how many edits failed, whether the agent edited a file
the reference patch changes (localization), and whether it touched test or
config files.

Usage:
  python scripts/analyze_run.py RUN_DIR VERIFY_JSONL [VERIFY_JSONL ...] [--data DIR]
RUN_DIR holds run_summary.json and results/<agent>/traces/trace_<task>.json
from the notebook; VERIFY_JSONL are scripts/verify_reference.py --patches
outputs for that run.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDIT_TOOLS = {"edit_file", "write_file"}
SHELL_WRITE = re.compile(r"(cat\s+>{1,2}\s*(?!/tmp)[\w.-][\w./-]*\.py|sed\s+-i)")
INSTALL = "SEXTANT_HELPER"


def changed_files(patch: str) -> set[str]:
    """Paths a unified diff changes (with or without git headers)."""
    return set(re.findall(r"^\+\+\+ b/(\S+)", patch or "", re.M))


def is_test_or_config(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    parts = path.split("/")[:-1]
    return (
        name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
        or name in {"pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini"}
        or any(p in {"tests", "test", "testing"} for p in parts)
    )


def trace_facts(trace_path: Path) -> dict:
    facts = {"calls": 0, "first_edit_call": None, "edit_failures": 0, "budget_errors": 0,
             "submitted": False, "errors": 0, "tools": collections.Counter()}
    if not trace_path.exists():
        return facts
    steps = json.loads(trace_path.read_text()).get("steps", [])
    for step in steps:
        obs = str((step.get("observation") or {}).get("content"))
        failed = '"status": "error"' in obs or "mandatory input parameters" in obs
        for call in step.get("tool_calls") or []:
            name = call.get("function_name")
            facts["tools"][name] += 1
            if name not in ("submit_patch", "get_status"):
                facts["calls"] += 1
            if name == "submit_patch":
                facts["submitted"] = True
            if failed:
                facts["errors"] += 1
                if "BudgetExceeded" in obs:
                    facts["budget_errors"] += 1
            args = json.dumps(call.get("arguments") or {})
            is_edit = name in EDIT_TOOLS or (
                name == "run_command" and INSTALL not in args
                and (SHELL_WRITE.search(args) or ("sx_edit.py" in args and "edited " in obs)))
            if is_edit:
                if failed:
                    facts["edit_failures"] += 1
                elif facts["first_edit_call"] is None:
                    facts["first_edit_call"] = facts["calls"]
    return facts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("verify", type=Path, nargs="+")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    args = ap.parse_args()

    gold = {}
    for tasks_file in (args.data / "tasks.jsonl", args.data / "feature" / "tasks.jsonl"):
        if tasks_file.exists():
            for line in tasks_file.read_text().splitlines():
                t = json.loads(line)
                gold[t["instance_id"]] = {f for f in changed_files(t["patch"]) if not is_test_or_config(f)}
    resolved = {}
    for v in args.verify:
        for line in v.read_text().splitlines():
            r = json.loads(line)
            resolved[(r["agent"], r["id"])] = r["resolved"]

    rows = json.loads((args.run_dir / "run_summary.json").read_text())["rows"]
    by_agent = collections.defaultdict(list)
    for row in rows:
        agent, tid = row["agent"], row["id"]
        facts = trace_facts(args.run_dir / "results" / agent / "traces" / f"trace_{tid}.json")
        edited = changed_files(row.get("patch", ""))
        err = row.get("error") or ""
        if "timeout" in err:
            end = "time cap"
        elif "turns" in err:
            end = "turn cap"
        elif facts["budget_errors"]:
            end = "call cap"
        elif facts["submitted"]:
            end = "submitted"
        elif err:
            end = "error: " + err[:40]
        else:
            end = "stopped"
        by_agent[agent].append({
            "id": tid,
            "resolved": resolved.get((agent, tid)),
            "end": end,
            "calls": facts["calls"],
            "seconds": round(row.get("agent_seconds") or 0),
            "first_edit": facts["first_edit_call"],
            "edit_fail": facts["edit_failures"],
            "found_file": bool(edited & gold.get(tid, set())) if gold.get(tid) else None,
            "empty": not edited,
            "touched_tests": sorted(f for f in edited if is_test_or_config(f)),
        })

    for agent, items in by_agent.items():
        n = len(items)
        res = sum(1 for i in items if i["resolved"])
        print(f"\n=== {agent}: resolved {res}/{n}")
        ends = collections.Counter(i["end"] for i in items)
        print("  ends:", dict(ends))
        secs = [i["seconds"] for i in items]
        print(f"  seconds: mean {sum(secs)/n:.0f}, max {max(secs)}; calls mean {sum(i['calls'] for i in items)/n:.1f}")
        found = [i for i in items if i["found_file"] is not None]
        print(f"  edited a reference file: {sum(i['found_file'] for i in found)}/{len(found)}; "
              f"empty patches: {sum(i['empty'] for i in items)}; edit failures: {sum(i['edit_fail'] for i in items)}")
        late = [i for i in items if i["first_edit"] is None or i["first_edit"] > 12]
        print(f"  no edit by call 12: {len(late)} (resolved {sum(1 for i in late if i['resolved'])})")
        touched = [i for i in items if i["touched_tests"]]
        if touched:
            print("  touched test/config files:", [(i["id"], i["touched_tests"]) for i in touched])
        print("  unresolved:")
        for i in items:
            if not i["resolved"]:
                print(f"    {i['id']:22s} end={i['end']:10s} calls={i['calls']:2d} s={i['seconds']:3d} "
                      f"first_edit={i['first_edit']} edit_fail={i['edit_fail']} found_file={i['found_file']} empty={i['empty']}")


if __name__ == "__main__":
    main()
