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

//! Parameter subsystem - read and write configuration parameters

use pyo3::prelude::*;
use pyo3_stub_gen_derive::*;
use std::sync::Arc;

use crate::error::to_pyerr;
use crate::value::value_to_python;

/// State of a persistent parameter returned by `Param.persistent_get_state()`
#[gen_stub_pyclass]
#[pyclass]
pub struct PersistentParamState {
    is_stored: bool,
    default_value: Py<PyAny>,
    stored_value: Py<PyAny>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PersistentParamState {
    /// True if a value is currently stored in persistent storage
    #[getter]
    #[gen_stub(override_return_type(type_repr = "bool"))]
    fn is_stored(&self) -> bool {
        self.is_stored
    }

    /// The firmware's default value for this parameter
    #[getter]
    #[gen_stub(override_return_type(type_repr = "int | float"))]
    fn default_value(&self, py: Python<'_>) -> Py<PyAny> {
        self.default_value.clone_ref(py)
    }

    /// The value stored in persistent storage, or None if not stored
    #[getter]
    #[gen_stub(override_return_type(type_repr = "int | float | None"))]
    fn stored_value(&self, py: Python<'_>) -> Py<PyAny> {
        self.stored_value.clone_ref(py)
    }
}

/// Access to the Crazyflie Param Subsystem
///
/// This struct provides methods to interact with the parameter subsystem.
///
/// The Crazyflie exposes a param subsystem that allows to easily declare parameter
/// variables in the Crazyflie and to discover, read and write them from the ground.
///
/// Variables are defined in a table of content that is downloaded upon connection.
/// Each param variable have a unique name composed from a group and a variable name.
/// Functions that accesses variables, take a `name` parameter that accepts a string
/// in the format "group.variable"
///
/// During connection, the full param table of content is downloaded form the
/// Crazyflie as well as the values of all the variable. If a variable value
/// is modified by the Crazyflie during runtime, it sends a packet with the new
/// value which updates the local value cache.
#[gen_stub_pyclass]
#[pyclass]
pub struct Param {
    pub(crate) cf: Arc<crazyflie_lib::Crazyflie>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Param {
    /// Get the names of all the parameters
    ///
    /// The names contain group and name of the parameter variable formatted as
    /// "group.name".
    fn names(&self) -> Vec<String> {
        self.cf.param.names()
    }

    /// Get the type of a parameter
    ///
    /// Returns the type string of the parameter (e.g., "u8", "f32", "i16").
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    ///
    /// # Returns
    /// String representing the parameter type
    fn get_type(&self, name: &str) -> PyResult<String> {
        let param_type = self.cf.param.get_type(name).map_err(to_pyerr)?;
        Ok(format!("{:?}", param_type))
    }

    /// Get param value
    ///
    /// Get value of a parameter. This function takes the value from a local
    /// cache and so is quick.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    ///
    /// # Returns
    /// Parameter value (int or float depending on parameter type)
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, int | float]"))]
    fn get<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let value = cf.param.get(&name).await.map_err(to_pyerr)?;
            Python::attach(|py| value_to_python(py, value))
        })
    }

    /// Set a parameter value
    ///
    /// Sets a parameter to the given value. The value is automatically converted
    /// to match the parameter's type. Returns an error if the parameter does not
    /// exist or if the value cannot be converted to the parameter's type without
    /// loss of information.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    /// * `value` - New parameter value (int or float)
    ///
    /// # Errors
    /// Returns an error if:
    /// - The parameter does not exist
    /// - The value is out of range for the parameter type
    /// - The value cannot be represented accurately (e.g., fractional value for integer param)
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn set<'py>(&self, py: Python<'py>, name: String, #[gen_stub(override_type(type_repr = "int | float"))] value: Py<PyAny>) -> PyResult<Bound<'py, PyAny>> {
        // Get the parameter type (sync, no GIL needed for this)
        let param_type = self.cf.param.get_type(&name).map_err(to_pyerr)?;

        // Convert Python value to appropriate Rust Value based on param type
        // This must be done while we have the GIL
        use crazyflie_lib::{Value, ValueType};
        let rust_value = match param_type {
            ValueType::U8 => {
                let v = value.extract::<u8>(py)?;
                Value::U8(v)
            }
            ValueType::U16 => {
                let v = value.extract::<u16>(py)?;
                Value::U16(v)
            }
            ValueType::U32 => {
                let v = value.extract::<u32>(py)?;
                Value::U32(v)
            }
            ValueType::U64 => {
                let v = value.extract::<u64>(py)?;
                Value::U64(v)
            }
            ValueType::I8 => {
                let v = value.extract::<i8>(py)?;
                Value::I8(v)
            }
            ValueType::I16 => {
                let v = value.extract::<i16>(py)?;
                Value::I16(v)
            }
            ValueType::I32 => {
                let v = value.extract::<i32>(py)?;
                Value::I32(v)
            }
            ValueType::I64 => {
                let v = value.extract::<i64>(py)?;
                Value::I64(v)
            }
            ValueType::F16 => {
                let v = value.extract::<f32>(py)?;
                Value::F32(v) // F16 converts to F32
            }
            ValueType::F32 => {
                let v = value.extract::<f32>(py)?;
                Value::F32(v)
            }
            ValueType::F64 => {
                let v = value.extract::<f64>(py)?;
                Value::F64(v)
            }
        };

        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.param.set(&name, rust_value).await.map_err(to_pyerr)?;
            Ok(())
        })
    }

    /// Check if a parameter is writable
    ///
    /// Returns True if the parameter can be set, False if it is read-only.
    /// Raises an error if the parameter does not exist.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    fn is_writable(&self, name: &str) -> PyResult<bool> {
        self.cf.param.is_writable(name).map_err(to_pyerr)
    }

    /// Check if a parameter supports persistent storage
    ///
    /// Returns False for parameters that do not support persistence.
    /// Raises an error if the parameter does not exist.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, bool]"))]
    fn is_persistent<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.param.is_persistent(&name).await.map_err(to_pyerr)
        })
    }

    /// Get the firmware's default value for a parameter
    ///
    /// Raises an error if the parameter is read-only or does not exist.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    ///
    /// # Returns
    /// The default value (int or float depending on parameter type)
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, int | float]"))]
    fn get_default_value<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let value = cf.param.get_default_value(&name).await.map_err(to_pyerr)?;
            Python::attach(|py| value_to_python(py, value))
        })
    }

    /// Get the persistent storage state of a parameter
    ///
    /// Returns a PersistentParamState with:
    /// - `is_stored`: True if a value is currently in persistent storage
    /// - `default_value`: The firmware's default value
    /// - `stored_value`: The stored value, or None if not stored
    ///
    /// Raises an error if the parameter does not exist or is not persistent.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, PersistentParamState]"))]
    fn persistent_get_state<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let state = cf.param.persistent_get_state(&name).await.map_err(to_pyerr)?;
            Python::attach(|py| {
                let stored = match state.stored_value {
                    Some(v) => value_to_python(py, v)?,
                    None => py.None(),
                };
                Ok(PersistentParamState {
                    is_stored: state.is_stored,
                    default_value: value_to_python(py, state.default_value)?,
                    stored_value: stored,
                })
            })
        })
    }

    /// Store the current parameter value to persistent storage
    ///
    /// The parameter's current value (set with `set()`) will be saved so that
    /// it persists across reboots. Raises an error if the parameter does not
    /// exist or is not persistent.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn persistent_store<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.param.persistent_store(&name).await.map_err(to_pyerr)
        })
    }

    /// Clear the stored value from persistent storage
    ///
    /// After clearing, the parameter will revert to the firmware default on
    /// the next reboot. Raises an error if the parameter does not exist or
    /// is not persistent.
    ///
    /// # Arguments
    /// * `name` - Parameter name in format "group.name"
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn persistent_clear<'py>(&self, py: Python<'py>, name: String) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            cf.param.persistent_clear(&name).await.map_err(to_pyerr)
        })
    }
}
