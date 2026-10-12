"""Admin authorization for the Telegram bot."""

from __future__ import annotations

import os


def configured_admin_username() -> str:
    """Return the configured admin Telegram username, without a leading @."""
    return os.environ.get("TELEGRAM_ADMIN_USERNAME", "").strip().lstrip("@").lower()


def is_admin_username(username: str | None) -> bool:
    """True when *username* matches TELEGRAM_ADMIN_USERNAME (case-insensitive)."""
    admin = configured_admin_username()
    if not admin or not username:
        return False
    return username.strip().lstrip("@").lower() == admin
