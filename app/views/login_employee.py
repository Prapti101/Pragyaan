"""Employee sign-in (Employee ID + password)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import auth_ui  # noqa: E402

auth_ui.login_page("employee")
