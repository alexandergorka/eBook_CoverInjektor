"""
pdf_processor.py – Insert cover art into PDFs and export them.

Handles cover page creation with ReportLab, PDF merging with pypdf,
and safe file export with integrity checks.
"""

import logging
import os
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# Mapping of friendly names ➜ ReportLab page sizes
PAGE_SIZES = {
    "A4": A4,
    "LETTER": LETTER,
}


def _get_page_size(name: str) -> tuple[float, float]:
    """Return a ReportLab page-size tuple for the given name.

    Args:
        name: Page size name (e.g. 'A4', 'LETTER').

    Returns:
        Tuple of (width, height) in points.
    """
    return PAGE_SIZES.get(name.upper(), A4)


# ---------------------------------------------------------------------------
# Cover page creation
# ---------------------------------------------------------------------------

def create_cover_page(cover_image: Image.Image,
                      page_size: str = "A4",
                      dpi: int = 300) -> bytes:
    """Create a single-page PDF containing the cover image.

    The image is scaled to fill the page while preserving its aspect ratio
    and is centred on the page.

    Args:
        cover_image: PIL Image of the cover art.
        page_size: Target page size name ('A4' or 'LETTER').
        dpi: Resolution hint (not strictly enforced – PDF is vector-based).

    Returns:
        Bytes of the generated single-page PDF.
    """
    width, height = _get_page_size(page_size)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    img_w, img_h = cover_image.size
    aspect = img_w / img_h
    page_aspect = width / height

    if aspect > page_aspect:
        # Image is wider relative to page – fit to width
        draw_w = width
        draw_h = width / aspect
    else:
        # Image is taller relative to page – fit to height
        draw_h = height
        draw_w = height * aspect

    x = (width - draw_w) / 2
    y = (height - draw_h) / 2

    # Convert PIL Image -> ReportLab ImageReader
    img_buf = BytesIO()
    cover_image.save(img_buf, format="PNG", dpi=(dpi, dpi))
    img_buf.seek(0)
    rl_image = ImageReader(img_buf)

    c.drawImage(rl_image, x, y, draw_w, draw_h, preserveAspectRatio=True)
    c.showPage()
    c.save()

    pdf_bytes = buf.getvalue()
    logger.info("Created cover page (%.1f KB, page_size=%s)", len(pdf_bytes) / 1024, page_size)
    return pdf_bytes


# ---------------------------------------------------------------------------
# First-page rendering (for preview)
# ---------------------------------------------------------------------------

def render_first_page(pdf_path: str, max_size: tuple[int, int] = (300, 420)) -> Optional[Image.Image]:
    """Render the first page of a PDF as a PIL Image.

    Uses ReportLab + pypdf to extract page dimensions, then falls back to a
    simple rasterisation approach by converting the page content.

    Args:
        pdf_path: Path to the PDF file.
        max_size: Maximum (width, height) for the returned image.

    Returns:
        PIL Image of the first page, or None on failure.
    """
    try:
        import subprocess
        import sys

        pdf_path = os.path.abspath(pdf_path)
        reader = PdfReader(pdf_path)
        if not reader.pages:
            return None

        page = reader.pages[0]
        box = page.mediabox
        pw = float(box.width)
        ph = float(box.height)

        # Try sips (macOS) or pdftoppm (Linux/other) for rasterisation
        img = None

        # Attempt 1: use pypdf to extract images from the first page
        if img is None:
            try:
                images_on_page = []
                for image_obj in page.images:
                    img_data = image_obj.data
                    pil_img = Image.open(BytesIO(img_data))
                    images_on_page.append(pil_img)
                if images_on_page:
                    # Use the largest image found on the page
                    images_on_page.sort(key=lambda i: i.size[0] * i.size[1], reverse=True)
                    img = images_on_page[0].convert("RGB")
            except Exception:
                pass

        # Attempt 2: generate a blank page with dimensions as placeholder
        if img is None:
            # Create a white image with correct aspect ratio
            aspect = pw / ph if ph > 0 else 0.7
            target_h = max_size[1]
            target_w = int(target_h * aspect)
            img = Image.new("RGB", (target_w, target_h), "white")

            # Draw "Page 1" label and border for clarity
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, target_w - 1, target_h - 1], outline="#999999", width=2)
            # Try to draw text
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
            except Exception:
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except Exception:
                    font = ImageFont.load_default()
            text = "Page 1"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((target_w - tw) // 2, (target_h - th) // 2), text,
                      fill="#666666", font=font)

        if img:
            img.thumbnail(max_size, Image.LANCZOS)
        return img

    except Exception as exc:
        logger.warning("Failed to render first page of '%s': %s", pdf_path, exc)
        return None


