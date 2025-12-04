# agents/Strategies/miner_strategies.py
import asyncio
from typing import Callable, Tuple

# ---------------------------
# Vertical Strategy
# ---------------------------
async def vertical_strategy(base_x=0, base_z=0, start_y=64, step=1) -> Callable[[], Tuple[int,int,int]]:
    """
    Devuelve un generador async de coordenadas verticales
    """
    y = start_y

    async def next_target():
        nonlocal y
        t = (base_x, y, base_z)
        y -= step
        await asyncio.sleep(0)  # yield control
        return t

    return next_target


# ---------------------------
# Grid Strategy
# ---------------------------
async def grid_strategy(x0=0, z0=0, width=5, depth=5, step=1, y=64) -> Callable[[], Tuple[int,int,int]]:
    """
    Devuelve un generador async de coordenadas en cuadrícula
    """
    i = 0

    async def next_target():
        nonlocal i
        xi = i % width
        zi = (i // width) % depth
        x = x0 + xi * step
        z = z0 + zi * step
        i += 1
        await asyncio.sleep(0)
        return (x, y, z)

    return next_target


# ---------------------------
# Vein Strategy
# ---------------------------
async def vein_strategy(seed_x=0, seed_z=0, radius=3, y=64) -> Callable[[], Tuple[int,int,int]]:
    """
    Devuelve un generador async de coordenadas alrededor de un punto semilla
    """
    offset = 0

    async def next_target():
        nonlocal offset
        r = offset
        x = seed_x + (r % (radius * 2)) - radius
        z = seed_z + ((r // (radius * 2)) % (radius * 2)) - radius
        offset += 1
        await asyncio.sleep(0)
        return (x, y, z)

    return next_target
