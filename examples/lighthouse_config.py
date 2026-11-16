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
"""
Read or write the lighthouse configuration of a Crazyflie.

This example demonstrates how to:
- Read base station geometry and calibration data and print it as YAML
- Load a YAML file, write the geometry and calibration data to the
  Crazyflie and persist it to permanent storage

The YAML file uses the same format as the cfclient, cflib and cfcli.

REQUIREMENTS:
- Crazyflie with Lighthouse deck

Example usage:
    python lighthouse_config.py                              # Read and print the configuration
    python lighthouse_config.py --write lighthouse.yaml      # Write and persist a configuration
    python lighthouse_config.py --uri radio://0/80/2M/E7E7E7E701   # Custom URI
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import tyro

from cflib2 import Crazyflie, LinkContext
from cflib2.memory import (
    LighthouseBsCalibration,
    LighthouseBsGeometry,
    LighthouseConfig,
    LighthouseWriteReport,
)

MAX_BASE_STATIONS = 16


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""
    write: str | None = None
    """YAML file to write to the Crazyflie. If not given, the configuration is read and printed"""


async def read_config(cf: Crazyflie) -> None:
    """Read the configuration from the Crazyflie and print it as YAML"""
    memory = cf.memory()

    print("\nReading geometries...")
    geometries = await memory.read_lighthouse_geometries()
    print("Reading calibrations...")
    calibrations = await memory.read_lighthouse_calibrations()
    system_type = int(await cf.param().get("lighthouse.systemType"))

    config = LighthouseConfig(system_type, geometries, calibrations)

    print()
    print(config.to_yaml())


async def write_config(cf: Crazyflie, path: str) -> None:
    """Load a YAML file and write the configuration to the Crazyflie"""
    # Checks the file type, version, system type and base station IDs, so an
    # invalid file fails here, before anything is written to the Crazyflie
    with open(path) as f:
        config = LighthouseConfig.from_yaml(f.read())
    print(f"\nLoaded {path}")

    # Start with empty (invalid) data in all 16 slots, so base stations that are
    # not in the file are cleared on the Crazyflie. Slots above what the
    # Crazyflie supports are rejected by the firmware and skipped.
    geometries = {bs_id: LighthouseBsGeometry() for bs_id in range(MAX_BASE_STATIONS)}
    calibrations = {
        bs_id: LighthouseBsCalibration() for bs_id in range(MAX_BASE_STATIONS)
    }
    file_geos = config.geometries
    file_calibs = config.calibrations
    geometries.update(file_geos)
    calibrations.update(file_calibs)

    # Set the system type first: changing it clears the geometry and calibration
    # data in the Crazyflie's RAM when base stations are visible. The switch can
    # take up to 0.5 s and setting the parameter gives no signal when it is done,
    # so wait before writing.
    print(f"Setting system type to {config.system_type}...")
    await cf.param().set("lighthouse.systemType", config.system_type)
    await asyncio.sleep(0.8)

    memory = cf.memory()

    print("Writing geometries...")
    geo_report = await memory.write_lighthouse_geometries(geometries)
    print_report(geo_report, file_geos)

    print("Writing calibrations...")
    calib_report = await memory.write_lighthouse_calibrations(calibrations)
    print_report(calib_report, file_calibs)

    # Only the written slots are persisted
    print("Persisting data...")
    persisted = (
        await cf.localization()
        .lighthouse()
        .persist_lighthouse_data(
            geo_list=geo_report.written, calib_list=calib_report.written
        )
    )

    if not persisted:
        raise RuntimeError("Persisting the configuration failed")

    print("✓ Configuration written and persisted!")


def print_report(report: LighthouseWriteReport, from_file: dict[int, Any]) -> None:
    """Print which base stations from the file were written, which slots were
    cleared, and which slots the Crazyflie does not support"""
    written = [bs_id for bs_id in report.written if bs_id in from_file]
    cleared = [bs_id for bs_id in report.written if bs_id not in from_file]
    missing = [bs_id for bs_id in report.rejected if bs_id in from_file]
    unsupported = [bs_id for bs_id in report.rejected if bs_id not in from_file]

    print(f"  Written from file: {written}")
    print(f"  Cleared: {cleared}")
    print(f"  Not supported by the Crazyflie: {unsupported}")
    if missing:
        print(
            f"  Warning: base stations {missing} from the file are not supported by the Crazyflie"
        )


async def main() -> None:
    args = tyro.cli(Args)

    print(f"Connecting to {args.uri}...")
    context = LinkContext()
    cf = await Crazyflie.connect_from_uri(context, args.uri)
    print("Connected!")

    try:
        if args.write is None:
            await read_config(cf)
        else:
            await write_config(cf, args.write)

    finally:
        print("\nDisconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
