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
"""Swarm description files.

A swarm file is YAML with a list of units::

    name: Flight Area
    lighthouse: bitcraze/flight-area
    units:
    - uri: radio:///65/2M/BADC0DE001
      name: CF-01
    - uri: radio:///65/2M/BADC0DE002
      name: CF-02

`name` is optional for the swarm and for each unit. Other top-level keys
(such as `lighthouse`) are kept in `SwarmConfig.extra`.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class Unit:
    uri: str
    name: str | None = None


@dataclass(frozen=True)
class SwarmConfig:
    units: list[Unit]
    name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def uris(self) -> list[str]:
        return [u.uri for u in self.units]

    @property
    def names(self) -> dict[str, str]:
        """URI to unit name, for the units that have a name"""
        return {u.uri: u.name for u in self.units if u.name}


def normalize_uri(uri: str) -> str:
    """Fill in radio 0 when the radio index is left out: `radio:///65/...`
    becomes `radio://0/65/...`"""
    if uri.startswith("radio:///"):
        return "radio://0/" + uri[len("radio:///") :]
    return uri


def parse_swarm_config(data: object) -> SwarmConfig:
    """Build a `SwarmConfig` from already parsed YAML/JSON data"""
    doc = cast(dict[str, Any], data if isinstance(data, dict) else {})
    if not isinstance(doc.get("units"), list):
        raise ValueError("Swarm file must contain a 'units' list")

    units = []
    for i, entry in enumerate(doc["units"], start=1):
        if not isinstance(entry, dict) or "uri" not in entry:
            raise ValueError(f"Unit {i} has no 'uri'")
        units.append(Unit(uri=normalize_uri(str(entry["uri"])), name=entry.get("name")))

    uris = [u.uri for u in units]
    duplicates = sorted({u for u in uris if uris.count(u) > 1})
    if duplicates:
        raise ValueError(f"Duplicate URIs in swarm file: {', '.join(duplicates)}")

    extra = {k: v for k, v in doc.items() if k not in ("name", "units")}
    return SwarmConfig(units=units, name=doc.get("name"), extra=extra)


def load_swarm_config(path: str | Path) -> SwarmConfig:
    """Read a swarm file. Requires PyYAML."""
    try:
        import yaml
    except ImportError as e:
        raise ImportError(
            "Reading swarm files requires PyYAML: pip install pyyaml"
        ) from e

    with open(path) as f:
        return parse_swarm_config(yaml.safe_load(f))
