#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: notion_pages.py
Author: Maria Kevin
Description: Minimal Notion Pages API wrapper
"""


from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel

from bot.config import Config


class NotionBlock(BaseModel):
    """Notion block content"""
    type: str
    content: Dict[str, Any]


class NotionPageCreator:
    """Creates Notion pages with hierarchical structure"""
    
    def __init__(self, token: Optional[str] = None, default_parent_id: Optional[str] = None):
        self.token = token or Config.NOTION_TOKEN
        self.default_parent_id = default_parent_id or Config.NOTION_PARENT_PAGE_ID 
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

    def create_page(
        self,
        title: str,
        parent_page_id: Optional[str] = None,
        blocks: Optional[List[Dict]] = None
    ) -> str:
        """Create a Notion page, returns page_id"""
        # Use provided parent, or fall back to default parent
        parent_id = parent_page_id or self.default_parent_id
        parent = {"page_id": parent_id}
        
        payload = {
            "parent": parent,
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            }
        }
        
        if blocks:
            payload["children"] = blocks
        
        response = requests.post(
            f"{self.base_url}/pages",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["id"]

    def create_text_block(self, text: str) -> Dict:
        """Create text paragraph block"""
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": text}}]
            }
        }

    def create_media_block(self, file_id: str, mime_type: str = "file", caption: str = "") -> Dict:
        """Create appropriate media block based on type (image, video, or file)"""
        # Determine block type from mime_type
        if mime_type in ["photo", "image"] or mime_type.startswith("image"):
            block_type = "image"
            media_key = "image"
        elif mime_type in ["video"] or mime_type.startswith("video"):
            block_type = "video"
            media_key = "video"
        else:
            block_type = "file"
            media_key = "file"
        
        block = {
            "type": block_type,
            media_key: {
                "type": "file_upload",
                "file_upload": {"id": file_id}
            }
        }
        
        if caption:
            block[media_key]["caption"] = [{"text": {"content": caption}}]
        else:
            block[media_key]["caption"] = []
        
        return block

    def create_file_block(self, file_id: str, caption: str = "") -> Dict:
        """Create file block from Notion file upload (legacy, use create_media_block)"""
        return self.create_media_block(file_id, "file", caption)

    def create_callout_block(self, text: str, emoji: str = "ℹ️") -> Dict:
        """Create callout block for metadata"""
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": text}}],
                "icon": {"emoji": emoji}
            }
        }

    def create_divider(self) -> Dict:
        """Create a divider block"""
        return {"type": "divider", "divider": {}}

    def create_heading(self, text: str, level: int = 3) -> Dict:
        """Create heading block (level 1, 2, or 3)"""
        heading_type = f"heading_{min(max(level, 1), 3)}"
        return {
            "type": heading_type,
            heading_type: {
                "rich_text": [{"text": {"content": text}}]
            }
        }

    def create_quote_block(self, text: str) -> Dict:
        """Create quote block for captions"""
        return {
            "type": "quote",
            "quote": {
                "rich_text": [{"text": {"content": text}}]
            }
        }
