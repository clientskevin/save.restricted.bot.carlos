from pyrogram import Client, filters
from database import db
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from bson import ObjectId


@Client.on_callback_query(filters.regex(r"^channels$"))
@Client.on_message(filters.command("channels") & filters.private & filters.incoming)
async def channels(bot, message: CallbackQuery | Message):
    user_channels = await db.user_channels.filter_documents(
        {"user_id": message.from_user.id}
    )

    key = ["user_channels"]

    text = "📺 **Your Channels**\n"

    buttons = []

    for i, channel in enumerate(user_channels):
        status = "✅ Active" if channel["status"] else "❌ Inactive"
        text += f"- {channel['title']} {status}\n"
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{channel['title']} {status}",
                    callback_data=f"view_channel {channel['_id']}",
                )
            ]
        )

    if not user_channels:
        text += "\n- No channels added yet. 🕒\n"

    buttons.append(
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")]
    )

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="settings")])

    await bot.reply(
        message,
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_callback_query(filters.regex(r"^add_channel$"))
async def add_channel(bot: Client, message: CallbackQuery):
    try:
        ask = await message.message.chat.ask(
            f"📥 Send me the channel ID you want to add or forward a message from the channel.\n\n"
            f"💬 Send me the group ID or username directly to use a group.\n\n"
            f"Example:\n"
            f"Channel: `@ChannelUsername` or `-1001234567890`\n"
            f"Group: `@GroupUsername` or `-1001234567890`\n\n"
            f"Note: For topic groups, you'll need to provide the topic ID separately.\n\n"
            f"/cancel to cancel",
        )
    except Exception as e:
        return await message.message.reply_text(
            f"🚫 Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
            ),
        )

    if ask.text and ask.text == "/cancel":
        return await ask.reply(
            "❌ Operation cancelled",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
            ),
        )

    channel_id = ask

    if channel_id.forward_from_chat:
        channel_id = channel_id.forward_from_chat.id
    else:
        if channel_id.text:
            if channel_id.text.replace("-", "").isdigit():
                channel_id = int(channel_id.text)
            else:
                channel_id = channel_id.text.replace("@", "")
        else:
            return await ask.reply(
                "⚠️ Invalid channel ID",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
                ),
            )

    try:
        channel = await bot.get_chat(channel_id)
    except Exception as e:
        return await ask.reply(
            "⚠️ Make sure the channel ID is correct and the bot is an admin in the channel",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
            ),
        )

    title = channel.title

    if channel.is_forum:
        try:
            ask = await message.message.chat.ask(
                f"🗂️ If it's a forum, send me the topic ID of the Topic\n\n/skip to skip\n/cancel to cancel",
            )
        except Exception as e:
            return await message.message.reply_text(
                f"🚫 Error: {e}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
                ),
            )

        if ask.text and ask.text == "/cancel":
            return await ask.reply(
                "❌ Operation cancelled",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
                ),
            )

        if ask.text and ask.text == "/skip":
            topic_id = None
        else:
            topic_id = ask.text
            if not topic_id.isdigit():
                return await ask.reply(
                    "⚠️ Invalid topic ID",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
                    ),
                )
            topic_id = int(topic_id)

    else:
        topic_id = None

    await db.user_channels.create(title, message.from_user.id, channel_id, topic_id)
    return await message.message.reply_text(
        f"✅ Channel added successfully with title: {title}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
        ),
    )


@Client.on_callback_query(filters.regex(r"^view_channel"))
async def view_channel(_, message: CallbackQuery):
    _id = ObjectId(message.data.split()[1])
    channel = await db.user_channels.filter_document({"_id": ObjectId(_id)})

    text = f"**Channel Details**\n\n"
    text += f"📌 Title: {channel['title']}\n"
    text += f"🔢 Channel ID: `{channel['channel_id']}`\n"
    if channel["topic_id"]:
        text += f"🗂️ Topic ID: `{channel['topic_id']}`\n"

    text += f"📊 Status: {'✅ Active' if channel['status'] else '❌ Inactive'}\n"
    text += f"💰 Paid Media: {'✅ Enabled' if channel['paid_media']['status'] else '❌ Disabled'}\n"
    text += f"⭐ Stars Required: {channel['paid_media']['stars']}\n"

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{'🔒 Disable' if channel['status'] else '🔓 Enable'}",
                    callback_data=f"toggle_channel {_id}",
                ),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_channel {_id}"),
            ],
            [
                InlineKeyboardButton(
                    f"{'💰 Disable Paid Media' if channel['paid_media']['status'] else '💰 Enable Paid Media'}",
                    callback_data=f"toggle_paid_media {_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⭐ Edit Stars",
                    callback_data=f"edit_stars {_id}",
                ),
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="channels")],
        ]
    )

    await message.message.edit_text(text, reply_markup=markup)


@Client.on_callback_query(filters.regex(r"^delete_channel"))
async def delete_channel(_, message: CallbackQuery):
    _id = message.data.split()[1]
    return await message.edit_message_text(
        "⚠️ Are you sure you want to delete this channel?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Yes", callback_data=f"confirm_delete_channel {_id}"
                    ),
                    InlineKeyboardButton("❌ No", callback_data="channels"),
                ]
            ]
        ),
    )


@Client.on_callback_query(filters.regex(r"^confirm_delete_channel"))
async def confirm_delete(_, message: CallbackQuery):
    _id = message.data.split()[1]
    await db.user_channels.delete(ObjectId(_id))
    await channels(_, message)


@Client.on_callback_query(filters.regex(r"^toggle_channel"))
async def toggle_channel(bot, message: CallbackQuery):

    _id = message.data.split()[1]
    channel = await db.user_channels.filter_document({"_id": ObjectId(_id)})
    await db.user_channels.update(ObjectId(_id), {"status": not channel["status"]})
    await view_channel(bot, message)


@Client.on_callback_query(filters.regex(r"^toggle_paid_media"))
async def toggle_paid_media(bot, message: CallbackQuery):
    _id = message.data.split()[1]
    channel = await db.user_channels.filter_document({"_id": ObjectId(_id)})
    await db.user_channels.update(
        ObjectId(_id), 
        {"paid_media.status": not channel["paid_media"]["status"]}
    )
    await view_channel(bot, message)


@Client.on_callback_query(filters.regex(r"^edit_stars"))
async def edit_stars(bot, message: CallbackQuery):
    _id = message.data.split()[1]
    channel = await db.user_channels.filter_document({"_id": ObjectId(_id)})
    
    try:
        ask = await message.message.chat.ask(
            f"Enter the number of stars required for paid media (0-100):\n"
            f"Current stars: {channel['paid_media']['stars']}\n\n"
            f"/cancel to cancel"
        )
    except Exception as e:
        return await message.message.reply_text(
            f"🚫 Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data=f"view_channel {_id}")]]
            ),
        )

    if ask.text and ask.text == "/cancel":
        return await ask.reply(
            "❌ Operation cancelled",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data=f"view_channel {_id}")]]
            ),
        )

    try:
        stars = int(ask.text)
        if not 0 <= stars <= 10000:
            raise ValueError("Stars must be between 0 and 10,000")
    except ValueError as e:
        return await ask.reply(
            "⚠️ Invalid number of stars. Please enter a number between 0 and 100.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data=f"view_channel {_id}")]]
            ),
        )

    await db.user_channels.update(
        ObjectId(_id), 
        {"paid_media.stars": stars}
    )
    
    return await message.message.reply_text(
        f"✅ Stars updated successfully to {stars}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data=f"view_channel {_id}")]]
        ),
    )
