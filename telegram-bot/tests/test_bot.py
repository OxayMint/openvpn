from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.constants import ChatType
from telegram.ext import ConversationHandler

import bot
import voice
from ovpn import ProfileError


def _update(*, username="alice", text=None, chat_type=ChatType.PRIVATE):
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()
    message.reply_document = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_message = message
    update.effective_user = MagicMock(username=username)
    update.effective_chat = MagicMock(type=chat_type)
    return update


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_USERNAME", "alice")


@pytest.mark.asyncio
async def test_start_introduces_krakkenvpn_to_admin(admin_env):
    update = _update(username="alice")
    await bot.start(update, MagicMock())
    text = update.message.reply_text.await_args.args[0]
    assert text == voice.START_ADMIN
    assert text.startswith("Hey — I'm KrakkenVPN.")


@pytest.mark.asyncio
async def test_start_introduces_krakkenvpn_to_user(admin_env):
    update = _update(username="eve")
    await bot.start(update, MagicMock())
    text = update.message.reply_text.await_args.args[0]
    assert "I'm KrakkenVPN" in text
    assert "eve" in text


@pytest.mark.asyncio
async def test_create_for_non_admin_uses_telegram_username(admin_env):
    update = _update(username="eve")
    context = MagicMock()
    context.application.bot_data = {
        "create_profile": lambda name: f"client\n# {name}\n"
    }
    result = await bot.create_start(update, context)
    assert result == ConversationHandler.END
    update.message.reply_document.assert_awaited()
    document = update.message.reply_document.await_args.kwargs["document"]
    assert document.filename == "eve.ovpn"
    assert b"# eve" in document.input_file_content
    caption = update.message.reply_document.await_args.kwargs["caption"]
    assert caption == voice.PROFILE_CAPTION.format(username="eve")
    assert "KrakkenVPN" in caption


@pytest.mark.asyncio
async def test_create_requires_telegram_username_for_non_admin(admin_env):
    update = _update(username=None)
    result = await bot.create_start(update, MagicMock())
    assert result == ConversationHandler.END
    assert update.message.reply_text.await_args.args[0] == voice.NEED_TELEGRAM_USERNAME


@pytest.mark.asyncio
async def test_create_asks_for_username(admin_env):
    update = _update(username="alice")
    result = await bot.create_start(update, MagicMock())
    assert result == bot.WAITING_FOR_USERNAME
    assert update.message.reply_text.await_args.args[0] == voice.ASK_PROFILE_USERNAME
    assert "KrakkenVPN" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_create_requires_private_chat(admin_env):
    update = _update(username="alice", chat_type=ChatType.GROUP)
    result = await bot.create_start(update, MagicMock())
    assert result == ConversationHandler.END
    assert update.message.reply_text.await_args.args[0] == voice.NEED_PRIVATE_CHAT


@pytest.mark.asyncio
async def test_invalid_username_keeps_waiting(admin_env):
    update = _update(username="alice", text="bad name")
    result = await bot.receive_username(update, MagicMock())
    assert result == bot.WAITING_FOR_USERNAME
    assert "Send another username" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_valid_username_sends_ovpn(admin_env):
    update = _update(username="alice", text="vpnuser")
    context = MagicMock()
    context.application.bot_data = {
        "create_profile": lambda name: f"client\nremote 1.2.3.4 1194\n# {name}\n"
    }
    result = await bot.receive_username(update, context)
    assert result == ConversationHandler.END
    update.message.reply_document.assert_awaited()
    document = update.message.reply_document.await_args.kwargs["document"]
    assert document.filename == "vpnuser.ovpn"
    assert document.input_file_content.startswith(b"client")
    assert "KrakkenVPN" in update.message.reply_document.await_args.kwargs["caption"]


@pytest.mark.asyncio
async def test_profile_error_is_reported(admin_env):
    update = _update(username="alice", text="vpnuser")
    context = MagicMock()
    context.application.bot_data = {
        "create_profile": lambda name: (_ for _ in ()).throw(ProfileError("container down"))
    }
    result = await bot.receive_username(update, context)
    assert result == ConversationHandler.END
    assert "container down" in update.message.reply_text.await_args.args[0]
