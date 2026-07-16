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
Reads the Crazyflie's supervisor state 20 times at 0.5 s intervals.

Hold the Crazyflie in your hand and tilt it upside down to observe state
changes. Once the tilt exceeds ~90°, can_fly becomes False and is_tumbled
becomes True.

Change the URI variable to your Crazyflie configuration.
"""

import asyncio
from dataclasses import dataclass

import tyro

from cflib2 import Crazyflie, LinkContext


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""


async def main() -> None:
    args = tyro.cli(Args)

    print(f"Connecting to {args.uri}...")
    ctx = LinkContext()
    cf = await Crazyflie.connect_from_uri(ctx, args.uri)
    print("Connected!")

    try:
        supervisor = cf.supervisor()
        print("Reading supervisor state:")
        for _ in range(20):
            print("=" * 78)
            # One read gives a consistent snapshot of all state flags
            state = await supervisor.read()
            print(f"Can fly:       {state.can_fly}")
            print(f"Is tumbled:    {state.is_tumbled}")
            print(f"Bitfield:      0x{state.raw:04x}")
            print(f"Active states: {state.active_states()}")
            print("=" * 78)
            await asyncio.sleep(0.5)
    finally:
        print("Disconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
