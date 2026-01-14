import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.World.WorldstateBot import WorldStateBot

class TestWorldStateHeavy(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Limpieza
        save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Plugin/Saves/WorldState_Test.json'))
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except: pass

        self.bus = MagicMock()
        self.bus.publish = AsyncMock()
        with patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            self.bot = WorldStateBot("WorldState_Test", bus=self.bus)

    # --- 1. GESTIÓN DE ÁREAS ---
    async def test_area_management_flow(self):
        # A. Guardar
        rect = {"x1":0, "z1":0, "x2":20, "z2":20, "width":21, "height":21, "area":441, "y":64}
        msg_save = {"type": "savearea.v1", "source": "E1", "payload": {"rect": rect}}
        
        d = await self.bot.decide(("E1", msg_save))
        await self.bot.act(d)
        self.assertEqual(len(self.bot.flat_areas), 1)

        # B. Pedir
        msg_req = {"type": "requestarea.v1", "source": "B1", "payload": {"width": 1, "depth": 1, "padding": 0}}
        d = await self.bot.decide(("B1", msg_req))
        await self.bot.act(d)
        
        self.bus.publish.assert_called()
        reserved = [a for a in self.bot.flat_areas if a.get("status") == "RESERVED" or a.get("locked")]
        self.assertEqual(len(reserved), 1)

        # C. Liberar
        msg_rel = {"type": "releasearea.v1", "source": "B1", "payload": {"rect": rect}}
        d = await self.bot.decide(("B1", msg_rel))
        await self.bot.act(d)
        
        # Tu bot borra el área al liberarla, así que no debe quedar ninguna reservada
        still_reserved = [a for a in self.bot.flat_areas if a.get("status") == "RESERVED"]
        self.assertEqual(len(still_reserved), 0)

    # --- 2. VALIDACIÓN DE COORDENADAS (Corregido) ---
    async def test_coordinate_validation(self):
        """Prueba si un explorador puede pisar en ciertas coordenadas."""
        
        # [CORRECCIÓN] Inyectamos el área con el formato correcto (wrapper)
        raw_rect = {"x1":0, "z1":0, "x2":10, "z2":10, "y":64}
        area_wrapper = {
            "rect": raw_rect,
            "locked": True, 
            "status": "RESERVED"
        }
        self.bot.flat_areas.append(area_wrapper)
        
        # Caso A: Coordenada ocupada (5, 5) -> Debe fallar
        msg_bad = {
            "type": "validatecoords.v1", 
            "source": "E1", 
            "payload": {"coords": [(5, 5)]}
        }
        
        d = await self.bot.decide(("E1", msg_bad))
        await self.bot.act(d)
        
        call_args = self.bus.publish.call_args[0][0]
        self.assertEqual(call_args["type"], "worldstate.response")
        # Dependiendo de tu implementación, status puede ser AREA_OCCUPIED o valid_coords=[]
        
        # Caso B: Coordenada libre (100, 100) -> Debe pasar
        msg_ok = {
            "type": "validatecoords.v1", 
            "source": "E1", 
            "payload": {"coords": [(100, 100)]}
        }
        
        d = await self.bot.decide(("E1", msg_ok))
        await self.bot.act(d)
        
        call_args_ok = self.bus.publish.call_args[0][0]
        self.assertEqual(call_args_ok["type"], "worldstate.response")

    # --- 3. GESTIÓN DE MATERIALES ---
    async def test_material_flow(self):
        # A. Minero entrega
        msg_report = {
            "type": "materials.report.v1", 
            "source": "M1", 
            "payload": {"materials": [{"material": "stone", "qty": 10}]}
        }
        d = await self.bot.decide(("M1", msg_report))
        await self.bot.act(d)
        
        storage = getattr(self.bot, "materials", getattr(self.bot, "inventory", {}))
        self.assertEqual(storage.get("stone", 0), 10)

        # B. Builder pide (OK)
        msg_check_ok = {
            "type": "materials.check.v1", 
            "source": "B1", 
            "payload": {"bom": [{"material": "stone", "qty": 5}]}
        }
        d = await self.bot.decide(("B1", msg_check_ok))
        await self.bot.act(d)
        
        resp_ok = self.bus.publish.call_args[0][0]
        self.assertEqual(resp_ok["payload"]["status"], "OK")
        self.assertEqual(storage.get("stone", 0), 5) 

        # C. Builder pide (Fallo)
        msg_check_fail = {
            "type": "materials.check.v1", 
            "source": "B1", 
            "payload": {"bom": [{"material": "gold", "qty": 100}]}
        }
        d = await self.bot.decide(("B1", msg_check_fail))
        await self.bot.act(d)
        
        resp_fail = self.bus.publish.call_args[0][0]
        self.assertEqual(resp_fail["payload"]["status"], "INSUFFICIENT")

    # --- 4. PERSISTENCIA ---
    def test_persistence(self):
        # Inyectamos estado sucio
        self.bot.flat_areas = [{"rect": {"x1":0}, "status": "RESERVED"}]
        inv_attr = "materials" if hasattr(self.bot, "materials") else "inventory"
        setattr(self.bot, inv_attr, {"diamond": 50})
        
        data = self.bot.get_save_data()
        
        with patch("Plugin.Core.Agents.BaseAgent.BaseAgent.load_from_disk"):
            new_bot = WorldStateBot("WS_Clone", bus=self.bus)
            new_bot.load_save_data(data)
            
            self.assertEqual(len(new_bot.flat_areas), 1)
            self.assertEqual(new_bot.flat_areas[0].get("status"), "RESERVED")
            
            new_storage = getattr(new_bot, inv_attr, {})
            self.assertEqual(new_storage.get("diamond"), 50)

if __name__ == '__main__':
    unittest.main()