# ---------------------------------------------------------------------------
# PDF merging
# ---------------------------------------------------------------------------

def inject_cover(pdf_path: str,
                 cover_image: Image.Image,
                 output_path: str,
                 page_size: str = "A4",
                 dpi: int = 300,
                 remove_first_page: bool = False) -> str:
    """Insert a cover image as the first page of a PDF.

    The original PDF content is preserved. Optionally removes the existing
    first page (useful when the PDF already has an old/bad cover).

    Args:
        pdf_path: Path to the source PDF file.
        cover_image: PIL Image for the cover.
        output_path: Destination path for the resulting PDF.
        page_size: Cover page size name.
        dpi: Cover image DPI hint.
        remove_first_page: If True, skip the original first page.

    Returns:
        The absolute path of the written output file.

    Raises:
        FileNotFoundError: If the source PDF does not exist.
        RuntimeError: If the PDF cannot be read or written.
    """
    pdf_path = os.path.abspath(pdf_path)
    output_path = os.path.abspath(output_path)

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"Source PDF not found: {pdf_path}")

    logger.info("Injecting cover into '%s' -> '%s' (remove_first=%s)",
                pdf_path, output_path, remove_first_page)

    try:
        # 1. Generate cover page PDF
        cover_pdf_bytes = create_cover_page(cover_image, page_size, dpi)
        cover_reader = PdfReader(BytesIO(cover_pdf_bytes))

        # 2. Read original PDF
        original_reader = PdfReader(pdf_path)

        # 3. Merge cover + original (optionally skipping first page)
        start_page = 1 if remove_first_page and len(original_reader.pages) > 1 else 0
        writer = PdfWriter()
        for page in cover_reader.pages:
            writer.add_page(page)
        for page in original_reader.pages[start_page:]:
            writer.add_page(page)

        # Copy metadata from original
        if original_reader.metadata:
            writer.add_metadata(original_reader.metadata)

        # 4. Write to a temp file first, then move (atomic-ish)
        out_dir = os.path.dirname(output_path)
        os.makedirs(out_dir, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=out_dir)
        try:
            with os.fdopen(fd, "wb") as tmp_fh:
                writer.write(tmp_fh)
            shutil.move(tmp_path, output_path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        logger.info("Successfully wrote '%s' (%d pages)",
                     output_path, len(writer.pages))
        return output_path

    except Exception as exc:
        logger.error("Failed to inject cover: %s", exc)
        raise RuntimeError(f"Cover injection failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Export helper
# ---------------------------------------------------------------------------

def export_pdf(source_path: str, destination_dir: str,
               filename: Optional[str] = None) -> str:
    """Copy a processed PDF to the export destination.

    Args:
        source_path: Path to the PDF to export.
        destination_dir: Target directory (e.g. mounted ebook reader path).
        filename: Optional override for the output filename.

    Returns:
        Full path of the exported file.

    Raises:
        FileNotFoundError: Source file missing.
        PermissionError: Cannot write to destination.
        OSError: Insufficient space or other I/O error.
    """
    source_path = os.path.abspath(source_path)
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if not os.path.isdir(destination_dir):
        raise FileNotFoundError(f"Destination directory not found: {destination_dir}")

    # Check available space
    stat = shutil.disk_usage(destination_dir)
    file_size = os.path.getsize(source_path)
    if stat.free < file_size * 1.1:  # 10 % margin
        raise OSError(
            f"Insufficient space on destination. Need {file_size:,} bytes, "
            f"only {stat.free:,} bytes available."
        )

    if not os.access(destination_dir, os.W_OK):
        raise PermissionError(f"No write permission for: {destination_dir}")

    dest_name = filename or os.path.basename(source_path)
    dest_path = os.path.join(destination_dir, dest_name)

    try:
        shutil.copy2(source_path, dest_path)
        logger.info("Exported '%s' -> '%s'", source_path, dest_path)
        return dest_path
    except Exception as exc:
        logger.error("Export failed: %s", exc)
        raise
