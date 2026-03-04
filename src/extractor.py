"""
YouTube Data Extractor Module.
Uses yt-dlp for robust metadata extraction (title, description, views, creator, thumbnail).
Implements graceful degradation: if scraping fails, returns None.
"""

import re
import sys
import yt_dlp
from src.logger import get_logger

logger = get_logger(__name__)

def _validate_youtube_url(url: str) -> bool:
    """Validates that the given URL is a legitimate YouTube video link."""
    # Simplified pattern that covers watch?, short/, and youtu.be/
    pattern = r"^(https?://)?(www\.)?(youtube\.com/|youtu\.be/)[\w\-\?=/]{5,}"
    return bool(re.match(pattern, url.strip()))

def extract_video_metadata(url: str) -> dict | None:
    """
    Main entry point for extracting YouTube video metadata using yt-dlp.
    Implements graceful degradation — returns None on failure instead of crashing.
    """
    if not url or not url.strip():
        logger.warning("Empty URL provided to extractor. Skipping.")
        return None

    if not _validate_youtube_url(url):
        logger.warning(f"Invalid YouTube URL format: {url}")
        return None

    logger.info(f"Attempting to extract metadata with yt-dlp: {url}")

    # yt-dlp configuration
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': True, # Don't extract playlist, just the video
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                logger.error("yt-dlp returned no info for URL.")
                return None

            metadata = {
                "title": info.get("title", "Unknown Title"),
                "description": info.get("description", ""),
                "creator": info.get("uploader", "Unknown Creator"),
                "views": info.get("view_count"),
                "thumbnail": info.get("thumbnail"),
                "source_url": url,
            }

            logger.info(f"Successfully extracted metadata for: {metadata['title']}")
            return metadata

    except Exception as e:
        logger.error(f"yt-dlp extraction error: {e}")
        return None
