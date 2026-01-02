#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: notion_mapping.py
Author: Maria Kevin
Description: Maps Telegram chat/topic IDs to Notion page IDs
"""

from typing import Optional

from database.core import Core


class NotionMappingDB(Core):
    """Maps chat_id/topic_id to Notion page_id"""

    def __init__(self, uri, database_name):
        super().__init__(uri, database_name, "notion_mapping")

    async def get_or_create(
        self,
        chat_id: int,
        chat_name: str,
        topic_id: Optional[int] = None,
        topic_name: Optional[str] = None,
    ) -> Optional[str]:
        """Get existing Notion page ID or return None to create new"""
        query = {"chat_id": chat_id}
        if topic_id:
            query["topic_id"] = topic_id
        
        doc = await self.get_document(query)
        return doc["notion_page_id"] if doc else None

    async def save_mapping(
        self,
        chat_id: int,
        notion_page_id: str,
        chat_name: str,
        topic_id: Optional[int] = None,
        topic_name: Optional[str] = None,
    ):
        """Save chat/topic to Notion page mapping"""
        doc = {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "notion_page_id": notion_page_id,
        }
        if topic_id:
            doc["topic_id"] = topic_id
            doc["topic_name"] = topic_name
        
        return await super().create(doc)
