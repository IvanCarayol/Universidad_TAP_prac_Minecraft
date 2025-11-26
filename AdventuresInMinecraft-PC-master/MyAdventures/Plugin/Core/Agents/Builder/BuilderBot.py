# agents/builder/builder_bot.py

import asyncio
import time
from typing import Dict, Any, Optional, List

from core.agent_base import BaseAgent, AgentState
from core.logging_config import get_logger

logger = get_logger(__name__)


# ============================================================
# Utility: simple templates
# These would normally be loaded from JSON files in templates/
# ============================================================
TEMPLATES = {
    "house_small": {
        "materials": {"wood": 10, "stone": 5},
        "height": 3,
        "width": 4,
        "depth": 4,
    },
    "tower": {
        "materials": {"stone": 20},
        "height": 6,
        "width": 3,
        "depth": 3,
    }
}


# ============================================================
# BuilderBot
# ============================================================
class BuilderBot(BaseAgent):
    """
    BuilderBot:
      - Recibe mapa desde ExplorerBot (map.v1).
      - Calcula BOM según plantilla.
      - Se coordina con MinerBot.
      - Espera materiales.
      - Construye estructura capa a capa.
      - Emite build.v1 updates.
    """

    BUILD_INTERVAL = 0.3  # delay between layers during construction

    def __init__(self, agent_id="BuilderBot", bus=None):
        super().__init__(agent_id, bus)
        self._last_map: Optional[Dict[str, Any]] = None
        self._template_name: str = "house_small"
        self._bom: Optional[Dict[str, int]] = None
        self._material_inventory: Dict[str, int] = {}
        self._build_progress = 0
        self._build_plan: Optional[List[Dict[str, Any]]] = None  # layers to build

        # Subscribe to incoming messages
        if bus:
            #bus.subscribe("map.v1", self._on_map)
            bus.subscribe("inventory.v1", self._on_inventory)
            bus.subscribe("command.*.v1", self._on_command_message)
            bus.subscribe("*", self._on_generic_message)

    # ---------------------------------------------------------
    # Message handlers
    # ---------------------------------------------------------
    async def _on_map(self, msg: Dict[str, Any]):
        """Receive map from ExplorerBot."""
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info("[MAP] Received map from %s", msg.get("source"))
        self._last_map = msg["payload"]

        # Recompute BOM & publish it
        await self._compute_and_send_bom()

    async def _on_inventory(self, msg: Dict[str, Any]):
        """Receive updated inventory from MinerBot."""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        if not isinstance(payload, dict):
            logger.error("[INVENTORY] Invalid payload: %s", payload)
            return

        logger.info("[INVENTORY] Received updated materials: %s", payload)
        self._material_inventory = payload

    async def _on_command_message(self, msg: Dict[str, Any]):
        """Control messages: pause/resume/stop/update"""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        cmd = msg.get("type", "")
        payload = msg.get("payload", {})

        if cmd.endswith(".pause.v1"):
            await self.pause()
        elif cmd.endswith(".resume.v1"):
            await self.resume()
        elif cmd.endswith(".stop.v1"):
            await self.stop()
        elif cmd.endswith(".update.v1"):
            await self.update(payload)
        else:
            return

    async def _on_generic_message(self, msg: Dict[str, Any]):
        """Optional message tap for debugging."""
        return

    # ---------------------------------------------------------
    # PDA implementation
    # ---------------------------------------------------------
    async def perceive(self) -> Dict[str, Any]:
        """Observe world state (map, inventory, plan, template)."""
        await asyncio.sleep(0)
        return {
            "map": self._last_map,
            "inventory": dict(self._material_inventory),
            "bom": dict(self._bom) if self._bom else None,
            "template": self._template_name,
            "build_progress": self._build_progress,
        }

    async def decide(self, percept: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decide between:
         - NO MAP → WAIT
         - BOM incomplete → WAIT
         - Enough materials → BUILD NEXT LAYER
         - Completed all layers → FINISH
        """
        if percept["map"] is None:
            return {"action": "wait_for_map"}

        if percept["bom"] is None:
            return {"action": "compute_bom"}

        # Check material fulfillment
        if not self._materials_ready(percept["bom"], percept["inventory"]):
            return {"action": "wait_for_materials"}

        # Initialize build plan if needed
        if self._build_plan is None:
            await self._make_build_plan()

        # All layers built?
        if self._build_progress >= len(self._build_plan):
            return {"action": "finish_building"}

        return {"action": "build_layer"}

    async def act(self, decision: Dict[str, Any]):
        action = decision["action"]

        if action == "wait_for_map":
            logger.info("[BUILDER] Waiting for map...")
            await asyncio.sleep(0.3)

        elif action == "compute_bom":
            await self._compute_and_send_bom()

        elif action == "wait_for_materials":
            logger.info("[BUILDER] Waiting for materials...")
            self.set_state(AgentState.WAITING, "Insufficient materials")
            await asyncio.sleep(0.5)

        elif action == "build_layer":
            self.set_state(AgentState.RUNNING, "Building layer")
            await self._build_next_layer()

        elif action == "finish_building":
            logger.info("[BUILDER] Construction completed")
            await self._publish_build_status("COMPLETED", final=True)
            self._reset_after_build()

    # ---------------------------------------------------------
    # BOM & Planning
    # ---------------------------------------------------------
    async def _compute_and_send_bom(self):
        """Compute BOM from template and publish it."""
        if self._template_name not in TEMPLATES:
            logger.error("Unknown template '%s'", self._template_name)
            return

        self._bom = dict(TEMPLATES[self._template_name]["materials"])

        msg = {
            "type": "materials.requirements.v1",
            "source": self.agent_id,
            "target": "MinerBot",
            "payload": self._bom,
            "context": {"template": self._template_name},
        }
        if self.bus:
            await self.bus.publish(msg)

        logger.info("[BUILDER] Published BOM: %s", self._bom)

    def _materials_ready(self, bom: Dict[str, int], inv: Dict[str, int]) -> bool:
        for mat, qty in bom.items():
            if inv.get(mat, 0) < qty:
                return False
        return True

    async def _make_build_plan(self):
        """Generate list of layers to build."""
        tpl = TEMPLATES[self._template_name]
        height = tpl["height"]
        width = tpl["width"]
        depth = tpl["depth"]

        self._build_plan = []
        for y in range(height):
            layer = {"y": y, "blocks": []}
            for x in range(width):
                for z in range(depth):
                    layer["blocks"].append({"x": x, "y": y, "z": z, "material": "stone"})
            self._build_plan.append(layer)

        logger.info("[BUILDER] Build plan generated with %d layers", height)

    # ---------------------------------------------------------
    # Building
    # ---------------------------------------------------------
    async def _build_next_layer(self):
        layer = self._build_plan[self._build_progress]
        y = layer["y"]

        logger.info("[BUILD] Building layer %d (%d blocks)", y, len(layer["blocks"]))

        # Simulate block placements
        for block in layer["blocks"]:
            # Real implementation would call mcpi: mc.setBlock(...)
            await asyncio.sleep(0.01)

        self._build_progress += 1

        await self._publish_build_status("LAYER_DONE", final=False)

    async def _publish_build_status(self, status: str, final: bool = False):
        msg = {
            "type": "build.v1",
            "source": self.agent_id,
            "target": "*",
            "payload": {
                "status": status,
                "progress": self._build_progress,
            },
            "context": {
                "template": self._template_name,
                "state": self.state.value,
            },
        }
        if self.bus:
            await self.bus.publish(msg)

        logger.info("[BUILD] Status published: %s", status)

        if final:
            await self.save_checkpoint()

    # ---------------------------------------------------------
    # Control commands
    # ---------------------------------------------------------
    async def update(self, params: Dict[str, Any]):
        """Runtime reconfiguration (change template, reset plan...)."""
        if "template" in params:
            name = params["template"]
            if name in TEMPLATES:
                self._template_name = name
                self._build_progress = 0
                self._build_plan = None
                logger.info("[BUILDER] Template changed to '%s'", name)
                await self._compute_and_send_bom()
        await super().update(params)

    async def stop(self):
        logger.info("[BUILDER] Stopping BuilderBot, saving checkpoint")
        await super().stop()

    async def save_checkpoint(self):
        logger.info("[CHECKPOINT] BuilderBot saved: template=%s progress=%s",
                    self._template_name, self._build_progress)

    # ---------------------------------------------------------
    # Reset Builder after completion
    # ---------------------------------------------------------
    def _reset_after_build(self):
        self._build_progress = 0
        self._build_plan = None
        self._bom = None
        self._material_inventory = {}
        self.set_state(AgentState.IDLE, "build done")
