"""The install block and file-ranking helper in the v6 prompt.

The install block is taken from the prompt and run through bash exactly as
the agent would send it, so a heredoc that mangles either helper fails here.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = sorted(p for p in [ROOT / "agent" / "prompts" / "system.md",
                             *(ROOT / "experiments").glob("*/prompts/system.md")]
                 if "SEXTANT_FIND" in p.read_text())
FIND_SRC = (ROOT / "agent_parts" / "sx_find.py").read_text()


def install_block(prompt: Path) -> str:
    text = prompt.read_text()
    start = text.index("Your first tool call must be")
    match = re.search(r"```\n(.*?)```", text[start:], re.S)
    return match.group(1)


@pytest.fixture(params=PROMPTS, ids=lambda p: p.parent.parent.name)
def installed(request, tmp_path):
    """Run the install block with /tmp redirected into the test directory."""
    block = install_block(request.param).replace("/tmp/", f"{tmp_path}/")
    subprocess.run(["bash", "-c", block], check=True)
    return tmp_path


def test_prompts_found():
    assert PROMPTS, "no prompt embeds the find helper"


def test_install_writes_both_helpers_byte_exact(installed):
    assert (installed / "sx_find.py").read_text() == FIND_SRC
    edit = (installed / "sx_edit.py").read_text()
    assert edit.startswith("import sys, py_compile") and "edited" in edit


def test_no_braces_in_embedded_code():
    # ADK reads {name} in an instruction as a session-state placeholder.
    assert not re.search(r"[{}]", FIND_SRC)


def make_repo(root: Path) -> None:
    files = {
        "pkg/__init__.py": "",
        "pkg/highlighter.py": "class ReprHighlighter:\n    url_pattern = 'url'\n",
        "pkg/console.py": "from pkg.highlighter import ReprHighlighter\nconsole = 1\n",
        "pkg/text.py": "def append(text):\n    return text\n",
        "tests/test_highlighter.py": "from pkg.highlighter import ReprHighlighter\nReprHighlighter\n",
        "scripts/tool.py": "reprhighlighter = 'url'\n",
    }
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def run_find(installed: Path, repo: Path, *words: str) -> list[str]:
    out = subprocess.run([sys.executable, str(installed / "sx_find.py"), *words],
                         cwd=repo, capture_output=True, text=True, check=True).stdout
    return [line.split()[1] for line in out.splitlines()]


def test_defining_file_ranks_first(installed, tmp_path):
    repo = tmp_path / "repo"
    make_repo(repo)
    ranked = run_find(installed, repo, "ReprHighlighter", "url")
    assert ranked[0] == "pkg/highlighter.py"
    assert not any(p.startswith("tests/") for p in ranked)


def test_unknown_words_print_nothing(installed, tmp_path):
    repo = tmp_path / "repo"
    make_repo(repo)
    assert run_find(installed, repo, "zzzz", "qqqq") == []
