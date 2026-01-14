import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Ajuste de ruta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.Builder.BuilderBot import BuilderBot
from Plugin.Core.Agents.BaseAgent import AgentState

class TestBuilderComplete(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # 1. Limpieza de ficheros residuales
        save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Plugin/Saves/Builder_Test.json'))
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except:
                pass

        self.bus = MagicMock()
        self.bus.publish = AsyncMock()
        self.bus.subscribe = MagicMock()
        self.mc = MagicMock()
        
        # Template falso para pruebas
        self.fake_templates = {
            "esencias": {
                "width": 10, "height": 5, "depth": 10,
                "materials": [{"material": "stone", "qty": 5}],
                "blocks": [(0,0,0, "stone"), (1,0,0, "unknown_block")]
            },
            "casa": {
                "width": 5, "height": 5, "depth": 5,
                "materials": [],
                "blocks": []
            }
        }

        # Inyectamos TEMPLATES antes de crear el bot
        with patch("Plugin.Core.Agents.Builder.BuilderBot.load_all_templates"), \
             patch.dict("Plugin.Core.Agents.Builder.BuilderBot.TEMPLATES", self.fake_templates, clear=True), \
             patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            
            self.bot = BuilderBot("Builder_Test", bus=self.bus, mc=self.mc)
            # Evitamos que el bot arranque hilos reales
            self.bot.start = AsyncMock()

    # --- 1. WORKFLOW ---
    async def test_workflow_command(self):
        msg = {
            "target": "Builder_Test", "source": "User",
            "payload": {
                "schem": "esencias", "x": 100, "z": 100, "range": 50,
                "e_strategy": "spiral", "m_strategy": "vein"
            }
        }
        
        with patch.dict("Plugin.Core.Agents.Builder.BuilderBot.TEMPLATES", self.fake_templates, clear=True):
            await self.bot._on_workflow_cmd(msg)
            
        self.assertTrue(self.bus.publish.call_count >= 3)

    # --- 2. DECISIONES ---
    async def test_decision_tree(self):
        self.bot.request_free_area_clean = AsyncMock(return_value={"x1":0, "z1":0, "width":10})
        
        with patch.dict("Plugin.Core.Agents.Builder.BuilderBot.TEMPLATES", self.fake_templates, clear=True):
            # CASO A: Sin Mapa -> Calcular BOM o Pedir Area
            percept = {"map": None, "bom": None, "template": "esencias", "build_progress": 0}
            d = await self.bot.decide(percept)
            self.assertEqual(d["action"], "compute_bom") 
            
            # CASO B: Sin BOM -> Calcular BOM
            percept["map"] = {"x1":0}
            d = await self.bot.decide(percept)
            self.assertEqual(d["action"], "compute_bom")

            # CASO C: Falta Material -> Esperar Materiales
            # [CORRECCIÓN] Damos un BOM para que no intente calcularlo de nuevo
            percept["bom"] = [{"material": "stone", "qty": 5}]
            
            self.bot.check_and_consume_materials = AsyncMock(return_value={
                "status": "INSUFFICIENT", "missing": [{"material": "stone", "qty": 1}]
            })
            d = await self.bot.decide(percept)
            self.assertEqual(d["action"], "wait_for_materials")
            
            # CASO D: Construir
            self.bot.check_and_consume_materials = AsyncMock(return_value={"status": "OK"})
            self.bot._materials_reserved = True 
            self.bot._build_plan = [{"y":0, "blocks": []}] 
            
            d = await self.bot.decide(percept)
            self.assertEqual(d["action"], "build_layer")

    # --- 3. ERRORES DE CONSTRUCCIÓN ---
    async def test_build_execution_and_errors(self):
        self.bot._valid_area = {"x1":0, "y":64, "z1":0}
        self.bot._build_plan = [
            {"y": 0, "blocks": [
                {"x":0, "y":0, "z":0, "material": "stone"}, 
                {"x":1, "y":0, "z":0, "material": "lava"}
            ]}
        ]
        self.bot._build_progress = 0
        
        self.mc.setBlock.side_effect = [None, Exception("Crash")]
        await self.bot._build_next_layer()
        self.assertEqual(self.bot._build_progress, 1)

    # --- 4. EXTRAS ---
    async def test_extras(self):
        # Callbacks
        self.bot._map_event = MagicMock()
        await self.bot._on_map({"target": "Builder_Test", "source": "E1", "payload": {"best_rectangle": {}}})
        self.bot._map_event.set.assert_called()
        
        self.bot._bom_event = MagicMock()
        await self.bot._on_inventory({"target": "Builder_Test", "source": "M1"})
        
        # List command
        with patch.dict("Plugin.Core.Agents.Builder.BuilderBot.TEMPLATES", self.fake_templates, clear=True):
            self.bot.list()

        # Block resolver
        blk = self.bot.get_block_from_name("stone")
        self.assertIsNotNone(blk)

    # --- 5. PERSISTENCIA ---
    def test_persistence(self):
        self.bot._build_progress = 5
        data = self.bot.get_save_data()
        self.assertEqual(data["build_progress"], 5)
        
        with patch("Plugin.Core.Agents.Builder.BuilderBot.load_all_templates"), \
             patch.dict("Plugin.Core.Agents.Builder.BuilderBot.TEMPLATES", self.fake_templates, clear=True), \
             patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
             
            new_bot = BuilderBot("Builder_Clone", bus=self.bus, mc=self.mc)
            new_bot.load_save_data(data)
            self.assertEqual(new_bot._build_progress, 5)

if __name__ == '__main__':
    unittest.main()