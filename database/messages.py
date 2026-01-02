#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: messages.py
Author: Maria Kevin
Description: Database class for storing message metadata
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pyrogram import types

from database.core import Core


class MessagesDB(Core):
    """Messages metadata storage"""

    def __init__(self, uri, database_name):
        super().__init__(uri, database_name, "messages")

    async def create(
        self,
        message_id: int,
        chat_id: int,
        topic_id: Optional[int] = None,
        channel_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        mime_type: str = "text",
        size: Optional[int] = None,
        caption: Optional[str] = None,
        media_title: Optional[str] = None,
        media_url: Optional[str] = None,
        indexed: bool = False,
        notion_page_id: Optional[str] = None,
    ):
        """Create a new message record"""
        doc = {
            "message_id": message_id,
            "chat_id": chat_id,
            "topic_id": topic_id,
            "channel_name": channel_name,
            "topic_name": topic_name,
            "mime_type": mime_type,
            "size": size,
            "caption": caption,
            "media_title": media_title,
            "media_url": media_url,
            "indexed": indexed,
            "notion_page_id": notion_page_id,
            "created_at": datetime.now(),
        }
        return await super().create(doc)

    async def create_from_pyrogram(
        self,
        message: "types.Message",
        file_id: Optional[str] = None,
    ):
        """Create message record from Pyrogram message object
        
        Args:
            message: Pyrogram message object
            file_id: Notion file ID (stored in media_url field)
        """
        # Extract basic info
        message_id = message.id
        chat_id = message.chat.id if message.chat else 0
        channel_name = getattr(message.chat, "title", None) if message.chat else None
        
        # Extract topic info
        topic_id = None
        topic_name = None
        if message.topic:
            topic_id = message.topic.id
            topic_name = message.topic.title
        
        # Determine mime type and size
        mime_type = "text"
        size = None
        media_title = None
        
        if message.text:
            mime_type = "text"
        elif message.photo:
            mime_type = "photo"
            size = message.photo.file_size
        elif message.video:
            mime_type = "video"
            size = message.video.file_size
            media_title = getattr(message.video, "file_name", None)
        elif message.audio:
            mime_type = "audio"
            size = message.audio.file_size
            media_title = getattr(message.audio, "file_name", None)
        elif message.document:
            mime_type = "document"
            size = message.document.file_size
            media_title = getattr(message.document, "file_name", None)
        
        # Get caption
        caption = message.text or message.caption
        
        return await self.create(
            message_id=message_id,
            chat_id=chat_id,
            topic_id=topic_id,
            channel_name=channel_name,
            topic_name=topic_name,
            mime_type=mime_type,
            size=size,
            caption=caption,
            media_title=media_title,
            media_url=file_id
        )

    async def get_unindexed(self):
        """Get all messages not yet indexed to Notion"""
        return await self.filter_documents({"indexed": False})

    async def mark_indexed(self, _id: str, notion_page_id: str):
        """Mark message as indexed with Notion page ID"""
        return await self.update_one(
            {"_id": _id},
            {"indexed": True, "notion_page_id": notion_page_id}
        )

