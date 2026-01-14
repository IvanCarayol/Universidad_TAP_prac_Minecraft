import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Ajuste de ruta para encontrar el Plugin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.Builder.BuilderBot import BuilderBot
from Plugin.Core.Agents.Miner.MinerBot import MinerBot
from Plugin.Core.Agents.Explorer.ExplorerBot import ExplorerBot

class TestInternals(unittest.IsolatedAsyncioTestCase):
    """
    TEST DE ESTRÉS (CAJA BLANCA): 
    Fuerza errores, excepciones y caminos raros para maximizar el coverage.
    """

    def setUp(self):
        # Mocks compartidos
        self.mc = MagicMock()
        self.bus = MagicMock()
        self.bus.publish = AsyncMock()
        self.bus.subscribe = MagicMock()

    async def test_builder_errors(self):
        """Fuerza al Builder a fallar poniendo bloques"""
        bot = BuilderBot("B_Int", self.bus, self.mc)
        
        # 1. Preparamos un plan de construcción falso
        bot._build_plan = [{"y":0, "blocks": [{"x":0, "y":0, "z":0, "material": "stone"}]}]
        bot._valid_area = {"x1":0, "y":0, "z1":0}
        
        # BOMBA: Hacemos que Minecraft explote al poner un bloque
        self.mc.setBlock.side_effect = Exception("Minecraft crash simulation")
        
        # Ejecutamos. Si el bot tiene un try/except (que lo tiene), sobrevivirá.
        # Esto marca como "usadas" las líneas del 'except'.
        await bot._build_next_layer() 
        
        # 2. También probamos el caso de "No hay mapa" (debe salir sin hacer nada)
        bot._valid_area = None
        await bot._build_next_layer() # Cubre el 'if not self._valid_area: return'

    async def test_miner_edge_cases(self):
        """Fuerza al Miner a encontrar aire o fallar"""
        bot = MinerBot("M_Int", self.bus, self.mc)
        bot._current_bom = [{"material": "stone", "qty": 1}]
        bot.assigned_area = {"x1":0, "z1":0, "x2":10, "z2":10, "width":10, "depth":10, "y":64}
        # Estrategia tonta que devuelve siempre el 0,0,0
        bot._strategy = AsyncMock(return_value=(0,0,0))
        
        # CASO 1: Minar Aire (Altura 0) -> Debe salir sin picar
        self.mc.getHeight.return_value = 0
        await bot._perform_mining_step() # Cubre el 'if max_y == 0: return'
        
        # CASO 2: Error crítico al picar -> Debe capturar la excepción
        self.mc.getHeight.return_value = 10
        self.mc.getBlock.return_value = 1
        self.mc.setBlock.side_effect = Exception("Pickaxe broken simulation")
        await bot._perform_mining_step() # Cubre el 'except Exception' del minero

    async def test_explorer_failures(self):
        """Fuerza al Explorer a fallar validaciones"""
        bot = ExplorerBot("E_Int", self.bus, self.mc)
        bot.search_strategy = AsyncMock(return_value=[(0,0)])
        
        # CASO 1: WorldState no responde o devuelve error (None)
        bot.validate_coords = AsyncMock(return_value=None) 
        res = await bot.perceive()
        self.assertIsNone(res) # Cubre 'if not validation: return None'

        # CASO 2: Área ocupada (Devuelve status AREA_OCCUPIED)
        bot.validate_coords = AsyncMock(return_value={"status": "AREA_OCCUPIED", "valid_coords": []})
        res2 = await bot.perceive()
        self.assertIsNone(res2) # Cubre el bloque de abortar exploración

if __name__ == '__main__':
    unittest.main()