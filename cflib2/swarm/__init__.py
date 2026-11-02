# ,---------,       ____  _ __
# |  ,-^-,  |      / __ )(_) /_______________ _____  ___
# | (  O  ) |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
# | / ,--'  |    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#    +------`   /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
# Copyright (C) 2026 Bitcraze AB
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Helpers for flying swarms of Crazyflies.

The modules are independent layers; use what you need:

- `swarm`: connecting, `parallel`/`sequential` with error policies, and the
  `flight()` safety scope
- `config`: YAML swarm files
- `layout`: pad layouts and matching drones to pads
- `grouping`: splitting the swarm into ordered groups
- `formation`: hover grids and the order to fill them
- `sequences`: take off, land, go to, in groups
- `docking`: landing on charging docks with retries
- `leds`: colour LED deck helpers
"""

from cflib2.swarm import formation, grouping
from cflib2.swarm.config import SwarmConfig, Unit, load_swarm_config
from cflib2.swarm.docking import (
    DockingSettings,
    check_docked,
    land_and_check,
    land_on_pads,
    precision_land,
    redock,
)
from cflib2.swarm.drone import Battery, Drone, DroneStatus, UnstablePositionError
from cflib2.swarm.layout import AssignmentError, Layout, Pad
from cflib2.swarm.sequences import (
    go_to,
    land,
    orbit,
    return_to_pads,
    run_in_groups,
    takeoff,
)
from cflib2.swarm.swarm import (
    DroneLostError,
    LowBatteryError,
    OnDroneLost,
    OnError,
    Swarm,
    SwarmError,
    UnhealthyDroneError,
)

__all__ = [
    "AssignmentError",
    "Battery",
    "DockingSettings",
    "Drone",
    "DroneLostError",
    "DroneStatus",
    "Layout",
    "LowBatteryError",
    "OnDroneLost",
    "OnError",
    "Pad",
    "Swarm",
    "SwarmConfig",
    "SwarmError",
    "UnhealthyDroneError",
    "Unit",
    "UnstablePositionError",
    "check_docked",
    "formation",
    "go_to",
    "grouping",
    "land",
    "land_and_check",
    "land_on_pads",
    "load_swarm_config",
    "orbit",
    "precision_land",
    "redock",
    "return_to_pads",
    "run_in_groups",
    "takeoff",
]
