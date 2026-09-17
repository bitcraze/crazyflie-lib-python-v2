// ,---------,       ____  _ __
// |  ,-^-,  |      / __ )(_) /_______________ _____  ___
// | (  O  ) |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
// | / ,--'  |    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
//    +------`   /_____/_/\__/\___/_/   \__,_/ /___/\___/
//
// Copyright (C) 2026 Bitcraze AB
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <http://www.gnu.org/licenses/>.

//! Supervisor subsystem - Crazyflie state, arming, crash recovery, and emergency stop

use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::sync::Arc;

use crate::error::to_pyerr;

/// Supervisor subsystem
///
/// Monitors the Crazyflie state and exposes arming, crash recovery,
/// and emergency stop controls. Obtain via `crazyflie.supervisor()`.
#[gen_stub_pyclass]
#[pyclass]
pub struct Supervisor {
    pub(crate) cf: Arc<crazyflie_lib::Crazyflie>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Supervisor {
    /// Read a consistent snapshot of the supervisor state
    ///
    /// All flags on the returned snapshot are decoded from a single bitfield
    /// read, so they are from the same moment and mutually consistent. Uses
    /// time-based caching to avoid flooding the link.
    ///
    /// The snapshot does not update itself: re-read to get fresh state, for
    /// example on every iteration when polling.
    ///
    /// Example:
    ///     state = await cf.supervisor().read()
    ///     if state.can_be_armed and not state.is_armed:
    ///         await cf.supervisor().send_arming_request(True)
    ///
    ///     # When polling, read inside the loop:
    ///     while not (await cf.supervisor().read()).is_armed:
    ///         await asyncio.sleep(0.5)
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, SupervisorState]"))]
    fn read<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let info = cf.supervisor.read_bitfield().await.map_err(to_pyerr)?;
            Ok(SupervisorState { info })
        })
    }

    /// Send arm/disarm request
    ///
    /// Arms or disarms the Crazyflie's motors. When disarmed, the motors
    /// will not spin even if thrust commands are sent.
    ///
    /// Args:
    ///     do_arm: True to arm, False to disarm
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn send_arming_request<'py>(&self, py: Python<'py>, do_arm: bool) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.supervisor.send_arming_request(do_arm).await.map_err(to_pyerr)?;
            Ok(())
        })
    }

    /// Send crash recovery request
    ///
    /// Requests recovery from a crash state detected by the Crazyflie.
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn send_crash_recovery_request<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.supervisor.send_crash_recovery_request().await.map_err(to_pyerr)?;
            Ok(())
        })
    }

    /// Send emergency stop
    ///
    /// Immediately stops all motors and puts the Crazyflie into a locked state.
    /// The drone will require a reboot before it can fly again.
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn send_emergency_stop<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.supervisor.send_emergency_stop().await.map_err(to_pyerr)?;
            Ok(())
        })
    }

    /// Send emergency stop watchdog
    ///
    /// Activates/resets a watchdog failsafe that will automatically emergency
    /// stop the drone if this message is not sent every 1000 ms. Once
    /// activated, you must keep sending this periodically or the drone will
    /// stop. Use only when you need automatic failsafe behaviour on
    /// communication loss.
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn send_emergency_stop_watchdog<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.supervisor.send_emergency_stop_watchdog().await.map_err(to_pyerr)?;
            Ok(())
        })
    }
}

/// A snapshot of the supervisor state
///
/// Decoded from a single supervisor bitfield read: all flags on one snapshot
/// are from the same moment and mutually consistent. The snapshot does not
/// update itself - call `Supervisor.read()` again for fresh state.
#[gen_stub_pyclass]
#[pyclass(frozen)]
pub struct SupervisorState {
    info: crazyflie_lib::subsystems::supervisor::SupervisorInfo,
}

#[gen_stub_pymethods]
#[pymethods]
impl SupervisorState {
    /// Raw bitfield value
    #[getter]
    fn raw(&self) -> u16 {
        self.info.raw
    }

    /// The Crazyflie can be armed - will accept an arming command
    #[getter]
    fn can_be_armed(&self) -> bool {
        self.info.can_be_armed()
    }

    /// The Crazyflie is armed
    #[getter]
    fn is_armed(&self) -> bool {
        self.info.is_armed()
    }

    /// The Crazyflie is configured to automatically arm
    #[getter]
    fn is_auto_armed(&self) -> bool {
        self.info.is_auto_armed()
    }

    /// The Crazyflie is ready to fly
    #[getter]
    fn can_fly(&self) -> bool {
        self.info.can_fly()
    }

    /// The Crazyflie is flying
    #[getter]
    fn is_flying(&self) -> bool {
        self.info.is_flying()
    }

    /// The Crazyflie is tumbled (upside down)
    #[getter]
    fn is_tumbled(&self) -> bool {
        self.info.is_tumbled()
    }

    /// The Crazyflie is in the locked state and must be restarted
    #[getter]
    fn is_locked(&self) -> bool {
        self.info.is_locked()
    }

    /// The Crazyflie has crashed
    #[getter]
    fn is_crashed(&self) -> bool {
        self.info.is_crashed()
    }

    /// High level commander is actively flying the drone
    #[getter]
    fn hl_control_active(&self) -> bool {
        self.info.hl_control_active()
    }

    /// High level commander trajectory has finished
    #[getter]
    fn hl_traj_finished(&self) -> bool {
        self.info.hl_traj_finished()
    }

    /// High level commander is disabled and not producing setpoints
    #[getter]
    fn hl_control_disabled(&self) -> bool {
        self.info.hl_control_disabled()
    }

    /// Names of all active states in this snapshot
    fn active_states(&self) -> Vec<String> {
        self.info
            .active_states()
            .into_iter()
            .map(|s| s.to_string())
            .collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "SupervisorState(raw=0x{:04x}, active=[{}])",
            self.info.raw,
            self.active_states().join(", ")
        )
    }
}
