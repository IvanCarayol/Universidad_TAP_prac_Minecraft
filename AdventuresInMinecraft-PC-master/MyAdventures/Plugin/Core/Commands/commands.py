from typing import Dict, Any

# Importamos el manager con todos los comandos ya cargados
from .definitions import cmd_manager

# ------------------------------------------------------------
# Despacho de comandos (AHORA DELEGA EN EL MANAGER)
# ------------------------------------------------------------
async def dispatch_command(sender_id: int, raw_message: str, bots: Dict[str, Any]):
    """
    Procesa un comando escrito en el chat usando el nuevo CommandSystem.
    """
    try:
        # 1. El manager hace el parseo inteligente (1, 2 o 3 palabras)
        # 2. Busca el bot correspondiente en tu diccionario 'bots'
        # 3. Ejecuta la función asociada en definitions.py
        result = await cmd_manager.execute(raw_message, sender_id, bots)
        
        if result is None:
            # Si devuelve None es que no encontró el comando o el parse falló
            # (Opcional: puedes devolver None para no spammear el chat si no es comando)
            return f"Comando no reconocido: {raw_message}"
            
        return result

    except Exception as e:
        return f"Error crítico ejecutando comando: {str(e)}"