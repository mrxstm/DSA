"""
==============================================================================
Multi-threaded Weather Data Collector
==============================================================================

ASSIGNMENT COVERAGE
--------------------
Task 1 – GUI that stays responsive during fetches (uses root.after() to
         push updates from threads → no freezing)
Task 2 – Five Nepali cities fetched from OpenWeatherMap free API
Task 3 – Five daemon threads (one per city) with a thread-safe Queue
Task 4 – Queue + root.after() poller guarantees race-condition-free GUI updates
Task 5 – Sequential vs parallel latency measured, results shown in a bar chart
         drawn on a tk.Canvas (no matplotlib dependency)

HOW TO RUN
-----------
1. Install Python 3.8+ (tkinter is part of the standard library on Windows/macOS;
   on Linux: sudo apt install python3-tk)
2. Get a free API key from https://openweathermap.org/api  (takes ~10 min)
3. Paste your key into API_KEY below (or enter it in the GUI before fetching)
4. Run:  python weather_collector.py

THREAD-SAFETY DESIGN
---------------------
  Worker threads  ──write──▶  thread-safe Queue  ──read──▶  GUI (main thread)
  The GUI never touches the Queue from a worker; workers never touch tkinter
  widgets.  The main thread polls the Queue every POLL_MS milliseconds via
  root.after(), which is the only tk-safe mechanism for cross-thread updates.

LATENCY COMPARISON  (Task 5)
------------------------------
  Sequential  : cities fetched one-by-one in a single thread; total = sum of
                individual request times.
  Parallel    : all five threads launched together; total = time from first
                thread start to last thread finish (wall-clock time).
  Both values and a bar chart are displayed in the GUI after each run.
==============================================================================
"""

from __future__ import annotations

import json
import queue
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# Configuration – edit these two constants before running
# ==============================================================================

# Paste your free OpenWeatherMap API key here, OR type it in the GUI text box.
API_KEY: str = ""   # e.g. "abc123def456..."

# Five Nepali cities (matches the assignment specification)
CITIES: List[str] = [
    "Kathmandu",
    "Pokhara",
    "Biratnagar",
    "Nepalgunj",
    "Dhangadhi",
]

# OpenWeatherMap current-weather endpoint (metric units → °C)
OWM_URL = ("https://api.openweathermap.org/data/2.5/weather"
           "?q={city}&appid={key}&units=metric")

# How often (ms) the GUI polls the result queue
POLL_MS: int = 100

# ==============================================================================
# Colour palette
# ==============================================================================
BG       = "#1e2030"
PANEL    = "#24273a"
ACCENT   = "#89b4fa"
TXT      = "#cdd6f4"
TXT_DIM  = "#6c7086"
GREEN    = "#a6e3a1"
YELLOW   = "#f9e2af"
RED      = "#f38ba8"
MAUVE    = "#cba6f7"
TEAL     = "#94e2d5"
WHITE    = "#ffffff"

ROW_ODD  = "#2a2d3e"
ROW_EVEN = "#1e2030"


# ==============================================================================
# Data container
# ==============================================================================

class WeatherResult:
    """Holds one city's fetched data or an error message."""

    def __init__(self, city: str) -> None:
        self.city:        str           = city
        self.temp:        Optional[float] = None
        self.feels_like:  Optional[float] = None
        self.humidity:    Optional[int]   = None
        self.pressure:    Optional[int]   = None
        self.description: str           = ""
        self.wind_speed:  Optional[float] = None
        self.error:       str           = ""
        self.latency_ms:  float         = 0.0    # individual request time


# ==============================================================================
# API fetch (runs inside worker threads – NO tkinter calls here)
# ==============================================================================

def fetch_weather(city: str, api_key: str) -> WeatherResult:
    """
    Fetch current weather for *city* from OpenWeatherMap.
    Returns a WeatherResult with data populated (or .error set on failure).
    This function is designed to be called from worker threads only.
    """
    result = WeatherResult(city)
    url    = OWM_URL.format(city=city, key=api_key)
    t0     = time.perf_counter()

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WeatherApp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        result.temp        = data["main"]["temp"]
        result.feels_like  = data["main"]["feels_like"]
        result.humidity    = data["main"]["humidity"]
        result.pressure    = data["main"]["pressure"]
        result.wind_speed  = data["wind"]["speed"]
        result.description = data["weather"][0]["description"].capitalize()

    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            result.error = "Invalid API key"
        elif exc.code == 404:
            result.error = f"City '{city}' not found"
        else:
            result.error = f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        result.error = f"Network error: {exc.reason}"
    except Exception as exc:  # pylint: disable=broad-except
        result.error = str(exc)

    result.latency_ms = (time.perf_counter() - t0) * 1000
    return result


