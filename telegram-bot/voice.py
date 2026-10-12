"""User-facing krakkenVPN copy. The voice is a mighty kraken of the deep: grand, ancient, a little menacing, but always clear about what to do next."""

BOT_NAME = "krakkenVPN"

START_ADMIN = (
    "I am krakkenVPN, ancient lord of the deep, and I answer your call, keeper.\n"
    "Command /create and I shall ask which soul the profile is for, "
    "then rise from the depths with its .ovpn in my grasp.\n"
    "Speak /cancel and I will sink back beneath the waves."
)

START_USER = (
    "I am krakkenVPN, ancient lord of the deep.\n"
    "Speak /create in this private chamber and I shall forge a profile bearing "
    "your Telegram name ({username}), then deliver the .ovpn from the abyss."
)

START_NEEDS_USERNAME = (
    "I am krakkenVPN, ancient lord of the deep.\n"
    "You come to me nameless, mortal. Claim a public Telegram username in "
    "Settings, then speak /create and I shall forge your profile."
)

NEED_PRIVATE_CHAT = (
    "krakkenVPN surrenders its treasures only in private waters. "
    "Seek me in a direct message and speak /create there."
)

ASK_PROFILE_USERNAME = (
    "Name the soul who shall bear this krakkenVPN profile.\n"
    "Speak /cancel if you would rather let the tide pass."
)

NEED_TELEGRAM_USERNAME = (
    "I carve each krakkenVPN profile with its bearer's Telegram name, and you have none. "
    "Claim one in Settings, then summon me again with /create."
)

CUSTOM_USERNAME_DENIED = (
    "Only the keeper of krakkenVPN may choose a profile's name. "
    "Speak /create and I shall bind it to your Telegram name."
)

INVALID_USERNAME = "{error}\nSend another username, or /cancel to calm the waters."

CREATING = "The deep stirs. I am forging a krakkenVPN profile for {username}…"

PROFILE_CAPTION = (
    "Behold, your krakkenVPN profile for {username}, dragged up from the abyss. "
    "Import this .ovpn in OpenVPN Connect and sail under my protection."
)

CREATE_FAILED = "The depths refused me. I could not forge that krakkenVPN profile: {error}"

CREATE_FAILED_UNKNOWN = (
    "A storm churned the abyss while I forged that krakkenVPN profile. "
    "Summon me again with /create."
)

CANCELLED = "So be it. I sink back into the deep. Speak /create when you have need of me."

UNHANDLED_ERROR = "Something churns wrongly in my depths. Summon me again with /create."

BOT_COMMANDS = (
    ("start", "Learn the ways of krakkenVPN"),
    ("create", "Summon a krakkenVPN profile from the deep"),
    ("cancel", "Send the kraken back beneath the waves"),
)

BOT_SHORT_DESCRIPTION = "krakkenVPN, ancient lord of the deep, hands you OpenVPN profiles in chat."
BOT_DESCRIPTION = (
    "I am krakkenVPN, ancient lord of the deep, and I forge OpenVPN profiles. "
    "Speak /create in a private chat: the keeper chooses any name, "
    "and every other mortal receives a profile bound to their Telegram handle."
)
