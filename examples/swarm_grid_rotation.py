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
Fly the swarm to a hover grid, turn it a full turn and land back on the docks.

1. Drones whose supervisor reports locked, crashed or tumbled are left
   out with a warning; they would accept commands but not fly. So are
   drones with a battery level below --min-battery. The others
   are split into groups with no two drones closer than --min-distance.
   Each group gets its own LED colour. The check is repeated right before
   each group arms, and before every docking re-try.
2. Group by group: arm, take off and fly to the hover grid. Groups take
   off --next-group-delay seconds apart, so a group does not have to wait
   for the previous one to arrive. With --tilt-x / --tilt-y the grid is
   slanted: each slot gets its own height, the grid seen from above stays
   the same.
   The grid is filled farthest from the docks first, so no drone has to pass
   a drone that is already hovering. A later group has a shorter way to go
   in the same time, so it does not catch up with the group in front.
   Within a group, drones are matched to slots so they keep their distance
   to each other in flight (see cflib2.swarm.formation.assign_slots).
3. The whole grid turns a full 360 degrees around its centre, so every drone
   is back in its own slot. (After a half turn the way back to the own
   docks would make the drones of a group meet in the middle.)
4. Group by group, last group first: it hovers closest to the docks, so it
   does not pass any drone that is still hovering. Fly back above the own
   dock and land once: stop 0.2 m above the dock, wait until the drone's
   smoothed position is within 1 cm of that point on every axis, then land
   in --land-duration seconds. The way back is the way out in reverse, so the
   drones keep the same distance. The next group starts flying back
   --next-return-delay seconds after the previous one started, or, if not
   given, once the previous group has landed. Whether a group is charging
   is checked on the side, so the next group does not wait for that.
5. All drones that did not dock (not charging) re-try together, no matter
   which group they took off with: each attempt they are split into new
   groups by --min-distance, and after it only the ones still not charging
   try again, until --retries attempts. If a drone loses its link or
   fails during the re-tries, only that drone is dropped; the others go on.
   Before that, any lost link lands the whole swarm.

Use --dry-run first: it connects, reads where the drones stand and prints the
plan without flying.

Example usage:
    python swarm_grid_rotation.py --center 0.5 1.0 --dry-run
    python swarm_grid_rotation.py --center 0.5 1.0 --spacing 0.6 --height 1.0
