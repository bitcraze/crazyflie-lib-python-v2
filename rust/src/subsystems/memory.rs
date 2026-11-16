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

//! # Memory subsystem bindings
//!
//! Provides Python bindings for memory operations.
//! Trajectory data is built in Python using [`Poly`], [`Poly4D`],
//! [`CompressedStart`], and [`CompressedSegment`], then uploaded
//! via the [`Memory`] subsystem. LED ring colors are set using
//! [`LedRingColor`] and written via [`Memory::write_led_ring`].
//! Lighthouse base station configuration is read and written as
//! [`LighthouseBsGeometry`] and [`LighthouseBsCalibration`], and loaded from
//! or saved to a configuration file with [`LighthouseConfig`].

use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;
use std::sync::Arc;

use crate::error::to_pyerr;
use crazyflie_lib::subsystems::memory::MemoryType;

/// A single LED color and intensity for the Crazyflie LED ring.
///
/// Used to build the list of 12 LED values passed to `Memory.write_led_ring()`.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LedRingColor {
    /// Red component (0-255)
    #[pyo3(get, set)]
    r: u8,
    /// Green component (0-255)
    #[pyo3(get, set)]
    g: u8,
    /// Blue component (0-255)
    #[pyo3(get, set)]
    b: u8,
    /// Intensity percentage (0-100); values above 100 are clamped to 100
    #[pyo3(get)]
    intensity: u8,
}

#[gen_stub_pymethods]
#[pymethods]
impl LedRingColor {
    /// Create a new LedRingColor.
    ///
    /// # Arguments
    /// * `r` - Red component (0-255, default 0)
    /// * `g` - Green component (0-255, default 0)
    /// * `b` - Blue component (0-255, default 0)
    /// * `intensity` - Intensity percentage (0-100, default 100); values above 100 are clamped to 100
    #[new]
    #[pyo3(signature = (r=0, g=0, b=0, intensity=100))]
    fn new(r: u8, g: u8, b: u8, intensity: u8) -> Self {
        Self { r, g, b, intensity: intensity.min(100) }
    }

    #[setter]
    fn set_intensity(&mut self, value: u8) {
        self.intensity = value.min(100);
    }

    /// Set R/G/B and optionally intensity in one call.
    ///
    /// # Arguments
    /// * `r` - Red component (0-255)
    /// * `g` - Green component (0-255)
    /// * `b` - Blue component (0-255)
    /// * `intensity` - Intensity percentage (0-100); if None, keeps current value; clamped to 100 if higher
    #[pyo3(signature = (r, g, b, intensity=None))]
    fn set(&mut self, r: u8, g: u8, b: u8, intensity: Option<u8>) {
        self.r = r;
        self.g = g;
        self.b = b;
        if let Some(i) = intensity {
            self.intensity = i.min(100);
        }
    }
}

/// A polynomial with up to 8 coefficients.
///
/// Coefficients beyond the provided values are zero-filled.
/// If more than 8 values are provided, only the first 8 are used.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct Poly {
    /// The polynomial coefficients
    values: Vec<f32>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Poly {
    #[new]
    fn new(values: Vec<f32>) -> Self {
        let mut padded = vec![0.0f32; 8];
        let len = values.len().min(8);
        padded[..len].copy_from_slice(&values[..len]);
        Self { values: padded }
    }

    /// Get the coefficient values as a list
    #[getter]
    fn values(&self) -> Vec<f32> {
        self.values.clone()
    }
}

impl Poly {
    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::Poly {
        crazyflie_lib::subsystems::memory::Poly::from_slice(&self.values)
    }
}

/// An uncompressed 4D polynomial trajectory segment.
///
/// Each segment defines motion along x, y, z, and yaw axes
/// using 8th-order polynomials over a given duration.
/// Packs to 132 bytes.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct Poly4D {
    duration: f32,
    x: Poly,
    y: Poly,
    z: Poly,
    yaw: Poly,
}

#[gen_stub_pymethods]
#[pymethods]
impl Poly4D {
    #[new]
    fn new(duration: f32, x: Poly, y: Poly, z: Poly, yaw: Poly) -> Self {
        Self { duration, x, y, z, yaw }
    }

