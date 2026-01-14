import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Ajuste de ruta para encontrar el Plugin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importamos las estrategias
from Plugin.Core.Agents.Strategies.explorer_strategies import search_line, search_spiral, search_random
from Plugin.Core.Agents.Strategies.miner_strategies import vertical_strategy, vein_strategy, grid_strategy

class TestStrategies(unittest.IsolatedAsyncioTestCase):

    async def test_explorer_strategies(self):
        # Mock básico del bot
        bot = MagicMock()
        
        # [CORRECCIÓN IMPORTANTE] 
        # Convertimos _yield_scan en asíncrono para que 'await' no falle
        bot._yield_scan = AsyncMock()
        
        # Simulamos respuesta de Minecraft
        bot.mc.getHeight.return_value = 64
        
        # Probamos Estrategia Lineal
        res_line = await search_line(bot, 0, 0, 5)
        self.assertTrue(len(res_line) > 0)

        # Probamos Estrategia Espiral
        res_spiral = await search_spiral(bot, 0, 0, 5)
        self.assertTrue(len(res_spiral) > 0)

        # Probamos Estrategia Aleatoria
        res_random = await search_random(bot, 0, 0, 5)
        self.assertTrue(len(res_random) > 0)

    async def test_miner_strategies(self):
        # Definimos un área de prueba completa
        area = {
            "x1": 0, "z1": 0, "x2": 10, "z2": 10, 
            "width": 10, "depth": 10, "height": 10, 
            "y": 64
        }
        
        # Probamos Vertical
        strat_v = await vertical_strategy(area)
        target_v = await strat_v() 
        self.assertIsNotNone(target_v)

        # Probamos Vein (Vetas)
        strat_vein = await vein_strategy(area)
        target_vein = await strat_vein()
        self.assertIsNotNone(target_vein)

        # Probamos Grid (Cuadrícula)
        strat_grid = await grid_strategy(area)
        target_grid = await strat_grid()
        self.assertIsNotNone(target_grid)

if __name__ == '__main__':
    unittest.main()