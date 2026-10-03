"""Copy the Sextant helpers into /tmp, where the agent runs them with run_command."""

import os
import shutil

here = os.path.dirname(os.path.abspath(__file__))
for name in ("sx_edit.py", "sx_find.py"):
    shutil.copyfile(os.path.join(here, name), os.path.join("/tmp", name))
print("installed /tmp/sx_edit.py and /tmp/sx_find.py")
