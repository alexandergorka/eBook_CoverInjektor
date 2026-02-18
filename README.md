# eBook CoverInjektor

A streamlined desktop tool that adds cover art to PDF ebooks and exports them to ebook reader devices or local directories.

![Preview](img/image.png)


## Features

- **Batch PDF processing** — select one or many PDFs at once  
- **Automatic cover art search** — fetches suggestions from Google Books and Open Library APIs  
- **AI-powered cover generation** — create unique, professional cover art using OpenAI DALL-E:
  - Supports both DALL-E 2 and DALL-E 3 models
  - Generates high-resolution covers (up to 1792x1024 px)
  - Customizable prompts with intelligent defaults based on book title
  - Choose between standard and HD quality (DALL-E 3)
  - Optimized for eBook portrait format with professional typography
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
    "google_books_api_key": "YOUR_GOOGLE_BOOKS_API_KEY_HERE",
    "openai_api_key": "YOUR_OPENAI_API_KEY_HERE"
}
```

> The application works without a Google API key (Open Library needs no key), but results may be limited and rate-throttled.

### OpenAI API (required for AI cover generation)

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to **API Keys** and click **Create new secret key**
4. Copy the key and paste it into `api_keys.json` as `openai_api_key`

> DALL-E 3 image generation costs approximately $0.04–$0.08 per image depending on size and quality. See [OpenAI pricing](https://openai.com/pricing) for details.

### Security note

`api_keys.json` is stored separately from the main config. **Do not commit this file to version control.** Add it to `.gitignore`:

```
api_keys.json
```

---

## AI Cover Generation

The AI cover generator uses OpenAI's DALL-E API to create custom, professional book covers from text descriptions.

### How it works

1. Enter a book title or detailed description
2. The app generates an optimized prompt that instructs DALL-E to create:
   - A single, flat, front-facing cover design (not a book mockup)
   - Portrait orientation optimized for PDF eBooks
   - Professional typography with prominent title placement
   - High-resolution output (300 DPI equivalent)
   - Clean composition without watermarks or branding
3. You can edit the prompt to specify:
   - Visual style (minimalist, vintage, modern, etc.)
   - Color palette preferences
   - Genre-specific elements
   - Author name placement
4. Generated covers are automatically downloaded and ready to use

### Model comparison

| Feature | DALL-E 2 | DALL-E 3 |
|---------|----------|----------|
| **Speed** | Faster | Slightly slower |
| **Cost** | ~$0.02/image | ~$0.04–$0.08/image |
| **Quality** | Good | Excellent |
| **Prompt adherence** | Moderate | Very high |
| **Available sizes** | 256x256, 512x512, 1024x1024 | 1024x1024, 1024x1792, 1792x1024 |
| **HD quality** | No | Yes (additional cost) |

**Recommendation:** Use DALL-E 3 with standard quality for best results. DALL-E 2 is suitable for quick prototypes or budget-conscious projects.

### Tips for better results

- **Be specific**: Instead of "a mystery novel cover", try "a dark mystery novel cover with a foggy Victorian street at night"
- **Mention colors**: "using deep blues and gold accents" or "warm autumn color palette"
- **Specify style**: "minimalist design", "watercolor illustration", "photorealistic", "vintage book cover style"
- **Genre matters**: Include the genre to guide DALL-E toward appropriate visual conventions
- **Iterate**: If the first result isn't perfect, refine your prompt and regenerate

### Costs

DALL-E charges per image generation:
- **DALL-E 2**: ~$0.02 per 1024x1024 image
- **DALL-E 3 (standard)**: ~$0.04 per 1024x1024 or 1024x1792 image
- **DALL-E 3 (HD)**: ~$0.08 per image

See [OpenAI pricing](https://openai.com/pricing) for current rates.

---

## Usage

### Launch the application

```bash
python main.py
```

### Workflow

1. **Select PDFs** — click *Browse PDFs…* to choose one or more PDF files  
2. **Choose a cover** —  
   - **Option A: Search for existing covers**
     - The search box auto-fills from the first PDF's filename  
     - Click *Search Covers* to fetch suggestions from Google Books & Open Library  
     - Click any thumbnail to select it; a preview appears on the right  
   - **Option B: Upload your own image**
     - Switch to *Custom image file* and pick a local image  
   - **Option C: Generate AI cover art** (requires OpenAI API key)
     - Switch to *Generate AI Cover Art*
     - A descriptive prompt auto-fills based on the book title — edit it to customize the design
     - Adjust generation parameters:
       - **Model**: Choose DALL-E 2 (faster, cheaper) or DALL-E 3 (higher quality, better prompt adherence)
       - **Quality**: Standard or HD (DALL-E 3 only; HD costs more but provides enhanced detail)
       - **Size**: Select from available dimensions (1024x1024, 1024x1792, 1792x1024 for DALL-E 3)
     - Click *Generate Cover* to create your custom design (usually takes 10-30 seconds)
     - The generated cover is automatically optimized for eBook formatting:
       - Portrait orientation suitable for PDF first pages
       - Professional typography with centered title placement
       - High contrast and readability
       - Clean, full-bleed design without mockup elements
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
    "max_concurrent_downloads": 4,
    "ai_model": "dall-e-3",
    "ai_image_size": "1024x1792",
    "ai_quality": "standard"
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
| `ai_model` | Default DALL-E model: `dall-e-3` or `dall-e-2` |
| `ai_image_size` | Default image size for AI generation |
| `ai_quality` | Default quality: `standard` or `hd` (DALL-E 3 only) |

---

## Project Structure

```
eBook_CoverInjektor/
├── main.py              # Entry point — launch the app
├── gui.py               # Tkinter GUI
├── cover_fetcher.py     # Google Books + Open Library API integration
├── ai_cover_generator.py # OpenAI DALL-E cover generation
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
| AI generation fails | Ensure `openai_api_key` is set in `api_keys.json`; check your OpenAI account balance |
| tkinter not found | Install `python3-tk` via your system package manager |
| Device not detected | Ensure the reader is mounted and its volume name matches a known pattern |
| Permission denied on export | Check write permissions on the target directory |
| Large PDF slow to process | Processing time scales with page count; the progress bar tracks each file |

---

## License

MIT