"""

import asyncio
import itertools
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import tyro

from cflib2.swarm import (
    DockingSettings,
    Drone,
    OnDroneLost,
    OnError,
    Swarm,
    check_docked,
    formation,
    go_to,
    grouping,
    orbit,
    precision_land,
    redock,
    return_to_pads,
    takeoff,
)
from cflib2.swarm.layout import Position
from cflib2.swarm.leds import set_color
from cflib2.toc_cache import FileTocCache

COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 180, 0),
    (200, 0, 255),
    (0, 200, 255),
    (255, 60, 0),
    (255, 255, 255),
]
OFF = (0, 0, 0)


@dataclass
class Args:
    center: tuple[float, float]
    """Centre (x, y) of the hover grid (m)"""
    swarm_file: Path = Path(__file__).parent / "swarm.yaml"
    """YAML file listing the drones"""
    spacing: float = 0.6
    """Distance between hover grid slots (m)"""
    height: float = 1.0
    """Height of the hover grid (m), in its centre when tilted"""
    tilt_x: float = 15.0
    """Slope of the grid along x (degrees): it rises in +x for positive values"""
    tilt_y: float = 15.0
    """Slope of the grid along y (degrees): it rises in +y for positive values"""
    min_distance: float = 0.5
    """Two drones closer than this (m) are never in the same group"""
    min_battery: int = 70
    """Leave out drones with a battery level below this (%)"""
    takeoff_duration: float = 2.0
    """Time (s) to take off"""
    transit_duration: float = 6.0
    """Time (s) to fly between the docks and the grid"""
    next_group_delay: float = 8.0
    """Seconds between the takeoffs of two groups"""
    next_return_delay: float | None = None
    """Seconds after a group starts flying back until the next group does
    (default: wait until the previous group has landed)"""
    rotation_duration: float = 12.0
    """Time (s) for the full turn"""
    land_duration: float = 1.2
    """Time (s) for the final landing from 0.2 m above the dock"""
    land_height: float = 0.0
    """Height (m) above the dock the landing aims for, e.g. -0.03 to touch down
    before the motors are cut"""
    retries: int = 5
    """Maximum number of re-tries per group to land on the docks"""
    clockwise: bool = False
    """Turn clockwise (seen from above) instead of counter-clockwise"""
    dry_run: bool = False
    """Only print the plan, do not fly"""


def print_plan(
    groups: list[list[Drone]],
    slot_of: dict[Drone, Position],
    slots: list[Position],
    entry: tuple[float, float],
) -> None:
    group_of = {d: number for number, group in enumerate(groups, 1) for d in group}
    drone_at = {slot_of[d]: d for d in slot_of}
    fill_number = {s: i for i, s in enumerate(formation.fill_order(slots, entry), 1)}

    print(f"\nDocks centre (entry point): x={entry[0]:.2f} y={entry[1]:.2f}")
    print("\nHover grid seen from above, +x right, +y up.")
    print("Each slot: fill order / group, '.' = empty\n")
    xs = sorted({s[0] for s in slots})
    ys = sorted({s[1] for s in slots}, reverse=True)
    for y in ys:
        row = []
        for x in xs:
            slot = next(s for s in slots if s[0] == x and s[1] == y)
            d = drone_at.get(slot)
            row.append(f"{fill_number[slot]:>2}/{group_of[d]}" if d else "  . ")
        print("   " + "  ".join(row))

    for number, group in enumerate(groups, 1):
        closest = formation.closest_approach(group, slot_of)
        spacing = (
            f", closest approach in flight {closest:.2f} m" if len(group) > 1 else ""
        )
        print(f"\nGroup {number}: {len(group)} drones{spacing}")
        for d in group:
            x, y, z = slot_of[d]
            print(f"    {d.name:<8} -> slot x={x:5.2f} y={y:5.2f} z={z:.2f}")
    print()


async def main() -> None:
    args = tyro.cli(Args)
    logging.basicConfig(level=logging.INFO)

    swarm = Swarm.from_file(args.swarm_file, toc_cache=FileTocCache("cache"))
    print(f"Connecting to the drones in {args.swarm_file}...")

    async with swarm:
        print("Reading where every drone stands...")
        await swarm.set_home_pads()

        # Locked, crashed or tumbled drones accept commands but will not fly:
        # leave them out of the plan
        if skipped := await swarm.skip_unhealthy():
            print(f"Leaving out: {', '.join(d.name for d in skipped)}")

        print("Battery levels:")
        for d, battery in (await swarm.read_batteries()).items():
            print(f"    {d.name:<8} {battery}")
        if skipped := await swarm.skip_low_battery(args.min_battery):
            names = ", ".join(d.name for d in skipped)
            print(f"Leaving out (battery below {args.min_battery}%): {names}")

        # Plan: groups, hover grid and which drone goes to which slot
        groups = grouping.by_min_separation(swarm.active, args.min_distance)
        entry = formation.centroid(swarm.active)
        rows, cols = formation.grid_shape(len(swarm))
        slots = formation.grid(
            rows,
            cols,
            args.spacing,
            args.center,
            args.height,
            tilt_x=args.tilt_x,
            tilt_y=args.tilt_y,
        )
        slot_of = formation.assign_slots(groups, slots, entry)

        print(f"{len(swarm)} drones, {len(groups)} groups, {rows}x{cols} hover grid")
        print_plan(groups, slot_of, slots, entry)
        if args.dry_run:
            return

        docking = DockingSettings(
            land_duration=args.land_duration,
            land_height=args.land_height,
            min_separation=args.min_distance,
        )

        try:
            for (r, g, b), group in zip(itertools.cycle(COLORS), groups):
                await set_color(swarm, (r, g, b), drones=group, wait=False)

            # Arming happens per group, right before it takes off
            async with swarm.flight(arm=False):

                async def launch(number: int, group: list[Drone]) -> None:
                    await swarm.skip_unhealthy(group)
                    if not any(d.active for d in group):
                        print(f"Group {number}: no healthy drones left, skipping")
                        return
                    print(f"Group {number}: arming and taking off")
                    await swarm.arm(drones=group)
                    await asyncio.sleep(1.0)
                    await takeoff(
                        swarm, args.height, args.takeoff_duration, groups=[group]
                    )
                    print(f"Group {number}: flying to the hover grid")
                    await go_to(
                        swarm, {d: slot_of[d] for d in group}, args.transit_duration
                    )

                # Groups can overlap; if one fails, the others are cancelled
                # and the flight block lands everyone. Done when all arrived.
                async with asyncio.TaskGroup() as launching:
                    for number, group in enumerate(groups, 1):
                        if number > 1:
                            await asyncio.sleep(args.next_group_delay)
                        launching.create_task(launch(number, group))

                print("Turning the grid a full turn")
                await orbit(
                    swarm,
                    slot_of,
                    args.center,
                    2 * math.pi,
                    args.rotation_duration,
                    clockwise=args.clockwise,
                )

                not_docked: list[Drone] = []

                async def check_group(number: int, group: list[Drone]) -> None:
                    failed = await check_docked(group, docking)
                    not_docked.extend(failed)
                    if failed:
                        names = ", ".join(d.name for d in failed)
                        print(f"Group {number}: not docked: {names}")

                async def return_and_land(number: int, group: list[Drone]) -> None:
                    print(f"Group {number}: flying back and landing")
                    await return_to_pads(
                        swarm, args.height, args.transit_duration, drones=group
                    )
                    await precision_land(swarm, group, docking)
                    # Charging is checked on the side: the next group does not
                    # have to wait for it
                    returning.create_task(check_group(number, group))

                # Last group first, it is closest to the docks. Groups can
                # overlap; if one fails, the others are cancelled and the
                # flight block lands everyone
                async with asyncio.TaskGroup() as returning:
                    for number, group in reversed(list(enumerate(groups, 1))):
                        group_done = returning.create_task(
                            return_and_land(number, group)
                        )
                        if args.next_return_delay is None:
                            await group_done
                        else:
                            await asyncio.sleep(args.next_return_delay)

            # Everyone is on or right above the docks now. From here a drone
            # that loses its link, or a command that fails on one, only takes
            # that drone out; the others keep re-trying.
            swarm.on_error = OnError.CONTINUE
            # All undocked drones together, regardless of their takeoff group:
            # every attempt they are split into new groups by --min-distance,
            # and only the ones still not charging afterwards try again
            async with swarm.flight(arm=False, on_drone_lost=OnDroneLost.CONTINUE):
                if not_docked:
                    names = ", ".join(d.name for d in not_docked)
                    print(f"Re-trying {len(not_docked)} drone(s): {names}")
                    gave_up = await redock(swarm, not_docked, docking, args.retries)
                    if gave_up:
                        print(f"Gave up on: {', '.join(d.name for d in gave_up)}")

            dropped = [d for d in swarm.drones if not d.active]
            if dropped:
                print("Dropped during re-tries (check by hand):")
                for d in dropped:
                    print(f"    {d.name}: {d.status.value}, {d.error}")
            print("Done")
        finally:
            await set_color(swarm, OFF)


if __name__ == "__main__":
    asyncio.run(main())
