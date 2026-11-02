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
"""Pad layouts and matching drones to pads by their estimated position"""

import math
from collections.abc import Hashable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

K = TypeVar("K", bound=Hashable)

Position = tuple[float, float, float]


@dataclass(frozen=True)
class Pad:
    """A landing/charging pad.

    `index` is a stable, 1-based identifier for the pad. `cell` is the
    `(ix, iy)` grid coordinate when the pad belongs to a grid layout, and is
    used by the grid based grouping strategies.
    """

    index: int
    x: float
    y: float
    z: float = 0.0
    cell: tuple[int, int] | None = None

    @property
    def position(self) -> Position:
        return (self.x, self.y, self.z)

    def distance_xy(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)


class AssignmentError(ValueError):
    """Raised when drones cannot be matched one-to-one with pads"""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(
            "Pad assignment failed:\n" + "\n".join(f"  {p}" for p in problems)
        )


class Layout:
    """An ordered collection of pads"""

    def __init__(self, pads: Iterable[Pad]) -> None:
        self._pads = {p.index: p for p in pads}

    @classmethod
    def grid(
        cls,
        nx: int,
        ny: int,
        spacing: float,
        center: tuple[float, float] = (0.0, 0.0),
        z: float = 0.0,
    ) -> "Layout":
        """A rectangular grid centred on `center`.

        Pads are numbered column first: `index = ix * ny + iy + 1`, where x
        increases with `ix` and y decreases with `iy`. For a 7x7 grid with
        0.8 m spacing pad 1 is at (-2.4, 2.4) and pad 49 at (2.4, -2.4).
        """
        cx, cy = center
        return cls(
            Pad(
                index=ix * ny + iy + 1,
                x=round(cx + (ix - (nx - 1) / 2) * spacing, 6),
                y=round(cy + ((ny - 1) / 2 - iy) * spacing, 6),
                z=z,
                cell=(ix, iy),
            )
            for ix in range(nx)
            for iy in range(ny)
        )

    @classmethod
    def from_positions(cls, positions: Sequence[Sequence[float]]) -> "Layout":
        """A free-form layout from a list of (x, y) or (x, y, z) positions.

        Pads are numbered 1..n in the order given.
        """
        return cls(
            Pad(index=i, x=p[0], y=p[1], z=p[2] if len(p) > 2 else 0.0)
            for i, p in enumerate(positions, start=1)
        )

    def __getitem__(self, index: int) -> Pad:
        return self._pads[index]

    def __iter__(self) -> Iterator[Pad]:
        return iter(self._pads.values())

    def __len__(self) -> int:
        return len(self._pads)

    def nearest(self, x: float, y: float) -> tuple[Pad, float]:
        """The pad closest to (x, y) in the horizontal plane and its distance"""
        pad = min(self._pads.values(), key=lambda p: p.distance_xy(x, y))
        return pad, pad.distance_xy(x, y)

    def assign(self, positions: Mapping[K, Position], tolerance: float) -> dict[K, Pad]:
        """Match every position to its nearest pad.

        Raises `AssignmentError` listing all problems if a position is further
        than `tolerance` (m, horizontal) from every pad, or if two positions
        match the same pad. Pads without a drone are allowed.
        """
        problems: list[str] = []
        claims: dict[int, list[K]] = {}
        for key, (x, y, _) in positions.items():
            pad, dist = self.nearest(x, y)
            if dist > tolerance:
                problems.append(
                    f"{key} at ({x:.3f}, {y:.3f}) is {dist:.2f} m from the nearest pad "
                    f"{pad.index} (tolerance {tolerance} m)"
                )
            else:
                claims.setdefault(pad.index, []).append(key)

        for index, keys in claims.items():
            if len(keys) > 1:
                problems.append(
                    f"Pad {index} is claimed by {len(keys)} drones: {', '.join(map(str, keys))}"
                )

        if problems:
            raise AssignmentError(problems)
        return {keys[0]: self._pads[index] for index, keys in claims.items()}
