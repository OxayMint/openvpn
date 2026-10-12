"""User-facing KrakkenVPN copy. Keep the voice named, direct, and unhurried."""

BOT_NAME = "KrakkenVPN"

START_ADMIN = (
    "Hey — I'm KrakkenVPN.\n"
    "Send /create when you want a new profile. I'll ask for the username, "
    "then send you the .ovpn.\n"
    "/cancel if you change your mind."
)

START_USER = (
    "Hey — I'm KrakkenVPN.\n"
    "Send /create in this private chat and I'll make a profile under your "
    "Telegram username ({username}), then send you the .ovpn."
)

START_NEEDS_USERNAME = (
    "Hey — I'm KrakkenVPN.\n"
    "Set a public Telegram username in Settings first. Then send /create "
    "and I'll get your profile ready."
)

NEED_PRIVATE_CHAT = (
    "KrakkenVPN only hands out profiles in a private chat. DM me and send /create there."
)

ASK_PROFILE_USERNAME = (
    "What username should this KrakkenVPN profile use?\n/cancel if you want to stop."
)

NEED_TELEGRAM_USERNAME = (
    "I name your KrakkenVPN profile after your Telegram username. "
    "Set one in Settings, then send /create again."
)

CUSTOM_USERNAME_DENIED = (
    "Only the KrakkenVPN admin can pick a custom profile name. "
    "Send /create and I'll use your Telegram username."
)

INVALID_USERNAME = "{error}\nSend another username, or /cancel."

CREATING = "On it — putting together a KrakkenVPN profile for {username}…"

PROFILE_CAPTION = (
    "Your KrakkenVPN profile for {username}. "
    "Import this .ovpn in OpenVPN Connect and you're in."
)

CREATE_FAILED = "Couldn't create that KrakkenVPN profile: {error}"

CREATE_FAILED_UNKNOWN = (
    "Something went wrong while building that KrakkenVPN profile. Try /create again."
)

CANCELLED = "Alright, cancelled. Send /create whenever you're ready."

UNHANDLED_ERROR = "Something went wrong on my side. Try /create again."

BOT_COMMANDS = (
    ("start", "How KrakkenVPN works"),
    ("create", "Get a KrakkenVPN profile"),
    ("cancel", "Cancel the current request"),
)

BOT_SHORT_DESCRIPTION = "KrakkenVPN bot — get your OpenVPN profile in chat."
BOT_DESCRIPTION = (
    "KrakkenVPN bot issues OpenVPN profiles. "
    "Send /create in a private chat: the admin chooses a username, "
    "everyone else gets a profile named after their Telegram handle."
)
