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
"""Tests for cflib2.swarm, using fake Crazyflies (no hardware needed)"""

import asyncio
import itertools
from collections.abc import Awaitable
import math

import pytest

from cflib2.swarm import (
    AssignmentError,
    Battery,
    Drone,
    DroneLostError,
    DroneStatus,
    Layout,
    LowBatteryError,
    OnDroneLost,
    OnError,
    Swarm,
    SwarmError,
    UnhealthyDroneError,
    UnstablePositionError,
    grouping,
    land,
    land_on_pads,
)
from cflib2.swarm.docking import (
    DockingSettings,
    check_docked,
    precision_land,
    redock,
)
from cflib2.swarm.leds import BOTTOM, set_color

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeHlc:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def take_off(self, *args: object) -> None:
        self.calls.append(("take_off", *args))

    async def land(self, *args: object) -> None:
        self.calls.append(("land", *args))

    async def go_to(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("go_to", *args, *kwargs.values()))

    async def stop(self, *args: object) -> None:
        self.calls.append(("stop",))

    async def spiral(self, *args: object) -> None:
        self.calls.append(("spiral", *args))

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


class FakeSupervisorState:
    def __init__(self, flying: bool, flags: set[str], armed: bool = False) -> None:
        self.is_flying = flying
        self.is_locked = "locked" in flags
        self.is_crashed = "crashed" in flags
        self.is_tumbled = "tumbled" in flags
        self.is_armed = armed
        self.can_be_armed = not armed and not flags
        self.can_fly = armed


class FakeSupervisor:
    def __init__(self, cf: "FakeCf") -> None:
        self._cf = cf

    async def send_arming_request(self, do_arm: bool) -> None:
        self._cf.arm_requests.append(do_arm)
        self._cf.armed = do_arm

    async def read(self) -> FakeSupervisorState:
        if self._cf.supervisor_error:
            raise self._cf.supervisor_error
        return FakeSupervisorState(
            self._cf.flying, self._cf.supervisor_flags, self._cf.armed
        )


class FakeParam:
    """Parameter writes take `set_delay` seconds, like a radio round trip"""

    def __init__(self, cf: "FakeCf") -> None:
        self._cf = cf

    async def set(self, name: str, value: int | float) -> None:
        await asyncio.sleep(self._cf.set_delay)
        if self._cf.set_error:
            raise self._cf.set_error
        self._cf.params[name] = value


class FakeLogData:
    def __init__(self, data: dict) -> None:
        self.data = data


class FakeStream:
    """Returns `cf.samples` one by one (repeating the last), every period"""

    def __init__(self, cf: "FakeCf", names: list[str], period_ms: int) -> None:
        self._cf, self._names, self._period = cf, names, period_ms / 1000
        self._index = 0

    async def next(self) -> FakeLogData:
        await asyncio.sleep(self._period)
        sample = self._cf.samples[min(self._index, len(self._cf.samples) - 1)]
        self._index += 1
        self._cf.samples_read += 1
        return FakeLogData(dict(zip(self._names, sample)))

    async def stop(self) -> None:
        pass


class FakeBlock:
    def __init__(self, cf: "FakeCf") -> None:
        self._cf, self._names = cf, []

    async def add_variable(self, name: str) -> None:
        self._names.append(name)

    async def start(self, period_ms: int) -> FakeStream:
        return FakeStream(self._cf, self._names, period_ms)


class FakeLog:
    def __init__(self, cf: "FakeCf") -> None:
        self._cf = cf

    async def create_block(self) -> FakeBlock:
        if self._cf.log_error:
            raise self._cf.log_error
        return FakeBlock(self._cf)


class FakeCf:
    def __init__(self) -> None:
        self.params: dict[str, int | float] = {}
        self.samples: list[tuple[float, ...]] = [(0.0, 0.0, 0.0)]
        self.samples_read = 0
        self.log_error: Exception | None = None
        self.set_delay = 0.0
        self.set_error: Exception | None = None
        self.hlc = FakeHlc()
        self.armed = False
        self.arm_requests: list[bool] = []
        self.flying = False
        self.supervisor_flags: set[str] = set()
        self.supervisor_error: Exception | None = None
        self._lost = asyncio.Event()

    def high_level_commander(self) -> FakeHlc:
        return self.hlc

    def param(self) -> "FakeParam":
        return FakeParam(self)

    def log(self) -> FakeLog:
        return FakeLog(self)

    def supervisor(self) -> FakeSupervisor:
        return FakeSupervisor(self)

    async def wait_disconnect(self) -> str:
        await self._lost.wait()
        return "link lost"

    def lose_link(self) -> None:
        self._lost.set()

    async def disconnect(self) -> None:
        pass


