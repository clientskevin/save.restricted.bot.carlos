#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: notion.py
Author: Maria Kevin
Description: Clean wrapper for Notion file upload API
"""

import mimetypes
import os
from typing import TYPE_CHECKING, Optional

import requests
from pydantic import BaseModel

from bot.config import Config

if TYPE_CHECKING:
    from pyrogram import types


class NotionUploadResponse(BaseModel):
    """Response from Notion file upload creation"""
    id: str
    upload_url: str


class NotionFileUploadResult(BaseModel):
    """Result of file upload to Notion"""
    file_id: str
    file_name: str
    success: bool = True


class NotionUploadError(Exception):
    """Custom exception for Notion upload errors"""
    pass



def upload_file_to_notion(
    file_path: str,
    notion_token: Optional[str] = None
) -> NotionFileUploadResult:
    """
    Upload a file to Notion using the File Upload API.
    
    Args:
        file_path: Path to the file to upload
        notion_token: Notion integration token (defaults to NOTION_TOKEN env var)
    
    Returns:
        NotionFileUploadResult with upload details
    
    Raises:
        NotionUploadError: If upload fails
        FileNotFoundError: If file doesn't exist
    """

    # Get token from parameter or environment
    token = notion_token or Config.NOTION_TOKEN
    if not token:
        raise NotionUploadError("NOTION_TOKEN not provided")
    
    # Validate file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    # Common headers for all requests
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        # Step 1: Create upload object with filename and content_type
        create_response = requests.post(
            "https://api.notion.com/v1/file_uploads",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={
                "filename": os.path.basename(file_path),
                "content_type": mime_type
            }
        )
        create_response.raise_for_status()
        
        # Parse response with Pydantic
        upload_info = NotionUploadResponse(**create_response.json())
        
        # Step 2: Upload file to the upload URL (requires auth headers)
        with open(file_path, "rb") as f:
            upload_response = requests.post(
                upload_info.upload_url,
                headers=auth_headers,
                files={"file": (os.path.basename(file_path), f, mime_type)}
            )
            upload_response.raise_for_status()
        
        # Return result with file_id
        return NotionFileUploadResult(
            file_id=upload_info.id,
            file_name=os.path.basename(file_path)
        )
        
    except requests.RequestException as e:
        error_msg = f"Upload failed: {str(e)}"
        if hasattr(e, "response") and e.response is not None:
            try:
                error_msg += f"\nResponse: {e.response.text}"
            except Exception:
                pass
        raise NotionUploadError(error_msg) from e


def upload_message_to_notion(
    message: "types.Message",
    file_path: Optional[str] = None,
    notion_token: Optional[str] = None
) -> Optional[NotionFileUploadResult]:
    """
    Upload a Pyrogram message's media to Notion.
    
    Args:
        message: Pyrogram message object
        file_path: Optional path to the file (if already downloaded)
        notion_token: Notion integration token (defaults to NOTION_TOKEN env var)
    
    Returns:
        NotionFileUploadResult if file was uploaded, None if no file to upload
    
    Raises:
        NotionUploadError: If upload fails
    """
    # Only upload if there's a file path
    if not file_path:
        return None
    
    # Upload to Notion
    return upload_file_to_notion(file_path, notion_token)

