from .vec3 import Vec3
import asyncio


# Diccionario global de bots disponibles
BOTS_REGISTRY = {}

# =====================================================
#  FUNCIÓN GLOBAL register_bot — IMPORTABLE DESDE main
# =====================================================
def register_bot(bot):
    """
    Registra un bot para procesamiento de comandos.
    """
    bot_key = bot.agent_id.lower().replace("bot", "")  # "ExplorerBot" → "explorer"
    BOTS_REGISTRY[bot_key] = bot
    print(f"[mcpi.event] Bot registrado: {bot_key}")
    return True

# =====================================================
#              EVENTOS
# =====================================================
async def chat_listener(mc, poll_interval: float = 0.1):
    """
    Escucha continuamente los mensajes de chat en el servidor y despacha eventos.
    """
    last_events = set()  # para evitar procesar mensajes repetidos
    while True:
        # Obtener mensajes recientes
        events = mc.events.pollChatPosts()  # devuelve lista de {'entityId', 'message'}
        for evt in events:
            key = (evt.entityId, evt.message)
            if key in last_events:
                continue  # ya procesado
            last_events.add(key)

            # Crear y despachar ChatEvent
            ChatEvent.Post(evt.entityId, evt.message)

        # Mantener la lista de eventos recientes pequeña
        if len(last_events) > 1000:
            last_events = set(list(last_events)[-500:])

        await asyncio.sleep(poll_interval)

# ==========================================================
# Función principal para arrancar el listener
# ==========================================================
def start_chat_listener(mc):
    asyncio.create_task(chat_listener(mc))
    print("[CHAT LISTENER] Iniciado")


class BlockEvent:
    HIT = 0

    def __init__(self, type, x, y, z, face, entityId):
        self.type = type
        self.pos = Vec3(x, y, z)
        self.face = face
        self.entityId = entityId

    @staticmethod
    def Hit(x, y, z, face, entityId):
        return BlockEvent(BlockEvent.HIT, x, y, z, face, entityId)


class ChatEvent:
    POST = 0

    def __init__(self, type, entityId, message):
        self.type = type
        self.entityId = entityId
        self.message = message

        if self.type == ChatEvent.POST:
            asyncio.create_task(self._dispatch())

    @staticmethod
    def Post(entityId, message):
        return ChatEvent(ChatEvent.POST, entityId, message)

    async def _dispatch(self):
        """Despacha el comando al bot correspondiente usando commandos.py"""
        try:
            from Plugin.Core.Commands import commands
            result = await commands.dispatch_command(self, BOTS_REGISTRY)
            if result:
                print(f"[CHAT CMD] {result}")
        except Exception as e:
            print(f"[CHAT CMD ERROR] {str(e)}")
