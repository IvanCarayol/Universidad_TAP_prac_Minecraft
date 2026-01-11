from typing import Dict, Any, Callable, Optional

class CommandSystem:
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}

    def on(self, command_text: str, topic: str, target_bot: str = None):
        """Decorador para registrar comandos."""
        def decorator(func: Callable):
            key = command_text.strip().lower().replace(" ", "_")
            self._registry[key] = {
                "topic": topic,
                "handler": func,
                "target_bot": target_bot
            }
            return func
        return decorator

    def parse(self, message: str) -> Optional[Dict[str, Any]]:
        """Logica de 'Longest Match' para parsear comandos de varias palabras."""
        if not message: return None
        parts = message.strip().lower().split()
        if not parts: return None

        # Busca coincidencias de hasta 3 palabras (ej: "miner set strategy")
        best_key = None
        args_idx = 0
        for i in range(min(len(parts), 3), 0, -1):
            candidate = "_".join(parts[:i])
            if candidate in self._registry:
                best_key = candidate
                args_idx = i
                break
        
        if not best_key: return None

        # Parsea parametros (x=10 flag=true)
        params = {}
        for p in parts[args_idx:]:
            if "=" in p:
                k, v = p.split("=", 1)
                try: params[k] = int(v)
                except ValueError: params[k] = v
            else:
                params[p] = True # Flags

        return {"cmd": best_key, "params": params}

    # ... (métodos __init__ y parse se quedan igual) ...

    async def execute(self, message: str, sender_id: int, bots: Dict[str, Any]):
        parts = message.strip().split()
        if not parts: return None

        first_word = parts[0] # Ej: "Builder_1"
        target_override = None
        command_to_parse = message 

        # 1. DETECTAR SI LA PRIMERA PALABRA ES UN BOT (Builder_1)
        # Buscamos si "Builder_1" (o "builder_1") está en las claves de bots
        matched_bot_id = None
        for bot_id in bots.keys():
            if bot_id.lower() == first_word.lower():
                matched_bot_id = bot_id
                break
        
        if matched_bot_id:
            # ¡Es un bot específico!
            target_override = matched_bot_id
            
            # 2. DEDUCIR EL ROL (Para saber qué comando ejecutar)
            # Si le hablas a "Builder_1", quieres ejecutar un comando de "builder"
            lower_id = matched_bot_id.lower()
            if "builder" in lower_id: role = "builder"
            elif "miner" in lower_id: role = "miner"
            elif "explorer" in lower_id: role = "explorer"
            elif "worldstate" in lower_id: role = "worldstate"
            else: role = lower_id # Fallback
            
            # Reconstruimos el comando simulado: "Builder_1 start" -> "builder start"
            command_to_parse = role + " " + " ".join(parts[1:])
        
        # 3. PARSEAR COMANDO
        parsed = self.parse(command_to_parse)
        if not parsed: return None

        cmd_info = self._registry[parsed["cmd"]]
        
        # 4. ELEGIR BOT FINAL
        bot_instance = None
        
        if target_override:
            # Caso A: Usuario dijo "Builder_1 start" -> Usamos Builder_1
            bot_instance = bots[target_override]
        elif cmd_info["target_bot"]:
            # Caso B: Usuario dijo "builder start" -> Buscamos el primer builder disponible
            target_key = cmd_info["target_bot"] # "builder"
            
            # Si existe un bot llamado exactamente "builder" (alias)
            if target_key in bots:
                bot_instance = bots[target_key]
            else:
                # Búsqueda parcial: Dame el primer bot que contenga "builder" en su ID
                for bid, b in bots.items():
                    if target_key.lower() in bid.lower():
                        bot_instance = b
                        break

        if not bot_instance:
             return f"No se encontró un bot para el comando '{parsed['cmd']}'"

        # 5. EJECUTAR
        return await cmd_info["handler"](
            bot=bot_instance, 
            params=parsed["params"], 
            sender_id=sender_id,
            topic=cmd_info["topic"]
        )