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

import cflib2


EXCEPTION_NAMES = [name for name in cflib2.__all__ if name.endswith("Error")]


class TestExceptionHierarchy:
    """Verify that all custom exceptions inherit from CrazyflieError."""

    @pytest.mark.parametrize("name", EXCEPTION_NAMES)
    def test_exception_is_subclass_of_crazyflie_error(self, name: str) -> None:
        exc_class = getattr(cflib2, name)
        assert issubclass(exc_class, cflib2.CrazyflieError)
