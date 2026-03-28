from __future__ import annotations

import os
from pathlib import Path

from config import APP_MODE_CLOUD, APP_MODE_ENV_VAR

os.environ.setdefault(APP_MODE_ENV_VAR, APP_MODE_CLOUD)

chromium_path = Path("/usr/bin/chromium")
if chromium_path.exists():
    os.environ.setdefault("BROWSER_PATH", str(chromium_path))

from app import main


main()
