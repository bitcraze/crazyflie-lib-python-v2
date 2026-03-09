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

//! Error conversion utilities for Python bindings

use pyo3::exceptions::PyException;
use pyo3::prelude::*;

pyo3_stub_gen::create_exception!(cflib2._rust, CrazyflieError, PyException, "Base exception for all Crazyflie errors.");
pyo3_stub_gen::create_exception!(cflib2._rust, ProtocolVersionNotSupportedError, CrazyflieError, "Protocol version not supported.");
pyo3_stub_gen::create_exception!(cflib2._rust, ProtocolError, CrazyflieError, "Unexpected protocol error.");
pyo3_stub_gen::create_exception!(cflib2._rust, ParamError, CrazyflieError, "Parameter subsystem error.");
pyo3_stub_gen::create_exception!(cflib2._rust, LogError, CrazyflieError, "Log subsystem error.");
pyo3_stub_gen::create_exception!(cflib2._rust, ConversionError, CrazyflieError, "Value conversion error.");
pyo3_stub_gen::create_exception!(cflib2._rust, LinkError, CrazyflieError, "Crazyflie link error.");
pyo3_stub_gen::create_exception!(cflib2._rust, DisconnectedError, CrazyflieError, "Crazyflie is disconnected.");
pyo3_stub_gen::create_exception!(cflib2._rust, VariableNotFoundError, CrazyflieError, "Variable not found in TOC.");
pyo3_stub_gen::create_exception!(cflib2._rust, SystemError, CrazyflieError, "Async executor error.");
pyo3_stub_gen::create_exception!(cflib2._rust, AppchannelPacketTooLargeError, CrazyflieError, "App channel packet exceeds MTU.");
pyo3_stub_gen::create_exception!(cflib2._rust, InvalidArgumentError, CrazyflieError, "Invalid argument.");
pyo3_stub_gen::create_exception!(cflib2._rust, TimeoutError, CrazyflieError, "Operation timed out.");
pyo3_stub_gen::create_exception!(cflib2._rust, MemoryError, CrazyflieError, "Memory subsystem error.");
pyo3_stub_gen::create_exception!(cflib2._rust, InvalidParameterError, CrazyflieError, "Invalid parameter.");

/// Register all custom exception types with the Python module
pub fn register_exceptions(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();
    m.add("CrazyflieError", py.get_type::<CrazyflieError>())?;
    m.add("ProtocolVersionNotSupportedError", py.get_type::<ProtocolVersionNotSupportedError>())?;
    m.add("ProtocolError", py.get_type::<ProtocolError>())?;
    m.add("ParamError", py.get_type::<ParamError>())?;
    m.add("LogError", py.get_type::<LogError>())?;
    m.add("ConversionError", py.get_type::<ConversionError>())?;
    m.add("LinkError", py.get_type::<LinkError>())?;
    m.add("DisconnectedError", py.get_type::<DisconnectedError>())?;
    m.add("VariableNotFoundError", py.get_type::<VariableNotFoundError>())?;
    m.add("SystemError", py.get_type::<SystemError>())?;
    m.add("AppchannelPacketTooLargeError", py.get_type::<AppchannelPacketTooLargeError>())?;
    m.add("InvalidArgumentError", py.get_type::<InvalidArgumentError>())?;
    m.add("TimeoutError", py.get_type::<TimeoutError>())?;
    m.add("MemoryError", py.get_type::<MemoryError>())?;
    m.add("InvalidParameterError", py.get_type::<InvalidParameterError>())?;
    Ok(())
}

/// Convert Rust crazyflie_lib errors to Python exceptions
pub fn to_pyerr(err: crazyflie_lib::Error) -> PyErr {
    use crazyflie_lib::Error::*;
    let msg = err.to_string();
    match err {
        ProtocolVersionNotSupported { .. } => ProtocolVersionNotSupportedError::new_err(msg),
        ProtocolError(_) => self::ProtocolError::new_err(msg),
        ParamError(_) => self::ParamError::new_err(msg),
        LogError(_) => self::LogError::new_err(msg),
        ConversionError(_) => self::ConversionError::new_err(msg),
        LinkError(_) => self::LinkError::new_err(msg),
        Disconnected => DisconnectedError::new_err(msg),
        VariableNotFound => VariableNotFoundError::new_err(msg),
        SystemError(_) => self::SystemError::new_err(msg),
        AppchannelPacketTooLarge => AppchannelPacketTooLargeError::new_err(msg),
        InvalidArgument(_) => InvalidArgumentError::new_err(msg),
        Timeout => self::TimeoutError::new_err(msg),
        MemoryError(_) => self::MemoryError::new_err(msg),
        InvalidParameter(_) => InvalidParameterError::new_err(msg),
    }
}
