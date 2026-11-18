"""
Aplikasi Tkinter Interaktif: Firefly Algorithm untuk Penjadwalan 4 Tugas pada 1 Mesin.
100% Pure Python + Tkinter (tanpa dependensi library eksternal).

Jalankan:
    python app_tkinter.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple

from firefly_scheduler import (
    WORK_END,
    WORK_START,
    Firefly,
    FireflyJobScheduler,
    JobSchedulingProblem,
    format_hour,
)


PARAM_HELP: Dict[str, Tuple[str, str]] = {
    "n_fireflies": (
        "Jumlah Firefly (N) — Ukuran Populasi Base Position",
        "• Memengaruhi: banyaknya variasi jadwal awal (Base Position) yang disebar pada iterasi 0.\n"
        "• N BESAR (25–40): peluang langsung mendapat kombinasi jam awal bagus makin besar, konvergensi lebih mantap.\n"
        "• N KECIL (6–10): lebih cepat per iterasi, namun pilihan awal sempit sehingga lebih mudah terjebak bentrok.",
    ),
    "beta0": (
        "β₀ (Base Attractiveness) — Daya Tarik Maksimum saat r = 0",
        "• Rumus: β(r) = β₀ · e^(-γ·r²).\n"
        "• Memengaruhi: seberapa kuat jadwal yang masih bentrok tertarik meniru jadwal lebih baik (EKSPLOITASI).\n"
        "• β₀ BESAR (1.0–1.5): balok tugas cepat bergeser mengikuti jadwal terbaik.\n"
        "• β₀ KECIL (0.1–0.2): tarikan sangat lemah, konvergensi lambat.",
    ),
    "gamma": (
        "γ (Light Absorption) — Redaman Cahaya terhadap Jarak",
        "• Rumus: β(r) = β₀ · e^(-γ·r²).\n"
        "• Memengaruhi: radius pandang kunang-kunang (Global vs Lokal).\n"
        "• γ KECIL (0.1–0.5): cahaya terlihat jauh → semua kunang-kunang tertarik ke Best Global.\n"
        "• γ BESAR (6.0–12.0): cahaya cepat redup oleh jarak → β mengecil drastis, interaksi jadi sangat lokal.",
    ),
    "alpha": (
        "α (Random Step / Randomization) — Skala Langkah Acak",
        "• Rumus: t_baru = t_lama + β(t_j - t_i) + α·(rand-0.5)·span.\n"
        "• Memengaruhi: kemampuan EKSPLORASI untuk keluar dari local optimum.\n"
        "• α KECIL (0.01–0.05): mudah mentok/terjebak di jadwal yang masih sedikit overlap atau telat.\n"
        "• α BESAR (0.75–1.0): jadwal melompat liar, rata-rata penalti populasi tinggi dan sulit stabil.",
    ),
    "alpha_decay": (
        "α Decay — Peluruhan Langkah Acak tiap Iterasi",
        "• Rumus: α(t+1) = max(0.02, α(t) × decay).\n"
        "• Memengaruhi: transisi dari eksplorasi luas (awal) ke penyempurnaan halus / fine-tuning (akhir).\n"
        "• Mendekati 1.00: eksplorasi lama aktif; lebih kecil (0.90–0.94): kawanan cepat tenang.",
    ),
    "max_iter": (
        "Max Iterasi (Steps) — Batas Langkah Simulasi",
        "• Menentukan jumlah langkah maksimal dalam mode Run.\n"
        "• Mode Run otomatis berhenti lebih cepat apabila Best Penalty sudah mencapai 0.00 (Jadwal Optimal).",
    ),
    "seed": (
        "Random Seed — Penentu Base Position Awal",
        "• Menjaga posisi awal (iterasi 0) tetap identik agar perbandingan efek β₀, γ, dan α adil dan terukur.",
    ),
}

GUIDE_TEXT = r"""======================================================================
  FIREFLY ALGORITHM — PENJADWALAN 4 TUGAS PADA 1 MESIN (OPSI 2)
======================================================================

1. RINGKASAN KASUS (MUDAH DIJELASKAN!)
   Satu mesin/server beroperasi pada jam 08:00 – 17:00 (9,0 jam) untuk
   menyelesaikan 4 tugas produksi (total durasi 7,5 jam):
   • T1 — Pemotongan Rangka  : durasi 2,0 jam | ready 08:00 | deadline 12:00
   • T2 — Perakitan Komponen : durasi 1,5 jam | ready 08:00 | deadline 13:30
   • T3 — Kalibrasi & Uji    : durasi 2,5 jam | ready 09:00 | deadline 16:00
   • T4 — Finishing & Packing: durasi 1,5 jam | ready 10:00 | deadline 17:00

   Hanya 2 Aturan Penalti (Target = 0,00):
   1) Overlap (Bentrok Mesin): bobot 10,0 per jam tumpang tindih.
   2) Lateness (Telat)       : bobot  6,0 per jam melewati deadline.

   Total Penalti :  f(x) = 10,0 · Overlap + 6,0 · Lateness
   Kecerahan (I) :  I(x) = 1 / (1 + f(x))
                    (Penalti = 0 → I = 1,0000 = Paling Terang!)

----------------------------------------------------------------------
2. BASE POSITION (x_i) — LANGSUNG BERUPA 4 JAM MULAI!
----------------------------------------------------------------------
   • Setiap kunang-kunang (firefly) hanya memiliki 4 angka kontinu:
       x_i = [t_T1,  t_T2,  t_T3,  t_T4]
     yang LANGSUNG adalah jam mulai tugas T1, T2, T3, dan T4!
   • Pada iterasi 0, ke-N kunang-kunang disebar acak → inilah BASE POSITION.
   • Ngefek ke mana?
     Menentukan titik awal penjadwalan & seberapa parah bentrok di awal.
     Lihat Tab 2 untuk membandingkan jam mulai Base Position (t=0)
     vs jam mulai Current Position (t sekarang).

