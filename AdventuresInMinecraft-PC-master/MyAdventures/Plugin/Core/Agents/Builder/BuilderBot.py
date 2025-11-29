# agents/builder/builder_bot.py
import asyncio
import os
from mcpi.minecraft import Minecraft
mc = Minecraft.create()
from mcpi.block import AIR, BLOCK_MAP, Block
from pathlib import Path
from Plugin.Schematics.schematic_loader import load_schematic, parse_schematic, schematic_to_blocks
from typing import Dict, Any, Optional
from ..BaseAgent import BaseAgent, AgentState
from ...Logger.logging_config import get_logger

logger = get_logger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = ROOT_DIR / "Schematics"
TEMPLATES = {}

def load_all_templates():
    logger.info("[BUILDER] Loading templates from ./Schematics/")

    if not os.path.isdir(TEMPLATE_DIR):
        logger.warning(f"[BUILDER] Template folder '{TEMPLATE_DIR}' does not exist")
        return

    for file in os.listdir(TEMPLATE_DIR):
        if not file.endswith(".schem"):
            continue

        name = file.replace(".schem", "")
        path = os.path.join(TEMPLATE_DIR, file)

        try:
            logger.info(f"[BUILDER] Loading template '{name}' ({file})...")
            nbt = load_schematic(path)
            struct = parse_schematic(nbt)
            blocks = schematic_to_blocks(struct)

            # Build material count
            materials = {}
            for (_, _, _, block) in blocks:
                if block != "minecraft:air":
                    materials[block] = materials.get(block, 0) + 1

            width, height, depth = struct["size"]

            TEMPLATES[name] = {
                "width": width,
                "height": height,
                "depth": depth,
                "materials": materials,
                "blocks": blocks,
            }

            logger.info(f"[BUILDER] Loaded template '{name}' "
                        f"({width}×{height}×{depth}, {len(blocks)} blocks)")

        except Exception as e:
            logger.error(f"[BUILDER] ERROR loading {file}: {e}")


