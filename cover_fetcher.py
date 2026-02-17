"""
cover_fetcher.py – Fetch cover art suggestions from Google Books and Open Library APIs.

Provides functions to search for book covers by title/filename and download
thumbnail images for display in the GUI.
"""

import io
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/olid/{olid}-L.jpg"

REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitise_query(filename: str) -> str:
    """Derive a human-readable search query from a PDF filename.

    Strips file extension, replaces underscores/hyphens with spaces, removes
    trailing noise such as edition numbers and years in parentheses.

    Args:
        filename: The PDF filename (with or without path).

    Returns:
        Cleaned-up search string.
    """
    name = Path(filename).stem
    # Replace common separators
    name = name.replace("_", " ").replace("-", " ")
    # Remove patterns like "(2nd Edition)", "(2023)", "[v2]", etc.
    name = re.sub(r"[\(\[][^)\]]*[\)\]]", "", name)
    # Remove leftover multiple spaces
    name = re.sub(r"\s{2,}", " ", name).strip()
    logger.debug("Sanitised query: '%s' -> '%s'", filename, name)
    return name


def _load_api_key(api_keys_path: str) -> str:
    """Load the Google Books API key from the keys file.

    Args:
        api_keys_path: Path to the JSON file containing API keys.

    Returns:
        The API key string (may be empty).
    """
    try:
        with open(api_keys_path, "r", encoding="utf-8") as fh:
            keys = json.load(fh)
        return keys.get("google_books_api_key", "")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load API keys from %s: %s", api_keys_path, exc)
        return ""


# ---------------------------------------------------------------------------
# Cover result data class
# ---------------------------------------------------------------------------

class CoverResult:
    """Container for a single cover art search result."""

    def __init__(self, title: str, author: str, thumbnail_url: str,
                 full_url: str, source: str):
        self.title = title
        self.author = author
        self.thumbnail_url = thumbnail_url
        self.full_url = full_url
        self.source = source
        self.thumbnail_image: Optional[Image.Image] = None

    def __repr__(self) -> str:
        return f"CoverResult(title={self.title!r}, source={self.source!r})"


# ---------------------------------------------------------------------------
# Google Books
# ---------------------------------------------------------------------------

def search_google_books(query: str, max_results: int = 8,
                        api_key: str = "") -> list[CoverResult]:
    """Search Google Books API for cover images.

    Args:
        query: Book title or search string.
        max_results: Maximum number of results to return.
        api_key: Optional Google Books API key for higher quotas.

    Returns:
        List of CoverResult objects.
    """
    params: dict = {
        "q": query,
        "maxResults": min(max_results, 40),
        "printType": "books",
    }
    if api_key:
        params["key"] = api_key

    results: list[CoverResult] = []
    try:
        resp = requests.get(GOOGLE_BOOKS_URL, params=params,
                            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Google Books API request failed: %s", exc)
        return results

    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        images = info.get("imageLinks", {})
        thumb = images.get("thumbnail", "")
        full = images.get("large", images.get("medium", thumb))
        if not thumb:
            continue
        # Google returns http URLs – upgrade to https
        thumb = thumb.replace("http://", "https://")
        full = full.replace("http://", "https://")
        results.append(CoverResult(
            title=info.get("title", "Unknown"),
            author=", ".join(info.get("authors", ["Unknown"])),
            thumbnail_url=thumb,
            full_url=full,
            source="Google Books",
        ))
    logger.info("Google Books returned %d results for '%s'", len(results), query)
    return results


# ---------------------------------------------------------------------------
# Open Library
# ---------------------------------------------------------------------------

def search_open_library(query: str, max_results: int = 8) -> list[CoverResult]:
    """Search Open Library for cover images.

    Args:
        query: Book title or search string.
        max_results: Maximum number of results to return.

    Returns:
        List of CoverResult objects.
    """
    params = {
        "title": query,
        "limit": max_results,
        "fields": "title,author_name,cover_edition_key,edition_key",
    }
    results: list[CoverResult] = []
    try:
        resp = requests.get(OPEN_LIBRARY_SEARCH_URL, params=params,
                            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Open Library API request failed: %s", exc)
        return results

    for doc in data.get("docs", []):
        olid = doc.get("cover_edition_key", "")
        if not olid:
            editions = doc.get("edition_key", [])
            olid = editions[0] if editions else ""
        if not olid:
            continue
        cover_url = OPEN_LIBRARY_COVER_URL.format(olid=olid)
        results.append(CoverResult(
            title=doc.get("title", "Unknown"),
            author=", ".join(doc.get("author_name", ["Unknown"])),
            thumbnail_url=cover_url,
            full_url=cover_url,
            source="Open Library",
        ))
    logger.info("Open Library returned %d results for '%s'", len(results), query)
    return results


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------

def download_image(url: str) -> Optional[Image.Image]:
    """Download an image from *url* and return a PIL Image.

    Args:
        url: Direct URL to the image.

    Returns:
        PIL Image object or None on failure.
    """
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img.load()  # force decode
        return img.convert("RGB")
    except Exception as exc:
        logger.warning("Failed to download image from %s: %s", url, exc)
        return None


def download_thumbnails(results: list[CoverResult],
                        size: tuple[int, int] = (150, 200),
                        max_workers: int = 4) -> list[CoverResult]:
    """Download thumbnails for a list of CoverResults in parallel.

    Populates the ``thumbnail_image`` attribute of each result.

    Args:
        results: List of CoverResult objects.
        size: Target thumbnail size (width, height).
        max_workers: Number of parallel download threads.

    Returns:
        The same list, with thumbnail_image populated where possible.
    """
    def _fetch(cr: CoverResult) -> CoverResult:
        img = download_image(cr.thumbnail_url)
        if img:
            img.thumbnail(size, Image.LANCZOS)
            cr.thumbnail_image = img
        return cr

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch, cr): cr for cr in results}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                logger.warning("Thumbnail download error: %s", exc)

    return results


# ---------------------------------------------------------------------------
# Public high-level API
# ---------------------------------------------------------------------------

def fetch_covers(filename: str, max_results: int = 8,
                 api_keys_path: str = "api_keys.json") -> list[CoverResult]:
    """Search both Google Books and Open Library for cover art.

    Results from both sources are merged and duplicates removed (by title).

    Args:
        filename: PDF filename used to derive a search query.
        max_results: Maximum total results to return.
        api_keys_path: Path to the API keys JSON file.

    Returns:
        List of CoverResult objects (thumbnails not yet downloaded).
    """
    query = _sanitise_query(filename)
    if not query:
        logger.warning("Empty query derived from filename '%s'", filename)
        return []

    api_key = _load_api_key(api_keys_path)

    # Fetch from both sources
    google_results = search_google_books(query, max_results, api_key)
    ol_results = search_open_library(query, max_results)

    # Merge & deduplicate by lowercase title
    seen: set[str] = set()
    merged: list[CoverResult] = []
    for cr in google_results + ol_results:
        key = cr.title.lower().strip()
        if key not in seen:
            seen.add(key)
            merged.append(cr)

    return merged[:max_results]
