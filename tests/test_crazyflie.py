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
import pytest


class TestCrazyflieConnection:
    """Test Crazyflie connection functionality"""

    @pytest.mark.asyncio
    async def test_crazyflie_invalid_uri_raises_exception(self) -> None:
        """Crazyflie.connect_from_uri() should raise exception for invalid URI"""
        from cflib2._rust import Crazyflie, LinkContext

        # Attempting to connect to invalid URI should fail
        context = LinkContext()
        with pytest.raises(Exception):
            await Crazyflie.connect_from_uri(context, "invalid://bad/uri")
