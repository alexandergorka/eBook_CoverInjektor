# eBook CoverInjektor

A streamlined desktop tool that adds cover art to PDF ebooks and exports them to ebook reader devices or local directories.

![Preview](img/image.png)


## Features

- **Batch PDF processing** — select one or many PDFs at once  
- **Automatic cover art search** — fetches suggestions from Google Books and Open Library APIs  
- **Custom cover upload** — use your own image file instead  
- **Smart device detection** — auto-detects Kindle, Kobo, PocketBook, and other mounted ebook readers (macOS, Linux, Windows)  
- **Safe export** — checks free space, write permissions, and provides full-path confirmation  
- **Simple tkinter GUI** — no browser or external runtime required  

---

## Installation

### 1. Clone / download the project

```bash
cd /path/to/eBook_CoverInjektor
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
| Package | Purpose |
|---------|---------|
| `pypdf` | PDF reading & writing |
| `Pillow` | Image loading & manipulation |
| `reportlab` | Cover page PDF generation |
| `requests` | API HTTP requests |
| `tkinter` | GUI (ships with Python on most platforms) |

> **Note:** tkinter is part of the Python standard library. If it is missing on Linux, install with:  
> `sudo apt install python3-tk` (Debian/Ubuntu) or  
> `sudo dnf install python3-tkinter` (Fedora)

---

## API Setup

Cover art suggestions are fetched from **Google Books** and **Open Library**.

### Google Books API (optional but recommended)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services → Library**
4. Search for **Books API** and enable it
5. Go to **APIs & Services → Credentials** and click **Create Credentials → API Key**
6. Copy the API key

### Configure the API key

Edit `api_keys.json` in the project root:

```json
{
    "google_books_api_key": "YOUR_GOOGLE_BOOKS_API_KEY_HERE"
}
```

> The application works without a Google API key (Open Library needs no key), but results may be limited and rate-throttled.

### Security note

`api_keys.json` is stored separately from the main config. **Do not commit this file to version control.** Add it to `.gitignore`:

```
api_keys.json
```

---

## Usage

### Launch the application

```bash
python main.py
```

### Workflow

1. **Select PDFs** — click *Browse PDFs…* to choose one or more PDF files  
2. **Choose a cover** —  
   - The search box auto-fills from the first PDF's filename  
   - Click *Search Covers* to fetch suggestions from Google Books & Open Library  
   - Click any thumbnail to select it; a preview appears on the right  
   - Or switch to *Custom image file* and pick a local image  
3. **Set destination** —  
   - Connected ebook readers are auto-detected and listed  
   - Click *Browse…* to choose any local directory  
   - Click *Refresh Devices* to re-scan for readers  
4. **Export** — click *Process & Export*  
   - A progress bar tracks batch operations  
   - A summary dialog shows exported paths or any errors  

---

## Configuration

Edit `config.json` to change defaults:

```json
{
    "api_keys_file": "api_keys.json",
    "default_export_directory": "",
    "cover_search_results": 8,
    "cover_page_size": "A4",
    "cover_dpi": 300,
    "log_level": "INFO",
    "log_file": "ebook_coverinjektor.log",
    "thumbnail_size": [150, 200],
    "max_concurrent_downloads": 4
}
```

| Setting | Description |
|---------|-------------|
| `api_keys_file` | Path to the API keys JSON file |
| `default_export_directory` | Pre-filled export path (leave empty to use device detection) |
| `cover_search_results` | Max number of cover suggestions to fetch |
| `cover_page_size` | Page format for the cover — `A4` or `LETTER` |
| `cover_dpi` | DPI hint for cover image rendering |
| `log_level` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `log_file` | Log file path (empty string to disable file logging) |
| `thumbnail_size` | `[width, height]` in pixels for thumbnail display |
| `max_concurrent_downloads` | Parallel thumbnail download threads |

---

## Project Structure

```
eBook_CoverInjektor/
├── main.py              # Entry point — launch the app
├── gui.py               # Tkinter GUI
├── cover_fetcher.py     # Google Books + Open Library API integration
├── pdf_processor.py     # Cover injection & PDF export
├── device_detector.py   # Cross-platform ebook reader detection
├── config.json          # Application settings
├── api_keys.json        # API keys (DO NOT commit)
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

---

## Supported Ebook Readers

The device detector looks for mounted volumes matching these names:

- **Kindle** (Amazon)
- **Kobo** (Rakuten)
- **PocketBook**
- **Nook** (Barnes & Noble)
- **Tolino**
- **Onyx Boox**
- **reMarkable**
- **Sony Reader**

Detection works on:
- **macOS** — scans `/Volumes/`
- **Linux** — scans `/media/<user>/` and `/mnt/`
- **Windows** — scans drive letters via volume labels

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No covers found | Check your internet connection; try a simpler search term |
| Google API errors | Verify the key in `api_keys.json`; check your API quota |
| tkinter not found | Install `python3-tk` via your system package manager |
| Device not detected | Ensure the reader is mounted and its volume name matches a known pattern |
| Permission denied on export | Check write permissions on the target directory |
| Large PDF slow to process | Processing time scales with page count; the progress bar tracks each file |

---

## License

MIT
