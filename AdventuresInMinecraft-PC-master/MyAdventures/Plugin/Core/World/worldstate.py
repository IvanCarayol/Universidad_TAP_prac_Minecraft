import asyncio
from Core.Agents import BaseAgent
from mcpi.event import ChatEvent

#Hacer que reciba mensajes de forma normal como el resto de bots
#Poner en percive un update de su informacion o algo como en builderbot
#Hacer que espere a la llegada de algun mensaje para despertarse si no le quedan mas
#Hacer que .send sea .bus
#Cambiar/aplicar el sistema de mensajeria a builderbot y explorerbot
#Crear un commando de start para el bot o dejarlo siempre encendido

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

        # Buffers del ciclo cognitivo
        self.perceptions = []   # mensajes recibidos
        self.decisions = []     # acciones derivadas de decide()

        self.bus.subscribe("command.worldstate.start.v1", self._on_start_cmd)
        self.bus.subscribe("command.worldstate.savearea.v1", self.on_message)
        self.bus.subscribe("command.worldstate.requestarea.v1", self.on_message)
        self.bus.subscribe("command.worldstate.lockarea.v1", self.on_message)

    async def _on_start_cmd(self, msg: Dict[str, Any]):
        """Handle `worldstate start.`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info("[WORLDSTATE] Start request")
        await self.start()

    async def on_message(self, sender, msg):
        """Recibe mensaje bruto → lo guarda como percepción"""
        self.perceptions.append((sender, msg))
        return ChatEvent.Post(self.id, f"[WorldState] Percepción recibida.")

    # ---------------------------------
    # PERCIBE: recibe mensajes de bots
    # ---------------------------------
    async def perceive(self):

        return {"height_map"}

    # ---------------------------------
    # DECIDE: interpreta percepciones
    # ---------------------------------
    async def decide(self):
        """
        Lee percepciones y decide qué acciones ejecutar.
        Las almacena en self.decisions como tuplas:
            ("ACTION_TYPE", data...)
        """

        if not self.perceptions:
            return  # nada por procesar

        for sender, msg in self.perceptions:

            if msg["type"] == "ADD_FLAT_AREA":
                self.decisions.append(("ADD_AREA", msg["rect"]))

            elif msg["type"] == "REQUEST_AREA":
                self.decisions.append(("ALLOCATE_AREA", sender, msg["required"]))

            elif msg["type"] == "MARK_AREA":
                self.decisions.append(("UPDATE_AREA", msg["rect"], msg["status"]))

            elif msg["type"] == "GET_AREAS":
                self.decisions.append(("RETURN_ALL", sender))

            else:
                self.decisions.append(("UNKNOWN", sender, msg))

        # limpiamos percepciones procesadas
        self.perceptions.clear()


    # ---------------------------------
    # ACT: ejecuta las decisiones
    # ---------------------------------
    async def act(self):
        """Procesa acciones decididas y las ejecuta realmente."""

        for decision in self.decisions:
            action = decision[0]

            # ------------------------------------
            if action == "ADD_AREA":
                rect = decision[1]
                await self._add_flat_area(rect)

            # ------------------------------------
            elif action == "ALLOCATE_AREA":
                sender, required = decision[1], decision[2]
                result = await self._request_area(sender, required)
                await self.send(sender, {
                    "type": "AREA_RESPONSE",
                    "data": result
                })

            # ------------------------------------
            elif action == "UPDATE_AREA":
                rect, status = decision[1], decision[2]
                await self._mark_area_status(rect, status)

            # ------------------------------------
            elif action == "RETURN_ALL":
                sender = decision[1]
                await self.send(sender, {
                    "type": "ALL_AREAS",
                    "areas": self.flat_areas
                })

            # ------------------------------------
            elif action == "UNKNOWN":
                sender, msg = decision[1], decision[2]
                await self.send(sender, {
                    "type": "ERROR",
                    "message": f"[WorldState] Mensaje desconocido: {msg}"
                })

        # limpiar después de actuar
        self.decisions.clear()


    # ---------------------------------
    # FUNCIONES REALES DE ESTADO
    # ---------------------------------
    async def _add_flat_area(self, rect):
        rect = normalize_rect(rect)
        area = {
            "rect": rect,
            "status": "FREE",
            "assigned_to": None
        }

        async with self._lock:
            self.flat_areas.append(area)


    async def _request_area(self, agent_id, required):
        req_w = required["width"]
        req_h = required["depth"]

        async with self._lock:
            candidates = []

            for a in self.flat_areas:
                if a["status"] != "FREE":
                    continue

                rect = a["rect"]
                if rect["width"] >= req_w and rect["height"] >= req_h:
                    candidates.append(a)

            if not candidates:
                return {"status": "NO_AREA_AVAILABLE"}

            best = max(candidates, key=lambda a: a["rect"]["area"])
            best["status"] = "RESERVED"
            best["assigned_to"] = agent_id

            return {
                "status": "OK",
                "rect": best["rect"]
            }


    async def _mark_area_status(self, rect, status):
        async with self._lock:
            for a in self.flat_areas:
                if a["rect"] == rect:
                    a["status"] = status
                    return
