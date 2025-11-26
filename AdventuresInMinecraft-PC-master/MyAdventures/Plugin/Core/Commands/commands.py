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
# Despacho de comandos con validación
# ------------------------------------------------------------
async def dispatch_command(event: ChatEvent, bots: Dict[str, Any]):
    from ..Agents.Explorer.ExplorerBot import ExplorerBot

    parsed = parse_command(event)
    if not parsed:
        return f"Comando no reconocido: {event.message}"

    cmd = parsed["cmd"]
    params = parsed["params"]

    try:
        # ----------- EXPLORER ----------- 
        if cmd.startswith("explorer") and "explorer" in bots:
            bot: ExplorerBot = bots["explorer"]

            if cmd == "explorer_start":
                await bot._on_start_cmd({"payload": params, "target": bot.agent_id})
                return f"ExplorerBot iniciado en ({params.get('x')},{params.get('z')})"

            elif cmd == "explorer_set":
                # Cambiar parámetros opcionales si existen
                update_params = {}
                if "range" in params:
                    update_params["range"] = params["range"]
                if "cube" in params:
                    update_params["cube"] = params["cube"]
                if "strategy" in params:
                    update_params["strategy"] = params["strategy"]

                if update_params:
                    await bot._on_update_cmd({"payload": update_params, "target": bot.agent_id})

                return f"ExplorerBot parámetros actualizados: {params}"
            
            elif cmd == "explorer_status":
                state_info = await bot.status()
                return f"ExplorerBot status: {state_info}"
            
            elif cmd == "explorer_stop":
                await bot.stop()
                return f"ExplorerBot detenido"

        # ----------- BUILDER ----------- 
        if cmd.startswith("builder") and "builder" in bots:
            bot = bots["builder"]
            if cmd == "builder_build":
                await bot._on_build_cmd({"payload": params, "target": bot.agent_id})
                return f"BuilderBot construyendo"

        return f"Comando válido pero bot no registrado: {cmd}"

    except Exception as e:
        return f"Error ejecutando comando {cmd}: {str(e)}"