def make_swarm(layout: Layout | None = None, **kwargs: object) -> Swarm:
    layout = layout or Layout.grid(3, 3, 1.0)
    drones = [Drone(uri=f"fake://{p.index}", cf=FakeCf(), pad=p) for p in layout]  # type: ignore[arg-type]
    return Swarm.from_drones(drones, **kwargs)  # type: ignore[arg-type]


def pad_ids(groups: list[list[Drone]]) -> list[list[int]]:
    return [[d.pad.index for d in g if d.pad] for g in groups]


def assert_separated(groups: list[list[Drone]], min_distance: float) -> None:
    for g in groups:
        for a, b in itertools.combinations(g, 2):
            assert a.pad and b.pad
            assert a.pad.distance_xy(b.pad.x, b.pad.y) >= min_distance


# CF-01..CF-26 without CF-24, as measured in the flight area
MEASURED_5X5 = [
    (1.26, -2.24), (1.24, -1.89), (0.84, -1.88), (0.81, -1.07), (0.43, -1.06),
    (0.44, -2.28), (1.23, -1.06), (1.23, -1.52), (0.81, -2.31), (0.02, -2.28),
    (0.85, -2.68), (0.42, -1.50), (-0.37, -1.89), (-0.36, -2.69), (0.85, -1.52),
    (0.04, -1.88), (0.42, -2.69), (0.44, -1.88), (-0.38, -1.09), (-0.36, -1.47),
    (0.02, -1.08), (0.03, -2.70), (0.03, -1.48), (1.25, -2.67), (-0.37, -2.30),
]  # fmt: skip


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class TestLayout:
    def test_grid_numbering_matches_column_first_convention(self) -> None:
        layout = Layout.grid(7, 7, 0.8)
        assert len(layout) == 49
        assert (layout[1].x, layout[1].y) == (-2.4, 2.4)
        assert (layout[2].x, layout[2].y) == (-2.4, 1.6)
        assert (layout[25].x, layout[25].y) == (0.0, 0.0)
        assert (layout[49].x, layout[49].y) == (2.4, -2.4)
        assert layout[25].cell == (3, 3)

    def test_assign_matches_nearest_pad(self) -> None:
        layout = Layout.grid(3, 3, 1.0)
        result = layout.assign(
            {"a": (-0.9, 1.1, 0.0), "b": (0.05, -0.02, 0.0)}, tolerance=0.3
        )
        assert result["a"].index == 1
        assert result["b"].index == 5

    def test_assign_reports_all_problems(self) -> None:
        layout = Layout.grid(3, 3, 1.0)
        with pytest.raises(AssignmentError) as exc_info:
            layout.assign(
                {"a": (0.0, 0.0, 0), "b": (0.1, 0.0, 0), "c": (0.5, 0.5, 0)},
                tolerance=0.3,
            )
        assert len(exc_info.value.problems) == 2  # c too far, pad 5 claimed twice


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