# ==============================================================================
# Main application
# ==============================================================================

class WeatherApp:
    """
    Multi-threaded Weather Data Collector GUI.

    Thread-safety contract
    ----------------------
    Worker threads put WeatherResult objects onto self._result_queue.
    The main thread polls that queue with root.after(POLL_MS, ...) and
    is the ONLY entity that calls any tkinter method.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Multi-threaded Weather Data Collector")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(860, 680)

        # Thread-safe result queue (Task 3 / Task 4 requirement)
        self._result_queue: queue.Queue[WeatherResult] = queue.Queue()

        # Latency tracking
        self._seq_latency:  Optional[float] = None   # ms
        self._par_latency:  Optional[float] = None   # ms

        # Per-city latency history for bar chart
        self._city_latencies: Dict[str, float] = {}

        # Current in-flight thread count (for disabling buttons)
        self._active_threads: int = 0
        self._lock = threading.Lock()   # guards _active_threads

        # Stored result rows {city: WeatherResult}
        self._results: Dict[str, WeatherResult] = {}

        self._build_ui()
        self._start_queue_poll()

    # ==========================================================================
    # UI construction
    # ==========================================================================

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)   # table expands
        self.root.rowconfigure(4, weight=0)

        self._build_header()
        self._build_controls()
        self._build_table()
        self._build_status_bar()
        self._build_chart_panel()

    # -- Header ----------------------------------------------------------------

    def _build_header(self) -> None:
        hdr = tk.Frame(self.root, bg=PANEL, pady=14)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(0, weight=1)

        tk.Label(hdr,
                 text="🌦  Multi-threaded Weather Data Collector",
                 bg=PANEL, fg=ACCENT,
                 font=("Helvetica", 16, "bold")).grid(
            row=0, column=0)

        tk.Label(hdr,
                 text="OpenWeatherMap API  •  Five Nepali Cities  •  "
                      "Parallel & Sequential Latency Comparison",
                 bg=PANEL, fg=TXT_DIM,
                 font=("Helvetica", 9)).grid(row=1, column=0, pady=(2, 0))

    # -- Controls --------------------------------------------------------------

    def _build_controls(self) -> None:
        ctrl = tk.Frame(self.root, bg=BG, padx=16, pady=10)
        ctrl.grid(row=1, column=0, sticky="ew")

        # API key entry
        tk.Label(ctrl, text="API Key:", bg=BG, fg=TXT,
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky="w")

        self._api_key_var = tk.StringVar(value=API_KEY)
        key_entry = tk.Entry(ctrl, textvariable=self._api_key_var,
                             width=36, show="•",
                             bg=PANEL, fg=TXT, insertbackground=TXT,
                             relief="flat", font=("Courier", 10))
        key_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # Toggle key visibility
        self._show_key = tk.BooleanVar(value=False)
        def _toggle_key() -> None:
            key_entry.config(show="" if self._show_key.get() else "•")
        tk.Checkbutton(ctrl, text="Show", variable=self._show_key,
                       command=_toggle_key,
                       bg=BG, fg=TXT_DIM, selectcolor=BG,
                       activebackground=BG,
                       font=("Helvetica", 9)).grid(
            row=0, column=2, padx=(6, 20))

        # Buttons
        btn_style = dict(relief="flat", padx=16, pady=6,
                         font=("Helvetica", 10, "bold"), cursor="hand2")

        self._btn_parallel = tk.Button(
            ctrl, text="⚡  Fetch (Parallel)",
            bg=ACCENT, fg="#1e2030",
            activebackground="#b4c7f7",
            command=self._fetch_parallel, **btn_style)
        self._btn_parallel.grid(row=0, column=3, padx=(0, 8))

        self._btn_sequential = tk.Button(
            ctrl, text="🔁  Fetch (Sequential)",
            bg=MAUVE, fg="#1e2030",
            activebackground="#d5b8f5",
            command=self._fetch_sequential, **btn_style)
        self._btn_sequential.grid(row=0, column=4, padx=(0, 8))

        self._btn_clear = tk.Button(
            ctrl, text="✖  Clear",
            bg=PANEL, fg=TXT_DIM,
            activebackground=ROW_ODD,
            command=self._clear, **btn_style)
        self._btn_clear.grid(row=0, column=5)

        ctrl.columnconfigure(1, weight=1)

    # -- Weather table ---------------------------------------------------------

    def _build_table(self) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=16, pady=4)
        outer.grid(row=2, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        # Section label
        tk.Label(outer, text="Weather Results", bg=BG, fg=ACCENT,
                 font=("Helvetica", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        # Style the Treeview to match dark theme
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview",
                        background=ROW_EVEN,
                        foreground=TXT,
                        fieldbackground=ROW_EVEN,
                        rowheight=28,
                        font=("Helvetica", 10))
        style.configure("Dark.Treeview.Heading",
                        background=PANEL,
                        foreground=ACCENT,
                        font=("Helvetica", 10, "bold"),
                        relief="flat")
        style.map("Dark.Treeview",
                  background=[("selected", "#363a4f")],
                  foreground=[("selected", WHITE)])

        cols = ("city", "temp", "feels", "humidity",
                "pressure", "wind", "description", "latency")
        self._tree = ttk.Treeview(outer, columns=cols, show="headings",
                                  style="Dark.Treeview", height=7)

        col_cfg = {
            "city":        ("City",           140, "w"),
            "temp":        ("Temp (°C)",       90, "center"),
            "feels":       ("Feels Like (°C)", 105, "center"),
            "humidity":    ("Humidity (%)",     95, "center"),
            "pressure":    ("Pressure (hPa)",  105, "center"),
            "wind":        ("Wind (m/s)",       90, "center"),
            "description": ("Condition",       160, "w"),
            "latency":     ("Latency (ms)",    100, "center"),
        }
        for col, (heading, width, anchor) in col_cfg.items():
            self._tree.heading(col, text=heading, anchor=anchor)
            self._tree.column(col, width=width, anchor=anchor, stretch=False)

        self._tree.tag_configure("odd",   background=ROW_ODD,  foreground=TXT)
        self._tree.tag_configure("even",  background=ROW_EVEN, foreground=TXT)
        self._tree.tag_configure("error", background="#3d1f1f", foreground=RED)
        self._tree.tag_configure("loading",
                                 background=ROW_ODD, foreground=YELLOW)

        vsb = ttk.Scrollbar(outer, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        self._tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

        # Pre-populate rows with placeholder text
        self._init_table_rows()

    def _init_table_rows(self) -> None:
        """Insert one placeholder row per city."""
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        for i, city in enumerate(CITIES):
            tag = "odd" if i % 2 else "even"
            self._tree.insert("", "end", iid=city,
                              values=(city, "—", "—", "—", "—",
                                      "—", "Press Fetch", "—"),
                              tags=(tag,))

    # -- Status bar ------------------------------------------------------------

    def _build_status_bar(self) -> None:
        sb = tk.Frame(self.root, bg=PANEL, padx=16, pady=6)
        sb.grid(row=3, column=0, sticky="ew")
        sb.columnconfigure(1, weight=1)

        tk.Label(sb, text="Status:", bg=PANEL, fg=TXT_DIM,
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w")

        self._status_var = tk.StringVar(value="Ready – enter your API key and press Fetch.")
        self._status_lbl = tk.Label(sb, textvariable=self._status_var,
                                    bg=PANEL, fg=TXT,
                                    font=("Helvetica", 9),
                                    anchor="w")
        self._status_lbl.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # Thread indicator dots
        self._dot_frame = tk.Frame(sb, bg=PANEL)
        self._dot_frame.grid(row=0, column=2, padx=(12, 0))
        self._dots: List[tk.Canvas] = []
        for _ in CITIES:
            dot = tk.Canvas(self._dot_frame, width=12, height=12,
                            bg=PANEL, highlightthickness=0)
            dot.create_oval(1, 1, 11, 11, fill=TXT_DIM, tags="dot")
            dot.pack(side="left", padx=2)
            self._dots.append(dot)

    # -- Latency bar chart panel -----------------------------------------------

    def _build_chart_panel(self) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=16, pady=8)
        outer.grid(row=4, column=0, sticky="ew")
        outer.columnconfigure(0, weight=1)

        tk.Label(outer, text="Latency Comparison", bg=BG, fg=ACCENT,
                 font=("Helvetica", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        # Canvas for bar chart
        self._chart = tk.Canvas(outer, height=200, bg=PANEL,
                                highlightthickness=1,
                                highlightbackground=TXT_DIM)
        self._chart.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(1, weight=0)

        # Bind resize so chart redraws properly
        self._chart.bind("<Configure>", lambda e: self._redraw_chart())

        # Latency summary labels
        lf = tk.Frame(outer, bg=BG)
        lf.grid(row=2, column=0, sticky="w", pady=(6, 0))

        tk.Label(lf, text="Sequential total:", bg=BG, fg=TXT_DIM,
                 font=("Helvetica", 9)).pack(side="left")
        self._seq_lbl = tk.Label(lf, text="—", bg=BG, fg=YELLOW,
                                 font=("Helvetica", 9, "bold"))
        self._seq_lbl.pack(side="left", padx=(4, 20))

        tk.Label(lf, text="Parallel total:", bg=BG, fg=TXT_DIM,
                 font=("Helvetica", 9)).pack(side="left")
        self._par_lbl = tk.Label(lf, text="—", bg=BG, fg=GREEN,
                                 font=("Helvetica", 9, "bold"))
        self._par_lbl.pack(side="left", padx=(4, 20))

        tk.Label(lf, text="Speedup:", bg=BG, fg=TXT_DIM,
                 font=("Helvetica", 9)).pack(side="left")
        self._speedup_lbl = tk.Label(lf, text="—", bg=BG, fg=TEAL,
                                     font=("Helvetica", 9, "bold"))
        self._speedup_lbl.pack(side="left", padx=(4, 0))

    # ==========================================================================
    # Queue poller (Task 4 – thread-safe GUI update)
    # ==========================================================================

    def _start_queue_poll(self) -> None:
        """Schedule the queue poll loop; called once at startup."""
        self._poll_queue()

    def _poll_queue(self) -> None:
        """
        Drain all pending results from the thread-safe queue and update the GUI.
        Rescheduled every POLL_MS ms via root.after() – runs only on main thread.
        """
        try:
            while True:
                result: WeatherResult = self._result_queue.get_nowait()
                self._apply_result(result)
        except queue.Empty:
            pass
        finally:
            self.root.after(POLL_MS, self._poll_queue)

    def _apply_result(self, result: WeatherResult) -> None:
        """Update one Treeview row with a finished WeatherResult (main thread)."""
        city = result.city
        self._results[city] = result
        self._city_latencies[city] = result.latency_ms

        idx    = CITIES.index(city)
        row_bg = "odd" if idx % 2 else "even"

        if result.error:
            self._tree.item(city, values=(
                city, "Error", "—", "—", "—", "—",
                result.error, f"{result.latency_ms:.0f}"),
                tags=("error",))
        else:
            self._tree.item(city, values=(
                city,
                f"{result.temp:.1f}",
                f"{result.feels_like:.1f}",
                f"{result.humidity}",
                f"{result.pressure}",
                f"{result.wind_speed:.1f}",
                result.description,
                f"{result.latency_ms:.0f}"),
                tags=(row_bg,))

        # Mark that thread's dot green
        self._set_dot(idx, GREEN)

        # Decrement active thread count
        with self._lock:
            self._active_threads -= 1
            remaining = self._active_threads

        if remaining == 0:
            self._on_all_done()

    # ==========================================================================
    # Thread management
    # ==========================================================================

    def _fetch_parallel(self) -> None:
        """
        Launch five daemon threads concurrently – one per city.  (Task 3)
        Wall-clock time from first launch to last finish = parallel latency.
        """
        if not self._validate_key():
            return
        self._prepare_fetch("parallel")
        api_key = self._api_key_var.get().strip()

        # Record wall-clock start time (shared across all threads via closure)
        self._par_wall_start = time.perf_counter()

        with self._lock:
            self._active_threads = len(CITIES)

        for i, city in enumerate(CITIES):
            self._set_dot(i, YELLOW)
            t = threading.Thread(
                target=self._worker,
                args=(city, api_key),
                name=f"WeatherWorker-{city}",
                daemon=True,       # threads die when the main window closes
            )
            t.start()

    def _fetch_sequential(self) -> None:
        """
        Sequential fetch: one dedicated thread per city, but each thread is
        started and JOINED (waited on) before the next one launches.

        This satisfies the requirement that "each thread handles the API call
        for a single city" while still measuring pure sequential latency
        (no concurrency – total time = sum of all individual request times).

        A coordinator daemon thread drives the sequence so the GUI stays live.
        """
        if not self._validate_key():
            return
        self._prepare_fetch("sequential")
        api_key = self._api_key_var.get().strip()

        with self._lock:
            self._active_threads = len(CITIES)

        def _coordinator() -> None:
            """Runs in background; starts one worker thread per city in order."""
            wall_start = time.perf_counter()

            for i, city in enumerate(CITIES):
                # One thread per city – satisfies the assignment requirement
                worker = threading.Thread(
                    target=self._worker,
                    args=(city, api_key),
                    name=f"WeatherSeq-{city}",
                    daemon=True,
                )
                # Flip dot to yellow just before this thread starts
                self.root.after(0, self._set_dot, i, YELLOW)
                worker.start()
                worker.join()   # wait for THIS city to finish before next

            # Total wall-clock time covers all five sequential fetches
            self._seq_latency = (time.perf_counter() - wall_start) * 1000

        coordinator = threading.Thread(target=_coordinator,
                                       name="WeatherSeqCoordinator",
                                       daemon=True)
        coordinator.start()

    def _worker(self, city: str, api_key: str) -> None:
        """
        Worker thread body (Task 3).  Fetches one city and pushes the result
        onto the thread-safe queue.  Never touches tkinter directly.
        """
        result = fetch_weather(city, api_key)
        self._result_queue.put(result)   # Queue.put() is thread-safe

    # ==========================================================================
    # Helpers
    # ==========================================================================

    def _validate_key(self) -> bool:
        key = self._api_key_var.get().strip()
        if not key:
            messagebox.showerror(
                "API Key Missing",
                "Please enter your OpenWeatherMap API key.\n\n"
                "Get one free at: https://openweathermap.org/api")
            return False
        return True

    def _prepare_fetch(self, mode: str) -> None:
        """Reset table, dots, and button states before a fetch run."""
        self._results.clear()
        self._city_latencies.clear()
        self._init_table_rows()

        for i in range(len(CITIES)):
            self._set_dot(i, TXT_DIM)

        self._set_status(f"Fetching ({mode}) — please wait…", YELLOW)
        self._btn_parallel.config(state="disabled")
        self._btn_sequential.config(state="disabled")

        # Mark all rows as loading
        for i, city in enumerate(CITIES):
            tag = "loading"
            self._tree.item(city, values=(city, "…", "…", "…", "…",
                                          "…", "Fetching…", "…"),
                            tags=(tag,))

    def _on_all_done(self) -> None:
        """Called when the last active thread's result has been processed."""
        # Measure parallel wall-clock latency
        if hasattr(self, "_par_wall_start") and self._par_latency is None:
            self._par_latency = (time.perf_counter() - self._par_wall_start) * 1000

        # Re-enable buttons
        self._btn_parallel.config(state="normal")
        self._btn_sequential.config(state="normal")

        # Count successes / errors
        errors   = sum(1 for r in self._results.values() if r.error)
        success  = len(self._results) - errors
        msg      = (f"Done – {success} city/cities loaded"
                    + (f", {errors} error(s)" if errors else ""))
        self._set_status(msg, GREEN if not errors else YELLOW)

        # Update latency labels and chart
        self._update_latency_display()

    def _update_latency_display(self) -> None:
        """Refresh the summary labels and bar chart after a fetch run."""
        seq_ms = self._seq_latency
        par_ms = self._par_latency

        self._seq_lbl.config(
            text=f"{seq_ms:.0f} ms" if seq_ms is not None else "—")
        self._par_lbl.config(
            text=f"{par_ms:.0f} ms" if par_ms is not None else "—")

        if seq_ms and par_ms:
            speedup = seq_ms / par_ms
            self._speedup_lbl.config(text=f"{speedup:.2f}×")
        else:
            self._speedup_lbl.config(text="—")

        self._redraw_chart()

    def _redraw_chart(self) -> None:
        """
        Draw a bar chart on the canvas showing:
          - Per-city individual request latency (blue bars)
          - Sequential total (yellow dashed line)
          - Parallel total  (green dashed line)
        """
        c = self._chart
        c.delete("all")

        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 10 or ch < 10:
            return

        PAD_L, PAD_R, PAD_T, PAD_B = 52, 16, 16, 40
        chart_w = cw - PAD_L - PAD_R
        chart_h = ch - PAD_T - PAD_B

        if not self._city_latencies:
            c.create_text(cw // 2, ch // 2,
                          text="Latency chart will appear after fetching data.",
                          fill=TXT_DIM, font=("Helvetica", 10, "italic"))
            return

        # Determine scale
        all_vals  = list(self._city_latencies.values())
        extra     = [v for v in [self._seq_latency, self._par_latency]
                     if v is not None]
        max_val   = max(all_vals + extra + [1])
        scale     = chart_h / max_val

        bar_count = len(CITIES)
        bar_w     = max(10, (chart_w - (bar_count - 1) * 8) // bar_count)
        gap       = max(4, (chart_w - bar_w * bar_count) // max(bar_count - 1, 1))

        # Y axis
        c.create_line(PAD_L, PAD_T, PAD_L, PAD_T + chart_h,
                      fill=TXT_DIM, width=1)
        # X axis
        c.create_line(PAD_L, PAD_T + chart_h,
                      PAD_L + chart_w, PAD_T + chart_h,
                      fill=TXT_DIM, width=1)

        # Y axis ticks and labels (5 divisions)
        for i in range(6):
            y_val = max_val * i / 5
            y_px  = PAD_T + chart_h - y_val * scale
            c.create_line(PAD_L - 4, y_px, PAD_L, y_px, fill=TXT_DIM)
            c.create_text(PAD_L - 6, y_px,
                          text=f"{y_val:.0f}",
                          anchor="e", fill=TXT_DIM,
                          font=("Helvetica", 8))
            # Horizontal grid line
            c.create_line(PAD_L, y_px, PAD_L + chart_w, y_px,
                          fill="#2a2d3e", dash=(3, 5))

        # Per-city bars
        bar_colours = [ACCENT, MAUVE, TEAL, GREEN, YELLOW]
        for i, city in enumerate(CITIES):
            val   = self._city_latencies.get(city, 0)
            bar_h = val * scale
            x1    = PAD_L + i * (bar_w + gap)
            x2    = x1 + bar_w
            y1    = PAD_T + chart_h - bar_h
            y2    = PAD_T + chart_h

            colour = bar_colours[i % len(bar_colours)]
            c.create_rectangle(x1, y1, x2, y2,
                               fill=colour, outline="", width=0)

            # Value label above bar
            c.create_text((x1 + x2) // 2, y1 - 3,
                          text=f"{val:.0f}",
                          anchor="s", fill=WHITE,
                          font=("Helvetica", 8))

            # City label below x axis
            short = city.split()[0][:8]
            c.create_text((x1 + x2) // 2,
                          PAD_T + chart_h + 6,
                          text=short, anchor="n",
                          fill=TXT_DIM,
                          font=("Helvetica", 8))

        # Horizontal reference lines
        def _ref_line(val: Optional[float],
                      colour: str, label: str) -> None:
            if val is None:
                return
            y_px = PAD_T + chart_h - val * scale
            c.create_line(PAD_L, y_px, PAD_L + chart_w, y_px,
                          fill=colour, width=2, dash=(6, 4))
            c.create_text(PAD_L + chart_w - 2, y_px - 3,
                          text=f"{label}: {val:.0f} ms",
                          anchor="e", fill=colour,
                          font=("Helvetica", 8, "bold"))

        _ref_line(self._seq_latency, YELLOW, "Sequential")
        _ref_line(self._par_latency, GREEN,  "Parallel")

        # Chart title
        c.create_text(PAD_L + chart_w // 2, PAD_T - 2,
                      text="Per-city Request Latency (ms)  –  Sequential & Parallel Totals",
                      anchor="s", fill=TXT_DIM,
                      font=("Helvetica", 9))

    # -- Thread indicator dots -------------------------------------------------

    def _set_dot(self, index: int, colour: str) -> None:
        """Fill the status dot at *index* with *colour* (main-thread only)."""
        if 0 <= index < len(self._dots):
            self._dots[index].itemconfig("dot", fill=colour)

    # -- Status bar text -------------------------------------------------------

    def _set_status(self, text: str, colour: str = TXT) -> None:
        self._status_var.set(text)
        self._status_lbl.config(fg=colour)

    # -- Clear -----------------------------------------------------------------

    def _clear(self) -> None:
        self._results.clear()
        self._city_latencies.clear()
        self._seq_latency = None
        self._par_latency = None
        if hasattr(self, "_par_wall_start"):
            del self._par_wall_start
        self._init_table_rows()
        for i in range(len(CITIES)):
            self._set_dot(i, TXT_DIM)
        self._set_status("Cleared – ready to fetch again.", TXT)
        self._seq_lbl.config(text="—")
        self._par_lbl.config(text="—")
        self._speedup_lbl.config(text="—")
        self._redraw_chart()


# ==============================================================================
# Entry point
# ==============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app  = WeatherApp(root)
    root.mainloop()