import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.utils import (
    show_active_task,
    format_task_text,
    make_task_markup,
    make_batch_menu
)
from database import db

logger = logging.getLogger(__name__)


@Client.on_message(filters.command(["batch", "nbatch"]) & filters.private & filters.incoming & filters.user(Config.OWNER_ID))
async def batch(bot: Client, message: Message):
    """Main batch command entry point"""
    notion_enabled = message.command[0] == "nbatch"
    await show_batch_menu(message, notion_enabled)


async def show_batch_menu(message: Message, notion_enabled: bool):
    """Displays the interactive batch menu to the user"""
    text, markup = make_batch_menu(notion_enabled)
    await message.reply_text(text, reply_markup=markup)


@Client.on_message(filters.command("batch_status") & filters.private & filters.incoming & filters.user(Config.OWNER_ID))
async def batch_status(bot: Client, message: Message):
    """Command to view status of active batch task"""
    await show_active_task(bot, message.chat.id, message.from_user.id)
