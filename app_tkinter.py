"""
Aplikasi Tkinter Interaktif: Firefly Algorithm untuk Penjadwalan Mata Kuliah.
100% Pure Python + Tkinter (tanpa dependensi library eksternal).

Jalankan:
    python app_tkinter.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple

from firefly_scheduler import Firefly, FireflyScheduler, SchedulingProblem


PARAM_HELP: Dict[str, Tuple[str, str]] = {
    "n_fireflies": (
        "Jumlah Firefly (N) — Ukuran Populasi Base Position",
        "• Memengaruhi: keragaman solusi awal (Base Position) & cakupan ruang pencarian.\n"
        "• Jika BESAR (30–40): peluang langsung mendapat jadwal awal bagus makin tinggi & sulit terjebak local optimum, tetapi tiap iterasi sedikit lebih lambat.\n"
        "• Jika KECIL (5–10): cepat per iterasi, namun pilihan jadwal awal sempit sehingga rawan mentok di jadwal bentrok.",
    ),
    "beta0": (
        "β₀ (Base Attractiveness) — Daya Tarik Maksimum saat r = 0",
        "• Rumus: β(r) = β₀ · e^(-γ·r²).\n"
        "• Memengaruhi: seberapa kuat kunang-kunang redup ditarik ke kunang-kunang lebih terang (EKSPLOITASI).\n"
        "• Jika BESAR (1.2–2.0): langkah tarikan agresif, kawanan cepat berkumpul (bisa overshoot/melewati titik target jika > 1).\n"
        "• Jika KECIL (0.1–0.3): tarikan lemah, kunang-kunang lambat meniru jadwal terbaik.",
    ),
    "gamma": (
        "γ (Light Absorption) — Redaman Cahaya terhadap Jarak",
        "• Rumus: β(r) = β₀ · e^(-γ·r²).\n"
        "• Memengaruhi: radius pandang kunang-kunang (pencarian Global vs Lokal).\n"
        "• Jika KECIL (0.1–0.5): cahaya menembus jauh → hampir semua firefly tertarik ke Best Global (konvergen cepat, tapi risiko premature convergence).\n"
        "• Jika BESAR (5.0–10.0): cahaya cepat redup → firefly hanya tertarik pada tetangga sangat dekat (pencarian lokal/hampir acak).",
    ),
    "alpha": (
        "α (Random Step / Randomization) — Skala Langkah Acak",
        "• Rumus: x_baru = x_lama + β(x_j - x_i) + α·ε_i.\n"
        "• Memengaruhi: kemampuan EKSPLORASI untuk keluar dari local optimum (jadwal bentrok yang mentok).\n"
        "• Jika BESAR (0.7–1.0): mudah melompat ke slot/ruangan baru, namun populasi lebih berisik/sulit tenang.\n"
        "• Jika KECIL (0.01–0.1): pergerakan halus, tetapi jika jadwal masih bentrok akan sulit berubah.",
    ),
    "alpha_decay": (
        "α Decay — Peluruhan Langkah Acak per Iterasi",
        "• Rumus: α(t+1) = α(t) × decay.\n"
        "• Memengaruhi: transisi dari eksplorasi (awal iterasi) ke eksploitasi/fine-tuning (akhir iterasi).\n"
        "• Mendekati 1.00: eksplorasi tetap aktif lama.\n"
        "• Lebih kecil (0.92–0.95): langkah acak cepat mengecil sehingga kawanan cepat stabil/konvergen.",
    ),
    "max_iter": (
        "Max Iterasi — Batas Langkah (Steps)",
        "• Memengaruhi: berapa kali seluruh populasi melakukan evaluasi cahaya, tarikan (β), dan perpindahan (Step).\n"
        "• Iterasi otomatis berhenti lebih cepat jika sudah mencapai Penalti = 0 (Jadwal Optimal) saat mode Run.",
    ),
    "seed": (
        "Random Seed — Penentu Base Position Awal",
        "• Mengatur generator acak untuk membangkitkan Base Position (iterasi 0) dan langkah acak ε_i.\n"
        "• Seed yang sama menghasilkan titik awal identik, cocok untuk membandingkan efek perubahan β₀, γ, dan α secara adil.",
    ),
}

GUIDE_TEXT = r"""======================================================================
  PANDUAN KONSEP FIREFLY ALGORITHM UNTUK PENJADWALAN MATA KULIAH
======================================================================

1. APA MASALAH PENJADWALAN YANG DISELESAIKAN?
   Kita memiliki 10 Mata Kuliah (MK01–MK10), 6 Slot Waktu (Senin–Rabu,
   Pagi & Siang), dan 3 Ruangan dengan kapasitas berbeda:
   • R1 (Ruang Besar A) : Kapasitas 40 (muat semua kelas)
   • R2 (Ruang Sedang B): Kapasitas 32 (terlalu kecil untuk kelas TI-A yg 35)
   • R3 (Lab Komputer C): Kapasitas 28 (hanya muat kelas TI-C yg 25)

   Aturan Penalti (semakin kecil semakin baik, target = 0):
   • Hard Constraint (+10 per pelanggaran):
     - Bentrok Ruangan : 2 MK berada di ruangan & slot waktu yang sama.
     - Bentrok Dosen   : Dosen yang sama mengajar 2 MK di slot yang sama.
     - Bentrok Kelas   : Kelas mahasiswa yang sama ada di 2 MK bersamaan.
   • Soft Constraint (+3 per pelanggaran):
     - Kapasitas       : Jumlah mahasiswa > kapasitas ruangan.

----------------------------------------------------------------------
2. BASE POSITION (x_i) — POSISI AWAL KUNANG-KUNANG
----------------------------------------------------------------------
   • Setiap kunang-kunang (firefly) merepresentasikan 1 calon JADWAL
     LENGKAP dalam bentuk vektor angka kontinu x_i ∈ [0, 1]^(20).
   • Untuk setiap mata kuliah k (dari 10 MK):
     - x[2k]     ∈ [0, 1] → dipetakan menjadi indeks Slot Waktu (0..5)
     - x[2k + 1] ∈ [0, 1] → dipetakan menjadi indeks Ruangan (0..2)
   • Pada iterasi 0, seluruh kunang-kunang disebar acak di [0, 1]^20.
     Titik awal inilah yang disebut BASE POSITION.
   • Ngefek ke mana?
     Base Position menentukan titik awal pencarian & penalti awal.
     Lihat Tab 2 untuk melihat perbandingan Base Position (t=0) vs
     Current Position (t sekarang) beserta hasil konversinya ke jadwal!