class BuilderBot(BaseAgent):

    BUILD_INTERVAL = 0.01

    def __init__(self, agent_id="BuilderBot", bus=None):
        super().__init__(agent_id, bus)
        
        load_all_templates()
 
        self._last_map: Optional[Dict[str, Any]] = None
        self._template_name = list(TEMPLATES.keys())[0]  # default first template
        self._bom = None
        self._material_inventory = {}
        self._build_progress = 0
        self._build_plan = None
        self._map_event = asyncio.Event()

        # Inicializar estado activo esperando mapas
        self.set_state(AgentState.WAITING, "Waiting for map")

        self.bus.subscribe("map.v1", self._on_map)
        self.bus.subscribe("inventory.v1", self._on_inventory)
        self.bus.subscribe("command.builder.start.v1", self._on_start_cmd)
        self.bus.subscribe("command.builder.set.v1", self._on_update_cmd)
        self.bus.subscribe("command.builder.list.v1", self._on_control)
        self.bus.subscribe("command.*.v1", self._on_control)
        self.bus.subscribe("*", self._on_generic)

    # ============ MESSAGE HANDLERS ====================
    async def _on_map(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        rect = payload.get("best_rectangle")

        if rect is None:
            logger.warning("[BUILDER] ExplorerBot did not find any valid flat area.")
            return  # ignorar mapa inválido

        # Rectangle dimensions (ExplorerBot guarantees x2 >= x1)
        rect_width = rect["width"]
        rect_depth = rect["height"]  # height aquí significa "profundidad"

        # Template requirements
        tpl = TEMPLATES[self._template_name]
        tpl_w = tpl["width"]
        tpl_d = tpl["depth"]

        logger.info(
            f"[BUILDER] Received rectangle {rect_width}×{rect_depth} "
            f"for template '{self._template_name}' ({tpl_w}×{tpl_d})"
        )

        # --- VALIDATION ---
        if rect_width < tpl_w or rect_depth < tpl_d:
            logger.warning(
                f"[BUILDER] Flat area too small. Needed at least {tpl_w}×{tpl_d}, "
                f"got {rect_width}×{rect_depth}. Waiting for new map…"
            )
            return  # NO aceptamos este mapa

        # If valid:
        self._last_map = payload
        logger.info("[MAP] Accepted map from %s", msg["source"])

        self._map_event.set()
        self.set_state(AgentState.RUNNING, "Processing map")

    async def _on_inventory(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        self._material_inventory = payload
        logger.info("[INVENTORY] Updated: %s", payload)
        
    async def _on_start_cmd(self, msg: Dict[str, Any]):
        """Handle `builder start.`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info("[BUILDER] Start request")

        # If the bot is running, queue new scan
        if self.state == AgentState.RUNNING:
            logger.info("[BUILDER] Queuing new request until current finishes")
        await self.start()

    async def _on_update_cmd(self, msg: Dict[str, Any]):
        """Handle `explorer set` command with optional parameters in payload."""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})

        # Actualizar rango si viene en payload
        if "schem" in payload:
            name = payload["schem"]
            if name not in TEMPLATES:
                return

            self._template_name = name
        # Llamar a update del BaseAgent para cualquier otro parámetro general
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
        elif cmdtype.endswith(".list.v1"):
            await self.list()

    async def _on_generic(self, msg: Dict[str, Any]):
        # Debug tap for other messages
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
            self.set_state(AgentState.WAITING, "Waiting for map")
            return {"action": "wait_for_map"}

        if p["bom"] is None:
            return {"action": "compute_bom"}

        #if not self._materials_ready(p["bom"], p["inventory"]):
            self.set_state(AgentState.WAITING, "Need materials")
            return {"action": "wait_for_materials"}

        if self._build_plan is None:
            await self._make_build_plan()

        if self._build_progress >= len(self._build_plan):
            return {"action": "finish_building"}

        self.set_state(AgentState.RUNNING, "Building")
        return {"action": "build_layer"}

    async def act(self, decision):
        action = decision["action"]

        if action == "wait_for_map":
            logger.info("[BUILDER] Waiting for map (bus event)…")

            # limpiar el evento por si acaso
            self._map_event.clear()

            # dormir hasta que llegue map.v1
            await self._map_event.wait()

            logger.info("[BUILDER] Map arrived! Resuming work.")
            return

        if action == "compute_bom":
            return await self._compute_and_send_bom()

        #if action == "wait_for_materials":
            logger.info("[BUILDER] Waiting for materials")
            return await asyncio.sleep(0.5)

        if action == "build_layer":
            return await self._build_next_layer()

        if action == "finish_building":
            await self._publish_build_status("COMPLETED", final=True)
            self._reset_after_build()
            await self.idle()

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
        blocks = tpl["blocks"]

        # Plan: lista de capas y cada capa lista de bloques reales
        max_y = tpl["height"]
        plan = [[] for _ in range(max_y)]

        for x, y, z, block in blocks:
            if block != "minecraft:air":
                plan[y].append({"x": x, "y": y, "z": z, "material": block})

        self._build_plan = [
            {"y": y, "blocks": layer}
            for y, layer in enumerate(plan)
        ]

        logger.info(f"[BUILDER] Build plan ready ({len(self._build_plan)} layers)")

    async def _build_next_layer(self):
        if not self._build_plan or self._build_progress >= len(self._build_plan):
            return

        layer = self._build_plan[self._build_progress]

        # Obtener coordenadas base del mapa de forma segura
        if not self._last_map:
            logger.warning("[BUILDER] No map available, cannot build layer")
            return

        rect = self._last_map.get("best_rectangle")
        if not rect:
            logger.warning("[BUILDER] Invalid map rectangle")
            return

        # Algunos mapas no tienen x/z, usar fallback 0
        base_x = rect.get("x", rect.get("x1", 0))
        base_z = rect.get("z", rect.get("z1", 0))
        base_y = rect.get("y", 0)  # altura base, si el mapa no da altura se asume 0

        for block_info in layer["blocks"]:
            bx, by, bz, block_name = block_info["x"], block_info["y"], block_info["z"], block_info["material"]

            block = self.get_block_from_name(block_name)

            try:
                mc.setBlock(base_x + bx, base_y + by, base_z + bz, block.id, block.data)
            except Exception as e:
                logger.warning(f"[BUILDER] Failed to place block {block_name} at {(bx, by, bz)}: {e}")

            await asyncio.sleep(self.BUILD_INTERVAL)

        self._build_progress += 1
        logger.info(f"[BUILDER] Layer {self._build_progress}/{len(self._build_plan)} built")


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

    # ------------- Funciones Auxiliares ---------------
    def list(self):
        """Print available templates and current selection via logger only."""

        logger.info("\n================= BUILDER TEMPLATE LIST =================")

        logger.info(f"Selected template: {self._template_name}")

        for name, tpl in TEMPLATES.items():
            logger.info(f"\n-> {name}")
            logger.info(f"   Size: {tpl['width']}×{tpl['height']}×{tpl['depth']}")

        logger.info("=========================================================")

    def _resolve_block(self, name: str):
        """Mapea nombre del bloque de .schem a block_id, data de MCPI."""
        return BLOCK_MAP.get(name, (None, None))
    
    # helpers.py o dentro de BuilderBot
    def get_block_from_name(self, name: str) -> Block:
        """
        Devuelve el Block correspondiente a partir del nombre,
        ignorando las propiedades de bloques entre corchetes.
        """
        base_name = name.split("[")[0]  # elimina propiedades tipo [east=true,...]
        block = BLOCK_MAP.get(base_name)
        if block is None:
            logger.warning(f"[BUILDER] Unknown material {name}, skipping")
            return AIR  # fallback
        return block

    
    async def idle(self):
        await super().idle()
