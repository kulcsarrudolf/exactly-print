"""The entrypoint Vercel loads, named in `[tool.vercel]` in pyproject.toml.

The package lives under `src/`, which is not on the path unless the project
is installed, so this puts it there and re-exports the app.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from exactly_print.app import app  # noqa: E402

__all__ = ["app"]