----------------------------------------------------------------------
3. LIGHT INTENSITY / BRIGHTNESS (I) — TINGKAT KECERAHAN
----------------------------------------------------------------------
   • Rumus:  I(x_i) = 1 / (1 + Penalty(x_i))
   • Penalti tinggi (banyak bentrok) → I kecil → kunang-kunang REDUP.
   • Penalti = 0 (bebas bentrok)     → I = 1.0 → kunang-kunang PALING TERANG.
   • Ngefek ke mana?
     Menentukan ARAH tarikan: kunang-kunang redup SELALU tertarik menuju
     kunang-kunang yang lebih terang (I_j > I_i).

----------------------------------------------------------------------
4. ATTRACTIVENESS (β) — DAYA TARIK ANTAR KUNANG-KUNANG
----------------------------------------------------------------------
   • Rumus:  β(r) = β₀ · exp(-γ · r²)
     dengan r = ||x_i - x_j|| / √D (jarak ternormalisasi di [0, 1]).
   • Dua parameter pengendalinya:
     a) β₀ (Base Attractiveness):
        - Daya tarik maksimum saat kedua kunang-kunang sangat dekat (r ≈ 0).
        - β₀ BESAR → tarikan kuat, jadwal redup cepat meniru jadwal terang.
        - β₀ KECIL → tarikan lemah, konvergensi melambat.
     b) γ (Light Absorption / Serapan Cahaya):
        - Mengatur seberapa cepat cahaya "memudar" oleh jarak r.
        - γ KECIL (≈ 0.1–0.5) → cahaya terlihat jauh → pencarian bersifat
          GLOBAL, kawanan cepat berkumpul ke solusi terbaik (tapi rawan
          kehilangan keragaman jika terlalu ekstrem).
        - γ BESAR (≈ 6–10) → cahaya cepat redup → β mendekati 0 untuk
          tetangga jauh → pencarian bersifat sangat LOKAL / mirip random walk.

----------------------------------------------------------------------
5. STEPS / MOVEMENT (Δx) — LANGKAH PERPINDAHAN TIAP ITERASI
----------------------------------------------------------------------
   • Rumus update posisi setiap step/iterasi:
       x_i(t+1) = x_i(t)  +  β(r) · (x_j - x_i)  +  α · ε_i
                              \________________/     \_____/
                               Attraction Step     Random Step
                                (Eksploitasi)      (Eksplorasi)
   • Komponen 1 — Attraction Step [β(r)·(x_j - x_i)]:
     Menarik vektor jadwal i mendekati jadwal j yang lebih terang.
     Artinya, slot waktu & ruangan milik jadwal redup ikut bergeser
     menyerupai jadwal yang lebih sedikit bentroknya.
   • Komponen 2 — Random Step [α · ε_i]:
     Memberi dorongan acak pada sebagian dimensi (slot/ruang mata kuliah)
     agar jadwal tidak terjebak di local optimum (misalnya mentok di
     1 pelanggaran kapasitas).
   • Peluruhan α (α_decay):
     Di awal iterasi, α besar → eksplorasi luas mencari kombinasi jadwal.
     Di akhir iterasi, α mengecil → langkah lebih halus untuk stabilisasi.

----------------------------------------------------------------------
6. CARA DEMO / PRESENTASI YANG EFEKTIF DENGAN APLIKASI INI
----------------------------------------------------------------------
   1) Klik "Reset (Base Pos)" → tunjukkan iterasi 0: titik tersebar acak
      di Canvas & tabel jadwal masih banyak warna merah/oranye (bentrok).
   2) Klik "Step (+1 Iterasi)" 2–3 kali → tunjukkan panah tarikan β di
      Canvas, lalu buka Tab 2 untuk membedah angka r, β, Step Tarikan,
      Step Acak, dan penurunan Penalti secara nyata.
   3) Klik "Run" pada preset "Seimbang (Optimal)" → grafik penalti turun
      menuju 0 dan tabel jadwal berubah HIJAU semua!
   4) Coba preset "Terlalu Lokal (γ besar)" atau "Minim Eksplorasi (α≈0)"
      dengan Seed yang sama (42) → bandingkan grafiknya untuk membuktikan
      secara visual pengaruh nyata dari γ dan α!
