import asyncio
import sys
import os
from Plugin.Core.Agents.Explorer.ExplorerBot import ExplorerBot
from mcpi.event import ChatEvent
from mcpi.minecraft import Minecraft
from Plugin.Core.Logger.logging_config import get_logger

# Ruta absoluta del directorio raíz del proyecto
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plugin"))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

MCPI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcpi"))
if MCPI_PATH not in sys.path:
    sys.path.insert(0, MCPI_PATH)
    
# ---------------------------------------------------------
# Configuración de logger
# ---------------------------------------------------------
logger = get_logger(__name__)


# -----------------------------------------------------
# Conectar con Minecraft
# -----------------------------------------------------
mc = Minecraft.create("localhost", 4711)

# ---------------------------------------------------------
# Función principal de arranque
# ---------------------------------------------------------
async def main():
    logger.info("Iniciando sistema de bots...")

    # -----------------------------------------------------
    # Inicializar ExplorerBot
    # -----------------------------------------------------
    explorer_bot = ExplorerBot(agent_id="ExplorerBot", bus=None)  # si tienes MessageBus, pásalo
    # Opcional: configurar parámetros iniciales
    await explorer_bot.update({"x": 100, "z": 100, "range": 30})

    logger.info("Bots registrados y listos para recibir comandos de chat.")

    # -----------------------------------------------------
    # Simular recepción de chat
    # -----------------------------------------------------
    async def simulate_chat():
        """Simula mensajes de chat para probar commandos"""
        await asyncio.sleep(1)
        ChatEvent.Post(entityId=1, message="/explorer start x=100 z=100 range=10 cube=3")
        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="/explorer pause")
        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="/explorer resume")
        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="/explorer stop")

    # -----------------------------------------------------
    # Iniciar bot y simulador de chat
    # -----------------------------------------------------
    await asyncio.gather(
        explorer_bot.start(),
        simulate_chat()
    )

# ---------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Programa detenido por el usuario")
        sys.exit(0)
