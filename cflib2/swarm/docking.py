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
"""Landing on charging docks, with verification and retries"""

import asyncio
import logging
from dataclasses import dataclass
from collections.abc import Awaitable, Callable, Iterable

from cflib2.swarm.drone import Drone
from cflib2.swarm.grouping import by_min_separation
from cflib2.swarm.sequences import go_to, ground_z, takeoff
from cflib2.swarm.swarm import Swarm

logger = logging.getLogger(__name__)

# pm.state values
PM_CHARGING = 1
PM_CHARGED = 2


async def is_charging(d: Drone) -> bool:
    """Docked check: the power management reports charging or fully charged"""
    state = int((await d.read_log(["pm.state"]))["pm.state"])
    return state in (PM_CHARGING, PM_CHARGED)


async def undocked(
    drones: Iterable[Drone], check: Callable[[Drone], Awaitable[bool]] = is_charging
) -> list[Drone]:
    """The drones that fail `check`. A drone whose check raises counts as undocked."""
    drones = [d for d in drones if d.active]
    results = await asyncio.gather(*(check(d) for d in drones), return_exceptions=True)
    failed = []
    for d, r in zip(drones, results):
        if r is not True:
            if isinstance(r, BaseException):
                logger.warning("Dock check failed on %s: %s", d, r)
            failed.append(d)
    return failed


@dataclass
class DockingSettings:
    approach_height: float = 0.2
    """Height (m) above the pad where the drone stops before landing"""
    approach_duration: float = 2.0
    """Time (s) to move to the approach point right above the pad"""
    approach_tolerance: float = 0.01
    """A drone lands once its smoothed position is within this distance (m)
    of the point above its pad, on every axis (see `Drone.wait_until_at`)"""
    approach_smoothing: float = 0.1
    """Weight of each new position sample (taken every 100 ms) in the
    smoothed position"""
    approach_timeout: float = 10.0
    """Land anyway if a drone has not settled after this long (s)"""
    land_duration: float = 0.8
    """Time (s) for the final landing from the approach point. The firmware
    cuts the motors when this time is up, so if it is too short the drone is
    still above the pad and drops"""
    land_height: float = 0.0
    """Height (m) above the pad the final landing aims for. Slightly negative
    (e.g. -0.03) makes the drone touch down before the motors are cut"""
    settle: float = 3.0
    """Wait (s) after landing before checking, so charging can start"""
    takeoff_duration: float = 1.0
    """Time (s) for a re-try to take off straight to `approach_height`"""
    arm_delay: float = 1.0
    """Wait (s) after arming before taking off on a re-try"""
    min_separation: float = 1.0
    """Re-tries are split into groups with no two drones closer than this (m),
    so a re-launching drone does not blow docked neighbours off their pads"""
    check: Callable[[Drone], Awaitable[bool]] = is_charging
    """Returns True when a drone is docked"""


async def precision_land(
    swarm: Swarm, drones: Iterable[Drone], settings: DockingSettings | None = None
) -> None:
    """Land on the pads like the on-board landing of the drone show app:

    1. Move to `approach_height` right above the pad in `approach_duration`.
    2. Right away, each drone starts smoothing its position and waits until
       the smoothed position is within `approach_tolerance` of that point on
       every axis (`Drone.wait_until_at`). After `approach_timeout` it lands
       anyway, with a warning; the on-board version has no timeout.
    3. Each drone lands on its own as soon as it is ready, in
       `land_duration` seconds, aiming for `land_height` above the pad.

    If a drone's position cannot be followed (e.g. a log error), it still
    lands, after the approach plus a fixed 2 s hover, with a warning.

    The drones should be close to their pads already (see `return_to_pads`);
    the first step only corrects the last bit of position. Returns once
    every drone has landed.
    """
    settings = settings or DockingSettings()
    targets = _with_pads(drones)
    approach = {
        d: (d.pad.x, d.pad.y, d.pad.z + settings.approach_height)
        for d in targets
        if d.pad is not None
    }
    loop = asyncio.get_running_loop()
    approach_started = loop.time()
    await go_to(swarm, approach, settings.approach_duration, wait=False)

    async def settle_and_land(d: Drone) -> None:
        try:
            settled = await d.wait_until_at(
                approach[d],
                settings.approach_tolerance,
                settings.approach_smoothing,
                settings.approach_timeout,
            )
        except Exception as e:
            # Not being able to follow the position must not keep a drone in
            # the air: give it the approach time plus a fixed hover instead
            logger.warning(
                "%s: cannot follow its position (%s), landing after a fixed wait",
                d,
                e,
            )
            remaining = approach_started + settings.approach_duration - loop.time()
            await asyncio.sleep(max(0.0, remaining) + _FALLBACK_HOVER)
            settled = True
        if not settled:
            logger.warning(
                "%s did not settle above its pad within %.0f s, landing anyway",
                d,
                settings.approach_timeout,
            )
        await d.hlc.land(
            ground_z(d) + settings.land_height, None, settings.land_duration, None
        )

    await swarm.parallel(settle_and_land, drones=targets)
    await asyncio.sleep(settings.land_duration + 0.5)


