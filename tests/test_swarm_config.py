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
"""Tests for swarm files and home pads"""

from pathlib import Path

import pytest

from cflib2.swarm import Drone, Swarm, load_swarm_config
from cflib2.swarm.config import normalize_uri, parse_swarm_config
from cflib2.swarm.layout import Position

EXAMPLE_FILE = Path(__file__).parent.parent / "examples" / "swarm.yaml"

SWARM_FILE = """\
name: Flight Area
lighthouse: bitcraze/flight-area
units:
- uri: radio:///65/2M/BADC0DE001
  name: CF-01
# - uri: radio:///65/2M/BADC0DE002
#   name: CF-02
- uri: radio:///65/2M/BADC0DE003
  name: CF-03
"""


class TestSwarmConfig:
    def test_load_file(self, tmp_path: Path) -> None:
        path = tmp_path / "swarm.yaml"
        path.write_text(SWARM_FILE)
        config = load_swarm_config(path)
        assert config.name == "Flight Area"
        assert config.extra == {"lighthouse": "bitcraze/flight-area"}
        assert len(config.units) == 2  # commented out unit skipped
        assert config.units[0].uri == "radio://0/65/2M/BADC0DE001"
        assert config.names["radio://0/65/2M/BADC0DE003"] == "CF-03"

    def test_example_file_is_valid(self) -> None:
        assert load_swarm_config(EXAMPLE_FILE).units

    def test_normalize_uri(self) -> None:
        assert normalize_uri("radio:///65/2M/E7") == "radio://0/65/2M/E7"
        assert normalize_uri("radio://1/65/2M/E7") == "radio://1/65/2M/E7"
        assert normalize_uri("usb://0") == "usb://0"

    def test_names_are_optional(self) -> None:
        config = parse_swarm_config({"units": [{"uri": "radio://0/80/2M/E7"}]})
        assert config.units[0].name is None
        assert config.names == {}

    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"units": "nope"},
            {"units": [{"name": "no uri"}]},
            {"units": [{"uri": "radio://0/80/2M/E7"}, {"uri": "radio://0/80/2M/E7"}]},
        ],
    )
    def test_invalid(self, data: dict) -> None:
        with pytest.raises(ValueError):
            parse_swarm_config(data)


class TestHomePads:
    @pytest.mark.asyncio
    async def test_set_home_pads_uses_current_position(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        positions = {"a": (1.0, 2.0, 0.1), "b": (-1.0, 0.5, 0.0)}

        async def read_position(self: Drone, timeout: float = 5.0) -> Position:
            return positions[self.uri]

        monkeypatch.setattr(Drone, "read_position", read_position)
        swarm = Swarm.from_drones(
            [Drone(uri="a", cf=None, label="CF-A"), Drone(uri="b", cf=None)]  # type: ignore[arg-type]
        )
        await swarm.set_home_pads()

        a, b = swarm.drones
        assert a.pad is not None and b.pad is not None
        assert (a.pad.index, a.pad.position) == (1, (1.0, 2.0, 0.1))
        assert (b.pad.index, b.pad.position) == (2, (-1.0, 0.5, 0.0))
        assert (a.name, b.name) == ("CF-A", "#2")