    /// Duration of this segment in seconds
    #[getter]
    fn duration(&self) -> f32 {
        self.duration
    }

    /// X polynomial
    #[getter]
    fn x(&self) -> Poly {
        self.x.clone()
    }

    /// Y polynomial
    #[getter]
    fn y(&self) -> Poly {
        self.y.clone()
    }

    /// Z polynomial
    #[getter]
    fn z(&self) -> Poly {
        self.z.clone()
    }

    /// Yaw polynomial
    #[getter]
    fn yaw(&self) -> Poly {
        self.yaw.clone()
    }
}

impl Poly4D {
    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::Poly4D {
        crazyflie_lib::subsystems::memory::Poly4D::new(
            self.duration,
            self.x.to_rust(),
            self.y.to_rust(),
            self.z.to_rust(),
            self.yaw.to_rust(),
        )
    }
}

/// Starting point for a compressed trajectory.
///
/// Defines the initial position (x, y, z in meters) and yaw (radians).
/// Spatial range: approximately ±32.767 meters.
/// Packs to 8 bytes.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct CompressedStart {
    /// X coordinate in meters
    #[pyo3(get)]
    x: f32,
    /// Y coordinate in meters
    #[pyo3(get)]
    y: f32,
    /// Z coordinate in meters
    #[pyo3(get)]
    z: f32,
    /// Yaw angle in radians
    #[pyo3(get)]
    yaw: f32,
}

#[gen_stub_pymethods]
#[pymethods]
impl CompressedStart {
    #[new]
    fn new(x: f32, y: f32, z: f32, yaw: f32) -> Self {
        Self { x, y, z, yaw }
    }
}

impl CompressedStart {
    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::CompressedStart {
        crazyflie_lib::subsystems::memory::CompressedStart::new(self.x, self.y, self.z, self.yaw)
    }
}

/// A segment in a compressed trajectory.
///
/// Each axis can have 0, 1, 3, or 7 polynomial coefficients.
/// Spatial values are encoded as millimeters (±32.767m range).
/// Yaw values are encoded as 1/10th degrees.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct CompressedSegment {
    /// Duration of this segment in seconds
    #[pyo3(get)]
    duration: f32,
    /// X polynomial coefficients (0, 1, 3, or 7 elements)
    #[pyo3(get)]
    x: Vec<f32>,
    /// Y polynomial coefficients (0, 1, 3, or 7 elements)
    #[pyo3(get)]
    y: Vec<f32>,
    /// Z polynomial coefficients (0, 1, 3, or 7 elements)
    #[pyo3(get)]
    z: Vec<f32>,
    /// Yaw polynomial coefficients (0, 1, 3, or 7 elements)
    #[pyo3(get)]
    yaw: Vec<f32>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CompressedSegment {
    /// Create a new compressed segment.
    ///
    /// Each element list must have 0, 1, 3, or 7 values.
    #[new]
    fn new(duration: f32, x: Vec<f32>, y: Vec<f32>, z: Vec<f32>, yaw: Vec<f32>) -> PyResult<Self> {
        // Validate lengths eagerly so errors are clear
        for (name, v) in [("x", &x), ("y", &y), ("z", &z), ("yaw", &yaw)] {
            let len = v.len();
            if len != 0 && len != 1 && len != 3 && len != 7 {
                return Err(PyValueError::new_err(
                    format!("{} element length must be 0, 1, 3, or 7 (got {})", name, len)
                ));
            }
        }
        Ok(Self { duration, x, y, z, yaw })
    }
}

impl CompressedSegment {
    fn to_rust(&self) -> crazyflie_lib::Result<crazyflie_lib::subsystems::memory::CompressedSegment> {
        crazyflie_lib::subsystems::memory::CompressedSegment::new(
            self.duration,
            self.x.clone(),
            self.y.clone(),
            self.z.clone(),
            self.yaw.clone(),
        )
    }
}

/// Calibration data for one sweep of a lighthouse base station.
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

