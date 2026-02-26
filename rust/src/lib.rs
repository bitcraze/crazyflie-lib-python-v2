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

//! Python bindings for the Crazyflie rust library

#![warn(missing_docs)]

use pyo3::prelude::*;

mod crazyflie;
mod error;
mod link_context;
pub mod subsystems;
mod toc_cache;

use crazyflie::Crazyflie;
use link_context::LinkContext;
use subsystems::{
    Commander, Console, Log, LogBlock, LogData, LogStream, Param, Platform, AppChannel,
    Localization, EmergencyControl, ExternalPose, Lighthouse, LocoPositioning,
    LighthouseAngleData, LighthouseAngles,
    Memory, Poly, Poly4D, CompressedStart, CompressedSegment,
};
use toc_cache::{NoTocCache, InMemoryTocCache, FileTocCache};

/// Python module definition
#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Crazyflie>()?;
    m.add_class::<LinkContext>()?;
    m.add_class::<Commander>()?;
    m.add_class::<Console>()?;
    m.add_class::<Log>()?;
    m.add_class::<LogBlock>()?;
    m.add_class::<LogData>()?;
    m.add_class::<LogStream>()?;
    m.add_class::<Param>()?;
    m.add_class::<Platform>()?;
    m.add_class::<AppChannel>()?;
    m.add_class::<Localization>()?;
    m.add_class::<EmergencyControl>()?;
    m.add_class::<ExternalPose>()?;
    m.add_class::<Lighthouse>()?;
    m.add_class::<LocoPositioning>()?;
    m.add_class::<LighthouseAngleData>()?;
    m.add_class::<LighthouseAngles>()?;
    m.add_class::<Memory>()?;
    m.add_class::<Poly>()?;
    m.add_class::<Poly4D>()?;
    m.add_class::<CompressedStart>()?;
    m.add_class::<CompressedSegment>()?;
    m.add_class::<NoTocCache>()?;
    m.add_class::<InMemoryTocCache>()?;
    m.add_class::<FileTocCache>()?;
    Ok(())
}

/// Custom stub info gatherer that looks for pyproject.toml in the parent directory.
pub fn stub_info() -> pyo3_stub_gen::Result<pyo3_stub_gen::StubInfo> {
    use std::path::PathBuf;

    // CARGO_MANIFEST_DIR is rust/, so go up one level to find pyproject.toml
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let pyproject_path = manifest_dir.parent().unwrap().join("pyproject.toml");

    pyo3_stub_gen::StubInfo::from_pyproject_toml(pyproject_path)
}
