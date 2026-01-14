import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.Builder.BuilderBot import BuilderBot
from Plugin.Core.Agents.Miner.MinerBot import MinerBot
from Plugin.Core.Agents.BaseAgent import AgentState

class TestBotControls(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.fake_bus = MagicMock()
        self.fake_bus.publish = AsyncMock()
        self.fake_bus.subscribe = MagicMock()
        self.fake_mc = MagicMock()

    async def test_builder_controls(self):
        bot = BuilderBot("Builder_Control_Test", bus=self.fake_bus, mc=self.fake_mc)
        
        # [CORRECCIÓN IMPORTANTE] 
        # Forzamos que el bot "crea" que está corriendo.
        # Si no hacemos esto, al hacer Pause guarda "IDLE", y al hacer Resume vuelve a "IDLE".
        bot._state = AgentState.RUNNING
        
        # 1. Test Pause
        await bot._on_control({"target": "Builder_Control_Test", "type": "command.builder.pause.v1"})
        self.assertEqual(bot.state, AgentState.PAUSED)

        # 2. Test Resume (Debe volver a RUNNING)
        await bot._on_control({"target": "Builder_Control_Test", "type": "command.builder.resume.v1"})
        self.assertEqual(bot.state, AgentState.RUNNING)

        # 3. Test Status (Solo comprueba que no explota)
        await bot._on_control({"target": "Builder_Control_Test", "type": "command.builder.status.v1"})
        
        # 4. Test Stop
        await bot._on_control({"target": "Builder_Control_Test", "type": "command.builder.stop.v1"})
        self.assertEqual(bot.state, AgentState.STOPPED)

    async def test_miner_controls(self):
        bot = MinerBot("Miner_Control_Test", bus=self.fake_bus, mc=self.fake_mc)
        bot._state = AgentState.RUNNING
        
        # Preparamos el bot para simular que tiene trabajo pendiente
        bot.inventory["stone"] = 5
        # Mockeamos las funciones de reporte para que devuelvan éxito
        bot.report_materials_to_worldstate = AsyncMock(return_value=True)
        bot.release_assigned_area = AsyncMock(return_value=True)

        # Test Stop (Debe intentar reportar materiales y liberar zona)
        await bot._on_control({"target": "Miner_Control_Test", "type": "command.miner.stop.v1"})
        
        self.assertEqual(bot.state, AgentState.STOPPED)
        # Verificamos que intentó reportar antes de apagarse
        bot.report_materials_to_worldstate.assert_called()

if __name__ == '__main__':
    unittest.main()