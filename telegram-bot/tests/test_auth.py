from __future__ import annotations

import auth


def test_configured_admin_strips_at_and_case(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_USERNAME", "@AliceAdmin")
    assert auth.configured_admin_username() == "aliceadmin"


def test_is_admin_matches_case_insensitively(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_USERNAME", "AliceAdmin")
    assert auth.is_admin_username("aliceadmin")
    assert auth.is_admin_username("@AliceAdmin")
    assert not auth.is_admin_username("eve")
    assert not auth.is_admin_username(None)
    assert not auth.is_admin_username("")


def test_is_admin_false_when_env_missing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ADMIN_USERNAME", raising=False)
    assert not auth.is_admin_username("aliceadmin")
