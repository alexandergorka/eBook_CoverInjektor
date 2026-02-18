"""
gui.py – Tkinter GUI for eBook CoverInjektor.

Provides the main application window with:
- PDF file selection (single / batch)
- Cover art search results displayed as a clickable thumbnail grid
- Custom cover upload option
- Device / directory export selector
- Progress bar and status messages
"""

import json
import logging
import os
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageTk

from cover_fetcher import (
    CoverResult,
    download_image,
    download_thumbnails,
    fetch_covers,
)
from ai_cover_generator import build_default_prompt, generate_cover
from device_detector import DetectedDevice, detect_ereaders
from pdf_processor import inject_cover, export_pdf, render_first_page

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

def _load_config(path: str = "config.json") -> dict:
    """Load application configuration from JSON file."""
    defaults = {
        "api_keys_file": "api_keys.json",
        "default_export_directory": "",
        "cover_search_results": 8,
        "cover_page_size": "A4",
        "cover_dpi": 300,
        "thumbnail_size": [150, 200],
        "max_concurrent_downloads": 4,
    }
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        defaults.update(cfg)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load config from %s: %s – using defaults", path, exc)
    return defaults


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class CoverInjektorApp:
    """Main tkinter application for eBook CoverInjektor."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("eBook CoverInjektor")
        self.root.geometry("1060x860")
        self.root.minsize(900, 720)

        self.config = _load_config()
        self.pdf_paths: list[str] = []
        self.cover_results: list[CoverResult] = []
        self.selected_cover_image: Optional[Image.Image] = None
        self.selected_cover_index: Optional[int] = None
        self.custom_cover_path: Optional[str] = None
        self.detected_devices: list[DetectedDevice] = []
        self.thumbnail_refs: list[ImageTk.PhotoImage] = []  # prevent GC

        self._build_ui()
        self._refresh_devices()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct all UI widgets."""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Helvetica", 14, "bold"))
        style.configure("Status.TLabel", font=("Helvetica", 10))
        style.configure("Selected.TFrame", relief="solid", borderwidth=3)

        # ── Top: PDF selection ────────────────────────────────────────
        pdf_frame = ttk.LabelFrame(self.root, text="  1 — Select PDF Files  ",
                                   padding=10)
        pdf_frame.pack(fill="x", padx=12, pady=(10, 4))

        btn_frame = ttk.Frame(pdf_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Browse PDFs…",
                   command=self._on_browse_pdfs).pack(side="left")
        ttk.Button(btn_frame, text="Clear",
                   command=self._on_clear_pdfs).pack(side="left", padx=(8, 0))

        self.pdf_listvar = tk.StringVar(value=[])
        self.pdf_listbox = tk.Listbox(pdf_frame, listvariable=self.pdf_listvar,
                                      height=3, selectmode="extended")
        self.pdf_listbox.pack(fill="x", pady=(6, 0))

        # ── Middle: Cover selection ───────────────────────────────────
        cover_frame = ttk.LabelFrame(self.root, text="  2 — Choose Cover Art  ",
                                     padding=10)
        cover_frame.pack(fill="both", expand=True, padx=12, pady=4)

        # Source radio buttons
        source_bar = ttk.Frame(cover_frame)
        source_bar.pack(fill="x", pady=(0, 6))

        self.cover_source = tk.StringVar(value="auto")
        ttk.Radiobutton(source_bar, text="Auto-search from APIs",
                        variable=self.cover_source, value="auto",
                        command=self._on_source_changed).pack(side="left")
        ttk.Radiobutton(source_bar, text="Generate AI Cover Art",
                        variable=self.cover_source, value="ai",
                        command=self._on_source_changed).pack(side="left")
        ttk.Radiobutton(source_bar, text="Custom image file",
                        variable=self.cover_source, value="custom",
                        command=self._on_source_changed).pack(side="left", padx=(16, 0))


        # ── Horizontal container: source frames (left) + preview (right) ──
        content_area = ttk.Frame(cover_frame)
        content_area.pack(fill="both", expand=True)

        # Left side: holds the switchable source frames
        self.source_container = ttk.Frame(content_area)
        self.source_container.pack(side="left", fill="both", expand=True)

        # Cover preview (right side, always visible)
        self.preview_frame = ttk.LabelFrame(content_area, text="  Preview  ",
                                            padding=6, width=300)
        self.preview_frame.pack(side="right", fill="y", padx=(10, 0))
        self.preview_frame.pack_propagate(False)

        # PDF first-page preview
        pdf_preview_section = ttk.LabelFrame(self.preview_frame,
                                             text="  Current First Page  ",
                                             padding=4)
        pdf_preview_section.pack(fill="both", expand=True, pady=(0, 4))
        self.pdf_page_label = ttk.Label(pdf_preview_section,
                                        text="No PDF\nloaded",
                                        anchor="center", justify="center")
        self.pdf_page_label.pack(expand=True)

        # Checkbox: remove first page
        self.remove_first_page_var = tk.BooleanVar(value=False)
        self.remove_first_cb = ttk.Checkbutton(
            self.preview_frame,
            text="Remove existing first page",
            variable=self.remove_first_page_var,
        )
        self.remove_first_cb.pack(pady=(2, 6))

        # Separator
        ttk.Separator(self.preview_frame, orient="horizontal").pack(fill="x", pady=2)

        # New cover preview
        cover_preview_section = ttk.LabelFrame(self.preview_frame,
                                                text="  New Cover  ",
                                                padding=4)
        cover_preview_section.pack(fill="both", expand=True, pady=(4, 0))
        self.preview_label = ttk.Label(cover_preview_section,
                                       text="No cover\nselected",
                                       anchor="center", justify="center")
        self.preview_label.pack(expand=True)

        # ── Auto-search controls ──────────────────────────────────────
        self.auto_frame = ttk.Frame(self.source_container)
        self.auto_frame.pack(fill="both", expand=True)

        search_bar = ttk.Frame(self.auto_frame)
        search_bar.pack(fill="x")
        ttk.Label(search_bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_bar, textvariable=self.search_var,
                                      width=40)
        self.search_entry.pack(side="left", padx=(6, 8))
        self.search_entry.bind("<Return>", lambda e: self._on_search_covers())
        ttk.Button(search_bar, text="Search Covers",
                   command=self._on_search_covers).pack(side="left")

        # Scrollable thumbnail grid
        thumb_container = ttk.Frame(self.auto_frame)
        thumb_container.pack(fill="both", expand=True, pady=(8, 0))

        self.thumb_canvas = tk.Canvas(thumb_container, height=430)
        thumb_scroll = ttk.Scrollbar(thumb_container, orient="horizontal",
                                     command=self.thumb_canvas.xview)
        self.thumb_canvas.configure(xscrollcommand=thumb_scroll.set)
        thumb_scroll.pack(side="bottom", fill="x")
        self.thumb_canvas.pack(side="top", fill="both", expand=True)

        self.thumb_inner = ttk.Frame(self.thumb_canvas)
        self.thumb_canvas.create_window((0, 0), window=self.thumb_inner,
                                        anchor="nw")
        self.thumb_inner.bind("<Configure>",
                              lambda e: self.thumb_canvas.configure(
                                  scrollregion=self.thumb_canvas.bbox("all")))

        # Loading overlay (hidden by default)
        self.loading_frame = ttk.Frame(self.thumb_canvas)
        self.loading_spinner = ttk.Progressbar(self.loading_frame, length=200,
                                               mode="indeterminate")
        self.loading_spinner.pack(pady=(8, 4))
        self.loading_label = ttk.Label(self.loading_frame,
                                       text="Searching for covers…",
                                       font=("Helvetica", 10))
        self.loading_label.pack()
        self._loading_window_id: int | None = None

        # ── Custom cover controls (hidden by default) ─────────────────
        self.custom_frame = ttk.Frame(self.source_container)
        cust_bar = ttk.Frame(self.custom_frame)
        cust_bar.pack(fill="x")
        ttk.Button(cust_bar, text="Choose Image File…",
                   command=self._on_browse_custom_cover).pack(side="left")
        self.custom_label = ttk.Label(cust_bar, text="No file selected")
        self.custom_label.pack(side="left", padx=(8, 0))

        self.custom_preview_label = ttk.Label(self.custom_frame)
        self.custom_preview_label.pack(pady=(8, 0))

        # ── AI cover generation controls (hidden by default) ──────────
        self.ai_frame = ttk.Frame(self.source_container)

        ai_top_bar = ttk.Frame(self.ai_frame)
        ai_top_bar.pack(fill="x", pady=(0, 6))

        # Model selector
        ttk.Label(ai_top_bar, text="Model:").pack(side="left")
        self.ai_model_var = tk.StringVar(value="dall-e-3")
        ai_model_combo = ttk.Combobox(ai_top_bar, textvariable=self.ai_model_var,
                                       values=["dall-e-3", "dall-e-2"],
                                       width=10, state="readonly")
        ai_model_combo.pack(side="left", padx=(4, 12))

        # Quality selector (dall-e-3 only)
        ttk.Label(ai_top_bar, text="Quality:").pack(side="left")
        self.ai_quality_var = tk.StringVar(value="standard")
        ai_quality_combo = ttk.Combobox(ai_top_bar, textvariable=self.ai_quality_var,
                                         values=["standard", "hd"],
                                         width=10, state="readonly")
        ai_quality_combo.pack(side="left", padx=(4, 12))

        # Size selector
        ttk.Label(ai_top_bar, text="Size:").pack(side="left")
        self.ai_size_var = tk.StringVar(value="1024x1024")
        ai_size_combo = ttk.Combobox(ai_top_bar, textvariable=self.ai_size_var,
                                      values=["1024x1024", "1792x1024"],
                                      width=12, state="readonly")
        ai_size_combo.pack(side="left", padx=(4, 0))

        # Prompt label
        ttk.Label(self.ai_frame, text="Prompt (edit to customise):",
                  font=("Helvetica", 10)).pack(fill="x", anchor="w")

        # Editable prompt text area
        prompt_container = ttk.Frame(self.ai_frame)
        prompt_container.pack(fill="both", expand=True, pady=(4, 6))

        self.ai_prompt_text = tk.Text(prompt_container, height=6, wrap="word",
                                      font=("Helvetica", 11))
        prompt_scroll = ttk.Scrollbar(prompt_container, orient="vertical",
                                      command=self.ai_prompt_text.yview)
        self.ai_prompt_text.configure(yscrollcommand=prompt_scroll.set)
        prompt_scroll.pack(side="right", fill="y")
        self.ai_prompt_text.pack(side="left", fill="both", expand=True)

        # Generate button row
        ai_btn_bar = ttk.Frame(self.ai_frame)
        ai_btn_bar.pack(fill="x")
        self.ai_generate_btn = ttk.Button(ai_btn_bar, text="Generate Cover",
                                          command=self._on_generate_ai_cover)
        self.ai_generate_btn.pack(side="left")
        self.ai_spinner = ttk.Progressbar(ai_btn_bar, length=180,
                                          mode="indeterminate")
        self.ai_spinner.pack(side="left", padx=(12, 0))
        self.ai_status_label = ttk.Label(ai_btn_bar, text="",
                                         font=("Helvetica", 9),
                                         foreground="gray")
        self.ai_status_label.pack(side="left", padx=(8, 0))

        # ── Bottom-left: Export ───────────────────────────────────────
        export_frame = ttk.LabelFrame(self.root, text="  3 — Export  ",
                                      padding=10)
        export_frame.pack(fill="x", padx=12, pady=(4, 4))

        dest_bar = ttk.Frame(export_frame)
        dest_bar.pack(fill="x")

        ttk.Label(dest_bar, text="Destination:").pack(side="left")
        self.dest_var = tk.StringVar()
        self.dest_combo = ttk.Combobox(dest_bar, textvariable=self.dest_var,
                                       width=50, state="readonly")
        self.dest_combo.pack(side="left", padx=(6, 8))
        ttk.Button(dest_bar, text="Browse…",
                   command=self._on_browse_dest).pack(side="left")
        ttk.Button(dest_bar, text="Refresh Devices",
                   command=self._refresh_devices).pack(side="left", padx=(8, 0))

        action_bar = ttk.Frame(export_frame)
        action_bar.pack(fill="x", pady=(8, 0))
        ttk.Button(action_bar, text="Process & Export",
                   command=self._on_process).pack(side="left")

        self.progress = ttk.Progressbar(action_bar, length=300, mode="determinate")
        self.progress.pack(side="left", padx=(12, 0))

        # ── Status bar ────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                               style="Status.TLabel", relief="sunken",
                               padding=(8, 4))
        status_bar.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # PDF file selection
    # ------------------------------------------------------------------

    def _on_browse_pdfs(self) -> None:
        """Open a file dialog to select one or more PDF files."""
        paths = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if paths:
            self.pdf_paths = list(paths)
            display = [os.path.basename(p) for p in self.pdf_paths]
            self.pdf_listvar.set(display)
            self._set_status(f"Selected {len(self.pdf_paths)} PDF(s).")
            # Pre-fill search box from first filename
            if self.pdf_paths:
                from cover_fetcher import _sanitise_query
                query = _sanitise_query(self.pdf_paths[0])
                self.search_var.set(query)
                # Pre-fill AI prompt if empty
                current_prompt = self.ai_prompt_text.get("1.0", "end").strip()
                if not current_prompt:
                    self.ai_prompt_text.delete("1.0", "end")
                    self.ai_prompt_text.insert("1.0", build_default_prompt(query))
            # Render first page preview of the first PDF
            self._update_pdf_preview()

    def _on_clear_pdfs(self) -> None:
        self.pdf_paths.clear()
        self.pdf_listvar.set([])
        self.pdf_page_label.configure(image="", text="No PDF\nloaded")
        if hasattr(self.pdf_page_label, "_page_ref"):
            del self.pdf_page_label._page_ref
        self.remove_first_page_var.set(False)
        self._set_status("PDF selection cleared.")

    # ------------------------------------------------------------------
    # Cover source switching
    # ------------------------------------------------------------------

    def _on_source_changed(self) -> None:
        source = self.cover_source.get()
        # Hide all source frames
        self.auto_frame.pack_forget()
        self.custom_frame.pack_forget()
        self.ai_frame.pack_forget()
        # Show the selected one inside source_container
        if source == "auto":
            self.auto_frame.pack(in_=self.source_container, fill="both", expand=True)
        elif source == "custom":
            self.custom_frame.pack(in_=self.source_container, fill="both", expand=True)
        elif source == "ai":
            self.ai_frame.pack(in_=self.source_container, fill="both", expand=True)
            self.ai_frame.pack(fill="both", expand=True)
            # Pre-fill prompt from search/filename if empty
            current = self.ai_prompt_text.get("1.0", "end").strip()
            if not current:
                title = self.search_var.get().strip()
                if title:
                    self.ai_prompt_text.insert("1.0", build_default_prompt(title))

    # ------------------------------------------------------------------
    # Cover searching (auto)
    # ------------------------------------------------------------------

    def _on_search_covers(self) -> None:
        """Initiate an API search for cover art in a background thread."""
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Search", "Please enter a search term.")
            return

        self._set_status(f"Searching covers for '{query}'…")
        self.selected_cover_image = None
        self.selected_cover_index = None
        self._show_loading(True)

        def _worker():
            try:
                results = fetch_covers(
                    query,
                    max_results=self.config.get("cover_search_results", 8),
                    api_keys_path=self.config.get("api_keys_file", "api_keys.json"),
                )
                thumb_size = tuple(self.config.get("thumbnail_size", [300, 200]))
                download_thumbnails(
                    results, size=thumb_size,
                    max_workers=self.config.get("max_concurrent_downloads", 4),
                )
                self.root.after(0, lambda: self._display_thumbnails(results))
            except Exception as exc:
                self.root.after(0, lambda: self._show_loading(False))
                self.root.after(0, lambda: self._set_status(f"Search failed: {exc}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _display_thumbnails(self, results: list[CoverResult]) -> None:
        """Populate the thumbnail grid with search results in a 2-row layout."""
        self._show_loading(False)

        # Clear previous
        for child in self.thumb_inner.winfo_children():
            child.destroy()
        self.thumbnail_refs.clear()
        self.cover_results = results

        if not results:
            ttk.Label(self.thumb_inner, text="No covers found.").grid(
                row=0, column=0, padx=20, pady=20)
            self._set_status("No covers found.")
            return

        # Arrange in 2 rows: row 0 gets first half, row 1 gets second half
        cols = (len(results) + 1) // 2  # ceiling division
        for idx, cr in enumerate(results):
            row = idx // cols
            col = idx % cols

            frame = ttk.Frame(self.thumb_inner, padding=4)
            frame.grid(row=row, column=col, padx=4, pady=4, sticky="n")

            if cr.thumbnail_image:
                tk_img = ImageTk.PhotoImage(cr.thumbnail_image)
                self.thumbnail_refs.append(tk_img)
                lbl = tk.Label(frame, image=tk_img, cursor="hand2",
                               borderwidth=2, relief="flat")
                lbl.pack()
                lbl.bind("<Button-1>", lambda e, i=idx: self._on_thumb_click(i))
            else:
                ttk.Label(frame, text="(no image)", width=18).pack()

            # Title (truncated)
            title = (cr.title[:22] + "…") if len(cr.title) > 24 else cr.title
            ttk.Label(frame, text=title, wraplength=140,
                      font=("Helvetica", 9)).pack(pady=(2, 0))
            ttk.Label(frame, text=cr.source,
                      font=("Helvetica", 8), foreground="gray").pack()

        self._set_status(f"Found {len(results)} cover(s). Click to select.")

    def _on_thumb_click(self, index: int) -> None:
        """Handle thumbnail selection."""
        self.selected_cover_index = index
        cr = self.cover_results[index]

        # Visual feedback – highlight selected
        for i, child in enumerate(self.thumb_inner.winfo_children()):
            for sub in child.winfo_children():
                if isinstance(sub, tk.Label) and sub.cget("cursor") == "hand2":
                    sub.configure(relief="solid" if i == index else "flat",
                                  borderwidth=3 if i == index else 2)

        self._set_status(f"Selected: {cr.title} ({cr.source}). Downloading full image…")

        def _fetch_full():
            img = download_image(cr.full_url)
            if img:
                self.selected_cover_image = img
                self.root.after(0, lambda: self._show_preview(img))
                self.root.after(0, lambda: self._set_status(
                    f"Cover ready: {cr.title}"))
            else:
                self.root.after(0, lambda: self._set_status(
                    "Failed to download full cover image."))

        threading.Thread(target=_fetch_full, daemon=True).start()

    # ------------------------------------------------------------------
    # Custom cover
    # ------------------------------------------------------------------

    def _on_browse_custom_cover(self) -> None:
        path = filedialog.askopenfilename(
            title="Select cover image",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self.custom_cover_path = path
            self.custom_label.configure(text=os.path.basename(path))
            try:
                img = Image.open(path).convert("RGB")
                self.selected_cover_image = img
                self._show_preview(img)
                self._set_status(f"Custom cover loaded: {os.path.basename(path)}")
            except Exception as exc:
                messagebox.showerror("Image Error", f"Cannot open image:\n{exc}")
                self.selected_cover_image = None

    # ------------------------------------------------------------------
    # AI cover generation
    # ------------------------------------------------------------------

    def _on_generate_ai_cover(self) -> None:
        """Generate a cover image using the OpenAI DALL-E API."""
        prompt = self.ai_prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("No Prompt",
                                   "Please enter a prompt describing the cover.")
            return

        model = self.ai_model_var.get()
        size = self.ai_size_var.get()
        quality = self.ai_quality_var.get()
        api_keys_path = self.config.get("api_keys_file", "api_keys.json")

        # Disable button and show spinner
        self.ai_generate_btn.configure(state="disabled")
        self.ai_spinner.start(15)
        self.ai_status_label.configure(text="Generating… this may take a moment",
                                       foreground="gray")
        self._set_status("Generating AI cover art…")

        def _worker():
            try:
                img = generate_cover(
                    prompt=prompt,
                    api_keys_path=api_keys_path,
                    model=model,
                    size=size,
                    quality=quality,
                )
                if img:
                    self.root.after(0, lambda: self._on_ai_cover_ready(img))
                else:
                    self.root.after(0, lambda: self._on_ai_cover_error(
                        "No image returned."))
            except Exception as exc:
                self.root.after(0, lambda: self._on_ai_cover_error(str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_ai_cover_ready(self, img: Image.Image) -> None:
        """Handle a successfully generated AI cover."""
        self.ai_spinner.stop()
        self.ai_generate_btn.configure(state="normal")
        self.ai_status_label.configure(text="Cover generated!", foreground="green")
        self.selected_cover_image = img
        self._show_preview(img)
        self._set_status("AI cover generated and ready.")

    def _on_ai_cover_error(self, error_msg: str) -> None:
        """Handle an AI cover generation error."""
        self.ai_spinner.stop()
        self.ai_generate_btn.configure(state="normal")
        self.ai_status_label.configure(text="Generation failed", foreground="red")
        self._set_status(f"AI generation error: {error_msg}")
        messagebox.showerror("AI Cover Error", f"Cover generation failed:\n\n{error_msg}")

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _show_preview(self, img: Image.Image) -> None:
        """Display a preview of the selected cover image."""
        preview = img.copy()
        preview.thumbnail((170, 180), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=tk_img, text="")
        self.preview_label._preview_ref = tk_img  # prevent GC

    # ------------------------------------------------------------------
    # PDF first-page preview
    # ------------------------------------------------------------------

    def _update_pdf_preview(self) -> None:
        """Render and display the first page of the first selected PDF."""
        if not self.pdf_paths:
            return

        def _worker():
            img = render_first_page(self.pdf_paths[0], max_size=(170, 180))
            if img:
                self.root.after(0, lambda: self._show_pdf_page(img))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_pdf_page(self, img: Image.Image) -> None:
        """Display the rendered PDF first-page image."""
        tk_img = ImageTk.PhotoImage(img)
        self.pdf_page_label.configure(image=tk_img, text="")
        self.pdf_page_label._page_ref = tk_img  # prevent GC

    # ------------------------------------------------------------------
    # Loading animation
    # ------------------------------------------------------------------

    def _show_loading(self, show: bool) -> None:
        """Show or hide the loading spinner overlay on the thumbnail canvas."""
        if show:
            # Clear existing thumbnails
            for child in self.thumb_inner.winfo_children():
                child.destroy()
            self.thumbnail_refs.clear()
            # Place loading overlay centred on canvas
            self.loading_spinner.start(15)
            canvas_w = self.thumb_canvas.winfo_width()
            canvas_h = self.thumb_canvas.winfo_height()
            if canvas_w < 10:
                canvas_w = 500
            if canvas_h < 10:
                canvas_h = 400
            if self._loading_window_id is not None:
                self.thumb_canvas.delete(self._loading_window_id)
            self._loading_window_id = self.thumb_canvas.create_window(
                canvas_w // 2, canvas_h // 2,
                window=self.loading_frame, anchor="center",
            )
        else:
            self.loading_spinner.stop()
            if self._loading_window_id is not None:
                self.thumb_canvas.delete(self._loading_window_id)
                self._loading_window_id = None

    # ------------------------------------------------------------------
    # Export destination
    # ------------------------------------------------------------------

    def _refresh_devices(self) -> None:
        """Detect ebook readers and populate the destination combo."""
        self.detected_devices = detect_ereaders()
        values: list[str] = []
        for dev in self.detected_devices:
            values.append(f"📖 {dev.name} — {dev.documents_dir}  ({dev.free_space_mb:.0f} MB free)")

        default_dir = self.config.get("default_export_directory", "")
        if default_dir and os.path.isdir(default_dir):
            values.append(f"📁 Default: {default_dir}")

        self.dest_combo["values"] = values
        if values:
            self.dest_combo.current(0)
            self._set_status(f"Found {len(self.detected_devices)} device(s).")
        else:
            self._set_status("No ebook readers detected. Use Browse to set a destination.")

    def _on_browse_dest(self) -> None:
        path = filedialog.askdirectory(title="Choose export directory")
        if path:
            self.dest_var.set(path)
            self._set_status(f"Export destination: {path}")

    def _resolve_destination(self) -> Optional[str]:
        """Resolve the currently selected destination to a directory path."""
        raw = self.dest_var.get().strip()
        if not raw:
            return None

        # If user browsed a plain directory
        if os.path.isdir(raw):
            return raw

        # Check detected devices
        for dev in self.detected_devices:
            if dev.documents_dir in raw or dev.name in raw:
                return dev.documents_dir

        # Check default directory entry
        if raw.startswith("📁 Default:"):
            ddir = raw.split(":", 1)[-1].strip()
            if os.path.isdir(ddir):
                return ddir

        return None

    # ------------------------------------------------------------------
    # Processing & export
    # ------------------------------------------------------------------

    def _on_process(self) -> None:
        """Validate inputs, inject covers, and export – all in a background thread."""
        # Validation
        if not self.pdf_paths:
            messagebox.showwarning("No PDFs", "Please select at least one PDF file.")
            return

        if self.selected_cover_image is None:
            messagebox.showwarning("No Cover",
                                   "Please select or upload a cover image first.")
            return

        dest = self._resolve_destination()
        if not dest:
            messagebox.showwarning("No Destination",
                                   "Please select an export destination.")
            return

        total = len(self.pdf_paths)
        self.progress["maximum"] = total
        self.progress["value"] = 0
        remove_first = self.remove_first_page_var.get()

        def _worker():
            exported: list[str] = []
            errors: list[str] = []
            page_size = self.config.get("cover_page_size", "A4")
            dpi = self.config.get("cover_dpi", 300)

            for i, pdf_path in enumerate(self.pdf_paths):
                base = os.path.basename(pdf_path)
                self.root.after(0, lambda b=base, n=i: self._set_status(
                    f"Processing {n + 1}/{total}: {b}"))
                try:
                    # Create a temp output file
                    tmp_dir = tempfile.mkdtemp(prefix="coverinjektor_")
                    out_name = f"cover_{base}"
                    out_path = os.path.join(tmp_dir, out_name)

                    inject_cover(pdf_path, self.selected_cover_image,
                                 out_path, page_size, dpi,
                                 remove_first_page=remove_first)

                    final = export_pdf(out_path, dest, base)
                    exported.append(final)
                except Exception as exc:
                    logger.error("Error processing %s: %s", pdf_path, exc)
                    errors.append(f"{base}: {exc}")

                self.root.after(0, lambda v=i + 1: self._update_progress(v))

            # Show summary
            self.root.after(0, lambda: self._show_summary(exported, errors, dest))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, value: int) -> None:
        self.progress["value"] = value

    def _show_summary(self, exported: list[str], errors: list[str],
                      dest: str) -> None:
        """Display a summary dialog after processing."""
        msg_parts: list[str] = []
        if exported:
            msg_parts.append(f"Successfully exported {len(exported)} file(s) to:\n{dest}\n")
            for p in exported:
                msg_parts.append(f"  • {os.path.basename(p)}")
        if errors:
            msg_parts.append(f"\n{len(errors)} error(s):")
            for e in errors:
                msg_parts.append(f"  ✗ {e}")

        full_msg = "\n".join(msg_parts)
        self._set_status(
            f"Done — {len(exported)} exported, {len(errors)} error(s)."
        )

        if errors:
            messagebox.showwarning("Processing Complete", full_msg)
        else:
            messagebox.showinfo("Processing Complete", full_msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)
        logger.info("STATUS: %s", msg)
