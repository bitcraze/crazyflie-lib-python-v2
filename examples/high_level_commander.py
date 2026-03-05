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

import asyncio
from dataclasses import dataclass

import tyro
import math

from cflib2 import Crazyflie, LinkContext


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""


async def main() -> None:
    args = tyro.cli(Args)

    ctx = LinkContext()

    print(f"Connecting to {args.uri}...")
    cf = await Crazyflie.connect_from_uri(ctx, args.uri)
    print("Connected!")

    hlc = cf.high_level_commander()

    try:
        print("Taking off...")
        await hlc.take_off(0.5, None, 2.0, None)
        await asyncio.sleep(2.0)

        print("Going to first position...")
        await hlc.go_to(0.0, 0.5, 0.5, 0.0, 2.0, False, False, None)
        await asyncio.sleep(2.0)

        print("Going to second position...")
        await hlc.go_to(-0.25, 0.0, 0.5, 0.0, 2.0, False, False, None)
        await asyncio.sleep(2.0)

        print("Moving in a spiral...")
        await hlc.spiral(-math.pi * 2.0, 0.5, 0.5, 0.0, 2.0, True, True, None)
        await asyncio.sleep(2.0)
    finally:
        print("Landing...")
        await hlc.land(0.0, None, 2.0, None)
        await asyncio.sleep(2.0)

        await hlc.stop(None)
        print("Done")

        await cf.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
