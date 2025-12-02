import asyncio
from ...Core.Agents.BaseAgent import BaseAgent
from ...Core.Logger.logging_config import get_logger

logger = get_logger(__name__)


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
        self.bus.subscribe("savearea.v1", self.on_message)
        self.bus.subscribe("requestarea.v1", self.on_message)
        self.bus.subscribe("lockarea.v1", self.on_message)
        self.bus.subscribe("getareas.v1", self.on_message)

    # ----------------------
    # Manejo de mensajes
    # ----------------------
    async def _on_start_cmd(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info("[WORLDSTATE] Start worldstate bot")
        await self.start()

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
            return ("ADD_AREA", rect)

        elif mtype == "requestarea.v1":
            required = payload.get("required")
            return ("ALLOCATE_AREA", sender, required)

        elif mtype == "lockarea.v1":
            rect = payload.get("rect")
            status = payload.get("status", "LOCKED")
            return ("UPDATE_AREA", rect, status)

        elif mtype == "getareas.v1":
            return ("RETURN_ALL", sender)

        else:
            return ("UNKNOWN", sender, msg)

    # ----------------------
    # ACT
    # ----------------------
    async def act(self, decision):
        action = decision[0]

        if action == "ADD_AREA":
            rect = decision[1]
            await self._add_flat_area(rect)
            logger.info("[WORLDSTATE] Staved flat area")

        elif action == "ALLOCATE_AREA":
            sender, required = decision[1], decision[2]
            result = await self._request_area(sender, required)
            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": result
            })

        elif action == "UPDATE_AREA":
            rect, status = decision[1], decision[2]
            await self._mark_area_status(rect, status)

        elif action == "RETURN_ALL":
            sender = decision[1]
            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": {
                    "areas": self.flat_areas
                }
            })

        elif action == "UNKNOWN":
            sender, msg = decision[1], decision[2]
            await self.bus.publish({
                "type": "worldstate.response",
                "source": self.agent_id,
                "target": sender,
                "payload": {
                    "error": f"[WorldStateBot] Mensaje desconocido: {msg}"
                }
            })

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


    async def _mark_area_status(self, rect, status):
        async with self._lock:
            for a in self.flat_areas:
                if a["rect"] == rect:
                    a["status"] = status
                    return