----------------------------------------------------------------------
3. ATTRACTIVENESS (β) — DAYA TARIK ANTAR KUNANG-KUNANG
----------------------------------------------------------------------
   • Rumus:  β(r) = β₀ · exp(-γ · r²)
     dengan r = jarak Euclidean ternormalisasi antara jadwal i dan j.
   • Kunang-kunang redup (banyak bentrok/telat) SELALU tertarik menuju
     kunang-kunang yang lebih terang (lebih rapi).
   • Efek parameter:
     - β₀ besar → tarikan kuat (eksploitasi cepat); β₀ kecil → lambat.
     - γ kecil  → cahaya menembus jauh (pencarian global).
     - γ besar  → cahaya cepat redup oleh jarak (interaksi sangat lokal).

----------------------------------------------------------------------
4. STEPS / MOVEMENT (Δx) — PERGESERAN BALOK JADWAL TIAP ITERASI
----------------------------------------------------------------------
   • Rumus update jam mulai tiap iterasi:
       t_baru = t_lama + β(r)·(t_j - t_i) + α · (rand - 0,5) · span
                         \______________/   \_____________________/
                          Attraction Step        Random Step
                           (Eksploitasi)         (Eksplorasi)
   • Efek α (Random Step):
     - α terlalu kecil (0,01) → kehilangan eksplorasi, mudah mentok di
       local optimum (penalti > 0).
     - α terlalu besar (0,85) → balok jadwal lompat liar, populasi sulit
       tenang/konvergen.
     - α_decay meluruhkan α bertahap agar eksploratif di awal lalu stabil
       di akhir hingga penalti 0,00.
