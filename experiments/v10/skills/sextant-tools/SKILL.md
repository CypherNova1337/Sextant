---
name: sextant-tools
description: Installs two command-line helpers into /tmp. sx_find.py ranks source files by words from the issue; sx_edit.py replaces exact lines in a file safely. Run scripts/install.py once at the start of the task.
---

Run `scripts/install.py` once with `run_skill_script`, then use the helpers through `run_command`:

- `python3 /tmp/sx_find.py word1 word2 ...` lists the source files that best match the words.
- `python3 /tmp/sx_edit.py path/to/file.py` replaces the lines in /tmp/old with the lines in /tmp/new.
