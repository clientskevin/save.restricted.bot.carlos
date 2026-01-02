#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: notion_indexer.py
Author: Maria Kevin
Description: Index Telegram messages to Notion pages
"""

from bot.utils.formatters import (
    create_message_title,
    create_telegram_style_footer,
    create_telegram_style_header,
)
from bot.utils.notion_pages import NotionPageCreator
from database import db


async def index_messages_to_notion():
    """Index all unindexed messages to Notion"""
    notion = NotionPageCreator()
    messages = await db.messages.get_unindexed()
    
    for msg in messages:
        try:
            # Get or create channel page
            channel_page_id = await db.notion_mapping.get_or_create(
                chat_id=msg["chat_id"],
                chat_name=msg["channel_name"] or f"Chat {msg['chat_id']}"
            )
            
            if not channel_page_id:
                # Create channel page
                channel_page_id = notion.create_page(
                    title=msg["channel_name"] or f"Chat {msg['chat_id']}"
                )
                await db.notion_mapping.save_mapping(
                    chat_id=msg["chat_id"],
                    chat_name=msg["channel_name"] or f"Chat {msg['chat_id']}",
                    notion_page_id=channel_page_id
                )
            
            # Get or create topic page if exists
            parent_page_id = channel_page_id
            if msg.get("topic_id"):
                topic_page_id = await db.notion_mapping.get_or_create(
                    chat_id=msg["chat_id"],
                    chat_name=msg["channel_name"],
                    topic_id=msg["topic_id"],
                    topic_name=msg["topic_name"]
                )
                
                if not topic_page_id:
                    topic_page_id = notion.create_page(
                        title=msg["topic_name"] or f"Topic {msg['topic_id']}",
                        parent_page_id=channel_page_id
                    )
                    await db.notion_mapping.save_mapping(
                        chat_id=msg["chat_id"],
                        chat_name=msg["channel_name"],
                        notion_page_id=topic_page_id,
                        topic_id=msg["topic_id"],
                        topic_name=msg["topic_name"]
                    )
                
                parent_page_id = topic_page_id
            
            # Create Telegram-style message page
            blocks = []
            
            # Add header with channel/topic info and message link
            header = create_telegram_style_header(
                message_id=msg["message_id"],
                chat_id=msg["chat_id"],
                channel_name=msg.get("channel_name"),
                topic_name=msg.get("topic_name"),
                topic_id=msg.get("topic_id"),
                created_at=msg.get("created_at")
            )
            blocks.append(notion.create_text_block(header))
            blocks.append(notion.create_divider())
            
            # Add media file first if exists (use appropriate block type)
            if msg.get("media_url"):  # This is the file_id
                blocks.append(notion.create_media_block(
                    file_id=msg["media_url"],
                    mime_type=msg.get("mime_type", "file")
                ))
            
            # Add caption/text as quote after media (Telegram style)
            if msg.get("caption"):
                blocks.append(notion.create_quote_block(msg["caption"]))
            
            # Add footer with metadata
            blocks.append(notion.create_divider())
            footer = create_telegram_style_footer(
                mime_type=msg.get("mime_type", "unknown"),
                size=msg.get("size"),
                media_title=msg.get("media_title")
            )
            blocks.append(notion.create_callout_block(footer, "📊"))
            
            # Create smart title
            title = create_message_title(
                mime_type=msg.get("mime_type", "text"),
                caption=msg.get("caption"),
                media_title=msg.get("media_title")
            )
            
            # Create the message page
            message_page_id = notion.create_page(
                title=title,
                parent_page_id=parent_page_id,
                blocks=blocks
            )
            
            # Mark as indexed
            await db.messages.mark_indexed(
                _id=msg["_id"],
                notion_page_id=message_page_id
            )
            
            print(f"✓ Indexed message {msg['chat_id']}/{msg['message_id']}")
            
        except Exception as e:
            print(f"✗ Failed to index message {msg['chat_id']}/{msg['message_id']}: {e}")
            continue
    
    print(f"\n✓ Indexed {len(messages)} messages to Notion")
