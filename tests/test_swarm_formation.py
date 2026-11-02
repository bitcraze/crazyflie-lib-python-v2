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
"""Tests for hover formations and the orbit sequence"""

import itertools
import math
import random

import pytest

from cflib2.swarm import Layout, formation, grouping, orbit
from tests.test_swarm import MEASURED_5X5, make_swarm


class TestGrid:
    def test_grid_is_centred(self) -> None:
        slots = formation.grid(2, 3, 0.5, (1.0, 2.0), 1.2)
        assert len(slots) == 6
        assert sorted({s[0] for s in slots}) == [0.5, 1.0, 1.5]
        assert sorted({s[1] for s in slots}) == [1.75, 2.25]
        assert all(s[2] == 1.2 for s in slots)

    def test_tilted_grid_only_changes_heights(self) -> None:
        flat = formation.grid(5, 5, 0.6, (0.5, 1.0), 1.0)
        tilted = formation.grid(5, 5, 0.6, (0.5, 1.0), 1.0, tilt_x=10, tilt_y=-20)

        assert [s[:2] for s in tilted] == [s[:2] for s in flat]
        for x, y, z in tilted:
            expected = (
                1.0
                + (x - 0.5) * math.tan(math.radians(10))
                - (y - 1.0) * math.tan(math.radians(20))
            )
            assert z == pytest.approx(expected, abs=1e-6)
        # Centre slot stays at the given height
        assert (0.5, 1.0, 1.0) in tilted

    def test_tilt_keeps_fill_order_and_clearance(self) -> None:
        drones = make_swarm(Layout.from_positions(MEASURED_5X5)).drones
        groups = grouping.by_min_separation(drones, 0.5)
        entry = formation.centroid(drones)
        flat = formation.grid(5, 5, 0.6, (0.5, 1.0), 1.0)
        tilted = formation.grid(5, 5, 0.6, (0.5, 1.0), 1.0, tilt_x=15, tilt_y=15)

        flat_plan = formation.assign_slots(groups, flat, entry)
        tilted_plan = formation.assign_slots(groups, tilted, entry)

        # Same slot for every drone, seen from above
        assert all(tilted_plan[d][:2] == flat_plan[d][:2] for d in drones)
        for group in groups:
            assert formation.closest_approach(group, tilted_plan) == pytest.approx(
                formation.closest_approach(group, flat_plan)
            )

    @pytest.mark.parametrize(
        "n, shape", [(1, (1, 1)), (4, (2, 2)), (5, (2, 3)), (25, (5, 5)), (26, (5, 6))]
    )
    def test_grid_shape(self, n: int, shape: tuple[int, int]) -> None:
        assert formation.grid_shape(n) == shape


class TestFillOrder:
    def test_5x5_entry_below_the_middle(self) -> None:
        # Same picture as in the design discussion: back row first, outer
        # slots before inner ones, base row last
        slots = formation.grid(5, 5, 1.0, (2.0, 2.0), 1.0)
        order = formation.fill_order(slots, (2.0, -4.0))
        rank = {(s[0], s[1]): i for i, s in enumerate(order, 1)}
        rows = [[rank[(x, y)] for x in range(5)] for y in reversed(range(5))]
        assert rows == [
            [1, 3, 5, 4, 2],
            [6, 8, 10, 9, 7],
            [11, 13, 15, 14, 12],
            [16, 18, 20, 19, 17],
            [21, 23, 25, 24, 22],
        ]

    def test_path_keeps_half_spacing_from_occupied_slots(self) -> None:
        # The guarantee behind the fill order: a straight path from the entry
        # point to the next slot never comes closer than spacing / 2 to a
        # slot that is already taken
        spacing = 0.6
        slots = formation.grid(5, 5, spacing, (0.5, 1.0), 1.0)
        for entry in [(0.5, -1.9), (3.0, 1.0), (-2.0, -2.0), (0.6, 0.9)]:
            order = formation.fill_order(slots, entry)
            for k, target in enumerate(order):
                for occupied in order[:k]:
                    clearance = _segment_distance(occupied[:2], entry, target[:2])
                    assert clearance >= spacing / 2 - 1e-9