async def check_docked(
    drones: Iterable[Drone], settings: DockingSettings | None = None
) -> list[Drone]:
    """Wait `settle` seconds so charging can start, then return the drones
    that are not docked. Needs no flying, so it can run in the background
    while other drones land."""
    settings = settings or DockingSettings()
    targets = [d for d in drones if d.active]
    await asyncio.sleep(settings.settle)
    return await undocked(targets, settings.check)


async def land_and_check(
    swarm: Swarm, drones: Iterable[Drone], settings: DockingSettings | None = None
) -> list[Drone]:
    """Land once on the pads (`precision_land`) and return the drones that
    did not dock (`check_docked`)."""
    targets = _with_pads(drones)
    await precision_land(swarm, targets, settings)
    return await check_docked(targets, settings)


async def redock(
    swarm: Swarm,
    drones: Iterable[Drone],
    settings: DockingSettings | None = None,
    retries: int = 3,
) -> list[Drone]:
    """Re-try landing for drones that are on the ground but not docked.

    Each attempt, like the on-board landing of the drone show app, the
    undocked drones take off straight to `approach_height` above their pad
    and land again with `precision_land`: re-centre at that height, wait
    until settled, land. The approach and the landing are the same as for
    the first landing. Before every attempt the supervisors are checked
    (`Swarm.skip_unhealthy`): locked, crashed or tumbled drones are taken out
    with a warning. Returns the drones that still are not docked after
    `retries` attempts, not counting the ones taken out.
    """
    settings = settings or DockingSettings()
    failed = _with_pads(drones)

    for attempt in range(1, retries + 1):
        # A locked, crashed or tumbled drone cannot re-try
        await swarm.skip_unhealthy(failed)
        failed = [d for d in failed if d.active]
        if not failed:
            break
        groups = by_min_separation(failed, settings.min_separation)
        logger.warning(
            "Docking attempt %d/%d for %s in %d group(s)",
            attempt,
            retries,
            ", ".join(d.name for d in failed),
            len(groups),
        )
        for group in groups:
            await _redock_group(swarm, group, settings)
        await asyncio.sleep(settings.settle)
        failed = await undocked(failed, settings.check)

    if failed:
        logger.error(
            "Not docked after %d retries: %s",
            retries,
            ", ".join(d.name for d in failed),
        )
    return failed


async def land_on_pads(
    swarm: Swarm,
    drones: Iterable[Drone] | None = None,
    settings: DockingSettings | None = None,
    retries: int = 3,
) -> list[Drone]:
    """Land on the pads and re-try the drones that did not dock.

    `land_and_check` followed by `redock`. Returns the drones that still are
    not docked after `retries` attempts.
    """
    targets = swarm.active if drones is None else drones
    failed = await land_and_check(swarm, targets, settings)
    return await redock(swarm, failed, settings, retries)


# Hover (s) above the pad before landing when the position cannot be followed
_FALLBACK_HOVER = 2.0


def _with_pads(drones: Iterable[Drone]) -> list[Drone]:
    targets = [d for d in drones if d.active]
    missing_pad = [d for d in targets if d.pad is None]
    if missing_pad:
        raise ValueError(
            f"No pad assigned to: {', '.join(d.name for d in missing_pad)}"
        )
    return targets


async def _redock_group(
    swarm: Swarm, group: list[Drone], settings: DockingSettings
) -> None:
    await swarm.arm(drones=group)
    await asyncio.sleep(settings.arm_delay)
    await takeoff(
        swarm,
        settings.approach_height,
        settings.takeoff_duration,
        groups=[group],
        settle=0.0,
    )
    await precision_land(swarm, group, settings)
