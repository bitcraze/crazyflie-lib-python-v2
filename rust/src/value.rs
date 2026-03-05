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

//! Crazyflie Value to Python conversion utilities

use pyo3::prelude::*;

/// Convert a crazyflie_lib::Value to a Python int or float.
pub fn value_to_python(py: Python<'_>, value: crazyflie_lib::Value) -> PyResult<Py<PyAny>> {
    Ok(match value {
        crazyflie_lib::Value::U8(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::U16(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::U32(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::U64(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::I8(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::I16(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::I32(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::I64(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::F16(v) => v.to_f32().into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::F32(v) => v.into_pyobject(py)?.into_any().unbind(),
        crazyflie_lib::Value::F64(v) => v.into_pyobject(py)?.into_any().unbind(),
    })
}