class TestGrouping:
    def setup_method(self) -> None:
        self.drones = make_swarm(Layout.grid(7, 7, 0.8)).drones

    def test_rings_7x7(self) -> None:
        groups = grouping.rings(self.drones)
        assert [len(g) for g in groups] == [1, 8, 16, 24]
        assert pad_ids(groups)[0] == [25]
        assert pad_ids(groups)[1] == [17, 18, 19, 24, 26, 31, 32, 33]

    def test_min_separation_has_no_close_pairs(self) -> None:
        groups = grouping.by_min_separation(self.drones, 1.5 * 0.8)
        assert len(groups) == 4
        assert sum(len(g) for g in groups) == 49
        assert_separated(groups, 1.5 * 0.8)

    @pytest.mark.parametrize("min_distance", [0.6, 0.7])
    def test_min_separation_measured_5x5(self, min_distance: float) -> None:
        # Positions measured on a real 5x5 dock grid (~0.4 m spacing), in
        # swarm file order, which is not the grid order. First-fit greedy
        # colouring needed 6 groups here.
        drones = make_swarm(Layout.from_positions(MEASURED_5X5)).drones
        groups = grouping.by_min_separation(drones, min_distance)
        assert len(groups) == 4
        assert_separated(groups, min_distance)

    def test_min_separation_far_beats_greedy(self) -> None:
        # 7x7 grid at 0.4 m with 1.0 m separation: clique bound is 7,
        # first-fit needs 11, DSatur 9, the optimum is 8
        drones = make_swarm(Layout.grid(7, 7, 0.4)).drones
        groups = grouping.by_min_separation(drones, 1.0, time_limit=10.0)
        assert len(groups) == 8
        assert_separated(groups, 1.0)

    def test_min_separation_ignores_input_order(self) -> None:
        drones = make_swarm(Layout.from_positions(MEASURED_5X5)).drones
        expected = pad_ids(grouping.by_min_separation(drones, 0.6))
        assert pad_ids(grouping.by_min_separation(reversed(drones), 0.6)) == expected

    def test_grid_strategies(self) -> None:
        assert len(grouping.checkerboard(self.drones)) == 2
        diagonal_sizes = [1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1]
        assert [len(g) for g in grouping.diagonals(self.drones)] == diagonal_sizes
        assert pad_ids(grouping.stripes(self.drones, "x"))[0] == list(range(1, 8))
        assert pad_ids(grouping.stripes(self.drones, "y"))[0] == list(range(1, 50, 7))

    def test_from_pad_indices_skips_missing(self) -> None:
        groups = grouping.from_pad_indices(self.drones[:3], [[3, 1], [99], [2]])
        assert pad_ids(groups) == [[1, 3], [2]]

    def test_grid_strategy_needs_grid(self) -> None:
        drones = make_swarm(Layout.from_positions([(0, 0), (1, 0)])).drones
        with pytest.raises(ValueError):
            grouping.rings(drones)
        assert len(grouping.by_min_separation(drones, 2.0)) == 2


# ---------------------------------------------------------------------------
# Parallel execution policies
# ---------------------------------------------------------------------------


async def fail_on_pad_2(d: Drone) -> int:
    if d.pad and d.pad.index == 2:
        raise RuntimeError("boom")
    await asyncio.sleep(0.05)
    return d.pad.index if d.pad else 0


class TestParallel:
    @pytest.mark.asyncio
    async def test_continue_excludes_failing_drone(self) -> None:
        swarm = make_swarm()
        results = await swarm.parallel(fail_on_pad_2, on_error=OnError.CONTINUE)
        assert len(results) == 8
        assert swarm.by_pad(2).status is DroneStatus.FAILED
        assert len(swarm.active) == 8

    @pytest.mark.asyncio
    async def test_raise_lets_all_finish(self) -> None:
        swarm = make_swarm()
        finished: list[Drone] = []

        async def fn(d: Drone) -> None:
            await fail_on_pad_2(d)
            finished.append(d)

        with pytest.raises(SwarmError) as exc_info:
            await swarm.parallel(fn, on_error=OnError.RAISE)
        assert list(exc_info.value.errors) == [swarm.by_pad(2)]
        assert len(finished) == 8
        assert len(swarm.active) == 9

    @pytest.mark.asyncio
    async def test_abort_cancels_the_rest(self) -> None:
        swarm = make_swarm()
        finished: list[Drone] = []

        async def fn(d: Drone) -> None:
            await fail_on_pad_2(d)
            finished.append(d)

        with pytest.raises(SwarmError):
            await swarm.parallel(fn, on_error=OnError.ABORT)
        assert finished == []

    @pytest.mark.asyncio
    async def test_timeout_counts_as_failure(self) -> None:
        swarm = make_swarm()
        with pytest.raises(SwarmError) as exc_info:
            await swarm.parallel(
                lambda d: asyncio.sleep(1), drones=swarm.drones[:1], timeout=0.01
            )
        assert isinstance(next(iter(exc_info.value.errors.values())), TimeoutError)

    @pytest.mark.asyncio
    async def test_sequential_abort_skips_remaining(self) -> None:
        swarm = make_swarm()
        seen: list[int] = []

        async def fn(d: Drone) -> None:
            seen.append(d.pad.index if d.pad else 0)
            await fail_on_pad_2(d)

        with pytest.raises(SwarmError):
            await swarm.sequential(fn, on_error=OnError.ABORT)
        assert seen == [1, 2]


