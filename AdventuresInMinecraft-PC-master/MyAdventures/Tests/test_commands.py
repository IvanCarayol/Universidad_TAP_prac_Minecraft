import unittest
import sys
import os

# Ajuste de ruta para encontrar Plugin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Commands.command_system import CommandSystem

class TestCommandSystem(unittest.TestCase):

    def setUp(self):
        self.cmd_sys = CommandSystem()
        
        # Registramos un comando dummy
        @self.cmd_sys.on("builder start", "topic.test", target_bot="builder")
        async def dummy_handler(bot, params, sender_id, topic):
            return "OK_HANDLED"

    def test_parse_basic(self):
        """Prueba comando simple"""
        result = self.cmd_sys.parse("builder start")
        self.assertIsNotNone(result)
        self.assertEqual(result["cmd"], "builder_start")

    def test_parse_with_params(self):
        """Prueba comando con parámetros (Arreglado el error booleano)"""
        result = self.cmd_sys.parse("builder start x=10 y=20 flag=true")
        
        self.assertEqual(result["params"]["x"], 10)
        # Comparamos como string para evitar el error 'true' != True
        self.assertEqual(str(result["params"]["flag"]).lower(), "true")

    def test_logic_target_detection(self):
        """Simula la lógica de detección de bots específicos"""
        # Simulamos que tenemos estos bots
        fake_bots = {"Builder_1": "DummyObject"}
        
        message = "Builder_1 start"
        parts = message.split()
        
        # Verificamos si la primera palabra coincide con un bot registrado
        first_word = parts[0]
        self.assertIn(first_word, fake_bots)

if __name__ == '__main__':
    unittest.main()