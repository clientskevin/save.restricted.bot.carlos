from pyrogram import Client, filters
from tabulate import tabulate
from database import db
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup


@Client.on_callback_query(filters.regex(r"^settings"))
@Client.on_message(filters.command("settings") & filters.private & filters.incoming)
async def settings(bot: Client, query: CallbackQuery):
    key = "settings"
    text = "Settings\n\n"
    user = await db.users.read(query.from_user.id)

    user_channels_count = await db.user_channels.count_documents(
        {"user_id": query.from_user.id}
    )

    session_username = (
        f'@{user["session"]["username"]}' if user["session"]["username"] else "No Username``"
    )

    text += f"┌─ User: {query.from_user.mention}\n"
    text += f"├─ Session: {session_username}\n"
    text += f"├─ User ID: `{query.from_user.id}`\n"
    text += f"└─ Linked Channels: {user_channels_count}\n"

    text += f"You can customize the way your files are uploaded by using the following settings.\n\n"

    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👤 My Account", callback_data="connected_account")],
            [
                InlineKeyboardButton("📢 Channels", callback_data="channels"),
            ],
            [InlineKeyboardButton("📋 Media Types", callback_data="mediatype_main")],
            [InlineKeyboardButton("🔙 Back", callback_data="start")],
        ]
    )
    text = get_settings_table(query, session_username, user_channels_count)

    await bot.reply(query, text=text, key=key, reply_markup=markup)


def get_settings_table(query, session_username, user_channels_count):
    table_data = [
        ["User", query.from_user.first_name],
        ["Session", session_username],
        ["User ID", f"{query.from_user.id}"],
        ["Channels", user_channels_count],
    ]

    header_text = "Settings\n\n"
    # Generate the table
    table = tabulate(
        table_data,
        tablefmt="grid",
        headers=["Setting", "Status"],
        colalign=("left", "right"),
    )
    table = "`" + table + "`"

    # Add additional info
    extra_info = "\n\nYou can customize the way your files are uploaded by using the following settings.\n\n"

    return header_text + table + extra_info


def get_tick(status: bool) -> str:
    return " ✔" if status else " ✘"


def get_content_status(c):
    return "Empty" if not c else "Set"
