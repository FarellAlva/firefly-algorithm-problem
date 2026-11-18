"""
Firefly Algorithm untuk Masalah Penjadwalan Mata Kuliah.
Pure Python standard library (tanpa dependensi eksternal).

Konsep inti yang dimodelkan:
1. Base Position (x_i):
   Vektor posisi kontinu dalam [0, 1]^(2*M), di mana M adalah jumlah mata kuliah.
   Setiap mata kuliah k memiliki 2 koordinat:
   - x[2k]     -> dipetakan ke Slot Waktu (0..num_slots-1)
   - x[2k + 1] -> dipetakan ke Ruangan (0..num_rooms-1)
2. Light Intensity / Brightness (I_i):
   I(x_i) = 1 / (1 + Penalty(x_i))
   Semakin kecil penalti bentrok jadwal, semakin terang kunang-kunang.
3. Attractiveness (beta):
   beta(r) = beta0 * exp(-gamma * r^2)
   Dengan r = ||x_i - x_j|| / sqrt(D) adalah jarak Euclidean ternormalisasi di [0, 1].
4. Steps / Movement (Delta x):
   x_i_new = x_i + beta(r) * (x_j - x_i) + alpha * (rand - 0.5)
   Terdiri dari:
   - Attraction step : tarikan menuju kunang-kunang yang lebih terang (eksploitasi)
   - Random step     : langkah acak terkendali oleh alpha (eksplorasi)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    lecturer: str
    student_group: str
    students: int


@dataclass(frozen=True)
class Room:
    code: str
    name: str
    capacity: int


@dataclass(frozen=True)
class TimeSlot:
    index: int
    day: str
    session: str
    label: str


@dataclass
class ConflictReport:
    room_conflicts: int
    lecturer_conflicts: int
    group_conflicts: int
    capacity_violations: int
    total_penalty: int
    conflicting_courses: Dict[int, List[str]]  # course_idx -> alasan konflik

    @property
    def hard_conflicts(self) -> int:
        return self.room_conflicts + self.lecturer_conflicts + self.group_conflicts


@dataclass
class MovementRecord:
    """Mencatat 1 peristiwa tarikan/langkah dari firefly i menuju firefly j."""

    iteration: int
    mover_id: int
    attractor_id: int
    mover_brightness_before: float
    attractor_brightness: float
    distance_r: float
    attractiveness_beta: float
    attraction_step_mag: float
    random_step_mag: float
    total_step_mag: float
    penalty_before: int
    penalty_after: int


@dataclass
class Firefly:
    id: int
    base_position: List[float]  # posisi awal (iterasi 0)
    position: List[float]       # posisi saat ini
    prev_position: List[float]  # posisi pada iterasi sebelumnya
    penalty: int = 0
    brightness: float = 0.0
    report: Optional[ConflictReport] = None
    last_attractor_id: Optional[int] = None
    last_beta: float = 0.0
    last_step_mag: float = 0.0
    trail_2d: List[Tuple[float, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dataset Penjadwalan Default (10 Mata Kuliah, 6 Slot Waktu, 3 Ruangan)
# ---------------------------------------------------------------------------

DEFAULT_COURSES: List[Course] = [
    Course("MK01", "Algoritma & Pemrog.", "Dr. Andi", "TI-A", 35),
    Course("MK02", "Struktur Data", "Dr. Andi", "TI-B", 30),
    Course("MK03", "Basis Data", "Bu Sari", "TI-A", 35),
    Course("MK04", "Kecerdasan Buatan", "Bu Sari", "TI-C", 25),
    Course("MK05", "Jaringan Komputer", "Pak Budi", "TI-B", 30),
    Course("MK06", "Sistem Operasi", "Pak Budi", "TI-C", 25),
    Course("MK07", "Rekayasa PL", "Dr. Citra", "TI-A", 35),
    Course("MK08", "Pemrograman Web", "Dr. Citra", "TI-B", 30),
    Course("MK09", "Bio-Computing", "Pak Dimas", "TI-C", 25),
    Course("MK10", "Keamanan Siber", "Pak Dimas", "TI-A", 35),
]

DEFAULT_ROOMS: List[Room] = [
    Room("R1", "Ruang Besar A (Kap 40)", 40),
    Room("R2", "Ruang Sedang B (Kap 32)", 32),
    Room("R3", "Lab Komputer C (Kap 28)", 28),
]

DEFAULT_SLOTS: List[TimeSlot] = [
    TimeSlot(0, "Senin", "Pagi", "Senin 08:00"),
    TimeSlot(1, "Senin", "Siang", "Senin 13:00"),
    TimeSlot(2, "Selasa", "Pagi", "Selasa 08:00"),
    TimeSlot(3, "Selasa", "Siang", "Selasa 13:00"),
    TimeSlot(4, "Rabu", "Pagi", "Rabu 08:00"),
    TimeSlot(5, "Rabu", "Siang", "Rabu 13:00"),
]


class SchedulingProblem:
    """Representasi masalah penjadwalan mata kuliah & fungsi evaluasi penalti."""

    HARD_PENALTY = 10
    SOFT_CAPACITY_PENALTY = 3

    def __init__(
        self,
        courses: Optional[List[Course]] = None,
        rooms: Optional[List[Room]] = None,
        slots: Optional[List[TimeSlot]] = None,
    ) -> None:
        self.courses = courses or list(DEFAULT_COURSES)
        self.rooms = rooms or list(DEFAULT_ROOMS)
        self.slots = slots or list(DEFAULT_SLOTS)
        self.dimension = 2 * len(self.courses)

    def decode(self, position: List[float]) -> List[Tuple[int, int]]:
        """
        Mengubah vektor posisi kontinu [0, 1]^(2*M) menjadi daftar
        (slot_idx, room_idx) untuk setiap mata kuliah.
        """
        num_slots = len(self.slots)
        num_rooms = len(self.rooms)
        assignments: List[Tuple[int, int]] = []
        for k in range(len(self.courses)):
            val_slot = max(0.0, min(0.999999, position[2 * k]))
            val_room = max(0.0, min(0.999999, position[2 * k + 1]))
            slot_idx = int(val_slot * num_slots)
            room_idx = int(val_room * num_rooms)
            assignments.append((slot_idx, room_idx))
        return assignments

    def evaluate(self, position: List[float]) -> ConflictReport:
        """Menghitung seluruh pelanggaran jadwal (Hard + Soft constraints)."""
        assignments = self.decode(position)
        room_slot_map: Dict[Tuple[int, int], List[int]] = {}
        lecturer_slot_map: Dict[Tuple[str, int], List[int]] = {}
        group_slot_map: Dict[Tuple[str, int], List[int]] = {}
        conflicting: Dict[int, List[str]] = {i: [] for i in range(len(self.courses))}

        capacity_violations = 0

        for idx, (slot_idx, room_idx) in enumerate(assignments):
            course = self.courses[idx]
            room = self.rooms[room_idx]

            room_slot_map.setdefault((slot_idx, room_idx), []).append(idx)
            lecturer_slot_map.setdefault((course.lecturer, slot_idx), []).append(idx)
            group_slot_map.setdefault((course.student_group, slot_idx), []).append(idx)

            if course.students > room.capacity:
                capacity_violations += 1
                conflicting[idx].append(
                    f"Kapasitas {room.code} ({room.capacity}) < {course.students}"
                )

        room_conflicts = 0
        for (slot_idx, room_idx), c_indices in room_slot_map.items():
            if len(c_indices) > 1:
                room_conflicts += len(c_indices) - 1
                for ci in c_indices:
                    conflicting[ci].append(f"Bentrok Ruang {self.rooms[room_idx].code}")

        lecturer_conflicts = 0
        for (lecturer, _slot_idx), c_indices in lecturer_slot_map.items():
            if len(c_indices) > 1:
                lecturer_conflicts += len(c_indices) - 1
                for ci in c_indices:
                    conflicting[ci].append(f"Bentrok Dosen ({lecturer})")

        group_conflicts = 0
        for (group, _slot_idx), c_indices in group_slot_map.items():
            if len(c_indices) > 1:
                group_conflicts += len(c_indices) - 1
                for ci in c_indices:
                    conflicting[ci].append(f"Bentrok Kelas ({group})")

        total_penalty = (
            (room_conflicts + lecturer_conflicts + group_conflicts) * self.HARD_PENALTY
            + capacity_violations * self.SOFT_CAPACITY_PENALTY
        )
        return ConflictReport(
            room_conflicts=room_conflicts,
            lecturer_conflicts=lecturer_conflicts,
            group_conflicts=group_conflicts,
            capacity_violations=capacity_violations,
            total_penalty=total_penalty,
            conflicting_courses=conflicting,
        )

    @staticmethod
    def brightness_from_penalty(penalty: int) -> float:
        return 1.0 / (1.0 + penalty)


class FireflyScheduler:
    """Mesin Firefly Algorithm untuk optimasi penjadwalan."""

    def __init__(
        self,
        problem: Optional[SchedulingProblem] = None,
        n_fireflies: int = 20,
        beta0: float = 1.0,
        gamma: float = 1.2,
        alpha: float = 0.28,
        alpha_decay: float = 0.97,
        seed: int = 42,
    ) -> None:
        self.problem = problem or SchedulingProblem()
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

        # Riwayat untuk grafik konvergensi dan inspeksi
        self.best_penalty_history: List[int] = []
        self.avg_penalty_history: List[float] = []
        self.avg_beta_history: List[float] = []
        self.avg_step_history: List[float] = []
        self.last_movements: List[MovementRecord] = []

        self.initialize()

    def project_2d(self, position: List[float]) -> Tuple[float, float]:
        """
        Proyeksi deterministik 2D dari vektor 2M-dimensi untuk visualisasi di Canvas:
        - Sumbu X: rata-rata koordinat slot waktu (indeks genap)
        - Sumbu Y: rata-rata koordinat ruangan (indeks ganjil)
        """
        xs = position[0::2]
        ys = position[1::2]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def _normalized_distance(self, pos_a: List[float], pos_b: List[float]) -> float:
        sq = sum((a - b) ** 2 for a, b in zip(pos_a, pos_b))
        return math.sqrt(sq / len(pos_a))

    def _evaluate_firefly(self, ff: Firefly) -> None:
        report = self.problem.evaluate(ff.position)
        ff.report = report
        ff.penalty = report.total_penalty
        ff.brightness = self.problem.brightness_from_penalty(ff.penalty)

    def initialize(self) -> None:
        """Membentuk populasi awal (Base Position acak di [0, 1]^D)."""
        self.rng = random.Random(self.seed)
        self.iteration = 0
        self.alpha = self.alpha_init
        self.fireflies = []
        self.last_movements = []

        dim = self.problem.dimension
        for i in range(self.n_fireflies):
            base_pos = [self.rng.random() for _ in range(dim)]
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

    def _avg_penalty(self) -> float:
        return sum(f.penalty for f in self.fireflies) / len(self.fireflies)

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
            last_beta=ff.last_beta,
            last_step_mag=ff.last_step_mag,
            trail_2d=list(ff.trail_2d),
        )

    def _update_best(self) -> None:
        current_best = min(self.fireflies, key=lambda f: f.penalty)
        if self.best_firefly is None or current_best.penalty <= self.best_firefly.penalty:
            self.best_firefly = self._clone_firefly(current_best)

    def step(self) -> List[MovementRecord]:
        """
        Menjalankan 1 iterasi Firefly Algorithm:
        - Untuk setiap pasangan (i, j): jika brightness(j) > brightness(i),
          firefly i bergerak mendekati j dengan daya tarik beta(r) + langkah acak alpha.
        - Firefly paling terang melakukan eksplorasi lokal kecil (greedy: diterima bila membaik).
        """
        self.iteration += 1
        dim = self.problem.dimension
        movements: List[MovementRecord] = []

        # Simpan snapshot posisi sebelum iterasi agar panah pergerakan jelas
        for ff in self.fireflies:
            ff.prev_position = list(ff.position)
            ff.last_attractor_id = None
            ff.last_beta = 0.0
            ff.last_step_mag = 0.0

        # Urutkan indeks berdasarkan brightness agar evaluasi stabil & jelas
        n = len(self.fireflies)
        # Temukan indeks firefly terbaik saat ini (paling terang)
        best_idx = min(range(n), key=lambda idx: self.fireflies[idx].penalty)

        for i in range(n):
            ff_i = self.fireflies[i]
            moved = False

            # Cari semua j yang lebih terang dari i
            # Untuk menjaga stabilitas dan memperlihatkan tarikan paling bermakna,
            # ikuti standar FA: bandingkan i dengan setiap j yang lebih terang.
            strongest_beta = -1.0
            strongest_attractor: Optional[int] = None
            accum_step_sq = 0.0

            for j in range(n):
                if i == j:
                    continue
                ff_j = self.fireflies[j]
                if ff_j.brightness > ff_i.brightness:
                    r = self._normalized_distance(ff_i.position, ff_j.position)
                    beta = self.beta0 * math.exp(-self.gamma * (r ** 2))

                    penalty_before = ff_i.penalty
                    brightness_before = ff_i.brightness

                    new_pos = []
                    attract_sq = 0.0
                    rand_sq = 0.0
                    total_sq = 0.0

                    for d in range(dim):
                        attract_comp = beta * (ff_j.position[d] - ff_i.position[d])
                        rand_comp = self.alpha * (self.rng.random() - 0.5)
                        delta = attract_comp + rand_comp
                        val = ff_i.position[d] + delta
                        # Clamp ke [0, 1]
                        val = max(0.0, min(1.0, val))
                        actual_delta = val - ff_i.position[d]

                        attract_sq += attract_comp ** 2
                        rand_sq += rand_comp ** 2
                        total_sq += actual_delta ** 2
                        new_pos.append(val)

                    ff_i.position = new_pos
                    self._evaluate_firefly(ff_i)

                    attract_mag = math.sqrt(attract_sq / dim)
                    rand_mag = math.sqrt(rand_sq / dim)
                    total_mag = math.sqrt(total_sq / dim)

                    movements.append(
                        MovementRecord(
                            iteration=self.iteration,
                            mover_id=ff_i.id,
                            attractor_id=ff_j.id,
                            mover_brightness_before=brightness_before,
                            attractor_brightness=ff_j.brightness,
                            distance_r=r,
                            attractiveness_beta=beta,
                            attraction_step_mag=attract_mag,
                            random_step_mag=rand_mag,
                            total_step_mag=total_mag,
                            penalty_before=penalty_before,
                            penalty_after=ff_i.penalty,
                        )
                    )

                    if beta > strongest_beta:
                        strongest_beta = beta
                        strongest_attractor = ff_j.id
                    accum_step_sq += total_mag ** 2
                    moved = True

            if moved:
                ff_i.last_attractor_id = strongest_attractor
                ff_i.last_beta = max(0.0, strongest_beta)
                ff_i.last_step_mag = math.sqrt(accum_step_sq)
            elif i == best_idx and ff_i.penalty > 0:
                # Firefly paling terang mencoba 1 langkah eksplorasi lokal (greedy)
                # agar tetap bisa keluar dari local optimum tanpa merusak solusi terbaik.
                candidate = list(ff_i.position)
                # Perturbasi terfokus pada mata kuliah yang masih konflik jika ada
                conflict_courses = [
                    c_idx
                    for c_idx, reasons in (ff_i.report.conflicting_courses.items() if ff_i.report else [])
                    if reasons
                ]
                if conflict_courses:
                    target_c = self.rng.choice(conflict_courses)
                    for offset in (0, 1):
                        d = 2 * target_c + offset
                        candidate[d] = max(0.0, min(1.0, candidate[d] + self.alpha * (self.rng.random() - 0.5) * 1.5))
                else:
                    for d in range(dim):
                        candidate[d] = max(0.0, min(1.0, candidate[d] + self.alpha * (self.rng.random() - 0.5) * 0.5))

                cand_report = self.problem.evaluate(candidate)
                if cand_report.total_penalty <= ff_i.penalty:
                    penalty_before = ff_i.penalty
                    brightness_before = ff_i.brightness
                    step_mag = self._normalized_distance(ff_i.position, candidate)
                    ff_i.position = candidate
                    ff_i.report = cand_report
                    ff_i.penalty = cand_report.total_penalty
                    ff_i.brightness = self.problem.brightness_from_penalty(ff_i.penalty)
                    ff_i.last_attractor_id = ff_i.id  # self-exploration
                    ff_i.last_beta = 0.0
                    ff_i.last_step_mag = step_mag
                    movements.append(
                        MovementRecord(
                            iteration=self.iteration,
                            mover_id=ff_i.id,
                            attractor_id=ff_i.id,
                            mover_brightness_before=brightness_before,
                            attractor_brightness=ff_i.brightness,
                            distance_r=0.0,
                            attractiveness_beta=0.0,
                            attraction_step_mag=0.0,
                            random_step_mag=step_mag,
                            total_step_mag=step_mag,
                            penalty_before=penalty_before,
                            penalty_after=ff_i.penalty,
                        )
                    )

            # Simpan jejak 2D (maksimal 25 titik terakhir supaya canvas tetap ringan)
            ff_i.trail_2d.append(self.project_2d(ff_i.position))
            if len(ff_i.trail_2d) > 25:
                ff_i.trail_2d.pop(0)

        # Elitisme ringan: pastikan firefly terbaik global tidak hilang
        self._update_best()
        worst_idx = max(range(n), key=lambda idx: self.fireflies[idx].penalty)
        if self.best_firefly and all(f.penalty > self.best_firefly.penalty for f in self.fireflies):
            el = self.fireflies[worst_idx]
            el.position = list(self.best_firefly.position)
            self._evaluate_firefly(el)
            el.trail_2d.append(self.project_2d(el.position))

        # Peluruhan langkah acak alpha (damping)
        self.alpha = max(0.01, self.alpha * self.alpha_decay)

        # Catat statistik iterasi
        self.last_movements = movements
        self.best_penalty_history.append(self.best_firefly.penalty if self.best_firefly else 0)
        self.avg_penalty_history.append(self._avg_penalty())

        if movements:
            avg_beta = sum(m.attractiveness_beta for m in movements) / len(movements)
            avg_step = sum(m.total_step_mag for m in movements) / len(movements)
        else:
            avg_beta = 0.0
            avg_step = 0.0

        self.avg_beta_history.append(avg_beta)
        self.avg_step_history.append(avg_step)
        return movements