"""


class FireflyJobApp:
    """Antarmuka Tkinter untuk Firefly Algorithm Penjadwalan 4 Tugas (Gantt Chart)."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Firefly Algorithm — Penjadwalan 4 Tugas pada 1 Mesin (Tkinter)")
        self.root.geometry("1360x820")
        self.root.minsize(1120, 700)

        self.problem = JobSchedulingProblem()
        self.scheduler: Optional[FireflyJobScheduler] = None
        self.is_running = False
        self.after_id: Optional[str] = None

        # Variabel Kontrol
        self.var_n = tk.IntVar(value=20)
        self.var_beta0 = tk.DoubleVar(value=1.0)
        self.var_gamma = tk.DoubleVar(value=1.5)
        self.var_alpha = tk.DoubleVar(value=0.35)
        self.var_decay = tk.DoubleVar(value=0.96)
        self.var_max_iter = tk.IntVar(value=50)
        self.var_speed = tk.IntVar(value=320)
        self.var_seed = tk.IntVar(value=42)
        self.var_inspect_ff = tk.StringVar(value="★ Best Firefly")

        self._configure_style()
        self._build_layout()
        self.reset_simulation()

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(bg="#f1f5f9")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", foreground="#0f172a", font=("Segoe UI", 9))
        style.configure("Section.TLabelframe", background="#ffffff", foreground="#0f172a")
        style.configure(
            "Section.TLabelframe.Label",
            background="#ffffff",
            foreground="#1e293b",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Treeview", font=("Segoe UI", 8), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 8, "bold"))

    def _build_layout(self) -> None:
        # Header Bar
        header = tk.Frame(self.root, bg="#0f172a", padx=14, pady=8)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Firefly Algorithm — Penjadwalan 4 Tugas pada 1 Mesin (08:00–17:00)",
            bg="#0f172a",
            fg="#f8fafc",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text="t_new = t_old + β(r)·(t_j - t_i) + α·ε   |   β(r) = β₀·e^(-γ·r²)   |   I = 1 / (1 + Penalti)",
            bg="#0f172a",
            fg="#fde047",
            font=("Consolas", 9, "bold"),
        ).pack(side="right")

        body = ttk.Frame(self.root, padding=8)
        body.pack(fill="both", expand=True)

        self._build_left_panel(body)
        self._build_right_panel(body)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        left_container = ttk.Frame(parent, width=325)
        left_container.pack(side="left", fill="y", padx=(0, 8))
        left_container.pack_propagate(False)

        canvas = tk.Canvas(left_container, bg="#f1f5f9", highlightthickness=0, width=310)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        sidebar = ttk.Frame(canvas)

        sidebar.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sidebar, anchor="nw", width=306)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 1. Kontrol Simulasi
        ctrl = ttk.LabelFrame(sidebar, text=" Kontrol Simulasi (Steps) ", style="Section.TLabelframe", padding=8)
        ctrl.pack(fill="x", pady=(0, 8))

        row1 = tk.Frame(ctrl, bg="#ffffff")
        row1.pack(fill="x", pady=(0, 5))
        self.btn_step = ttk.Button(row1, text="⏭ Step (+1)", style="Accent.TButton", command=self.do_single_step)
        self.btn_step.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_run = ttk.Button(row1, text="▶ Run", style="Accent.TButton", command=self.toggle_run)
        self.btn_run.pack(side="left", fill="x", expand=True, padx=(4, 0))

        ttk.Button(ctrl, text="↺ Reset (Base Position)", command=self.reset_simulation).pack(fill="x", pady=(0, 6))

        tk.Label(
            ctrl,
            text="Preset Eksperimen (Seed sama = perbandingan adil):",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 3))

        pgrid = tk.Frame(ctrl, bg="#ffffff")
        pgrid.pack(fill="x")
        presets = [
            ("Seimbang (Optimal)", (20, 1.0, 1.5, 0.35, 0.96), "beta0"),
            ("Minim Acak (α=0.01)", (20, 1.0, 1.5, 0.01, 0.98), "alpha"),
            ("Acak Liar (α=0.85)", (20, 0.8, 1.5, 0.85, 0.995), "alpha"),
            ("Tarikan Lemah", (20, 0.15, 10.0, 0.20, 0.97), "gamma"),
        ]
        for idx, (label, vals, hk) in enumerate(presets):
            ttk.Button(pgrid, text=label, command=lambda v=vals, k=hk: self._apply_preset(v, k)).grid(
                row=idx // 2, column=idx % 2, sticky="ew", padx=2, pady=2
            )
        pgrid.columnconfigure(0, weight=1)
        pgrid.columnconfigure(1, weight=1)

        # 2. Status Live
        mframe = ttk.LabelFrame(sidebar, text=" Status Iterasi Live ", style="Section.TLabelframe", padding=8)
        mframe.pack(fill="x", pady=(0, 8))

        self.lbl_status_badge = tk.Label(
            mframe, text="BASE POSITION (Iterasi 0)", bg="#e0f2fe", fg="#075985", font=("Segoe UI", 9, "bold"), pady=4
        )
        self.lbl_status_badge.pack(fill="x", pady=(0, 6))

        mgrid = tk.Frame(mframe, bg="#ffffff")
        mgrid.pack(fill="x")
        mgrid.columnconfigure(1, weight=1)

        self.metric_vars: Dict[str, tk.StringVar] = {}
        specs = [
            ("iter", "Iterasi (Step):"),
            ("best_pen", "Best Penalty:"),
            ("avg_pen", "Rata-rata Penalty:"),
            ("best_bright", "Best Brightness (I):"),
            ("alpha_cur", "Alpha Aktif (α_t):"),
            ("avg_beta", "Rata-rata β:"),
            ("avg_step", "Rata-rata Step (jam):"),
        ]
        for r_i, (key, title) in enumerate(specs):
            tk.Label(mgrid, text=title, bg="#ffffff", fg="#475569", font=("Segoe UI", 8)).grid(
                row=r_i, column=0, sticky="w", pady=1
            )
            sv = tk.StringVar(value="-")
            self.metric_vars[key] = sv
            tk.Label(mgrid, textvariable=sv, bg="#ffffff", fg="#0f172a", font=("Consolas", 9, "bold")).grid(
                row=r_i, column=1, sticky="e", pady=1
            )

        # 3. Parameter Firefly
        pframe = ttk.LabelFrame(sidebar, text=" Parameter Firefly (Klik/Geser) ", style="Section.TLabelframe", padding=8)
        pframe.pack(fill="x", pady=(0, 8))

        self._add_slider(pframe, "Jumlah Firefly (N)", self.var_n, 6, 40, 1, "n_fireflies", is_int=True)
        self._add_slider(pframe, "β₀ (Base Attractiveness)", self.var_beta0, 0.1, 2.0, 0.05, "beta0")
        self._add_slider(pframe, "γ (Light Absorption)", self.var_gamma, 0.0, 12.0, 0.1, "gamma")
        self._add_slider(pframe, "α (Random Step)", self.var_alpha, 0.0, 1.0, 0.01, "alpha")
        self._add_slider(pframe, "α Decay (Peluruhan)", self.var_decay, 0.90, 1.00, 0.005, "alpha_decay")
        self._add_slider(pframe, "Max Iterasi", self.var_max_iter, 10, 120, 5, "max_iter", is_int=True)
        self._add_slider(pframe, "Kecepatan (ms/step)", self.var_speed, 50, 800, 25, "max_iter", is_int=True)

        seed_row = tk.Frame(pframe, bg="#ffffff")
        seed_row.pack(fill="x", pady=(4, 0))
        tk.Label(seed_row, text="Random Seed:", bg="#ffffff", fg="#334155", font=("Segoe UI", 8, "bold")).pack(side="left")
        sp = ttk.Spinbox(seed_row, from_=0, to=9999, textvariable=self.var_seed, width=8)
        sp.pack(side="right")
        sp.bind("<FocusIn>", lambda _e: self._show_param_help("seed"))

        # 4. Penjelasan Efek Parameter Live
        hframe = ttk.LabelFrame(sidebar, text=" Ngefek ke Mana & Bagaimana? ", style="Section.TLabelframe", padding=8)
        hframe.pack(fill="x", pady=(0, 4))

        self.lbl_help_title = tk.Label(
            hframe, text="", bg="#ffffff", fg="#0369a1", font=("Segoe UI", 8, "bold"), justify="left", wraplength=280
        )
        self.lbl_help_title.pack(anchor="w", pady=(0, 4))
        self.lbl_help_body = tk.Label(
            hframe, text="", bg="#ffffff", fg="#334155", font=("Segoe UI", 8), justify="left", wraplength=280
        )
        self.lbl_help_body.pack(anchor="w")
        self._show_param_help("beta0")

    def _add_slider(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.Variable,
        from_: float,
        to: float,
        resolution: float,
        help_key: str,
        is_int: bool = False,
    ) -> None:
        block = tk.Frame(parent, bg="#ffffff")
        block.pack(fill="x", pady=2)

        top = tk.Frame(block, bg="#ffffff")
        top.pack(fill="x")
        lbl = tk.Label(top, text=label, bg="#ffffff", fg="#1e293b", font=("Segoe UI", 8, "bold"))
        lbl.pack(side="left")
        val_lbl = tk.Label(top, bg="#ffffff", fg="#0369a1", font=("Consolas", 8, "bold"))
        val_lbl.pack(side="right")

        def update_text(*_args: object) -> None:
            v = float(variable.get())
            if is_int:
                val_lbl.configure(text=f"{int(round(v))}")
            else:
                fmt = "{:.3f}" if resolution < 0.01 else "{:.2f}"
                val_lbl.configure(text=fmt.format(v))
            if self.scheduler is not None:
                if help_key == "beta0":
                    self.scheduler.beta0 = float(self.var_beta0.get())
                elif help_key == "gamma":
                    self.scheduler.gamma = float(self.var_gamma.get())
                elif help_key == "alpha":
                    self.scheduler.alpha = float(self.var_alpha.get())
                    self.scheduler.alpha_init = float(self.var_alpha.get())
                elif help_key == "alpha_decay":
                    self.scheduler.alpha_decay = float(self.var_decay.get())

        def on_scale(raw_val: str) -> None:
            snapped = round(float(raw_val) / resolution) * resolution
            if is_int:
                variable.set(int(round(snapped)))
            else:
                variable.set(round(snapped, 4))
            update_text()
            self._show_param_help(help_key)

        scale = ttk.Scale(block, from_=from_, to=to, orient="horizontal", command=on_scale)
        scale.set(float(variable.get()))
        scale.pack(fill="x")

        def sync_scale(*_args: object) -> None:
            try:
                cur = float(variable.get())
                if abs(scale.get() - cur) > resolution * 0.4:
                    scale.set(cur)
                update_text()
            except (tk.TclError, ValueError):
                pass

        variable.trace_add("write", sync_scale)
        lbl.bind("<Button-1>", lambda _e: self._show_param_help(help_key))
        scale.bind("<Button-1>", lambda _e: self._show_param_help(help_key))
        update_text()

    def _show_param_help(self, key: str) -> None:
        if not hasattr(self, "lbl_help_title"):
            return
        title, body = PARAM_HELP.get(key, PARAM_HELP["beta0"])
        self.lbl_help_title.configure(text=title)
        self.lbl_help_body.configure(text=body)

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(side="right", fill="both", expand=True)

        self.tab_main = ttk.Frame(self.notebook, padding=6)
        self.tab_inspect = ttk.Frame(self.notebook, padding=6)
        self.tab_guide = ttk.Frame(self.notebook, padding=6)

        self.notebook.add(self.tab_main, text="  1. Gantt Chart & Visualisasi Firefly  ")
        self.notebook.add(self.tab_inspect, text="  2. Bedah Base Position, Attractiveness & Steps  ")
        self.notebook.add(self.tab_guide, text="  3. Panduan Konsep & Efek Parameter  ")

        self._build_tab_main()
        self._build_tab_inspect()
        self._build_tab_guide()

    # ------------------------------------------------------------------
    # Tab 1: Gantt Chart (Atas) + Firefly Canvas & Convergence Chart (Bawah)
    # ------------------------------------------------------------------

    def _build_tab_main(self) -> None:
        # Bagian Atas: Gantt Chart Utama
        gantt_card = ttk.LabelFrame(
            self.tab_main,
            text=" Gantt Chart Jadwal Terbaik (Best Firefly — Timeline Jam 08:00 s.d. 17:00) ",
            style="Section.TLabelframe",
            padding=6,
        )
        gantt_card.pack(fill="both", expand=True, pady=(0, 6))

        self.lbl_gantt_summary = tk.Label(
            gantt_card, text="", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold"), anchor="w"
        )
        self.lbl_gantt_summary.pack(fill="x", pady=(0, 4))

        self.canvas_gantt = tk.Canvas(
            gantt_card, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1", height=270
        )
        self.canvas_gantt.pack(fill="both", expand=True)
        self.canvas_gantt.bind("<Configure>", lambda _e: self._draw_gantt_canvas())

        tk.Label(
            gantt_card,
            text="Keterangan:  │ Garis Hijau = Ready Time   ┆ Garis Merah Putus = Deadline   ■ Bingkai Merah = Overlap (Bentrok)   ■ Oranye = Lewat Deadline   ✓ = Valid",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(4, 0))

        # Bagian Bawah: 2 Kolom (Swarm 2D + Grafik Konvergensi)
        bottom = ttk.Frame(self.tab_main)
        bottom.pack(fill="both", expand=True)
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=2)
        bottom.rowconfigure(0, weight=1)

        swarm_card = ttk.LabelFrame(
            bottom,
            text=" Kawanan Firefly (Base Position □ → Steps & Panah Attractiveness β) ",
            style="Section.TLabelframe",
            padding=6,
        )
        swarm_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.canvas_swarm = tk.Canvas(swarm_card, bg="#0b1220", highlightthickness=0, height=270)
        self.canvas_swarm.pack(fill="both", expand=True)
        self.canvas_swarm.bind("<Configure>", lambda _e: self._draw_swarm_canvas())

        tk.Label(
            swarm_card,
            text="★ Hijau: Best Firefly   ● Kuning: Terang (Penalti kecil)   → Biru: Tarikan β   □ Abu: Base Position (t=0)",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(3, 0))

        chart_card = ttk.LabelFrame(
            bottom,
            text=" Grafik Konvergensi Penalti (Best vs Rata-rata Populasi) ",
            style="Section.TLabelframe",
            padding=6,
        )
        chart_card.grid(row=0, column=1, sticky="nsew")

        self.canvas_chart = tk.Canvas(
            chart_card, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1", height=270
        )
        self.canvas_chart.pack(fill="both", expand=True)
        self.canvas_chart.bind("<Configure>", lambda _e: self._draw_convergence_chart())

        tk.Label(
            chart_card,
            text="━━ Hijau: Best Penalty   ━━ Biru: Avg Penalty   --- Target: 0.00",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(3, 0))

    # ------------------------------------------------------------------
    # Tab 2: Bedah Base Position, Attractiveness & Steps
    # ------------------------------------------------------------------

    def _build_tab_inspect(self) -> None:
        pos_card = ttk.LabelFrame(
            self.tab_inspect,
            text=" 1. Bedah Base Position [t1, t2, t3, t4] (Iterasi 0) → Current Position (Jam Mulai Aktual) ",
            style="Section.TLabelframe",
            padding=8,
        )
        pos_card.pack(fill="x", pady=(0, 8))

        picker = tk.Frame(pos_card, bg="#ffffff")
        picker.pack(fill="x", pady=(0, 6))
        tk.Label(picker, text="Pilih Firefly:", bg="#ffffff", fg="#1e293b", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.cmb_firefly = ttk.Combobox(picker, textvariable=self.var_inspect_ff, state="readonly", width=24)
        self.cmb_firefly.pack(side="left", padx=8)
        self.cmb_firefly.bind("<<ComboboxSelected>>", lambda _e: self._update_inspector_tables())

        self.lbl_ff_summary = tk.Label(picker, text="", bg="#ffffff", fg="#0369a1", font=("Consolas", 8, "bold"))
        self.lbl_ff_summary.pack(side="right")

        cols_pos = ("task", "dur", "base_start", "cur_start", "shift", "end_dl", "status")
        self.tree_pos = ttk.Treeview(pos_card, columns=cols_pos, show="headings", height=5)
        for col, text, width in [
            ("task", "Tugas", 175),
            ("dur", "Durasi & Ready", 125),
            ("base_start", "Base Position (t=0)", 135),
            ("cur_start", "Current Position (t)", 135),
            ("shift", "Pergeseran (Δ jam)", 115),
            ("end_dl", "Selesai vs Deadline", 145),
            ("status", "Status Validitas", 175),
        ]:
            self.tree_pos.heading(col, text=text)
            self.tree_pos.column(col, width=width, anchor="w")
        self.tree_pos.pack(fill="x")
        self.tree_pos.tag_configure("ok", background="#ecfdf5", foreground="#065f46")
        self.tree_pos.tag_configure("warn", background="#fef3c7", foreground="#92400e")
        self.tree_pos.tag_configure("err", background="#fee2e2", foreground="#991b1b")

        # Log Attractiveness & Steps
        move_card = ttk.LabelFrame(
            self.tab_inspect,
            text=" 2. Log Attractiveness (β) & Steps (Δx = Tarikan + Acak) pada Iterasi Terakhir ",
            style="Section.TLabelframe",
            padding=8,
        )
        move_card.pack(fill="both", expand=True)

        self.lbl_move_note = tk.Label(move_card, text="", bg="#ffffff", fg="#475569", font=("Segoe UI", 8), anchor="w")
        self.lbl_move_note.pack(fill="x", pady=(0, 4))

        cols_mov = ("pair", "bright", "dist", "beta", "att", "rnd", "tot", "pen")
        self.tree_moves = ttk.Treeview(move_card, columns=cols_mov, show="headings", height=12)
        for col, text, width in [
            ("pair", "Firefly i → Penarik j", 165),
            ("bright", "Brightness (I_i → I_j)", 140),
            ("dist", "Jarak (r)", 75),
            ("beta", "Attractiveness (β)", 115),
            ("att", "Step Tarikan (jam)", 110),
            ("rnd", "Step Acak (jam)", 100),
            ("tot", "Total Step (jam)", 105),
            ("pen", "Penalti (Before → After)", 165),
        ]:
            self.tree_moves.heading(col, text=text)
            self.tree_moves.column(col, width=width, anchor="center")

        mscroll = ttk.Scrollbar(move_card, orient="vertical", command=self.tree_moves.yview)
        self.tree_moves.configure(yscrollcommand=mscroll.set)
        self.tree_moves.pack(side="left", fill="both", expand=True)
        mscroll.pack(side="right", fill="y")

        self.tree_moves.tag_configure("better", background="#ecfdf5", foreground="#065f46")
        self.tree_moves.tag_configure("same", background="#f8fafc", foreground="#334155")
        self.tree_moves.tag_configure("worse", background="#fff1f2", foreground="#9f1239")

    # ------------------------------------------------------------------
    # Tab 3: Panduan Konsep
    # ------------------------------------------------------------------

    def _build_tab_guide(self) -> None:
        gcard = ttk.LabelFrame(
            self.tab_guide,
            text=" Materi Ringkas: Base Position, Attractiveness, Steps & Efek Parameter ",
            style="Section.TLabelframe",
            padding=8,
        )
        gcard.pack(fill="both", expand=True)

        txt = tk.Text(
            gcard, wrap="word", font=("Consolas", 9), bg="#ffffff", fg="#0f172a", padx=12, pady=10, relief="flat"
        )
        sc = ttk.Scrollbar(gcard, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sc.set)
        txt.insert("1.0", GUIDE_TEXT)
        txt.configure(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Kontrol Simulasi
    # ------------------------------------------------------------------

    def _apply_preset(self, values: Tuple[int, float, float, float, float], help_key: str) -> None:
        n, beta0, gamma, alpha, decay = values
        self.var_n.set(n)
        self.var_beta0.set(beta0)
        self.var_gamma.set(gamma)
        self.var_alpha.set(alpha)
        self.var_decay.set(decay)
        self._show_param_help(help_key)
        self.reset_simulation()

    def reset_simulation(self) -> None:
        self._stop_run()
        self.scheduler = FireflyJobScheduler(
            problem=self.problem,
            n_fireflies=int(self.var_n.get()),
            beta0=float(self.var_beta0.get()),
            gamma=float(self.var_gamma.get()),
            alpha=float(self.var_alpha.get()),
            alpha_decay=float(self.var_decay.get()),
            seed=int(self.var_seed.get()),
        )
        opts = ["★ Best Firefly"] + [f"Firefly F{ff.id}" for ff in self.scheduler.fireflies]
        self.cmb_firefly.configure(values=opts)
        self.var_inspect_ff.set("★ Best Firefly")
        self._refresh_all_views()

    def do_single_step(self) -> None:
        if self.scheduler is None:
            return
        self.scheduler.step()
        self._refresh_all_views()

    def toggle_run(self) -> None:
        if self.is_running:
            self._stop_run()
        else:
            if self.scheduler is None:
                self.reset_simulation()
            if self.scheduler and self.scheduler.iteration >= int(self.var_max_iter.get()):
                self.reset_simulation()
            self.is_running = True
            self.btn_run.configure(text="⏸ Pause")
            self._run_loop()

    def _stop_run(self) -> None:
        self.is_running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        if hasattr(self, "btn_run"):
            self.btn_run.configure(text="▶ Run")

    def _run_loop(self) -> None:
        if not self.is_running or self.scheduler is None:
            return
        max_iter = int(self.var_max_iter.get())
        if self.scheduler.iteration >= max_iter or (
            self.scheduler.best_firefly
            and self.scheduler.best_firefly.report
            and self.scheduler.best_firefly.report.is_optimal
        ):
            self._stop_run()
            self._refresh_all_views()
            return

        self.scheduler.step()
        self._refresh_all_views()

        if (
            self.scheduler.best_firefly
            and self.scheduler.best_firefly.report
            and self.scheduler.best_firefly.report.is_optimal
        ):
            self._stop_run()
            return

        self.after_id = self.root.after(max(40, int(self.var_speed.get())), self._run_loop)

    # ------------------------------------------------------------------
    # Rendering Visualisasi
    # ------------------------------------------------------------------

    def _refresh_all_views(self) -> None:
        if self.scheduler is None:
            return
        self._update_metrics()
        self._draw_gantt_canvas()
        self._draw_swarm_canvas()
        self._draw_convergence_chart()
        self._update_inspector_tables()

    def _update_metrics(self) -> None:
        assert self.scheduler is not None
        best = self.scheduler.best_firefly
        assert best is not None and best.report is not None

        it = self.scheduler.iteration
        max_it = int(self.var_max_iter.get())
        self.metric_vars["iter"].set(f"{it} / {max_it}")
        self.metric_vars["best_pen"].set(f"{best.penalty:.2f}")
        self.metric_vars["avg_pen"].set(f"{self.scheduler.avg_penalty_history[-1]:.2f}")
        self.metric_vars["best_bright"].set(f"{best.brightness:.4f}")
        self.metric_vars["alpha_cur"].set(f"{self.scheduler.alpha:.3f}")
        self.metric_vars["avg_beta"].set(f"{self.scheduler.avg_beta_history[-1]:.3f}")
        self.metric_vars["avg_step"].set(f"{self.scheduler.avg_step_history[-1]:.3f} j")

        rep = best.report
        if rep.is_optimal:
            self.lbl_status_badge.configure(
                text=f"✓ OPTIMAL! 0 Overlap & 0 Telat (Iterasi {it})", bg="#dcfce7", fg="#166534"
            )
        elif it == 0:
            self.lbl_status_badge.configure(
                text=f"BASE POSITION — Penalti Awal: {best.penalty:.2f}", bg="#e0f2fe", fg="#075985"
            )
        else:
            self.lbl_status_badge.configure(
                text=f"Iterasi {it} — Overlap: {rep.total_overlap_hours:.2f}j | Telat: {rep.total_lateness_hours:.2f}j",
                bg="#fee2e2" if rep.total_overlap_hours > 0.01 else "#fef3c7",
                fg="#991b1b" if rep.total_overlap_hours > 0.01 else "#92400e",
            )

    def _draw_gantt_canvas(self) -> None:
        c = self.canvas_gantt
        c.delete("all")
        if self.scheduler is None or self.scheduler.best_firefly is None:
            return

        best = self.scheduler.best_firefly
        rep = best.report
        assert rep is not None

        if rep.is_optimal:
            self.lbl_gantt_summary.configure(
                text=f"★ Best Firefly F{best.id} — SEMPURNA! 0,00 jam Overlap | 0,00 jam Telat | Penalti = 0,00 | Brightness I = 1,0000",
                fg="#166534",
            )
        else:
            self.lbl_gantt_summary.configure(
                text=(
                    f"★ Best Firefly F{best.id} — Penalti: {rep.total_penalty:.2f}  |  "
                    f"Total Overlap: {rep.total_overlap_hours:.2f} jam (×10)  •  "
                    f"Total Telat: {rep.total_lateness_hours:.2f} jam (×6)  •  "
                    f"Brightness I = {best.brightness:.4f}"
                ),
                fg="#991b1b" if rep.total_overlap_hours > 0.01 else "#92400e",
            )

        w = max(480, c.winfo_width())
        h = max(210, c.winfo_height())
        pad_l, pad_r, pad_t, pad_b = 175, 28, 30, 26
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b
        total_hours = WORK_END - WORK_START

        def hour_to_x(hr: float) -> float:
            return pad_l + ((hr - WORK_START) / total_hours) * plot_w

        # Grid jam 08:00 .. 17:00
        for hr in range(int(WORK_START), int(WORK_END) + 1):
            gx = hour_to_x(float(hr))
            c.create_line(gx, pad_t, gx, pad_t + plot_h, fill="#e2e8f0")
            c.create_text(gx, pad_t - 10, text=f"{hr:02d}:00", fill="#475569", font=("Consolas", 8, "bold"))

        c.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#94a3b8")

        n_tasks = len(self.problem.tasks)
        row_h = plot_h / n_tasks

        # Sorot zona merah vertikal jika ada overlap antar tugas
        for a in range(n_tasks):
            sa = rep.task_statuses[a]
            for b in range(a + 1, n_tasks):
                sb = rep.task_statuses[b]
                ov_s = max(sa.start, sb.start)
                ov_e = min(sa.end, sb.end)
                if ov_e - ov_s > 1e-4:
                    c.create_rectangle(
                        hour_to_x(ov_s),
                        pad_t + 1,
                        hour_to_x(ov_e),
                        pad_t + plot_h - 1,
                        fill="#fee2e2",
                        outline="",
                    )

        # Gambar setiap baris tugas
        for idx, task in enumerate(self.problem.tasks):
            st = rep.task_statuses[idx]
            y_top = pad_t + idx * row_h
            y_mid = y_top + row_h / 2.0
            bar_h = min(32.0, row_h * 0.56)

            if idx > 0:
                c.create_line(pad_l, y_top, pad_l + plot_w, y_top, fill="#f1f5f9")

            # Label tugas di kiri
            c.create_text(
                10,
                y_mid - 7,
                anchor="w",
                text=f"{task.code} • {task.name}",
                fill="#0f172a",
                font=("Segoe UI", 8, "bold"),
            )
            c.create_text(
                10,
                y_mid + 8,
                anchor="w",
                text=f"Dur {task.duration:.1f}j | Rdy {format_hour(task.ready_time)} | DL {format_hour(task.deadline)}",
                fill="#64748b",
                font=("Consolas", 7),
            )

            # Garis Ready Time (hijau tipis) & Deadline (merah putus-putus)
            rx = hour_to_x(task.ready_time)
            dx = hour_to_x(task.deadline)
            c.create_line(rx, y_top + 4, rx, y_top + row_h - 4, fill="#22c55e", width=1.5)
            c.create_line(dx, y_top + 3, dx, y_top + row_h - 3, fill="#ef4444", width=1.5, dash=(3, 2))
            c.create_text(
                dx - 3,
                y_top + 9,
                anchor="e",
                text=f"DL {format_hour(task.deadline)}",
                fill="#dc2626",
                font=("Consolas", 7, "bold"),
            )

            # Balok jadwal tugas
            x1 = hour_to_x(st.start)
            x2 = hour_to_x(st.end)
            y1 = y_mid - bar_h / 2.0
            y2 = y_mid + bar_h / 2.0

            outline = "#dc2626" if st.overlap_hours > 1e-4 else ("#d97706" if st.lateness_hours > 1e-4 else "#0f172a")
            owidth = 2.5 if not st.is_valid else 1.2
            c.create_rectangle(x1, y1, x2, y2, fill=task.color, outline=outline, width=owidth)

            # Jika lewat deadline, arsir bagian telat dengan oranye-merah
            if st.lateness_hours > 1e-4:
                late_x1 = max(x1, dx)
                c.create_rectangle(late_x1, y1, x2, y2, fill="#f97316", outline="#dc2626", width=2)

            # Teks di dalam balok
            bar_txt = f"{format_hour(st.start)}–{format_hour(st.end)}"
            c.create_text(
                (x1 + x2) / 2.0,
                y_mid,
                text=bar_txt,
                fill="#ffffff",
                font=("Consolas", 8, "bold"),
            )

            # Badge status di ujung kanan balok
            if st.is_valid:
                badge, bcol = "✓ AMAN", "#166534"
            else:
                parts = []
                if st.overlap_hours > 1e-4:
                    parts.append(f"BENTROK ({','.join(st.overlaps_with)})")
                if st.lateness_hours > 1e-4:
                    parts.append(f"TELAT +{st.lateness_hours:.1f}j")
                badge, bcol = "⚠ " + " & ".join(parts), "#b91c1c"

            tx = min(pad_l + plot_w - 4, x2 + 6)
            anchor = "w" if x2 + 125 < pad_l + plot_w else "e"
            if anchor == "e":
                tx = max(pad_l + 4, x1 - 6)
            c.create_text(tx, y_mid, anchor=anchor, text=badge, fill=bcol, font=("Segoe UI", 8, "bold"))

    def _draw_swarm_canvas(self) -> None:
        c = self.canvas_swarm
        c.delete("all")
        if self.scheduler is None:
            return

        w = max(200, c.winfo_width())
        h = max(160, c.winfo_height())
        pad_l, pad_r, pad_t, pad_b = 46, 18, 22, 28
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        # Rentang proyeksi jam mulai (08:00 .. 16:00)
        x_min, x_max = 8.0, 15.5
        y_min, y_max = 9.0, 15.5

        def to_xy(px: float, py: float) -> Tuple[float, float]:
            nx = max(0.0, min(1.0, (px - x_min) / (x_max - x_min)))
            ny = max(0.0, min(1.0, (py - y_min) / (y_max - y_min)))
            return (pad_l + nx * plot_w, pad_t + (1.0 - ny) * plot_h)

        for i in range(5):
            frac = i / 4.0
            gx = pad_l + frac * plot_w
            gy = pad_t + frac * plot_h
            c.create_line(gx, pad_t, gx, pad_t + plot_h, fill="#1e293b", dash=(2, 4))
            c.create_line(pad_l, gy, pad_l + plot_w, gy, fill="#1e293b", dash=(2, 4))

        c.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#334155")
        c.create_text(
            pad_l + plot_w / 2, h - 10, text="Rata-rata Jam Mulai T1 & T2 (08:00–15:30)", fill="#94a3b8", font=("Segoe UI", 8)
        )
        c.create_text(14, pad_t + plot_h / 2, text="Avg T3 & T4", fill="#94a3b8", font=("Segoe UI", 8), angle=90)

        ff_by_id = {ff.id: ff for ff in self.scheduler.fireflies}
        best_id = self.scheduler.best_firefly.id if self.scheduler.best_firefly else -1

        # Base Position & jejak Steps
        for ff in self.scheduler.fireflies:
            bx, by = to_xy(*self.scheduler.project_2d(ff.base_position))
            c.create_rectangle(bx - 2, by - 2, bx + 2, by + 2, outline="#475569", fill="")
            if len(ff.trail_2d) > 1:
                pts: List[float] = []
                for tp in ff.trail_2d[-12:]:
                    tx, ty = to_xy(*tp)
                    pts.extend([tx, ty])
                c.create_line(*pts, fill="#15803d" if ff.id == best_id else "#1e3a5f", width=1.5 if ff.id == best_id else 1)

        # Panah Attractiveness (β)
        moves = [m for m in self.scheduler.last_movements if not m.is_self_exploration]
        for m in sorted(moves, key=lambda item: item.attractiveness_beta, reverse=True)[:12]:
            mover = ff_by_id.get(m.mover_id)
            att = ff_by_id.get(m.attractor_id)
            if mover is None or att is None:
                continue
            x1, y1 = to_xy(*self.scheduler.project_2d(mover.prev_position))
            x2, y2 = to_xy(*self.scheduler.project_2d(att.prev_position))
            if abs(x2 - x1) + abs(y2 - y1) > 4:
                c.create_line(
                    x1, y1, x2, y2, fill="#38bdf8", width=max(1.0, min(2.5, m.attractiveness_beta * 2.0)), arrow=tk.LAST
                )

        # Titik Firefly bercahaya
        max_b = max((ff.brightness for ff in self.scheduler.fireflies), default=1.0)
        min_b = min((ff.brightness for ff in self.scheduler.fireflies), default=0.0)
        span_b = max(1e-6, max_b - min_b)

        for ff in self.scheduler.fireflies:
            cx, cy = to_xy(*self.scheduler.project_2d(ff.position))
            norm = (ff.brightness - min_b) / span_b if span_b > 1e-5 else 1.0
            rad = 4.0 + norm * 5.0
            if norm > 0.35 or ff.id == best_id:
                hr = rad + 4 + norm * 3.5
                c.create_oval(
                    cx - hr, cy - hr, cx + hr, cy + hr, fill="#166534" if ff.id == best_id else "#713f12", outline=""
                )
            if ff.id == best_id:
                col, out = "#4ade80", "#ffffff"
            else:
                rc = int(125 + norm * 130)
                gc = int(110 + norm * 130)
                bc = int(70 - norm * 40)
                col = f"#{rc:02x}{gc:02x}{max(0, bc):02x}"
                out = "#fef08a" if norm > 0.6 else "#64748b"
            c.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill=col, outline=out, width=1.5)
            c.create_text(
                cx,
                cy - rad - 7,
                text=f"★F{ff.id}" if ff.id == best_id else f"F{ff.id}",
                fill="#86efac" if ff.id == best_id else "#cbd5e1",
                font=("Consolas", 7, "bold" if ff.id == best_id else "normal"),
            )

        c.create_text(
            pad_l + 6,
            11,
            anchor="w",
            text=f"t={self.scheduler.iteration} | N={len(self.scheduler.fireflies)} | β₀={self.scheduler.beta0:.2f} | γ={self.scheduler.gamma:.2f} | α_t={self.scheduler.alpha:.3f}",
            fill="#e2e8f0",
            font=("Consolas", 8, "bold"),
        )

    def _draw_convergence_chart(self) -> None:
        c = self.canvas_chart
        c.delete("all")
        if self.scheduler is None:
            return

        w = max(180, c.winfo_width())
        h = max(160, c.winfo_height())
        pad_l, pad_r, pad_t, pad_b = 42, 18, 22, 26
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        best_h = self.scheduler.best_penalty_history
        avg_h = self.scheduler.avg_penalty_history
        max_x = max(10, int(self.var_max_iter.get()), len(best_h) - 1)
        max_y = max(5.0, max(avg_h) * 1.12, max(best_h) * 1.12)

        def to_xy(it: int, val: float) -> Tuple[float, float]:
            return (pad_l + (it / max_x) * plot_w, pad_t + (1.0 - val / max_y) * plot_h)

        for i in range(5):
            val = max_y * (i / 4.0)
            _, gy = to_xy(0, val)
            c.create_line(pad_l, gy, pad_l + plot_w, gy, fill="#e2e8f0")
            c.create_text(pad_l - 6, gy, text=f"{val:.0f}", anchor="e", fill="#64748b", font=("Consolas", 8))

        _, y0 = to_xy(0, 0.0)
        c.create_line(pad_l, y0, pad_l + plot_w, y0, fill="#22c55e", dash=(4, 3), width=1.5)
        c.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#94a3b8")
        c.create_text(pad_l + plot_w / 2, h - 9, text="Iterasi (Steps)", fill="#475569", font=("Segoe UI", 8))
        c.create_text(pad_l, h - 9, text="0", fill="#64748b", font=("Consolas", 8))
        c.create_text(pad_l + plot_w, h - 9, text=str(max_x), fill="#64748b", font=("Consolas", 8))

        if len(avg_h) > 1:
            pts_avg: List[float] = []
            for idx, v in enumerate(avg_h):
                pts_avg.extend(to_xy(idx, v))
            c.create_line(*pts_avg, fill="#3b82f6", width=2)
        if len(best_h) > 1:
            pts_best: List[float] = []
            for idx, v in enumerate(best_h):
                pts_best.extend(to_xy(idx, v))
            c.create_line(*pts_best, fill="#16a34a", width=2.5)

        bx, by = to_xy(len(best_h) - 1, best_h[-1])
        c.create_oval(bx - 4, by - 4, bx + 4, by + 4, fill="#16a34a", outline="#ffffff", width=1.5)
        c.create_text(
            min(pad_l + plot_w - 50, bx + 8),
            max(pad_t + 10, by - 10),
            text=f"Best: {best_h[-1]:.2f}",
            fill="#15803d",
            font=("Consolas", 8, "bold"),
            anchor="w",
        )

    def _get_selected_firefly(self) -> Optional[Firefly]:
        if self.scheduler is None:
            return None
        sel = self.var_inspect_ff.get()
        if sel.startswith("★"):
            return self.scheduler.best_firefly
        try:
            fid = int(sel.replace("Firefly F", "").strip())
            for ff in self.scheduler.fireflies:
                if ff.id == fid:
                    return ff
        except ValueError:
            pass
        return self.scheduler.best_firefly

    def _update_inspector_tables(self) -> None:
        assert self.scheduler is not None

        for item in self.tree_pos.get_children():
            self.tree_pos.delete(item)

        ff = self._get_selected_firefly()
        if ff is not None and ff.report is not None:
            dist_base = self.scheduler.normalized_distance(ff.base_position, ff.position)
            self.lbl_ff_summary.configure(
                text=f"F{ff.id} | Penalti: {ff.penalty:.2f} | Brightness I: {ff.brightness:.4f} | Jarak dari Base Pos: {dist_base:.3f}"
            )
            for k, task in enumerate(self.problem.tasks):
                st = ff.report.task_statuses[k]
                b_hr = ff.base_position[k]
                c_hr = ff.position[k]
                diff = c_hr - b_hr
                if st.is_valid:
                    status, tag = "✓ Valid (0 overlap, 0 telat)", "ok"
                elif st.overlap_hours > 1e-4:
                    status, tag = f"✗ Overlap {st.overlap_hours:.2f}j ({','.join(st.overlaps_with)})", "err"
                else:
                    status, tag = f"⚠ Telat +{st.lateness_hours:.2f}j", "warn"

                self.tree_pos.insert(
                    "",
                    "end",
                    values=(
                        f"{task.code} {task.name}",
                        f"{task.duration:.1f} jam (≥ {format_hour(task.ready_time)})",
                        f"{format_hour(b_hr)} ({b_hr:.2f} j)",
                        f"{format_hour(c_hr)} ({c_hr:.2f} j)",
                        f"{diff:+.2f} jam",
                        f"{format_hour(st.end)} / DL {format_hour(task.deadline)}",
                        status,
                    ),
                    tags=(tag,),
                )

        for item in self.tree_moves.get_children():
            self.tree_moves.delete(item)

        moves = self.scheduler.last_movements
        if not moves:
            self.lbl_move_note.configure(
                text="Iterasi 0 (Base Position): belum ada pergerakan. Klik 'Step (+1)' untuk melihat Attractiveness (β) & Steps!"
            )
            return

        improved = sum(1 for m in moves if m.penalty_after < m.penalty_before - 1e-4)
        self.lbl_move_note.configure(
            text=(
                f"Iterasi {self.scheduler.iteration}: {len(moves)} pergerakan ({improved} membaik) | "
                f"β(r) = {self.scheduler.beta0:.2f}·e^(-{self.scheduler.gamma:.2f}·r²), α = {self.scheduler.alpha:.3f}"
            )
        )

        for m in sorted(moves, key=lambda x: (x.penalty_after - x.penalty_before, -x.attractiveness_beta)):
            pair = f"★ F{m.mover_id} (Eksplorasi Mandiri)" if m.is_self_exploration else f"F{m.mover_id} → F{m.attractor_id}"
            diff = m.penalty_after - m.penalty_before
            if diff < -0.01:
                ptxt, tag = f"{m.penalty_before:.2f} → {m.penalty_after:.2f} ({diff:+.2f})", "better"
            elif abs(diff) <= 0.01:
                ptxt, tag = f"{m.penalty_before:.2f} → {m.penalty_after:.2f} (Tetap)", "same"
            else:
                ptxt, tag = f"{m.penalty_before:.2f} → {m.penalty_after:.2f} ({diff:+.2f})", "worse"

            self.tree_moves.insert(
                "",
                "end",
                values=(
                    pair,
                    f"{m.mover_brightness_before:.3f} → {m.attractor_brightness:.3f}",
                    f"{m.distance_r:.3f}",
                    f"{m.attractiveness_beta:.4f}",
                    f"{m.attraction_step_hours:.3f} j",
                    f"{m.random_step_hours:.3f} j",
                    f"{m.total_step_hours:.3f} j",
                    ptxt,
                ),
                tags=(tag,),
            )


def main() -> None:
    root = tk.Tk()
    FireflyJobApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