class TestAssignSlots:
    def test_first_group_gets_farthest_slots(self) -> None:
        drones = make_swarm(Layout.from_positions(MEASURED_5X5)).drones
        groups = grouping.by_min_separation(drones, 0.7)
        entry = formation.centroid(drones)
        slots = formation.grid(5, 5, 0.6, (0.5, 2.0), 1.0)
        slot_of = formation.assign_slots(groups, slots, entry)

        assert len(set(slot_of.values())) == 25
        order = formation.fill_order(slots, entry)
        start = 0
        for group in groups:
            expected = set(order[start : start + len(group)])
            assert {slot_of[d] for d in group} == expected
            start += len(group)

    @pytest.mark.parametrize("center", [(0.5, 1.0), (2.5, -1.9), (0.45, 0.0)])
    def test_drones_in_a_group_keep_their_distance(
        self, center: tuple[float, float]
    ) -> None:
        # With plain distances as cost, drones of one group met mid-air
        # (closest approach 0.00-0.13 m) on these real dock positions
        drones = make_swarm(Layout.from_positions(MEASURED_5X5)).drones
        groups = grouping.by_min_separation(drones, 0.5)
        slots = formation.grid(5, 5, 0.6, center, 1.0)
        slot_of = formation.assign_slots(groups, slots, formation.centroid(drones))
        for group in groups:
            # Guarantee: min(pad separation, slot spacing) / sqrt(2)
            assert formation.closest_approach(group, slot_of) >= 0.5 / math.sqrt(2)

    def test_closest_approach(self) -> None:
        a, b = make_swarm(Layout.from_positions([(0, 0), (1, 0)])).drones
        # Swapping sides: they meet in the middle
        assert formation.closest_approach([a, b], {a: (1, 0, 1), b: (0, 0, 1)}) == 0
        # Moving in parallel: distance stays 1
        targets = {a: (0, 2, 1), b: (1, 2, 1)}
        assert formation.closest_approach([a, b], targets) == pytest.approx(1)
        assert formation.closest_approach([a], targets) == math.inf

    def test_too_few_slots(self) -> None:
        drones = make_swarm(Layout.grid(3, 3, 1.0)).drones
        with pytest.raises(ValueError):
            formation.assign_slots(
                [drones], formation.grid(2, 2, 1.0, (0, 0), 1), (0, 0)
            )

    def test_min_cost_matching_is_optimal(self) -> None:
        rng = random.Random(3)
        for n in range(1, 7):
            for _ in range(20):
                cost = [[rng.uniform(0, 10) for _ in range(n)] for _ in range(n)]
                match = formation.min_cost_matching(cost)
                assert sorted(match) == list(range(n))
                best = min(
                    sum(cost[i][p[i]] for i in range(n))
                    for p in itertools.permutations(range(n))
                )
                assert sum(cost[i][match[i]] for i in range(n)) == pytest.approx(best)

    def test_rotated_180(self) -> None:
        assert formation.rotated_180((1.0, 2.0, 0.5), (0.0, 1.0)) == (-1.0, 0.0, 0.5)


class TestOrbit:
    @pytest.mark.asyncio
    async def test_half_turn(self) -> None:
        swarm = make_swarm(Layout.grid(3, 3, 1.0))
        center = (0.0, 0.0)
        positions = {d: (d.pad.x, d.pad.y, 1.0) for d in swarm.drones if d.pad}

        end = await orbit(
            swarm, positions, center, math.pi, 0.0, yaw_duration=0.0, settle=0.0
        )

        for d, (x, y, z) in positions.items():
            assert end[d] == pytest.approx(formation.rotated_180((x, y, z), center))
            calls = d.cf.hlc.calls  # type: ignore[attr-defined]
            if (x, y) == (0.0, 0.0):
                # Centre drone turns on the spot (relative go_to)
                assert [c[0] for c in calls] == ["go_to"]
                assert calls[0][4] == pytest.approx(math.pi)
            else:
                assert [c[0] for c in calls] == ["go_to", "spiral"]
                radius = math.hypot(x, y)
                assert calls[1][1:4] == (math.pi, radius, radius)


def _segment_distance(
    p: tuple[float, ...], a: tuple[float, ...], b: tuple[float, ...]
) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
