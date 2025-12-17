import asyncio
import random
from typing import Any, Dict
from ..BaseAgent import BaseAgent
from ...Logger.logging_config import get_logger

logger = get_logger(__name__)

def rects_overlap(r1, r2):
    """Devuelve True si dos rectángulos se solapan."""
    return not (
        r1["x2"] < r2["x1"] or
        r2["x2"] < r1["x1"] or
        r1["z2"] < r2["z1"] or
        r2["z2"] < r1["z1"]
    )

def normalize_rect(rect):
    if isinstance(rect, dict):
        return rect
    if isinstance(rect, tuple) and len(rect) == 4:
        x1, z1, x2, z2 = rect
        return {
            "x1": x1,
            "z1": z1,
            "x2": x2,
            "z2": z2,
            "width": abs(x2 - x1) + 1,
            "height": abs((z2 - z1) + 1),
            "area": abs((x2 - x1) + 1) * abs((z2 - z1) + 1),
            "y": 63
        }
    raise ValueError(f"Invalid rect format: {rect}")


class WorldStateBot(BaseAgent):
    def __init__(self, agent_id, bus=None):
        super().__init__(agent_id, bus)

        # Estado interno
        self.flat_areas = []
        self._lock = asyncio.Lock()

        # Cola de percepciones
        self._inbox = asyncio.Queue()
        self._msg_event = asyncio.Event()

        # Subscripciones
        self.bus.subscribe("command.worldstate.start.v1", self._on_start_cmd)
        self.bus.subscribe("command.worldstate.status.v1", self._on_control)
        self.bus.subscribe("savearea.v1", self.on_message)
        self.bus.subscribe("requestarea.v1", self.on_message)
        self.bus.subscribe("releasearea.v1", self.on_message)
        self.bus.subscribe("lockarea.v1", self.on_message)
        self.bus.subscribe("validatecoords.v1", self.on_message)

    # ----------------------
    # Manejo de mensajes
    # ----------------------
    async def _on_start_cmd(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info("[WORLDSTATE] Start worldstate bot")
        await self.start()
        
    async def _on_control(self, msg: Dict[str, Any]):
        """pause/resume/stop commands"""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        cmdtype = msg.get("type", "")
        if cmdtype.endswith(".pause.v1"):
            await self.pause()
        elif cmdtype.endswith(".resume.v1"):
            await self.resume()
        elif cmdtype.endswith(".stop.v1"):
            await self.stop()
        elif cmdtype.endswith(".list.v1"):
            await self.list()
        elif cmdtype.endswith(".status.v1"):
            await self.status()

    async def on_message(self, msg):
        """Recibe mensaje del bus y lo mete en la cola de percepciones"""
        sender = msg.get("source")
        await self._inbox.put((sender, msg))
        self._msg_event.set()

    # ----------------------
    # PERCIBE
    # ----------------------
    async def perceive(self):
        """Espera hasta recibir un mensaje"""
        while self._inbox.empty():
            await self._msg_event.wait()
            self._msg_event.clear()
        return await self._inbox.get()

    # ----------------------
    # DECIDE
    # ----------------------
    async def decide(self, percept):
        sender, msg = percept
        mtype = msg.get("type")
        payload = msg.get("payload", {})

        if mtype == "savearea.v1":
            rect = payload.get("rect")
            return ("ADD_AREA_AND_REPLY", sender, rect)

        elif mtype == "requestarea.v1":
            return ("ALLOCATE_AREA_FROM_EXISTING", sender, payload)
        
        elif mtype == "releasearea.v1":
            rect = payload.get("rect")
            return ("RELEASE_AREA", sender, rect)

        elif mtype == "lockarea.v1":
            return ("GENERATE_NEW_AREA", sender, payload)

        elif mtype == "validatecoords.v1":
            return ("VALIDATE_COORDS", sender, payload)

        else:
            return ("UNKNOWN", sender, msg)

    # ----------------------
    # ACT
    # ----------------------
    async def act(self, decision):
        action = decision[0]

        # Guardar área enviada desde ExplorerBot
        if action == "ADD_AREA_AND_REPLY":
            sender, rect = decision[1], decision[2]
            await self._add_flat_area(rect)

            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": {
                    "status": "OK",
                    "message": "AREA_SAVED",
                    "rect": rect
                }
            })
            return

        # BuilderBot: elige área existente
        if action == "ALLOCATE_AREA_FROM_EXISTING":
            sender, required = decision[1], decision[2]
            result = await self._request_area(sender, required)

            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": result
            })
            return

        # MinerBot: libera el área que estaba usando
        elif action == "RELEASE_AREA":
            sender, rect = decision[1], decision[2]
            result = await self._release_area(sender, rect)
            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": result
            })

        # MinerBot: genera un área nueva completamente libre
        if action == "GENERATE_NEW_AREA":
            sender, required = decision[1], decision[2]
            result = await self._lock_area(sender, required)

            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": result
            })
            return

        # ExplorerBot: valida coordenadas disponibles
        if action == "VALIDATE_COORDS":
            sender, payload = decision[1], decision[2]
            result = await self._validate_coords(payload)

            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": result
            })
            return

        # Mensaje desconocido
        if action == "UNKNOWN":
            sender, msg = decision[1], decision[2]
            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": {
                    "error": f"[WorldStateBot] Mensaje desconocido: {msg}"
                }
            })
            return

    # ----------------------
    # Funciones internas de estado
    # ----------------------
    async def _add_flat_area(self, rect):
        rect = normalize_rect(rect)
        async with self._lock:
            self.flat_areas.append({
                "rect": rect,
                "status": "FREE",
                "assigned_to": None
            })

    async def _request_area(self, agent_id, required):
        if required is None:
            logger.warning(f"[WORLDSTATE] Received request with empty required payload from {agent_id}")
            return {"status": "INVALID_REQUEST"}

        req_w = required.get("width")
        req_h = required.get("depth")

        if req_w is None or req_h is None:
            logger.warning(f"[WORLDSTATE] Missing width/depth in request from {agent_id}")
            return {"status": "INVALID_REQUEST"}

        async with self._lock:
            candidates = [
                a for a in self.flat_areas
                if a["status"] == "FREE"
                and a["rect"]["width"] >= req_w
                and a["rect"]["height"] >= req_h
            ]

            if not candidates:
                return {"status": "NO_AREA_AVAILABLE"}

            best = max(candidates, key=lambda a: a["rect"]["area"])
            best["status"] = "RESERVED"
            best["assigned_to"] = agent_id

            return {"status": "OK", "rect": best["rect"]}
    
    async def _release_area(self, agent_id, rect):
        if rect is None:
            return {"status": "INVALID_REQUEST"}

        norm = normalize_rect(rect)

        async with self._lock:
            for i, a in enumerate(self.flat_areas):
                if (
                    a["rect"]["x1"] == norm["x1"] and
                    a["rect"]["z1"] == norm["z1"] and
                    a["rect"]["x2"] == norm["x2"] and
                    a["rect"]["z2"] == norm["z2"]
                ):
                    removed = self.flat_areas.pop(i)

                    logger.info(
                        f"[WORLDSTATE] Área eliminada por {agent_id}: {removed['rect']}"
                    )

                    return {
                        "status": "OK",
                        "rect": removed["rect"],
                        "removed": True
                    }

            logger.warning(
                f"[WORLDSTATE] Intento de eliminar un área NO registrada: {norm}"
            )
            return {"status": "NOT_FOUND", "rect": norm}

    async def _lock_area(self, agent_id, required):
        if required is None:
            return {"status": "INVALID_REQUEST"}

        req_w = required.get("width")
        req_h = required.get("depth")

        if req_w is None or req_h is None:
            return {"status": "INVALID_REQUEST"}

        MAX_TRIES = 50   # máximo intentos de encontrar un hueco libre
        WORLD_MIN = -200
        WORLD_MAX = 200

        async with self._lock:
            for _ in range(MAX_TRIES):

                # --- GENERAR CANDIDATO ALEATORIO ---
                x1 = random.randint(WORLD_MIN, WORLD_MAX - req_w)
                z1 = random.randint(WORLD_MIN, WORLD_MAX - req_h)
                x2 = x1 + req_w
                z2 = z1 + req_h

                candidate = normalize_rect((x1, z1, x2, z2))

                # --- COMPROBAR SOLAPAMIENTO ---
                overlaps = False
                for a in self.flat_areas:
                    if rects_overlap(candidate, a["rect"]):
                        overlaps = True
                        break

                if overlaps:
                    continue  # intentar otra coordenada

                # --- CANDIDATO ES VÁLIDO -> GUARDAR ---
                new_area = {
                    "rect": candidate,
                    "status": "RESERVED",
                    "assigned_to": agent_id
                }

                self.flat_areas.append(new_area)

                return {
                    "status": "OK",
                    "rect": candidate
                }

            # Si tras muchos intentos no hay hueco...
            return {"status": "NO_AREA_AVAILABLE"}
        
    def _point_in_rect(self, x, z, rect):
        return (
        rect["x1"] <= x <= rect["x2"] and
        rect["z1"] <= z <= rect["z2"]
        )

    async def _validate_coords(self, payload):
        coords = payload.get("coords")
        if not coords:
            return {"status": "INVALID_REQUEST"}

        valid = []

        async with self._lock:
            for (x, z) in coords:
                inside = False
                for a in self.flat_areas:
                    if self._point_in_rect(x, z, a["rect"]):
                        inside = True
                        break

                if not inside:
                    valid.append((x, z))

        if not valid:
            return {
                "status": "AREA_OCCUPIED",
                "valid_coords": []
            }

        if len(valid) == len(coords):
            return {
                "status": "AREA_FREE",
                "valid_coords": coords
            }

        return {
            "status": "AREA_PARTIAL",
            "valid_coords": valid
        }

                
    # ---------------------------------------------------------
    # Control Overloads
    # ---------------------------------------------------------
    async def status(self):
        """Imprime el estado actual del bot en el logger"""
        info = {
            "areas": self.flat_areas,
            "messages": self._inbox,
        }
        logger.info("[WORLDSTATE STATUS] %s", info)