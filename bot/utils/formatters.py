#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: formatters.py
Author: Maria Kevin
Description: Formatting utilities for Notion content
"""

from datetime import datetime
from typing import Optional


def format_file_size(size_bytes: Optional[int]) -> str:
    """Convert bytes to human-readable format"""
    if not size_bytes:
        return "Unknown"
    
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format datetime to readable string"""
    if not dt:
        return "Unknown"
    return dt.strftime("%B %d, %Y at %I:%M %p")


def get_media_emoji(mime_type: str) -> str:
    """Get emoji for media type"""
    emoji_map = {
        "photo": "🖼️",
        "image": "🖼️",
        "video": "🎥",
        "audio": "🎵",
        "document": "📄",
        "text": "💬"
    }
    
    for key, emoji in emoji_map.items():
        if mime_type.startswith(key) or mime_type == key:
            return emoji
    
    return "📎"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def create_message_title(
    mime_type: str,
    caption: Optional[str] = None,
    media_title: Optional[str] = None
) -> str:
    """Create smart message title based on content"""
    emoji = get_media_emoji(mime_type)
    
    # Priority: media_title > caption > generic
    if media_title:
        return f"{emoji} {truncate_text(media_title)}"
    elif caption:
        return f"{emoji} {truncate_text(caption)}"
    else:
        return f"{emoji} {mime_type.upper()}"


def create_message_link(chat_id: int, message_id: int, topic_id: Optional[int] = None) -> str:
    """Create Telegram message link"""
    # Handle negative chat IDs (channels/groups)
    if chat_id < 0:
        # Remove the -100 prefix for public channels
        chat_str = str(chat_id)[4:] if str(chat_id).startswith("-100") else str(abs(chat_id))
    else:
        chat_str = str(chat_id)
    
    base_link = f"https://t.me/c/{chat_str}/{message_id}"
    
    if topic_id:
        base_link = f"https://t.me/c/{chat_str}/{topic_id}/{message_id}"
    
    return base_link


def create_telegram_style_header(
    message_id: int,
    chat_id: int,
    channel_name: Optional[str],
    topic_name: Optional[str],
    topic_id: Optional[int] = None,
    created_at: Optional[datetime] = None
) -> str:
    """Create Telegram-style message header"""
    parts = []
    
    if channel_name:
        parts.append(f"{channel_name}")
    
    if topic_name:
        parts.append(f"{topic_name}")
    
    # Add message link instead of just ID
    msg_link = create_message_link(chat_id, message_id, topic_id)
    parts.append(f"{msg_link}")
    
    if created_at:
        parts.append(f"🕐 {format_timestamp(created_at)}")
    
    return " • ".join(parts)


def create_telegram_style_footer(
    mime_type: str,
    size: Optional[int] = None,
    media_title: Optional[str] = None
) -> str:
    """Create Telegram-style message footer with metadata"""
    emoji = get_media_emoji(mime_type)
    parts = [f"{emoji} {mime_type.upper()}"]
    
    if media_title:
        parts.append(f"{media_title}")
    
    if size:
        parts.append(f"{format_file_size(size)}")
    
    return " • ".join(parts)
