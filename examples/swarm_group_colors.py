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
"""
Show swarm groups with the colour LED deck. Nothing flies.

The drones are read from a swarm file (see swarm.yaml next to this script).
Where each drone stands when the script starts is taken as its home pad.
The swarm is then split into groups so that no two drones in the same group
are closer than --min-distance, and every group lights up in its own colour.

Use this to check the groups before flying: drones with the same colour will
take off and land at the same time.

Example usage:
    python swarm_group_colors.py
    python swarm_group_colors.py --swarm-file my_swarm.yaml --min-distance 1.2
"""

import asyncio
import itertools
import time
from dataclasses import dataclass
from pathlib import Path

import tyro

from cflib2.swarm import Drone, Swarm, grouping
from cflib2.swarm.leds import set_color
from cflib2.toc_cache import FileTocCache

# One colour per group. If there are more groups than colours, they repeat.
COLORS = [
    ("red", (255, 0, 0)),
    ("green", (0, 255, 0)),
    ("blue", (0, 0, 255)),
    ("yellow", (255, 180, 0)),
    ("purple", (200, 0, 255)),
    ("cyan", (0, 200, 255)),
    ("orange", (255, 60, 0)),
    ("white", (255, 255, 255)),
]
OFF = (0, 0, 0)


@dataclass
class Args:
    swarm_file: Path = Path(__file__).parent / "swarm.yaml"
    """YAML file listing the drones"""
    min_distance: float = 0.7
    """Two drones closer than this (m) are never in the same group"""
    wait: bool = True
    """Wait for every drone to confirm its colour (--no-wait: only send them)"""


def closest_pair_distance(group: list[Drone]) -> float | None:
    """The smallest distance between two drones in the group, if it has two"""
    distances = [
        a.pad.distance_xy(b.pad.x, b.pad.y)
        for a, b in itertools.combinations(group, 2)
        if a.pad and b.pad
    ]
    return min(distances, default=None)


def print_groups(groups: list[list[Drone]]) -> None:
    for number, group in enumerate(groups, 1):
        color_name, _ = COLORS[(number - 1) % len(COLORS)]
        closest = closest_pair_distance(group)
        spacing = f", closest pair {closest:.2f} m" if closest is not None else ""

        print(f"\nGroup {number} ({color_name}): {len(group)} drones{spacing}")
        for d in group:
            if d.pad:
                print(f"    {d.name:<8} x={d.pad.x:6.2f}  y={d.pad.y:6.2f}")
    print()


async def main() -> None:
    args = tyro.cli(Args)

    swarm = Swarm.from_file(args.swarm_file, toc_cache=FileTocCache("cache"))
    print(f"Connecting to the drones in {args.swarm_file}...")

    async with swarm:
        print("Reading where every drone stands...")
        await swarm.set_home_pads()

        groups = grouping.by_min_separation(swarm.active, args.min_distance)
        print(
            f"{len(swarm)} drones split into {len(groups)} groups "
            f"(minimum distance {args.min_distance} m)"
        )
        print_groups(groups)

        try:
            # All groups at once, so no group waits for the previous one
            start = time.perf_counter()
            await asyncio.gather(
                *(
                    set_color(swarm, rgb, drones=group, wait=args.wait)
                    for (_, rgb), group in zip(itertools.cycle(COLORS), groups)
                )
            )
            what = "confirmed" if args.wait else "sent"
            print(f"Colours {what} in {(time.perf_counter() - start) * 1000:.0f} ms")

            await asyncio.to_thread(
                input, "LEDs are on. Press Enter to turn them off..."
            )
        finally:
            await set_color(swarm, OFF)


if __name__ == "__main__":
    asyncio.run(main())
