#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: archive_handler.py
Author: Maria Kevin
Description: Handle extraction and processing of archive files (.zip, .rar)
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional
import rarfile


class ArchiveHandlerError(Exception):
    """Custom exception for archive handling errors"""
    pass


class ExtractedFile:
    """Represents an extracted file from an archive"""
    def __init__(self, path: str, relative_path: str, size: int):
        self.path = path
        self.relative_path = relative_path
        self.size = size
        self.name = os.path.basename(path)


def is_archive(file_path: str) -> bool:
    """
    Check if a file is a supported archive format.
    
    Args:
        file_path: Path to the file
    
    Returns:
        True if file is .zip or .rar, False otherwise
    """
    ext = Path(file_path).suffix.lower()
    return ext in ['.zip', '.rar']


def extract_archive(
    archive_path: str,
    extract_to: Optional[str] = None,
) -> List[ExtractedFile]:
    """
    Extract archive file (.zip or .rar) to a directory.
    
    Args:
        archive_path: Path to the archive file
        extract_to: Directory to extract to (defaults to temp directory)
    
    Returns:
        List of ExtractedFile objects
    
    Raises:
        ArchiveHandlerError: If extraction fails or limits are exceeded
        FileNotFoundError: If archive doesn't exist
    """
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"Archive not found: {archive_path}")
    
    ext = Path(archive_path).suffix.lower()
    
    # Create extraction directory
    if extract_to is None:
        extract_to = tempfile.mkdtemp(prefix="archive_extract_")
    else:
        os.makedirs(extract_to, exist_ok=True)
    
    extracted_files = []

    try:
        if ext == '.zip':
            extracted_files = _extract_zip(
                archive_path, extract_to
            )
        elif ext == '.rar':
            extracted_files = _extract_rar(
                archive_path, extract_to
            )
        else:
            raise ArchiveHandlerError(f"Unsupported archive format: {ext}")
        
        return extracted_files
    
    except Exception as e:
        # Clean up on error
        if extract_to and os.path.exists(extract_to):
            shutil.rmtree(extract_to, ignore_errors=True)
        raise ArchiveHandlerError(f"Failed to extract archive: {str(e)}") from e


def _extract_zip(
    zip_path: str,
    extract_to: str,
) -> List[ExtractedFile]:
    """Extract ZIP archive"""
    extracted_files = []
    total_size = 0
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Get list of files (excluding directories)

        
        # Check total size before extraction
        for file_info in zip_ref.infolist():
            if not file_info.is_dir():
                total_size += file_info.file_size
        

        
        # Extract all files
        zip_ref.extractall(extract_to)
        
        # Build list of extracted files
        for file_info in zip_ref.infolist():
            if not file_info.is_dir():
                full_path = os.path.join(extract_to, file_info.filename)
                if os.path.exists(full_path):
                    extracted_files.append(ExtractedFile(
                        path=full_path,
                        relative_path=file_info.filename,
                        size=file_info.file_size
                    ))
    
    return extracted_files


def _extract_rar(
    rar_path: str,
    extract_to: str,
) -> List[ExtractedFile]:
    """Extract RAR archive"""
    extracted_files = []
    total_size = 0
    
    with rarfile.RarFile(rar_path, 'r') as rar_ref:
        # Check total size before extraction
        for file_info in rar_ref.infolist():
            if not file_info.isdir():
                total_size += file_info.file_size
        

        # Extract all files
        rar_ref.extractall(extract_to)
        
        # Build list of extracted files
        for file_info in rar_ref.infolist():
            if not file_info.isdir():
                full_path = os.path.join(extract_to, file_info.filename)
                if os.path.exists(full_path):
                    extracted_files.append(ExtractedFile(
                        path=full_path,
                        relative_path=file_info.filename,
                        size=file_info.file_size
                    ))
    
    return extracted_files


def cleanup_extracted_files(extract_dir: str):
    """
    Clean up extracted files directory.
    
    Args:
        extract_dir: Directory containing extracted files
    """
    if extract_dir and os.path.exists(extract_dir):
        try:
            shutil.rmtree(extract_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {extract_dir}: {e}")
