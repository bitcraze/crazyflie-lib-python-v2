# ,---------,       ____  _ __
# |  ,-^-,  |      / __ )(_) /_______________ _____  ___
# | (  O  ) |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
# | / ,--'  |    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#    +------`   /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
# Copyright (C) 2026 Bitcraze AB
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Strategies for splitting a swarm into an ordered list of groups.

Every strategy takes drones that have a pad assigned and returns
`list[list[Drone]]`: groups in execution order, each sorted by pad index.
Empty groups are never returned.
"""

import itertools
import math
import time
from collections.abc import Callable, Hashable, Iterable, Sequence

from cflib2.swarm.drone import Drone
from cflib2.swarm.layout import Pad

Groups = list[list[Drone]]


def _pad(d: Drone) -> Pad:
    if d.pad is None:
        raise ValueError(f"{d} has no pad assigned, call Swarm.assign_pads first")
    return d.pad


def _cell(d: Drone) -> tuple[int, int]:
    cell = _pad(d).cell
    if cell is None:
        raise ValueError(f"Pad {_pad(d).index} is not part of a grid layout")
    return cell


def group_by(drones: Iterable[Drone], key: Callable[[Drone], Hashable]) -> Groups:
    """One group per distinct key value, groups ordered by key"""
    buckets: dict = {}
    for d in drones:
        buckets.setdefault(key(d), []).append(d)
    return [sorted(buckets[k], key=lambda d: _pad(d).index) for k in sorted(buckets)]


def by_min_separation(
    drones: Iterable[Drone], min_distance: float, *, time_limit: float = 1.0
) -> Groups:
    """As few groups as possible, with no two drones in a group closer than
    `min_distance` (m, horizontal distance between their pads).

    Use this to take off or land without disturbing neighbours. Works for any
    layout. On a grid with spacing `s`, a `min_distance` between `1.42 * s`
    and `2 * s` excludes side and diagonal neighbours (4 groups); between `s`
    and `1.41 * s` only side neighbours (2 groups, a checkerboard). Keep it
    well away from those boundaries, measured positions are never exact.

    This is graph colouring: drones are nodes, drones that are too close are
    connected, and each colour is a group. A DSatur colouring (Brelaz, 1979)
    is improved by an exact branch and bound search for up to `time_limit`
    seconds. The search stops early when the result equals the largest set of
    mutually conflicting drones, as no solution can use fewer groups. If time
    runs out, the best colouring found so far is used. Deterministic for a
    given set of pad positions, whatever the order of `drones`.
    """
    drones = sorted(drones, key=lambda d: _pad(d).index)
    pads = [_pad(d) for d in drones]
    conflicts = [
        {
            j
            for j, q in enumerate(pads)
            if j != i and p.distance_xy(q.x, q.y) < min_distance
        }
        for i, p in enumerate(pads)
    ]

    colors = _dsatur(conflicts)
    lower_bound = _max_clique_size(conflicts)
    if max(colors, default=-1) + 1 > lower_bound:
        deadline = time.monotonic() + time_limit
        colors = _exact_coloring(conflicts, colors, lower_bound, deadline)

    groups: Groups = [[] for _ in range(max(colors, default=-1) + 1)]
    for d, c in zip(drones, colors):
        groups[c].append(d)
    return groups


def _saturation(v: int, conflicts: list[set[int]], colors: list[int]) -> int:
    return len({colors[u] for u in conflicts[v] if colors[u] >= 0})


def _next_vertex(conflicts: list[set[int]], colors: list[int]) -> int:
    """DSatur choice: the uncoloured vertex with the most distinct colours
    among its neighbours, ties broken by most neighbours, then lowest index"""
    return max(
        (v for v in range(len(colors)) if colors[v] < 0),
        key=lambda v: (_saturation(v, conflicts, colors), len(conflicts[v]), -v),
    )


def _dsatur(conflicts: list[set[int]]) -> list[int]:
    colors = [-1] * len(conflicts)
    for _ in range(len(conflicts)):
        v = _next_vertex(conflicts, colors)
        used = {colors[u] for u in conflicts[v]}
        colors[v] = next(c for c in itertools.count() if c not in used)
    return colors


def _max_clique_size(conflicts: list[set[int]]) -> int:
    """Bron-Kerbosch with pivoting"""
    best = 0

    def expand(size: int, candidates: set[int], excluded: set[int]) -> None:
        nonlocal best
        if not candidates and not excluded:
            best = max(best, size)
            return
        if size + len(candidates) <= best:
            return
        pivot = max(candidates | excluded, key=lambda u: len(conflicts[u]))
        for v in list(candidates - conflicts[pivot]):
            expand(size + 1, candidates & conflicts[v], excluded & conflicts[v])
            candidates = candidates - {v}
            excluded = excluded | {v}

    expand(0, set(range(len(conflicts))), set())
    return best


class _OutOfTime(Exception):
    pass


def _exact_coloring(
    conflicts: list[set[int]], best: list[int], lower_bound: int, deadline: float
) -> list[int]:
    """Branch and bound in DSatur order, for a colouring with fewer colours
    than `best`. Returns `best` if none is found before `deadline`."""
    n = len(conflicts)
    colors = [-1] * n
    best_count = max(best) + 1

    def search(colored: int, used_count: int) -> bool:
        """True when a colouring with `lower_bound` colours was found"""
        nonlocal best, best_count
        if time.monotonic() > deadline:
            raise _OutOfTime
        if used_count >= best_count:
            return False
        if colored == n:
            best, best_count = colors.copy(), used_count
            return best_count == lower_bound
        v = _next_vertex(conflicts, colors)
        taken = {colors[u] for u in conflicts[v]}
        # Only try colours that keep the total below the best so far; a new
        # colour (== used_count) is tried once, they are interchangeable
        for c in range(min(used_count + 1, best_count - 1)):
            if c not in taken:
                colors[v] = c
                if search(colored + 1, max(used_count, c + 1)):
                    return True
        colors[v] = -1
        return False

    try:
        search(0, 0)
    except _OutOfTime:
        pass
    return best


def by_distance(
    drones: Iterable[Drone], step: float, center: tuple[float, float] = (0.0, 0.0)
) -> Groups:
    """Concentric bands of width `step` (m) around `center`, inside out"""
    cx, cy = center
    return group_by(drones, lambda d: math.floor(_pad(d).distance_xy(cx, cy) / step))


def rings(drones: Iterable[Drone], center: tuple[float, float] | None = None) -> Groups:
    """Square rings on a grid, inside out (Chebyshev distance from the centre cell).

    `center` is in cell coordinates and defaults to the centre of the cells
    in use. On a 7x7 grid this gives groups of 1, 8, 16 and 24.
    """
    drones = list(drones)
    if center is None:
        xs = [_cell(d)[0] for d in drones]
        ys = [_cell(d)[1] for d in drones]
        center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    cx, cy = center
    return group_by(drones, lambda d: max(abs(_cell(d)[0] - cx), abs(_cell(d)[1] - cy)))


def stripes(drones: Iterable[Drone], axis: str = "x") -> Groups:
    """Straight lines on a grid, one group per `ix` (axis="x") or `iy` (axis="y")"""
    if axis not in ("x", "y"):
        raise ValueError("axis must be 'x' or 'y'")
    i = 0 if axis == "x" else 1
    return group_by(drones, lambda d: _cell(d)[i])


def diagonals(drones: Iterable[Drone], flip: bool = False) -> Groups:
    """Diagonal lines on a grid, corner to corner: one group per `ix + iy`
    (or `ix - iy` with `flip`)"""
    sign = -1 if flip else 1
    return group_by(drones, lambda d: _cell(d)[0] + sign * _cell(d)[1])


def checkerboard(drones: Iterable[Drone]) -> Groups:
    """Two interleaved groups on a grid; no two side neighbours in one group"""
    return group_by(drones, lambda d: sum(_cell(d)) % 2)


def from_pad_indices(drones: Iterable[Drone], spec: Sequence[Iterable[int]]) -> Groups:
    """Explicit groups given as pad indices, e.g. `[[25], [17, 18, 19], ...]`.

    Drones on pads not listed in `spec` are left out.
    """
    by_index = {_pad(d).index: d for d in drones}
    groups = [
        sorted(
            (by_index[i] for i in indices if i in by_index), key=lambda d: _pad(d).index
        )
        for indices in spec
    ]
    return [g for g in groups if g]
