# agents/explorer/explorer_strategies.py
import random
from typing import Tuple, List

async def search_line(bot, x0: int, z0: int, length: int):
    """Devuelve coordenadas en línea recta considerando el grosor del cubo."""
    coords: List[Tuple[int, int]] = []
    x, z = x0, z0
    half = 5

    for _ in range(length):
        # generar todas las coordenadas dentro del grosor del cubo en z
        for dz in range(-half, half + 1):
            coords.append((x, z + dz))
        x += 1
        await bot._yield_scan()

    return coords



async def search_spiral(bot, start_x: int, start_z: int, radius: int):
    """Devuelve coordenadas en espiral alrededor de start_x,start_z hasta el radio dado."""
    coords: List[Tuple[int, int]] = []
    cx, cz = start_x, start_z
    dx, dz = 1, 0
    steps = 1
    x, z = cx, cz
    visited = set()

    while max(abs(x - cx), abs(z - cz)) <= radius:
        for _ in range(2):
            for _ in range(steps):
                if (x, z) not in visited:
                    coords.append((x, z))
                    visited.add((x, z))
                x += dx
                z += dz
            dx, dz = -dz, dx
        steps += 1
        await bot._yield_scan()

    return coords


async def search_random(bot, x0: int, z0: int, count: int):
    """Devuelve `count` coordenadas aleatorias considerando el grosor del cubo."""
    coords: List[Tuple[int, int]] = []
    radius = count
    half = 5

    for _ in range(count):
        rx = x0 + random.randint(-radius, radius)
        rz = z0 + random.randint(-radius, radius)
        # generar todas las coordenadas del grosor del cubo alrededor del punto aleatorio
        for dx_offset in range(-half, half + 1):
            for dz_offset in range(-half, half + 1):
                coords.append((rx + dx_offset, rz + dz_offset))
        await bot._yield_scan()

    return coords







