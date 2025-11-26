import asyncio
import sys
import os

from Plugin.Core.Agents.Explorer.ExplorerBot import ExplorerBot
from Plugin.Core.Logger.logging_config import get_logger
from mcpi.minecraft import Minecraft
from mcpi.event import ChatEvent, register_bot, start_chat_listener 


# --------------------------
# Rutas del proyecto
# --------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plugin"))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

MCPI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcpi"))
if MCPI_PATH not in sys.path:
    sys.path.insert(0, MCPI_PATH)


# --------------------------
# Logger
# --------------------------
logger = get_logger(__name__)


# --------------------------
# Conectar con Minecraft
# --------------------------
mc = Minecraft.create("localhost", 4711)


# --------------------------
# Función principal
# --------------------------
async def main():
    logger.info("Iniciando sistema de bots...")

    # -----------------------------------------------------
    # Crear instancias reales de bots
    # -----------------------------------------------------
    explorer_bot = ExplorerBot(agent_id="ExplorerBot", bus=None, terrain_api=None)
    explorer_bot.terrain.mc = mc  # conectar MCPI al bot

    # Si tienes otros bots, créalos aquí:
    # builder_bot = BuilderBot(...)
    # miner_bot = MinerBot(...)

    # -----------------------------------------------------
    # Registrar bots en ChatEvent (MUY IMPORTANTE)
    # -----------------------------------------------------
    register_bot(explorer_bot)
    # register_bot(builder_bot)
    # register_bot(miner_bot)

    logger.info("Bots registrados correctamente.")

    start_chat_listener(mc)
    # -----------------------------------------------------
    # Simulador de chat
    # -----------------------------------------------------
    async def simulate_chat():
        await asyncio.sleep(1)
        ChatEvent.Post(entityId=1, message="explorer start x=100 z=100 range=1000 cube=3")

        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="explorer pause")

        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="explorer resume")

        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="explorer stop")

    # -----------------------------------------------------
    # Lanzar bot + simulador
    # -----------------------------------------------------
    #ChatEvent.Post(entityId=1, message="explorer start x=-180 z=70 range=30 cube=5")
    #ChatEvent.Post(entityId=2, message="explorer start x=180 z=-70 range=20 cube=5")
    while True:
        await asyncio.sleep(1)


# --------------------------
# Entry point
# --------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Programa detenido por el usuario")
        sys.exit(0)
