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
    _active_dispatches = set()  # global: mensajes que ya están en dispatch

    def __init__(self, type, entityId, message):
        self.type = type
        self.entityId = entityId
        self.message = message

        if self.type == ChatEvent.POST:
            key = (self.entityId, self.message)
            if key not in ChatEvent._active_dispatches:
                ChatEvent._active_dispatches.add(key)
                asyncio.create_task(self._dispatch(key))

    @staticmethod
    def Post(entityId, message):
        return ChatEvent(ChatEvent.POST, entityId, message)

    async def _dispatch(self, key):
        """Despacha el comando y libera el lock después."""
        try:
            from Plugin.Core.Commands import commands
            await commands.dispatch_command(self, BOTS_REGISTRY)
        except Exception as e:
            print(f"[CHAT CMD ERROR] {str(e)}")
        finally:
            ChatEvent._active_dispatches.discard(key)



# =====================================================
# Listener de chat
# =====================================================
async def chat_listener(mc, poll_interval: float = 0.1):
    """
    Escucha continuamente los mensajes de chat en el servidor y despacha eventos.
    """
    while True:
        events = mc.events.pollChatPosts()
        for evt in events:
            ChatEvent.Post(evt.entityId, evt.message)
        await asyncio.sleep(poll_interval)


def start_chat_listener(mc):
    asyncio.create_task(chat_listener(mc))
    print("[CHAT LISTENER] Iniciado")
