#!/usr/bin/env python3
"""krakkenVPN Telegram bot: /create issues an .ovpn profile."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from telegram import BotCommand, InputFile, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import voice
from auth import configured_admin_username, is_admin_username
from ovpn import ProfileError, create_ovpn_profile, validate_username

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("krakkenvpn")

WAITING_FOR_USERNAME = 1


def _from_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user) and is_admin_username(user.username)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if _from_admin(update):
        await update.message.reply_text(voice.START_ADMIN)
        return
    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text(voice.START_NEEDS_USERNAME)
        return
    await update.message.reply_text(voice.START_USER.format(username=user.username))


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ConversationHandler.END
    chat = update.effective_chat
    if chat is None or chat.type != ChatType.PRIVATE:
        await update.message.reply_text(voice.NEED_PRIVATE_CHAT)
        return ConversationHandler.END
    if _from_admin(update):
        await update.message.reply_text(voice.ASK_PROFILE_USERNAME)
        return WAITING_FOR_USERNAME

    user = update.effective_user
    if not user or not user.username:
        await update.message.reply_text(voice.NEED_TELEGRAM_USERNAME)
        return ConversationHandler.END
    return await _create_and_send(update, context, user.username)


async def receive_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WAITING_FOR_USERNAME
    if not _from_admin(update):
        await update.message.reply_text(voice.CUSTOM_USERNAME_DENIED)
        return ConversationHandler.END

    try:
        username = validate_username(update.message.text)
    except ValueError as exc:
        await update.message.reply_text(voice.INVALID_USERNAME.format(error=exc))
        return WAITING_FOR_USERNAME

    return await _create_and_send(update, context, username)


async def _create_and_send(
    update: Update, context: ContextTypes.DEFAULT_TYPE, username: str
) -> int:
    assert update.message is not None
    try:
        username = validate_username(username)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return ConversationHandler.END
    requester = update.effective_user.username if update.effective_user else "?"
    await update.message.reply_text(voice.CREATING.format(username=username))
    logger.info("User %s requested profile %s", requester, username)

    create = context.application.bot_data.get("create_profile", create_ovpn_profile)
    try:
        profile = await asyncio.to_thread(create, username)
    except ProfileError as exc:
        logger.warning("Profile creation failed for %s: %s", username, exc)
        await update.message.reply_text(voice.CREATE_FAILED.format(error=exc))
        return ConversationHandler.END
    except Exception:
        logger.exception("Unexpected error creating profile %s", username)
        await update.message.reply_text(voice.CREATE_FAILED_UNKNOWN)
        return ConversationHandler.END

    await update.message.reply_document(
        document=InputFile(profile.encode("utf-8"), filename=f"{username}.ovpn"),
        caption=voice.PROFILE_CAPTION.format(username=username),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text(voice.CANCELLED)
    return ConversationHandler.END


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(voice.UNHANDLED_ERROR)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [BotCommand(command, description) for command, description in voice.BOT_COMMANDS]
    )
    try:
        await application.bot.set_my_name(voice.BOT_NAME)
        await application.bot.set_my_short_description(voice.BOT_SHORT_DESCRIPTION)
        await application.bot.set_my_description(voice.BOT_DESCRIPTION)
    except Exception:
        logger.warning("Could not update the krakkenVPN bot profile on Telegram", exc_info=True)


def build_application(token: str) -> Application:
    application = (
        Application.builder()
        .token(token)
        .concurrent_updates(False)
        .post_init(post_init)
        .build()
    )
    create_conv = ConversationHandler(
        entry_points=[CommandHandler("create", create_start)],
        states={
            WAITING_FOR_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_username),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("create", create_start),
        ],
        allow_reentry=True,
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(create_conv)
    application.add_error_handler(on_error)
    return application


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    admin = configured_admin_username()
    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not admin:
        missing.append("TELEGRAM_ADMIN_USERNAME")
    if missing:
        logger.error(
            "krakkenVPN bot is idle: set %s in the environment.",
            " and ".join(missing),
        )
        signal.pause()
        return

    logger.info("Starting krakkenVPN bot for admin @%s", admin)
    application = build_application(token)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
