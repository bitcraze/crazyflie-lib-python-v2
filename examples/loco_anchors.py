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
Example that connects to the Crazyflie at `URI` and reads the Loco
Positioning anchor data: the configured anchor IDs, the currently active
anchor IDs and the position of each anchor.

Requires a Loco Positioning deck.

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
        data = await cf.memory().read_loco_anchor_data()

        print(f"Anchor IDs: {data.anchor_ids}")
        print(f"Active anchor IDs: {data.active_anchor_ids}")
        for anchor_id in data.anchor_ids:
            anchor = data.anchors[anchor_id]
            x, y, z = anchor.position
            active = "active" if anchor_id in data.active_anchor_ids else "inactive"
            valid = "valid" if anchor.is_valid else "invalid"
            print(
                f"  Anchor {anchor_id}: ({x:.2f}, {y:.2f}, {z:.2f}) {valid}, {active}"
            )

    finally:
        print("Disconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
