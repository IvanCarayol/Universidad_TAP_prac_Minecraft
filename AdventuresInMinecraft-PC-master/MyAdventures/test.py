import asyncio
from mcpi.minecraft import Minecraft

class ExplorerBot:
    def __init__(self, mc, center):
        self.mc = mc
        self.center = center  # referencia independiente del jugador

    async def perceive(self):
        x0, z0 = self.center
        flat = await self.flatsurface(x0, z0)

        # Si no es plano, buscar superficie plana hacia +x
        while not flat:
            x0 += 1
            flat = await self.flatsurface(x0, z0)

        height = self.mc.getHeight(x0, z0)
        return {"height": height, "x": x0, "z": z0, "flat_surface": bool(flat)}

    async def flatsurface(self, x0, z0):
        """
        Verifica un área 3x3 alrededor de (x0, z0) para ver si todos los bloques
        tienen la misma altura.
        """
        center_height = self.mc.getHeight(x0, z0)
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                if self.mc.getHeight(x0 + dx, z0 + dz) != center_height:
                    return 0  # No es plano
        return 1  # Es plano

async def main():
    # Conectar con Minecraft real
    mc = Minecraft.create("localhost", 4711)

    # Crear el ExplorerBot
    bot = ExplorerBot(
        mc=mc,
        center=(100, 100)
    )

    # Ejecutar percepción del mundo
    print(">>> Ejecutando ExplorerBot en Minecraft Real...")
    percept = await bot.perceive()
    print("PERCEPT:", percept)
    print("hecho")

asyncio.run(main())