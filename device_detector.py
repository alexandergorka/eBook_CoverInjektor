"""
device_detector.py – Detect mounted ebook reader devices.

Cross-platform detection for Kindle, Kobo, PocketBook, and other
common USB-mounted ebook readers on macOS, Linux, and Windows.
"""

import logging
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Known ebook reader volume-name patterns (case-insensitive)
EREADER_PATTERNS: list[re.Pattern] = [
    re.compile(r"kindle", re.IGNORECASE),
    re.compile(r"kobo", re.IGNORECASE),
    re.compile(r"pocketbook", re.IGNORECASE),
    re.compile(r"nook", re.IGNORECASE),
    re.compile(r"tolino", re.IGNORECASE),
    re.compile(r"onyx", re.IGNORECASE),
    re.compile(r"boox", re.IGNORECASE),
    re.compile(r"remarkable", re.IGNORECASE),
    re.compile(r"sony.?reader", re.IGNORECASE),
]

# Subdirectories commonly used for documents on ebook readers
EREADER_DOC_DIRS = ["documents", "Documents", "Books", "books", "eBooks", "ebooks"]


@dataclass
class DetectedDevice:
    """Represents a detected ebook reader device."""
    name: str
    mount_point: str
    documents_dir: str
    free_space_bytes: int = 0

    @property
    def free_space_mb(self) -> float:
        return self.free_space_bytes / (1024 * 1024)

    def __str__(self) -> str:
        return f"{self.name} ({self.free_space_mb:.0f} MB free)"


# ---------------------------------------------------------------------------
# Platform-specific detection
# ---------------------------------------------------------------------------

def _detect_macos() -> list[DetectedDevice]:
    """Detect ebook readers mounted under /Volumes on macOS."""
    devices: list[DetectedDevice] = []
    volumes_dir = Path("/Volumes")
    if not volumes_dir.is_dir():
        return devices

    for vol in volumes_dir.iterdir():
        if not vol.is_dir():
            continue
        vol_name = vol.name
        for pattern in EREADER_PATTERNS:
            if pattern.search(vol_name):
                doc_dir = _find_documents_dir(str(vol))
                try:
                    usage = os.statvfs(str(vol))
                    free = usage.f_bavail * usage.f_frsize
                except OSError:
                    free = 0
                devices.append(DetectedDevice(
                    name=vol_name,
                    mount_point=str(vol),
                    documents_dir=doc_dir,
                    free_space_bytes=free,
                ))
                logger.info("Detected ebook reader: %s at %s", vol_name, vol)
                break
    return devices


def _detect_linux() -> list[DetectedDevice]:
    """Detect ebook readers mounted under /media or /mnt on Linux."""
    devices: list[DetectedDevice] = []
    search_roots = []

    # /media/<user>/
    media = Path("/media")
    if media.is_dir():
        for user_dir in media.iterdir():
            if user_dir.is_dir():
                search_roots.extend(user_dir.iterdir())

    # /mnt/
    mnt = Path("/mnt")
    if mnt.is_dir():
        search_roots.extend(mnt.iterdir())

    for vol in search_roots:
        if not vol.is_dir():
            continue
        vol_name = vol.name
        for pattern in EREADER_PATTERNS:
            if pattern.search(vol_name):
                doc_dir = _find_documents_dir(str(vol))
                try:
                    usage = os.statvfs(str(vol))
                    free = usage.f_bavail * usage.f_frsize
                except OSError:
                    free = 0
                devices.append(DetectedDevice(
                    name=vol_name,
                    mount_point=str(vol),
                    documents_dir=doc_dir,
                    free_space_bytes=free,
                ))
                logger.info("Detected ebook reader: %s at %s", vol_name, vol)
                break
    return devices


def _detect_windows() -> list[DetectedDevice]:
    """Detect ebook readers on Windows drive letters."""
    devices: list[DetectedDevice] = []
    try:
        # Use wmic to list volumes (works without admin)
        result = subprocess.run(
            ["wmic", "logicaldisk", "get", "caption,volumename,freespace"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().splitlines()[1:]  # skip header
    except Exception as exc:
        logger.warning("Windows drive detection failed: %s", exc)
        # Fallback: iterate common drive letters
        lines = []
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            if os.path.isdir(drive):
                try:
                    vol_label = _get_windows_label(drive)
                    lines.append(f"{letter}:  {0}  {vol_label}")
                except Exception:
                    pass

    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        drive_letter = parts[0]  # e.g. "E:"
        vol_name = " ".join(parts[2:]) if len(parts) > 2 else ""
        drive_path = drive_letter + "\\"

        for pattern in EREADER_PATTERNS:
            if pattern.search(vol_name) or pattern.search(drive_letter):
                doc_dir = _find_documents_dir(drive_path)
                try:
                    import shutil
                    usage = shutil.disk_usage(drive_path)
                    free = usage.free
                except OSError:
                    free = 0
                devices.append(DetectedDevice(
                    name=vol_name or drive_letter,
                    mount_point=drive_path,
                    documents_dir=doc_dir,
                    free_space_bytes=free,
                ))
                logger.info("Detected ebook reader: %s at %s", vol_name, drive_path)
                break
    return devices


def _get_windows_label(drive: str) -> str:
    """Get the volume label for a Windows drive."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        buf = ctypes.create_unicode_buffer(1024)
        kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive), buf, ctypes.sizeof(buf),
            None, None, None, None, 0,
        )
        return buf.value
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_documents_dir(mount_point: str) -> str:
    """Try to find a documents subdirectory on the mounted device.

    Falls back to the mount point root if none is found.

    Args:
        mount_point: Root path of the mounted device.

    Returns:
        Path to the documents directory.
    """
    for dirname in EREADER_DOC_DIRS:
        candidate = os.path.join(mount_point, dirname)
        if os.path.isdir(candidate):
            return candidate
    return mount_point


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_ereaders() -> list[DetectedDevice]:
    """Detect connected ebook reader devices (cross-platform).

    Returns:
        List of DetectedDevice objects for each detected reader.
    """
    system = platform.system()
    logger.debug("Detecting ebook readers on %s", system)

    if system == "Darwin":
        return _detect_macos()
    elif system == "Linux":
        return _detect_linux()
    elif system == "Windows":
        return _detect_windows()
    else:
        logger.warning("Unsupported platform for device detection: %s", system)
        return []