"""


class FireflyTkinterApp:
    """Antarmuka Tkinter untuk simulasi & edukasi Firefly Algorithm Penjadwalan."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Firefly Algorithm — Optimasi Penjadwalan Mata Kuliah (Tkinter)")
        self.root.geometry("1360x820")
        self.root.minsize(1120, 700)

        self.problem = SchedulingProblem()
        self.scheduler: Optional[FireflyScheduler] = None
        self.is_running = False
        self.after_id: Optional[str] = None

        # Variabel Kontrol Tkinter
        self.var_n = tk.IntVar(value=25)
        self.var_beta0 = tk.DoubleVar(value=1.0)
        self.var_gamma = tk.DoubleVar(value=1.5)
        self.var_alpha = tk.DoubleVar(value=0.60)
        self.var_decay = tk.DoubleVar(value=0.985)
        self.var_max_iter = tk.IntVar(value=60)
        self.var_speed = tk.IntVar(value=220)
        self.var_seed = tk.IntVar(value=42)
        self.var_inspect_ff = tk.StringVar(value="★ Best Firefly")

        self._configure_style()
        self._build_layout()
        self.reset_simulation()

    # ------------------------------------------------------------------
    # Styling & Layout
    # ------------------------------------------------------------------

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg="#f1f5f9")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)
        style.configure("TLabel", background="#f1f5f9", foreground="#0f172a", font=("Segoe UI", 9))
        style.configure("Card.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#475569", font=("Segoe UI", 8))
        style.configure("Header.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 12, "bold"))
        style.configure("Formula.TLabel", background="#0f172a", foreground="#fde047", font=("Consolas", 9, "bold"))
        style.configure("Section.TLabelframe", background="#ffffff", foreground="#0f172a")
        style.configure("Section.TLabelframe.Label", background="#ffffff", foreground="#1e293b", font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Treeview", font=("Segoe UI", 8), rowheight=22)
        style.configure("Treeview.Heading", font=("Segoe UI", 8, "bold"))

    def _build_layout(self) -> None:
        # 1. Header Bar
        header = tk.Frame(self.root, bg="#0f172a", padx=14, pady=8)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Firefly Algorithm — Penjadwalan Mata Kuliah",
            bg="#0f172a",
            fg="#f8fafc",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text="x_i(t+1) = x_i(t) + β(r)·(x_j - x_i) + α·ε_i   |   β(r) = β₀·e^(-γ·r²)   |   I = 1 / (1 + Penalti)",
            bg="#0f172a",
            fg="#fde047",
            font=("Consolas", 9, "bold"),
        ).pack(side="right")

        # 2. Body Container (Kiri: Kontrol, Kanan: Notebook Visualisasi)
        body = ttk.Frame(self.root, padding=8)
        body.pack(fill="both", expand=True)

        self._build_left_panel(body)
        self._build_right_panel(body)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        left_container = ttk.Frame(parent, width=325)
        left_container.pack(side="left", fill="y", padx=(0, 8))
        left_container.pack_propagate(False)

        # Scrollable sidebar ringan jika layar lebih pendek
        canvas = tk.Canvas(left_container, bg="#f1f5f9", highlightthickness=0, width=310)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        sidebar = ttk.Frame(canvas)

        sidebar.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=sidebar, anchor="nw", width=306)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Kartu 1: Kontrol Simulasi ---
        ctrl_frame = ttk.LabelFrame(sidebar, text=" Kontrol Simulasi (Steps) ", style="Section.TLabelframe", padding=8)
        ctrl_frame.pack(fill="x", pady=(0, 8))

        btn_row1 = tk.Frame(ctrl_frame, bg="#ffffff")
        btn_row1.pack(fill="x", pady=(0, 5))

        self.btn_step = ttk.Button(btn_row1, text="⏭ Step (+1)", style="Accent.TButton", command=self.do_single_step)
        self.btn_step.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_run = ttk.Button(btn_row1, text="▶ Run", style="Accent.TButton", command=self.toggle_run)
        self.btn_run.pack(side="left", fill="x", expand=True, padx=(4, 0))

        btn_row2 = tk.Frame(ctrl_frame, bg="#ffffff")
        btn_row2.pack(fill="x", pady=(0, 6))

        ttk.Button(btn_row2, text="↺ Reset (Base Position)", command=self.reset_simulation).pack(
            side="left", fill="x", expand=True
        )

        # Preset Eksperimen Cepat
        tk.Label(
            ctrl_frame,
            text="Preset Eksperimen (untuk melihat efek parameter):",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(2, 3))

        presets_grid = tk.Frame(ctrl_frame, bg="#ffffff")
        presets_grid.pack(fill="x")

        presets = [
            ("Seimbang (Optimal)", (25, 1.0, 1.5, 0.60, 0.985), "beta0"),
            ("Global (γ=0.2)", (25, 1.1, 0.2, 0.45, 0.98), "gamma"),
            ("Lokal (γ=10)", (25, 1.0, 10.0, 0.30, 0.98), "gamma"),
            ("Minim Acak (α=0.02)", (25, 1.0, 1.5, 0.02, 0.99), "alpha"),
        ]
        for idx, (label, vals, help_key) in enumerate(presets):
            b = ttk.Button(
                presets_grid,
                text=label,
                command=lambda v=vals, hk=help_key: self._apply_preset(v, hk),
            )
            b.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=2, pady=2)
        presets_grid.columnconfigure(0, weight=1)
        presets_grid.columnconfigure(1, weight=1)

        # --- Kartu 2: Status & Metrik Live ---
        metric_frame = ttk.LabelFrame(sidebar, text=" Status Iterasi Live ", style="Section.TLabelframe", padding=8)
        metric_frame.pack(fill="x", pady=(0, 8))

        self.lbl_status_badge = tk.Label(
            metric_frame,
            text="BASE POSITION (Iterasi 0)",
            bg="#e2e8f0",
            fg="#0f172a",
            font=("Segoe UI", 9, "bold"),
            pady=4,
        )
        self.lbl_status_badge.pack(fill="x", pady=(0, 6))

        metrics_grid = tk.Frame(metric_frame, bg="#ffffff")
        metrics_grid.pack(fill="x")
        metrics_grid.columnconfigure(1, weight=1)

        self.metric_vars: Dict[str, tk.StringVar] = {}
        metric_specs = [
            ("iter", "Iterasi (Step):"),
            ("best_pen", "Best Penalty:"),
            ("avg_pen", "Rata-rata Penalty:"),
            ("best_bright", "Best Brightness (I):"),
            ("alpha_cur", "Alpha Aktif (α_t):"),
            ("avg_beta", "Rata-rata β:"),
            ("avg_step", "Rata-rata Step ‖Δx‖:"),
        ]
        for row_idx, (key, title) in enumerate(metric_specs):
            tk.Label(metrics_grid, text=title, bg="#ffffff", fg="#475569", font=("Segoe UI", 8)).grid(
                row=row_idx, column=0, sticky="w", pady=1
            )
            v = tk.StringVar(value="-")
            self.metric_vars[key] = v
            tk.Label(
                metrics_grid, textvariable=v, bg="#ffffff", fg="#0f172a", font=("Consolas", 9, "bold")
            ).grid(row=row_idx, column=1, sticky="e", pady=1)

        # --- Kartu 3: Parameter Firefly ---
        param_frame = ttk.LabelFrame(
            sidebar, text=" Parameter Firefly (Klik/Geser) ", style="Section.TLabelframe", padding=8
        )
        param_frame.pack(fill="x", pady=(0, 8))

        self._add_slider(param_frame, "Jumlah Firefly (N)", self.var_n, 6, 40, 1, "n_fireflies", is_int=True)
        self._add_slider(param_frame, "β₀ (Base Attractiveness)", self.var_beta0, 0.1, 2.0, 0.05, "beta0")
        self._add_slider(param_frame, "γ (Light Absorption)", self.var_gamma, 0.0, 12.0, 0.1, "gamma")
        self._add_slider(param_frame, "α (Random Step)", self.var_alpha, 0.0, 1.0, 0.02, "alpha")
        self._add_slider(param_frame, "α Decay (Peluruhan)", self.var_decay, 0.90, 1.00, 0.005, "alpha_decay")
        self._add_slider(param_frame, "Max Iterasi", self.var_max_iter, 10, 150, 5, "max_iter", is_int=True)
        self._add_slider(param_frame, "Kecepatan (ms/step)", self.var_speed, 40, 800, 20, "max_iter", is_int=True)

        seed_row = tk.Frame(param_frame, bg="#ffffff")
        seed_row.pack(fill="x", pady=(4, 0))
        tk.Label(seed_row, text="Random Seed:", bg="#ffffff", fg="#334155", font=("Segoe UI", 8, "bold")).pack(
            side="left"
        )
        seed_spin = ttk.Spinbox(seed_row, from_=0, to=9999, textvariable=self.var_seed, width=8)
        seed_spin.pack(side="right")
        seed_spin.bind("<FocusIn>", lambda _e: self._show_param_help("seed"))

        # --- Kartu 4: Live Penjelasan Efek Parameter ---
        help_frame = ttk.LabelFrame(
            sidebar, text=" Ngefek ke Mana & Bagaimana? ", style="Section.TLabelframe", padding=8
        )
        help_frame.pack(fill="x", pady=(0, 4))

        self.lbl_help_title = tk.Label(
            help_frame,
            text="",
            bg="#ffffff",
            fg="#0369a1",
            font=("Segoe UI", 8, "bold"),
            justify="left",
            wraplength=280,
        )
        self.lbl_help_title.pack(anchor="w", pady=(0, 4))

        self.lbl_help_body = tk.Label(
            help_frame,
            text="",
            bg="#ffffff",
            fg="#334155",
            font=("Segoe UI", 8),
            justify="left",
            wraplength=280,
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
            v = variable.get()
            if is_int:
                val_lbl.configure(text=f"{int(round(float(v)))}")
            else:
                fmt = "{:.3f}" if resolution < 0.01 else "{:.2f}"
                val_lbl.configure(text=fmt.format(float(v)))
            # Terapkan perubahan parameter secara live ke scheduler jika sudah ada
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
            num = float(raw_val)
            snapped = round(num / resolution) * resolution
            if is_int:
                variable.set(int(round(snapped)))
            else:
                variable.set(round(snapped, 4))
            update_text()
            self._show_param_help(help_key)

        scale = ttk.Scale(block, from_=from_, to=to, orient="horizontal", command=on_scale)
        scale.set(float(variable.get()))
        scale.pack(fill="x")

        # Sinkronkan posisi slider jika preset mengubah variable secara programatik
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

        self.notebook.add(self.tab_main, text="  1. Visualisasi Firefly & Jadwal  ")
        self.notebook.add(self.tab_inspect, text="  2. Bedah Base Position, Attractiveness & Steps  ")
        self.notebook.add(self.tab_guide, text="  3. Penjelasan Konsep & Efek Parameter  ")

        self._build_tab_main()
        self._build_tab_inspect()
        self._build_tab_guide()

    # ------------------------------------------------------------------
    # Tab 1: Canvas Firefly + Grafik Konvergensi + Tabel Jadwal
    # ------------------------------------------------------------------

    def _build_tab_main(self) -> None:
        top_pane = ttk.Frame(self.tab_main)
        top_pane.pack(fill="both", expand=True, pady=(0, 6))
        top_pane.columnconfigure(0, weight=3)
        top_pane.columnconfigure(1, weight=2)
        top_pane.rowconfigure(0, weight=1)

        # Kiri: Canvas Ruang Pencarian Kunang-kunang
        ff_card = ttk.LabelFrame(
            top_pane,
            text=" Ruang Pencarian Firefly (Proyeksi 2D: Base Position → Steps & Panah Attractiveness β) ",
            style="Section.TLabelframe",
            padding=6,
        )
        ff_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.canvas_swarm = tk.Canvas(ff_card, bg="#0b1220", highlightthickness=0, height=270)
        self.canvas_swarm.pack(fill="both", expand=True)
        self.canvas_swarm.bind("<Configure>", lambda _e: self._draw_swarm_canvas())

        legend = tk.Label(
            ff_card,
            text="★ Hijau: Best Firefly   ● Kuning Terang: Penalti Kecil (I tinggi)   ● Redup: Penalti Besar   → Panah: Tarikan Attractiveness (β)   □ Abu: Base Position (t=0)",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8),
        )
        legend.pack(anchor="w", pady=(4, 0))

        # Kanan: Grafik Konvergensi Penalti (Canvas murni Tkinter)
        chart_card = ttk.LabelFrame(
            top_pane,
            text=" Grafik Konvergensi Penalti (Best vs Rata-rata Populasi) ",
            style="Section.TLabelframe",
            padding=6,
        )
        chart_card.grid(row=0, column=1, sticky="nsew")

        self.canvas_chart = tk.Canvas(chart_card, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1", height=270)
        self.canvas_chart.pack(fill="both", expand=True)
        self.canvas_chart.bind("<Configure>", lambda _e: self._draw_convergence_chart())

        chart_legend = tk.Label(
            chart_card,
            text="━━ Hijau: Best Penalty   ━━ Biru: Avg Penalty   --- Garis Target: 0 Konflik",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8),
        )
        chart_legend.pack(anchor="w", pady=(4, 0))

        # Bawah: Tabel Jadwal Terbaik
        sched_card = ttk.LabelFrame(
            self.tab_main,
            text=" Jadwal Terbaik (Hasil Decode Posisi Best Firefly) ",
            style="Section.TLabelframe",
            padding=6,
        )
        sched_card.pack(fill="both", expand=True)

        self.lbl_conflict_summary = tk.Label(
            sched_card,
            text="",
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        self.lbl_conflict_summary.pack(fill="x", pady=(0, 6))

        self.schedule_grid_frame = tk.Frame(sched_card, bg="#cbd5e1", bd=1)
        self.schedule_grid_frame.pack(fill="both", expand=True)

        # Bangun header & cell grid 6 slot x 3 ruangan sekali saja, lalu update isinya
        self.schedule_cells: Dict[Tuple[int, int], tk.Label] = {}
        headers = ["Slot Waktu"] + [f"{r.code}: {r.name}" for r in self.problem.rooms]
        for col, text in enumerate(headers):
            lbl = tk.Label(
                self.schedule_grid_frame,
                text=text,
                bg="#1e293b",
                fg="#f8fafc",
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=5,
            )
            lbl.grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

        self.schedule_grid_frame.columnconfigure(0, weight=1, minsize=105)
        for c in range(1, len(self.problem.rooms) + 1):
            self.schedule_grid_frame.columnconfigure(c, weight=3, minsize=180)

        for r_idx, slot in enumerate(self.problem.slots, start=1):
            self.schedule_grid_frame.rowconfigure(r_idx, weight=1)
            slot_lbl = tk.Label(
                self.schedule_grid_frame,
                text=f"S{slot.index} • {slot.label}",
                bg="#e2e8f0",
                fg="#0f172a",
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=4,
            )
            slot_lbl.grid(row=r_idx, column=0, sticky="nsew", padx=1, pady=1)

            for c_idx in range(len(self.problem.rooms)):
                cell = tk.Label(
                    self.schedule_grid_frame,
                    text="—",
                    bg="#f8fafc",
                    fg="#64748b",
                    font=("Segoe UI", 8),
                    justify="left",
                    anchor="w",
                    padx=6,
                    pady=3,
                    wraplength=240,
                )
                cell.grid(row=r_idx, column=c_idx + 1, sticky="nsew", padx=1, pady=1)
                self.schedule_cells[(slot.index, c_idx)] = cell

    # ------------------------------------------------------------------
    # Tab 2: Bedah Base Position, Attractiveness & Steps
    # ------------------------------------------------------------------

    def _build_tab_inspect(self) -> None:
        # Bagian Atas: Base Position vs Current Position
        pos_card = ttk.LabelFrame(
            self.tab_inspect,
            text=" 1. Bedah Base Position (Iterasi 0) → Current Position & Decoding ke Jadwal ",
            style="Section.TLabelframe",
            padding=8,
        )
        pos_card.pack(fill="both", expand=True, pady=(0, 8))

        picker_row = tk.Frame(pos_card, bg="#ffffff")
        picker_row.pack(fill="x", pady=(0, 6))

        tk.Label(
            picker_row,
            text="Pilih Firefly untuk dibedah:",
            bg="#ffffff",
            fg="#1e293b",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        self.cmb_firefly = ttk.Combobox(
            picker_row, textvariable=self.var_inspect_ff, state="readonly", width=26
        )
        self.cmb_firefly.pack(side="left", padx=8)
        self.cmb_firefly.bind("<<ComboboxSelected>>", lambda _e: self._update_inspector_tables())

        self.lbl_ff_summary = tk.Label(
            picker_row, text="", bg="#ffffff", fg="#0369a1", font=("Consolas", 8, "bold")
        )
        self.lbl_ff_summary.pack(side="right")

        cols_pos = (
            "mk",
            "info",
            "base_slot",
            "cur_slot",
            "base_room",
            "cur_room",
            "status",
        )
        self.tree_pos = ttk.Treeview(pos_card, columns=cols_pos, show="headings", height=10)
        headings_pos = {
            "mk": ("Mata Kuliah", 150),
            "info": ("Dosen / Kelas (Mhs)", 155),
            "base_slot": ("Base x_slot (t=0) → Slot", 145),
            "cur_slot": ("Current x_slot → Slot", 145),
            "base_room": ("Base x_room (t=0) → Ruang", 145),
            "cur_room": ("Current x_room → Ruang", 145),
            "status": ("Status Jadwal", 170),
        }
        for col, (text, width) in headings_pos.items():
            self.tree_pos.heading(col, text=text)
            self.tree_pos.column(col, width=width, anchor="w")

        pos_scroll = ttk.Scrollbar(pos_card, orient="vertical", command=self.tree_pos.yview)
        self.tree_pos.configure(yscrollcommand=pos_scroll.set)
        self.tree_pos.pack(side="left", fill="both", expand=True)
        pos_scroll.pack(side="right", fill="y")

        self.tree_pos.tag_configure("ok", background="#ecfdf5", foreground="#065f46")
        self.tree_pos.tag_configure("warn", background="#fef3c7", foreground="#92400e")
        self.tree_pos.tag_configure("err", background="#fee2e2", foreground="#991b1b")

        # Bagian Bawah: Log Attractiveness & Steps
        move_card = ttk.LabelFrame(
            self.tab_inspect,
            text=" 2. Log Attractiveness (β) & Steps (Δx = Tarikan + Acak) pada Iterasi Terakhir ",
            style="Section.TLabelframe",
            padding=8,
        )
        move_card.pack(fill="both", expand=True)

        self.lbl_move_note = tk.Label(
            move_card,
            text="Tekan 'Step (+1)' atau 'Run' untuk melihat interaksi tarikan antar kunang-kunang pada iterasi aktif.",
            bg="#ffffff",
            fg="#475569",
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.lbl_move_note.pack(fill="x", pady=(0, 4))

        cols_mov = (
            "pair",
            "bright",
            "dist",
            "beta",
            "step_att",
            "step_rnd",
            "step_tot",
            "pen_change",
        )
        self.tree_moves = ttk.Treeview(move_card, columns=cols_mov, show="headings", height=10)
        headings_mov = {
            "pair": ("Firefly i → Penarik j", 160),
            "bright": ("Brightness (I_i → I_j)", 140),
            "dist": ("Jarak (r)", 75),
            "beta": ("Attractiveness (β)", 115),
            "step_att": ("Step Tarikan", 95),
            "step_rnd": ("Step Acak (α·ε)", 100),
            "step_tot": ("Total Step ‖Δx‖", 105),
            "pen_change": ("Penalti (Before → After)", 150),
        }
        for col, (text, width) in headings_mov.items():
            self.tree_moves.heading(col, text=text)
            self.tree_moves.column(col, width=width, anchor="center")

        mov_scroll = ttk.Scrollbar(move_card, orient="vertical", command=self.tree_moves.yview)
        self.tree_moves.configure(yscrollcommand=mov_scroll.set)
        self.tree_moves.pack(side="left", fill="both", expand=True)
        mov_scroll.pack(side="right", fill="y")

        self.tree_moves.tag_configure("better", background="#ecfdf5", foreground="#065f46")
        self.tree_moves.tag_configure("same", background="#f8fafc", foreground="#334155")
        self.tree_moves.tag_configure("worse", background="#fff1f2", foreground="#9f1239")

    # ------------------------------------------------------------------
    # Tab 3: Penjelasan Konsep & Cheat Sheet Presentasi
    # ------------------------------------------------------------------

    def _build_tab_guide(self) -> None:
        guide_card = ttk.LabelFrame(
            self.tab_guide,
            text=" Materi Ringkas: Base Position, Attractiveness, Steps & Efek Parameter ",
            style="Section.TLabelframe",
            padding=8,
        )
        guide_card.pack(fill="both", expand=True)

        text = tk.Text(
            guide_card,
            wrap="word",
            font=("Consolas", 9),
            bg="#ffffff",
            fg="#0f172a",
            padx=12,
            pady=10,
            relief="flat",
        )
        scroll = ttk.Scrollbar(guide_card, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", GUIDE_TEXT)
        text.configure(state="disabled")

        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Logika Kontrol Simulasi
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
        self.scheduler = FireflyScheduler(
            problem=self.problem,
            n_fireflies=int(self.var_n.get()),
            beta0=float(self.var_beta0.get()),
            gamma=float(self.var_gamma.get()),
            alpha=float(self.var_alpha.get()),
            alpha_decay=float(self.var_decay.get()),
            seed=int(self.var_seed.get()),
        )
        # Update dropdown pilihan firefly di Tab 2
        options = ["★ Best Firefly"] + [f"Firefly F{ff.id}" for ff in self.scheduler.fireflies]
        self.cmb_firefly.configure(values=options)
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
            self.scheduler.best_firefly and self.scheduler.best_firefly.penalty == 0
        ):
            self._stop_run()
            self._refresh_all_views()
            return

        self.scheduler.step()
        self._refresh_all_views()

        if self.scheduler.best_firefly and self.scheduler.best_firefly.penalty == 0:
            self._stop_run()
            return

        delay = max(30, int(self.var_speed.get()))
        self.after_id = self.root.after(delay, self._run_loop)

    # ------------------------------------------------------------------
    # Pembaruan Tampilan (Metrics, Canvas, Grafik, Jadwal, Inspector)
    # ------------------------------------------------------------------

    def _refresh_all_views(self) -> None:
        if self.scheduler is None:
            return
        self._update_metrics()
        self._draw_swarm_canvas()
        self._draw_convergence_chart()
        self._update_schedule_grid()
        self._update_inspector_tables()

    def _update_metrics(self) -> None:
        assert self.scheduler is not None
        best = self.scheduler.best_firefly
        assert best is not None

        it = self.scheduler.iteration
        max_it = int(self.var_max_iter.get())
        avg_pen = self.scheduler.avg_penalty_history[-1]
        avg_beta = self.scheduler.avg_beta_history[-1]
        avg_step = self.scheduler.avg_step_history[-1]

        self.metric_vars["iter"].set(f"{it} / {max_it}")
        self.metric_vars["best_pen"].set(f"{best.penalty}")
        self.metric_vars["avg_pen"].set(f"{avg_pen:.2f}")
        self.metric_vars["best_bright"].set(f"{best.brightness:.4f}")
        self.metric_vars["alpha_cur"].set(f"{self.scheduler.alpha:.3f}")
        self.metric_vars["avg_beta"].set(f"{avg_beta:.3f}")
        self.metric_vars["avg_step"].set(f"{avg_step:.4f}")

        if best.penalty == 0:
            self.lbl_status_badge.configure(
                text=f"✓ OPTIMAL! 0 Konflik (Iterasi {it})",
                bg="#dcfce7",
                fg="#166534",
            )
        elif it == 0:
            self.lbl_status_badge.configure(
                text=f"BASE POSITION — Penalti Awal: {best.penalty}",
                bg="#e0f2fe",
                fg="#075985",
            )
        else:
            hard = best.report.hard_conflicts if best.report else 0
            soft = best.report.capacity_violations if best.report else 0
            self.lbl_status_badge.configure(
                text=f"Iterasi {it} — Hard: {hard} | Soft Kapasitas: {soft}",
                bg="#fef3c7" if hard == 0 else "#fee2e2",
                fg="#92400e" if hard == 0 else "#991b1b",
            )

    def _draw_swarm_canvas(self) -> None:
        c = self.canvas_swarm
        c.delete("all")
        if self.scheduler is None:
            return

        w = max(200, c.winfo_width())
        h = max(160, c.winfo_height())
        pad_l, pad_r, pad_t, pad_b = 42, 20, 22, 30
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        def to_xy(px: float, py: float) -> Tuple[float, float]:
            # Fokuskan ke area [0.1, 0.9] agar sebaran rata-rata 10 MK terlihat lebar & tidak menumpuk di tengah
            nx = max(0.0, min(1.0, (px - 0.15) / 0.70))
            ny = max(0.0, min(1.0, (py - 0.15) / 0.70))
            return (pad_l + nx * plot_w, pad_t + (1.0 - ny) * plot_h)

        # Grid latar malam
        for step_i in range(5):
            frac = step_i / 4.0
            gx = pad_l + frac * plot_w
            gy = pad_t + frac * plot_h
            c.create_line(gx, pad_t, gx, pad_t + plot_h, fill="#1e293b", dash=(2, 4))
            c.create_line(pad_l, gy, pad_l + plot_w, gy, fill="#1e293b", dash=(2, 4))

        # Sumbu
        c.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#334155")
        c.create_text(
            pad_l + plot_w / 2,
            h - 10,
            text="Rata-rata Posisi Slot Waktu (x genap)",
            fill="#94a3b8",
            font=("Segoe UI", 8),
        )
        c.create_text(
            14,
            pad_t + plot_h / 2,
            text="Rata-rata Ruang",
            fill="#94a3b8",
            font=("Segoe UI", 8),
            angle=90,
        )

        # Lookup posisi firefly sekarang
        ff_by_id = {ff.id: ff for ff in self.scheduler.fireflies}
        best_id = self.scheduler.best_firefly.id if self.scheduler.best_firefly else -1

        # 1. Gambar Base Position (t=0) dan Jejak Steps
        for ff in self.scheduler.fireflies:
            bx, by = to_xy(*self.scheduler.project_2d(ff.base_position))
            c.create_rectangle(bx - 2, by - 2, bx + 2, by + 2, outline="#475569", fill="")

            if len(ff.trail_2d) > 1:
                pts: List[float] = []
                for tp in ff.trail_2d[-12:]:
                    tx, ty = to_xy(*tp)
                    pts.extend([tx, ty])
                trail_col = "#14532d" if ff.id == best_id else "#1e3a5f"
                c.create_line(*pts, fill=trail_col, width=1.5 if ff.id == best_id else 1)

        # 2. Gambar panah Attractiveness (β) pada step terakhir (maksimal 12 panah terkuat agar bersih)
        moves = [m for m in self.scheduler.last_movements if not m.is_self_exploration]
        moves_sorted = sorted(moves, key=lambda m: m.attractiveness_beta, reverse=True)[:12]
        for m in moves_sorted:
            mover = ff_by_id.get(m.mover_id)
            att = ff_by_id.get(m.attractor_id)
            if mover is None or att is None:
                continue
            x1, y1 = to_xy(*self.scheduler.project_2d(mover.prev_position))
            x2, y2 = to_xy(*self.scheduler.project_2d(att.prev_position))
            if abs(x2 - x1) + abs(y2 - y1) > 4:
                c.create_line(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="#38bdf8",
                    width=max(1, min(2.5, m.attractiveness_beta * 2.0)),
                    arrow=tk.LAST,
                    arrowshape=(7, 9, 3),
                )

        # 3. Gambar titik Firefly dengan kecerahan proporsional terhadap brightness I
        max_b = max((ff.brightness for ff in self.scheduler.fireflies), default=1.0)
        min_b = min((ff.brightness for ff in self.scheduler.fireflies), default=0.0)
        span_b = max(1e-6, max_b - min_b)

        for ff in self.scheduler.fireflies:
            cx, cy = to_xy(*self.scheduler.project_2d(ff.position))
            norm = (ff.brightness - min_b) / span_b if span_b > 1e-5 else 1.0
            rad = 4 + norm * 5.5

            # Halo cahaya
            if norm > 0.35 or ff.id == best_id:
                halo_r = rad + 4 + norm * 4
                halo_col = "#166534" if ff.id == best_id else "#713f12"
                c.create_oval(
                    cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r, fill=halo_col, outline=""
                )

            # Warna inti dari redup (abu-amber) ke sangat terang (kuning emas)
            if ff.id == best_id:
                core_col = "#4ade80"
                outline_col = "#ffffff"
            else:
                r_col = int(120 + norm * 135)
                g_col = int(110 + norm * 130)
                b_col = int(70 - norm * 40)
                core_col = f"#{r_col:02x}{g_col:02x}{max(0, b_col):02x}"
                outline_col = "#fef08a" if norm > 0.6 else "#64748b"

            c.create_oval(
                cx - rad, cy - rad, cx + rad, cy + rad, fill=core_col, outline=outline_col, width=1.5
            )
            c.create_text(
                cx,
                cy - rad - 7,
                text=f"★F{ff.id}" if ff.id == best_id else f"F{ff.id}",
                fill="#86efac" if ff.id == best_id else "#cbd5e1",
                font=("Consolas", 7, "bold" if ff.id == best_id else "normal"),
            )

        # Info iterasi di pojok kiri atas canvas
        c.create_text(
            pad_l + 6,
            11,
            anchor="w",
            text=f"Iterasi t={self.scheduler.iteration} | N={len(self.scheduler.fireflies)} | α_t={self.scheduler.alpha:.3f} | γ={self.scheduler.gamma:.2f} | β₀={self.scheduler.beta0:.2f}",
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
        pad_l, pad_r, pad_t, pad_b = 42, 18, 22, 28
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        best_hist = self.scheduler.best_penalty_history
        avg_hist = self.scheduler.avg_penalty_history
        max_x = max(10, int(self.var_max_iter.get()), len(best_hist) - 1)
        max_y = max(10.0, max(avg_hist) * 1.12, max(best_hist) * 1.12)

        def to_xy(it: int, val: float) -> Tuple[float, float]:
            x = pad_l + (it / max_x) * plot_w
            y = pad_t + (1.0 - val / max_y) * plot_h
            return (x, y)

        # Grid Y & label penalti
        for i in range(5):
            val = max_y * (i / 4.0)
            _, gy = to_xy(0, val)
            c.create_line(pad_l, gy, pad_l + plot_w, gy, fill="#e2e8f0")
            c.create_text(pad_l - 6, gy, text=f"{val:.0f}", anchor="e", fill="#64748b", font=("Consolas", 8))

        # Garis target penalti = 0
        _, y0 = to_xy(0, 0)
        c.create_line(pad_l, y0, pad_l + plot_w, y0, fill="#22c55e", dash=(4, 3), width=1.5)

        # Sumbu X
        c.create_rectangle(pad_l, pad_t, pad_l + plot_w, pad_t + plot_h, outline="#94a3b8")
        c.create_text(
            pad_l + plot_w / 2, h - 10, text="Iterasi (Steps)", fill="#475569", font=("Segoe UI", 8)
        )
        c.create_text(pad_l, h - 10, text="0", fill="#64748b", font=("Consolas", 8))
        c.create_text(pad_l + plot_w, h - 10, text=str(max_x), fill="#64748b", font=("Consolas", 8))

        # Kurva Average Penalty (biru)
        if len(avg_hist) > 1:
            pts_avg: List[float] = []
            for idx, val in enumerate(avg_hist):
                pts_avg.extend(to_xy(idx, val))
            c.create_line(*pts_avg, fill="#3b82f6", width=2)
        else:
            ax, ay = to_xy(0, avg_hist[0])
            c.create_oval(ax - 3, ay - 3, ax + 3, ay + 3, fill="#3b82f6", outline="")

        # Kurva Best Penalty (hijau)
        if len(best_hist) > 1:
            pts_best: List[float] = []
            for idx, val in enumerate(best_hist):
                pts_best.extend(to_xy(idx, val))
            c.create_line(*pts_best, fill="#16a34a", width=2.5)
        bx, by = to_xy(len(best_hist) - 1, best_hist[-1])
        c.create_oval(bx - 4, by - 4, bx + 4, by + 4, fill="#16a34a", outline="#ffffff", width=1.5)
        c.create_text(
            min(pad_l + plot_w - 28, bx + 10),
            max(pad_t + 10, by - 10),
            text=f"Best: {best_hist[-1]}",
            fill="#15803d",
            font=("Consolas", 8, "bold"),
            anchor="w",
        )

    def _update_schedule_grid(self) -> None:
        assert self.scheduler is not None
        best = self.scheduler.best_firefly
        assert best is not None and best.report is not None

        rep = best.report
        if rep.total_penalty == 0:
            self.lbl_conflict_summary.configure(
                text=f"★ Best Firefly F{best.id} — SEMPURNA! 0 Bentrok Ruang | 0 Bentrok Dosen | 0 Bentrok Kelas | 0 Pelanggaran Kapasitas (Penalti = 0)",
                fg="#166534",
            )
        else:
            self.lbl_conflict_summary.configure(
                text=(
                    f"★ Best Firefly F{best.id} — Penalti: {rep.total_penalty}  |  "
                    f"Bentrok Ruang: {rep.room_conflicts} (+10)  •  "
                    f"Bentrok Dosen: {rep.lecturer_conflicts} (+10)  •  "
                    f"Bentrok Kelas: {rep.group_conflicts} (+10)  •  "
                    f"Kapasitas Kurang: {rep.capacity_violations} (+3)"
                ),
                fg="#991b1b" if rep.hard_conflicts > 0 else "#92400e",
            )

        assignments = self.problem.decode(best.position)
        cell_map: Dict[Tuple[int, int], List[int]] = {}
        for c_idx, (slot_idx, room_idx) in enumerate(assignments):
            cell_map.setdefault((slot_idx, room_idx), []).append(c_idx)

        for (slot_idx, room_idx), lbl in self.schedule_cells.items():
            c_indices = cell_map.get((slot_idx, room_idx), [])
            if not c_indices:
                lbl.configure(text="— (Kosong)", bg="#f8fafc", fg="#94a3b8")
                continue

            lines: List[str] = []
            has_hard = False
            has_soft = False
            for ci in c_indices:
                course = self.problem.courses[ci]
                reasons = rep.conflicting_courses.get(ci, [])
                for r_txt in reasons:
                    if r_txt.startswith("Bentrok"):
                        has_hard = True
                    else:
                        has_soft = True
                suffix = f"  ⚠ {'; '.join(reasons)}" if reasons else "  ✓"
                lines.append(
                    f"{course.code} {course.name} ({course.lecturer}, {course.student_group}/{course.students} mhs){suffix}"
                )

            if has_hard:
                bg, fg = "#fee2e2", "#991b1b"
            elif has_soft:
                bg, fg = "#fef3c7", "#92400e"
            else:
                bg, fg = "#dcfce7", "#166534"

            lbl.configure(text="\n".join(lines), bg=bg, fg=fg)

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

        # 1. Tabel Base Position -> Current Position
        for item in self.tree_pos.get_children():
            self.tree_pos.delete(item)

        ff = self._get_selected_firefly()
        if ff is not None and ff.report is not None:
            base_assign = self.problem.decode(ff.base_position)
            cur_assign = self.problem.decode(ff.position)
            dist_from_base = self.scheduler.normalized_distance(ff.base_position, ff.position)

            self.lbl_ff_summary.configure(
                text=(
                    f"F{ff.id} | Penalty: {ff.penalty} | Brightness I: {ff.brightness:.4f} | "
                    f"Pergeseran dari Base Pos: {dist_from_base:.3f}"
                )
            )

            for k, course in enumerate(self.problem.courses):
                b_slot, b_room = base_assign[k]
                c_slot, c_room = cur_assign[k]
                reasons = ff.report.conflicting_courses.get(k, [])
                if not reasons:
                    status, tag = "✓ Valid (0 konflik)", "ok"
                elif any(r.startswith("Bentrok") for r in reasons):
                    status, tag = "✗ " + ", ".join(reasons), "err"
                else:
                    status, tag = "⚠ " + ", ".join(reasons), "warn"

                self.tree_pos.insert(
                    "",
                    "end",
                    values=(
                        f"{course.code} {course.name}",
                        f"{course.lecturer} | {course.student_group} ({course.students})",
                        f"{ff.base_position[2*k]:.2f} → S{b_slot} ({self.problem.slots[b_slot].day} {self.problem.slots[b_slot].session})",
                        f"{ff.position[2*k]:.2f} → S{c_slot} ({self.problem.slots[c_slot].day} {self.problem.slots[c_slot].session})",
                        f"{ff.base_position[2*k+1]:.2f} → {self.problem.rooms[b_room].code}",
                        f"{ff.position[2*k+1]:.2f} → {self.problem.rooms[c_room].code}",
                        status,
                    ),
                    tags=(tag,),
                )

        # 2. Tabel Log Attractiveness & Steps (Iterasi Terakhir)
        for item in self.tree_moves.get_children():
            self.tree_moves.delete(item)

        moves = self.scheduler.last_movements
        if not moves:
            self.lbl_move_note.configure(
                text="Iterasi 0 (Base Position): belum ada pergerakan. Klik 'Step (+1)' untuk melihat tarikan Attractiveness (β) dan Steps (Δx)!"
            )
            return

        improved = sum(1 for m in moves if m.penalty_after < m.penalty_before)
        self.lbl_move_note.configure(
            text=(
                f"Iterasi {self.scheduler.iteration}: tercatat {len(moves)} pergerakan "
                f"({improved} membaik penaltinya) | Rumus: β(r) = {self.scheduler.beta0:.2f}·e^(-{self.scheduler.gamma:.2f}·r²), α = {self.scheduler.alpha:.3f}"
            )
        )

        # Urutkan agar yang membaik dan beta terbesar muncul di atas
        sorted_moves = sorted(
            moves,
            key=lambda m: (m.penalty_after - m.penalty_before, -m.attractiveness_beta),
        )
        for m in sorted_moves:
            if m.is_self_exploration:
                pair_txt = f"★ F{m.mover_id} (Eksplorasi Mandiri)"
            else:
                pair_txt = f"F{m.mover_id} → F{m.attractor_id}"

            diff = m.penalty_after - m.penalty_before
            if diff < 0:
                pen_txt = f"{m.penalty_before} → {m.penalty_after} (Membaik {diff})"
                tag = "better"
            elif diff == 0:
                pen_txt = f"{m.penalty_before} → {m.penalty_after} (Tetap)"
                tag = "same"
            else:
                pen_txt = f"{m.penalty_before} → {m.penalty_after} (+{diff})"
                tag = "worse"

            self.tree_moves.insert(
                "",
                "end",
                values=(
                    pair_txt,
                    f"{m.mover_brightness_before:.3f} → {m.attractor_brightness:.3f}",
                    f"{m.distance_r:.3f}",
                    f"{m.attractiveness_beta:.4f}",
                    f"{m.attraction_step_mag:.4f}",
                    f"{m.random_step_mag:.4f}",
                    f"{m.total_step_mag:.4f}",
                    pen_txt,
                ),
                tags=(tag,),
            )


def main() -> None:
    root = tk.Tk()
    FireflyTkinterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
