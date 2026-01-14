import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
import sys
import os
from collections import defaultdict

# Ajuste de ruta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.Miner.MinerBot import MinerBot
from Plugin.Core.Agents.BaseAgent import AgentState

class TestMinerComprehensive(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Limpieza
        save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Plugin/Saves/Miner_Test.json'))
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except: pass

        self.bus = MagicMock()
        self.bus.publish = AsyncMock()
        self.bus.subscribe = MagicMock()
        self.bus.unsubscribe = MagicMock()
        
        self.mc = MagicMock()
        self.mc.getHeight.return_value = 60
        self.mc.getBlock.return_value = 1 
        self.mc.player.getTilePos.return_value = MagicMock(x=0, y=64, z=0)

        with patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            self.bot = MinerBot("Miner_Test", bus=self.bus, mc=self.mc)

    # --- 1. GESTIÓN DE BOM ---
    async def test_bom_handling(self):
        payload_ok = {"bom": [{"material": "stone", "qty": 10}]}
        await self.bot._on_materials_request({"target": "Miner_Test", "source": "Builder1", "payload": payload_ok})
        self.assertIsNotNone(self.bot._current_bom)
        self.assertTrue(self.bot._bom_event.is_set())
        
        self.bot._current_bom = None
        payload_list = [{"material": "dirt", "qty": 5}]
        await self.bot._on_materials_request({"target": "Miner_Test", "payload": payload_list})
        self.assertEqual(self.bot._current_bom[0]["material"], "dirt")

        self.bot._current_bom = None
        payload_bad = [{"cosarara": "si"}]
        await self.bot._on_materials_request({"target": "Miner_Test", "payload": {"bom": payload_bad}})
        self.assertIsNone(self.bot._current_bom)

    # --- 2. ESTRATEGIAS ---
    async def test_strategy_switching(self):
        # [CORRECCIÓN] Usamos 'height' en lugar de 'depth' porque tu estrategia lo espera así
        area = {"x1":0, "z1":0, "x2":10, "z2":10, "y":64, "width":11, "height":11}
        
        self.bot._strategy_name = "grid"
        strat = await self.bot._build_strategy(area)
        self.assertTrue(callable(strat))
        
        await self.bot._on_update_cmd({"target": "Miner_Test", "payload": {"strategy": "vertical"}})
        self.assertEqual(self.bot._strategy_name, "vertical")
        strat = await self.bot._build_strategy(area)
        self.assertTrue(callable(strat))

        self.bot._strategy_name = "vein"
        strat = await self.bot._build_strategy(area)
        self.assertTrue(callable(strat))

    # --- 3. CICLO DE MINADO ---
    async def test_perform_mining_step(self):
        self.bot._current_bom = [{"material": "cobblestone", "qty": 64}]
        self.bot._state = AgentState.RUNNING 
        
        self.bot.request_single_area = AsyncMock(return_value=True)
        self.bot.assigned_area = {"x1":0, "z1":0, "x2":10, "z2":10, "width":11, "depth":11, "y":64, "z2":10}
        
        mock_strategy = AsyncMock(return_value=(5, 64, 5))
        self.bot._build_strategy = AsyncMock(return_value=mock_strategy)
        
        self.mc.getHeight.return_value = 60
        self.mc.getBlock.return_value = 1
        
        await self.bot._perform_mining_step()
        
        self.mc.setBlock.assert_called_with(5, 59, 5, 0)
        self.assertEqual(self.bot.inventory["cobblestone"], 1)

    async def test_mining_simulation_logic(self):
        self.bot._current_bom = [
            {"material": "diamond", "qty": 5},
            {"material": "stone", "qty": 64}
        ]
        
        mat = self.bot._simulate_material_from_target((0,0,0))
        self.assertEqual(mat, "diamond")
        
        self.bot.inventory["diamond"] = 5
        mat = self.bot._simulate_material_from_target((0,0,0))
        self.assertEqual(mat, "stone")

    # --- 4. COMUNICACIÓN WORLDSTATE ---
    async def test_request_area_flow(self):
        callbacks = {}
        def side_effect_subscribe(topic, cb):
            callbacks[topic] = cb
        self.bus.subscribe.side_effect = side_effect_subscribe

        task = asyncio.create_task(self.bot.request_single_area({"width": 16}))
        await asyncio.sleep(0.01)
        
        if "worldstate.response" in callbacks:
            fake_response = {
                "type": "worldstate.response",
                "target": "Miner_Test",
                "payload": {"status": "OK", "rect": {"x1": 100}}
            }
            await callbacks["worldstate.response"](fake_response)
        
        result = await task
        self.assertTrue(result)
        self.assertEqual(self.bot.assigned_area["x1"], 100)

    async def test_report_materials_flow(self):
        self.bot.inventory = {"gold": 10}
        
        with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = {"status": "OK"}
            success = await self.bot.report_materials_to_worldstate()
            self.assertTrue(success)
            
            mock_wait.side_effect = asyncio.TimeoutError()
            success = await self.bot.report_materials_to_worldstate()
            self.assertFalse(success)

    # --- 5. DECISIONES ---
    async def test_decide_logic(self):
        d = await self.bot.decide({"bom": None})
        self.assertEqual(d["action"], "wait_for_bom")
        
        self.bot.inventory = {}
        d = await self.bot.decide({"bom": [{"material": "stone", "qty": 10}]})
        self.assertEqual(d["action"], "mine")
        
        self.bot.inventory = {"stone": 20}
        self.bot.current_requester = "Builder1"
        d = await self.bot.decide({"bom": [{"material": "stone", "qty": 10}]})
        self.assertEqual(d["action"], "report_complete")

    async def test_stop_sequence(self):
        self.bot.inventory = {"iron": 1}
        self.bot.assigned_area = {"x1": 0}
        
        self.bot.report_materials_to_worldstate = AsyncMock(return_value=True)
        self.bot.release_assigned_area = AsyncMock(return_value=True)
        self.bot._publish_inventory = AsyncMock()
        
        await self.bot.stop()
        
        self.bot.report_materials_to_worldstate.assert_called()
        self.bot.release_assigned_area.assert_called()

    # --- 6. PERSISTENCIA ---
    def test_save_load(self):
        self.bot.inventory = defaultdict(int, {"coal": 50})
        self.bot._strategy_name = "vein"
        
        data = self.bot.get_save_data()
        
        with patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            new_bot = MinerBot("Miner_Clone", bus=self.bus, mc=self.mc)
            new_bot.load_save_data(data)
            
            self.assertEqual(new_bot.inventory["coal"], 50)
            self.assertEqual(new_bot._strategy_name, "vein")

if __name__ == '__main__':
    unittest.main()