impl From<&crazyflie_lib::subsystems::memory::LighthouseCalibrationSweep> for LighthouseCalibrationSweep {
    fn from(sweep: &crazyflie_lib::subsystems::memory::LighthouseCalibrationSweep) -> Self {
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

impl LighthouseCalibrationSweep {
    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::LighthouseCalibrationSweep {
        crazyflie_lib::subsystems::memory::LighthouseCalibrationSweep {
            phase: self.phase,
            tilt: self.tilt,
            curve: self.curve,
            gibmag: self.gibmag,
            gibphase: self.gibphase,
            ogeemag: self.ogeemag,
            ogeephase: self.ogeephase,
        }
    }
}

/// Calibration data for one lighthouse base station.
///
/// `sweeps` returns copies, so to change a sweep, modify it and assign the
/// whole list back: `calib.sweeps = [sweep0, sweep1]`.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseBsCalibration {
    sweeps: [LighthouseCalibrationSweep; 2],
    /// Base station UID
    #[pyo3(get, set)]
    uid: u32,
    /// Whether this calibration data is valid
    #[pyo3(get, set)]
    valid: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseBsCalibration {
    /// Create a new LighthouseBsCalibration.
    ///
    /// # Arguments
    /// * `sweeps` - List of exactly 2 LighthouseCalibrationSweep (default: two zeroed sweeps)
    /// * `uid` - Base station UID (default 0)
    /// * `valid` - Whether the data is valid (default False)
    #[new]
    #[pyo3(signature = (sweeps=None, uid=0, valid=false))]
    fn new(sweeps: Option<Vec<LighthouseCalibrationSweep>>, uid: u32, valid: bool) -> PyResult<Self> {
        let sweeps = match sweeps {
            Some(sweeps) => Self::sweeps_from_vec(sweeps)?,
            None => std::array::from_fn(|_| LighthouseCalibrationSweep::new(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        };
        Ok(Self { sweeps, uid, valid })
    }

    /// Calibration for the 2 sweeps (list of 2 LighthouseCalibrationSweep)
    #[getter]
    fn sweeps(&self) -> Vec<LighthouseCalibrationSweep> {
        self.sweeps.to_vec()
    }

    #[setter]
    fn set_sweeps(&mut self, sweeps: Vec<LighthouseCalibrationSweep>) -> PyResult<()> {
        self.sweeps = Self::sweeps_from_vec(sweeps)?;
        Ok(())
    }
}

impl LighthouseBsCalibration {
    fn sweeps_from_vec(sweeps: Vec<LighthouseCalibrationSweep>) -> PyResult<[LighthouseCalibrationSweep; 2]> {
        let len = sweeps.len();
        sweeps.try_into().map_err(|_| PyValueError::new_err(
            format!("Expected 2 sweeps, got {}", len)
        ))
    }

    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::LighthouseBsCalibration {
        crazyflie_lib::subsystems::memory::LighthouseBsCalibration {
            sweeps: [self.sweeps[0].to_rust(), self.sweeps[1].to_rust()],
            uid: self.uid,
            valid: self.valid,
        }
    }
}

impl From<&crazyflie_lib::subsystems::memory::LighthouseBsCalibration> for LighthouseBsCalibration {
    fn from(calib: &crazyflie_lib::subsystems::memory::LighthouseBsCalibration) -> Self {
        Self {
            sweeps: [(&calib.sweeps[0]).into(), (&calib.sweeps[1]).into()],
            uid: calib.uid,
            valid: calib.valid,
        }
    }
}

/// Geometry data (position and orientation) for one lighthouse base station.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseBsGeometry {
    origin: [f32; 3],
    rotation_matrix: [[f32; 3]; 3],
    /// Whether this geometry data is valid
    #[pyo3(get, set)]
    valid: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseBsGeometry {
    /// Create a new LighthouseBsGeometry.
    ///
    /// # Arguments
    /// * `origin` - Position [x, y, z] in meters (default all zeros)
    /// * `rotation_matrix` - 3x3 rotation matrix as a list of 3 rows (default all zeros)
    /// * `valid` - Whether the data is valid (default False)
    #[new]
    #[pyo3(signature = (origin=None, rotation_matrix=None, valid=false))]
    fn new(origin: Option<Vec<f32>>, rotation_matrix: Option<Vec<Vec<f32>>>, valid: bool) -> PyResult<Self> {
        let origin = match origin {
            Some(origin) => Self::origin_from_vec(origin)?,
            None => [0.0; 3],
        };
        let rotation_matrix = match rotation_matrix {
            Some(rotation_matrix) => Self::rotation_matrix_from_vec(rotation_matrix)?,
            None => [[0.0; 3]; 3],
        };
        Ok(Self { origin, rotation_matrix, valid })
    }

    /// Position of the base station [x, y, z] in meters
    #[getter]
    fn origin(&self) -> Vec<f32> {
        self.origin.to_vec()
    }

    #[setter]
    fn set_origin(&mut self, origin: Vec<f32>) -> PyResult<()> {
        self.origin = Self::origin_from_vec(origin)?;
        Ok(())
    }

    /// Rotation matrix of the base station, as a list of 3 rows with 3 values each
    #[getter]
    fn rotation_matrix(&self) -> Vec<Vec<f32>> {
        self.rotation_matrix.iter().map(|row| row.to_vec()).collect()
    }

    #[setter]
    fn set_rotation_matrix(&mut self, rotation_matrix: Vec<Vec<f32>>) -> PyResult<()> {
        self.rotation_matrix = Self::rotation_matrix_from_vec(rotation_matrix)?;
        Ok(())
    }
}

impl LighthouseBsGeometry {
    fn origin_from_vec(origin: Vec<f32>) -> PyResult<[f32; 3]> {
        let len = origin.len();
        origin.try_into().map_err(|_| PyValueError::new_err(
            format!("origin must have 3 values [x, y, z], got {}", len)
        ))
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

    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::LighthouseBsGeometry {
        crazyflie_lib::subsystems::memory::LighthouseBsGeometry {
            origin: self.origin,
            rotation_matrix: self.rotation_matrix,
            valid: self.valid,
        }
    }
}

impl From<&crazyflie_lib::subsystems::memory::LighthouseBsGeometry> for LighthouseBsGeometry {
    fn from(geo: &crazyflie_lib::subsystems::memory::LighthouseBsGeometry) -> Self {
        Self {
            origin: geo.origin,
            rotation_matrix: geo.rotation_matrix,
            valid: geo.valid,
        }
    }
}

/// Result of writing several lighthouse base station slots.
///
/// Returned by `Memory.write_lighthouse_geometries()` and
/// `Memory.write_lighthouse_calibrations()`. Use `written` to decide which
/// slots to persist with `Lighthouse.persist_lighthouse_data()`.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseWriteReport {
    /// Base station IDs that were written, in ascending order
    #[pyo3(get)]
    written: Vec<u8>,
    /// Base station IDs the Crazyflie rejected because it does not support
    /// that many base stations, in ascending order
    #[pyo3(get)]
    rejected: Vec<u8>,
}

impl From<crazyflie_lib::subsystems::memory::LighthouseWriteReport> for LighthouseWriteReport {
    fn from(report: crazyflie_lib::subsystems::memory::LighthouseWriteReport) -> Self {
        Self { written: report.written, rejected: report.rejected }
    }
}

/// A lighthouse system configuration, as stored in a configuration file.
///
/// Use `LighthouseConfig.from_yaml()` to load a file and `to_yaml()` to save one.
/// The geometries and calibrations can be written to the Crazyflie with
/// `Memory.write_lighthouse_geometries()` and `Memory.write_lighthouse_calibrations()`.
///
/// `geometries` and `calibrations` return copies, so to change them, modify the
/// dict and assign it back: `config.geometries = geos`.
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct LighthouseConfig {
    /// Lighthouse system type (1 = Lighthouse V1, 2 = Lighthouse V2)
    #[pyo3(get, set)]
    system_type: u8,
    /// Geometry data, mapping base station ID to LighthouseBsGeometry
    #[pyo3(get, set)]
    geometries: HashMap<u8, LighthouseBsGeometry>,
    /// Calibration data, mapping base station ID to LighthouseBsCalibration
    #[pyo3(get, set)]
    calibrations: HashMap<u8, LighthouseBsCalibration>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LighthouseConfig {
    /// Create a new LighthouseConfig.
    ///
    /// # Arguments
    /// * `system_type` - Lighthouse system type, 1 or 2 (default 2)
    /// * `geometries` - Dict mapping base station ID to LighthouseBsGeometry (default empty)
    /// * `calibrations` - Dict mapping base station ID to LighthouseBsCalibration (default empty)
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

    /// Parse a lighthouse configuration from YAML.
    ///
    /// The file must have `type: lighthouse_system_configuration` and `version: '1'`.
    /// `systemType` defaults to 2 if missing, and `geos` and `calibs` default to empty.
    /// All geometries and calibrations in the file are marked valid.
    ///
    /// Raises `InvalidArgumentError` if the YAML can not be parsed, if the file type or
    /// version is missing or not supported, if the system type is not 1 or 2, or if a
    /// base station ID is out of range (0-15).
    ///
    /// # Arguments
    /// * `yaml` - The YAML content of the configuration file
    #[staticmethod]
    fn from_yaml(yaml: &str) -> PyResult<Self> {
        let config = crazyflie_lib::subsystems::memory::LighthouseConfig::from_yaml(yaml)
            .map_err(to_pyerr)?;
        Ok(Self::from(&config))
    }

    /// Serialize the configuration to YAML.
    ///
    /// Base stations are written in ascending ID order. Geometries and calibrations
    /// that are not valid are left out, since the file format has no valid flag.
    fn to_yaml(&self) -> PyResult<String> {
        self.to_rust().to_yaml().map_err(to_pyerr)
    }
}

impl LighthouseConfig {
    fn to_rust(&self) -> crazyflie_lib::subsystems::memory::LighthouseConfig {
        crazyflie_lib::subsystems::memory::LighthouseConfig {
            system_type: self.system_type,
            geometries: self.geometries.iter()
                .map(|(&bs_id, geo)| (bs_id, geo.to_rust()))
                .collect(),
            calibrations: self.calibrations.iter()
                .map(|(&bs_id, calib)| (bs_id, calib.to_rust()))
                .collect(),
        }
    }
}

impl From<&crazyflie_lib::subsystems::memory::LighthouseConfig> for LighthouseConfig {
    fn from(config: &crazyflie_lib::subsystems::memory::LighthouseConfig) -> Self {
        Self {
            system_type: config.system_type,
            geometries: config.geometries.iter()
                .map(|(&bs_id, geo)| (bs_id, LighthouseBsGeometry::from(geo)))
                .collect(),
            calibrations: config.calibrations.iter()
                .map(|(&bs_id, calib)| (bs_id, LighthouseBsCalibration::from(calib)))
                .collect(),
        }
    }
}

/// Find and open the lighthouse memory
async fn open_lighthouse_memory(
    cf: &crazyflie_lib::Crazyflie,
) -> PyResult<crazyflie_lib::subsystems::memory::LighthouseMemory> {
    let memories = cf.memory.get_memories(Some(MemoryType::Lighthouse));
    let mem_device = (*memories.first()
        .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
            "No lighthouse memory found on Crazyflie".to_owned()
        )))?)
        .clone();

    cf.memory.open_memory(mem_device).await
        .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
            "Failed to open lighthouse memory".to_owned()
        )))?
        .map_err(to_pyerr)
}

