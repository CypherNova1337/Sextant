import os, re, sys, math
words = [w.lower() for w in sys.argv[1:] if len(w) > 2]
word_re = re.compile("[A-Za-z_][A-Za-z0-9_]" + chr(123) + "2," + chr(125))
def_re = re.compile("^[ ]*(?:async[ ]+)?(?:def|class)[ ]+([A-Za-z_][A-Za-z0-9_]*)", re.M)
aux = ("scripts", "examples", "docs", "benchmarks", "tools")
files = []
for top, dirs, names in os.walk("."):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("tests", "test", "testing", "node_modules", "build", "dist")]
    for name in names:
        if name.endswith(".py") and not name.startswith("test_") and not name.endswith("_test.py") and name != "conftest.py":
            files.append(os.path.join(top, name)[2:])
toks = []
defs = []
for f in files:
    try:
        text = open(f, errors="ignore").read()
    except OSError:
        text = ""
    toks.append(set(w.lower() for w in word_re.findall(text)))
    defs.append(set(d.lower() for d in def_re.findall(text)))
n = len(files)
df = dict()
for s in toks:
    for w in s:
        df[w] = df.get(w, 0) + 1
present = sorted(set(w for w in words if df.get(w)), key=lambda w: (df[w], w))[:30]
scores = []
for i, f in enumerate(files):
    s = 0.0
    hit = []
    for w in present:
        if w in toks[i]:
            v = math.log((n + 1) / (df[w] + 0.5)) * (3 if w in defs[i] else 1)
            s += v
            hit.append(w)
    if f.split("/")[0] in aux:
        s *= 0.5
    if s > 0:
        scores.append((-s, f, hit))
scores.sort()
print("terms used:", " ".join(present) if present else "none found in the repository")
for neg, f, hit in scores[:10]:
    print(round(-neg, 1), f, "  matches:", " ".join(hit))
