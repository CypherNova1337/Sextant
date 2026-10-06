"""Skill-packaged helpers must match the tested sources byte for byte.

v9 ships the helpers as skill scripts instead of embedding them in the
prompt. The edit helper's source of truth is the version embedded in the v8
prompt (covered by test_edit_helper.py); the ranker's is agent_parts/.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted((ROOT / "experiments").glob("*/skills/sextant-tools"))


def embedded_edit_helper() -> str:
    text = (ROOT / "experiments" / "v8" / "prompts" / "system.md").read_text()
    return re.search(r"<<'SEXTANT_HELPER'\n(.*?)SEXTANT_HELPER\n", text, re.S).group(1)


def test_skills_found():
    assert SKILLS


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.parent.name)
def test_helpers_match_sources(skill):
    assert (skill / "scripts" / "sx_edit.py").read_text() == embedded_edit_helper()
    assert (skill / "scripts" / "sx_find.py").read_text() == (ROOT / "agent_parts" / "sx_find.py").read_text()


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.parent.name)
def test_install_copies_helpers(skill, tmp_path):
    script = (skill / "scripts" / "install.py").read_text().replace('"/tmp"', repr(str(tmp_path)))
    runner = skill / "scripts" / "_install_test.py"
    runner.write_text(script)
    try:
        out = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True, check=True).stdout
    finally:
        runner.unlink()
    assert "installed" in out
    for name in ("sx_edit.py", "sx_find.py"):
        assert (tmp_path / name).read_text() == (skill / "scripts" / name).read_text()
