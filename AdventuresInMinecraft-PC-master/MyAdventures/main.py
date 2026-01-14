import asyncio
import sys
import os

from Plugin.Core.Agents.Factory.AgentFactory import AgentFactory

from Plugin.Core.Logger.logging_config import get_console_logger
from mcpi.minecraft import Minecraft
from Plugin.Core.Listener.Chatlistener import register_bot, start_chat_listener 
from mcpi.event import ChatEvent
from Plugin.Core.Bus.Bus import MessageBus



# Rutas del proyecto

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plugin"))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

MCPI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcpi"))
if MCPI_PATH not in sys.path:
    sys.path.insert(0, MCPI_PATH)



# Logger

logger = get_console_logger(__name__)



# Conectar con Minecraft

mc = Minecraft.create("localhost", 4711)



# Función principal

async def main():
    logger.info("Iniciando sistema de bots...")

    # Crear instancias reales de bots

    shared_bus = MessageBus()
    worldstate_bot = AgentFactory.create("worldstate", "WorldstateBot", shared_bus)
    register_bot(worldstate_bot)

    NUM_SQUADS = 2
    
    for i in range(NUM_SQUADS):
        suffix = f"_{i+1}" # Genera "_1", "_2"
        
        # Nombres únicos para este equipo
        b_name = f"Builder{suffix}"
        m_name = f"Miner{suffix}"
        e_name = f"Explorer{suffix}"

        logger.info(f"--- Creando Escuadrón {suffix}: {b_name} + {m_name} + {e_name} ---")

        # A. Crear bots con la Factory
        builder = AgentFactory.create("builder", b_name, shared_bus, mc)
        miner   = AgentFactory.create("miner",   m_name, shared_bus, mc)
        explorer= AgentFactory.create("explorer", e_name, shared_bus, mc)

        # B. ¡AQUÍ ESTÁ LA CLAVE! Asignamos el equipo al Builder
        # Le decimos: "Builder_1, tu minero es Miner_1"
        builder.set_squad(m_name, e_name)

        # C. Registramos a todos para que escuchen el chat
        register_bot(builder)
        register_bot(miner)
        register_bot(explorer)

    logger.info("Bots registrados correctamente.")

    start_chat_listener(mc)

    # Simulador de chat

    async def simulate_chat():
        await asyncio.sleep(1)
        ChatEvent.Post(entityId=1, message="explorer start x=100 z=100 range=1000 cube=3")

        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="explorer pause")

        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="explorer resume")

        await asyncio.sleep(2)
        ChatEvent.Post(entityId=1, message="explorer stop")


    # Lanzar bot + simulador

    #ChatEvent.Post(entityId=1, message="explorer start x=-180 z=70 range=5 cube=5")
    #ChatEvent.Post(entityId=2, message="builder start")
    while True:
        await asyncio.sleep(1)



# Entry point

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Programa detenido por el usuario")
        sys.exit(0)
