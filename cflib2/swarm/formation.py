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
"""Hover formations: grids of slots and the order to fill them in.

Drones enter a formation from an entry point, normally the middle of the
docks. Slots are filled farthest from the entry point first, so a drone on
its way to its slot never has to pass a slot that is already taken: a
straight path from the entry point to the next slot stays at least half the
grid spacing away from every occupied slot. Leaving works the other way
round, the drone closest to the entry point leaves first.
"""

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence

from cflib2.swarm.drone import Drone
from cflib2.swarm.layout import Position

Point = tuple[float, float]


def grid(
    rows: int,
    cols: int,
    spacing: float,
    center: Point,
    z: float,
    tilt_x: float = 0.0,
    tilt_y: float = 0.0,
) -> list[Position]:
    """Slots of an axis-aligned grid centred on `center` at height `z`.

    With `tilt_x` / `tilt_y` (degrees) the grid lies on a slanted plane: it
    rises by tan(tilt_x) per metre in +x and tan(tilt_y) per metre in +y,
    and stays at height `z` in the centre. Only the heights change; seen from
    above the slots stay `spacing` apart, so the fill order and the
    clearance guarantees, which use horizontal distances, are unaffected.
    """
    cx, cy = center
    slope_x = math.tan(math.radians(tilt_x))
    slope_y = math.tan(math.radians(tilt_y))
    slots = []
    for row in range(rows):
        for col in range(cols):
            x = round(cx + (col - (cols - 1) / 2) * spacing, 6)
            y = round(cy + (row - (rows - 1) / 2) * spacing, 6)
            height = z + (x - cx) * slope_x + (y - cy) * slope_y
            slots.append((x, y, round(height, 6)))
    return slots


def grid_shape(n: int) -> tuple[int, int]:
    """(rows, cols) of the most square grid with room for `n` drones"""
    cols = math.ceil(math.sqrt(n))
    return math.ceil(n / cols), cols


def centroid(drones: Iterable[Drone]) -> Point:
    """Middle of the pads of the given drones, the default entry point"""
    pads = [d.pad for d in drones if d.pad is not None]
    if not pads:
        raise ValueError("No pads assigned")
    return (sum(p.x for p in pads) / len(pads), sum(p.y for p in pads) / len(pads))


def fill_order(slots: Iterable[Position], entry: Point) -> list[Position]:
    """Slots sorted farthest from `entry` first. Ties are broken by x, then y,
    so the order is deterministic."""
    return sorted(
        slots,
        key=lambda s: (-round(math.dist(s[:2], entry), 6), s[0], s[1]),
    )


def assign_slots(
    groups: Sequence[Sequence[Drone]], slots: Iterable[Position], entry: Point
) -> dict[Drone, Position]:
    """Give every drone a slot: group 1 gets the first slots in fill order,
    group 2 the next ones, and so on.

    Within a group, drones are matched to the group's slots so that the sum
    of the *squared* distances from pad to slot is as small as possible
    (CAPT, Turpin, Michael & Kumar 2014). When all drones of a group start
    and arrive at the same time, two of them then never get closer than
    `min(distance between their pads, distance between their slots) / sqrt(2)`
    during the flight. Minimising plain distances would only prevent paths
    from crossing on the map, not drones from meeting mid-air.
    """
    order = fill_order(slots, entry)
    needed = sum(len(g) for g in groups)
    if needed > len(order):
        raise ValueError(f"{needed} drones but only {len(order)} slots")

    assignment: dict[Drone, Position] = {}
    start = 0
    for group in groups:
        group_slots = order[start : start + len(group)]
        start += len(group)
        cost = [
            [d.pad.distance_xy(s[0], s[1]) ** 2 if d.pad else 0.0 for s in group_slots]
            for d in group
        ]
        for i, j in enumerate(min_cost_matching(cost)):
            assignment[group[i]] = group_slots[j]
    return assignment


def closest_approach(
    group: Iterable[Drone], targets: Mapping[Drone, Position]
) -> float:
    """Smallest horizontal distance (m) between two drones of the group while
    they fly from their pads to `targets`, all starting and arriving at the
    same time. `inf` for groups of one."""
    paths = [((d.pad.x, d.pad.y), targets[d][:2]) for d in group if d.pad is not None]
    closest = math.inf
    for (a0, a1), (b0, b1) in itertools.combinations(paths, 2):
        # Relative position goes linearly from `start` to `end`
        start = (a0[0] - b0[0], a0[1] - b0[1])
        end = (a1[0] - b1[0], a1[1] - b1[1])
        change = (end[0] - start[0], end[1] - start[1])
        length2 = change[0] ** 2 + change[1] ** 2
        s = 0.0
        if length2 > 0:
            s = -(start[0] * change[0] + start[1] * change[1]) / length2
            s = max(0.0, min(1.0, s))
        closest = min(
            closest, math.hypot(start[0] + s * change[0], start[1] + s * change[1])
        )
    return closest


def rotated_180(position: Position, center: Point) -> Position:
    """Where `position` ends up after half a turn around `center`"""
    x, y, z = position
    return (2 * center[0] - x, 2 * center[1] - y, z)


def min_cost_matching(cost: Sequence[Sequence[float]]) -> list[int]:
    """Hungarian algorithm for a square cost matrix, O(n^3).

    Returns `match` where row `i` is matched to column `match[i]` and the
    total cost is minimal.
    """
    n = len(cost)
    inf = math.inf
    # 1-based potentials and matching, column 0 is a sentinel
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    row_of_col = [0] * (n + 1)
    way = [0] * (n + 1)
    for row in range(1, n + 1):
        row_of_col[0] = row
        col = 0
        min_to = [inf] * (n + 1)
        used = [False] * (n + 1)
        while row_of_col[col] != 0:
            used[col] = True
            r = row_of_col[col]
            delta, next_col = inf, 0
            for c in range(1, n + 1):
                if not used[c]:
                    reduced = cost[r - 1][c - 1] - u[r] - v[c]
                    if reduced < min_to[c]:
                        min_to[c], way[c] = reduced, col
                    if min_to[c] < delta:
                        delta, next_col = min_to[c], c
            for c in range(n + 1):
                if used[c]:
                    u[row_of_col[c]] += delta
                    v[c] -= delta
                else:
                    min_to[c] -= delta
            col = next_col
        while col != 0:
            prev = way[col]
            row_of_col[col] = row_of_col[prev]
            col = prev

    match = [0] * n
    for c in range(1, n + 1):
        match[row_of_col[c] - 1] = c - 1
    return match
