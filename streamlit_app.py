from __future__ import annotations

import os

from config import APP_MODE_CLOUD, APP_MODE_ENV_VAR

os.environ.setdefault(APP_MODE_ENV_VAR, APP_MODE_CLOUD)

from app import main


main()
