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
Power cycle the STM32 domain on a swarm of Crazyflies concurrently.

This example shows how to:
- Share a single LinkContext between multiple Crazyflies
- Power off the STM32 and decks on all drones in parallel
- Wait, then power them all back on in parallel
- Report per-drone failures without aborting the others

The nRF51 stays powered while the STM32 domain is off, which is what allows
the drones to be woken up again over the radio. No full connection is needed.

Example usage:
    python swarm_power_cycle_stm32.py
"""

import asyncio
from collections.abc import Awaitable, Callable

from cflib2 import Crazyflie, LinkContext

URIS = [
    "radio://0/80/2M/E7E7E7E701",
    "radio://0/80/2M/E7E7E7E702",
    "radio://0/80/2M/E7E7E7E703",
    "radio://0/80/2M/E7E7E7E704",
    "radio://0/80/2M/E7E7E7E705",
    "radio://0/80/2M/E7E7E7E706",
    "radio://0/80/2M/E7E7E7E707",
    "radio://0/80/2M/E7E7E7E708",
    "radio://0/80/2M/E7E7E7E709",
]

OFF_DURATION_S = 10.0


async def run_on_all(
    context: LinkContext, action: Callable[[LinkContext, str], Awaitable[None]]
) -> None:
    """Run a power action on all URIs concurrently and report the results."""
    results = await asyncio.gather(
        *[action(context, uri) for uri in URIS],
        return_exceptions=True,
    )

    for uri, result in zip(URIS, results):
        if isinstance(result, Exception):
            print(f"  ✗ {uri}: {result}")
        else:
            print(f"  ✓ {uri}")


async def main() -> None:
    # Shared LinkContext for all drones
    context = LinkContext()

    print(f"Powering off STM32 domain on {len(URIS)} Crazyflies...")
    await run_on_all(context, Crazyflie.power_off_stm32_domain)

    print(f"\nWaiting {OFF_DURATION_S:.0f} seconds...")
    await asyncio.sleep(OFF_DURATION_S)

    print(f"\nPowering on STM32 domain on {len(URIS)} Crazyflies...")
    await run_on_all(context, Crazyflie.power_on_stm32_domain)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
