import os, re, sys, math
W = set(w.lower() for w in sys.argv[1:] if len(w) > 2)
T, D = [], []
for r, ds, fs in os.walk("."):
    ds[:] = [d for d in ds if d[0] != "." and d not in ("tests", "test", "build", "dist")]
    for f in fs:
        if f.endswith(".py") and not f.startswith("test_") and f != "conftest.py":
            p = os.path.join(r, f)[2:]
            s = open(p, errors="ignore").read().lower()
            T.append((p, set(re.findall("[a-z_][a-z0-9_]+", s)) & W, set(re.findall("(?:def|class) ([a-z_][a-z0-9_]*)", s)) & W))
n = len(T)
df = dict((w, sum(w in t[1] for t in T)) for w in W)
R = []
for p, h, d in T:
    s = sum(math.log((n + 1) / (df[w] + 0.5)) * (3 if w in d else 1) for w in h)
    if p.split("/")[0] in ("scripts", "examples", "docs", "benchmarks", "tools"):
        s = s / 2
    if s > 0:
        R.append((-s, p, " ".join(sorted(h))))
for s, p, h in sorted(R)[:8]:
    print(round(-s, 1), p, "|", h)
