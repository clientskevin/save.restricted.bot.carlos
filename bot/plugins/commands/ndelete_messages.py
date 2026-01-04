#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: ndelete_messages.py
Author: Maria Kevin
Description: Delete messages from Notion database with various filters
"""

from pyrogram import Client, filters, types

from bot.utils import check_admin
from database import db

HELP_TEXT = """
**🗑️ Notion Delete Command**

Delete messages from the Notion database:

**Usage:**
• `/ndelete` - Show this help message
• `/ndelete all` - Delete ALL messages (⚠️ use with caution!)
• `/ndelete <chat_id>` - Delete all messages from a specific chat
• `/ndelete <chat_id> <message_id>` - Delete a specific message
• `/ndelete <chat_id> topic <topic_id>` - Delete all messages from a topic

**Examples:**
• `/ndelete -1001234567890` - Delete all messages from chat -1001234567890
• `/ndelete -1001234567890 123` - Delete message 123 from that chat
• `/ndelete -1001234567890 topic 456` - Delete all messages from topic 456

**Note:** This only deletes from the database, not from Telegram or Notion pages.
"""


@Client.on_message(filters.command("ndelete", prefixes="/") & filters.incoming)
@check_admin
async def ndelete_messages(client: Client, message: types.Message):
    """Handle /ndelete command to delete messages from database"""
    
    # Parse command arguments
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    # Show help if no arguments
    if not args:
        await message.reply_text(HELP_TEXT)
        return
    
    # Handle different delete operations
    try:
        # Delete all messages
        if args[0].lower() == "all":
            # Get count first
            total_count = await db.messages.count_messages()
            
            # Ask for confirmation
            confirm_text = f"⚠️ **WARNING**\n\nYou are about to delete **{total_count}** messages from the database.\n\nThis action cannot be undone!\n\nType `/ndelete confirm_all` to proceed."
            await message.reply_text(confirm_text)
            return
        
        # Confirm delete all
        if args[0].lower() == "confirm_all":
            deleted_count = await db.messages.delete_all_messages()
            await message.reply_text(f"✅ Deleted **{deleted_count}** messages from the database.")
            return
        
        # Delete by chat_id
        if len(args) == 1:
            try:
                chat_id = int(args[0])
                
                # Get count first
                count = await db.messages.count_messages({"chat_id": chat_id})
                if count == 0:
                    await message.reply_text(f"❌ No messages found for chat ID `{chat_id}`")
                    return
                
                deleted_count = await db.messages.delete_by_chat_id(chat_id)
                await message.reply_text(
                    f"✅ Deleted **{deleted_count}** messages from chat `{chat_id}`"
                )
            except ValueError:
                await message.reply_text("❌ Invalid chat ID. Must be a number.")
            return
        
        # Delete by chat_id and message_id
        if len(args) == 2 and args[1].lower() != "topic":
            try:
                chat_id = int(args[0])
                message_id = int(args[1])
                
                deleted_count = await db.messages.delete_by_message_id(chat_id, message_id)
                if deleted_count > 0:
                    await message.reply_text(
                        f"✅ Deleted message `{message_id}` from chat `{chat_id}`"
                    )
                else:
                    await message.reply_text(
                        f"❌ Message `{message_id}` not found in chat `{chat_id}`"
                    )
            except ValueError:
                await message.reply_text("❌ Invalid chat ID or message ID. Must be numbers.")
            return
        
        # Delete by chat_id and topic_id
        if len(args) == 3 and args[1].lower() == "topic":
            try:
                chat_id = int(args[0])
                topic_id = int(args[2])
                
                # Get count first
                count = await db.messages.count_messages({
                    "chat_id": chat_id,
                    "topic_id": topic_id
                })
                if count == 0:
                    await message.reply_text(
                        f"❌ No messages found for chat `{chat_id}` topic `{topic_id}`"
                    )
                    return
                
                deleted_count = await db.messages.delete_by_topic_id(chat_id, topic_id)
                await message.reply_text(
                    f"✅ Deleted **{deleted_count}** messages from chat `{chat_id}` topic `{topic_id}`"
                )
            except ValueError:
                await message.reply_text("❌ Invalid chat ID or topic ID. Must be numbers.")
            return
        
        # Invalid arguments
        await message.reply_text(
            "❌ Invalid arguments.\n\nUse `/ndelete` to see usage instructions."
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
        print(f"Error in ndelete command: {e}")
