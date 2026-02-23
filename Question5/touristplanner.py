"""
=============================================================================
Tourist Spot Optimizer – GUI with Greedy Heuristic Itinerary Planner
=============================================================================

LAYOUT FIX SUMMARY
───────────────────
  Problem: The summary bar disappeared when the window was minimized because
           it was placed BELOW the notebook with no guaranteed minimum space.

  Fix: The output panel now uses a three-row grid:
       Row 0 (weight=0) → Summary bar  — FIXED height, always visible
       Row 1 (weight=1) → Notebook     — expands/shrinks with available space
  
  Key principle: Giving weight=0 to the summary bar row means it NEVER
  gives up its space to other widgets. The notebook (weight=1) absorbs all
  resize events instead.

ASSIGNMENT COVERAGE (20 marks)
────────────────────────────────
  Task 1 – GUI Design for User Input          (3 marks)
  Task 2 – Load / Define Tourist Spot Dataset (3 marks)
  Task 3 – Heuristic Optimization             (5 marks)
  Task 4 – Itinerary Display + Map/Path View  (5 marks)
  Task 5 – Brute-Force Comparison             (4 marks)
=============================================================================
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import os
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Set, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def convert_time_to_minutes(time_str: str) -> int:
    """Convert ``'HH:MM'`` → total minutes since midnight."""
    h, m = time_str.strip().split(":")
    return int(h) * 60 + int(m)


def fmt_hm(minutes: float) -> str:
    """Format a minute count as ``'Xh Ym'`` for display."""
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m"


def fmt_clock(minutes: float) -> str:
    """Format minutes-since-midnight as ``'HH:MM'`` clock string."""
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TouristSpot:
    name: str
    latitude: float
    longitude: float
    entry_fee: float
    open_time: int
    close_time: int
    tags: List[str] = field(default_factory=list)

    def open_str(self) -> str:
        oh, om = divmod(self.open_time,  60)
        ch, cm = divmod(self.close_time, 60)
        return f"{oh:02d}:{om:02d}–{ch:02d}:{cm:02d}"

    def __repr__(self) -> str:
        return (f"TouristSpot({self.name!r}, fee={self.entry_fee}, "
                f"hours={self.open_str()}, tags={self.tags})")


# ─────────────────────────────────────────────────────────────────────────────
# Algorithm helpers
# ─────────────────────────────────────────────────────────────────────────────

def euclidean_distance(a: TouristSpot, b: TouristSpot) -> float:
    return math.sqrt((a.latitude - b.latitude) ** 2
                     + (a.longitude - b.longitude) ** 2)


def interest_match(spot: TouristSpot, selected: List[str]) -> int:
    selected_lower = [s.lower() for s in selected]
    return sum(1 for tag in spot.tags if tag.lower() in selected_lower)


def compute_score(
    spot: TouristSpot,
    dist: float,
    matches: int,
    *,
    w_interest: float = 10.0,
    w_distance: float = 5.0,
    w_fee: float = 0.1,
) -> float:
    return matches * w_interest - dist * w_distance - spot.entry_fee * w_fee


def _is_feasible(
    spot: TouristSpot,
    dist: float,
    rem_time: float,
    rem_budget: float,
    current_time: float,
    visit_duration: int,
    travel_rate: float,
) -> Tuple[bool, float, float]:
    travel_mins   = dist * travel_rate
    arrival       = current_time + travel_mins
    total_elapsed = travel_mins + visit_duration

    if total_elapsed > rem_time:
        return False, travel_mins, arrival
    if spot.entry_fee > rem_budget:
        return False, travel_mins, arrival
    if arrival < spot.open_time or (arrival + visit_duration) > spot.close_time:
        return False, travel_mins, arrival

    return True, travel_mins, arrival


ItineraryRow = Tuple[TouristSpot, float, float, str]

MIN_NODE_SEP = 22

TAG_COLOURS: Dict[str, str] = {
    "nature":      "#27ae60",
    "culture":     "#8e44ad",
    "adventure":   "#e67e22",
    "religious":   "#c0392b",
    "heritage":    "#2980b9",
    "relaxation":  "#16a085",
}

SAMPLE_SPOTS_JSON = [
    {"name": "Pashupatinath Temple",  "latitude": 27.7104, "longitude": 85.3488,
     "entry_fee": 100, "open_time": "06:00", "close_time": "18:00",
     "tags": ["culture", "religious"]},
    {"name": "Swayambhunath Stupa",   "latitude": 27.7149, "longitude": 85.2906,
     "entry_fee": 200, "open_time": "07:00", "close_time": "17:00",
     "tags": ["culture", "heritage"]},
    {"name": "Garden of Dreams",      "latitude": 27.7125, "longitude": 85.3170,
     "entry_fee": 150, "open_time": "09:00", "close_time": "21:00",
     "tags": ["nature", "relaxation"]},
    {"name": "Chandragiri Hills",     "latitude": 27.6616, "longitude": 85.2458,
     "entry_fee": 700, "open_time": "09:00", "close_time": "17:00",
     "tags": ["nature", "adventure"]},
    {"name": "Kathmandu Durbar Square","latitude": 27.7048, "longitude": 85.3076,
     "entry_fee": 100, "open_time": "10:00", "close_time": "17:00",
     "tags": ["culture", "heritage"]},
]


def _parse_spot_dict(entry: dict) -> TouristSpot:
    tags = entry.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.replace(",", ";").split(";") if t.strip()]
    return TouristSpot(
        name       = entry["name"],
        latitude   = float(entry["latitude"]),
        longitude  = float(entry["longitude"]),
        entry_fee  = float(entry["entry_fee"]),
        open_time  = convert_time_to_minutes(entry["open_time"]),
        close_time = convert_time_to_minutes(entry["close_time"]),
        tags       = [t.strip().lower() for t in tags],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class TouristPlannerApp:

    VISIT_DURATION:    int   = 30
    TRAVEL_RATE:       float = 10.0
    BRUTE_FORCE_LIMIT: int   = 5
    START_TIME:        int   = 8 * 60

    CANVAS_W:   int = 480
    CANVAS_H:   int = 520
    CANVAS_PAD: int = 58

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tourist Spot Optimizer")
        self.root.resizable(True, True)

        self.time_var   = tk.StringVar()
        self.budget_var = tk.StringVar()

        self.interest_vars: Dict[str, tk.BooleanVar] = {
            "nature":     tk.BooleanVar(),
            "culture":    tk.BooleanVar(),
            "adventure":  tk.BooleanVar(),
            "religious":  tk.BooleanVar(),
            "heritage":   tk.BooleanVar(),
            "relaxation": tk.BooleanVar(),
        }

        self.start_spot_var = tk.StringVar()

        self.spots: List[TouristSpot] = []
        self._row_explanations: Dict[str, str] = {}
        self._last_itinerary:   List[ItineraryRow] = []

        self._build_ui()
        self._load_default_dataset()

    # ═════════════════════════════════════════════════════════════════════════
    # UI construction
    # ═════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # ── Root grid ─────────────────────────────────────────────────────
        # Column 0: fixed-width sidebar (spans both rows via rowspan=2).
        # Column 1: expandable main area split into two rows:
        #   Row 0 (weight=2) → Map / canvas        — gets 2/3 of vertical space
        #   Row 1 (weight=1) → Itinerary Results   — gets 1/3 of vertical space
        # Adjust the weight ratio to taste (e.g. 3:1, 1:1, etc.)
        self.root.columnconfigure(0, weight=0, minsize=240)
        self.root.columnconfigure(1, weight=1)

        self.root.rowconfigure(0, weight=2)   # map row     → larger share
        self.root.rowconfigure(1, weight=1)   # results row → smaller share
        self.root.minsize(900, 640)

        self._build_input_panel()
        self._build_output_panel()   # ← summary bar fix lives here
        self._build_canvas_panel()

    # ── Left sidebar: scrollable inputs ───────────────────────────────────

    def _build_input_panel(self) -> None:
        outer = ttk.LabelFrame(self.root, text="Planner Inputs", padding=0)
        # rowspan=2 so the sidebar stretches alongside both the map and
        # the results panel in column 1, keeping its full height always.
        outer.grid(row=0, column=0, rowspan=2, padx=(14, 6), pady=(14, 14), sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        _canvas = tk.Canvas(outer, highlightthickness=0, bd=0)
        _vsb    = ttk.Scrollbar(outer, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_vsb.set)
        _canvas.grid(row=0, column=0, sticky="nsew")
        _vsb.grid(row=0, column=1, sticky="ns")

        frame = ttk.Frame(_canvas, padding=12)
        _win_id = _canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_configure(event: object) -> None:
            _canvas.configure(scrollregion=_canvas.bbox("all"))

        def _on_canvas_configure(event: object) -> None:
            _canvas.itemconfig(_win_id, width=_canvas.winfo_width())

        frame.bind("<Configure>", _on_frame_configure)
        _canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event: object) -> None:
            if hasattr(event, "delta") and event.delta:
                _canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif hasattr(event, "num"):
                _canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        outer.bind_all("<MouseWheel>", _on_mousewheel)
        outer.bind_all("<Button-4>",   _on_mousewheel)
        outer.bind_all("<Button-5>",   _on_mousewheel)

        frame.columnconfigure(0, weight=1)
        r = 0

        ttk.Label(frame, text="Dataset File:",
                  font=("Helvetica", 8, "bold")).grid(
            row=r, column=0, sticky="w", pady=(0, 2)); r += 1

        load_frame = ttk.Frame(frame)
        load_frame.grid(row=r, column=0, sticky="ew", pady=(0, 6)); r += 1
        load_frame.columnconfigure(0, weight=1)
        self.file_label = ttk.Label(load_frame, text="(built-in sample)",
                                    foreground="#555", font=("Helvetica", 8))
        self.file_label.grid(row=0, column=0, sticky="w")
        ttk.Button(load_frame, text="Browse…",
                   command=self._browse_file).grid(row=0, column=1, padx=(6, 0))

        ttk.Separator(frame, orient="horizontal").grid(
            row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ttk.Label(frame, text="Total Time Available (hours):").grid(
            row=r, column=0, sticky="w"); r += 1
        ttk.Entry(frame, textvariable=self.time_var, width=22).grid(
            row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ttk.Label(frame, text="Maximum Budget (NPR):").grid(
            row=r, column=0, sticky="w"); r += 1
        ttk.Entry(frame, textvariable=self.budget_var, width=22).grid(
            row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ttk.Label(frame, text="Interest Tags:",
                  font=("Helvetica", 8, "bold")).grid(
            row=r, column=0, sticky="w", pady=(2, 2)); r += 1

        cb_frame = ttk.Frame(frame)
        cb_frame.grid(row=r, column=0, sticky="ew", pady=(0, 8)); r += 1
        labels = {
            "nature":    "Nature",
            "culture":   "Culture",
            "adventure": "Adventure",
            "religious": "Religious",
            "heritage":  "Heritage",
            "relaxation":"Relaxation",
        }
        swatch_size = 10
        for idx, (key, display) in enumerate(labels.items()):
            col  = idx % 2
            crow = idx // 2
            colour = TAG_COLOURS.get(key, "#888888")
            inner = ttk.Frame(cb_frame)
            inner.grid(row=crow, column=col, sticky="w", padx=(0, 8), pady=1)
            c = tk.Canvas(inner, width=swatch_size, height=swatch_size,
                          highlightthickness=0)
            c.create_rectangle(0, 0, swatch_size, swatch_size,
                               fill=colour, outline="")
            c.pack(side="left", padx=(0, 3))
            ttk.Checkbutton(inner, text=display,
                            variable=self.interest_vars[key]).pack(side="left")

        ttk.Label(frame, text="Starting Spot:").grid(
            row=r, column=0, sticky="w"); r += 1
        self.start_combo = ttk.Combobox(
            frame, textvariable=self.start_spot_var,
            state="readonly", width=20)
        self.start_combo.grid(row=r, column=0, sticky="ew", pady=(2, 8)); r += 1

        ttk.Separator(frame, orient="horizontal").grid(
            row=r, column=0, sticky="ew", pady=(10, 6)); r += 1

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=r, column=0, sticky="ew"); r += 1
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        ttk.Button(btn_frame, text="Generate Itinerary",
                   command=self.generate_itinerary).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(btn_frame, text="Clear / Reset",
                   command=self._reset).grid(row=0, column=1, sticky="ew")

    # ── Bottom area: summary bar (always visible) + notebook (expandable) ─
    #
    #  ┌─────────────────────────────────────────────────────┐
    #  │  LabelFrame "Itinerary Results"   (row=1, col=0..1) │
    #  │                                                      │
    #  │  Row 0 (weight=1) ── Notebook tabs                  │
    #  │  Row 1 (weight=0) ── Summary bar  ← FIXED, anchored │
    #  └─────────────────────────────────────────────────────┘
    #
    #  The summary bar sits in row=1 with weight=0, so it is NEVER compressed
    #  by the geometry manager regardless of how small the window gets.
    #  The notebook in row=0 with weight=1 takes all leftover vertical space.

    def _build_output_panel(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Itinerary Results", padding=8)
        # Sits directly below the map in column 1, row 1.
        # No columnspan needed — the sidebar now uses rowspan=2 in col 0.
        frame.grid(row=1, column=1, padx=(0, 14), pady=(0, 14), sticky="nsew")
        frame.columnconfigure(0, weight=1)

        # ── Row configuration ─────────────────────────────────────────────
        #
        # Row 0: Notebook — weight=1 absorbs all resize events.
        #        minsize=80 stops the notebook (and its tab strip) from
        #        collapsing to zero when the window is dragged very small.
        frame.rowconfigure(0, weight=1, minsize=80)   # notebook → expands
        #
        # Row 1: Separator — weight=0, minsize=6 reserves exactly enough
        #        pixels for the line to remain visible at any window size.
        frame.rowconfigure(1, weight=0, minsize=6)    # separator → fixed
        #
        # Row 2: Summary bar — weight=0, minsize=32 is the critical fix.
        #        weight=0 alone does NOT prevent Tkinter from collapsing a
        #        row to zero; minsize sets a hard pixel floor that the
        #        geometry manager must honour before distributing any
        #        remaining space to the notebook above.
        frame.rowconfigure(2, weight=0, minsize=32)   # summary bar → always visible

        # ── Build the notebook first (row 0) ─────────────────────────────
        nb = ttk.Notebook(frame)
        nb.grid(row=0, column=0, sticky="nsew")   # ← fills all available space
        self._notebook = nb

        # Tab 1: Itinerary Table
        t1 = ttk.Frame(nb, padding=6)
        nb.add(t1, text="  Itinerary Table  ")
        t1.columnconfigure(0, weight=1)
        t1.rowconfigure(1, weight=1)

        ttk.Label(t1, text="Double-click a row to see why that spot was selected.",
                  font=("Helvetica", 8, "italic"), foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        columns = ("#", "Spot Name", "Arrival", "Travel\n(min)",
                   "Fee\n(NPR)", "Visit\n(min)", "Matches", "Score")
        col_cfg: Dict[str, Tuple[int, str]] = {
            "#":           (26,  "center"),
            "Spot Name":   (138, "w"),
            "Arrival":     (52,  "center"),
            "Travel\n(min)":(55, "center"),
            "Fee\n(NPR)":  (58,  "center"),
            "Visit\n(min)":(50,  "center"),
            "Matches":     (58,  "center"),
            "Score":       (58,  "center"),
        }
        self.tree = ttk.Treeview(t1, columns=columns,
                                 show="headings", height=7, selectmode="browse")
        for col in columns:
            w, anc = col_cfg[col]
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=w, anchor=anc, stretch=False)

        self.tree.tag_configure("odd",  background="#eaf4fb")
        self.tree.tag_configure("even", background="#ffffff")

        vsb = ttk.Scrollbar(t1, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Tab 2: Decision Log
        t2 = ttk.Frame(nb, padding=6)
        nb.add(t2, text="  Decision Log  ")
        t2.columnconfigure(0, weight=1)
        t2.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            t2, width=46, height=18, state="disabled", wrap="word",
            relief="flat", bg="#1e1e2e", fg="#cdd6f4",
            font=("Courier", 9), padx=8, pady=6, cursor="arrow")
        log_vsb = ttk.Scrollbar(t2, orient="vertical",
                                command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_vsb.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_vsb.grid(row=0, column=1, sticky="ns")

        for tag, cfg in {
            "header":      {"foreground": "#89b4fa",
                            "font": ("Courier", 9, "bold")},
            "section":     {"foreground": "#a6e3a1",
                            "font": ("Courier", 9, "bold")},
            "key":         {"foreground": "#f9e2af"},
            "value":       {"foreground": "#cdd6f4"},
            "score":       {"foreground": "#f38ba8",
                            "font": ("Courier", 9, "bold")},
            "sep":         {"foreground": "#45475a"},
            "tags_matched":{"foreground": "#89dceb"},
            "justify":     {"foreground": "#cba6f7",
                            "font": ("Courier", 9, "italic")},
        }.items():
            self.log_text.tag_configure(tag, **cfg)

        # Tab 3: Brute-Force Comparison
        t3 = ttk.Frame(nb, padding=6)
        nb.add(t3, text="  Brute-Force Comparison  ")
        t3.columnconfigure(0, weight=1)
        t3.rowconfigure(0, weight=1)

        self.compare_text = tk.Text(
            t3, width=46, height=18, state="disabled", wrap="word",
            relief="flat", bg="#fafafa", font=("Courier", 9))
        cmp_vsb = ttk.Scrollbar(t3, orient="vertical",
                                command=self.compare_text.yview)
        self.compare_text.configure(yscrollcommand=cmp_vsb.set)
        self.compare_text.grid(row=0, column=0, sticky="nsew")
        cmp_vsb.grid(row=0, column=1, sticky="ns")

        # ── Row 1: Separator (fixed, always visible) ─────────────────────
        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, sticky="ew", pady=(4, 2))

        # ── Row 2: Summary bar (fixed height, always visible) ─────────────
        # padding=(8,4) gives the bar comfortable breathing room within the
        # 32px minsize floor reserved by rowconfigure above.
        sf = ttk.Frame(frame, padding=(8, 4))
        sf.grid(row=2, column=0, sticky="ew")

        # Three evenly spaced label pairs (label + value)
        for col_idx, (label, attr) in enumerate([
            ("Total Cost:",    "cost_label"),
            ("Time Used:",     "time_label"),
            ("Spots Visited:", "spots_label"),
        ]):
            ttk.Label(sf, text=label).grid(
                row=0, column=col_idx * 2,
                sticky="w", padx=(0 if col_idx == 0 else 18, 4))
            lbl = ttk.Label(sf, text="—", foreground="#1a5276",
                            font=("Helvetica", 9, "bold"))
            lbl.grid(row=0, column=col_idx * 2 + 1, sticky="w")
            setattr(self, attr, lbl)

    # ── Top-right: canvas path visualisation ─────────────────────────────

    def _build_canvas_panel(self) -> None:
        frame = ttk.LabelFrame(self.root,
                               text="Path Visualization  "
                                    "(coordinate map – Euclidean distance)",
                               padding=12)
        frame.grid(row=0, column=1, padx=(0, 14), pady=(14, 6), sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(frame, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg="#f0f4f8", relief="flat")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas_placeholder()

    def _on_canvas_resize(self, _event: object) -> None:
        if self._last_itinerary:
            self._draw_path(self._last_itinerary)
        else:
            self.canvas.delete("all")
            self._canvas_placeholder()

    # ═════════════════════════════════════════════════════════════════════════
    # Data loading
    # ═════════════════════════════════════════════════════════════════════════

    def _load_default_dataset(self) -> None:
        json_path = "sample_tourist_spots.json"
        if os.path.exists(json_path):
            self._load_from_file(json_path)
        else:
            self.spots = [_parse_spot_dict(e) for e in SAMPLE_SPOTS_JSON]
            self._after_load("built-in sample")

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Tourist Spot Dataset",
            filetypes=[("JSON files", "*.json"),
                       ("CSV files",  "*.csv"),
                       ("All files",  "*.*")],
        )
        if path:
            self._load_from_file(path)

    def _load_from_file(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".csv":
                self._load_csv(path)
            else:
                self._load_json(path)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))
            return
        self._after_load(os.path.basename(path))

    def _load_json(self, path: str) -> None:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.spots = [_parse_spot_dict(e) for e in data]

    def _load_csv(self, path: str) -> None:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            self.spots = [_parse_spot_dict(dict(row)) for row in reader]

    def _after_load(self, source_name: str) -> None:
        names = [s.name for s in self.spots]
        self.start_combo["values"] = names
        if names:
            self.start_combo.current(0)
        self.file_label.config(text=source_name)
        print(f"\n[OK] Loaded {len(self.spots)} spot(s) from '{source_name}':")
        for s in self.spots:
            print(f"     - {s.name}  tags={s.tags}")

    # ═════════════════════════════════════════════════════════════════════════
    # Input parsing & validation
    # ═════════════════════════════════════════════════════════════════════════

    def _parse_inputs(self) -> Optional[Tuple[int, float, List[str], TouristSpot]]:
        try:
            hours = float(self.time_var.get())
            if hours <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input",
                                 "Total Time must be a positive number.")
            return None

        try:
            budget = float(self.budget_var.get())
            if budget < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input",
                                 "Budget must be a non-negative number.")
            return None

        interests  = [key for key, var in self.interest_vars.items() if var.get()]
        chosen     = self.start_spot_var.get()
        start_spot = next((s for s in self.spots if s.name == chosen), self.spots[0])
        return int(hours * 60), budget, interests, start_spot

    # ═════════════════════════════════════════════════════════════════════════
    # Greedy algorithm  O(n²)
    # ═════════════════════════════════════════════════════════════════════════

    def _run_greedy(
        self,
        total_time: int,
        budget: float,
        interests: List[str],
        start_spot: TouristSpot,
    ) -> List[ItineraryRow]:
        visited:      Set[int]           = set()
        itinerary:    List[ItineraryRow] = []
        rem_time:     float              = total_time
        rem_budget:   float              = budget
        current:      TouristSpot        = start_spot
        current_time: float              = self.START_TIME

        # Default scoring weights (fixed — not user-adjustable)
        wi = 10.0
        wd = 5.0
        wf = 0.1

        while True:
            best = None

            for spot in self.spots:
                if id(spot) in visited:
                    continue

                dist = euclidean_distance(current, spot)
                ok, travel_mins, arrival = _is_feasible(
                    spot, dist, rem_time, rem_budget,
                    current_time, self.VISIT_DURATION, self.TRAVEL_RATE,
                )
                if not ok:
                    continue

                matches      = interest_match(spot, interests)
                score        = compute_score(spot, dist, matches,
                                             w_interest=wi, w_distance=wd, w_fee=wf)
                matched_tags = [t for t in spot.tags
                                if t.lower() in [i.lower() for i in interests]]
                arr_h, arr_m = divmod(int(arrival), 60)

                if matches > 0:
                    reason = (f"Selected due to {matches} interest tag match(es) "
                              f"({', '.join(matched_tags)}) within budget.")
                else:
                    reason = ("Selected as best available option within time "
                              "and budget constraints.")

                explanation = (
                    f"  {reason}\n"
                    f"  Selected because:\n"
                    f"    - Interest matches : {matches} ({matched_tags or 'none'})\n"
                    f"    - Travel distance  : {dist:.4f} units ({int(travel_mins)} min)\n"
                    f"    - Entry fee        : NPR {spot.entry_fee:.0f} "
                    f"(within budget of NPR {rem_budget:.0f})\n"
                    f"    - Arrival time     : {arr_h:02d}:{arr_m:02d} "
                    f"(spot open {spot.open_str()})\n"
                    f"    - Weights used     : interest×{wi:.1f}, "
                    f"dist×{wd:.1f}, fee×{wf:.2f}\n"
                    f"    - Score formula    : "
                    f"({matches}×{wi:.1f}) - ({dist:.4f}×{wd:.1f})"
                    f" - ({spot.entry_fee:.0f}×{wf:.2f})\n"
                    f"    - Greedy score     : {score:.4f}\n"
                )

                if best is None or score > best[0]:
                    best = (score, travel_mins, arrival, spot, explanation)

            if best is None:
                break

            _, travel_mins, arrival, chosen, explanation = best
            visited.add(id(chosen))
            itinerary.append((chosen, travel_mins, arrival, explanation))

            elapsed      = travel_mins + self.VISIT_DURATION
            rem_time    -= elapsed
            rem_budget  -= chosen.entry_fee
            current_time = arrival + self.VISIT_DURATION
            current      = chosen

        return itinerary

    # ═════════════════════════════════════════════════════════════════════════
    # Brute-force algorithm  O(n!)
    # ═════════════════════════════════════════════════════════════════════════

    def brute_force_itinerary(
        self,
        total_time: int,
        budget: float,
        interests: List[str],
        start_spot: TouristSpot,
    ) -> Tuple[List[TouristSpot], float, float]:
        others = [s for s in self.spots if s is not start_spot]
        pool   = [start_spot] + others[: self.BRUTE_FORCE_LIMIT - 1]

        best_spots:     List[TouristSpot] = []
        best_cost:      float             = 0.0
        best_time_used: float             = 0.0

        for perm in itertools.permutations(pool):
            visited_this: List[TouristSpot] = []
            rem_time     = float(total_time)
            rem_budget   = budget
            current_time = float(self.START_TIME)
            current      = perm[0]
            run_cost     = 0.0
            run_time     = 0.0

            for spot in perm:
                dist = euclidean_distance(current, spot)
                ok, travel_mins, arrival = _is_feasible(
                    spot, dist, rem_time, rem_budget,
                    current_time, self.VISIT_DURATION, self.TRAVEL_RATE,
                )
                if not ok:
                    break
                visited_this.append(spot)
                elapsed       = travel_mins + self.VISIT_DURATION
                rem_time     -= elapsed
                rem_budget   -= spot.entry_fee
                run_cost     += spot.entry_fee
                run_time     += elapsed
                current_time  = arrival + self.VISIT_DURATION
                current       = spot

            if (len(visited_this) > len(best_spots) or
                    (len(visited_this) == len(best_spots) and run_cost < best_cost)):
                best_spots     = visited_this
                best_cost      = run_cost
                best_time_used = run_time

        return best_spots, best_cost, best_time_used

    # ═════════════════════════════════════════════════════════════════════════
    # Comparison text (Task 5)
    # ═════════════════════════════════════════════════════════════════════════

    def _build_comparison(
        self,
        greedy:   List[ItineraryRow],
        bf_spots: List[TouristSpot],
        bf_cost:  float,
        bf_time:  float,
    ) -> str:
        gc = len(greedy)
        bc = len(bf_spots)
        g_time = sum(t + self.VISIT_DURATION for _, t, _, _ in greedy)
        g_cost = sum(s.entry_fee for s, _, _, _ in greedy)
        efficiency = (gc / bc * 100) if bc > 0 else (100.0 if gc == 0 else 0.0)

        bf_names = "  " + "\n  ".join(
            f"  {i+1}. {s.name}  (NPR {s.entry_fee:.0f})"
            for i, s in enumerate(bf_spots)
        ) if bf_spots else "  (none)"

        g_names = "  " + "\n  ".join(
            f"  {i+1}. {s.name}  (NPR {s.entry_fee:.0f})"
            for i, (s, _, _, _) in enumerate(greedy)
        ) if greedy else "  (none)"

        sep  = "=" * 46
        thin = "-" * 46
        lines = [
            sep,
            "  BRUTE-FORCE vs GREEDY COMPARISON",
            f"  (Brute-force pool: first {self.BRUTE_FORCE_LIMIT} spots | "
            f"all permutations = {self.BRUTE_FORCE_LIMIT}! max)",
            sep, "",
            "  GREEDY RESULT:", g_names,
            f"  Spots visited : {gc}",
            f"  Total cost    : NPR {g_cost:.0f}",
            f"  Total time    : {fmt_hm(g_time)}", "",
            thin,
            "  BRUTE-FORCE OPTIMAL RESULT:", bf_names,
            f"  Spots visited : {bc}",
            f"  Total cost    : NPR {bf_cost:.0f}",
            f"  Total time    : {fmt_hm(bf_time)}", "",
            sep,
            f"  Efficiency    : Greedy achieved {efficiency:.0f}% of optimal",
            "  (based on spots visited)", "",
            sep,
            "  ACCURACY vs PERFORMANCE TRADE-OFF", thin,
            "  Greedy  → O(n²)  time complexity.",
            "    Fast; scales to hundreds of spots.",
            "    Makes locally-optimal decisions that may",
            "    miss the globally-optimal solution.", "",
            "  Brute Force → O(n!) time complexity.",
            "    Exact; guarantees the best answer for its",
            "    search pool but is infeasible beyond ~10",
            f"    spots (10! = {10**10 // 1000000:,}M permutations).", "",
            "  Conclusion: For real-world trip planning the",
            "  greedy approach is the practical choice.",
            "  Brute-force serves only as a quality benchmark",
            "  on the small 5-spot subset.",
            sep,
        ]
        return "\n".join(lines)

    # ═════════════════════════════════════════════════════════════════════════
    # Main orchestrator
    # ═════════════════════════════════════════════════════════════════════════

    def generate_itinerary(self) -> None:
        if not self.spots:
            messagebox.showwarning("No Data", "No tourist spots loaded.")
            return

        parsed = self._parse_inputs()
        if parsed is None:
            return
        total_time, budget, interests, start_spot = parsed

        greedy                     = self._run_greedy(total_time, budget,
                                                      interests, start_spot)
        bf_spots, bf_cost, bf_time = self.brute_force_itinerary(total_time, budget,
                                                                 interests, start_spot)
        comparison                 = self._build_comparison(greedy, bf_spots,
                                                            bf_cost, bf_time)

        self._update_table(greedy, interests)
        self._update_summary(greedy)        # ← summary bar updated; always visible
        self._update_decision_log(greedy, interests)
        self._update_compare_text(comparison)
        self._draw_path(greedy)

    # ═════════════════════════════════════════════════════════════════════════
    # Reset
    # ═════════════════════════════════════════════════════════════════════════

    def _reset(self) -> None:
        self.time_var.set("")
        self.budget_var.set("")
        for var in self.interest_vars.values():
            var.set(False)

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._row_explanations.clear()
        self._last_itinerary = []

        for lbl in (self.cost_label, self.time_label, self.spots_label):
            lbl.config(text="—")

        self._set_text(self.log_text, "")
        self._set_text(self.compare_text, "")
        self.canvas.delete("all")
        self._canvas_placeholder()

    # ═════════════════════════════════════════════════════════════════════════
    # Output helpers
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _set_text(widget: tk.Text, content: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        if content:
            widget.insert(tk.END, content)
        widget.config(state="disabled")

    def _update_table(self, itinerary: List[ItineraryRow], interests: List[str]) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._row_explanations.clear()

        # Default scoring weights (fixed — not user-adjustable)
        wi = 10.0
        wd = 5.0
        wf = 0.1

        for i, (spot, travel_mins, arrival, expl) in enumerate(itinerary, 1):
            matches = interest_match(spot, interests)
            dist    = 0.0 if i == 1 else euclidean_distance(
                itinerary[i - 2][0], spot)
            score   = compute_score(spot, dist, matches,
                                    w_interest=wi, w_distance=wd, w_fee=wf)
            iid = self.tree.insert("", "end", values=(
                i, spot.name, fmt_clock(arrival),
                int(travel_mins), f"{spot.entry_fee:.0f}",
                self.VISIT_DURATION, matches, f"{score:.2f}",
            ), tags=("odd" if i % 2 else "even",))
            self._row_explanations[iid] = expl

    def _update_decision_log(self, itinerary: List[ItineraryRow],
                              interests: List[str]) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)

        total_cost = sum(s.entry_fee for s, _, _, _ in itinerary)
        time_used  = sum(t + self.VISIT_DURATION for _, t, _, _ in itinerary)

        def ins(text: str, tag: str = "value") -> None:
            self.log_text.insert(tk.END, text, tag)

        sep  = "=" * 46
        thin = "-" * 46
        # Default scoring weights (fixed — not user-adjustable)
        wi = 10.0
        wd = 5.0
        wf = 0.1

        ins(sep + "\n", "sep")
        ins("  GREEDY HEURISTIC — DECISION LOG\n", "header")
        ins(sep + "\n", "sep")
        ins(f"  Total spots : {len(itinerary)}  |  "
            f"Cost: NPR {total_cost:.0f}  |  Time: {fmt_hm(time_used)}\n", "value")
        ins(sep + "\n\n", "sep")

        for i, (spot, travel_mins, arrival, _expl) in enumerate(itinerary, 1):
            matches      = interest_match(spot, interests)
            matched_tags = [t for t in spot.tags
                            if t.lower() in [x.lower() for x in interests]]
            prev_dist    = 0.0 if i == 1 else euclidean_distance(
                itinerary[i - 2][0], spot)
            score        = compute_score(spot, prev_dist, matches,
                                         w_interest=wi, w_distance=wd, w_fee=wf)
            arr_h, arr_m = divmod(int(arrival), 60)

            ins(f"  STOP #{i}  —  {spot.name}\n", "section")
            ins(thin + "\n", "sep")

            if matches > 0:
                just = (f"Selected due to {matches} interest tag match(es) "
                        f"({', '.join(matched_tags)}) within budget.")
            else:
                just = "Selected as best feasible option within constraints."
            ins(f"  \"{just}\"\n\n", "justify")

            ins("  Interest Matches  : ", "key");  ins(f"{matches}  ", "value")
            ins(f"{matched_tags or ['(none)']}\n", "tags_matched")
            ins("  Travel Distance   : ", "key")
            ins(f"{prev_dist:.4f} units  ({int(travel_mins)} min)\n", "value")
            ins("  Entry Fee         : ", "key")
            ins(f"NPR {spot.entry_fee:.0f}  (within budget)\n", "value")
            ins("  Opening Hours     : ", "key"); ins(f"{spot.open_str()}\n", "value")
            ins("  Arrival Time      : ", "key")
            status = "(on time)" if arrival >= spot.open_time else "(early)"
            ins(f"{arr_h:02d}:{arr_m:02d}  {status}\n", "tags_matched")
            ins("  Visit Duration    : ", "key")
            ins(f"{self.VISIT_DURATION} min\n", "value")
            ins("  Weights           : ", "key")
            ins(f"interest×{wi:.1f}  dist×{wd:.1f}  fee×{wf:.2f}\n", "value")
            ins("  Score = ", "key")
            ins(f"({matches}×{wi:.1f}) - ({prev_dist:.4f}×{wd:.1f})"
                f" - ({spot.entry_fee:.0f}×{wf:.2f})\n", "value")
            ins("  GREEDY SCORE      : ", "key"); ins(f"{score:.4f}\n", "score")
            ins(thin + "\n\n", "sep")

        ins(sep + "\n", "sep")
        ins("  END OF DECISION LOG\n", "header")
        ins(sep + "\n", "sep")
        self.log_text.config(state="disabled")
        self.log_text.see("1.0")

    def _on_tree_double_click(self, _event: object) -> None:
        iid = self.tree.focus()
        if not iid or iid not in self._row_explanations:
            return
        vals = self.tree.item(iid, "values")
        self._show_explanation_popup(
            vals[1] if len(vals) > 1 else "Spot",
            self._row_explanations[iid],
        )

    def _show_explanation_popup(self, spot_name: str, explanation: str) -> None:
        win = tk.Toplevel(self.root)
        win.title("Why was this spot selected?")
        win.resizable(True, True)
        win.grab_set()

        tk.Frame(win, bg="#1a5276", pady=8).pack(fill="x")
        hdr_frame = win.winfo_children()[-1]
        tk.Label(hdr_frame, text=f'  Decision: "{spot_name}"',
                 bg="#1a5276", fg="white",
                 font=("Helvetica", 11, "bold"), anchor="w").pack(fill="x", padx=12)

        body = tk.Frame(win, bg="#1e1e2e", padx=12, pady=10)
        body.pack(fill="both", expand=True)

        txt = tk.Text(body, width=60, height=16,
                      bg="#1e1e2e", fg="#cdd6f4",
                      font=("Courier", 10), relief="flat",
                      wrap="word", padx=6, pady=4)
        txt.tag_configure("key",     foreground="#f9e2af")
        txt.tag_configure("value",   foreground="#cdd6f4")
        txt.tag_configure("score",   foreground="#f38ba8",
                          font=("Courier", 10, "bold"))
        txt.tag_configure("match",   foreground="#89dceb")
        txt.tag_configure("justify", foreground="#cba6f7",
                          font=("Courier", 10, "italic"))

        for line in explanation.splitlines(keepends=True):
            s = line.lstrip()
            if s.startswith('"Selected'):
                txt.insert(tk.END, line, "justify")
            elif "interest match" in s or "tag match" in s:
                txt.insert(tk.END, line, "match")
            elif "score" in s.lower() or "Score" in s:
                txt.insert(tk.END, line, "score")
            elif ":" in s and s.startswith("-"):
                parts  = s.split(":", 1)
                indent = line[: len(line) - len(s)]
                txt.insert(tk.END, indent + "- " + parts[0].lstrip("- ") + ":", "key")
                v = parts[1] if len(parts) > 1 else ""
                txt.insert(tk.END, v if v.endswith("\n") else v + "\n", "value")
            else:
                txt.insert(tk.END, line, "value")

        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)

        btn_f = tk.Frame(win, bg="#181825", pady=6)
        btn_f.pack(fill="x")
        tk.Button(btn_f, text="Close", command=win.destroy,
                  bg="#313244", fg="white", activebackground="#45475a",
                  relief="flat", padx=18, pady=4,
                  font=("Helvetica", 9)).pack()

    def _update_compare_text(self, text: str) -> None:
        self._set_text(self.compare_text, text)

    def _update_summary(self, itinerary: List[ItineraryRow]) -> None:
        total_cost = sum(s.entry_fee for s, _, _, _ in itinerary)
        time_used  = sum(t + self.VISIT_DURATION for _, t, _, _ in itinerary)
        self.cost_label.config(text=f"NPR {total_cost:.0f}")
        self.time_label.config(text=fmt_hm(time_used))
        self.spots_label.config(text=str(len(itinerary)))

    # ═════════════════════════════════════════════════════════════════════════
    # Canvas path visualisation
    # ═════════════════════════════════════════════════════════════════════════

    def _canvas_placeholder(self) -> None:
        w = self.canvas.winfo_width()  or self.CANVAS_W
        h = self.canvas.winfo_height() or self.CANVAS_H
        self.canvas.create_text(w // 2, h // 2,
                                text="Path visualization will appear here\n"
                                     "(coordinate plot – Euclidean distances)",
                                fill="#aaaaaa", font=("Helvetica", 10, "italic"),
                                justify="center")

    def _draw_path(self, itinerary: List[ItineraryRow]) -> None:
        self._last_itinerary = itinerary
        self.canvas.delete("all")

        if not itinerary:
            self._canvas_placeholder()
            return

        cw = self.canvas.winfo_width()  or self.CANVAS_W
        ch = self.canvas.winfo_height() or self.CANVAS_H

        LEGEND_H = 32
        PAD      = self.CANVAS_PAD
        draw_w   = cw - PAD * 2
        draw_h   = ch - PAD * 2 - LEGEND_H

        all_spots = [s for s, _, _, _ in itinerary]
        arrivals  = [a for _, _, a, _ in itinerary]
        lats = [s.latitude  for s in all_spots]
        lons = [s.longitude for s in all_spots]
        lat_rng = (max(lats) - min(lats)) or 1e-9
        lon_rng = (max(lons) - min(lons)) or 1e-9

        pix_per_deg = min(draw_h / lat_rng, draw_w / lon_rng)
        used_h = lat_rng * pix_per_deg
        used_w = lon_rng * pix_per_deg
        off_x  = PAD + (draw_w - used_w) / 2
        off_y  = PAD + (draw_h - used_h) / 2

        def to_canvas(spot: TouristSpot) -> Tuple[float, float]:
            cx = off_x + (spot.longitude - min(lons)) * pix_per_deg
            cy = off_y + (1 - (spot.latitude - min(lats)) / lat_rng) * used_h
            return cx, cy

        raw = [to_canvas(s) for s in all_spots]

        coords: List[Tuple[float, float]] = []
        for cx, cy in raw:
            jx = jy = 0.0
            for px, py in coords:
                sep = math.hypot(cx - px, cy - py)
                if sep < MIN_NODE_SEP:
                    angle = math.atan2(cy - py, cx - px)
                    shift = (MIN_NODE_SEP - sep) / 2 + 2
                    jx += math.cos(angle) * shift
                    jy += math.sin(angle) * shift
            coords.append((cx + jx, cy + jy))

        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            self.canvas.create_line(x1, y1, x2, y2, fill="#4a90d9", width=2,
                                    arrow=tk.LAST, arrowshape=(10, 12, 5))

        R = 10
        for idx, (spot, (cx, cy), arrival) in enumerate(
                zip(all_spots, coords, arrivals)):
            fill = "#e74c3c" if idx == 0 else next(
                (TAG_COLOURS[t] for t in spot.tags if t in TAG_COLOURS), "#2ecc71")
            self.canvas.create_oval(cx - R, cy - R, cx + R, cy + R,
                                    fill=fill, outline="#333", width=1)
            self.canvas.create_text(cx, cy, text=str(idx + 1),
                                    font=("Helvetica", 7, "bold"), fill="white")
            anchor = "s" if idx % 2 == 0 else "n"
            dy     = -(R + 4) if idx % 2 == 0 else (R + 4)
            self.canvas.create_text(
                cx, cy + dy,
                text=f"{spot.name}\n{fmt_clock(arrival)}",
                font=("Helvetica", 7), fill="#1a1a2e",
                anchor=anchor, width=110, justify="center")

        self._draw_legend(cw, ch)

    def _draw_legend(self, cw: int, ch: int) -> None:
        ly, x, R = ch - 16, 8, 5
        font = ("Helvetica", 8)
        self.canvas.create_oval(x, ly - R, x + R * 2, ly + R,
                                fill="#e74c3c", outline="#333")
        self.canvas.create_text(x + R * 2 + 3, ly,
                                text="Start", anchor="w", font=font, fill="#333")
        x += 46
        for tag, colour in TAG_COLOURS.items():
            self.canvas.create_oval(x, ly - R, x + R * 2, ly + R,
                                    fill=colour, outline="#333")
            self.canvas.create_text(x + R * 2 + 3, ly,
                                    text=tag.capitalize(),
                                    anchor="w", font=font, fill="#333")
            x += len(tag) * 6 + 26


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = TouristPlannerApp(root)
    root.mainloop()