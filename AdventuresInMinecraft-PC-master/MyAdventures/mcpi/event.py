from .vec3 import Vec3
import asyncio

# Diccionario global de bots disponibles
BOTS_REGISTRY = {"ExplorerBot","BuilderBot","MinerBot"}

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
    _bots_registered = False

    def __init__(self, type, entityId, message):
        self.type = type
        self.entityId = entityId
        self.message = message

        if not ChatEvent._bots_registered:
            ChatEvent._auto_register_bots()
            ChatEvent._bots_registered = True

        if self.type == ChatEvent.POST and BOTS_REGISTRY:
            asyncio.create_task(self._dispatch())

    @staticmethod
    def Post(entityId, message):
        return ChatEvent(ChatEvent.POST, entityId, message)

    @staticmethod
    def _auto_register_bots():
        bots = BOTS_REGISTRY
        print(f"[ChatEvent] Bots registrados automáticamente: {list(bots)}")

    async def _dispatch(self):
        """Despacha el comando al bot correspondiente usando commandos.py"""
        try:
            from Plugin.Core.Commands import commands
            result = await commands.dispatch_command(self, BOTS_REGISTRY)
            if result:
                print(f"[CHAT CMD] {result}")
        except Exception as e:
            print(f"[CHAT CMD ERROR] {str(e)}")
