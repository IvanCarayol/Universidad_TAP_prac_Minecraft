# agents/explorer/explorer_bot.py
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
import sys
import os

from ..Strategies.explorer_strategies import search_line, search_spiral, search_random
from ..BaseAgent import BaseAgent, AgentState
from ...Logger.logging_config import get_logger

sys.path.append(os.path.join(os.path.dirname(__file__), "Core"))

logger = get_logger(__name__)

# ============================================================
# ExplorerBot Implementation
# ============================================================
class ExplorerBot(BaseAgent):
    SCAN_DELAY = 0.01

    def __init__(self, agent_id="ExplorerBot", bus=None, mc=None):
        super().__init__(agent_id, bus)
        self.center: Tuple[int, int] = (0, 0)
        self.range: int = 30
        self._last_publish: float = 0.0
        self._queued_request: Optional[Tuple[int, int, int, int]] = None
        self.mc = mc
        self.occupied = set()
        self.bus = bus

        # Estrategia por defecto
        self.search_strategy = search_random

        self.bus.subscribe("command.explorer.start.v1", self._on_start_cmd)
        self.bus.subscribe("command.explorer.set.v1", self._on_update_cmd)
        self.bus.subscribe("command.explorer.pause.v1", self._on_control)
        self.bus.subscribe("command.explorer.resume.v1", self._on_control)
        self.bus.subscribe("command.explorer.stop.v1", self._on_control)
        self.bus.subscribe("command.explorer.status.v1", self._on_control)
        self.bus.subscribe("*", self._on_generic)

    def set_strategy(self, strategy_name: str):
        strategies = {
            "line": search_line,
            "spiral": search_spiral,
            "random": search_random
        }
        if strategy_name in strategies:
            self.search_strategy = strategies[strategy_name]

    async def _yield_scan(self):
        await asyncio.sleep(self.SCAN_DELAY)

    # ---------------------------------------------------------
    # Message handlers
    # ---------------------------------------------------------
    async def _on_start_cmd(self, msg: Dict[str, Any]):
        """Handle `explorer start x=... z=... range=...`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        x = int(payload.get("x", self.center[0]))
        z = int(payload.get("z", self.center[1]))
        r = int(payload.get("range", self.range))

        logger.info("[EXPLORER] Start request: x=%s z=%s range=%s", x, z, r)

        # If the bot is running, queue new scan
        if self.state == AgentState.RUNNING:
            logger.info("[EXPLORER] Queuing new request until current scan finishes")
            self._queued_request = (x, z, r)
        else:
            self.center = (x, z)
            self.range = r
            await self.start()

    async def _on_update_cmd(self, msg: Dict[str, Any]):
        """Handle `explorer set` command with optional parameters in payload."""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})

        # Actualizar rango si viene en payload
        if "range" in payload:
            self.range = int(payload["range"])

        # Actualizar estrategia si viene en payload
        if "strategy" in payload:
            self.set_strategy(payload["strategy"])

        # Llamar a update del BaseAgent para logger
        await super().update(payload)


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
        elif cmdtype.endswith(".status.v1"):
            await self.status()

    async def _on_generic(self, msg: Dict[str, Any]):
        # Debug tap for other messages
        return

    # ---------------------------------------------------------
    # PDA Methods
    # ---------------------------------------------------------
    async def perceive(self):
        """
        Percibe un bloque válido a la vez.
        Mantiene una cola interna de coordenadas válidas.
        """
        if not hasattr(self, "_pending_coords") or not self._pending_coords:
            # Inicializar o recargar coordenadas
            x0, z0 = self.center
            r = self.range
            candidates = await self.search_strategy(self, x0, z0, r)
            validation = await self.validate_coords(candidates)

            if not validation:
                logger.warning("[EXPLORER] WorldStateBot no respondió")
                return None

            status = validation["status"]
            valid_coords = validation["valid_coords"]

            if status == "AREA_OCCUPIED":
                logger.info("[EXPLORER] Área completamente ocupada, abortando exploración")
                return None

            self._pending_coords = valid_coords.copy()
            self._height_map = {}  # reset del mapa de alturas
            logger.info(
                f"[EXPLORER] Validación: {status} "
                f"({len(valid_coords)}/{len(candidates)} coords válidas)"
            )

        # Percibir un bloque de la cola
        coord = self._pending_coords.pop(0)
        x, z = coord
        h = self.mc.getHeight(x, z)
        self._height_map[coord] = h
        logger.info(f"[EXPLORER] Percibiendo coordenadas ({x},{z}) con altura {h}")

        await asyncio.sleep(self.SCAN_DELAY)

        return {"coord": coord, "height": h}

    async def decide(self, percept):
        """
        Acumula los bloques percibidos y solo devuelve el rectángulo
        cuando ya se hayan percibido todos los bloques.
        """
        # Si todavía hay bloques pendientes, no devolvemos nada
        if hasattr(self, "_pending_coords") and self._pending_coords:
            return None

        # Construimos el rectángulo a partir de self._height_map
        height_map = getattr(self, "_height_map", {})
        if not height_map:
            return {"best_rectangle": None}

        # --- mismo código de antes para calcular el mejor rectángulo ---
        levels = {}
        for (x, z), h in height_map.items():
            levels.setdefault(h, []).append((x, z))

        best_rect = None

        for h, coords in levels.items():
            xs = sorted(set([c[0] for c in coords]))
            zs = sorted(set([c[1] for c in coords]))
            x_index = {x: i for i, x in enumerate(xs)}
            z_index = {z: i for i, z in enumerate(zs)}
            grid = [[0] * len(zs) for _ in range(len(xs))]
            for (x, z) in coords:
                grid[x_index[x]][z_index[z]] = 1
            matrix = list(zip(*grid))
            rect = self._largest_rectangle_in_matrix(matrix)
            if rect is None:
                continue
            area, (z1_i, x1_i), (z2_i, x2_i) = rect
            x1, x2 = xs[x1_i], xs[x2_i]
            z1, z2 = zs[z1_i], zs[z2_i]
            if best_rect is None or area > best_rect[0]:
                best_rect = (area, x1, z1, x2, z2, h)

        if best_rect:
            area, x1, z1, x2, z2, h = best_rect
            return {
                "best_rectangle": {
                    "x1": x1,
                    "z1": z1,
                    "x2": x2,
                    "z2": z2,
                    "width": abs(x2 - x1) + 1,
                    "height": abs(z2 - z1) + 1,
                    "area": area,
                    "y": h
                }
            }

        return {"best_rectangle": None}

    async def act(self, decision):
        # --- 0. Si no hay decision, significa que todavía quedan bloques pendientes ---
        if decision is None:
            # No hacemos nada, volverá a llamar a perceive para el siguiente bloque
            return

        rect = decision.get("best_rectangle")

        # --- 1. No hay rectángulo válido tras percibir todos los bloques ---
        if rect is None:
            logger.info("[EXPLORER] No se encontró ningún rectángulo válido tras explorar todos los bloques")
            await self._publish_map(None)
            await self._handle_next_or_idle()
            # Limpiar memoria interna
            self._pending_coords = []
            self._height_map = {}
            return

        # --- 2. Logging del rectángulo encontrado ---
        logger.info(
            f"[EXPLORER] Mejor rectángulo: "
            f"({rect['x1']},{rect['z1']}) → ({rect['x2']},{rect['z2']}), "
            f"area={rect['area']}, y={rect['y']}"
        )

        # --- 3. Guardar área en WorldState ---
        result = await self.save_area_clean(rect)

        if result is None:
            logger.warning("[EXPLORER] No response from WorldStateBot (timeout)")
        elif result.get("status") != "OK":
            logger.info(f"[EXPLORER] WorldStateBot rechazó el área: {result}")
        else:
            logger.info("[EXPLORER] Área guardada correctamente en WorldState")
            await self._publish_map(rect)

        # --- 4. Continuar flujo normal ---
        await self._handle_next_or_idle()

        # --- 5. Limpiar memoria interna ---
        self._pending_coords = []
        self._height_map = {}


    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _largest_rectangle_hist(self, heights):
        """Largest rectangle in histogram algorithm."""
        stack = []
        max_area = 0
        left = right = 0

        heights.append(0)
        for i, h in enumerate(heights):
            start = i
            while stack and stack[-1][1] > h:
                index, height = stack.pop()
                area = height * (i - index)
                if area > max_area:
                    max_area = area
                    left = index
                    right = i - 1
                start = index
            stack.append((start, h))
        heights.pop()

        return max_area, left, right


    def _largest_rectangle_in_matrix(self, matrix):
        """
        Encuentra el mayor rectángulo de 1s en una matriz binaria.
        matrix[fila=z][columna=x]
        """
        if not matrix:
            return None

        rows = len(matrix)
        cols = len(matrix[0])
        heights = [0] * cols

        best = None  # (area, (z1,x1), (z2,x2))

        for z in range(rows):
            for x in range(cols):
                heights[x] = heights[x] + 1 if matrix[z][x] == 1 else 0

            area, x1, x2 = self._largest_rectangle_hist(heights)
            if area > 0:
                height = area // (x2 - x1 + 1)
                z2 = z
                z1 = z - height + 1

                if best is None or area > best[0]:
                    best = (area, (z1, x1), (z2, x2))

        return best

    async def _publish_map(self, rect: Optional[Dict[str, Any]]):
        """
        Publica el resultado para BuilderBot en formato limpio.
        rect = None o un dict con x1,z1,x2,z2,area,width,height,y
        """
        msg = {
            "type": "map.v1",
            "source": self.agent_id,
            "target": "BuilderBot",
            "payload": {
                "best_rectangle": rect,
            },
            "context": {
                "center": self.center,
                "range": self.range,
                "state": self.state.value,
            },
        }

        await self.bus.publish(msg)

        if rect:
            logger.info(
                f"[EXPLORER] Published map.v1 (rect area={rect['area']}, "
                f"coords=({rect['x1']},{rect['z1']})→({rect['x2']},{rect['z2']}))"
            )
        else:
            logger.info("[EXPLORER] Published map.v1 (no rectangle found)")

    async def _handle_next_or_idle(self):
        if self._queued_request:
            x, z, r = self._queued_request
            self._queued_request = None
            self.center = (x, z)
            self.range = r
            logger.info(
                f"[EXPLORER] Switching to queued request: ({x},{z}) r={r}"
            )
        else:
            await self.idle()

    # ---------------------------------------------------------
    # Funciones para comunicacion con WorldstateBot
    # ---------------------------------------------------------
    async def validate_coords(self, coords, timeout=5.0):
        future = asyncio.get_event_loop().create_future()

        async def _temp(msg):
            if msg.get("type") != "worldstate.response":
                return
            if msg.get("target") not in (self.agent_id, "*"):
                return

            payload = msg.get("payload", {})
            if "status" in payload and not future.done():
                future.set_result(payload)

        self.bus.subscribe("worldstate.response", _temp)

        await self.bus.publish({
            "type": "validatecoords.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": {
                "coords": coords
            }
        })

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self.bus.unsubscribe("worldstate.response", _temp)

    async def save_area_clean(self, rect: dict, timeout=5.0):
        """
        Envía un mensaje savearea.v1 a WorldStateBot y espera
        una respuesta worldstate.response dirigida a este bot.
        """

        future = asyncio.get_event_loop().create_future()

        # --- callback temporal para esta respuesta ---
        async def _temp(msg):
            if msg.get("type") != "worldstate.response":
                return
            if msg.get("target") not in (self.agent_id, "*"):
                return

            payload = msg.get("payload", {})
            if not future.done():
                future.set_result(payload)

        # Suscripción temporal
        self.bus.subscribe("worldstate.response", _temp)

        # Enviar solicitud
        await self.bus.publish({
            "type": "savearea.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": {
                "rect": rect
            }
        })

        try:
            # Esperar respuesta
            result = await asyncio.wait_for(future, timeout=timeout)
            return result  # puede contener {"status": "..."} u otros datos

        except asyncio.TimeoutError:
            return None
        
        finally:
            # liberar suscripción temporal
            self.bus.unsubscribe("worldstate.response", _temp)

    # ---------------------------------------------------------
    # Control Overloads
    # ---------------------------------------------------------
    async def stop(self):
        await super().stop()

    async def pause(self):
        await super().pause()

    async def resume(self):
        await super().resume()

    async def idle(self):
        await super().idle()

    async def save_checkpoint(self):
        logger.info("[CHECKPOINT] ExplorerBot saved: center=%s range=%s", self.center, self.range)
    
    async def status(self):
        """Imprime el estado actual del bot en el logger"""
        info = {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "center": self.center,
            "range": self.range,
            "strategy": self.search_strategy.__name__,
        }
        logger.info("[EXPLORER STATUS] %s", info)


