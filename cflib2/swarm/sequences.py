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
"""Swarm-wide high-level commander sequences.

High-level commander calls return as soon as the command is sent. These
helpers also wait for the motion to finish, so they can be chained.
Heights are relative to each drone's pad (or z=0 without a pad).
"""

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from typing import cast

from cflib2.swarm.drone import Drone
from cflib2.swarm.layout import Position
from cflib2.swarm.swarm import Swarm


def ground_z(d: Drone) -> float:
    return d.pad.z if d.pad is not None else 0.0


async def run_in_groups(
    swarm: Swarm,
    groups: Sequence[Sequence[Drone]],
    fn: Callable[[Drone], Awaitable[object]],
    interval: float,
) -> None:
    """Start `fn` on each group in turn, `interval` seconds apart.

    Groups start on a fixed schedule, so slow radio traffic for one group does
    not delay the timing of the next. Returns when the last group has been
    started, not when its motion is done.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()
    for i, group in enumerate(groups):
        await asyncio.sleep(max(0.0, start + i * interval - loop.time()))
        await swarm.parallel(fn, drones=group)


async def takeoff(
    swarm: Swarm,
    height: float,
    duration: float = 2.0,
    *,
    groups: Sequence[Sequence[Drone]] | None = None,
    interval: float | None = None,
    settle: float = 0.5,
) -> None:
    """Take off to `height` above the pad.

    With `groups`, each group starts `interval` seconds after the previous
    (default: once the previous group has reached its height).
    """
    await run_in_groups(
        swarm,
        groups if groups is not None else [swarm.active],
        lambda d: d.hlc.take_off(ground_z(d) + height, None, duration, None),
        interval if interval is not None else duration + settle,
    )
    await asyncio.sleep(duration + settle)


async def land(
    swarm: Swarm,
    height: float = 0.0,
    duration: float = 3.0,
    *,
    groups: Sequence[Sequence[Drone]] | None = None,
    interval: float | None = None,
    settle: float = 0.5,
    stop: bool = False,
) -> None:
    """Land straight down to `height` above the pad (default: pad height).

    The firmware turns the motors off by itself when the landing is done, at
    whatever height the drone has reached by then. A small negative `height`
    (e.g. -0.03) aims slightly below the pad, so the drone touches down
    before the motors are cut instead of dropping the last centimetres.
    With `stop`, a high-level stop is sent as well afterwards.
    """
    groups = groups if groups is not None else [swarm.active]
    await run_in_groups(
        swarm,
        groups,
        lambda d: d.hlc.land(ground_z(d) + height, None, duration, None),
        interval if interval is not None else duration + settle,
    )
    await asyncio.sleep(duration + settle)
    if stop:
        await swarm.parallel(
            lambda d: d.hlc.stop(None), drones=[d for g in groups for d in g]
        )


async def go_to(
    swarm: Swarm,
    targets: Mapping[Drone, Position] | Callable[[Drone], Position],
    duration: float,
    *,
    yaw: float = 0.0,
    linear: bool = False,
    settle: float = 0.5,
    wait: bool = True,
) -> None:
    """Fly each drone to an absolute target.

    `targets` is either a mapping (drones missing from it stay put) or a
    function from drone to position.
    """
    target_of: Callable[[Drone], Position]
    if isinstance(targets, Mapping):
        mapping = cast(Mapping[Drone, Position], targets)
        target_of = mapping.__getitem__
        drones = [d for d in swarm.active if d in mapping]
    else:
        target_of = targets
        drones = swarm.active
    await swarm.parallel(
        lambda d: d.hlc.go_to(
            *target_of(d), yaw, duration, relative=False, linear=linear, group_mask=None
        ),
        drones=drones,
    )
    if wait:
        await asyncio.sleep(duration + settle)


async def return_to_pads(
    swarm: Swarm,
    height: float,
    duration: float = 4.0,
    *,
    drones: Iterable[Drone] | None = None,
    settle: float = 0.5,
) -> None:
    """Fly the drones (default: all active) to `height` above their own pad"""
    targets = swarm.active if drones is None else drones
    await go_to(
        swarm,
        {d: (d.pad.x, d.pad.y, d.pad.z + height) for d in targets if d.pad is not None},
        duration,
        settle=settle,
    )


async def orbit(
    swarm: Swarm,
    positions: Mapping[Drone, Position],
    center: tuple[float, float],
    angle: float,
    duration: float,
    *,
    clockwise: bool = False,
    yaw_duration: float = 2.0,
    settle: float = 0.5,
) -> dict[Drone, Position]:
    """Fly every drone along a circle around `center` by `angle` radians,
    all at the same time, keeping their height.

    `positions` are where the drones hover now. First each drone turns to
    face along its circle (`yaw_duration`), then they all fly the arc with
    the high-level commander spiral. A drone at the centre turns on the spot.

    Returns where every drone ends up.
    """
    sign = -1 if clockwise else 1
    cx, cy = center
    radius = {d: math.hypot(p[0] - cx, p[1] - cy) for d, p in positions.items()}
    on_circle = [d for d in positions if radius[d] >= _MIN_ORBIT_RADIUS]
    in_center = [d for d in positions if radius[d] < _MIN_ORBIT_RADIUS]

    def tangent_yaw(d: Drone) -> float:
        dx, dy = positions[d][0] - cx, positions[d][1] - cy
        return math.atan2(dx, -dy) if sign > 0 else math.atan2(-dx, dy)

    await swarm.parallel(
        lambda d: d.hlc.go_to(
            *positions[d],
            tangent_yaw(d),
            yaw_duration,
            relative=False,
            linear=False,
            group_mask=None,
        ),
        drones=on_circle,
    )
    await asyncio.sleep(yaw_duration + settle)

    await asyncio.gather(
        swarm.parallel(
            lambda d: d.hlc.spiral(
                angle, radius[d], radius[d], 0.0, duration, False, clockwise, None
            ),
            drones=on_circle,
        ),
        swarm.parallel(
            lambda d: d.hlc.go_to(
                0.0,
                0.0,
                0.0,
                sign * angle,
                duration,
                relative=True,
                linear=False,
                group_mask=None,
            ),
            drones=in_center,
        ),
    )
    await asyncio.sleep(duration + settle)

    cos_a, sin_a = math.cos(sign * angle), math.sin(sign * angle)
    return {
        d: (
            cx + (x - cx) * cos_a - (y - cy) * sin_a,
            cy + (x - cx) * sin_a + (y - cy) * cos_a,
            z,
        )
        for d, (x, y, z) in positions.items()
    }


# Closer to the centre than this (m), a drone turns on the spot instead
_MIN_ORBIT_RADIUS = 0.05
