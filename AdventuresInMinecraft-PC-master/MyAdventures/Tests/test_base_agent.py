import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Plugin.Core.Agents.BaseAgent import BaseAgent, AgentState

class TestBaseAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.bus.publish = AsyncMock()
        self.agent = BaseAgent("Base_Test", self.bus)

    async def test_state_changes(self):
        """Prueba pausar y reanudar"""
        self.agent.set_state(AgentState.RUNNING, "Go")
        self.assertEqual(self.agent.state, AgentState.RUNNING)
        
        await self.agent.pause()
        self.assertEqual(self.agent.state, AgentState.PAUSED)
        
        await self.agent.resume()
        self.assertEqual(self.agent.state, AgentState.RUNNING)

if __name__ == '__main__':
    unittest.main()