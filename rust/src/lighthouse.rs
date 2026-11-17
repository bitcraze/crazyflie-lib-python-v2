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

//! Lighthouse configuration, from crazyflie_ecosystem::lighthouse

use crazyflie_ecosystem::crazyflie_lib::subsystems::memory as lib;
use crazyflie_ecosystem::lighthouse as eco;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

use crate::crazyflie::Crazyflie;
use crate::error::ecosystem_to_pyerr;

/// Calibration of one sweep of a lighthouse base station
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseCalibrationSweep {
    /// Phase offset
    #[pyo3(get, set)]
    phase: f32,
    /// Tilt angle
    #[pyo3(get, set)]
    tilt: f32,
    /// Curve compensation
    #[pyo3(get, set)]
    curve: f32,
    /// Gibbs magnitude
    #[pyo3(get, set)]
    gibmag: f32,
    /// Gibbs phase
    #[pyo3(get, set)]
    gibphase: f32,
    /// OGEE magnitude
    #[pyo3(get, set)]
    ogeemag: f32,
    /// OGEE phase
    #[pyo3(get, set)]
    ogeephase: f32,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseCalibrationSweep {
    /// Create a new LighthouseCalibrationSweep. All values default to 0.0.
    #[new]
    #[pyo3(signature = (phase=0.0, tilt=0.0, curve=0.0, gibmag=0.0, gibphase=0.0, ogeemag=0.0, ogeephase=0.0))]
    fn new(phase: f32, tilt: f32, curve: f32, gibmag: f32, gibphase: f32, ogeemag: f32, ogeephase: f32) -> Self {
        Self { phase, tilt, curve, gibmag, gibphase, ogeemag, ogeephase }
    }
}

impl From<&lib::LighthouseCalibrationSweep> for LighthouseCalibrationSweep {
    fn from(sweep: &lib::LighthouseCalibrationSweep) -> Self {
        Self {
            phase: sweep.phase,
            tilt: sweep.tilt,
            curve: sweep.curve,
            gibmag: sweep.gibmag,
            gibphase: sweep.gibphase,
            ogeemag: sweep.ogeemag,
            ogeephase: sweep.ogeephase,
        }
    }
}

impl From<&LighthouseCalibrationSweep> for lib::LighthouseCalibrationSweep {
    fn from(sweep: &LighthouseCalibrationSweep) -> Self {
        Self {
            phase: sweep.phase,
            tilt: sweep.tilt,
            curve: sweep.curve,
            gibmag: sweep.gibmag,
            gibphase: sweep.gibphase,
            ogeemag: sweep.ogeemag,
            ogeephase: sweep.ogeephase,
        }
    }
}

/// Calibration of one lighthouse base station
///
/// `sweeps` returns copies: modify a sweep and assign the whole list back.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseBsCalibration {
    sweeps: [LighthouseCalibrationSweep; 2],
    /// Base station UID
    #[pyo3(get, set)]
    uid: u32,
    /// Whether the calibration is valid
    #[pyo3(get, set)]
    valid: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseBsCalibration {
    /// Create a new LighthouseBsCalibration. `sweeps` must have 2 elements and defaults to zeroed sweeps.
    #[new]
    #[pyo3(signature = (sweeps=None, uid=0, valid=false))]
    fn new(sweeps: Option<Vec<LighthouseCalibrationSweep>>, uid: u32, valid: bool) -> PyResult<Self> {
        let sweeps = match sweeps {
            Some(sweeps) => sweeps_from_vec(sweeps)?,
            None => std::array::from_fn(|_| LighthouseCalibrationSweep::new(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        };
        Ok(Self { sweeps, uid, valid })
    }

    /// Calibration of the 2 sweeps
    #[getter]
    fn sweeps(&self) -> Vec<LighthouseCalibrationSweep> {
        self.sweeps.to_vec()
    }

    #[setter]
    fn set_sweeps(&mut self, sweeps: Vec<LighthouseCalibrationSweep>) -> PyResult<()> {
        self.sweeps = sweeps_from_vec(sweeps)?;
        Ok(())
    }
}

fn sweeps_from_vec(sweeps: Vec<LighthouseCalibrationSweep>) -> PyResult<[LighthouseCalibrationSweep; 2]> {
    let len = sweeps.len();
    sweeps
        .try_into()
        .map_err(|_| PyValueError::new_err(format!("Expected 2 sweeps, got {}", len)))
}

impl From<&lib::LighthouseBsCalibration> for LighthouseBsCalibration {
    fn from(calib: &lib::LighthouseBsCalibration) -> Self {
        Self {
            sweeps: [(&calib.sweeps[0]).into(), (&calib.sweeps[1]).into()],
            uid: calib.uid,
            valid: calib.valid,
        }
    }
}

impl From<&LighthouseBsCalibration> for lib::LighthouseBsCalibration {
    fn from(calib: &LighthouseBsCalibration) -> Self {
        Self {
            sweeps: [(&calib.sweeps[0]).into(), (&calib.sweeps[1]).into()],
            uid: calib.uid,
            valid: calib.valid,
        }
    }
}

/// Position and orientation of one lighthouse base station
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseBsGeometry {
    origin: [f32; 3],
    rotation_matrix: [[f32; 3]; 3],
    /// Whether the geometry is valid
    #[pyo3(get, set)]
    valid: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseBsGeometry {
    /// Create a new LighthouseBsGeometry. `origin` and `rotation_matrix` default to zeros.
    #[new]
    #[pyo3(signature = (origin=None, rotation_matrix=None, valid=false))]
    fn new(origin: Option<Vec<f32>>, rotation_matrix: Option<Vec<Vec<f32>>>, valid: bool) -> PyResult<Self> {
        let origin = match origin {
            Some(origin) => origin_from_vec(origin)?,
            None => [0.0; 3],
        };
        let rotation_matrix = match rotation_matrix {
            Some(rotation_matrix) => rotation_matrix_from_vec(rotation_matrix)?,
            None => [[0.0; 3]; 3],
        };
        Ok(Self { origin, rotation_matrix, valid })
    }

    /// Position [x, y, z] in meters
    #[getter]
    fn origin(&self) -> Vec<f32> {
        self.origin.to_vec()
    }

    #[setter]
    fn set_origin(&mut self, origin: Vec<f32>) -> PyResult<()> {
        self.origin = origin_from_vec(origin)?;
        Ok(())
    }

    /// Rotation matrix, as 3 rows of 3 values
    #[getter]
    fn rotation_matrix(&self) -> Vec<Vec<f32>> {
        self.rotation_matrix.iter().map(|row| row.to_vec()).collect()
    }

    #[setter]
    fn set_rotation_matrix(&mut self, rotation_matrix: Vec<Vec<f32>>) -> PyResult<()> {
        self.rotation_matrix = rotation_matrix_from_vec(rotation_matrix)?;
        Ok(())
    }
}

fn origin_from_vec(origin: Vec<f32>) -> PyResult<[f32; 3]> {
    let len = origin.len();
    origin
        .try_into()
        .map_err(|_| PyValueError::new_err(format!("origin must have 3 values [x, y, z], got {}", len)))
}

fn rotation_matrix_from_vec(rotation_matrix: Vec<Vec<f32>>) -> PyResult<[[f32; 3]; 3]> {
    let error = || PyValueError::new_err("rotation_matrix must be 3 rows with 3 values each");
    let rows: [Vec<f32>; 3] = rotation_matrix.try_into().map_err(|_| error())?;
    let mut result = [[0.0; 3]; 3];
    for (row, values) in result.iter_mut().zip(rows) {
        *row = values.try_into().map_err(|_| error())?;
    }
    Ok(result)
}

impl From<&lib::LighthouseBsGeometry> for LighthouseBsGeometry {
    fn from(geo: &lib::LighthouseBsGeometry) -> Self {
        Self { origin: geo.origin, rotation_matrix: geo.rotation_matrix, valid: geo.valid }
    }
}

impl From<&LighthouseBsGeometry> for lib::LighthouseBsGeometry {
    fn from(geo: &LighthouseBsGeometry) -> Self {
        Self { origin: geo.origin, rotation_matrix: geo.rotation_matrix, valid: geo.valid }
    }
}

/// A lighthouse system configuration
///
/// `geometries` and `calibrations` return copies: modify the dict and assign it back.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseConfig {
    /// Lighthouse system type (1 = Lighthouse V1, 2 = Lighthouse V2)
    #[pyo3(get, set)]
    system_type: u8,
    /// Geometry by base station ID
    #[pyo3(get, set)]
    geometries: HashMap<u8, LighthouseBsGeometry>,
    /// Calibration by base station ID
    #[pyo3(get, set)]
    calibrations: HashMap<u8, LighthouseBsCalibration>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseConfig {
    /// Create a new LighthouseConfig
    #[new]
    #[pyo3(signature = (system_type=2, geometries=None, calibrations=None))]
    fn new(
        system_type: u8,
        geometries: Option<HashMap<u8, LighthouseBsGeometry>>,
        calibrations: Option<HashMap<u8, LighthouseBsCalibration>>,
    ) -> Self {
        Self {
            system_type,
            geometries: geometries.unwrap_or_default(),
            calibrations: calibrations.unwrap_or_default(),
        }
    }

    /// Parse and check a lighthouse configuration from YAML
    ///
    /// Raises `ConfigFileError` if the file is malformed or not supported.
    #[staticmethod]
    fn from_yaml(yaml: &str) -> PyResult<Self> {
        let config = eco::LighthouseConfig::from_yaml(yaml).map_err(ecosystem_to_pyerr)?;
        Ok(Self::from(&config))
    }

    /// Serialize the configuration to YAML. Invalid geometries and calibrations are left out.
    fn to_yaml(&self) -> PyResult<String> {
        eco::LighthouseConfig::from(self).to_yaml().map_err(ecosystem_to_pyerr)
    }
}

impl From<&eco::LighthouseConfig> for LighthouseConfig {
    fn from(config: &eco::LighthouseConfig) -> Self {
        Self {
            system_type: config.system_type,
            geometries: config.geometries.iter().map(|(&id, geo)| (id, geo.into())).collect(),
            calibrations: config.calibrations.iter().map(|(&id, calib)| (id, calib.into())).collect(),
        }
    }
}

impl From<&LighthouseConfig> for eco::LighthouseConfig {
    fn from(config: &LighthouseConfig) -> Self {
        Self {
            system_type: config.system_type,
            geometries: config.geometries.iter().map(|(&id, geo)| (id, geo.into())).collect(),
            calibrations: config.calibrations.iter().map(|(&id, calib)| (id, calib.into())).collect(),
        }
    }
}

/// Outcome of writing geometry or calibration to all base station slots
// IDs are stored as u32: PyO3 converts Vec<u8> to bytes instead of a list
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseSlotReport {
    /// Base stations from the configuration that were written
    #[pyo3(get)]
    written: Vec<u32>,
    /// Slots not in the configuration that were cleared
    #[pyo3(get)]
    cleared: Vec<u32>,
    /// Base stations from the configuration that the Crazyflie does not support
    #[pyo3(get)]
    rejected: Vec<u32>,
}

impl From<eco::LighthouseSlotReport> for LighthouseSlotReport {
    fn from(report: eco::LighthouseSlotReport) -> Self {
        let ids = |ids: Vec<u8>| ids.into_iter().map(u32::from).collect();
        Self { written: ids(report.written), cleared: ids(report.cleared), rejected: ids(report.rejected) }
    }
}

/// Result of `write_config()`
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseConfigWriteReport {
    /// Geometry slots
    #[pyo3(get)]
    geometries: LighthouseSlotReport,
    /// Calibration slots
    #[pyo3(get)]
    calibrations: LighthouseSlotReport,
    complete: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseConfigWriteReport {
    /// True if every base station in the configuration was written
    fn is_complete(&self) -> bool {
        self.complete
    }
}

impl From<eco::LighthouseConfigWriteReport> for LighthouseConfigWriteReport {
    fn from(report: eco::LighthouseConfigWriteReport) -> Self {
        let complete = report.is_complete();
        Self { geometries: report.geometries.into(), calibrations: report.calibrations.into(), complete }
    }
}

/// Read the lighthouse system configuration from the Crazyflie
///
/// Only slots with valid data are included.
#[gen_stub_pyfunction]
#[pyfunction]
#[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, LighthouseConfig]"))]
pub fn read_lighthouse_config<'py>(py: Python<'py>, cf: PyRef<'py, Crazyflie>) -> PyResult<Bound<'py, PyAny>> {
    let cf = cf.inner.clone();
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let config = eco::read_config(&cf).await.map_err(ecosystem_to_pyerr)?;
        Ok(LighthouseConfig::from(&config))
    })
}

/// Write a lighthouse system configuration to the Crazyflie and persist it
///
/// Sets the system type, writes all 16 slots (clearing the ones not in `config`) and persists
/// the written slots. Base stations the Crazyflie does not support are skipped and listed in
/// `rejected` of the report.
#[gen_stub_pyfunction]
#[pyfunction]
#[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, LighthouseConfigWriteReport]"))]
pub fn write_lighthouse_config<'py>(
    py: Python<'py>,
    cf: PyRef<'py, Crazyflie>,
    config: LighthouseConfig,
) -> PyResult<Bound<'py, PyAny>> {
    let cf = cf.inner.clone();
    let config = eco::LighthouseConfig::from(&config);
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let report = eco::write_config(&cf, &config).await.map_err(ecosystem_to_pyerr)?;
        Ok(LighthouseConfigWriteReport::from(report))
    })
}
