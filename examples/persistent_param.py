# ,---------,       ____  _ __
# |  ,-^-,  |      / __ )(_) /_______________ _____  ___
# | (  O  ) |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
# | / ,--'  |    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#    +------`   /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
# Copyright (C) 2025 Bitcraze AB
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
Demonstrate persistent parameter storage on the Crazyflie.

Persistent parameters retain their values across reboots by storing them
in EEPROM. This example shows how to:
- List all persistent parameters
- Get default values
- Query persistent storage state
- Store a parameter value to EEPROM
- Clear a stored value from EEPROM

Example usage:
    python persistent_param.py                                    # Use default URI
    python persistent_param.py --uri radio://0/80/2M/E7E7E7E701  # Custom URI
"""

import asyncio
from dataclasses import dataclass

import tyro

from cflib2 import Crazyflie, LinkContext


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""


async def main() -> None:
    args = tyro.cli(Args)

    print(f"Connecting to {args.uri}...")
    context = LinkContext()
    cf = await Crazyflie.connect_from_uri(context, args.uri)
    print("Connected!\n")

    param = cf.param()

    try:
        # Step 1: List persistent parameters
        print("=== Persistent Parameters ===")
        persistent_params = []

        for name in param.names():
            if await param.is_persistent(name):
                persistent_params.append(name)

        print(f"Found {len(persistent_params)} persistent parameters\n")

        # Step 2: Get default values
        print("=== Default Values ===\n")

        test_params = ["ring.effect", "activeMarker.back", "pm.lowVoltage"]

        for name in test_params:
            value = await param.get_default_value(name)
            print(f"{name}: {value}")

        # Step 3: Get persistent state
        print("\n=== Persistent Parameter States ===\n")

        for name in test_params:
            state = await param.persistent_get_state(name)
            print(f"{name}:")
            print(f"  Default value: {state.default_value}")
            if state.is_stored:
                print(f"  Stored value:  {state.stored_value}")
            else:
                print("  Stored: No (using default)")
            print()

        # Step 4: Store a value to EEPROM
        print("=== Storing a Parameter ===\n")

        test_param = "ring.effect"

        current_value = await param.get(test_param)
        print(f"Current value of {test_param}: {current_value}")

        new_value = 10
        print(f"Setting {test_param} to {new_value}")
        await param.set(test_param, new_value)

        print("Storing to EEPROM...")
        await param.persistent_store(test_param)
        print("Stored successfully!\n")

        # Verify it's now marked as stored
        state = await param.persistent_get_state(test_param)
        print("Verification:")
        print(f"  Default value: {state.default_value}")
        if state.is_stored:
            print(f"  Stored value:  {state.stored_value}")
        else:
            print("  Stored: No (using default)")

        # Step 5: Clear a stored value from EEPROM
        print("\n=== Clearing a Stored Parameter ===\n")

        print("Clearing stored value from EEPROM...")
        await param.persistent_clear(test_param)
        print("Cleared successfully!\n")

        # Verify it's now using the default again
        state = await param.persistent_get_state(test_param)
        print("Verification:")
        print(f"  Default value: {state.default_value}")
        if state.is_stored:
            print(f"  Stored value:  {state.stored_value}")
        else:
            print("  Stored: No (using default)")

    finally:
        print("\nDisconnecting...")
        await cf.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
