import asyncio
import random
from mcpi.minecraft import Minecraft
from mcpi import block

CUBE_SIZE = 5

class ExplorerBot:
    def __init__(self, mc, center=(0,0)):
        self.mc = mc
        self.center = center  # centro fijo de la espiral (0,0)
        self.occupied = set()  # bloques ya usados
        self.last_pos = (0,0)  # última posición del cubo

    # ------------------------------
    # Verifica si un área 3x3 es plana y libre
    # ------------------------------
    async def is_flat_area(self, x0, z0):
        half = CUBE_SIZE // 2
        h0 = self.mc.getHeight(x0, z0)
        for dx in range(-half, half + 1):
            for dz in range(-half, half + 1):
                x, z = x0 + dx, z0 + dz
                if (x, z) in self.occupied:
                    return False
                if self.mc.getHeight(x, z) != h0:
                    return False
        return True

    async def find_flat_area(self, x, z):
        if await self.is_flat_area(x, z):
            h = self.mc.getHeight(x, z)
            return x, z, CUBE_SIZE, h
        return None

    # ------------------------------
    # Búsqueda lineal
    # ------------------------------
    async def search_line(self, x0, z0):
        x, z = x0, z0
        while True:
            print(f"Buscando en posición: ({x}, {z})")
            area = await self.find_flat_area(x, z)
            if area:
                return area
            x += 1

    # ------------------------------
    # Búsqueda espiral
    # ------------------------------
    async def search_spiral(self, start_x, start_z):
        cx, cz = self.center  # centro fijo de la espiral
        dx, dz = 1, 0
        steps = 1
        x, z = start_x, start_z
        visited = set()

        while True:
            for _ in range(2):
                for _ in range(steps):
                    if (x, z) not in visited:
                        print(f"Buscando en posición: ({x}, {z})")
                        area = await self.find_flat_area(x, z)
                        if area:
                            return area
                        visited.add((x, z))
                    x += dx
                    z += dz
                dx, dz = -dz, dx
            steps += 1

    # ------------------------------
    # Búsqueda aleatoria
    # ------------------------------
    async def search_random(self, x0, z0, radius=50):
        while True:
            rx = x0 + random.randint(-radius, radius)
            rz = z0 + random.randint(-radius, radius)
            print(f"Buscando en posición aleatoria: ({rx}, {rz})")
            area = await self.find_flat_area(rx, rz)
            if area:
                return area

    # ------------------------------
    # Exploración infinita
    # ------------------------------
    async def explore_forever(self, mode="line"):
        while True:
            # iniciar desde la última posición del cubo
            x0, z0 = self.last_pos

            if mode == "line":
                x, z, size, h = await self.search_line(x0, z0)
            elif mode == "spiral":
                x, z, size, h = await self.search_spiral(x0, z0)
            elif mode == "random":
                x, z, size, h = await self.search_random(x0, z0)
            else:
                raise ValueError("Modo inválido: line, spiral o random")

            print(f"Área plana encontrada: Centro=({x},{z}) Tamaño={size}x{size} Altura={h}")

            # Teletransportar al jugador
            #self.mc.player.setPos(x, h, z)

            # Construir cubo y marcar bloques ocupados
            await self.build_glass_cube(x, h, z)

            # actualizar la última posición
            self.last_pos = (x, z)

            await asyncio.sleep(1)

    # ------------------------------
    # Construir cubo de cristal y marcar bloques
    # ------------------------------
    async def build_glass_cube(self, x, y, z):
        half = CUBE_SIZE // 2
        print(f"Construyendo cubo de cristal en ({x},{z})...")
        for dx in range(-half, half + 1):
            for dy in range(CUBE_SIZE):
                for dz in range(-half, half + 1):
                    bx, by, bz = x + dx, y + dy, z + dz
                    self.mc.setBlock(bx, by, bz, block.GLASS.id)
                    if dy == 0:
                        self.occupied.add((bx, bz))  # marcar solo la base

async def main():
    mc = Minecraft.create("localhost", 4711)
    bot = ExplorerBot(mc, center=(0, 0))

    print("Iniciando exploración infinita desde última posición...")
    await bot.explore_forever(mode="line")  # modos: spiral, line, random

asyncio.run(main())
