#!/usr/bin/env python3
"""Telegram bot: admin /create → ask for a username → send the .ovpn profile."""

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

from auth import configured_admin_username, is_admin_username
from ovpn import ProfileError, create_ovpn_profile, validate_username

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("telegram-bot")

WAITING_FOR_USERNAME = 1


def _from_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user) and is_admin_username(user.username)


async def _deny(update: Update) -> int:
    if update.message:
        await update.message.reply_text("You are not allowed to use this bot.")
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _from_admin(update):
        await _deny(update)
        return
    await update.message.reply_text(
        "Send /create to make a new OpenVPN profile.\n"
        "I will ask for the profile username, then send the .ovpn file.\n"
        "Send /cancel to abort."
    )


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ConversationHandler.END
    if not _from_admin(update):
        return await _deny(update)
    chat = update.effective_chat
    if chat is None or chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Use /create in a private chat with this bot.")
        return ConversationHandler.END
    await update.message.reply_text(
        "What username should the new OpenVPN profile use?\nSend /cancel to abort."
    )
    return WAITING_FOR_USERNAME


async def receive_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return WAITING_FOR_USERNAME
    if not _from_admin(update):
        return await _deny(update)

    try:
        username = validate_username(update.message.text)
    except ValueError as exc:
        await update.message.reply_text(f"{exc}\nSend another username, or /cancel.")
        return WAITING_FOR_USERNAME

    await update.message.reply_text(f"Creating an OpenVPN profile for {username}…")
    logger.info(
        "Admin %s requested profile %s",
        update.effective_user.username if update.effective_user else "?",
        username,
    )

    create = context.application.bot_data.get("create_profile", create_ovpn_profile)
    try:
        profile = await asyncio.to_thread(create, username)
    except ProfileError as exc:
        logger.warning("Profile creation failed for %s: %s", username, exc)
        await update.message.reply_text(f"Could not create the profile: {exc}")
        return ConversationHandler.END
    except Exception:
        logger.exception("Unexpected error creating profile %s", username)
        await update.message.reply_text("Could not create the profile. Check the bot logs.")
        return ConversationHandler.END

    await update.message.reply_document(
        document=InputFile(profile.encode("utf-8"), filename=f"{username}.ovpn"),
        caption=f"OpenVPN profile for {username}. Import this file in OpenVPN Connect.",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Something went wrong. Try /create again."
        )


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Show help"),
            BotCommand("create", "Create a new OpenVPN profile"),
            BotCommand("cancel", "Cancel the current operation"),
        ]
    )


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
            "Telegram bot is idle: set %s in the environment.",
            " and ".join(missing),
        )
        signal.pause()
        return

    logger.info("Starting Telegram bot for admin @%s", admin)
    application = build_application(token)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
