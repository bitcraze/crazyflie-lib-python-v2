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

//! Subsystems module - exposes all Crazyflie subsystems

mod commander;
mod console;
pub mod high_level_commander;
pub mod localization;
mod log;
pub mod memory;
mod param;
mod platform;

pub use commander::Commander;
pub use console::Console;
pub use high_level_commander::HighLevelCommander;
pub use localization::{Localization, EmergencyControl, ExternalPose, Lighthouse, LocoPositioning, LighthouseAngleData, LighthouseAngles};
pub use log::{Log, LogBlock, LogStream};
pub use memory::{Memory, Poly, Poly4D, CompressedStart, CompressedSegment};
pub use param::Param;
pub use platform::{Platform, AppChannel};
