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
    PUBLISH_INTERVAL = 1.0

    def __init__(self, agent_id="ExplorerBot", bus=None):
        super().__init__(agent_id, bus)
        self.center: Tuple[int, int] = (0, 0)
        self.range: int = 30
        self._last_publish: float = 0.0
        self._queued_request: Optional[Tuple[int, int, int]] = None
        self.terrain = TerrainAPI()
        self.occupied = set()
        self.cube_size = 3

        # Estrategia por defecto
        self.search_strategy = search_random

        if bus:
            bus.subscribe("command.explorer.start.v1", self._on_start_cmd)
            bus.subscribe("command.explorer.set.v1", self._on_update_cmd)
            bus.subscribe("command.explorer.pause.v1", self._on_control)
            bus.subscribe("command.explorer.resume.v1", self._on_control)
            bus.subscribe("command.explorer.stop.v1", self._on_control)
            bus.subscribe("command.explorer.update.v1", self._on_control)
            bus.subscribe("*", self._on_generic)

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
        x = int(payload.get("x", 0))
        z = int(payload.get("z", 0))
        r = int(payload.get("range", self.range))
        cube = int(payload.get("cube", self.cube_size))

        logger.info("[EXPLORER] Start request: x=%s z=%s range=%s cube=%s", x, z, r, cube)

        # If the bot is running, queue new scan
        if self.state == AgentState.RUNNING:
            logger.info("[EXPLORER] Queuing new request until current scan finishes")
            self._queued_request = (x, z, r, cube)
        else:
            self.center = (x, z)
            self.range = r
            self.cube = cube
            await self.start()

    async def _on_update_cmd(self, msg: Dict[str, Any]):
        """Handle `explorer set` command with optional parameters in payload."""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})

        # Actualizar rango si viene en payload
        if "range" in payload:
            self.range = int(payload["range"])

        # Actualizar tamaño del cubo si viene en payload
        if "cube" in payload:
            self.cube_size = int(payload["cube"])

        # Actualizar estrategia si viene en payload
        if "strategy" in payload:
            self.set_strategy(payload["strategy"])

        # Llamar a update del BaseAgent para cualquier otro parámetro general
        await self.update(payload)


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
        elif cmdtype.endswith(".update.v1"):
            await self.update(msg.get("payload", {}))

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
        """Detect flat areas by checking neighboring heights and ignoring occupied zones."""
        height_map = percept["height_map"]
        flat_spots = []
        cube_half = self.cube_size // 2

        for (x, z), h0 in height_map.items():
            is_flat = True
            # Comprobar vecinos dentro de cube_size x cube_size
            for dx in range(-cube_half, cube_half + 1):
                for dz in range(-cube_half, cube_half + 1):
                    nx, nz = x + dx, z + dz
                    if (nx, nz) in self.occupied or height_map.get((nx, nz), None) != h0:
                        is_flat = False
                        break
                if not is_flat:
                    break

            if is_flat:
                flat_spots.append({"x": x, "z": z})
                # marcar todas las coordenadas de esta zona como ocupadas
                for dx in range(-cube_half, cube_half + 1):
                    for dz in range(-cube_half, cube_half + 1):
                        self.occupied.add((x + dx, z + dz))

        return {
            "flat_areas": flat_spots,
            "count": len(flat_spots),
            "cube_size": self.cube_size
        }

    async def act(self, decision: Dict[str, Any]):
        """Publish map.v1 periodically, handle queued requests, and build cubes."""
        now = time.time()

        # --- NUEVO: construir cubos ---
        flats = decision.get("flat_areas", [])
        for area in flats:
            x, z = area["x"], area["z"]
            logger.info(f"[EXPLORER] Construyendo cubo en zona plana ({x},{z})")
            await self._build_cube(x, z, block_id=20)

        # --- publicar como siempre ---
        if now - self._last_publish >= ExplorerBot.PUBLISH_INTERVAL:
            await self._publish_map(decision)
            self._last_publish = now

        # --- manejar peticiones nuevas ---
        if self._queued_request:
            (x, z, r, cube) = self._queued_request
            self._queued_request = None
            self.center = (x, z)
            self.range = r
            self.cube_size = cube
            logger.info("[EXPLORER] Switching to queued request: (%s,%s) r=%s cube=%s", x, z, r, cube)
        else:
            logger.info("[EXPLORER] Exploration completed. Marking as FINISHED.")
            await self.stop()




    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    async def _build_cube(self, x: int, z: int, block_id: int = 20):
        """
        Construye un cubo sólido tamaño NxNxN sobre la posición plana detectada.
        `block_id=1` = Stone por defecto.
        """
        # y = altura del terreno en ese punto
        y = self.terrain.get_height(x, z)

        half = self.cube_size // 2
        for dx in range(-half, half + 1):
            for dy in range(0, self.cube_size):
                for dz in range(-half, half + 1):
                    bx = x + dx
                    by = y + dy
                    bz = z + dz
                    self.terrain.set_block(bx, by, bz, block_id)
                    self.occupied.add((bx, bz))
                    await asyncio.sleep(0)   # yield control

    async def _publish_map(self, decision: Dict[str, Any]):
        msg = {
            "type": "map.v1",
            "source": self.agent_id,
            "target": "BuilderBot",
            "payload": decision,
            "context": {
                "center": self.center,
                "range": self.range,
                "state": self.state.value,
            },
        }
        if self.bus:
            await self.bus.publish(msg)

        logger.info("[EXPLORER] Published map.v1")

    # ---------------------------------------------------------
    # Control Overloads
    # ---------------------------------------------------------
    async def update(self, params: Dict[str, Any]):
        """Allow updating center, range, etc."""
        if "x" in params and "z" in params:
            self.center = (int(params["x"]), int(params["z"]))
        if "range" in params:
            self.range = int(params["range"])
        await super().update(params)

    async def stop(self):
        logger.info("[EXPLORER] Stopping ExplorerBot, saving checkpoint")
        await super().stop()

    async def save_checkpoint(self):
        logger.info("[CHECKPOINT] ExplorerBot saved: center=%s range=%s", self.center, self.range)
    
    async def status(self):
        """Devuelve el estado actual del bot"""
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "center": self.center,
            "range": self.range,
            "cube_size": self.cube_size,
            "strategy": self.search_strategy.__name__,
        }

