#!/usr/bin/env python3
"""
eBook CoverInjektor – Main entry point.

A streamlined tool that adds cover art to PDF ebooks and exports
them to ebook reader devices or local directories.

Usage:
    python main.py
"""

import json
import logging
import os
import sys
import tkinter as tk
from pathlib import Path


def _setup_logging(config: dict) -> None:
    """Configure application-wide logging.

    Args:
        config: Application configuration dictionary.
    """
    log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    log_file = config.get("log_file", "ebook_coverinjektor.log")

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def _load_config() -> dict:
    """Load config.json from the application directory."""
    config_path = Path(__file__).parent / "config.json"
    defaults = {
        "api_keys_file": "api_keys.json",
        "log_level": "INFO",
        "log_file": "ebook_coverinjektor.log",
    }
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        defaults.update(cfg)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Warning: Could not load config.json: {exc}")
    return defaults


def _check_dependencies() -> None:
    """Verify that required packages are installed."""
    missing: list[str] = []
    for pkg, import_name in [("pypdf", "pypdf"), ("Pillow", "PIL"),
                              ("reportlab", "reportlab"), ("requests", "requests")]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        print("=" * 56)
        print("  Missing dependencies: " + ", ".join(missing))
        print("  Install with:  pip install -r requirements.txt")
        print("=" * 56)
        sys.exit(1)


def main() -> None:
    """Launch the eBook CoverInjektor application."""
    # Ensure working directory is the script's directory
    os.chdir(Path(__file__).parent)

    _check_dependencies()

    config = _load_config()
    _setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("Starting eBook CoverInjektor")

    # Import GUI after logging is configured
    from gui import CoverInjektorApp

    root = tk.Tk()

    # Set application icon (if available)
    try:
        icon_path = Path(__file__).parent / "icon.png"
        if icon_path.exists():
            icon = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon)
    except Exception:
        pass

    app = CoverInjektorApp(root)
    root.mainloop()

    logger.info("Application closed.")


if __name__ == "__main__":
    main()
