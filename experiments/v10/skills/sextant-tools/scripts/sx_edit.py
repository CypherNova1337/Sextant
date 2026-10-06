import sys, py_compile
p = sys.argv[1]
s = open(p).read()
o = open("/tmp/old").read()
n = open("/tmp/new").read()
if not o.endswith("\n"):
    o, n = o + "\n", n + "\n"
tail = "" if s.endswith("\n") else "\n"
L = "\n" + s + tail
def count(t):
    k, i = 0, L.find("\n" + t)
    while i >= 0:
        k, i = k + 1, L.find("\n" + t, i + 1)
    return k
c = count(o)
how = "exact"
if c == 0:
    b = chr(92)
    o2 = o.replace(b + b, b)
    if o2 != o and count(o2) == 1:
        o, n, c, how = o2, n.replace(b + b, b), 1, "after halving doubled backslashes"
if c == 0:
    fl = s.split("\n")
    ol = o.rstrip("\n").split("\n")
    hits = [i for i in range(len(fl) - len(ol) + 1) if all(fl[i + k].strip() == ol[k].strip() for k in range(len(ol)))]
    if len(hits) == 1:
        i = hits[0]
        pad = len(fl[i]) - len(fl[i].lstrip()) - (len(ol[0]) - len(ol[0].lstrip()))
        nl = n.rstrip("\n").split("\n")
        nl = [(" " * pad + x) if pad > 0 and x.strip() else (x[-pad:] if pad < 0 and x[:-pad].strip() == "" else x) for x in nl]
        o = "\n".join(fl[i:i + len(ol)]) + "\n"
        n = "\n".join(nl) + "\n"
        c, how = 1, "ignoring indentation"
print(p, "matches:", c, "(" + how + ")" if c == 1 else "")
if c == 1:
    new = L.replace("\n" + o, "\n" + n, 1)[1:]
    if tail and new.endswith("\n"):
        new = new[:-1]
    open(p, "w").write(new)
    if p.endswith(".py"):
        try:
            py_compile.compile(p, doraise=True)
        except py_compile.PyCompileError as e:
            open(p, "w").write(s)
            print("REVERTED: the edit broke the syntax:", str(e).strip().splitlines()[-1])
            sys.exit(1)
    print("edited", p)
elif c == 0:
    print("no change: copy the old lines exactly as the file has them")
else:
    print("no change: the old lines appear", c, "times; include more surrounding lines")
