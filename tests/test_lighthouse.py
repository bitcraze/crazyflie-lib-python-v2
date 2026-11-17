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
import pytest

from cflib2.error import ConfigFileError
from cflib2.lighthouse import (
    LighthouseBsCalibration,
    LighthouseBsGeometry,
    LighthouseCalibrationSweep,
    LighthouseConfig,
)

CONFIG_FILE = """\
calibs:
  1:
    sweeps:
    - curve: 3.0
      gibmag: 4.0
      gibphase: 5.0
      ogeemag: 6.0
      ogeephase: 7.0
      phase: 1.0
      tilt: 2.0
    - curve: 3.5
      gibmag: 4.5
      gibphase: 5.5
      ogeemag: 6.5
      ogeephase: 7.5
      phase: 1.5
      tilt: 2.5
    uid: 1234
geos:
  1:
    origin:
    - 1.0
    - 2.0
    - 3.0
    rotation:
    - - 4.0
      - 5.0
      - 6.0
    - - 7.0
      - 8.0
      - 9.0
    - - 10.0
      - 11.0
      - 12.0
systemType: 1
type: lighthouse_system_configuration
version: '1'
"""


class TestLighthouseConfig:
    def test_from_yaml(self) -> None:
        config = LighthouseConfig.from_yaml(CONFIG_FILE)

        assert config.system_type == 1
        geo = config.geometries[1]
        assert geo.origin == [1.0, 2.0, 3.0]
        assert geo.rotation_matrix[2] == [10.0, 11.0, 12.0]
        assert geo.valid
        calib = config.calibrations[1]
        assert calib.uid == 1234
        assert calib.sweeps[1].ogeephase == 7.5
        assert calib.valid

    def test_round_trip(self) -> None:
        assert LighthouseConfig.from_yaml(CONFIG_FILE).to_yaml() == CONFIG_FILE

    def test_build_and_save(self) -> None:
        sweep = LighthouseCalibrationSweep(phase=1.0)
        config = LighthouseConfig(
            geometries={0: LighthouseBsGeometry(origin=[1.0, 2.0, 3.0], valid=True)},
            calibrations={
                0: LighthouseBsCalibration(sweeps=[sweep, sweep], uid=7, valid=True)
            },
        )

        loaded = LighthouseConfig.from_yaml(config.to_yaml())
        assert loaded.system_type == 2
        assert loaded.geometries[0].origin == [1.0, 2.0, 3.0]
        assert loaded.calibrations[0].uid == 7

    def test_invalid_file_raises(self) -> None:
        with pytest.raises(ConfigFileError):
            LighthouseConfig.from_yaml("type: something_else\nversion: '1'\n")

    def test_invalid_lengths_raise(self) -> None:
        with pytest.raises(ValueError):
            LighthouseBsGeometry(origin=[1.0, 2.0])
        with pytest.raises(ValueError):
            LighthouseBsCalibration(sweeps=[LighthouseCalibrationSweep()])
