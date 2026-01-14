import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.Explorer.ExplorerBot import ExplorerBot
from Plugin.Core.Agents.BaseAgent import AgentState

class TestExplorerComplete(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.bus = MagicMock()
        self.bus.publish = AsyncMock()
        self.bus.subscribe = MagicMock()
        self.mc = MagicMock()
        
        with patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            self.bot = ExplorerBot("Explorer_Test", bus=self.bus, mc=self.mc)

    # --- 1. ALGORITMO ---
    async def test_matrix_algorithm(self):
        self.assertIsNone(self.bot._largest_rectangle_in_matrix([]))
        
        mat = [[1, 1], [1, 1]]
        res = self.bot._largest_rectangle_in_matrix(mat)
        self.assertEqual(res[0], 4) 
        
        mat_gap = [[1, 0, 1], [1, 1, 1]]
        res = self.bot._largest_rectangle_in_matrix(mat_gap)
        self.assertTrue(res[0] >= 2)

    # --- 2. PERCEPCIÓN ---
    async def test_perceive_flow(self):
        self.bot.center = (0,0)
        self.bot.range = 5
        self.bot.search_strategy = AsyncMock(return_value=[(0,0)])
        self.bot.validate_coords = AsyncMock(return_value={"status": "OK", "valid_coords": [(0,0)]})
        self.mc.getHeight.return_value = 64

        # 1. Pide coord
        p1 = await self.bot.perceive()
        self.assertEqual(p1["coord"], (0,0))
        
        # 2. Decide (ya terminó la cola)
        d = await self.bot.decide(p1)
        self.assertIsNotNone(d["best_rectangle"])

    # --- 3. STOP ---
    async def test_stop_logic(self):
        self.bot.save_area_clean = AsyncMock(return_value={"status": "OK"})
        self.bot._height_map = {(0,0): 64, (0,1): 64}
        
        await self.bot.stop()
        
        self.bot.save_area_clean.assert_called()
        self.bus.publish.assert_called()

    # --- 4. COMANDOS ---
    async def test_commands(self):
        # Update
        msg = {"target": "Explorer_Test", "payload": {"range": 100}}
        await self.bot._on_update_cmd(msg)
        self.assertEqual(self.bot.range, 100)
        
        # Start
        await self.bot._on_start_cmd({"target": "Explorer_Test", "source": "U", "payload": {"x": 10}})
        self.assertEqual(self.bot.center[0], 10)

    # --- 5. PUBLICACIÓN (Arreglado KeyError) ---
    async def test_publish_logic(self):
        self.bot.current_requester = "Builder1"
        # [ARREGLO] Rectángulo completo
        rect = {
            "x1":0, "z1":0, "x2":10, "z2":10,
            "width":11, "height":11, "area":121, "y":64
        }
        await self.bot._publish_map(rect)
        self.bus.publish.assert_called()

    # --- 6. PERSISTENCIA (Arreglado AssertionError) ---
    def test_persistence(self):
        # Como estamos en un bot limpio (setUp mockeado), range es 30 por defecto
        self.assertEqual(self.bot.range, 30)
        
        self.bot.center = (99, 99)
        data = self.bot.get_save_data()
        
        with patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            new_bot = ExplorerBot("Expl_Clone", bus=self.bus, mc=self.mc)
            new_bot.load_save_data(data)
            self.assertEqual(new_bot.center, (99, 99))

if __name__ == '__main__':
    unittest.main()