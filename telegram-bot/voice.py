"""User-facing krakkenVPN copy. Keep the voice named, direct, and unhurried."""

BOT_NAME = "krakkenVPN"

START_ADMIN = (
    "Hey — I'm krakkenVPN.\n"
    "Send /create when you want a new profile. I'll ask for the username, "
    "then send you the .ovpn.\n"
    "/cancel if you change your mind."
)

START_USER = (
    "Hey — I'm krakkenVPN.\n"
    "Send /create in this private chat and I'll make a profile under your "
    "Telegram username ({username}), then send you the .ovpn."
)

START_NEEDS_USERNAME = (
    "Hey — I'm krakkenVPN.\n"
    "Set a public Telegram username in Settings first. Then send /create "
    "and I'll get your profile ready."
)

NEED_PRIVATE_CHAT = (
    "krakkenVPN only hands out profiles in a private chat. DM me and send /create there."
)

ASK_PROFILE_USERNAME = (
    "What username should this krakkenVPN profile use?\n/cancel if you want to stop."
)

NEED_TELEGRAM_USERNAME = (
    "I name your krakkenVPN profile after your Telegram username. "
    "Set one in Settings, then send /create again."
)

CUSTOM_USERNAME_DENIED = (
    "Only the krakkenVPN admin can pick a custom profile name. "
    "Send /create and I'll use your Telegram username."
)

INVALID_USERNAME = "{error}\nSend another username, or /cancel."

CREATING = "On it — putting together a krakkenVPN profile for {username}…"

PROFILE_CAPTION = (
    "Your krakkenVPN profile for {username}. "
    "Import this .ovpn in OpenVPN Connect and you're in."
)

CREATE_FAILED = "Couldn't create that krakkenVPN profile: {error}"

CREATE_FAILED_UNKNOWN = (
    "Something went wrong while building that krakkenVPN profile. Try /create again."
)

CANCELLED = "Alright, cancelled. Send /create whenever you're ready."

UNHANDLED_ERROR = "Something went wrong on my side. Try /create again."

BOT_COMMANDS = (
    ("start", "How krakkenVPN works"),
    ("create", "Get a krakkenVPN profile"),
    ("cancel", "Cancel the current request"),
)

BOT_SHORT_DESCRIPTION = "krakkenVPN bot — get your OpenVPN profile in chat."
BOT_DESCRIPTION = (
    "krakkenVPN bot issues OpenVPN profiles. "
    "Send /create in a private chat: the admin chooses a username, "
    "everyone else gets a profile named after their Telegram handle."
)
