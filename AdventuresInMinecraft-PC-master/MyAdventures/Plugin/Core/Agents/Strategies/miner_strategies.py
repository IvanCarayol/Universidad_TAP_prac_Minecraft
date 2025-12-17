# agents/Strategies/miner_strategies.py
import asyncio
from typing import Callable, Tuple, Dict

# ---------------------------
# Grid Strategy (AREA-BASED)
# ---------------------------
async def grid_strategy(
    area: Dict[str, int],
    step: int = 1,
    y: int = 64
) -> Callable[[], Tuple[int, int, int]]:
    """
    Recorre el área asignada en forma de grid.
    area = {x1, z1, x2, z2, width, height}
    """

    x1 = area["x1"]
    z1 = area["z1"]
    width = area["width"]
    depth = area["height"]

    i = 0
    total = width * depth

    async def next_target():
        nonlocal i

        if i >= total:
            i = 0  # volver a empezar si se termina el área

        xi = i % width
        zi = (i // width) % depth

        x = x1 + xi * step
        z = z1 + zi * step

        i += 1
        await asyncio.sleep(0)
        return (x, y, z)

    return next_target


# ---------------------------
# Vertical Strategy (AREA-BASED)
# ---------------------------
async def vertical_strategy(
    area: Dict[str, int],
    start_y: int = 64,
    step: int = 1
) -> Callable[[], Tuple[int, int, int]]:
    """
    Mina verticalmente dentro del área
    """

    x = area["x1"]
    z = area["z1"]
    y = start_y

    async def next_target():
        nonlocal y
        t = (x, y, z)
        y -= step
        await asyncio.sleep(0)
        return t

    return next_target


# ---------------------------
# Vein Strategy (AREA-BASED)
# ---------------------------
async def vein_strategy(
    area: Dict[str, int],
    radius: int = 3,
    y: int = 64
) -> Callable[[], Tuple[int, int, int]]:
    """
    Explora alrededor del centro del área
    """

    cx = (area["x1"] + area["x2"]) // 2
    cz = (area["z1"] + area["z2"]) // 2
    offset = 0
    diameter = radius * 2 + 1

    async def next_target():
        nonlocal offset

        x = cx + (offset % diameter) - radius
        z = cz + ((offset // diameter) % diameter) - radius

        offset += 1
        await asyncio.sleep(0)
        return (x, y, z)

    return next_target
