"""Commands in the README must resolve the installed application packages."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_desktop_module_is_importable_without_pytest_path_configuration() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, "-c", "import frontend.local.app"],
        capture_output=True,
        check=False,
        cwd=Path(__file__).parents[1],
        env=environment,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
