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
        chat_id = int(message.chat.id) if message.chat and message.chat.id else 0
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

    async def message_exists(self, message_id: int, chat_id: int) -> Optional[dict]:
        """
        Check if a message already exists in the database.
        
        Args:
            message_id: Telegram message ID
            chat_id: Telegram chat ID
        
        Returns:
            Message document if exists, None otherwise
        """
        messages = await self.filter_document({
            "message_id": message_id,
            "chat_id": chat_id
        })
        return messages

    async def get_or_update_from_pyrogram(
        self,
        message: "types.Message",
        file_id: Optional[str] = None,
    ) -> tuple[Optional[str], bool]:
        """
        Get existing message or update if exists with indexed=False, otherwise create new.
        
        Args:
            message: Pyrogram message object
            file_id: Notion file ID (stored in media_url field)
        
        Returns:
            Tuple of (_id, should_index_to_notion)
            - _id: Document ID (existing or newly created)
            - should_index_to_notion: True if message should be indexed to Notion, False if already indexed
        """
        message_id = message.id
        chat_id = int(message.chat.id) if message.chat and message.chat.id else 0
        
        # Check if message already exists
        existing = await self.message_exists(message_id, chat_id)
        
        if existing:
            # If already indexed, don't re-index
            if existing.get("indexed", False):
                print(f"⚠️ Message {chat_id}/{message_id} already indexed, skipping Notion upload")
                return existing["_id"], False
            
            # If not indexed, update the existing record
            print(f"ℹ️ Message {chat_id}/{message_id} exists but not indexed, updating...")
            
            # Extract updated info from message
            channel_name = getattr(message.chat, "title", None) if message.chat else None
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
            
            caption = message.text or message.caption
            
            # Update the existing document
            update_data = {
                "channel_name": channel_name,
                "topic_id": topic_id,
                "topic_name": topic_name,
                "mime_type": mime_type,
                "size": size,
                "caption": caption,
                "media_title": media_title,
            }
            
            if file_id:
                update_data["media_url"] = file_id
            
            await self.update_one(
                {"_id": existing["_id"]},
                update_data
            )
            
            return existing["_id"], True
        
        # Message doesn't exist, create new
        _id = await self.create_from_pyrogram(message, file_id)
        return _id, True

    async def get_unindexed(self):
        """Get all messages not yet indexed to Notion"""
        return await self.filter_documents({"indexed": False})

    async def mark_indexed(self, _id: str, notion_page_id: str):
        """Mark message as indexed with Notion page ID"""
        return await self.update_one(
            {"_id": _id},
            {"indexed": True, "notion_page_id": notion_page_id}
        )