class TestParallelNoWait:
    @pytest.mark.asyncio
    async def test_returns_before_drones_finish(self) -> None:
        swarm = make_swarm()
        done: list[Drone] = []

        async def slow(d: Drone) -> int:
            await asyncio.sleep(0.05)
            done.append(d)
            return 1

        futures = await swarm.parallel(slow, wait=False)
        assert len(futures) == 9 and done == []
        assert await asyncio.gather(*futures.values()) == [1] * 9

    @pytest.mark.asyncio
    async def test_commands_are_sent_immediately(self) -> None:
        # fn is called for every drone before parallel returns, so the
        # commands go out even if the caller never awaits anything again
        swarm = make_swarm()
        called: list[Drone] = []

        def send(d: Drone) -> "asyncio.Future[None]":
            called.append(d)
            fut = asyncio.get_running_loop().create_future()
            fut.set_result(None)
            return fut

        await swarm.parallel(send, wait=False)
        assert len(called) == 9

    @pytest.mark.parametrize(
        "policy, status",
        [
            (OnError.CONTINUE, DroneStatus.FAILED),
            (OnError.IGNORE, DroneStatus.ACTIVE),
            (OnError.RAISE, DroneStatus.ACTIVE),
        ],
    )
    @pytest.mark.asyncio
    async def test_failures_handled_in_background(
        self,
        policy: OnError,
        status: DroneStatus,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        swarm = make_swarm()
        await swarm.parallel(fail_on_pad_2, on_error=policy, wait=False)
        await asyncio.sleep(0.1)
        assert swarm.by_pad(2).status is status
        assert "#2 failed" in caplog.text
        assert len([d for d in swarm.drones if d.status is not DroneStatus.ACTIVE]) == (
            status is DroneStatus.FAILED
        )

    @pytest.mark.asyncio
    async def test_ignore_with_wait_keeps_drone(self) -> None:
        swarm = make_swarm()
        results = await swarm.parallel(fail_on_pad_2, on_error=OnError.IGNORE)
        assert len(results) == 8
        assert swarm.by_pad(2).active

    @pytest.mark.asyncio
    async def test_fn_raising_synchronously_counts_as_failure(self) -> None:
        swarm = make_swarm()

        def bad(d: Drone) -> Awaitable[None]:
            raise KeyError("no such param")

        with pytest.raises(SwarmError) as exc_info:
            await swarm.parallel(bad, drones=swarm.drones[:2])
        assert len(exc_info.value.errors) == 2


class TestSkipUnhealthy:
    @pytest.mark.asyncio
    async def test_bad_supervisor_states_are_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        swarm = make_swarm()
        swarm.by_pad(2).cf.supervisor_flags = {"crashed"}  # type: ignore[attr-defined]
        swarm.by_pad(5).cf.supervisor_flags = {"locked", "tumbled"}  # type: ignore[attr-defined]

        skipped = await swarm.skip_unhealthy()

        assert {d.pad.index for d in skipped if d.pad} == {2, 5}
        assert len(swarm.active) == 7
        error = swarm.by_pad(5).error
        assert isinstance(error, UnhealthyDroneError)
        assert error.states == ["locked", "tumbled"]
        assert "#2 is crashed, skipping it" in caplog.text
        assert "#5 is locked and tumbled, skipping it" in caplog.text

    @pytest.mark.asyncio
    async def test_unreadable_supervisor_is_skipped(self) -> None:
        swarm = make_swarm()
        swarm.by_pad(3).cf.supervisor_error = RuntimeError("timeout")  # type: ignore[attr-defined]

        skipped = await swarm.skip_unhealthy()

        assert skipped == [swarm.by_pad(3)]
        assert swarm.by_pad(3).status is DroneStatus.FAILED

    @pytest.mark.asyncio
    async def test_only_checks_given_drones(self) -> None:
        swarm = make_swarm()
        swarm.by_pad(2).cf.supervisor_flags = {"crashed"}  # type: ignore[attr-defined]
        assert await swarm.skip_unhealthy(swarm.drones[2:]) == []
        assert swarm.by_pad(2).active


class TestBattery:
    @pytest.mark.asyncio
    async def test_read_battery(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0)]))
        # pm.batteryLevel, pm.vbat, pm.state
        swarm.drones[0].cf.samples = [(87, 4.05, 1)]  # type: ignore[attr-defined]

        battery = await swarm.drones[0].read_battery()

        assert battery == Battery(level=87, voltage=4.05, state=1)
        assert battery.charging
        assert str(battery) == "87% 4.05 V charging"

    @pytest.mark.asyncio
    async def test_skip_low_battery(self, caplog: pytest.LogCaptureFixture) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0), (1, 0), (2, 0), (3, 0)]))
        full, low, unreadable, exact = swarm.drones
        full.cf.samples = [(95, 4.1, 2)]  # type: ignore[attr-defined]
        low.cf.samples = [(42, 3.7, 0)]  # type: ignore[attr-defined]
        unreadable.cf.log_error = RuntimeError("timeout")  # type: ignore[attr-defined]
        exact.cf.samples = [(80, 3.95, 1)]  # type: ignore[attr-defined]

        skipped = await swarm.skip_low_battery(80)

        assert skipped == [low, unreadable]
        assert swarm.active == [full, exact]
        assert isinstance(low.error, LowBatteryError) and low.error.level == 42
        assert isinstance(unreadable.error, LowBatteryError)
        assert unreadable.error.level is None
        assert "#2: battery at 42%, below 80%, skipping it" in caplog.text
        assert "#3: battery level could not be read, skipping it" in caplog.text

    @pytest.mark.asyncio
    async def test_read_batteries_leaves_out_unreadable(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0), (1, 0)]))
        swarm.drones[0].cf.samples = [(60, 3.9, 0)]  # type: ignore[attr-defined]
        swarm.drones[1].cf.log_error = RuntimeError("timeout")  # type: ignore[attr-defined]

        batteries = await swarm.read_batteries()

        assert list(batteries) == [swarm.drones[0]]
        assert swarm.drones[1].active  # only reading, nothing is skipped


