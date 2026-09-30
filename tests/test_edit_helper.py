"""The edit helper embedded in agent/prompts/system.md, run on edge cases.

The helper is extracted from the prompt text itself, so these tests cover
exactly what the agent installs.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

PROMPT = Path(__file__).resolve().parent.parent / "agent" / "prompts" / "system.md"
SOURCE = '''import re
class A:
    _escape = re.compile(r"(\\\\*)(\\[[a-z#/@][^[]*?])").sub

    def f(self):
        x = 1
        return x
y = 5'''


def helper_source() -> str:
    match = re.search(r"<<'SEXTANT_HELPER'\n(.*?)SEXTANT_HELPER\n", PROMPT.read_text(), re.S)
    assert match, "helper install block not found in the prompt"
    return match.group(1)


@pytest.fixture
def edit(tmp_path, monkeypatch):
    helper = tmp_path / "sx_edit.py"
    # The helper reads /tmp/old and /tmp/new; point it at the test directory.
    helper.write_text(helper_source().replace('"/tmp/old"', repr(str(tmp_path / "old")))
                      .replace('"/tmp/new"', repr(str(tmp_path / "new"))))
    target = tmp_path / "m.py"
    target.write_text(SOURCE)

    def run(old: str, new: str, source: str = SOURCE) -> tuple[str, str]:
        target.write_text(source)
        (tmp_path / "old").write_text(old)
        (tmp_path / "new").write_text(new)
        out = subprocess.run([sys.executable, str(helper), str(target)], capture_output=True, text=True)
        return out.stdout, target.read_text()

    return run


def test_exact(edit):
    out, text = edit("        x = 1\n", "        x = 3\n")
    assert "edited" in out and "        x = 3\n" in text


def test_doubled_backslashes_as_seen_in_json(edit):
    old = '    _escape = re.compile(r"(\\\\\\\\*)(\\\\[[a-z#/@][^[]*?])").sub\n'
    new = '    _escape = re.compile(r"(\\\\\\\\*)(\\\\[[a-z#/@][^[]*?]|$)").sub\n'
    out, text = edit(old, new)
    assert "halving" in out
    assert 'r"(\\\\*)(\\[[a-z#/@][^[]*?]|$)"' in text


def test_indentation_shift(edit):
    out, text = edit("def f(self):\n    x = 1\n", "def f(self):\n    x = 2\n")
    assert "ignoring indentation" in out
    assert "    def f(self):\n        x = 2\n" in text


def test_partial_line_does_not_match(edit):
    out, text = edit("x\n", "z\n")
    assert "no change" in out and text == SOURCE


def test_ambiguous_match_changes_nothing(edit):
    source = "z = 0\nz = 0\n"
    out, text = edit("z = 0\n", "z = 1\n", source)
    assert "2 times" in out and text == source


def test_syntax_error_is_reverted(edit):
    out, text = edit("        x = 1\n", "        x = (\n")
    assert "REVERTED" in out and text == SOURCE


def test_last_line_without_newline(edit):
    out, text = edit("y = 5", "y = 6")
    assert "edited" in out and text.endswith("y = 6") and not text.endswith("\n")
