import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os
from collections import namedtuple

# Ajustamos la ruta para que Python encuentre tus carpetas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.Factory.AgentFactory import AgentFactory
from Plugin.Core.Bus.Bus import MessageBus
from Plugin.Core.Commands.command_system import CommandSystem

# [CORRECCIÓN 1]: Importamos el Chatlistener desde su carpeta real (Core/Listener)
from Plugin.Core.Listener.Chatlistener import _dispatch, register_bot

# Evento falso para simular el chat de Minecraft
ChatEvent = namedtuple("ChatEvent", ["entityId", "message"])

class TestInfrastructure(unittest.IsolatedAsyncioTestCase):

    # ==========================================
    # 1. TEST DE LA FÁBRICA DE AGENTES
    # ==========================================
    def test_agent_factory(self):
        bus = MagicMock()
        
        # Comprobamos que crea correctamente cada tipo de robot
        miner = AgentFactory.create("miner", "Miner1", bus)
        self.assertEqual(miner.agent_id, "Miner1")
        
        explorer = AgentFactory.create("explorer", "Expl1", bus)
        self.assertEqual(explorer.agent_id, "Expl1")

        builder = AgentFactory.create("builder", "Build1", bus)
        self.assertEqual(builder.agent_id, "Build1")

        ws = AgentFactory.create("worldstate", "WS1", bus)
        self.assertEqual(ws.agent_id, "WS1")

        # Comprobamos que falla si pedimos un robot inventado
        with self.assertRaises(ValueError):
            AgentFactory.create("robot_cocina", "Chef1", bus)

    # ==========================================
    # 2. TEST DEL BUS DE MENSAJES
    # ==========================================
    async def test_message_bus(self):
        bus = MessageBus()
        callback = AsyncMock()

        # Suscribirse
        bus.subscribe("test.topic", callback)
        self.assertIn("test.topic", bus.subscribers)

        # Publicar (el callback debe ejecutarse)
        await bus.publish({"type": "test.topic", "data": 1})
        callback.assert_called_once()

        # Desuscribirse
        bus.unsubscribe("test.topic", callback)
        self.assertNotIn("test.topic", bus.subscribers)

        # Intentar borrar algo que no existe (no debería fallar)
        try:
            bus.unsubscribe("test.topic", callback) 
        except Exception:
            self.fail("El Bus falló al intentar borrar una suscripción que no existía")

    # ==========================================
    # 3. TEST DEL SISTEMA DE COMANDOS
    # ==========================================
    async def test_command_system_complex(self):
        sys = CommandSystem()
        handler = AsyncMock(return_value="OK")
        
        # [CORRECCIÓN 2]: Añadimos target_bot="miner". 
        # Si no ponemos esto, el sistema no sabe a quién mandar la orden y falla.
        sys.on("miner set", "topic.miner", target_bot="miner")(handler)

        bot_mock = MagicMock()
        # El sistema busca "miner" dentro de "MinerBot", así que lo encontrará
        bots = {"MinerBot": bot_mock}

        # CASO 1: Probar parámetros complejos
        await sys.execute("miner set range=50 verbose", 1, bots)
        
        # Verificamos que los parámetros llegaron bien
        args = handler.call_args[1]
        self.assertEqual(args["params"]["range"], 50)
        self.assertEqual(args["params"]["verbose"], True)

        # CASO 2: Probar comando simple
        await sys.execute("miner set", 1, bots)
        handler.assert_called()

        # CASO 3: Comando desconocido (devuelve None)
        res = await sys.execute("cocinar pizza", 1, bots)
        self.assertIsNone(res)

    # ==========================================
    # 4. TEST DEL ESCUCHA DE CHAT
    # ==========================================
    async def test_chat_dispatch(self):
        evt = ChatEvent(entityId=99, message="miner start")
        
        # [CORRECCIÓN 3]: Usamos la ruta completa correcta para el 'patch'.
        # Antes fallaba porque buscaba en 'Plugin.Chatlistener' en vez de 'Plugin.Core.Listener...'
        ruta_registro = "Plugin.Core.Listener.Chatlistener.BOTS_REGISTRY"
        ruta_dispatch = "Plugin.Core.Commands.commands.dispatch_command"
        
        with patch(ruta_registro, {"MinerBot": MagicMock()}), \
             patch(ruta_dispatch, new_callable=AsyncMock) as mock_cmd:
            
            # Ejecutamos la función interna
            await _dispatch(evt, "key_dummy")
            
            # Verificamos que se llamó al comando correcto
            mock_cmd.assert_called_once()
            self.assertEqual(mock_cmd.call_args[0][1], "miner start")

    def test_register_bot(self):
        bot = MagicMock()
        bot.agent_id = "SuperMinerBot"
        
        # Usamos la misma ruta corregida
        ruta_registro = "Plugin.Core.Listener.Chatlistener.BOTS_REGISTRY"
        
        with patch(ruta_registro, {}) as registry:
            register_bot(bot)
            # Debe haber guardado el bot en minúsculas y sin la palabra 'bot'
            self.assertIn("superminer", registry)

if __name__ == '__main__':
    unittest.main()