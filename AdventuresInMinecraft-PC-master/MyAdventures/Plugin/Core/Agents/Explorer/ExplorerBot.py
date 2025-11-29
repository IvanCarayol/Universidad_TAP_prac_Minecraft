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
# Optional MCPI wrapper for getHeight (real or mocked)
# ============================================================
class TerrainAPI:
    """
    Wrapper around mcpi.getHeight(x,z) and setBlock.
    """
    def __init__(self, mc=None):
        self.mc = mc

    def get_height(self, x: int, z: int) -> int:
        return self.mc.getHeight(x, z)

    def set_block(self, x: int, y: int, z: int, block_id: int):
        self.mc.setBlock(x, y, z, block_id)

# ============================================================
# ExplorerBot Implementation
# ============================================================
class ExplorerBot(BaseAgent):
    SCAN_DELAY = 0.01

    def __init__(self, agent_id="ExplorerBot", bus=None):
        super().__init__(agent_id, bus)
        self.center: Tuple[int, int] = (0, 0)
        self.range: int = 30
        self._last_publish: float = 0.0
        self._queued_request: Optional[Tuple[int, int, int, int]] = None
        self.terrain = TerrainAPI()
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

        logger.info("[EXPLORER] Start request: x=%s z=%s range=%s cube=%s", x, z, r)

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
    async def perceive(self) -> Dict[str, any]:
        x0, z0 = self.center
        r = self.range

        # coords según la estrategia seleccionada
        candidates = await self.search_strategy(self, x0, z0, r)

        # construir height_map
        height_map = {}
        for x, z in candidates:
            h = self.terrain.get_height(x, z)
            height_map[(x, z)] = h
            logger.info(f"[EXPLORER] Perciviendo coordenadas ({x},{z}) con altura {h}")
            await asyncio.sleep(self.SCAN_DELAY)

        return {"height_map": height_map}

    async def decide(self, percept: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detecta el rectángulo más grande para cualquier altura encontrada.
        Devuelve: { x1, z1, x2, z2, height, width, area }
        """
        height_map = percept["height_map"]

        # Agrupar coordenadas por altura
        levels = {}
        for (x, z), h in height_map.items():
            levels.setdefault(h, []).append((x, z))

        best_rect = None  # (area, x1, z1, x2, z2, height_level)

        # Procesar altura por altura
        for h, coords in levels.items():
            # Construir grid local
            xs = sorted(set([c[0] for c in coords]))
            zs = sorted(set([c[1] for c in coords]))

            x_index = {x: i for i, x in enumerate(xs)}
            z_index = {z: i for i, z in enumerate(zs)}

            grid = [[0] * len(zs) for _ in range(len(xs))]

            for (x, z) in coords:
                grid[x_index[x]][z_index[z]] = 1

            # Convertir en "matriz por filas"
            matrix = list(zip(*grid))  # filas = z, columnas = x

            # Buscar mayor rectángulo
            rect = self._largest_rectangle_in_matrix(matrix)

            if rect is None:
                continue

            area, (z1_i, x1_i), (z2_i, x2_i) = rect

            # Convertir indices a coords reales
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

    async def act(self, decision: Dict[str, Any]):
        """
        Publica map.v1, muestra logs correctos y gestiona peticiones en cola.
        El decision contiene:
        {
            "best_rectangle": {
                x1, z1, x2, z2, width, height, area, y
            }
        }
        """
        rect = decision.get("best_rectangle")

        if rect is None:
            logger.info("[EXPLORER] No se ha encontrado ninguna zona plana utilizable.")
        else:
            logger.info(
                f"[EXPLORER] Mejor rectángulo encontrado: "
                f"({rect['x1']},{rect['z1']}) → ({rect['x2']},{rect['z2']}), "
                f"area={rect['area']} bloques, altura={rect['y']}"
            )

        # Publicar resultados
        await self._publish_map(rect)

        # Manejar siguiente petición si existe
        if self._queued_request:
            x, z, r = self._queued_request
            self._queued_request = None

            self.center = (x, z)
            self.range = r

            logger.info(
                "[EXPLORER] Switching to queued request: "
                f"({x},{z}) r={r}"
            )

        else:
            logger.info("[EXPLORER] Exploration completed. Going IDLE.")
            await self.idle()


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


    # ---------------------------------------------------------
    # Control Overloads
    # ---------------------------------------------------------
    async def stop(self):
        await super().stop()

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


