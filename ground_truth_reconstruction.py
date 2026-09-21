"""Deterministic ground-truth reconstruction baseline.

IMPORTANT: the 2025 Vehicles paper says the truth values were produced with a
Python simulation and validated by traffic-engineering experts, The published paper points to an official Zenodo record (14171745). This file is
NOT that source code; it is the earlier transparent reconstruction retained as a
separate baseline/sensitivity analysis backend.

Assumptions not numerically specified in the paper are collected in GTConfig so
experiments can freeze and report them.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import hypot, inf
from typing import Iterable

from intersection import direction_on_right


@dataclass(frozen=True)
class GTConfig:
    conflict_distance_m: float = 2.2
    temporal_threshold_s: float = 2.5
    intersection_half_width_m: float = 8.0
    clearance_time_s: float = 2.0
    sample_step: float = 0.025


# Coordinates follow Figure 4's drawing: paper direction labels are retained.
# Incoming points are lane-specific; outgoing destination letters are lane-specific.
ENTRY = {
    "1": (8.0, 2.0), "2": (8.0, -2.0),
    "3": (2.0, -8.0), "4": (-2.0, -8.0),
    "5": (-8.0, -2.0), "6": (-8.0, 2.0),
    "7": (-2.0, 8.0), "8": (2.0, 8.0),
}
EXIT = {
    "A": (8.0, 2.0), "B": (8.0, -2.0),
    "C": (2.0, -8.0), "D": (-2.0, -8.0),
    "E": (-8.0, -2.0), "F": (-8.0, 2.0),
    "G": (-2.0, 8.0), "H": (2.0, 8.0),
}


def _quadratic_bezier(p0, p1, p2, t):
    u = 1.0 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def route_points(vehicle, cfg: GTConfig) -> list[tuple[float, float]]:
    p0 = ENTRY[vehicle.lane]
    p2 = EXIT[vehicle.destination]
    movement = vehicle.movement()
    n = max(10, round(1.0 / cfg.sample_step))

    if movement == "straight":
        return [
            (p0[0] + (p2[0] - p0[0]) * i / n,
             p0[1] + (p2[1] - p0[1]) * i / n)
            for i in range(n + 1)
        ]

    # Turning trajectories use a smooth quadratic curve through the center area.
    # Left turns are broader than right turns; lane endpoints preserve the paper layout.
    if movement == "left":
        control = (0.0, 0.0)
    else:  # right
        control = ((p0[0] + p2[0]) * 0.62, (p0[1] + p2[1]) * 0.62)
    return [_quadratic_bezier(p0, control, p2, i / n) for i in range(n + 1)]


def _polyline_lengths(points):
    cum = [0.0]
    for a, b in zip(points, points[1:]):
        cum.append(cum[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    return cum


def _closest_route_points(v1, v2, cfg: GTConfig):
    r1, r2 = route_points(v1, cfg), route_points(v2, cfg)
    l1, l2 = _polyline_lengths(r1), _polyline_lengths(r2)
    best = (inf, 0, 0)
    for i, a in enumerate(r1):
        for j, b in enumerate(r2):
            d = hypot(a[0] - b[0], a[1] - b[1])
            if d < best[0]:
                best = (d, i, j)
    d, i, j = best
    return d, l1[i], l2[j]


def _time_at_route_distance(v, route_distance_m):
    if v.speed <= 0:
        return inf
    return v.time_to_intersection() + route_distance_m / v.speed_mps()


def pair_conflict(v1, v2, cfg: GTConfig = GTConfig()) -> dict:
    # Same approach is intentionally excluded: this experiment targets crossing
    # conflicts inside the intersection, not car-following/rear-end conflicts.
    if v1.direction == v2.direction:
        return {
            "is_conflict": False,
            "reason": "same_approach_not_scored_as_intersection_crossing_conflict",
        }

    distance, d1, d2 = _closest_route_points(v1, v2, cfg)
    if distance > cfg.conflict_distance_m:
        return {
            "is_conflict": False,
            "reason": "movement_paths_do_not_overlap",
            "minimum_path_separation_m": round(distance, 3),
        }

    t1 = _time_at_route_distance(v1, d1)
    t2 = _time_at_route_distance(v2, d2)
    dt = abs(t1 - t2)
    conflict = dt <= cfg.temporal_threshold_s
    return {
        "is_conflict": conflict,
        "reason": "spatiotemporal_path_overlap" if conflict else "path_overlap_but_arrival_times_separated",
        "minimum_path_separation_m": round(distance, 3),
        "vehicle1_time_to_conflict_s": None if t1 == inf else round(t1, 3),
        "vehicle2_time_to_conflict_s": None if t2 == inf else round(t2, 3),
        "arrival_time_gap_s": None if dt == inf else round(dt, 3),
    }


def _movement_rank(v):
    # Paper: straight generally has priority over turning; left-turn vehicles
    # must wait for right-turn vehicles. Lower rank means higher priority.
    return {"straight": 0, "right": 1, "left": 2}.get(v.movement(), 3)


def higher_priority(v1, v2):
    r1, r2 = _movement_rank(v1), _movement_rank(v2)
    if r1 != r2:
        return (v1, v2) if r1 < r2 else (v2, v1)

    t1, t2 = v1.time_to_intersection(), v2.time_to_intersection()
    if abs(t1 - t2) > 0.5:
        return (v1, v2) if t1 < t2 else (v2, v1)

    # Same movement class, approximately simultaneous: right-hand rule.
    if direction_on_right(v1.direction) == v2.direction:
        return v2, v1
    if direction_on_right(v2.direction) == v1.direction:
        return v1, v2

    # Deterministic final tie-breaker for opposite approaches.
    return (v1, v2) if v1.vehicle_id < v2.vehicle_id else (v2, v1)


def analyze_ground_truth(vehicles: Iterable, cfg: GTConfig = GTConfig()) -> dict:
    vehicles = list(vehicles)
    by_id = {v.vehicle_id: v for v in vehicles}
    conflicts = []
    edges = []  # winner -> loser

    for v1, v2 in combinations(vehicles, 2):
        info = pair_conflict(v1, v2, cfg)
        if info["is_conflict"]:
            winner, loser = higher_priority(v1, v2)
            conflicts.append({
                "vehicle1_id": v1.vehicle_id,
                "vehicle2_id": v2.vehicle_id,
                **info,
                "yield_vehicle": loser.vehicle_id,
                "priority_vehicle": winner.vehicle_id,
            })
            edges.append((winner.vehicle_id, loser.vehicle_id))

    # Aggregate a stable global priority order using pairwise losses, movement rank,
    # and arrival time. This makes the output easy to compare with LLM JSON.
    losses = {vid: 0 for vid in by_id}
    wins = {vid: 0 for vid in by_id}
    for w, l in edges:
        wins[w] += 1
        losses[l] += 1

    priority_order = sorted(
        by_id,
        key=lambda vid: (
            losses[vid],
            _movement_rank(by_id[vid]),
            by_id[vid].time_to_intersection(),
            -wins[vid],
            vid,
        ),
    )

    # Waiting time proxy: each vehicle waits until all higher-priority conflicting
    # vehicles have cleared. The paper does not publish its exact waiting-time formula.
    waiting = {vid: 0.0 for vid in by_id}
    for w, l in edges:
        winner = by_id[w]
        loser = by_id[l]
        winner_clear = winner.time_to_intersection() + cfg.clearance_time_s
        if winner_clear != inf and loser.time_to_intersection() != inf:
            waiting[l] = max(waiting[l], winner_clear - loser.time_to_intersection(), 0.0)

    decisions = []
    yielding = {l for _, l in edges}
    winners = {w for w, _ in edges}
    for vid in priority_order:
        if vid in yielding:
            action = "yield"
        elif vid in winners:
            action = "proceed"
        else:
            action = "proceed"
        decisions.append({"vehicle_id": vid, "action": action})

    return {
        "is_conflict": bool(conflicts),
        "number_of_conflicts": len(conflicts),
        "places_of_conflicts": ["intersection"] * len(conflicts),
        "conflict_vehicles": conflicts,
        "decisions": decisions,
        "priority_order": priority_order,
        "waiting_times": {k: round(v, 3) for k, v in waiting.items()},
        "ground_truth_method": "geometric_reconstruction_v1_not_author_code",
        "ground_truth_config": cfg.__dict__,
    }
