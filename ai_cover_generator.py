"""
ai_cover_generator.py – Generate cover art using OpenAI DALL-E API.

Provides functions to generate book cover images from text prompts
using OpenAI's image generation API (DALL-E 3).
"""

import io
import json
import logging
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/images/generations"
REQUEST_TIMEOUT = 120  # image generation can take a while


def _load_openai_key(api_keys_path: str = "api_keys.json") -> str:
    """Load the OpenAI API key from the keys file.

    Args:
        api_keys_path: Path to the JSON file containing API keys.

    Returns:
        The API key string (may be empty).
    """
    try:
        with open(api_keys_path, "r", encoding="utf-8") as fh:
            keys = json.load(fh)
        return keys.get("openai_api_key", "")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load API keys from %s: %s", api_keys_path, exc)
        return ""


def build_default_prompt(title: str, style = "", coloPalette = "", authorName = "") -> str:
    """Build a sensible default prompt for generating a book cover.

    Args:
        title: The book title or search term.

    Returns:
        A descriptive prompt string.
    """

    if style != "":
        style = "Style: " + style + "\n"

    if coloPalette != "":
        coloPalette = "Color Palette: " + coloPalette + "\n"
    
    if authorName != "":
        authorName = "Author name: " + authorName + "\n"

    return (
            f"Create a single, full-page eBook cover design based on the following title:"
            f"\"{title}\""
            f"The cover must be designed as a complete first page for a PDF eBook (portrait orientation, A4 size, 2480 x 3508 px, high resolution 300 DPI).\n"
            f"Show only ONE book cover — do not display multiple mockups, stacked books, 3D book renders, or books placed on tables.\n"
            f"The result must be a flat, front-facing, full-bleed cover page without any background scene or presentation mockup. No shadows, no perspective angles, no additional objects.\n"
            f"The design should be professional, modern, and visually appealing, suitable for a digital eBook.\n"
            f"Use balanced typography, strong composition, and high contrast for readability.\n"
            f"Center the title prominently on the cover.\n"
            f"Do not add any platform logos, watermarks, or branding unless specified.\n"
            f"{style}"
            f"{coloPalette}"
            f"{authorName}"
            f"Output only the final flat cover design as a single image.\n"
        )


def generate_cover(prompt: str,
                   api_keys_path: str = "api_keys.json",
                   model: str = "dall-e-3",
                   size: str = "1024x1024",
                   quality: str = "standard") -> Optional[Image.Image]:
    """Generate a cover image using the OpenAI DALL-E API.

    Args:
        prompt: The text prompt describing the desired cover art.
        api_keys_path: Path to the JSON file containing API keys.
        model: The DALL-E model to use ('dall-e-2' or 'dall-e-3').
        size: Image size. For dall-e-3: '1024x1024', '1024x1024', '1792x1024'.
              For dall-e-2: '256x256', '512x512', '1024x1024'.
        quality: Image quality ('standard' or 'hd'). Only for dall-e-3.

    Returns:
        PIL Image of the generated cover, or None on failure.

    Raises:
        ValueError: If the API key is not configured.
        RuntimeError: If the API request fails.
    """
    api_key = _load_openai_key(api_keys_path)
    if not api_key:
        raise ValueError(
            "OpenAI API key not configured.\n\n"
            "Add your key to api_keys.json:\n"
            '  "openai_api_key": "sk-..."'
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "url",
    }

    # quality param is only valid for dall-e-3
    if model == "dall-e-3":
        payload["quality"] = quality

    logger.info("Generating AI cover (model=%s, size=%s)…", model, size)
    logger.debug("Prompt: %s", prompt)

    try:
        resp = requests.post(
            OPENAI_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        error_msg = str(exc)
        # Try to extract a more helpful error message from the response
        try:
            err_data = resp.json()  # type: ignore[union-attr]
            error_msg = err_data.get("error", {}).get("message", error_msg)
        except Exception:
            pass
        logger.error("OpenAI API request failed: %s", error_msg)
        raise RuntimeError(f"AI generation failed: {error_msg}") from exc

    # Extract the image URL
    try:
        image_url = data["data"][0]["url"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected API response format: %s", data)
        raise RuntimeError("Unexpected response from OpenAI API.") from exc

    # Download the generated image
    try:
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        img = Image.open(io.BytesIO(img_resp.content))
        img.load()
        img = img.convert("RGB")
        logger.info("AI cover generated successfully (%dx%d)", img.width, img.height)
        return img
    except Exception as exc:
        logger.error("Failed to download generated image: %s", exc)
        raise RuntimeError(f"Failed to download generated image: {exc}") from exc
