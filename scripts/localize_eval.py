"""How well does the issue text alone point at the file to fix?

For every public task, rank the repository's non-test source files using only
the problem statement, and report how often a file the reference patch
changes appears in the top k. The corpus is the provided code graph (symbol
source by module); a symbol's module is its longest dotted prefix that is
not itself a symbol, since modules are not graph nodes.

Rankers:
  ident  - distinctive identifiers from the issue (code-like tokens, weighted
           by inverse file frequency), with a bonus when a file defines a
           symbol of that name;
  bm25   - BM25 over all word tokens.

Usage: python scripts/localize_eval.py [--data DIR] [--ks 1 3 5 10]
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
# Code-like: snake_case, CamelCase, dotted paths, or backticked spans.
CODEY = re.compile(r"`([^`\n]{2,80})`|\b([A-Za-z_]+(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b|\b([a-z]+_[a-z0-9_]+)\b|\b([A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*)\b")
STOP = set("""the and for that this with from not are was but you have has had can will would should could
into when what which there their them they then than also just like use used using get set new old none true false
self return def class import issue bug fix error test tests code example python version file line""".split())


def is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in "/" + path or name == "conftest.py"


def module_files(graph: dict) -> dict[str, dict]:
    """module -> {"text": concatenated source, "defs": set of short symbol names}."""
    ids = {n["id"] for n in graph["nodes"]}
    mods: dict[str, dict] = defaultdict(lambda: {"text": [], "defs": set()})
    for n in graph["nodes"]:
        parts = n["id"].split(".")
        mod = None
        for k in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:k])
            if prefix not in ids:
                mod = prefix
                break
        if mod is None:
            continue
        mods[mod]["text"].append(n.get("text") or "")
        mods[mod]["defs"].add(parts[-1].lower())
    return {m: {"text": "\n".join(v["text"]), "defs": v["defs"]} for m, v in mods.items()}


def gold_modules(patch: str) -> set[str]:
    out = set()
    for path in re.findall(r"^\+\+\+ b/(\S+\.py)$", patch, re.M):
        if is_test(path):
            continue
        p = path[:-3]
        if p.startswith("src/"):
            p = p[4:]
        if p.endswith("/__init__"):
            p = p[: -len("/__init__")]
        out.add(p.replace("/", "."))
    return out


def issue_terms(text: str) -> tuple[Counter, set[str]]:
    words = Counter(w.lower() for w in WORD.findall(text) if w.lower() not in STOP)
    codey = set()
    for groups in CODEY.findall(text):
        for g in groups:
            for w in WORD.findall(g):
                if w.lower() not in STOP:
                    codey.add(w.lower())
    return words, codey


def rank_ident(mods: dict, words: Counter, codey: set[str]) -> list[str]:
    toks = {m: set(w.lower() for w in WORD.findall(v["text"])) for m, v in mods.items()}
    n = len(mods)
    df = Counter(t for s in toks.values() for t in s)
    scores = {}
    for m, v in mods.items():
        s = 0.0
        for w in words:
            if w in toks[m]:
                idf = math.log((n + 1) / (df[w] + 0.5))
                weight = 3.0 if w in codey else 1.0
                s += weight * idf
                if w in v["defs"]:
                    s += 2.0 * weight * idf
        scores[m] = s
    return sorted(scores, key=lambda m: (-scores[m], m))


def rank_bm25(mods: dict, words: Counter, k1: float = 1.2, b: float = 0.75) -> list[str]:
    docs = {m: Counter(w.lower() for w in WORD.findall(v["text"])) for m, v in mods.items()}
    n = len(docs)
    avg = sum(sum(d.values()) for d in docs.values()) / max(n, 1)
    df = Counter(t for d in docs.values() for t in d)
    scores = {}
    for m, d in docs.items():
        dl = sum(d.values())
        s = 0.0
        for w in words:
            tf = d.get(w, 0)
            if tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avg))
        scores[m] = s
    return sorted(scores, key=lambda m: (-scores[m], m))


def fuse(*rankings: list[str], k: int = 60) -> list[str]:
    """Reciprocal-rank fusion, ties broken by name."""
    score: Counter = Counter()
    for r in rankings:
        for i, m in enumerate(r):
            score[m] += 1.0 / (k + i + 1)
    return sorted(score, key=lambda m: (-score[m], m))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5, 10])
    ap.add_argument("--split", choices=["dev", "held_out", "all"], default="dev",
                    help="tune on dev only; report held_out once a ranker is chosen")
    args = ap.parse_args()
    tasks = [json.loads(l) for l in (args.data / "tasks.jsonl").read_text().splitlines()]
    if args.split != "all":
        keep = set((ROOT / "splits" / f"{args.split}.txt").read_text().split())
        tasks = [t for t in tasks if t["instance_id"] in keep]
    names = ("ident", "bm25", "fused")
    hits = {r: Counter() for r in names}
    counted = 0
    per_repo = defaultdict(lambda: {r: Counter() for r in names} | {"n": 0})
    for t in tasks:
        short = t["instance_id"].rsplit("_", 1)[0]
        gpath = args.data / "graphs" / f"{short}_{t['base_commit']}.json"
        if not gpath.exists():
            continue
        gold = gold_modules(t["patch"])
        if not gold:
            continue
        mods = {m: v for m, v in module_files(json.loads(gpath.read_text())).items()
                if not is_test(m.replace(".", "/") + ".py")}
        if not gold & set(mods):
            continue  # gold module absent from the graph (e.g. only module-level code)
        words, codey = issue_terms(t["problem_statement"])
        counted += 1
        per_repo[t["repo"]]["n"] += 1
        ri, rb = rank_ident(mods, words, codey), rank_bm25(mods, words)
        for name, ranking in (("ident", ri), ("bm25", rb), ("fused", fuse(ri, rb))):
            for k in args.ks:
                if gold & set(ranking[:k]):
                    hits[name][k] += 1
                    per_repo[t["repo"]][name][k] += 1
    print(f"tasks scored: {counted} of {len(tasks)}")
    for name in hits:
        print(f"{name:6s}", "  ".join(f"top{k}={hits[name][k] / counted:.0%}" for k in args.ks))
    for repo, d in sorted(per_repo.items()):
        print(f"  {repo:18s} n={d['n']:3d}", "  ".join(
            f"{name}@5={d[name][5] / d['n']:.0%}" for name in names))


if __name__ == "__main__":
    main()
