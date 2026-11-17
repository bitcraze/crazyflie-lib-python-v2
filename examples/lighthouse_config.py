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

- Without `--write`: reads the base station geometry and calibration data and
  prints it as YAML
- With `--write <file>`: loads a YAML file, writes it to the Crazyflie and
  persists it to permanent storage

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

import tyro

from cflib2 import Crazyflie, LinkContext
from cflib2.lighthouse import (
    LighthouseConfig,
    LighthouseSlotReport,
    read_config,
    write_config,
)


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""
    write: str | None = None
    """YAML file to write to the Crazyflie. If not given, the configuration is read and printed"""


async def read(cf: Crazyflie) -> None:
    """Read the configuration from the Crazyflie and print it as YAML"""
    print("\nReading geometries and calibrations...")
    config = await read_config(cf)

    print()
    print(config.to_yaml())


async def write(cf: Crazyflie, path: str) -> None:
    """Load a YAML file and write the configuration to the Crazyflie"""
    with open(path) as f:
        config = LighthouseConfig.from_yaml(f.read())
    print(f"\nLoaded {path}")

    print(f"Setting system type to {config.system_type}, writing and persisting...")
    report = await write_config(cf, config)

    print("Geometries:")
    print_report(report.geometries)
    print("Calibrations:")
    print_report(report.calibrations)

    print("✓ Configuration written and persisted!")


def print_report(report: LighthouseSlotReport) -> None:
    print(f"  Written from file: {report.written}")
    print(f"  Cleared: {report.cleared}")
    if report.rejected:
        print(
            f"  Warning: base stations {report.rejected} from the file are not supported by the Crazyflie"
        )


async def main() -> None:
    args = tyro.cli(Args)

    print(f"Connecting to {args.uri}...")
    context = LinkContext()
    cf = await Crazyflie.connect_from_uri(context, args.uri)
    print("Connected!")

    try:
        if args.write is None:
            await read(cf)
        else:
            await write(cf, args.write)

    finally:
        print("\nDisconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
