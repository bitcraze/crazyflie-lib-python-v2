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
"""Connection management, parallel execution and flight safety for a swarm"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, TypeVar, overload

from cflib2 import Crazyflie, LinkContext
from cflib2.swarm.config import load_swarm_config
from cflib2.swarm.drone import Battery, Drone, DroneStatus
from cflib2.swarm.layout import Layout, Pad, Position
from cflib2.toc_cache import FileTocCache, InMemoryTocCache, NoTocCache

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OnError(Enum):
    """What `Swarm.parallel` does when the operation fails on some drones"""

    CONTINUE = "continue"
    """Mark the failing drones FAILED (excluded from later operations) and
    return the results of the others. Like `parallel` in the old cflib."""
    RAISE = "raise"
    """Let every drone finish, then raise `SwarmError`. Like `parallel_safe`
    in the old cflib."""
    ABORT = "abort"
    """Cancel the operation on all other drones at the first failure and
    raise `SwarmError`."""
    IGNORE = "ignore"
    """Log a warning and keep the drone active. For operations that are not
    worth stopping for, such as LED effects."""


class OnDroneLost(Enum):
    """What a `Swarm.flight()` block does when the link to a drone is lost"""

    CONTINUE = "continue"
    """Mark the drone LOST and let the rest of the swarm carry on"""
    LAND_ALL = "land_all"
    """Interrupt the flight block, land every drone and raise `DroneLostError`"""


class SwarmError(Exception):
    """An operation failed on one or more drones"""

    def __init__(
        self,
        message: str,
        errors: Mapping[Any, BaseException],
    ) -> None:
        self.errors: dict[Drone | str, BaseException] = dict(errors)  # by drone or URI
        details = "\n".join(
            f"  {d}: {type(e).__name__}: {e}" for d, e in self.errors.items()
        )
        super().__init__(f"{message}:\n{details}")


class DroneLostError(SwarmError):
    """The link to one or more drones was lost during a flight block"""


class UnhealthyDroneError(Exception):
    """The supervisor reports a state in which the drone will not fly"""

    def __init__(self, states: list[str]) -> None:
        self.states = states
        super().__init__(f"supervisor reports: {', '.join(states)}")


class LowBatteryError(Exception):
    """The battery is too low to fly, or could not be read"""

    def __init__(self, level: int | None, min_level: int) -> None:
        self.level = level
        self.min_level = min_level
        if level is None:
            super().__init__("battery level could not be read")
        else:
            super().__init__(f"battery at {level}%, below {min_level}%")


# Supervisor states in which a drone accepts commands but will not fly
UNHEALTHY_STATES = ("is_locked", "is_crashed", "is_tumbled")


class Swarm:
    """A group of Crazyflies sharing one `LinkContext`.

    Use as an async context manager to connect and disconnect::

        async with Swarm.from_file("swarm.yaml") as swarm:
            await swarm.set_home_pads()
            async with swarm.flight():
                groups = by_min_separation(swarm.active, 1.0)
                await takeoff(swarm, 1.0, groups=groups)
                ...
    """

    def __init__(
        self,
        uris: Iterable[str],
        *,
        names: Mapping[str, str] | None = None,
        link_context: LinkContext | None = None,
        toc_cache: NoTocCache | InMemoryTocCache | FileTocCache | None = None,
        on_error: OnError = OnError.RAISE,
        require_all: bool = True,
        connect_timeout: float = 10.0,
    ) -> None:
        """
        Args:
            uris: The URIs to connect to
            names: Optional human-readable name per URI, used in messages
            link_context: Shared link context, a new one is created if omitted
            toc_cache: TOC cache shared by all drones. Defaults to an
                in-memory cache, so identical firmware only fetches the TOC once.
            on_error: Default error policy for `parallel` and `sequential`
            require_all: If True, `connect` fails if any drone fails to
                connect. If False, the swarm continues with the ones that did.
            connect_timeout: Per-drone connection timeout (s)
        """
        self._uris = list(uris)
        self._names = dict(names or {})
        self._link_context = link_context or LinkContext()
        self._toc_cache = toc_cache if toc_cache is not None else InMemoryTocCache()
        self.on_error = on_error
        self._require_all = require_all
        self._connect_timeout = connect_timeout
        self.drones: list[Drone] = []
        self.connect_errors: dict[str, BaseException] = {}
        # Commands started with wait=False, kept until done so they are not
        # garbage collected early
        self._in_flight: set[asyncio.Future] = set()

    @classmethod
    def from_drones(
        cls, drones: Iterable[Drone], *, on_error: OnError = OnError.RAISE
    ) -> "Swarm":
        """A swarm of already connected drones"""
        swarm = cls([], on_error=on_error)
        swarm.drones = list(drones)
        swarm._uris = [d.uri for d in swarm.drones]
        return swarm

    @classmethod
    def from_file(cls, path: str | Path, **kwargs: Any) -> "Swarm":  # noqa: ANN401
        """A swarm described by a YAML swarm file, see `cflib2.swarm.config`.

        Keyword arguments are passed on to `Swarm()`.
        """
        config = load_swarm_config(path)
        return cls(config.uris, names=config.names, **kwargs)

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    async def connect(self) -> None:
        async def connect_one(uri: str) -> Crazyflie:
            async with asyncio.timeout(self._connect_timeout):
                return await Crazyflie.connect_from_uri(
                    self._link_context, uri, self._toc_cache
                )

        results = await asyncio.gather(
            *(connect_one(uri) for uri in self._uris), return_exceptions=True
        )
        for uri, result in zip(self._uris, results):
            if isinstance(result, BaseException):
                self.connect_errors[uri] = result
            else:
                self.drones.append(
                    Drone(uri=uri, cf=result, label=self._names.get(uri))
                )

        if self.connect_errors:
            if self._require_all:
                await self.disconnect()
                raise SwarmError("Failed to connect", self.connect_errors)
            for uri, error in self.connect_errors.items():
                logger.warning(
                    "Failed to connect to %s, continuing without it: %s", uri, error
                )

    async def disconnect(self) -> None:
        await asyncio.gather(
            *(d.cf.disconnect() for d in self.drones), return_exceptions=True
        )

    async def __aenter__(self) -> "Swarm":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------ #
    # Membership
    # ------------------------------------------------------------------ #

    @property
    def active(self) -> list[Drone]:
        """Drones that take part in swarm operations"""
        return [d for d in self.drones if d.active]

    @property
    def connected(self) -> list[Drone]:
        """Drones with a working link, including FAILED ones"""
        return [d for d in self.drones if d.status is not DroneStatus.LOST]

    def by_pad(self, index: int) -> Drone:
        for d in self.drones:
            if d.pad is not None and d.pad.index == index:
                return d
        raise KeyError(f"No drone on pad {index}")

    def __iter__(self) -> Iterator[Drone]:
        return iter(self.active)

    def __len__(self) -> int:
        return len(self.active)

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    @overload
    async def parallel(
        self,
        fn: Callable[[Drone], Awaitable[T]],
        *,
        drones: Iterable[Drone] | None = None,
        timeout: float | None = None,
        on_error: OnError | None = None,
        wait: Literal[True] = True,
    ) -> dict[Drone, T]: ...

    @overload
    async def parallel(
        self,
        fn: Callable[[Drone], Awaitable[T]],
        *,
        drones: Iterable[Drone] | None = None,
        timeout: float | None = None,
        on_error: OnError | None = None,
        wait: Literal[False],
    ) -> "dict[Drone, asyncio.Future[T]]": ...

    async def parallel(
        self,
        fn: Callable[[Drone], Awaitable[T]],
        *,
        drones: Iterable[Drone] | None = None,
        timeout: float | None = None,
        on_error: OnError | None = None,
        wait: bool = True,
    ) -> "dict[Drone, T] | dict[Drone, asyncio.Future[T]]":
        """Run `fn(drone)` concurrently on every active drone.

        `fn` is called for every drone right away, so all commands are sent
        at practically the same time. `wait` decides what happens next:

        - `wait=True`: wait for every drone to finish (e.g. to confirm a
          parameter write), then apply the `OnError` policy.
        - `wait=False`: return immediately, without waiting for any drone.
          Use it when commands must not be held back by radio round trips,
          e.g. LED effects or successive commands to different groups.
          Failures are handled in the background as they arrive: FAILED
          (`CONTINUE`) or logged (`IGNORE`). Nothing can be raised to the
          caller any more, so with `RAISE` and `ABORT` they are logged as
          errors.

        Args:
            fn: Async function, or a lambda returning an awaitable, called
                once per drone, e.g. `lambda d: d.hlc.take_off(1.0, None, 2.0, None)`
            drones: Subset to run on (inactive drones are skipped). Defaults
                to all active drones.
            timeout: Per-drone timeout (s). A timeout counts as a failure.
            on_error: Overrides the swarm's default `OnError` policy
            wait: Wait for the drones to finish, see above

        Returns:
            With `wait=True`, the result per drone for the drones that
            succeeded. With `wait=False`, a future per drone, which can be
            awaited later if needed.
        """
        policy = on_error or self.on_error
        targets = [d for d in (self.active if drones is None else drones) if d.active]
        tasks = {d: self._start(fn, d, timeout) for d in targets}

        if not wait:
            for d, task in tasks.items():
                self._in_flight.add(task)
                task.add_done_callback(self._in_flight.discard)
                task.add_done_callback(
                    lambda t, d=d: self._handle_background_result(d, t, policy)
                )
            return tasks

        try:
            if tasks:
                when = (
                    asyncio.FIRST_EXCEPTION
                    if policy is OnError.ABORT
                    else asyncio.ALL_COMPLETED
                )
                await asyncio.wait(tasks.values(), return_when=when)
        finally:
            # Covers ABORT and the caller being cancelled while waiting
            pending = [t for t in tasks.values() if not t.done()]
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        return self._collect(tasks, policy)

    @staticmethod
    def _start(
        fn: Callable[[Drone], Awaitable[T]], d: Drone, timeout: float | None
    ) -> "asyncio.Future[T]":
        """Call `fn(d)` now, so the command is sent immediately, and track it"""
        try:
            awaitable = fn(d)
        except Exception as e:
            failed: asyncio.Future[T] = asyncio.get_running_loop().create_future()
            failed.set_exception(e)
            return failed

        async def run() -> T:
            async with asyncio.timeout(timeout):
                return await awaitable

        return asyncio.ensure_future(run())

    def _handle_background_result(
        self, d: Drone, task: "asyncio.Future[object]", policy: OnError
    ) -> None:
        if task.cancelled() or (exc := task.exception()) is None:
            return
        if policy in (OnError.CONTINUE, OnError.IGNORE):
            self._handle_failure(d, exc, policy)
        else:
            logger.error(
                "%s failed (wait=False, so not raised): %s: %s",
                d,
                type(exc).__name__,
                exc,
            )

    def _handle_failure(self, d: Drone, exc: BaseException, policy: OnError) -> None:
        """Apply a CONTINUE or IGNORE policy to one failed drone"""
        if policy is OnError.IGNORE:
            logger.warning("%s failed: %s: %s", d, type(exc).__name__, exc)
            return
        d.status, d.error = DroneStatus.FAILED, exc
        logger.warning(
            "%s failed and is excluded from the swarm: %s: %s",
            d,
            type(exc).__name__,
            exc,
        )

    async def sequential(
        self,
        fn: Callable[[Drone], Awaitable[T]],
        *,
        drones: Iterable[Drone] | None = None,
        timeout: float | None = None,
        on_error: OnError | None = None,
    ) -> dict[Drone, T]:
        """Like `parallel`, but one drone at a time in order.

        With `OnError.ABORT` the remaining drones are skipped at the first failure.
        """
        policy = on_error or self.on_error
        targets = [d for d in (self.active if drones is None else drones) if d.active]
        tasks: dict[Drone, asyncio.Future[T]] = {}
        for d in targets:
            task = self._start(fn, d, timeout)
            tasks[d] = task
            await asyncio.wait([task])
            if policy is OnError.ABORT and task.exception() is not None:
                break
        return self._collect(tasks, policy)

    def _collect(
        self, tasks: Mapping[Drone, "asyncio.Future[T]"], policy: OnError
    ) -> dict[Drone, T]:
        results: dict[Drone, T] = {}
        errors: dict[Drone | str, BaseException] = {}
        for d, t in tasks.items():
            if t.cancelled():
                continue
            if (exc := t.exception()) is not None:
                errors[d] = exc
            else:
                results[d] = t.result()

        if errors:
            if policy in (OnError.RAISE, OnError.ABORT):
                raise SwarmError("Operation failed", errors)
            for d, exc in errors.items():
                assert isinstance(d, Drone)
                self._handle_failure(d, exc, policy)
        return results

    # ------------------------------------------------------------------ #
    # Common operations
    # ------------------------------------------------------------------ #

    async def read_positions(
        self, drones: Iterable[Drone] | None = None
    ) -> dict[Drone, Position]:
        """Average position of every drone over 1 s, all in parallel. Fails
        if any drone cannot be read or its estimate is not stable (see
        `Drone.read_position`)."""
        return await self.parallel(
            lambda d: d.read_position(), drones=drones, on_error=OnError.RAISE
        )

    async def assign_pads(self, layout: Layout, tolerance: float) -> None:
        """Match every active drone to a pad by its estimated position.

        Afterwards `drones` is sorted by pad index. Raises `AssignmentError`
        listing every unmatched drone and contested pad.
        """
        assignment = layout.assign(await self.read_positions(), tolerance)
        for d, pad in assignment.items():
            d.pad = pad
        self.drones.sort(key=lambda d: (d.pad is None, d.pad.index if d.pad else 0))

    async def set_home_pads(self) -> None:
        """Use where every active drone stands now as its pad.

        Pads are numbered in the order of `drones` (the order of the swarm
        file). Use this when the pads are not described anywhere else.
        """
        positions = await self.read_positions()
        for index, d in enumerate(self.drones, start=1):
            if d in positions:
                d.pad = Pad(index, *positions[d])

    async def skip_unhealthy(
        self,
        drones: Iterable[Drone] | None = None,
        *,
        states: Iterable[str] = UNHEALTHY_STATES,
        timeout: float = 2.0,
    ) -> list[Drone]:
        """Check the supervisor of every active drone (default: all) and take
        the unhealthy ones out of the swarm.

        A drone in one of `states` (`SupervisorState` flags, default: locked,
        crashed or tumbled) still accepts commands but will not fly. It is
        marked FAILED with an `UnhealthyDroneError`, so later operations skip
        it, and a warning is logged. A drone whose supervisor cannot be read
        within `timeout` seconds is skipped the same way.

        Returns the drones that were skipped.
        """
        states = tuple(states)
        targets = [d for d in (self.active if drones is None else drones) if d.active]
        readings = await self.parallel(
            lambda d: d.cf.supervisor().read(),
            drones=targets,
            timeout=timeout,
            on_error=OnError.CONTINUE,
        )
        skipped = [d for d in targets if d not in readings]
        for d, reading in readings.items():
            bad = [s.removeprefix("is_") for s in states if getattr(reading, s)]
            if bad:
                d.status, d.error = DroneStatus.FAILED, UnhealthyDroneError(bad)
                logger.warning("%s is %s, skipping it", d, " and ".join(bad))
                skipped.append(d)
        return skipped

    async def read_batteries(
        self, drones: Iterable[Drone] | None = None, *, timeout: float = 5.0
    ) -> dict[Drone, Battery]:
        """Battery level, voltage and power state of every active drone
        (default: all), read in parallel. Drones whose battery cannot be read
        are left out of the result, with a warning, and stay active."""
        return await self.parallel(
            lambda d: d.read_battery(timeout), drones=drones, on_error=OnError.IGNORE
        )

    async def skip_low_battery(
        self,
        min_level: int,
        drones: Iterable[Drone] | None = None,
        *,
        timeout: float = 5.0,
    ) -> list[Drone]:
        """Take the drones with a battery level below `min_level` (%) out of
        the swarm.

        They are marked FAILED with a `LowBatteryError`, so later operations
        skip them, and a warning is logged. Drones whose battery cannot be read
        are taken out the same way. Returns the drones that were taken out.
        """
        targets = [d for d in (self.active if drones is None else drones) if d.active]
        batteries = await self.read_batteries(targets, timeout=timeout)
        skipped = []
        for d in targets:
            battery = batteries.get(d)
            if battery is not None and battery.level >= min_level:
                continue
            error = LowBatteryError(battery.level if battery else None, min_level)
            d.status, d.error = DroneStatus.FAILED, error
            logger.warning("%s: %s, skipping it", d, error)
            skipped.append(d)
        return skipped

    async def arm(
        self, drones: Iterable[Drone] | None = None, *, timeout: float = 5.0
    ) -> None:
        """Arm the drones (default: all active) and wait until they can fly,
        see `Drone.arm`"""
        await self.parallel(lambda d: d.arm(timeout), drones=drones)

    async def disarm(self, drones: Iterable[Drone] | None = None) -> None:
        """Disarm, best effort, including FAILED drones"""
        targets = self.connected if drones is None else drones
        await asyncio.gather(
            *(d.cf.supervisor().send_arming_request(False) for d in targets),
            return_exceptions=True,
        )

    async def land_now(
        self, duration: float = 4.0, *, only_flying: bool = False
    ) -> None:
        """Emergency landing: every connected drone (FAILED included) lands
        straight down from where it is, then motors are stopped.

        Errors are logged, never raised. With `only_flying`, drones whose
        supervisor reports them as not flying are left alone.
        """
        targets = self.connected
        if only_flying:
            targets = [d for d in targets if await _maybe_flying(d)]
        if not targets:
            return

        results = await asyncio.gather(
            *(
                d.hlc.land(d.pad.z if d.pad else 0.0, None, duration, None)
                for d in targets
            ),
            return_exceptions=True,
        )
        for d, r in zip(targets, results):
            if isinstance(r, BaseException):
                logger.error("Emergency land failed on %s: %s", d, r)
        await asyncio.sleep(duration + 0.5)
        await asyncio.gather(
            *(d.hlc.stop(None) for d in targets), return_exceptions=True
        )

    def flight(
        self,
        *,
        on_drone_lost: OnDroneLost = OnDroneLost.LAND_ALL,
        arm: bool = True,
        emergency_land_duration: float = 4.0,
    ) -> "Flight":
        """A safety scope for flying. See `Flight`."""
        return Flight(self, on_drone_lost, arm, emergency_land_duration)


async def _maybe_flying(d: Drone) -> bool:
    try:
        async with asyncio.timeout(1.0):
            return (await d.cf.supervisor().read()).is_flying
    except Exception:
        return True  # Unknown: assume flying and land it


class Flight:
    """Async context manager that guarantees the swarm ends up on the ground.

    - On entry: arms the drones and starts watching every link.
    - If the block raises (including Ctrl+C / cancellation), every connected
      drone does an emergency landing before the exception propagates.
    - If a link is lost and the policy is `OnDroneLost.LAND_ALL`, the block
      is interrupted, the swarm lands and `DroneLostError` is raised.
    - On normal exit any drone still flying is landed as a safety net.
    - Drones are always disarmed on exit.

    Note that nothing can be done from here for a drone whose link is lost:
    it keeps executing its last high-level command.
    """

    def __init__(
        self,
        swarm: Swarm,
        on_drone_lost: OnDroneLost,
        arm: bool,
        emergency_land_duration: float,
    ) -> None:
        self._swarm = swarm
        self._on_drone_lost = on_drone_lost
        self._arm = arm
        self._land_duration = emergency_land_duration
        self._task: asyncio.Task | None = None
        self._watchers: list[asyncio.Task] = []
        self._lost: list[Drone] = []
        self._interrupted = False

    async def __aenter__(self) -> Swarm:
        self._task = asyncio.current_task()
        if self._arm:
            try:
                await self._swarm.arm()
            except BaseException:
                # __aexit__ does not run when entering fails: disarm here
                await self._swarm.disarm()
                raise
        self._watchers = [
            asyncio.create_task(self._watch(d)) for d in self._swarm.connected
        ]
        return self._swarm

    async def _watch(self, d: Drone) -> None:
        reason = await d.cf.wait_disconnect()
        d.status, d.error = DroneStatus.LOST, ConnectionError(reason)
        self._lost.append(d)
        logger.error("Lost link to %s: %s", d, reason)
        if self._on_drone_lost is OnDroneLost.LAND_ALL and not self._interrupted:
            self._interrupted = True
            assert self._task is not None
            self._task.cancel()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        for w in self._watchers:
            w.cancel()
        await asyncio.gather(*self._watchers, return_exceptions=True)

        # Swallow our own cancellation (same pattern as asyncio.timeout), but
        # keep propagating if someone else cancelled the task as well
        raise_lost = False
        if self._interrupted and exc_type is asyncio.CancelledError:
            assert self._task is not None
            raise_lost = self._task.uncancel() == 0

        try:
            if exc is not None:
                logger.error(
                    "Flight aborted (%s), landing all drones",
                    exc_type.__name__ if exc_type else "",
                )
                await self._swarm.land_now(self._land_duration)
            else:
                await self._swarm.land_now(self._land_duration, only_flying=True)
        finally:
            await self._swarm.disarm()

        if raise_lost:
            raise DroneLostError(
                "Lost link during flight", {d: d.error for d in self._lost if d.error}
            ) from None
        return False
