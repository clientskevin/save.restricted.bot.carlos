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

    text = "📺 **Your Channel Pairs**\n"
    text += "This lists the links between your Source (where files are taken) and Destination (where files are uploaded) channels.\n\n"

    buttons = []

    for i, channel in enumerate(user_channels):
        status = "✅ Active" if channel["status"] else "❌ Inactive"
        source_title = channel.get("source_title", "Unknown Source")
        destination_title = channel.get("destination_title", "Unknown Dest")
        text += f"- **{source_title}** ➡️ **{destination_title}** ({status})\n"
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{source_title} ➡️ {destination_title}",
                    callback_data=f"view_channel {channel['_id']}",
                )
            ]
        )

    if not user_channels:
        text += "\n- No channel pairs added yet. 🕒\n"

    buttons.append(
        [InlineKeyboardButton("➕ Add Channel Pair", callback_data="add_channel")]
    )

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="start")])

    await bot.reply(
        message,
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_callback_query(filters.regex(r"^add_channel$"))
async def add_channel(bot: Client, message: CallbackQuery):
    user_id = message.from_user.id

    # Step 1: Ask for Source Channel
    try:
        ask_source = await message.message.chat.ask(
            "📥 **Step 1 of 3: Source Channel**\n\n"
            "Send me the ID, username, or forward a message from the **Source Channel** (where the files will be copied from).\n\n"
            "**Examples**:\n"
            "- Username: `@MySourceChannel`\n"
            "- Chat ID: `-1001234567890`\n\n"
            "Send `/cancel` to stop.",
        )
    except Exception as e:
        return await message.message.reply_text(
            f"🚫 Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
            ),
        )

    if ask_source.text and ask_source.text.strip() == "/cancel":
        return await ask_source.reply(
            "❌ Cancelled.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
            ),
        )

    source_input = ask_source
    if source_input.forward_from_chat:
        source_id = source_input.forward_from_chat.id
    elif source_input.text:
        text_val = source_input.text.strip()
        if text_val.replace("-", "").isdigit():
            source_id = int(text_val)
        else:
            source_id = text_val.replace("@", "")
    else:
        return await ask_source.reply(
            "⚠️ Invalid input. Please send a text ID/username or forward a message.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
            ),
        )

    try:
        source_chat = await bot.get_chat(source_id)
        source_title = source_chat.title or "Source Chat"
        source_channel_id = source_chat.id
    except Exception as e:
        return await ask_source.reply(
            f"⚠️ Could not access the Source Channel.\n"
            f"Make sure the bot is an Admin in the channel or a Member of the group.\n\n"
            f"Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
            ),
        )

    # Step 2: Ask for Destination Channel
    try:
        ask_dest = await message.message.chat.ask(
            f"📤 **Step 2 of 3: Destination Channel**\n\n"
            f"Selected Source: **{source_title}**\n\n"
            "Now send the ID, username, or forward a message from the **Destination Channel** (where files will be uploaded to).\n\n"
            "**Examples**:\n"
            "- Username: `@MyDestinationChannel`\n"
            "- Chat ID: `-1009876543210`\n\n"
            "Send `/cancel` to stop.",
        )
    except Exception as e:
        return await message.message.reply_text(
            f"🚫 Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
            ),
        )

    if ask_dest.text and ask_dest.text.strip() == "/cancel":
        return await ask_dest.reply(
            "❌ Cancelled.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
            ),
        )

    dest_input = ask_dest
    if dest_input.forward_from_chat:
        dest_id = dest_input.forward_from_chat.id
    elif dest_input.text:
        text_val = dest_input.text.strip()
        if text_val.replace("-", "").isdigit():
            dest_id = int(text_val)
        else:
            dest_id = text_val.replace("@", "")
    else:
        return await ask_dest.reply(
            "⚠️ Invalid input. Please send a text ID/username or forward a message.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
            ),
        )

    try:
        dest_chat = await bot.get_chat(dest_id)
        destination_title = dest_chat.title or "Destination Chat"
        destination_channel_id = dest_chat.id
    except Exception as e:
        return await ask_dest.reply(
            f"⚠️ Could not access the Destination Channel.\n"
            f"Make sure the bot is an Admin in the channel or a Member of the group.\n\n"
            f"Error: {e}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
            ),
        )

    # Step 3: Ask for Topic ID if Destination is a forum
    topic_id = None
    if dest_chat.is_forum:
        try:
            ask_topic = await message.message.chat.ask(
                "🗂️ **Step 3 of 3: Forum Topic**\n\n"
                "The destination is a forum. Send the **Topic ID** where the files should go.\n\n"
                "Send `/skip` to let the bot auto-create topics/forums.\n"
                "Send `/cancel` to stop.",
            )
        except Exception as e:
            return await message.message.reply_text(
                f"🚫 Error: {e}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="channels")]]
                ),
            )

        if ask_topic.text and ask_topic.text.strip() == "/cancel":
            return await ask_topic.reply(
                "❌ Cancelled.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
                ),
            )

        if ask_topic.text and ask_topic.text.strip() != "/skip":
            topic_val = ask_topic.text.strip()
            if not topic_val.isdigit():
                return await ask_topic.reply(
                    "⚠️ Invalid Topic ID. It must be a number.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
                    ),
                )
            topic_id = int(topic_val)

    # Create mapping
    await db.user_channels.create(
        user_id=user_id,
        source_channel_id=source_channel_id,
        source_title=source_title,
        destination_channel_id=destination_channel_id,
        destination_title=destination_title,
        topic_id=topic_id,
    )
    return await ask_dest.reply(
        f"✅ **Channel pair added successfully!**\n\n"
        f"📢 **Source**: {source_title}\n"
        f"➡️ **Destination**: {destination_title}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")]]
        ),
    )


@Client.on_callback_query(filters.regex(r"^view_channel"))
async def view_channel(_, message: CallbackQuery):
    _id = ObjectId(message.data.split()[1])
    channel = await db.user_channels.filter_document({"_id": ObjectId(_id)})

    text = f"⚙️ **Channel Pair Details**\n\n"
    text += f"📢 **Source Channel** (from which files are read):\n"
    text += f"├─ Title: **{channel.get('source_title', 'Unknown')}**\n"
    text += f"└─ ID: `{channel.get('source_channel_id', 'Unknown')}`\n\n"

    text += f"➡️ **Destination Channel** (where files are uploaded):\n"
    text += f"├─ Title: **{channel.get('destination_title', 'Unknown')}**\n"
    text += f"└─ ID: `{channel.get('destination_channel_id', 'Unknown')}`\n"
    if channel.get("topic_id"):
        text += f"├─ Topic ID: `{channel['topic_id']}`\n"
    text += "\n"

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
            [InlineKeyboardButton("🔙 Back to Channels", callback_data="channels")],
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
