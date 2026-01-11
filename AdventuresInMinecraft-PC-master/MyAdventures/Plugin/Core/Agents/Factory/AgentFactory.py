# Importamos las clases de los bots. 
# NOTA: Ajusta las rutas si moviste el WorldStateBot de sitio.
from ..Miner.MinerBot import MinerBot
from ..Explorer.ExplorerBot import ExplorerBot
from ..Builder.BuilderBot import BuilderBot
from ..World.WorldstateBot import WorldStateBot 
from Plugin.Core.Bus.Bus import MessageBus
bus = MessageBus()

class AgentFactory:
    @staticmethod
    def create(agent_type: str, agent_id: str, mc=None):
        """
        Crea y devuelve una instancia del bot solicitado.
        
        Args:
            agent_type (str): "miner", "explorer", "builder", "worldstate"
            agent_id (str): El nombre único del bot (ej: "MinerBot1")
            bus (MessageBus): El bus de comunicaciones compartido
            mc (Minecraft): La conexión al juego (opcional para algunos bots)
            
        Returns:
            BaseAgent: La instancia del bot creada.
        """
        
        t = agent_type.strip().lower()
        
        if t == "miner":
            # El minero necesita 'mc' para moverse y picar
            return MinerBot(agent_id, bus=bus, mc=mc)
            
        elif t == "explorer":
            # El explorador necesita 'mc' para ver el terreno
            return ExplorerBot(agent_id, bus=bus, mc=mc)
            
        elif t == "builder":
            # El builder suele gestionar su propia conexión o no la pide en init
            # (Según tu código, acepta 'bus' y 'agent_id')
            return BuilderBot(agent_id, bus=bus)
            
        elif t == "worldstate":
            # El worldstate es pura lógica, no suele usar 'mc' directo en init
            return WorldStateBot(agent_id, bus=bus)
            
        else:
            raise ValueError(f"Tipo de agente desconocido: {agent_type}")