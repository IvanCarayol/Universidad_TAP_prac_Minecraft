import asyncio
from  mcpi.event import ChatEvent

# Registro global de bots
BOTS_REGISTRY = {}

# Registro de dispatches activos
_ACTIVE_DISPATCHES = set()


async def chat_listener(mc, poll_interval: float = 0.1):
    """
    Escucha mensajes del chat.
    Usa ChatEvent solo como contenedor, ya no como sistema de eventos.
    """
    print("[CHAT LISTENER] Escuchando mensajes...")

    while True:
        events = mc.events.pollChatPosts()

        for evt in events:
            entity_id = evt.entityId
            message = evt.message.strip()

            # Crear un ChatEvent para compatibilidad o logs
            chat_evt = ChatEvent.Post(entity_id, message)

            key = f"{entity_id}:{message}"

            if key in _ACTIVE_DISPATCHES:
                continue

            _ACTIVE_DISPATCHES.add(key)

            # Pasar el ChatEvent al dispatcher interno
            asyncio.create_task(_dispatch(chat_evt, key))

        await asyncio.sleep(poll_interval)


def start_chat_listener(mc):
    asyncio.create_task(chat_listener(mc))
    print("[CHAT LISTENER] Iniciado")


async def _dispatch(chat_evt: ChatEvent, dispatch_key):
    """
    Despacha usando nuestro sistema propio.
    ChatEvent es solo un objeto con datos.
    """
    try:
        from Plugin.Core.Commands import commands

        # Llama sistema de comandos
        await commands.dispatch_command(
            chat_evt.entityId,
            chat_evt.message,
            BOTS_REGISTRY
        )

    except Exception as e:
        print(f"[CHAT CMD ERROR] {e}")

    finally:
        _ACTIVE_DISPATCHES.discard(dispatch_key)


def register_bot(bot):
    """
    Registra un bot para el sistema de comandos.
    """
    bot_key = bot.agent_id.lower().replace("bot", "")
    BOTS_REGISTRY[bot_key] = bot

    print(f"[CHAT LISTENER] Bot registrado: {bot_key}")
    return True
