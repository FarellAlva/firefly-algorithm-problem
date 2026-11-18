"""
Firefly Algorithm untuk Penjadwalan 4 Tugas pada 1 Mesin (Anti-Overlap & Anti-Telat).
Pure Python standard library (tanpa dependensi eksternal).

Model Opsi 2 (Kontinu 4 Dimensi — Sangat Intuitif):
1. Base Position (x_i):
   Vektor 4 angka kontinu [t_1, t_2, t_3, t_4] yang LANGSUNG menyatakan
   jam mulai masing-masing tugas (T1..T4) dalam jam operasional 08:00 - 17:00.
2. Evaluasi Penalti (Cost f(x)):
   Hanya 2 aturan sederhana:
   - Overlap (bentrok waktu di 1 mesin)  : bobot 10.0 per jam tumpang tindih
   - Lateness (melewati deadline tugas)  : bobot  6.0 per jam keterlambatan
   Total Penalti: f(x) = 10.0 * Overlap + 6.0 * Lateness
3. Light Intensity / Brightness (I):
   I(x_i) = 1 / (1 + f(x_i))
   Penalti = 0.00 -> I = 1.0000 (paling terang / jadwal optimal).
4. Attractiveness (beta):
   beta(r) = beta0 * exp(-gamma * r^2)
   dengan r = jarak Euclidean ternormalisasi di [0, 1].
5. Steps / Movement (Delta x):
   t_new = t_old + beta(r) * (t_j - t_i) + alpha * (rand - 0.5) * span
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


WORK_START = 8.0   # 08:00
WORK_END = 17.0    # 17:00


def format_hour(hour_float: float) -> str:
    """Mengubah jam desimal (misal 10.5) menjadi format HH:MM ('10:30')."""
    total_minutes = int(round(hour_float * 60))
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


@dataclass(frozen=True)
class Task:
    code: str
    name: str
    duration: float     # jam
    ready_time: float   # jam paling awal boleh mulai
    deadline: float     # jam maksimal harus selesai
    color: str          # warna balok di Gantt Chart

    @property
    def min_start(self) -> float:
        return self.ready_time

    @property
    def max_start(self) -> float:
        return WORK_END - self.duration

    @property
    def span(self) -> float:
        return max(0.5, self.max_start - self.min_start)


@dataclass
class TaskStatus:
    task_index: int
    start: float
    end: float
    overlap_hours: float
    lateness_hours: float
    overlaps_with: List[str]

    @property
    def is_valid(self) -> bool:
        return self.overlap_hours < 1e-4 and self.lateness_hours < 1e-4


@dataclass
class ScheduleReport:
    total_overlap_hours: float
    total_lateness_hours: float
    overlap_pairs: int
    late_tasks: int
    total_penalty: float
    task_statuses: List[TaskStatus]

    @property
    def is_optimal(self) -> bool:
        return self.total_penalty < 0.05


@dataclass
class MovementRecord:
    """Mencatat 1 peristiwa tarikan/langkah dari firefly i menuju firefly j."""

    iteration: int
    mover_id: int
    attractor_id: int
    is_self_exploration: bool
    mover_brightness_before: float
    attractor_brightness: float
    distance_r: float
    attractiveness_beta: float
    attraction_step_hours: float
    random_step_hours: float
    total_step_hours: float
    penalty_before: float
    penalty_after: float


@dataclass
class Firefly:
    id: int
    base_position: List[float]  # [t1, t2, t3, t4] pada iterasi 0
    position: List[float]       # [t1, t2, t3, t4] saat ini
    prev_position: List[float]  # [t1, t2, t3, t4] sebelum step terakhir
    penalty: float = 0.0
    brightness: float = 0.0
    report: Optional[ScheduleReport] = None
    last_attractor_id: Optional[int] = None
    last_distance_r: float = 0.0
    last_beta: float = 0.0
    last_step_hours: float = 0.0
    trail_2d: List[Tuple[float, float]] = field(default_factory=list)


DEFAULT_TASKS: List[Task] = [
    Task("T1", "Pemotongan Rangka", 2.0, 8.0, 12.0, "#3b82f6"),
    Task("T2", "Perakitan Komponen", 1.5, 8.0, 13.5, "#8b5cf6"),
    Task("T3", "Kalibrasi & Uji Beban", 2.5, 9.0, 16.0, "#06b6d4"),
    Task("T4", "Finishing & Packing", 1.5, 10.0, 17.0, "#10b981"),
]


class JobSchedulingProblem:
    """Masalah penjadwalan 4 tugas di 1 mesin: anti-overlap & anti-telat."""

    OVERLAP_WEIGHT = 10.0   # penalti per jam tumpang tindih
    LATENESS_WEIGHT = 6.0   # penalti per jam melewati deadline

    def __init__(self, tasks: Optional[List[Task]] = None) -> None:
        self.tasks = tasks or list(DEFAULT_TASKS)
        self.dimension = len(self.tasks)

    def clamp(self, position: List[float]) -> List[float]:
        clamped: List[float] = []
        for val, task in zip(position, self.tasks):
            clamped.append(max(task.min_start, min(task.max_start, val)))
        return clamped

    def evaluate(self, position: List[float]) -> ScheduleReport:
        n = len(self.tasks)
        starts = list(position)
        ends = [starts[k] + self.tasks[k].duration for k in range(n)]

        overlap_per_task = [0.0] * n
        overlap_names: List[List[str]] = [[] for _ in range(n)]
        total_overlap = 0.0
        overlap_pairs = 0

        for a in range(n):
            for b in range(a + 1, n):
                ov = min(ends[a], ends[b]) - max(starts[a], starts[b])
                if ov > 1e-4:
                    total_overlap += ov
                    overlap_pairs += 1
                    overlap_per_task[a] += ov
                    overlap_per_task[b] += ov
                    overlap_names[a].append(self.tasks[b].code)
                    overlap_names[b].append(self.tasks[a].code)

        total_lateness = 0.0
        late_tasks = 0
        statuses: List[TaskStatus] = []

        for k in range(n):
            late = max(0.0, ends[k] - self.tasks[k].deadline)
            if late > 1e-4:
                total_lateness += late
                late_tasks += 1
            statuses.append(
                TaskStatus(
                    task_index=k,
                    start=starts[k],
                    end=ends[k],
                    overlap_hours=overlap_per_task[k],
                    lateness_hours=late,
                    overlaps_with=overlap_names[k],
                )
            )

        total_penalty = (
            self.OVERLAP_WEIGHT * total_overlap + self.LATENESS_WEIGHT * total_lateness
        )
        return ScheduleReport(
            total_overlap_hours=total_overlap,
            total_lateness_hours=total_lateness,
            overlap_pairs=overlap_pairs,
            late_tasks=late_tasks,
            total_penalty=total_penalty,
            task_statuses=statuses,
        )

    @staticmethod
    def brightness_from_penalty(penalty: float) -> float:
        return 1.0 / (1.0 + penalty)


class FireflyJobScheduler:
    """Mesin Firefly Algorithm kontinu 4D untuk penjadwalan 4 tugas."""

    def __init__(
        self,
        problem: Optional[JobSchedulingProblem] = None,
        n_fireflies: int = 20,
        beta0: float = 1.0,
        gamma: float = 1.5,
        alpha: float = 0.35,
        alpha_decay: float = 0.96,
        seed: int = 42,
    ) -> None:
        self.problem = problem or JobSchedulingProblem()
        self.n_fireflies = n_fireflies
        self.beta0 = beta0
        self.gamma = gamma
        self.alpha_init = alpha
        self.alpha = alpha
        self.alpha_decay = alpha_decay
        self.seed = seed

        self.rng = random.Random(seed)
        self.iteration = 0
        self.fireflies: List[Firefly] = []
        self.best_firefly: Optional[Firefly] = None

        self.best_penalty_history: List[float] = []
        self.avg_penalty_history: List[float] = []
        self.avg_beta_history: List[float] = []
        self.avg_step_history: List[float] = []
        self.last_movements: List[MovementRecord] = []

        self.initialize()

    def normalized_distance(self, pos_a: List[float], pos_b: List[float]) -> float:
        """Jarak Euclidean ternormalisasi ke [0, 1] berdasarkan span tiap tugas."""
        sq = 0.0
        for a, b, task in zip(pos_a, pos_b, self.problem.tasks):
            diff = (a - b) / task.span
            sq += diff * diff
        return math.sqrt(sq / len(self.problem.tasks))

    def compute_attractiveness(self, r: float) -> float:
        """Rumus Attractiveness FA: beta(r) = beta0 * exp(-gamma * r^2)."""
        return self.beta0 * math.exp(-self.gamma * (r ** 2))

    def project_2d(self, position: List[float]) -> Tuple[float, float]:
        """
        Proyeksi 2D intuitif untuk Canvas Firefly:
        - Sumbu X: rata-rata jam mulai Tugas Awal (T1 & T2)
        - Sumbu Y: rata-rata jam mulai Tugas Lanjut (T3 & T4)
        """
        x_val = 0.5 * (position[0] + position[1])
        y_val = 0.5 * (position[2] + position[3])
        return (x_val, y_val)

    def _evaluate_firefly(self, ff: Firefly) -> None:
        rep = self.problem.evaluate(ff.position)
        ff.report = rep
        ff.penalty = rep.total_penalty
        ff.brightness = self.problem.brightness_from_penalty(ff.penalty)

    def _clone_firefly(self, ff: Firefly) -> Firefly:
        return Firefly(
            id=ff.id,
            base_position=list(ff.base_position),
            position=list(ff.position),
            prev_position=list(ff.prev_position),
            penalty=ff.penalty,
            brightness=ff.brightness,
            report=ff.report,
            last_attractor_id=ff.last_attractor_id,
            last_distance_r=ff.last_distance_r,
            last_beta=ff.last_beta,
            last_step_hours=ff.last_step_hours,
            trail_2d=list(ff.trail_2d),
        )

    def _update_best(self) -> None:
        current_best = min(self.fireflies, key=lambda f: f.penalty)
        if self.best_firefly is None or current_best.penalty <= self.best_firefly.penalty:
            self.best_firefly = self._clone_firefly(current_best)

    def _avg_penalty(self) -> float:
        return sum(f.penalty for f in self.fireflies) / len(self.fireflies)

    def initialize(self) -> None:
        """Membentuk Base Position acak [t1, t2, t3, t4] pada iterasi 0."""
        self.rng = random.Random(self.seed)
        self.iteration = 0
        self.alpha = self.alpha_init
        self.fireflies = []
        self.last_movements = []
        self.best_firefly = None

        for i in range(self.n_fireflies):
            base_pos = [
                task.min_start + self.rng.random() * task.span
                for task in self.problem.tasks
            ]
            ff = Firefly(
                id=i,
                base_position=list(base_pos),
                position=list(base_pos),
                prev_position=list(base_pos),
            )
            self._evaluate_firefly(ff)
            ff.trail_2d = [self.project_2d(ff.position)]
            self.fireflies.append(ff)

        self._update_best()
        self.best_penalty_history = [self.best_firefly.penalty]
        self.avg_penalty_history = [self._avg_penalty()]
        self.avg_beta_history = [0.0]
        self.avg_step_history = [0.0]

    def step(self) -> List[MovementRecord]:
        """
        Menjalankan 1 iterasi Firefly Algorithm:
        - Setiap firefly i mencari penarik j yang lebih terang (I_j > I_i)
          dengan daya tarik efektif beta(r_ij) * I_j terbesar.
        - Posisi jam mulai diperbarui:
          t_new = t_old + beta(r) * (t_j - t_i) + alpha * (rand - 0.5) * span
        - Firefly paling terang melakukan eksplorasi lokal kecil (greedy).
        """
        self.iteration += 1
        n = len(self.fireflies)
        dim = self.problem.dimension
        movements: List[MovementRecord] = []

        old_positions = [list(ff.position) for ff in self.fireflies]
        old_brightness = [ff.brightness for ff in self.fireflies]

        for i in range(n):
            ff_i = self.fireflies[i]
            ff_i.prev_position = list(old_positions[i])
            pen_before = ff_i.penalty
            bri_before = old_brightness[i]

            brighters = [j for j in range(n) if old_brightness[j] > bri_before + 1e-9]

            if not brighters:
                ff_i.last_attractor_id = ff_i.id
                ff_i.last_distance_r = 0.0
                ff_i.last_beta = 0.0

                if ff_i.penalty >= 0.05:
                    cand = list(old_positions[i])
                    rand_sq = 0.0
                    for d, task in enumerate(self.problem.tasks):
                        rc = self.alpha * (self.rng.random() - 0.5) * task.span * 0.6
                        cand[d] = max(task.min_start, min(task.max_start, cand[d] + rc))
                        rand_sq += rc * rc
                    cand_rep = self.problem.evaluate(cand)
                    if cand_rep.total_penalty <= ff_i.penalty:
                        tot_hr = math.sqrt(
                            sum((cand[d] - old_positions[i][d]) ** 2 for d in range(dim)) / dim
                        )
                        rnd_hr = math.sqrt(rand_sq / dim)
                        ff_i.position = cand
                        ff_i.report = cand_rep
                        ff_i.penalty = cand_rep.total_penalty
                        ff_i.brightness = self.problem.brightness_from_penalty(ff_i.penalty)
                        ff_i.last_step_hours = tot_hr
                        movements.append(
                            MovementRecord(
                                iteration=self.iteration,
                                mover_id=ff_i.id,
                                attractor_id=ff_i.id,
                                is_self_exploration=True,
                                mover_brightness_before=bri_before,
                                attractor_brightness=ff_i.brightness,
                                distance_r=0.0,
                                attractiveness_beta=0.0,
                                attraction_step_hours=0.0,
                                random_step_hours=rnd_hr,
                                total_step_hours=tot_hr,
                                penalty_before=pen_before,
                                penalty_after=ff_i.penalty,
                            )
                        )
                    else:
                        ff_i.last_step_hours = 0.0
                else:
                    ff_i.last_step_hours = 0.0
            else:
                best_j = max(
                    brighters,
                    key=lambda j: self.compute_attractiveness(
                        self.normalized_distance(old_positions[i], old_positions[j])
                    )
                    * old_brightness[j],
                )
                r = self.normalized_distance(old_positions[i], old_positions[best_j])
                beta = self.compute_attractiveness(r)

                new_pos: List[float] = []
                att_sq = 0.0
                rnd_sq = 0.0
                tot_sq = 0.0

                for d, task in enumerate(self.problem.tasks):
                    att_comp = beta * (old_positions[best_j][d] - old_positions[i][d])
                    rnd_comp = self.alpha * (self.rng.random() - 0.5) * task.span
                    val = max(
                        task.min_start,
                        min(task.max_start, old_positions[i][d] + att_comp + rnd_comp),
                    )
                    actual = val - old_positions[i][d]
                    att_sq += att_comp * att_comp
                    rnd_sq += rnd_comp * rnd_comp
                    tot_sq += actual * actual
                    new_pos.append(val)

                ff_i.position = new_pos
                self._evaluate_firefly(ff_i)

                att_hr = math.sqrt(att_sq / dim)
                rnd_hr = math.sqrt(rnd_sq / dim)
                tot_hr = math.sqrt(tot_sq / dim)

                ff_i.last_attractor_id = best_j
                ff_i.last_distance_r = r
                ff_i.last_beta = beta
                ff_i.last_step_hours = tot_hr

                movements.append(
                    MovementRecord(
                        iteration=self.iteration,
                        mover_id=ff_i.id,
                        attractor_id=best_j,
                        is_self_exploration=False,
                        mover_brightness_before=bri_before,
                        attractor_brightness=old_brightness[best_j],
                        distance_r=r,
                        attractiveness_beta=beta,
                        attraction_step_hours=att_hr,
                        random_step_hours=rnd_hr,
                        total_step_hours=tot_hr,
                        penalty_before=pen_before,
                        penalty_after=ff_i.penalty,
                    )
                )

            ff_i.trail_2d.append(self.project_2d(ff_i.position))
            if len(ff_i.trail_2d) > 25:
                ff_i.trail_2d.pop(0)

        # Elitisme ringan
        self._update_best()
        if self.best_firefly and all(f.penalty > self.best_firefly.penalty + 1e-9 for f in self.fireflies):
            worst_idx = max(range(n), key=lambda idx: self.fireflies[idx].penalty)
            el = self.fireflies[worst_idx]
            el.position = list(self.best_firefly.position)
            self._evaluate_firefly(el)
            el.trail_2d.append(self.project_2d(el.position))

        # Peluruhan alpha
        self.alpha = max(0.02, self.alpha * self.alpha_decay)

        self.last_movements = movements
        self.best_penalty_history.append(self.best_firefly.penalty if self.best_firefly else 0.0)
        self.avg_penalty_history.append(self._avg_penalty())

        non_self = [m for m in movements if not m.is_self_exploration]
        avg_beta = sum(m.attractiveness_beta for m in non_self) / len(non_self) if non_self else 0.0
        avg_step = sum(m.total_step_hours for m in movements) / len(movements) if movements else 0.0
        self.avg_beta_history.append(avg_beta)
        self.avg_step_history.append(avg_step)
        return movements
