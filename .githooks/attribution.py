#!/usr/bin/env python3
"""Attribution checks shared by the git hooks.

The blocked names are stored only as SHA-256 digests, so this file never
contains the words it looks for and the whole tree can be swept, hooks included.

    attribution.py msg <file>   commit message (commit-msg hook)
    attribution.py staged       staged additions (pre-commit hook)
    attribution.py push         commits being pushed, read from stdin (pre-push hook)
    attribution.py tree         every tracked file (manual sweep)
"""
import hashlib
import re
import subprocess
import sys

# Window length -> digests of the lower-cased blocked names of that length.
BLOCKED = {
    6: {"c857d09db23e6822e3600bc06ad8d58f92ed62bc8efd81c753f77048662cb97d"},
    9: {"c70eca6b0f88f44d81a41311647e50fda1ac454ec04ffd442b0eb4743a993131"},
}
# Vendor-neutral patterns. The bracketed letter keeps each pattern from
# matching its own source line, so the sweep can include this file.
PATTERNS = [
    re.compile(r"co-authored-by:.*norepl[y]", re.I),
    re.compile(r"generated[ ]with", re.I),
    re.compile(r"norepl[y]@", re.I),
]
WANT_AUTHOR = "CypherNova1337 <131998711+CypherNova1337@users.noreply.github.com>"
ZERO = "0" * 40


def blocked_name(text):
    low = text.lower()
    for n, digests in BLOCKED.items():
        for i in range(len(low) - n + 1):
            if hashlib.sha256(low[i:i + n].encode()).hexdigest() in digests:
                return True
    return False


def findings(text, where):
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if blocked_name(line) or any(p.search(line) for p in PATTERNS):
            out.append(f"{where}:{no}: {line.strip()[:120]}")
    return out


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          errors="replace", check=True).stdout


def added_lines(diff):
    return "\n".join(l[1:] for l in diff.splitlines()
                     if l.startswith("+") and not l.startswith("+++"))


def check_msg(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return findings(f.read(), "message")


def check_staged():
    return findings(added_lines(git("diff", "--cached", "-U0", "--no-color")), "staged")


def check_push(stdin):
    out = []
    for line in stdin.read().splitlines():
        _, local, _, remote = line.split()
        if local == ZERO:
            continue
        span = [local, "--not", "--remotes"] if remote == ZERO else [f"{remote}..{local}"]
        for sha in git("rev-list", *span).split():
            short = sha[:9]
            for who in ("%an <%ae>", "%cn <%ce>"):
                ident = git("show", "-s", f"--format={who}", sha).strip()
                if ident != WANT_AUTHOR:
                    out.append(f"{short}: identity is '{ident}'")
            out += findings(git("show", "-s", "--format=%B", sha), f"{short} message")
            out += findings(added_lines(git("show", "--format=", "-U0", "--no-color", sha)),
                            f"{short} diff")
    return out


def check_tree():
    out = []
    for path in git("ls-files", "-z").split("\0"):
        if not path:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                out += findings(f.read(), path)
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
    return out


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "msg" and len(argv) == 3:
        found = check_msg(argv[2])
    elif mode == "staged":
        found = check_staged()
    elif mode == "push":
        found = check_push(sys.stdin)
    elif mode == "tree":
        found = check_tree()
    else:
        print(__doc__, file=sys.stderr)
        return 2
    for f in found:
        print(f, file=sys.stderr)
    if found:
        print(f"{mode}: attribution found above. Remove it.", file=sys.stderr)
        return 1
    if mode == "tree":
        print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