# ---------------------------------------------------------------------------
# Flight safety
# ---------------------------------------------------------------------------


class TestFlight:
    @pytest.mark.asyncio
    async def test_lost_drone_lands_all(self) -> None:
        swarm = make_swarm()
        lost = swarm.by_pad(5)
        body_finished = False

        with pytest.raises(DroneLostError) as exc_info:
            async with swarm.flight(emergency_land_duration=0.0):
                lost.cf.lose_link()  # type: ignore[attr-defined]
                await asyncio.sleep(5)
                body_finished = True

        assert not body_finished
        assert list(exc_info.value.errors) == [lost]
        assert lost.status is DroneStatus.LOST
        for d in swarm.drones:
            if d is not lost:
                assert d.cf.hlc.names() == ["land", "stop"]
                assert not d.cf.armed

    @pytest.mark.asyncio
    async def test_lost_drone_continue(self) -> None:
        swarm = make_swarm()
        async with swarm.flight(
            on_drone_lost=OnDroneLost.CONTINUE, emergency_land_duration=0.0
        ):
            swarm.by_pad(5).cf.lose_link()  # type: ignore[attr-defined]
            await asyncio.sleep(0.01)
            assert len(swarm.active) == 8

    @pytest.mark.asyncio
    async def test_exception_lands_and_propagates(self) -> None:
        swarm = make_swarm()
        with pytest.raises(ZeroDivisionError):
            async with swarm.flight(emergency_land_duration=0.0):
                1 / 0
        assert all(d.cf.hlc.names() == ["land", "stop"] for d in swarm.drones)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_normal_exit_only_lands_flying(self) -> None:
        swarm = make_swarm()
        swarm.by_pad(1).cf.flying = True  # type: ignore[attr-defined]
        async with swarm.flight(emergency_land_duration=0.0):
            pass
        assert swarm.by_pad(1).cf.hlc.names() == ["land", "stop"]  # type: ignore[attr-defined]
        assert swarm.by_pad(2).cf.hlc.names() == []  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_external_cancel_still_cancels(self) -> None:
        swarm = make_swarm()

        async def fly() -> None:
            async with swarm.flight(emergency_land_duration=0.0):
                await asyncio.sleep(5)

        task = asyncio.create_task(fly())
        await asyncio.sleep(0.3)  # past arming, into the block
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all("land" in d.cf.hlc.names() for d in swarm.drones)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_arm_waits_until_it_can_be_armed(self) -> None:
        swarm = make_swarm()
        d = swarm.by_pad(1)
        d.cf.supervisor_flags = {"not ready"}  # type: ignore[attr-defined]

        async def ready_later() -> None:
            await asyncio.sleep(0.25)
            d.cf.supervisor_flags = set()  # type: ignore[attr-defined]

        asyncio.create_task(ready_later())
        await swarm.arm()
        assert all(x.cf.armed for x in swarm.drones)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_arm_rearms_a_drone_still_armed_after_landing(self) -> None:
        swarm = make_swarm()
        d = swarm.by_pad(1)
        d.cf.armed = True  # type: ignore[attr-defined]
        await swarm.arm(drones=[d])
        requests = d.cf.arm_requests  # type: ignore[attr-defined]
        assert requests[0] is False and requests[-1] is True
        assert d.cf.armed  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_arm_times_out_and_flight_disarms(self) -> None:
        swarm = make_swarm()
        swarm.by_pad(1).cf.supervisor_flags = {"not ready"}  # type: ignore[attr-defined]
        with pytest.raises(SwarmError):
            async with swarm.flight():
                pass
        assert not any(d.cf.armed for d in swarm.drones)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Docking
