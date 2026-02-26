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
Stream console output from a Crazyflie until user interrupts (Ctrl+C).

Example usage:
    python console.py                              # Connect to default URI
    python console.py --uri radio://0/80/2M/E7E7E7E701   # Connect to custom URI
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
    context = LinkContext()
    cf = await Crazyflie.connect_from_uri(context, args.uri)
    print("Connected!")

    console = cf.console()

    try:
        print("\nConsole output (Press Ctrl+C to exit):")
        print("-" * 60)

        while True:
            lines: list[str] = await console.get_lines()
            for line in lines:
                print(line)

            # Small delay to avoid busy-waiting
            await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("Interrupted by user")

    finally:
        print("Disconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
