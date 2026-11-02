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
Fly a swarm standing on charging docks, using cflib2.swarm.

This example shows how to:
- Read the swarm from a swarm file (see swarm.yaml next to this script)
- Use where each drone stands as its home pad
- Take off in groups so neighbours do not disturb each other
- Colour groups with the LED deck
- Land on the docks and retry the drones that did not start charging
- Land everything automatically if a link is lost, an error occurs or
  Ctrl+C is pressed (the `swarm.flight()` block)

Example usage:
    python swarm_groups.py --swarm-file my_swarm.yaml --min-distance 1.0
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import tyro

from cflib2.swarm import Swarm, grouping, land_on_pads, return_to_pads, takeoff
from cflib2.swarm.leds import set_color
from cflib2.toc_cache import FileTocCache

GROUP_COLORS = [(0, 0, 255), (255, 150, 0), (0, 255, 0), (200, 0, 255)]


@dataclass
class Args:
    swarm_file: Path = Path(__file__).parent / "swarm.yaml"
    """YAML file listing the drones"""
    min_distance: float = 0.7
    """Drones closer than this (m) never take off at the same time"""
    height: float = 1.0
    """Hover height above the pads (m)"""


async def main() -> None:
    args = tyro.cli(Args)
    logging.basicConfig(level=logging.INFO)

    async with Swarm.from_file(
        args.swarm_file, toc_cache=FileTocCache("cache")
    ) as swarm:
        await swarm.set_home_pads()
        print(f"{len(swarm)} drones on pads")

        takeoff_groups = grouping.by_min_separation(swarm.active, args.min_distance)

        async with swarm.flight():
            await swarm.parallel(lambda d: d.cf.param().set("led.bitmask", 128))
            await takeoff(swarm, args.height, groups=takeoff_groups)

            for number, group in enumerate(takeoff_groups):
                color = GROUP_COLORS[number % len(GROUP_COLORS)]
                await set_color(swarm, color, drones=group)
            await asyncio.sleep(3.0)
            await set_color(swarm, (0, 0, 0))

            await return_to_pads(swarm, args.height)
            await swarm.parallel(lambda d: d.cf.param().set("stabilizer.controller", 2))
            await asyncio.sleep(1.0)

            not_docked = await land_on_pads(swarm, retries=2)
            if not_docked:
                print("Not docked:", ", ".join(d.name for d in not_docked))

            await swarm.parallel(lambda d: d.cf.param().set("led.bitmask", 0))


if __name__ == "__main__":
    asyncio.run(main())
