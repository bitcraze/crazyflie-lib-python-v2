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
Simple example showing how to fly the Crazyflie using supervisor state.

Based on the current state, the Crazyflie will arm (if it can be armed),
take off (if it can fly), and land (if it is flying). A safety check is
performed before each action.

Tested with the Flow deck V2 and the Lighthouse positioning system.

Change the URI variable to your Crazyflie configuration.
"""

import asyncio
from dataclasses import dataclass

import tyro

from cflib2 import Crazyflie, LinkContext
from cflib2.supervisor import Supervisor


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""


async def safety_check(supervisor: Supervisor) -> None:
    if await supervisor.is_crashed():
        raise RuntimeError("Crazyflie crashed!")
    if await supervisor.is_locked():
        raise RuntimeError("Crazyflie locked!")
    if await supervisor.is_tumbled():
        raise RuntimeError("Crazyflie tumbled!")


async def run_sequence(cf: Crazyflie) -> None:
    supervisor = cf.supervisor()
    hlc = cf.high_level_commander()

    await safety_check(supervisor)

    if await supervisor.can_be_armed():
        print("The Crazyflie can be armed...arming!")
        await safety_check(supervisor)
        await supervisor.send_arming_request(True)
        await asyncio.sleep(1)

    await safety_check(supervisor)

    if await supervisor.can_fly():
        print("The Crazyflie can fly...taking off!")
        await hlc.take_off(1.0, None, 2.0, None)
        await asyncio.sleep(3)

    await safety_check(supervisor)

    if await supervisor.is_flying():
        print("The Crazyflie is flying...landing!")
        await hlc.land(0.0, None, 2.0, None)
        await asyncio.sleep(3)

    await safety_check(supervisor)


async def main() -> None:
    args = tyro.cli(Args)

    print(f"Connecting to {args.uri}...")
    ctx = LinkContext()
    cf = await Crazyflie.connect_from_uri(ctx, args.uri)
    print("Connected!")

    await asyncio.sleep(0.5)

    try:
        await run_sequence(cf)
        print("Sequence completed successfully!")
    except RuntimeError as e:
        print(f"Safety check failed: {e}")
    finally:
        print("Disconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
