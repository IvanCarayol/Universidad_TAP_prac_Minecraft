from typing import Dict, Any, Optional

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
    "explorer_pause": {
        "description": "Pausa el bot Explorer",
        "params": [],
    },
    "explorer_resume": {
        "description": "Reanuda el bot Explorer",
        "params": [],
    },
    "explorer_status": {
        "description": "Devuelve el estado de el bot",
        "params": [],
    },
    "builder_start": {
        "description": "Inicia el bot Builder",
        "params": [],
    },
    "builder_stop": {
        "description": "Detiene el bot Builder",
        "params": [],
    },
    "builder_pause": {
        "description": "Pausa el bot Builder",
        "params": [],
    },
    "builder_resume": {
        "description": "Reanuda el bot Builder",
        "params": [],
    },
    "builder_set": {
        "description": "Cambia la schem",
        "params": ["schem"],
    },
    "builder_list": {
        "description": "Muestra la lista schem",
        "params": ["schem"],
    },
    "builder_status": {
        "description": "Devuelve el estado de el bot",
        "params": [],
    },
    "worldstate_start": {
        "description": "Inicia el bot WorldState",
        "params": [],
    },
    "worldstate_status": {
        "description": "Devuelve el estado de el bot",
        "params": [],
    },
    "miner_start": {
        "description": "Inicia el bot Miner",
        "params": [],
    },
    "miner_status": {
        "description": "Devuelve el estado de el bot",
        "params": [],
    },
    "miner_stop": {
        "description": "Detiene el bot Miner",
        "params": [],
    },
    "miner_pause": {
        "description": "Pausa el bot Miner",
        "params": [],
    },
    "miner_resume": {
        "description": "Reanuda el bot Miner",
        "params": [],
    },
}

# ------------------------------------------------------------
# Función de parseo de mensajes de chat
# ------------------------------------------------------------
def parse_command(message: str):
    parts = message.strip().lower().split()
    if not parts:
        return None

    # "builder start", "explorer set", "builder list"
    cmd_name = "_".join(parts[:2]) if len(parts) >= 2 else parts[0]
    params = {}

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
async def dispatch_command(sender_id: int, raw_message: str, bots: Dict[str, Any]):
    """
    Procesa un comando escrito en el chat.
    raw_message: mensaje de texto del chat
    sender_id: ID del jugador que lo envió
    bots: registro global de bots
    """
    try:
        # Parsear el comando (ahora pasa raw_message en vez de un ChatEvent)
        parsed = parse_command(raw_message)
        if not parsed:
            return f"Comando no reconocido: {raw_message}"

        cmd = parsed["cmd"]
        params = parsed["params"]

        # ============================
        #          EXPLORER
        # ============================
        if cmd.startswith("explorer") and "explorer" in bots:
            bot = bots["explorer"]

            type_map = {
                "explorer_start":  "command.explorer.start.v1",
                "explorer_set":    "command.explorer.set.v1",
                "explorer_stop":   "command.explorer.stop.v1",
                "explorer_pause":  "command.explorer.pause.v1",
                "explorer_resume": "command.explorer.resume.v1",
                "explorer_status": "command.explorer.status.v1",
            }

            msg_type = type_map.get(cmd)
            if not msg_type:
                return f"No hay tipo definido en bus para comando {cmd}"

            msg = {
                "type": msg_type,
                "source": f"player:{sender_id}",
                "target": bot.agent_id,
                "payload": params,
            }

            await bot.bus.publish(msg)
            return f"[ExplorerBot] recibió comando: {cmd} {params}"

        # ============================
        #          BUILDER
        # ============================
        if cmd.startswith("builder") and "builder" in bots:
            bot = bots["builder"]

            type_map = {
                "builder_start":  "command.builder.start.v1",
                "builder_set":    "command.builder.set.v1",
                "builder_pause":  "command.builder.pause.v1",
                "builder_resume": "command.builder.resume.v1",
                "builder_stop":   "command.builder.stop.v1",
                "builder_list":   "command.builder.list.v1",
                "builder_status": "command.builder.status.v1",
            }

            msg_type = type_map.get(cmd)
            if not msg_type:
                return f"No hay tipo definido en bus para comando {cmd}"

            msg = {
                "type": msg_type,
                "source": f"player:{sender_id}",
                "target": bot.agent_id,
                "payload": params,
            }

            await bot.bus.publish(msg)
            return f"[BuilderBot] recibió comando: {cmd} {params}"

        # ============================
        #          MINER
        # ============================
        if cmd.startswith("miner") and "miner" in bots:
            bot = bots["miner"]

            type_map = {
                "miner_start":  "command.miner.start.v1",
                "miner_set":    "command.miner.set.v1",
                "miner_stop":   "command.miner.stop.v1",
                "miner_status": "command.miner.status.v1",
                "miner_pause": "command.miner.pause.v1",
                "miner_resume": "command.miner.resume.v1",
            }

            msg_type = type_map.get(cmd)
            if not msg_type:
                return f"No hay tipo definido en bus para comando {cmd}"

            msg = {
                "type": msg_type,
                "source": f"player:{sender_id}",
                "target": bot.agent_id,
                "payload": params,
            }

            await bot.bus.publish(msg)
            return f"[MinerBot] recibió comando: {cmd} {params}"
        
        # ============================
        #          WorldState
        # ============================
        if cmd.startswith("worldstate") and "worldstate" in bots:
            bot = bots["worldstate"]

            type_map = {
                "worldstate_start":  "command.worldstate.start.v1",
                "worldstate_status":  "command.worldstate.status.v1",
            }

            msg_type = type_map.get(cmd)
            if not msg_type:
                return f"No hay tipo definido en bus para comando {cmd}"

            msg = {
                "type": msg_type,
                "source": f"player:{sender_id}",
                "target": bot.agent_id,
                "payload": params,
            }

            await bot.bus.publish(msg)
            return f"[Worldstate] recibió comando: {cmd} {params}"

        return f"Comando válido pero ningún bot lo gestiona: {cmd}"

    except Exception as e:
        return f"Error ejecutando comando '{raw_message}': {str(e)}"
