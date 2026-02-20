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

//! Console subsystem - read text output from the Crazyflie

use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::sync::Arc;
use tokio::sync::Mutex;
use futures::stream::Stream;
use std::pin::Pin;

type LineStream = Pin<Box<dyn Stream<Item = String> + Send>>;

/// Access to the console subsystem
///
/// The Crazyflie has a text console that is used to communicate various information
/// and debug message to the ground.
#[gen_stub_pyclass]
#[pyclass]
pub struct Console {
    pub(crate) cf: Arc<crazyflie_lib::Crazyflie>,
    stream: Arc<Mutex<Option<LineStream>>>,
}

impl Console {
    /// Create a new Console instance
    pub fn new(cf: Arc<crazyflie_lib::Crazyflie>) -> Self {
        Console {
            cf,
            stream: Arc::new(Mutex::new(None)),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl Console {
    /// Get console lines as they arrive
    ///
    /// This function returns console lines line-by-line. It buffers lines internally
    /// and returns up to 100 lines per call with a 10ms timeout per line.
    ///
    /// The lib keeps track of the console history since connection, so the first
    /// call to this function will return all lines received since connection.
    ///
    /// Returns:
    ///     List of console output lines (up to 100 with 10ms timeout)
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.list[builtins.str]]"))]
    fn get_lines<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        let stream = self.stream.clone();

        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            use futures::StreamExt;

            let mut stream_guard = stream.lock().await;

            // Initialize stream if not already created
            if stream_guard.is_none() {
                let new_stream = cf.console.line_stream().await;
                *stream_guard = Some(Box::pin(new_stream));
            }

            let stream_ref = stream_guard.as_mut().unwrap();
            let mut lines = Vec::new();

            // Get up to 100 lines or timeout
            for _ in 0..100 {
                if let Ok(Some(line)) = tokio::time::timeout(
                    std::time::Duration::from_millis(10),
                    stream_ref.next()
                ).await {
                    lines.push(line);
                } else {
                    break;
                }
            }
            Ok(lines)
        })
    }
}
