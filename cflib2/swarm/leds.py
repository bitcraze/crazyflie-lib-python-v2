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
"""Colour LED deck helpers"""

from collections.abc import Iterable

from cflib2.swarm.drone import Drone
from cflib2.swarm.swarm import OnError, Swarm

RGB = tuple[int, int, int]

BOTTOM = "colorLedBot.wrgb8888"
TOP = "colorLedTop.wrgb8888"


def rgb_to_wrgb(r: int, g: int, b: int) -> int:
    """Pack 8-bit RGB into the WRGB8888 format, moving the common part to white"""
    w = min(r, g, b)
    return (w << 24) | ((r - w) << 16) | ((g - w) << 8) | (b - w)


async def set_color(
    swarm: Swarm,
    color: RGB,
    drones: Iterable[Drone] | None = None,
    param: str = BOTTOM,
    *,
    wait: bool = True,
) -> None:
    """Set the colour LED deck on the given drones (default: all active).

    `wait` is passed on to `Swarm.parallel`: wait for every drone to confirm,
    or only send. A failing LED is not worth stopping a show for, so errors
    are logged and the drone stays active (`OnError.IGNORE`).
    """
    wrgb = rgb_to_wrgb(*color)
    await swarm.parallel(
        lambda d: d.cf.param().set(param, wrgb),
        drones=drones,
        on_error=OnError.IGNORE,
        wait=wait,
    )
