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

    async def execute(self, message: str, sender_id: int, bots: Dict[str, Any]):
        parsed = self.parse(message)
        if not parsed: return None

        cmd_info = self._registry[parsed["cmd"]]
        target_bot_key = cmd_info["target_bot"]
        
        # Inyección del bot correcto
        bot_instance = None
        if target_bot_key:
            if target_bot_key not in bots:
                return f"Bot '{target_bot_key}' no disponible."
            bot_instance = bots[target_bot_key]

        # Ejecuta la función decorada
        return await cmd_info["handler"](
            bot=bot_instance, 
            params=parsed["params"], 
            sender_id=sender_id,
            topic=cmd_info["topic"]
        )