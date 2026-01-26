from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.plugins.on_message import on_https_message
from bot.utils import get_link_parts, get_user_client, is_input_cancelled
from database import db
import logging


logger = logging.getLogger(__name__)

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

    # if (first_topic_id and not last_topic_id) or (not first_topic_id and last_topic_id):
    #     text = "⚠️ Both messages should be from the same topic."
    #     await message.reply_text(text)
    #     return

    # if (first_topic_id and last_topic_id) and first_message_id != last_message_id:
    #     text = "⚠️ Both messages should be from the same topic."
    #     await message.reply_text(text)
    #     return

    out = await message.reply_text("🔄 Fetching messages...")

    if not (first_topic_id and last_topic_id):
        messages = []
        total_messages = list(range(first_message_id, last_message_id + 1))
        logger.info(f"Fetching {len(total_messages)} messages from {first_chat_id}: from {first_message_id} to {last_message_id}")
        for i in range(0, len(total_messages), 200):
            try:
                messages.extend(
                    await app.get_messages(first_chat_id, total_messages[i : i + 200])
                )
            except Exception as e:
                text = f"⚠️ Some error occurred while fetching messages: {e}"
                return await out.edit(text)
    else:
        # messages = []
        # async for message in app.get_discussion_replies(
        #     first_chat_id, first_message_id
        # ):
        #     print(message.id)
        #     if not message.topic:
        #         continue

        #     # if (
        #     #     message.topic.id != first_message_id
        #     # ):  # for topic links, message id acts as topic id
        #     #     continue

        #     if len(messages) > len(range(first_topic_id, last_topic_id + 1)):
        #         logger.info(
        #             f"Got {len(messages)} messages for {len(range(first_topic_id, last_topic_id + 1))} topics"
        #         )
        #         break

        #     if message.id not in range(first_topic_id, last_topic_id + 1):
        #         continue

        #     messages.append(message)
        #     messages = sorted(messages, key=lambda x: x.id)

        if is_last_message_digit:
            last_topic_id = last_message_id + first_topic_id 

        messages = []
        total_messages = list(range(first_topic_id, last_topic_id + 1))

        logger.info(f"Fetching {len(total_messages)} messages from {first_chat_id}: from {first_topic_id} to {last_topic_id}")
        for i in range(0, len(total_messages), 200):
            try:
                messages.extend(
                    await app.get_messages(first_chat_id, total_messages[i : i + 200])
                )
            except Exception as e:
                text = f"⚠️ Some error occurred while fetching messages: {e}"
                return await out.edit(text)

    valid_messages = []

    for message in messages:
        if message.empty:
            continue

        if message.chat.type == enums.ChatType.BOT:
            link = f"https://t.me/{message.chat.username}/{message.id}"
        else:
            link = message.link

        valid_messages.append(link)

    if not valid_messages:
        text = "🔍 No valid messages found."
        return await out.edit(text)

    await out.delete()
    text = "\n".join(valid_messages)

    user_message.text = text

    logger.info(f"Batching {len(valid_messages)} messages")
    await on_https_message(bot, user_message, is_batch=True, notion_enabled=notion_enabled)
