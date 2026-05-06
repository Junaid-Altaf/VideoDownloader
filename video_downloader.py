"""
Social Media Video Downloader
Supports: YouTube, Facebook, Instagram, TikTok, Twitter/X, Vimeo, and 1000+ sites via yt-dlp

SECURITY: Downloads ONLY happen when the user explicitly clicks "Download Video"
with a valid URL manually pasted into the URL box. No automatic, background,
or batch downloading of any kind.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import re
import webbrowser
import urllib.parse
from pathlib import Path
import yt_dlp

# ── Strict URL validation ────────────────────────────────────────────────────
PLACEHOLDER = "https://www.youtube.com/watch?v=..."

def is_valid_url(url: str) -> bool:
    """Return True only if url looks like a real http/https web address."""
    url = url.strip()
    pattern = re.compile(
        r'^https?://'                      # must start with http:// or https://
        r'([\w\-]+\.)+[\w\-]{2,}'         # domain
        r'(/[\w\-._~:/?#\[\]@!$&\'()*+,;=%]*)?$',  # optional path/query
        re.IGNORECASE
    )
    return bool(pattern.match(url)) and url != PLACEHOLDER


# ─────────────────────────── Colour / Style constants ───────────────────────
BG_DARK       = "#1a1a2e"
BG_CARD       = "#16213e"
BG_INPUT      = "#0f3460"
ACCENT        = "#e94560"
ACCENT_HOVER  = "#c73652"
TEXT_PRIMARY  = "#eaeaea"
TEXT_MUTED    = "#a0a0b0"
SUCCESS       = "#4caf50"
WARNING       = "#ff9800"
BORDER        = "#2a2a4a"
FONT_TITLE    = ("Segoe UI", 22, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)
FONT_BODY     = ("Segoe UI", 10)
FONT_SMALL    = ("Segoe UI", 9)
FONT_MONO     = ("Consolas", 9)


# ─────────────────────────── Helper widgets ─────────────────────────────────
class HoverButton(tk.Button):
    def __init__(self, master, bg_normal, bg_hover, **kwargs):
        super().__init__(master, bg=bg_normal, activebackground=bg_hover, **kwargs)
        self._bg_normal = bg_normal
        self._bg_hover  = bg_hover
        self.bind("<Enter>", lambda e: self.config(bg=bg_hover))
        self.bind("<Leave>", lambda e: self.config(bg=bg_normal))


class TooltipLabel(tk.Label):
    """Label that shows a tooltip on hover."""
    def __init__(self, master, tooltip_text="", **kwargs):
        super().__init__(master, **kwargs)
        self._tip_text = tooltip_text
        self._tip_win  = None
        self.bind("<Enter>", self._show)
        self.bind("<Leave>", self._hide)

    def _show(self, _=None):
        x = self.winfo_rootx() + 20
        y = self.winfo_rooty() + 20
        self._tip_win = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._tip_text, bg="#ffffe0", relief="solid",
                 borderwidth=1, font=FONT_SMALL, padx=6, pady=3).pack()

    def _hide(self, _=None):
        if self._tip_win:
            self._tip_win.destroy()
            self._tip_win = None


# ─────────────────────────── Main Application ───────────────────────────────
class VideoDownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._configure_root()
        self._init_state()
        self._build_ui()

    # ── window setup ──────────────────────────────────────────────────────
    def _configure_root(self):
        self.root.title("Social Media Video Downloader")
        self.root.geometry("820x720")
        self.root.minsize(700, 600)
        self.root.configure(bg=BG_DARK)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _init_state(self):
        self.download_folder = str(Path.home() / "Downloads")
        self.is_downloading  = False
        self.video_info      = None
        self._user_pasted    = False   # True only after user manually pastes/types a URL

        # tkinter variables
        self.url_var       = tk.StringVar()
        self.format_var    = tk.StringVar(value="Best Quality (Video+Audio)")
        self.progress_var  = tk.DoubleVar(value=0)
        self.status_var    = tk.StringVar(value="Paste a video URL above to begin")
        self.speed_var     = tk.StringVar(value="")
        self.eta_var       = tk.StringVar(value="")
        self.filename_var  = tk.StringVar(value="")

    # ── full UI build ──────────────────────────────────────────────────────
    def _build_ui(self):
        # ── header ──
        header = tk.Frame(self.root, bg=BG_DARK, pady=18)
        header.pack(fill="x")

        tk.Label(header, text="Video Downloader", font=FONT_TITLE,
                 bg=BG_DARK, fg=ACCENT).pack()
        tk.Label(header,
                 text="YouTube  •  Facebook  •  Instagram  •  TikTok  •  Twitter/X  •  Vimeo  •  1000+ sites",
                 font=FONT_SUBTITLE, bg=BG_DARK, fg=TEXT_MUTED).pack(pady=(2, 0))

        # ── scrollable main canvas ──
        canvas_frame = tk.Frame(self.root, bg=BG_DARK)
        canvas_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        canvas = tk.Canvas(canvas_frame, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=BG_DARK)
        self.scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        sf = self.scroll_frame   # shorthand

        self._build_url_section(sf)
        self._build_options_section(sf)
        self._build_folder_section(sf)
        self._build_action_buttons(sf)
        self._build_progress_section(sf)
        self._build_info_section(sf)
        self._build_history_section(sf)
        self._build_share_section(sf)
        self._build_footer()

    # ── card helper ───────────────────────────────────────────────────────
    def _card(self, parent, title=""):
        outer = tk.Frame(parent, bg=BG_DARK, pady=6)
        outer.pack(fill="x")
        card = tk.Frame(outer, bg=BG_CARD, bd=0, relief="flat",
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", ipady=10, ipadx=14)
        if title:
            tk.Label(card, text=title, font=("Segoe UI", 10, "bold"),
                     bg=BG_CARD, fg=ACCENT).pack(anchor="w", pady=(6, 4))
        return card

    # ── URL section ───────────────────────────────────────────────────────
    def _build_url_section(self, parent):
        card = self._card(parent, "Paste Video URL")

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x", pady=4)

        self.url_entry = tk.Entry(row, textvariable=self.url_var,
                                  font=FONT_BODY, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                  insertbackground=TEXT_PRIMARY, relief="flat",
                                  bd=0, highlightthickness=1,
                                  highlightbackground=BORDER,
                                  highlightcolor=ACCENT)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.url_entry.insert(0, PLACEHOLDER)
        self.url_entry.bind("<FocusIn>",  self._clear_placeholder)
        self.url_entry.bind("<FocusOut>", self._restore_placeholder)
        # Validate URL on every keystroke — enable/disable Download button live
        self.url_var.trace_add("write", self._on_url_change)

        self.fetch_btn = HoverButton(row, ACCENT, ACCENT_HOVER,
                    text="Fetch Info", font=FONT_BODY, fg="white",
                    relief="flat", bd=0, padx=14, pady=8, cursor="hand2",
                    state="disabled",
                    command=self._fetch_info)
        self.fetch_btn.pack(side="left")

        # supported sites note
        tk.Label(card,
                 text="Supported: YouTube, Facebook, Instagram, TikTok, Twitter/X, Vimeo, Dailymotion & 1000+ more",
                 font=FONT_SMALL, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(2, 6))

    def _clear_placeholder(self, _):
        if self.url_var.get() == PLACEHOLDER:
            self.url_entry.delete(0, "end")
            self.url_entry.config(fg=TEXT_PRIMARY)

    def _restore_placeholder(self, _):
        if not self.url_var.get().strip():
            self.url_entry.insert(0, PLACEHOLDER)
            self.url_entry.config(fg=TEXT_MUTED)

    def _on_url_change(self, *_):
        """Enable Download & Fetch buttons only when a valid URL is present."""
        url = self.url_var.get().strip()
        valid = is_valid_url(url)
        state = "normal" if valid else "disabled"
        if hasattr(self, "download_btn") and not self.is_downloading:
            self.download_btn.config(state=state)
        if hasattr(self, "fetch_btn"):
            self.fetch_btn.config(state=state)

    # ── options section ───────────────────────────────────────────────────
    def _build_options_section(self, parent):
        card = self._card(parent, "Download Options")

        formats = [
            "Best Quality (Video+Audio)",
            "1080p MP4",
            "720p MP4",
            "480p MP4",
            "360p MP4",
            "Audio Only (MP3)",
            "Audio Only (M4A)",
        ]

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Format:", font=FONT_BODY, bg=BG_CARD,
                 fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.TCombobox",
                         fieldbackground=BG_INPUT, background=BG_INPUT,
                         foreground=TEXT_PRIMARY, selectbackground=ACCENT,
                         selectforeground="white", borderwidth=0)

        self.format_combo = ttk.Combobox(row, textvariable=self.format_var,
                                          values=formats, state="readonly",
                                          style="Custom.TCombobox",
                                          font=FONT_BODY, width=30)
        self.format_combo.pack(side="left", ipady=5)

    # ── folder section ────────────────────────────────────────────────────
    def _build_folder_section(self, parent):
        card = self._card(parent, "Save Location")

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x", pady=4)

        self.folder_label = tk.Label(row, text=self.download_folder,
                                     font=FONT_SMALL, bg=BG_INPUT, fg=TEXT_MUTED,
                                     anchor="w", relief="flat", bd=0,
                                     highlightthickness=1, highlightbackground=BORDER)
        self.folder_label.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        HoverButton(row, BG_INPUT, BORDER,
                    text="Browse", font=FONT_BODY, fg=TEXT_PRIMARY,
                    relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
                    command=self._browse_folder).pack(side="left")

        HoverButton(row, BG_INPUT, BORDER,
                    text="Open Folder", font=FONT_BODY, fg=TEXT_PRIMARY,
                    relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
                    command=self._open_folder).pack(side="left", padx=(6, 0))

    # ── action buttons ────────────────────────────────────────────────────
    def _build_action_buttons(self, parent):
        row = tk.Frame(parent, bg=BG_DARK, pady=6)
        row.pack(fill="x")

        self.download_btn = HoverButton(row, ACCENT, ACCENT_HOVER,
                                         text="  Download Video  ",
                                         font=("Segoe UI", 12, "bold"),
                                         fg="white", relief="flat", bd=0,
                                         padx=24, pady=12, cursor="hand2",
                                         state="disabled",
                                         command=self._start_download)
        self.download_btn.pack(side="left", padx=(0, 8))

        HoverButton(row, BG_CARD, BORDER,
                    text="Clear", font=FONT_BODY, fg=TEXT_MUTED,
                    relief="flat", bd=0, padx=18, pady=12, cursor="hand2",
                    command=self._clear_all).pack(side="left")

        # filename display
        tk.Label(row, textvariable=self.filename_var,
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                 wraplength=350, anchor="w").pack(side="left", padx=10)

    # ── progress section ──────────────────────────────────────────────────
    def _build_progress_section(self, parent):
        card = self._card(parent, "Progress")

        style = ttk.Style()
        style.configure("Red.Horizontal.TProgressbar",
                         troughcolor=BG_INPUT, background=ACCENT,
                         borderwidth=0, thickness=14)

        self.progress_bar = ttk.Progressbar(card, variable=self.progress_var,
                                             maximum=100, length=100,
                                             style="Red.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(4, 6))

        stats = tk.Frame(card, bg=BG_CARD)
        stats.pack(fill="x")
        tk.Label(stats, textvariable=self.status_var,
                 font=FONT_BODY, bg=BG_CARD, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(stats, textvariable=self.speed_var,
                 font=FONT_SMALL, bg=BG_CARD, fg=SUCCESS).pack(side="right", padx=(6, 0))
        tk.Label(stats, textvariable=self.eta_var,
                 font=FONT_SMALL, bg=BG_CARD, fg=WARNING).pack(side="right")

    # ── video info section ────────────────────────────────────────────────
    def _build_info_section(self, parent):
        card = self._card(parent, "Video Information")
        self.info_text = tk.Text(card, height=5, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                  font=FONT_MONO, relief="flat", bd=0,
                                  wrap="word", state="disabled",
                                  selectbackground=ACCENT)
        self.info_text.pack(fill="x", pady=4)

    # ── download history ──────────────────────────────────────────────────
    def _build_history_section(self, parent):
        card = self._card(parent, "Download History")

        top = tk.Frame(card, bg=BG_CARD)
        top.pack(fill="x")
        tk.Label(top, text="Recent downloads", font=FONT_SMALL,
                 bg=BG_CARD, fg=TEXT_MUTED).pack(side="left")
        HoverButton(top, BG_CARD, BORDER,
                    text="Clear History", font=FONT_SMALL, fg=TEXT_MUTED,
                    relief="flat", bd=0, padx=8, pady=2, cursor="hand2",
                    command=self._clear_history).pack(side="right")

        self.history_list = tk.Listbox(card, height=4, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                        font=FONT_SMALL, relief="flat", bd=0,
                                        selectbackground=ACCENT, activestyle="none",
                                        highlightthickness=0)
        self.history_list.pack(fill="x", pady=(4, 2))
        self.history_list.bind("<Double-Button-1>", self._open_history_item)

        tk.Label(card, text="Double-click an entry to open it",
                 font=FONT_SMALL, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w")

    # ── share section ─────────────────────────────────────────────────────
    def _build_share_section(self, parent):
        card = self._card(parent, "Share")
        tk.Label(card,
                 text="After downloading, share the video file or its original link on any platform:",
                 font=FONT_SMALL, bg=BG_CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(card, bg=BG_CARD)
        btn_row.pack(fill="x")

        share_buttons = [
            ("LinkedIn",   "#0077b5", "#005f8d", self._share_linkedin),
            ("Twitter/X",  "#1da1f2", "#0d8dd4", self._share_twitter),
            ("WhatsApp",   "#25d366", "#1aaa52", self._share_whatsapp),
            ("Facebook",   "#1877f2", "#0d65d9", self._share_facebook),
            ("Copy Link",  BG_INPUT,  BORDER,    self._copy_link),
        ]
        for label, bg, hover, cmd in share_buttons:
            HoverButton(btn_row, bg, hover,
                        text=label, font=FONT_SMALL, fg="white",
                        relief="flat", bd=0, padx=12, pady=7, cursor="hand2",
                        command=cmd).pack(side="left", padx=(0, 6), pady=4)

    # ── footer ────────────────────────────────────────────────────────────
    def _build_footer(self):
        footer = tk.Frame(self.root, bg=BG_DARK, pady=6)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer,
                 text="Powered by yt-dlp  •  Supports 1000+ platforms  •  For personal use only",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack()

    # ══════════════════════════════════════════════════════════════════════
    #  Logic
    # ══════════════════════════════════════════════════════════════════════

    def _get_url(self) -> str:
        """Return the URL only if it passes strict validation, else empty string."""
        url = self.url_var.get().strip()
        return url if is_valid_url(url) else ""

    # ── fetch video metadata ───────────────────────────────────────────────
    def _fetch_info(self):
        url = self._get_url()
        if not url:
            messagebox.showwarning("No URL", "Please paste a video URL first.")
            return
        self.status_var.set("Fetching video info...")
        threading.Thread(target=self._fetch_info_thread, args=(url,), daemon=True).start()

    def _fetch_info_thread(self, url):
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            self.video_info = info
            self.root.after(0, self._display_info, info)
        except Exception as exc:
            self.root.after(0, self.status_var.set, f"Error: {exc}")

    def _display_info(self, info):
        title    = info.get("title", "Unknown")
        uploader = info.get("uploader", "Unknown")
        duration = info.get("duration")
        views    = info.get("view_count")
        site     = info.get("extractor_key", "Unknown")

        dur_str  = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "N/A"
        view_str = f"{views:,}" if views else "N/A"

        text = (f"Title    : {title}\n"
                f"Uploader : {uploader}\n"
                f"Platform : {site}\n"
                f"Duration : {dur_str}\n"
                f"Views    : {view_str}")

        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", text)
        self.info_text.config(state="disabled")
        self.status_var.set(f"Ready — {title[:60]}")

    # ── download ───────────────────────────────────────────────────────────
    def _start_download(self):
        url = self._get_url()
        if not url:
            messagebox.showwarning("Invalid URL",
                "Please paste a valid video URL (must start with http:// or https://).")
            return
        if self.is_downloading:
            messagebox.showinfo("Busy", "A download is already in progress.")
            return

        # ── Explicit user confirmation before ANY download starts ──
        confirmed = messagebox.askyesno(
            "Confirm Download",
            f"You are about to download:\n\n{url}\n\n"
            f"Format: {self.format_var.get()}\n"
            f"Save to: {self.download_folder}\n\n"
            "Proceed?"
        )
        if not confirmed:
            return

        self.is_downloading = True
        self.progress_var.set(0)
        self.download_btn.config(state="disabled", text="  Downloading...  ")
        threading.Thread(target=self._download_thread, args=(url,), daemon=True).start()

    def _build_ydl_opts(self) -> dict:
        fmt_map = {
            "Best Quality (Video+Audio)": "bestvideo+bestaudio/best",
            "1080p MP4":   "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            "720p MP4":    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "480p MP4":    "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
            "360p MP4":    "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
            "Audio Only (MP3)": "bestaudio/best",
            "Audio Only (M4A)": "bestaudio[ext=m4a]/bestaudio",
        }
        selected = self.format_var.get()
        fmt      = fmt_map.get(selected, "bestvideo+bestaudio/best")

        opts = {
            "format":   fmt,
            "outtmpl":  os.path.join(self.download_folder, "%(title)s.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "quiet":    True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }

        if "MP3" in selected:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]

        return opts

    def _download_thread(self, url):
        try:
            with yt_dlp.YoutubeDL(self._build_ydl_opts()) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            self.root.after(0, self._download_complete, filename)
        except Exception as exc:
            self.root.after(0, self._download_error, str(exc))

    def _progress_hook(self, d):
        if d["status"] == "downloading":
            total     = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded= d.get("downloaded_bytes", 0)
            pct       = (downloaded / total * 100) if total else 0
            speed     = d.get("speed")
            eta       = d.get("eta")
            speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else ""
            eta_str   = f"ETA: {eta}s" if eta else ""
            fname     = d.get("filename", "")

            self.root.after(0, self.progress_var.set, pct)
            self.root.after(0, self.status_var.set, f"Downloading… {pct:.1f}%")
            self.root.after(0, self.speed_var.set, speed_str)
            self.root.after(0, self.eta_var.set, eta_str)
            self.root.after(0, self.filename_var.set, os.path.basename(fname)[:50])
        elif d["status"] == "finished":
            self.root.after(0, self.status_var.set, "Processing file…")

    def _download_complete(self, filename):
        self.is_downloading = False
        self.progress_var.set(100)
        self.status_var.set("Download complete!")
        self.speed_var.set("")
        self.eta_var.set("")
        # Re-enable only if there's still a valid URL in the box
        self._on_url_change()
        self.download_btn.config(text="  Download Video  ")
        short = os.path.basename(filename)
        self.history_list.insert(0, short)
        if self.history_list.size() > 20:
            self.history_list.delete(20, "end")
        messagebox.showinfo("Done", f"Downloaded successfully:\n\n{short}\n\nSaved to:\n{self.download_folder}")

    def _download_error(self, msg):
        self.is_downloading = False
        self.progress_var.set(0)
        self.status_var.set("Download failed.")
        self._on_url_change()
        self.download_btn.config(text="  Download Video  ")
        messagebox.showerror("Download Error", f"Failed to download:\n\n{msg}")

    # ── folder helpers ─────────────────────────────────────────────────────
    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.folder_label.config(text=folder)

    def _open_folder(self):
        os.startfile(self.download_folder)

    # ── history helpers ────────────────────────────────────────────────────
    def _open_history_item(self, _):
        sel = self.history_list.curselection()
        if not sel:
            return
        name = self.history_list.get(sel[0])
        path = os.path.join(self.download_folder, name)
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("Not Found", f"File not found:\n{path}")

    def _clear_history(self):
        self.history_list.delete(0, "end")

    # ── clear all ──────────────────────────────────────────────────────────
    def _clear_all(self):
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, PLACEHOLDER)
        self.url_entry.config(fg=TEXT_MUTED)
        self.progress_var.set(0)
        self.status_var.set("Paste a video URL above to begin")
        self.speed_var.set("")
        self.eta_var.set("")
        self.filename_var.set("")
        self.video_info = None
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.config(state="disabled")
        # Disable buttons since URL box is now empty
        self.download_btn.config(state="disabled")
        self.fetch_btn.config(state="disabled")

    # ── share helpers ──────────────────────────────────────────────────────
    def _current_url(self) -> str:
        url = self._get_url()
        return url if url else "https://example.com"

    def _share_linkedin(self):
        url   = urllib.parse.quote(self._current_url(), safe="")
        share = f"https://www.linkedin.com/sharing/share-offsite/?url={url}"
        webbrowser.open(share)

    def _share_twitter(self):
        url   = urllib.parse.quote(self._current_url(), safe="")
        title = ""
        if self.video_info:
            title = urllib.parse.quote(self.video_info.get("title", "")[:100], safe="")
        share = f"https://twitter.com/intent/tweet?url={url}&text={title}"
        webbrowser.open(share)

    def _share_whatsapp(self):
        url   = urllib.parse.quote(self._current_url(), safe="")
        share = f"https://api.whatsapp.com/send?text={url}"
        webbrowser.open(share)

    def _share_facebook(self):
        url   = urllib.parse.quote(self._current_url(), safe="")
        share = f"https://www.facebook.com/sharer/sharer.php?u={url}"
        webbrowser.open(share)

    def _copy_link(self):
        url = self._current_url()
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo("Copied", "Link copied to clipboard!")


# ─────────────────────────── Entry point ────────────────────────────────────
def main():
    root = tk.Tk()

    # dark title bar on Windows 10/11
    try:
        from ctypes import windll, byref, sizeof, c_int
        HWND = windll.user32.GetParent(root.winfo_id())
        windll.dwmapi.DwmSetWindowAttribute(HWND, 20, byref(c_int(1)), sizeof(c_int))
    except Exception:
        pass

    app = VideoDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