# ---------------------------------------------------------------------------


class TestDocking:
    @pytest.mark.asyncio
    async def test_retries_only_undocked_drones(self) -> None:
        swarm = make_swarm()
        attempts: dict[int, int] = {}

        async def check(d: Drone) -> bool:
            # Pads 1 and 2 need one retry, pad 9 never docks
            idx = d.pad.index if d.pad else 0
            attempts[idx] = attempts.get(idx, 0) + 1
            return idx not in (1, 2, 9) or (idx != 9 and attempts[idx] > 1)

        settings = DockingSettings(
            approach_duration=0.0,
            approach_timeout=0.0,
            land_duration=0.0,
            settle=0.0,
            takeoff_duration=0.0,
            arm_delay=0.0,
            min_separation=1.5,
            check=check,
        )
        failed = await land_on_pads(swarm, settings=settings, retries=2)

        assert [d.pad.index for d in failed if d.pad] == [9]
        landing = ["go_to", "land"]  # approach point, then the final landing
        assert swarm.by_pad(5).cf.hlc.names() == landing  # type: ignore[attr-defined]
        redock = ["take_off", *landing]
        assert swarm.by_pad(1).cf.hlc.names() == [*landing, *redock]  # type: ignore[attr-defined]
        assert swarm.by_pad(9).cf.hlc.names() == [*landing, *redock, *redock]  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_lost_drone_during_retries_does_not_stop_the_others(self) -> None:
        swarm = make_swarm()
        swarm.on_error = OnError.CONTINUE
        lost = swarm.by_pad(1)
        settings = DockingSettings(
            approach_duration=0.0,
            approach_timeout=0.0,
            land_duration=0.0,
            settle=0.0,
            takeoff_duration=0.0,
            arm_delay=0.0,
            min_separation=1.5,
            check=lambda d: _never_docked(),
        )

        async with swarm.flight(
            arm=False,
            on_drone_lost=OnDroneLost.CONTINUE,
            emergency_land_duration=0.0,
        ):
            lost.cf.lose_link()  # type: ignore[attr-defined]
            await asyncio.sleep(0.01)
            still_failed = await redock(swarm, swarm.drones, settings, retries=2)

        assert lost.status is DroneStatus.LOST
        assert lost not in still_failed
        assert len(still_failed) == 8  # the others tried both times
        assert lost.cf.hlc.names() == []  # type: ignore[attr-defined]
        redock_twice = ["take_off", "go_to", "land"] * 2
        assert swarm.by_pad(9).cf.hlc.names() == redock_twice  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_each_drone_lands_once_stable_above_its_pad(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        swarm = make_swarm(Layout.from_positions([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]))
        steady, drifting = swarm.drones
        steady.cf.samples = [(0.0, 0.0, 0.2)]  # type: ignore[attr-defined]
        drifting.cf.samples = [(1.0, 0.1, 0.2)]  # type: ignore[attr-defined]
        settings = DockingSettings(
            approach_duration=0.0,
            approach_timeout=0.3,
            land_duration=0.0,
        )

        await precision_land(swarm, swarm.drones, settings)

        # Both land in the end; only the drifting one is reported
        assert steady.cf.hlc.names() == ["go_to", "land"]  # type: ignore[attr-defined]
        assert drifting.cf.hlc.names() == ["go_to", "land"]  # type: ignore[attr-defined]
        assert "#2 did not settle above its pad" in caplog.text
        assert "#1 did not settle" not in caplog.text

    @pytest.mark.asyncio
    async def test_check_docked_waits_then_reports_undocked(self) -> None:
        swarm = make_swarm()
        checked_at: list[float] = []
        loop = asyncio.get_running_loop()
        start = loop.time()

        async def check(d: Drone) -> bool:
            checked_at.append(loop.time() - start)
            return d.pad is not None and d.pad.index != 4

        settings = DockingSettings(settle=0.05, check=check)
        failed = await check_docked(swarm.drones, settings)

        assert failed == [swarm.by_pad(4)]
        assert min(checked_at) >= 0.05  # charging had time to start
        assert all(d.cf.hlc.names() == [] for d in swarm.drones)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_retry_takes_off_straight_to_approach_height(self) -> None:
        swarm = make_swarm(Layout.from_positions([(1.0, 2.0, 0.05)]))
        settings = DockingSettings(
            approach_duration=0.0,
            approach_timeout=0.0,
            land_duration=0.0,
            settle=0.0,
            takeoff_duration=0.01,
            arm_delay=0.0,
            check=lambda d: _never_docked(),
        )
        await redock(swarm, swarm.drones, settings, retries=1)

        take_off, go_to, land = swarm.drones[0].cf.hlc.calls  # type: ignore[attr-defined]
        # hlc.take_off(height, yaw, duration, group_mask)
        assert take_off[1] == pytest.approx(0.05 + 0.2)
        assert take_off[3] == pytest.approx(0.01)
        # Then re-centre at that same height, as the first landing does
        assert go_to[1:4] == pytest.approx((1.0, 2.0, 0.05 + 0.2))
        assert land[1] == pytest.approx(0.05)

    @pytest.mark.asyncio
    async def test_retries_skip_crashed_drones(self) -> None:
        swarm = make_swarm()
        crashed = swarm.by_pad(9)
        crashed.cf.supervisor_flags = {"crashed"}  # type: ignore[attr-defined]
        settings = DockingSettings(
            approach_duration=0.0,
            approach_timeout=0.0,
            land_duration=0.0,
            settle=0.0,
            takeoff_duration=0.0,
            arm_delay=0.0,
            check=lambda d: _never_docked(),
        )

        still_failed = await redock(swarm, [swarm.by_pad(1), crashed], settings, 2)

        assert crashed.cf.hlc.names() == []  # type: ignore[attr-defined]
        assert isinstance(crashed.error, UnhealthyDroneError)
        assert still_failed == [swarm.by_pad(1)]

    @pytest.mark.asyncio
    async def test_log_error_still_lands_that_drone_and_the_others(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        swarm = make_swarm(Layout.from_positions([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]))
        ok, broken = swarm.drones
        ok.cf.samples = [(0.0, 0.0, 0.2)]  # type: ignore[attr-defined]
        broken.cf.log_error = RuntimeError("Protocol error when deleting block: 2")  # type: ignore[attr-defined]
        settings = DockingSettings(approach_duration=0.0, land_duration=0.0)

        await precision_land(swarm, swarm.drones, settings)

        assert ok.cf.hlc.names() == ["go_to", "land"]  # type: ignore[attr-defined]
        assert broken.cf.hlc.names() == ["go_to", "land"]  # type: ignore[attr-defined]
        assert broken.active
        assert "#2: cannot follow its position" in caplog.text

    @pytest.mark.asyncio
    async def test_precision_land_stops_above_pad_then_lands(self) -> None:
        swarm = make_swarm(Layout.from_positions([(1.0, 2.0, 0.05)]))
        settings = DockingSettings(
            approach_duration=0.0, approach_timeout=0.0, land_duration=0.0
        )
        await precision_land(swarm, swarm.drones, settings)

        go_to, land = swarm.drones[0].cf.hlc.calls  # type: ignore[attr-defined]
        assert go_to[1:4] == pytest.approx((1.0, 2.0, 0.05 + 0.2))
        assert land[1] == pytest.approx(0.05)  # lands on pad height

    @pytest.mark.asyncio
    async def test_precision_land_height_and_duration(self) -> None:
        swarm = make_swarm(Layout.from_positions([(1.0, 2.0, 0.05)]))
        settings = DockingSettings(
            approach_duration=0.0,
            approach_timeout=0.0,
            land_duration=0.01,
            land_height=-0.03,
        )
        await precision_land(swarm, swarm.drones, settings)

        _, land = swarm.drones[0].cf.hlc.calls  # type: ignore[attr-defined]
        # hlc.land(height, yaw, duration, group_mask)
        assert land[1] == pytest.approx(0.05 - 0.03)
        assert land[3] == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# LEDs
# ---------------------------------------------------------------------------


class TestLeds:
    @pytest.mark.asyncio
    async def test_wait_returns_after_confirmation(self) -> None:
        swarm = make_swarm()
        for d in swarm.drones:
            d.cf.set_delay = 0.05  # type: ignore[attr-defined]
        await set_color(swarm, (255, 0, 0))
        assert all(d.cf.params[BOTTOM] == 0x00FF0000 for d in swarm.drones)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_no_wait_returns_immediately_and_still_sends(self) -> None:
        swarm = make_swarm()
        for d in swarm.drones:
            d.cf.set_delay = 0.05  # type: ignore[attr-defined]
        await set_color(swarm, (255, 0, 0), wait=False)
        assert all(BOTTOM not in d.cf.params for d in swarm.drones)  # type: ignore[attr-defined]
        await asyncio.sleep(0.1)
        assert all(d.cf.params[BOTTOM] == 0x00FF0000 for d in swarm.drones)  # type: ignore[attr-defined]

    @pytest.mark.parametrize("wait", [True, False])
    @pytest.mark.asyncio
    async def test_failure_is_logged_not_raised(
        self, wait: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        swarm = make_swarm()
        swarm.by_pad(3).cf.set_error = RuntimeError("no deck")  # type: ignore[attr-defined]
        await set_color(swarm, (0, 0, 255), wait=wait)
        await asyncio.sleep(0.01)
        assert "#3 failed: RuntimeError: no deck" in caplog.text
        assert swarm.by_pad(3).active


# ---------------------------------------------------------------------------
# Reading positions
# ---------------------------------------------------------------------------


class TestReadPosition:
    @pytest.mark.asyncio
    async def test_averages_samples_over_duration(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0)]))
        cf = swarm.drones[0].cf
        cf.samples = [(1.000, 2.000, 0.040), (1.002, 1.998, 0.042)] * 20  # type: ignore[attr-defined]

        x, y, z = await swarm.drones[0].read_position(duration=0.2, period_ms=10)

        # Alternating samples, so the average is the midpoint within 0.1 mm
        assert (x, y, z) == pytest.approx((1.001, 1.999, 0.041), abs=1e-4)
        assert cf.samples_read >= 15  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_unstable_estimate_is_rejected(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0)]))
        swarm.drones[0].cf.samples = [(0.0, 0.0, 0.0), (0.05, 0.0, 0.0)]  # type: ignore[attr-defined]

        with pytest.raises(UnstablePositionError, match="#1"):
            await swarm.drones[0].read_position(
                duration=0.05, period_ms=10, max_spread=0.01
            )

    @pytest.mark.asyncio
    async def test_wait_until_at_uses_smoothed_position(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0)]))
        cf = swarm.drones[0].cf
        at, off = (1.0, 2.0, 0.2), (1.0, 2.1, 0.2)
        cf.samples = [off] + [at] * 40  # type: ignore[attr-defined]

        assert await swarm.drones[0].wait_until_at(at, period_ms=1)
        # Smoothed error after k samples on target: 0.1 * 0.9^k, which drops
        # below 1 cm after k = 22, so 23 samples in total
        assert cf.samples_read == 23  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_wait_until_at_checks_every_axis(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0)]))
        # Exactly above, but 1.5 cm too high
        swarm.drones[0].cf.samples = [(1.0, 2.0, 0.215)]  # type: ignore[attr-defined]

        settled = await swarm.drones[0].wait_until_at(
            (1.0, 2.0, 0.2), timeout=0.1, period_ms=1
        )
        assert not settled

    @pytest.mark.asyncio
    async def test_read_log_returns_one_sample(self) -> None:
        swarm = make_swarm(Layout.from_positions([(0, 0)]))
        cf = swarm.drones[0].cf
        cf.samples = [(2.0,)]  # type: ignore[attr-defined]

        assert await swarm.drones[0].read_log(["pm.state"]) == {"pm.state": 2.0}
        assert cf.samples_read == 1  # type: ignore[attr-defined]


async def _never_docked() -> bool:
    return False
