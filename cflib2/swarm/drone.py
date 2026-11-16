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
"""A single member of a swarm"""

import asyncio
import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from cflib2 import Crazyflie
from cflib2.swarm.layout import Pad, Position

if TYPE_CHECKING:
    from cflib2._rust import HighLevelCommander


# pm.state values
POWER_STATES = {
    0: "battery",
    1: "charging",
    2: "charged",
    3: "low power",
    4: "shutdown",
}


@dataclass(frozen=True)
class Battery:
    """One reading of the power management"""

    level: int
    """Charge level (%)"""
    voltage: float
    """Battery voltage (V)"""
    state: int
    """pm.state, see `state_name`"""

    @property
    def state_name(self) -> str:
        return POWER_STATES.get(self.state, f"unknown ({self.state})")

    @property
    def charging(self) -> bool:
        """On a charger: charging or fully charged"""
        return self.state in (1, 2)

    def __str__(self) -> str:
        return f"{self.level}% {self.voltage:.2f} V {self.state_name}"


class DroneStatus(Enum):
    ACTIVE = "active"
    """Connected and taking part in swarm operations"""
    FAILED = "failed"
    """Still connected, but excluded after an operation on it failed"""
    LOST = "lost"
    """The link was lost"""


@dataclass(eq=False)
class Drone:
    """One Crazyflie in a swarm.

    Drones compare and hash by identity, so they can be used as dict keys.
    """

    uri: str
    cf: Crazyflie
    pad: Pad | None = None
    label: str | None = None
    """Human-readable name, e.g. from the swarm file"""
    status: DroneStatus = DroneStatus.ACTIVE
    error: BaseException | None = None
    """The exception that made this drone FAILED/LOST, if any"""

    @property
    def active(self) -> bool:
        return self.status is DroneStatus.ACTIVE

    @property
    def hlc(self) -> "HighLevelCommander":
        return self.cf.high_level_commander()

    @property
    def name(self) -> str:
        """Label if set, else pad number if assigned, else URI. Used in messages."""
        if self.label:
            return self.label
        return f"#{self.pad.index}" if self.pad is not None else self.uri

    def __str__(self) -> str:
        return self.name

    async def arm(self, timeout: float = 5.0, poll: float = 0.1) -> None:
        """Arm and wait until the supervisor reports the drone can fly.

        The firmware only accepts an arming request when the supervisor can
        be armed (pre-flight checks passed) and silently drops it otherwise,
        e.g. in the moments right after a disarm or a landing. So the request
        is sent once the drone can be armed, and again if arming falls through
        (e.g. the motor spin-up check fails).

        "Can fly" only counts after our own request: right after a landing
        the supervisor still reports it (state Landed, until it resets), and
        supervisor reads are cached for 100 ms. A drone still armed on the
        ground is disarmed first, so it goes through a fresh arming; a drone
        that is flying is left alone. Raises `TimeoutError` if the drone
        cannot fly after `timeout` seconds.
        """
        supervisor = self.cf.supervisor()
        try:
            async with asyncio.timeout(timeout):
                state = await supervisor.read()
                if state.is_flying:
                    return
                if state.is_armed:
                    await supervisor.send_arming_request(False)
                requested = False
                while True:
                    await asyncio.sleep(poll)
                    state = await supervisor.read()
                    if requested and state.can_fly:
                        return
                    if state.can_be_armed:
                        await supervisor.send_arming_request(True)
                        requested = True
        except TimeoutError:
            raise TimeoutError(f"{self} did not arm within {timeout:.0f} s") from None

    async def read_log(
        self, names: list[str], timeout: float = 5.0, period_ms: int = 50
    ) -> dict:
        """Read one sample of the given log variables"""
        return (await self.read_log_samples(names, 0.0, period_ms, timeout))[0]

    async def read_log_samples(
        self,
        names: list[str],
        duration: float,
        period_ms: int = 50,
        timeout: float = 5.0,
    ) -> list[dict]:
        """Read the given log variables every `period_ms` for `duration`
        seconds, counted from the first sample. Returns at least one sample.
        `timeout` is the longest wait (s) for any single sample."""
        block = await self.cf.log().create_block()
        for name in names:
            await block.add_variable(name)
        stream = await block.start(period_ms)
        try:
            loop = asyncio.get_running_loop()
            samples = [(await asyncio.wait_for(stream.next(), timeout)).data]
            end = loop.time() + duration
            while loop.time() < end:
                samples.append((await asyncio.wait_for(stream.next(), timeout)).data)
            return samples
        finally:
            await stream.stop()

    async def read_battery(self, timeout: float = 5.0) -> Battery:
        """Read the battery level, voltage and power state"""
        data = await self.read_log(["pm.batteryLevel", "pm.vbat", "pm.state"], timeout)
        return Battery(
            level=int(data["pm.batteryLevel"]),
            voltage=float(data["pm.vbat"]),
            state=int(data["pm.state"]),
        )

    async def read_position(
        self,
        duration: float = 1.0,
        period_ms: int = 50,
        max_spread: float = 0.1,
        timeout: float = 5.0,
    ) -> Position:
        """Average position estimate over `duration` seconds, sampled every
        `period_ms`.

        Raises `UnstablePositionError` if a sample is more than `max_spread`
        (m) from the average, e.g. because the estimator has not settled yet
        or the drone lost sight of the base stations.
        """
        names = ["stateEstimate.x", "stateEstimate.y", "stateEstimate.z"]
        samples = [
            tuple(float(s[n]) for n in names)
            for s in await self.read_log_samples(names, duration, period_ms, timeout)
        ]
        x, y, z = (sum(axis) / len(samples) for axis in zip(*samples))
        average = (x, y, z)
        spread = max(math.dist(sample, average) for sample in samples)
        if spread > max_spread:
            raise UnstablePositionError(
                f"Position of {self} is not stable: samples up to {spread * 100:.1f} cm "
                f"from the average (allowed {max_spread * 100:.1f} cm)"
            )
        return average

    async def wait_until_at(
        self,
        target: Position,
        tolerance: float = 0.01,
        smoothing: float = 0.1,
        timeout: float = 15.0,
        period_ms: int = 100,
    ) -> bool:
        """Wait until the drone is settled at `target`, the way the on-board
        landing of the drone show app does it.

        Every `period_ms` the position estimate is blended into a smoothed
        position, `smoothed = (1 - smoothing) * smoothed + smoothing * sample`
        (about 1 s time constant with the defaults). The drone is settled once
        the smoothed position is within `tolerance` (m) of `target` on every
        axis (x, y and z separately).

        Start waiting right after sending the drone towards `target`: the
        smoothing absorbs the approach. Returns True when settled, False if
        that did not happen within `timeout` seconds.
        """
        names = ["stateEstimate.x", "stateEstimate.y", "stateEstimate.z"]
        block = await self.cf.log().create_block()
        for name in names:
            await block.add_variable(name)
        stream = await block.start(period_ms)
        smoothed: tuple[float, ...] | None = None
        try:
            async with asyncio.timeout(timeout):
                while True:
                    data = (await stream.next()).data
                    sample = tuple(float(data[n]) for n in names)
                    smoothed = (
                        sample
                        if smoothed is None
                        else tuple(
                            (1 - smoothing) * s + smoothing * v
                            for s, v in zip(smoothed, sample)
                        )
                    )
                    if all(abs(s - t) < tolerance for s, t in zip(smoothed, target)):
                        return True
        except TimeoutError:
            return False
        finally:
            await stream.stop()


class UnstablePositionError(Exception):
    """The position estimate varied too much while being read"""
