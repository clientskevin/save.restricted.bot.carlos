from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.plugins.on_message import on_https_message
from bot.utils import get_link_parts, get_user_client, is_input_cancelled
from database import db
import logging


logger = logging.getLogger(__name__)


async def fetch_and_process_chunk(
    app: Client,
    bot: Client,
    chat_id: int,
    message_ids: list,
    user_message: Message,
    notion_enabled: bool,
) -> int:
    """Fetch and process a chunk of messages"""
    messages = []
    for start in range(0, len(message_ids), 200):
        try:
            messages.extend(await app.get_messages(chat_id, message_ids[start:start + 200]))
        except Exception as exception:
            logger.error(f"Error fetching messages: {exception}")

    valid_links = []
    for msg in messages:
        if msg and not msg.empty:
            is_bot = msg.chat.type == enums.ChatType.BOT
            link = f"https://t.me/{msg.chat.username}/{msg.id}" if is_bot else msg.link
            valid_links.append(link)

    if valid_links:
        user_message.text = "\n".join(valid_links)
        await on_https_message(bot, user_message, is_batch=True, notion_enabled=notion_enabled)
    return len(valid_links)


@Client.on_message(filters.command(["batch", "nbatch"]) & filters.private & filters.incoming & filters.user(Config.OWNER_ID))
async def batch(bot: Client, message: Message):
    user_id = message.from_user.id
    cmd = message.command[0]

    if cmd == "nbatch":
        notion_enabled = True
    else:
        notion_enabled = False

    app = await get_user_client(user_id)

    if not app or not app.is_connected:
        Config.CLIENTS.pop(app.me.id, None) if app and app.me else None
        return await message.reply_text(
            "⚠️ You need to login first to use this feature.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Login", callback_data="connect_account")]]
            ),
        )

    user_message = message


    text = "📊 Batch\n\n"
    text += "Forward the first message link from the chat from where you'd like to batch-save messages.\n\n"
    text += "Example: \n1. https://t.me/c/2114152609/1\n\n"
    text += "\n\n/cancel to cancel ❌"

    ask = await message.chat.ask(text)

    if await is_input_cancelled(ask):
        return

    first_message = ask

    text = "Please send any one of the following:\n\n"
    text += "1. Copy the last message link and send it to me 📎\n"
    text += "Example: https://t.me/c/2114152609/10\n\n"
    text += "2. Send the number of messages you'd like to batch-save 🔢\n"
    text += "Example: 10"
    text += "\n\n/cancel to cancel ❌"

    ask = await message.chat.ask(text)

    if await is_input_cancelled(ask):
        return

    last_message = ask

    first_parts = get_link_parts(first_message.text)

    if not first_parts:
        text = f"❌ Invalid link - {first_message.text}"
        await message.reply_text(text)
        return

    is_last_message_digit = last_message.text.isdigit()

    if is_last_message_digit:
        last_parts = (
            first_parts[0],
            first_parts[1] + int(last_message.text) - 1,
            first_parts[2],
        )
    else:
        last_parts = get_link_parts(last_message.text)

    if not last_parts:
        text = f"❌ Invalid link - {last_message.text}"
        await message.reply_text(text)
        return

    first_chat_id, first_message_id, first_topic_id = first_parts
    last_chat_id, last_message_id, last_topic_id = last_parts
    

    if last_message_id < first_message_id:
        text = "⚠️ Last message should be older than the first message."
        await message.reply_text(text)
        return

    if first_chat_id != last_chat_id:
        text = "⚠️ Both messages should be from the same chat."
        await message.reply_text(text)
        return


    out = await message.reply_text("🔄 Fetching messages...")

    if not (first_topic_id and last_topic_id):
        total_messages = list(range(first_message_id, last_message_id + 1))
    else:
        if is_last_message_digit:
            last_topic_id = last_message_id + first_topic_id 
        total_messages = list(range(first_topic_id, last_topic_id + 1))

    logger.info(f"Batching {len(total_messages)} messages from {first_chat_id}")
    await out.delete()

    total_valid = 0
    for chunk_start in range(0, len(total_messages), 500):
        ids_chunk = total_messages[chunk_start:chunk_start + 500]
        total_valid += await fetch_and_process_chunk(
            app, bot, first_chat_id, ids_chunk, user_message, notion_enabled
        )

    if total_valid == 0:
        await message.reply_text("🔍 No valid messages found.")
