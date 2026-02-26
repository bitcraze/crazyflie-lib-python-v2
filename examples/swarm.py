# ,---------,       ____  _ __
# |  ,-^-,  |      / __ )(_) /_______________ _____  ___
# | (  O  ) |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
# | / ,--'  |    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#    +------`   /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
# Copyright (C) 2025 Bitcraze AB
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""
Demonstrate LED blinking on multiple Crazyflies using a shared LinkContext.

This example shows how to:
- Share a single LinkContext between multiple Crazyflie connections
- Connect to multiple drones through the same radio
- Blink LEDs on all drones in parallel using parameter setting
- Optionally use TOC file caching for faster reconnections

The shared LinkContext enables efficient radio multiplexing for swarm operations.

Example usage:
    python swarm_blink.py radio://0/80/2M/E7E7E7E701 radio://0/80/2M/E7E7E7E702
    python swarm_blink.py --cache radio://0/80/2M/E7E7E7E701 radio://0/80/2M/E7E7E7E702
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import tyro

from cflib2 import Crazyflie, LinkContext, FileTocCache, NoTocCache


@dataclass
class Args:
    uris: list[str] = field(
        default_factory=lambda: [
            "radio://0/80/2M/E7E7E7E701",
            "radio://0/80/2M/E7E7E7E702",
        ]
    )
    """Crazyflie URIs"""
    cache: bool = False
    """Enable TOC file caching (uses cache/ in project root)"""


async def blink(cf: Crazyflie) -> None:
    """Blink LEDs on one Crazyflie."""
    print(f"[{cf}] Starting blink sequence")
    param = cf.param()
    param_name = "led.bitmask"

    for _ in range(10):
        await param.set(param_name, 212)
        await asyncio.sleep(2)
        await param.set(param_name, 0)
        await asyncio.sleep(2)

    print(f"[{cf}] Done blinking")


async def main() -> None:
    args = tyro.cli(Args)

    # Set up TOC cache (file-based if --cache specified, otherwise no caching)
    if args.cache:
        cache_dir = str(Path(__file__).parent.parent / "cache")
        cache = FileTocCache(cache_dir)
        print(f"Using TOC cache: {cache.get_cache_dir()}")
    else:
        cache = NoTocCache()

    # Shared LinkContext for all connections
    context = LinkContext()

    # Connect to all concurrently
    print(f"Connecting to {len(args.uris)} Crazyflies...")
    cfs = await asyncio.gather(
        *[Crazyflie.connect_from_uri(context, uri, cache) for uri in args.uris]
    )
    print("All connected!\n")

    try:
        # Blink LEDs on all drones in parallel
        await asyncio.gather(*[blink(cf) for cf in cfs])

    finally:
        # Disconnect all concurrently
        print("\nDisconnecting...")
        await asyncio.gather(*[cf.disconnect() for cf in cfs])
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
