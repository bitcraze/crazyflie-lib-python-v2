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
Example demonstrating TOC (Table of Contents) caching with the Crazyflie.

TOC caching significantly speeds up connection times by storing the parameter
and log variable tables locally, avoiding the need to download them on every
connection.

This example demonstrates three types of caches by connecting multiple times
and measuring the performance improvement:

1. NoTocCache - No caching (downloads TOCs every time, slowest)
2. InMemoryTocCache - Cache in RAM (fast for multiple connections in same script)
3. FileTocCache - Cache to disk (fast and persistent across script runs)

Example usage:
    python toc_cache.py                              # No cache (default URI)
    python toc_cache.py --cache none                 # No cache
    python toc_cache.py --cache memory               # In-memory cache
    python toc_cache.py --cache file                 # File cache
    python toc_cache.py --connections 5              # Connect 5 times
    python toc_cache.py --uri radio://0/80/2M/E7E7E7E7E7  # Custom URI
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Union

import tyro

from cflib2 import Crazyflie, LinkContext, NoTocCache, InMemoryTocCache, FileTocCache


@dataclass
class Args:
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    """Crazyflie URI"""
    cache: Literal["none", "memory", "file"] = "none"
    """Type of TOC cache to use"""
    cache_dir: str | None = None
    """Directory for file cache (uses cache/ in project root if unset)"""
    connections: int = 3
    """Number of connection attempts to perform"""


async def main() -> int:
    args = tyro.cli(Args)

    # Create the appropriate cache based on user choice
    cache: Union[NoTocCache, InMemoryTocCache, FileTocCache]

    if args.cache == "none":
        cache = NoTocCache()
        print("Using NoTocCache (no caching)")
        print("Note: Every connection will download TOCs from scratch\n")
    elif args.cache == "memory":
        cache = InMemoryTocCache()
        print("Using InMemoryTocCache (RAM cache)")
        print(f"  Initial cache size: {cache.size()} TOCs")
        print("Note: Cache speeds up connections in THIS script, lost on exit\n")
    else:  # file
        # Use specified directory or create a temp directory
        if args.cache_dir:
            cache_dir = args.cache_dir
        else:
            cache_dir = str(Path(__file__).parent.parent / "cache")

        cache = FileTocCache(cache_dir)
        print(f"Using FileTocCache (persistent cache)")
        print(f"  Cache directory: {cache.get_cache_dir()}")
        print("Note: Cache persists across script runs\n")

    print(f"Connecting to {args.uri}...")
    # Connect multiple times to demonstrate cache performance
    connection_times: list[float] = []
    context = LinkContext()

    for attempt in range(1, args.connections + 1):
        print(f"Connection {attempt}/{args.connections}: ", end="", flush=True)

        start_time = time.time()

        try:
            cf = await Crazyflie.connect_from_uri(context, args.uri, toc_cache=cache)
            connect_time = time.time() - start_time
            connection_times.append(connect_time)

            print(f"{connect_time:.3f}s")

            await cf.disconnect()

            # Brief pause between connections
            if attempt < args.connections:
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"FAILED - {e}")
            return 1

    # Print summary
    print(f"\nConnection times: {', '.join(f'{t:.3f}s' for t in connection_times)}")

    if isinstance(cache, FileTocCache):
        print(f"Cache: {cache.get_cache_dir()}")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