/// Memory subsystem wrapper.
///
/// Provides methods to upload trajectory data to the Crazyflie.
/// Access via `cf.memory()`.
#[gen_stub_pyclass]
#[pyclass]
pub struct Memory {
    pub(crate) cf: Arc<crazyflie_lib::Crazyflie>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Memory {
    /// Write an uncompressed (Poly4D) trajectory to the Crazyflie.
    ///
    /// Opens the trajectory memory, writes all segments, and closes
    /// the memory. Returns the number of bytes written.
    ///
    /// # Arguments
    /// * `trajectory` - List of Poly4D segments to upload
    /// * `start_addr` - Address in trajectory memory (default 0)
    #[pyo3(signature = (trajectory, start_addr=0))]
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, int]"))]
    fn write_trajectory<'py>(
        &self,
        py: Python<'py>,
        trajectory: Vec<Poly4D>,
        start_addr: usize,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            // Convert Python types to Rust types
            let rust_segments: Vec<crazyflie_lib::subsystems::memory::Poly4D> =
                trajectory.iter().map(|s| s.to_rust()).collect();

            // Find trajectory memory
            let memories = cf.memory.get_memories(Some(MemoryType::Trajectory));
            let mem_device = (*memories.first()
                .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                    "No trajectory memory found on Crazyflie".to_owned()
                )))?)
                .clone();

            // Open, write, close
            let traj_mem: crazyflie_lib::subsystems::memory::TrajectoryMemory =
                cf.memory.open_memory(mem_device).await
                    .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                        "Failed to open trajectory memory".to_owned()
                    )))?
                    .map_err(to_pyerr)?;

            let bytes_written = traj_mem.write_uncompressed(&rust_segments, start_addr).await
                .map_err(to_pyerr)?;

            cf.memory.close_memory(traj_mem).await.map_err(to_pyerr)?;

            Ok(bytes_written)
        })
    }

    /// Write a compressed trajectory to the Crazyflie.
    ///
    /// Opens the trajectory memory, writes the start point followed
    /// by all compressed segments, and closes the memory.
    /// Returns the number of bytes written.
    ///
    /// # Arguments
    /// * `start` - CompressedStart defining the initial position
    /// * `segments` - List of CompressedSegment instances
    /// * `start_addr` - Address in trajectory memory (default 0)
    #[pyo3(signature = (start, segments, start_addr=0))]
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, int]"))]
    fn write_compressed_trajectory<'py>(
        &self,
        py: Python<'py>,
        start: CompressedStart,
        segments: Vec<CompressedSegment>,
        start_addr: usize,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            // Convert Python types to Rust types
            let rust_start = start.to_rust();
            let rust_segments: Vec<crazyflie_lib::subsystems::memory::CompressedSegment> =
                segments.iter()
                    .map(|s| s.to_rust())
                    .collect::<crazyflie_lib::Result<Vec<_>>>()
                    .map_err(to_pyerr)?;

            // Find trajectory memory
            let memories = cf.memory.get_memories(Some(MemoryType::Trajectory));
            let mem_device = (*memories.first()
                .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                    "No trajectory memory found on Crazyflie".to_owned()
                )))?)
                .clone();

            // Open memory
            let traj_mem: crazyflie_lib::subsystems::memory::TrajectoryMemory =
                cf.memory.open_memory(mem_device).await
                    .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                        "Failed to open trajectory memory".to_owned()
                    )))?
                    .map_err(to_pyerr)?;

            // Write compressed trajectory (start point + segments)
            let bytes_written = traj_mem.write_compressed(
                &rust_start,
                &rust_segments,
                start_addr,
            ).await.map_err(to_pyerr)?;

            cf.memory.close_memory(traj_mem).await.map_err(to_pyerr)?;

            Ok(bytes_written)
        })
    }

    /// Write LED colors to the Crazyflie LED ring.
    ///
    /// Opens the LED driver memory, sets all 12 LED values, writes them to
    /// the ring, and closes the memory.
    ///
    /// # Arguments
    /// * `leds` - List of exactly 12 LedRingColor instances
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn write_led_ring<'py>(
        &self,
        py: Python<'py>,
        leds: Vec<LedRingColor>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            if leds.len() != 12 {
                return Err(PyValueError::new_err(
                    format!("Expected 12 LEDs, got {}", leds.len())
                ));
            }

            let memories = cf.memory.get_memories(Some(MemoryType::DriverLed));
            let mem_device = (*memories.first()
                .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                    "No LED driver memory found on Crazyflie".to_owned()
                )))?)
                .clone();

            let mut led_mem: crazyflie_lib::subsystems::memory::LedDriverMemory =
                cf.memory.initialize_memory(mem_device).await
                    .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                        "Failed to open LED driver memory".to_owned()
                    )))?
                    .map_err(to_pyerr)?;

            for (i, led) in leds.iter().enumerate() {
                led_mem.leds[i].r = led.r;
                led_mem.leds[i].g = led.g;
                led_mem.leds[i].b = led.b;
                led_mem.leds[i].intensity = led.intensity;
            }

            let write_result = led_mem.write_leds().await.map_err(to_pyerr);
            let close_result = cf.memory.close_memory(led_mem).await.map_err(to_pyerr);

            write_result?;
            close_result?;

            Ok(())
        })
    }

    /// Read lighthouse geometry data for all base stations.
    ///
    /// Opens the lighthouse memory, reads all slots the Crazyflie supports,
    /// and closes the memory.
    ///
    /// Returns a dict mapping base station ID to LighthouseBsGeometry.
    /// Only base stations with valid data are included.
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.dict[builtins.int, LighthouseBsGeometry]]"))]
    fn read_lighthouse_geometries<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let lh_mem = open_lighthouse_memory(&cf).await?;

            let read_result = lh_mem.read_all_geometries().await.map_err(to_pyerr);
            let close_result = cf.memory.close_memory(lh_mem).await.map_err(to_pyerr);

            let geometries = read_result?;
            close_result?;

            Ok(geometries.iter()
                .map(|(&bs_id, geo)| (bs_id, LighthouseBsGeometry::from(geo)))
                .collect::<HashMap<_, _>>())
        })
    }

    /// Read lighthouse calibration data for all base stations.
    ///
    /// Opens the lighthouse memory, reads all slots the Crazyflie supports,
    /// and closes the memory.
    ///
    /// Returns a dict mapping base station ID to LighthouseBsCalibration.
    /// Only base stations with valid data are included.
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, builtins.dict[builtins.int, LighthouseBsCalibration]]"))]
    fn read_lighthouse_calibrations<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let lh_mem = open_lighthouse_memory(&cf).await?;

            let read_result = lh_mem.read_all_calibrations().await.map_err(to_pyerr);
            let close_result = cf.memory.close_memory(lh_mem).await.map_err(to_pyerr);

            let calibrations = read_result?;
            close_result?;

            Ok(calibrations.iter()
                .map(|(&bs_id, calib)| (bs_id, LighthouseBsCalibration::from(calib)))
                .collect::<HashMap<_, _>>())
        })
    }

    /// Write lighthouse geometry data for several base stations.
    ///
    /// Opens the lighthouse memory, writes the slots in ascending order, and
    /// closes the memory. Slots the Crazyflie does not support are skipped
    /// and listed in the returned report. Any other error stops the write.
    ///
    /// The data is written to RAM only. Use
    /// `Lighthouse.persist_lighthouse_data()` with `report.written` to store it.
    ///
    /// # Arguments
    /// * `geometries` - Dict mapping base station ID (0-15) to LighthouseBsGeometry
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, LighthouseWriteReport]"))]
    fn write_lighthouse_geometries<'py>(
        &self,
        py: Python<'py>,
        geometries: HashMap<u8, LighthouseBsGeometry>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let rust_geometries = geometries.iter()
                .map(|(&bs_id, geo)| (bs_id, geo.to_rust()))
                .collect();

            let lh_mem = open_lighthouse_memory(&cf).await?;

            let write_result = lh_mem.write_geometries(&rust_geometries).await.map_err(to_pyerr);
            let close_result = cf.memory.close_memory(lh_mem).await.map_err(to_pyerr);

            let report = write_result?;
            close_result?;

            Ok(LighthouseWriteReport::from(report))
        })
    }

    /// Write lighthouse calibration data for several base stations.
    ///
    /// Opens the lighthouse memory, writes the slots in ascending order, and
    /// closes the memory. Slots the Crazyflie does not support are skipped
    /// and listed in the returned report. Any other error stops the write.
    ///
    /// The data is written to RAM only. Use
    /// `Lighthouse.persist_lighthouse_data()` with `report.written` to store it.
    ///
    /// # Arguments
    /// * `calibrations` - Dict mapping base station ID (0-15) to LighthouseBsCalibration
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, LighthouseWriteReport]"))]
    fn write_lighthouse_calibrations<'py>(
        &self,
        py: Python<'py>,
        calibrations: HashMap<u8, LighthouseBsCalibration>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let rust_calibrations = calibrations.iter()
                .map(|(&bs_id, calib)| (bs_id, calib.to_rust()))
                .collect();

            let lh_mem = open_lighthouse_memory(&cf).await?;

            let write_result = lh_mem.write_calibrations(&rust_calibrations).await.map_err(to_pyerr);
            let close_result = cf.memory.close_memory(lh_mem).await.map_err(to_pyerr);

            let report = write_result?;
            close_result?;

            Ok(LighthouseWriteReport::from(report))
        })
    }

    /// List all memories available on the Crazyflie.
    ///
    /// Returns a list of tuples `(id, type, size)`:
    /// - `id` (int): Memory ID used for read_raw/write_raw
    /// - `type` (int): Memory type (e.g. 0x12 for trajectory)
    /// - `size` (int): Memory size in bytes
    ///
    /// Optionally filter by memory type.
    #[pyo3(signature = (memory_type=None))]
    fn get_memories(&self, memory_type: Option<u8>) -> PyResult<Vec<(u8, u8, u32)>> {
        let filter = match memory_type {
            Some(t) => Some(MemoryType::try_from(t).map_err(to_pyerr)?),
            None => None,
        };
        let memories = self.cf.memory.get_memories(filter);
        Ok(memories.iter().map(|m| (m.memory_id, m.memory_type as u8, m.size)).collect())
    }

    /// Write raw bytes to a memory on the Crazyflie.
    ///
    /// Use `get_memories()` to discover available memory IDs.
    ///
    /// # Arguments
    /// * `memory_id` - ID of the memory to write to (from `get_memories()`)
    /// * `data` - Raw bytes to write
    /// * `start_addr` - Address in memory to write to (default 0)
    #[pyo3(signature = (memory_id, data, start_addr=0))]
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
    fn write_raw<'py>(
        &self,
        py: Python<'py>,
        memory_id: u8,
        data: Vec<u8>,
        start_addr: usize,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mem_device = cf.memory.get_memories(None).into_iter()
                .find(|m| m.memory_id == memory_id)
                .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                    format!("No memory with ID {} found", memory_id)
                )))?
                .clone();

            let raw_mem: crazyflie_lib::subsystems::memory::RawMemory =
                cf.memory.open_memory(mem_device).await
                    .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                        format!("Failed to open memory ID {}", memory_id)
                    )))?
                    .map_err(to_pyerr)?;

            raw_mem.write(start_addr, &data).await.map_err(to_pyerr)?;

            cf.memory.close_memory(raw_mem).await.map_err(to_pyerr)?;

            Ok(())
        })
    }

    /// Read raw bytes from a memory on the Crazyflie.
    ///
    /// Use `get_memories()` to discover available memory IDs.
    ///
    /// # Arguments
    /// * `memory_id` - ID of the memory to read from (from `get_memories()`)
    /// * `address` - Address in memory to read from
    /// * `length` - Number of bytes to read
    #[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, bytes]"))]
    fn read_raw<'py>(
        &self,
        py: Python<'py>,
        memory_id: u8,
        address: usize,
        length: usize,
    ) -> PyResult<Bound<'py, PyAny>> {
        let cf = self.cf.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let mem_device = cf.memory.get_memories(None).into_iter()
                .find(|m| m.memory_id == memory_id)
                .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                    format!("No memory with ID {} found", memory_id)
                )))?
                .clone();

            let raw_mem: crazyflie_lib::subsystems::memory::RawMemory =
                cf.memory.open_memory(mem_device).await
                    .ok_or_else(|| to_pyerr(crazyflie_lib::Error::MemoryError(
                        format!("Failed to open memory ID {}", memory_id)
                    )))?
                    .map_err(to_pyerr)?;

            let data = raw_mem.read(address, length).await.map_err(to_pyerr)?;

            cf.memory.close_memory(raw_mem).await.map_err(to_pyerr)?;

            Ok(data)
        })
    }
}
