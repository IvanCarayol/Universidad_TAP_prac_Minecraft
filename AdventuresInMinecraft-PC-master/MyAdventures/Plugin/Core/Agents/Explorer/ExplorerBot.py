# agents/explorer/explorer_bot.py

import asyncio
import statistics
from typing import Dict, Any, Optional, Tuple, List

from core.agent_base import BaseAgent, AgentState
from core.logging_config import get_logger

logger = get_logger(__name__)


# ============================================================
# Optional MCPI wrapper for getHeight (real or mocked)
# ============================================================
class TerrainAPI:
    """
    Wrapper around mcpi.getHeight(x, z).
    In real implementation, inject mcpi.minecraft.Minecraft().
    """
    def __init__(self, mc=None):
        self.mc = mc

    def get_height(self, x: int, z: int) -> int:
        if self.mc:
            return self.mc.getHeight(x, z)
        # Mock fallback: pseudo height map
        return ((x * 3 + z * 7) % 5) + 64


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
        self.range: int = 6                         # default range
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
        """Scan terrain around (center, range)."""
        await asyncio.sleep(0)  # yield control

        x0, z0 = self.center
        r = self.range

        heights = []
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                h = self.terrain.get_height(x0 + dx, z0 + dz)
                heights.append({"x": x0 + dx, "z": z0 + dz, "h": h})
                await asyncio.sleep(self.SCAN_DELAY)

        return {"heights": heights}

    async def decide(self, percept: Dict[str, Any]) -> Dict[str, Any]:
        """Compute:

        - altura media
        - varianza
        - zonas planas (subgrids)
        """
        heights = percept["heights"]
        h_values = [p["h"] for p in heights]

        avg_h = sum(h_values) / len(h_values)
        var_h = statistics.pvariance(h_values) if len(h_values) > 1 else 0

        # Detect flat spots (3×3 subgrid with low variance)
        flat_areas = self._detect_flat_areas(heights)

        return {
            "average_height": avg_h,
            "variance": var_h,
            "flat_areas": flat_areas,
            "scan_size": len(heights),
        }

    async def act(self, decision: Dict[str, Any]):
        """Publish map.v1 periodically and handle queued requests."""
        now = time.time()

        if now - self._last_publish >= ExplorerBot.PUBLISH_INTERVAL:
            await self._publish_map(decision)
            self._last_publish = now

        # If scan finished a full cycle and a queued request exists → switch
        if self._queued_request:
            (x, z, r) = self._queued_request
            self._queued_request = None
            self.center = (x, z)
            self.range = r
            logger.info("[EXPLORER] Switching to queued request: (%s,%s) r=%s", x, z, r)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _detect_flat_areas(self, heights: List[Dict[str, int]]) -> List[Dict[str, Any]]:
        """Identify flat 3×3 subregions with low variance."""
        # Organize by (x,z): h
        grid = {(p["x"], p["z"]): p["h"] for p in heights}

        flat_areas = []
        # check all possible centers
        for (x, z), _ in grid.items():
            sub = []
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if (x + dx, z + dz) in grid:
                        sub.append(grid[(x + dx, z + dz)])
            if len(sub) == 9:
                var = statistics.pvariance(sub)
                if var < 0.3:  # threshold for "flat"
                    flat_areas.append({"x": x, "z": z, "variance": var})

        return flat_areas

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
