from typing import Dict, Any, Optional
from mcpi.event import ChatEvent

# ------------------------------------------------------------
# Comandos disponibles y sus parámetros
# ------------------------------------------------------------
COMMANDS = {
    "explorer_start": {
        "description": "Inicia el bot Explorer en una posición y rango",
        "params": ["x", "z", "range", "cube"],
    },
    "explorer_set": {
        "description": "Actualiza parámetros del bot Explorer",
        "params": ["range", "cube"],
    },
    "explorer_stop": {
        "description": "Detiene el bot Explorer",
        "params": [],
    },
    "builder_build": {
        "description": "Ordena construir en una posición específica",
        "params": ["x", "z", "size", "block_id"],
    },
}

# ------------------------------------------------------------
# Función de parseo de mensajes de chat
# ------------------------------------------------------------
def parse_command(event: ChatEvent) -> Optional[Dict[str, Any]]:
    """
    Parsea un mensaje de chat en un comando y parámetros.
    Devuelve None si no es un comando válido.
    """
    if event.type != ChatEvent.POST:
        return None

    message = event.message.strip()
    if not message.startswith("/"):
        return None

    parts = message[1:].split()
    if not parts:
        return None

    # Construir nombre de comando: ej. "/explorer start" → "explorer_start"
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
# Despacho de comandos con validación
# ------------------------------------------------------------
async def dispatch_command(event: ChatEvent, bots: Dict[str, Any]):
    """
    Recibe un ChatEvent y despacha a los bots correspondientes.
    bots = {"ExplorerBot": explorer_bot_instance, "BuilderBot": builder_bot_instance}
    Devuelve un string de resultado (éxito o error).
    """
    parsed = parse_command(event)
    if not parsed:
        return f"Comando no reconocido: {event.message}"

    cmd = parsed["cmd"]
    params = parsed["params"]

    # Validar parámetros requeridos
    required_params = COMMANDS[cmd]["params"]
    missing = [p for p in required_params if p not in params]
    if missing:
        return f"Parámetros faltantes para {cmd}: {', '.join(missing)}"

    # Despachar al bot correspondiente
    try:
        if cmd.startswith("explorer") and "ExplorerBot" in bots:
            bot = bots["ExplorerBot"]
            if cmd == "explorer_start":
                await bot._on_start_cmd({"payload": params, "target": bot.agent_id})
                return f"ExplorerBot iniciado en ({params.get('x')},{params.get('z')})"
            elif cmd == "explorer_set":
                await bot._on_update_cmd({"payload": params, "target": bot.agent_id})
                return f"ExplorerBot parámetros actualizados"
            elif cmd == "explorer_stop":
                await bot.stop()
                return f"ExplorerBot detenido"
        elif cmd.startswith("builder") and "BuilderBot" in bots:
            bot = bots["BuilderBot"]
            if cmd == "builder_build":
                await bot._on_build_cmd({"payload": params, "target": bot.agent_id})
                return f"BuilderBot construyendo en ({params.get('x')},{params.get('z')})"
        else:
            return f"Comando válido pero bot no registrado: {cmd}"
    except Exception as e:
        return f"Error ejecutando comando {cmd}: {str(e)}"
