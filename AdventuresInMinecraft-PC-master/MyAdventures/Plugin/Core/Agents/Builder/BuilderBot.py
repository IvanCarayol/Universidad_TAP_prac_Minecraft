# agents/builder/builder_bot.py
import asyncio
import time
from typing import Dict, Any, Optional, List

from ..BaseAgent import BaseAgent, AgentState
from ...Logger.logging_config import get_logger

logger = get_logger(__name__)

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


class BuilderBot(BaseAgent):

    BUILD_INTERVAL = 0.3

    def __init__(self, agent_id="BuilderBot", bus=None):
        super().__init__(agent_id, bus)

        self._last_map: Optional[Dict[str, Any]] = None
        self._template_name = "house_small"
        self._bom = None
        self._material_inventory = {}
        self._build_progress = 0
        self._build_plan = None

        if bus:
            bus.subscribe("map.v1", self._on_map)
            bus.subscribe("inventory.v1", self._on_inventory)
            bus.subscribe("command.*.v1", self._on_command_message)
            bus.subscribe("*", self._on_generic_message)

    # ============ MESSAGE HANDLERS ================
    async def _on_map(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        self._last_map = msg["payload"]
        logger.info("[MAP] Received map from %s", msg["source"])
        await self._compute_and_send_bom()

    async def _on_inventory(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        self._material_inventory = payload
        logger.info("[INVENTORY] Updated: %s", payload)

    async def _on_command_message(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        t = msg.get("type", "")
        p = msg.get("payload", {})

        if t.endswith(".pause.v1"):
            await self.pause()
        elif t.endswith(".resume.v1"):
            await self.resume()
        elif t.endswith(".stop.v1"):
            await self.stop()
        elif t.endswith(".update.v1"):
            await self.update(p)

    async def _on_generic_message(self, msg):
        return

    # ------------------ PDA ---------------------

    async def perceive(self):
        return {
            "map": self._last_map,
            "inventory": dict(self._material_inventory),
            "bom": dict(self._bom) if self._bom else None,
            "template": self._template_name,
            "build_progress": self._build_progress,
        }

    async def decide(self, p):
        if p["map"] is None:
            return {"action": "wait_for_map"}

        if p["bom"] is None:
            return {"action": "compute_bom"}

        if not self._materials_ready(p["bom"], p["inventory"]):
            return {"action": "wait_for_materials"}

        if self._build_plan is None:
            await self._make_build_plan()

        if self._build_progress >= len(self._build_plan):
            return {"action": "finish_building"}

        return {"action": "build_layer"}

    async def act(self, decision):
        action = decision["action"]

        if action == "wait_for_map":
            return await asyncio.sleep(0.3)

        if action == "compute_bom":
            return await self._compute_and_send_bom()

        if action == "wait_for_materials":
            self.set_state(AgentState.WAITING, "Need materials")
            return await asyncio.sleep(0.5)

        if action == "build_layer":
            return await self._build_next_layer()

        if action == "finish_building":
            await self._publish_build_status("COMPLETED", final=True)
            self._reset_after_build()

    # ------------- BOM / BUILD PLAN ---------------

    async def _compute_and_send_bom(self):
        tpl = TEMPLATES[self._template_name]
        self._bom = dict(tpl["materials"])

        msg = self.build_message(
            "materials.requirements.v1",
            "MinerBot",
            payload=self._bom,
            context={"template": self._template_name}
        )
        await self.bus.publish(msg)

        logger.info("[BUILDER] Published BOM: %s", self._bom)

    def _materials_ready(self, bom, inv):
        return all(inv.get(k, 0) >= v for k, v in bom.items())

    async def _make_build_plan(self):
        tpl = TEMPLATES[self._template_name]
        h, w, d = tpl["height"], tpl["width"], tpl["depth"]

        self._build_plan = []
        for y in range(h):
            layer = {
                "y": y,
                "blocks": [
                    {"x": x, "y": y, "z": z, "material": "stone"}
                    for x in range(w) for z in range(d)
                ]
            }
            self._build_plan.append(layer)

    async def _build_next_layer(self):
        layer = self._build_plan[self._build_progress]

        for _ in layer["blocks"]:
            await asyncio.sleep(0.01)

        self._build_progress += 1
        await self._publish_build_status("LAYER_DONE")

    async def _publish_build_status(self, status, final=False):
        msg = self.build_message(
            "build.v1",
            "*",
            payload={"status": status, "progress": self._build_progress},
            context={"template": self._template_name}
        )
        await self.bus.publish(msg)

        if final:
            await self.save_checkpoint()

    def _reset_after_build(self):
        self._build_progress = 0
        self._build_plan = None
        self._bom = None
        self._material_inventory = {}
        self.set_state(AgentState.IDLE, "build done")
