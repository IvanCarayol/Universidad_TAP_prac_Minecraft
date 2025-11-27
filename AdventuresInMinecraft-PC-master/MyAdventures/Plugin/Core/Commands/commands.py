from typing import Dict, Any, Optional
from mcpi.event import ChatEvent

# ------------------------------------------------------------
# Comandos disponibles y sus parámetros
# ------------------------------------------------------------
COMMANDS = {
    "explorer_start": {
        "description": "Inicia el bot Explorer en una posición y rango",
        "params": ["x", "z"],
    },
    "explorer_set": {
        "description": "Actualiza parámetros del bot Explorer",
        "params": [],
    },
    "explorer_stop": {
        "description": "Detiene el bot Explorer",
        "params": [],
    },
    "explorer_status": {
        "description": "Devuelve el estado de el bot",
        "params": [],
    },
    "builder_start": {
        "description": "Ordena construir",
        "params": [],
    },
}

# ------------------------------------------------------------
# Función de parseo de mensajes de chat
# ------------------------------------------------------------
def parse_command(event: ChatEvent) -> Optional[Dict[str, Any]]:
    """
    Parsea un mensaje de chat en un comando y parámetros.
    Devuelve None si no es un comando válido.
    Ahora no requiere "/" al inicio.
    """
    if event.type != ChatEvent.POST:
        return None

    message = event.message.strip()
    if not message:
        return None

    # Split normal por espacios
    parts = message.split()
    if not parts:
        return None

    # Construir nombre de comando: ej. "explorer start" → "explorer_start"
    cmd_name = "_".join(parts[:2]) if len(parts) > 1 else parts[0]
    params: Dict[str, Any] = {}

    # Parsear parámetros clave=valor
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            try:
                params[k] = int(v)
            except ValueError:
                params[k] = v

    if cmd_name not in COMMANDS:
        return None

    return {"cmd": cmd_name, "params": params}

# ------------------------------------------------------------
# Despacho de comandos con bus
# ------------------------------------------------------------
async def dispatch_command(event: ChatEvent, bots: Dict[str, Any]):
    parsed = parse_command(event)
    if not parsed:
        return f"Comando no reconocido: {event.message}"

    cmd = parsed["cmd"]
    params = parsed["params"]

    try:
        # ----------- EXPLORER ----------- 
        if cmd.startswith("explorer") and "explorer" in bots:
            bot = bots["explorer"]

            # Mapear cmd a type exacto para que coincida con bus.subscribe
            type_map = {
                "explorer_start": "command.explorer.start.v1",
                "explorer_set": "command.explorer.set.v1",
                "explorer_stop": "command.explorer.stop.v1",
                "explorer_status": "command.explorer.status.v1",
            }

            msg_type = type_map.get(cmd)
            if not msg_type:
                return f"No hay tipo definido en bus para {cmd}"

            msg = {
                "type": msg_type,
                "source": "chat",
                "target": bot.agent_id,
                "payload": params,
            }

            await bot.bus.publish(msg)
            return f"ExplorerBot recibió comando: {cmd} ({params})"


        # ----------- BUILDER ----------- 
        if cmd.startswith("builder") and "builder" in bots:
            bot = bots["builder"]
            type_map = {
                "builder_start": "command.builder.start.v1",
            }
            msg_type = type_map.get(cmd)
            if not msg_type:
                return f"No hay tipo definido en bus para {cmd}"

            msg = {
                "type": msg_type,
                "source": "chat",
                "target": bot.agent_id,
                "payload": params,
            }

            await bot.bus.publish(msg)
            return f"BuilderBot recibió comando: {cmd} ({params})"


        return f"Comando válido pero bot no registrado: {cmd}"

    except Exception as e:
        return f"Error ejecutando comando {cmd}: {str(e)}"
