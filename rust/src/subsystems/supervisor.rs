// ,---------,       ____  _ __
// |  ,-^-,  |      / __ )(_) /_______________ _____  ___
// | (  O  ) |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
// | / ,--'  |    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
//    +------`   /_____/_/\__/\___/_/   \__,_/ /___/\___/
//
// Copyright (C) 2025 Bitcraze AB
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

//! Supervisor subsystem - system state, arming, crash recovery, and emergency stop

use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::sync::Arc;

use crate::error::to_pyerr;

/// Supervisor subsystem
///
/// Monitors the Crazyflie's system state and exposes arming, crash recovery,
/// and emergency stop controls. Obtain via `crazyflie.supervisor()`.
#[gen_stub_pyclass]
#[pyclass]
pub struct Supervisor {
    pub(crate) cf: Arc<crazyflie_lib::Crazyflie>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Supervisor {
    /// Read the raw supervisor state bitfield
    ///
    /// Returns the raw bitfield as an integer. Uses time-based caching (100 ms)
    /// to avoid flooding the link.
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.int]"))]
    fn read_bitfield<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let info = cf.supervisor.read_bitfield().await.map_err(to_pyerr)?;
            Ok(info.raw)
        })
    }

    /// Names of all currently active states
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.list[builtins.str]]"))]
    fn active_states<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let states = cf.supervisor.read_bitfield().await.map_err(to_pyerr)?
                .active_states()
                .into_iter()
                .map(|s| s.to_string())
                .collect::<Vec<_>>();
            Ok(states)
        })
    }

    /// System can be armed - will accept an arming command
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn can_be_armed<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.can_be_armed())
        })
    }

    /// System is armed
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn is_armed<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.is_armed())
        })
    }

    /// System is configured to automatically arm
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn is_auto_armed<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.is_auto_armed())
        })
    }

    /// The Crazyflie is ready to fly
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn can_fly<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.can_fly())
        })
    }

    /// The Crazyflie is flying
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn is_flying<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.is_flying())
        })
    }

    /// The Crazyflie is tumbled (upside down)
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn is_tumbled<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.is_tumbled())
        })
    }

    /// The Crazyflie is in the locked state and must be restarted
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn is_locked<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.is_locked())
        })
    }

    /// The Crazyflie has crashed
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn is_crashed<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.is_crashed())
        })
    }

    /// High level commander is actively flying the drone
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn hl_control_active<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.hl_control_active())
        })
    }

    /// High level commander trajectory has finished
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn hl_traj_finished<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.hl_traj_finished())
        })
    }

    /// High level commander is disabled and not producing setpoints
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.bool]"))]
    fn hl_control_disabled<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            Ok(cf.supervisor.read_bitfield().await.map_err(to_pyerr)?.hl_control_disabled())
        })
    }

    /// Send system arm/disarm request
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
    /// Requests recovery from a crashed state. The firmware may allow
    /// recovery without a full reboot depending on the crash type.
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
