# agents/explorer/explorer_bot.py
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
import sys
import os

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
    """
    ExplorerBot:

    - Escanea una región (x/z + rango)
    - Calcula varianza de alturas por sub-zonas
    - Detecta áreas planas
    - Publica mensajes map.v1
    - Responde a control messages
    - Permite reconfiguración dinámica (update)
    - Respeta el modelo de estado del enunciado
    """

    SCAN_DELAY = 0.05  # delay entre lecturas de altura
    PUBLISH_INTERVAL = 1.0

    def __init__(self, agent_id="ExplorerBot", bus=None, terrain_api=None):
        super().__init__(agent_id, bus)
        self.center: Tuple[int, int] = (0, 0)       # (x, z)
        self.range: int = 30                        # default range
        self._scan_results: Dict[str, Any] = {}
        self._last_publish: float = 0.0
        self._queued_request: Optional[Tuple[int, int, int]] = None  # (x,z,range)
        self.terrain = terrain_api or TerrainAPI()

        # Subscribe to messages
        if bus:
            bus.subscribe("command.explorer.start.v1", self._on_start_cmd)
            bus.subscribe("command.explorer.set.v1", self._on_update_cmd)
            bus.subscribe("command.*.v1", self._on_control)
            bus.subscribe("*", self._on_generic)

    # ---------------------------------------------------------
    # Message handlers
    # ---------------------------------------------------------
    async def _on_start_cmd(self, msg: Dict[str, Any]):
        """Handle `/explorer start x=... z=... range=...`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return


        payload = msg.get("payload", {})
        x = int(payload.get("x", 0))
        z = int(payload.get("z", 0))
        r = int(payload.get("range", self.range))

        if "cube" in payload:
            self.cube_size = int(payload["cube"])
        else:
            self.cube_size = 5  # default

        logger.info("[EXPLORER] Start request: x=%s z=%s range=%s cube=%s", x, z, r, self.cube_size)

        # If the bot is running, queue new scan
        if self.state == AgentState.RUNNING:
            logger.info("[EXPLORER] Queuing new request until current scan finishes")
            self._queued_request = (x, z, r)
        else:
            self.center = (x, z)
            self.range = r
            await self.start()

    async def _on_update_cmd(self, msg: Dict[str, Any]):
        """Handle `/explorer set range N`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        if "range" in payload:
            self.range = int(payload["range"])
            logger.info("[EXPLORER] Range updated to %s", self.range)

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
    async def perceive(self) -> Dict[str, Any]:
        """Scan only needed positions for diagonal flat-area detection."""
        await asyncio.sleep(0)

        x0, z0 = self.center
        r = self.range

        # No leemos todo el rango; solo apuntamos a posiciones candidatas.
        candidates = []

        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):

                # Guardamos todos los puntos para probarlos en `decide`
                candidates.append((x0 + dx, z0 + dz))

                await asyncio.sleep(self.SCAN_DELAY)

        return {"candidates": candidates}

    async def decide(self, percept: Dict[str, Any]) -> Dict[str, Any]:
        """Detect flat cube-sized areas using diagonal check logic."""

        candidates = percept["candidates"]
        flat_spots = []

        for (x, z) in candidates:
            if self._is_flat_area(x, z):
                flat_spots.append({"x": x, "z": z})

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
            await self._build_cube(x, z, size=3, block_id=1)

        # --- publicar como siempre ---
        if now - self._last_publish >= ExplorerBot.PUBLISH_INTERVAL:
            await self._publish_map(decision)
            self._last_publish = now

        # --- manejar peticiones nuevas ---
        if self._queued_request:
            (x, z, r) = self._queued_request
            self._queued_request = None
            self.center = (x, z)
            self.range = r
            logger.info("[EXPLORER] Switching to queued request: (%s,%s) r=%s", x, z, r)


    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    async def _build_cube(self, x: int, z: int, size: int = 3, block_id: int = 1):
        """
        Construye un cubo sólido tamaño NxNxN sobre la posición plana detectada.
        `block_id=1` = Stone por defecto.
        """
        # y = altura del terreno en ese punto
        y = self.terrain.get_height(x, z)

        half = size // 2
        for dx in range(-half, half + 1):
            for dy in range(0, size):
                for dz in range(-half, half + 1):
                    bx = x + dx
                    by = y + dy
                    bz = z + dz
                    self.terrain.set_block(bx, by, bz, block_id)
                    await asyncio.sleep(0)   # yield control

    def _is_flat_area(self, x0, z0):
        half = self.cube_size // 2
        h0 = self.terrain.get_height(x0, z0)

        # Revisar diagonales desde la más exterior hasta la más interior
        for d in range(1, half + 1):
            check_positions = [
                (x0 + d, z0 + d),
                (x0 + d, z0 - d),
                (x0 - d, z0 + d),
                (x0 - d, z0 - d),
            ]

            for x, z in check_positions:
                if (x, z) in getattr(self, "occupied", set()):
                    return False
                if self.terrain.get_height(x, z) != h0:
                    return False

        return True


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
