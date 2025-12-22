from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Script
from bot.utils import add_user


@Client.on_message(filters.command("start") & filters.private & filters.incoming)
@Client.on_callback_query(filters.regex("^start$"))
async def start(bot: Client, message: Message):
    await add_user(bot, message.from_user)
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("❓ Help", callback_data="help_1"),
            ],
        ]
    )

    await bot.reply(
        message,
        text=Script.START_MESSAGE,
        reply_markup=markup,
        disable_web_page_preview=True,
    )
