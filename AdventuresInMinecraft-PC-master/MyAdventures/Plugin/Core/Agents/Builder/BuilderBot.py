# agents/builder/builder_bot.py
import asyncio
import os
from mcpi.minecraft import Minecraft
mc = Minecraft.create()
from mcpi.block import AIR, Block
from pathlib import Path
from Plugin.Schematics.blockmap import BLOCK_MAP
from Plugin.Schematics.schematic_loader import load_schematic, parse_schematic, schematic_to_blocks
from typing import Dict, Any, Optional
from ..BaseAgent import BaseAgent, AgentState
from ...Logger.logging_config import get_console_logger
from collections import Counter
import random


logger = get_console_logger(__name__)

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
            counter = Counter()
            for (_, _, _, block) in blocks:
                if block != "minecraft:air":
                    counter[block] += 1

            materials = [
                {"material": mat, "qty": qty}
                for mat, qty in counter.items()
            ]

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

    BUILD_INTERVAL = 0.001

    def __init__(self, agent_id="BuilderBot", bus= None):
        
        load_all_templates()
 
        self.miner_id = "MinerBot"       # Por defecto
        self.explorer_id = "ExplorerBot" # Por defecto

        self._valid_area: Optional[Dict[str, Any]] = None
        self._template_name = list(TEMPLATES.keys())[0]  # default first template
        self._bom: Optional[list[dict]] = None
        self._materials_reserved = False
        self._build_progress = 0
        self._build_plan = None
        self._search_origin = None   # (x, z)
        self._search_radius = 128    # zona asignada por builder
        self._map_event = asyncio.Event()
        self._bom_event = asyncio.Event()

        super().__init__(agent_id, bus)

        self.bus.subscribe("map.v1", self._on_map)
        self.bus.subscribe("inventory.v1", self._on_inventory)
        self.bus.subscribe("command.builder.start.v1", self._on_start_cmd)
        self.bus.subscribe("command.builder.pause.v1", self._on_control)
        self.bus.subscribe("command.builder.resume.v1", self._on_control)
        self.bus.subscribe("command.builder.stop.v1", self._on_control)
        self.bus.subscribe("command.builder.set.v1", self._on_update_cmd)
        self.bus.subscribe("command.builder.list.v1", self._on_control)
        self.bus.subscribe("command.builder.status.v1", self._on_control)
        self.bus.subscribe("command.builder.workflow.v1", self._on_workflow_cmd)
        self.bus.subscribe("*", self._on_generic)

        if self._search_origin is None:
            self._init_search_origin()

    def set_squad(self, miner_id, explorer_id):
        self.miner_id = miner_id
        self.explorer_id = explorer_id
        logger.info(f"[{self.agent_id}] Equipo asignado: Miner={self.miner_id}, Explorer={self.explorer_id}")

    # ============ MESSAGE HANDLERS ====================

    async def _on_map(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})
        rect = payload.get("best_rectangle")

        if rect is None:
            logger.warning(f"[{self.agent_id}] ExplorerBot did not find any valid flat area.")
            return  # ignorar mapa inválido
        
        logger.info("[MAP] Recived map from %s", msg["source"])

        self._map_event.set()


    async def _on_inventory(self, msg):
        if msg.get("target") not in (self.agent_id, "*"):
            return

        self._bom_event.set()

    async def _on_start_cmd(self, msg: Dict[str, Any]):
        """Handle `builder start.`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info(f"[{self.agent_id}] Start request")

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
        elif cmdtype.endswith(".status.v1"):
            await self.status()

    async def _on_workflow_cmd(self, msg: Dict[str, Any]):
        """Ejecuta un workflow completo de construcción."""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})

        # ---------- 1. Template ----------
        template = payload.get("schem")
        if template:
            if template not in TEMPLATES:
                logger.warning(f"[{self.agent_id}] Unknown template '{template}'")
                return
            self._template_name = template

        tpl = TEMPLATES[self._template_name]

        # ---------- 2. Área de exploración ----------
        x = payload.get("x")
        z = payload.get("z")
        scan_range = payload.get(
            "range",
            max(tpl["width"], tpl["depth"]) + 5
        )

        # Inicializar search origin si no existe
        if self._search_origin is None:
            self._init_search_origin()

        if x is not None and z is not None:
            self._search_origin = (x, z)

        ox, oz = self._search_origin

        logger.info(
            f"[{self.agent_id}] Workflow: explorer search at ({ox}, {oz}) range={scan_range}"
        )
        
        # ---------- 3. Configurar Explorer ----------
        explorer_strategy = payload.get("e_strategy")
        if explorer_strategy:
            await self.bus.publish({
                "type": "command.explorer.set.v1",
                "source": self.agent_id,
                "target": self.explorer_id,
                "payload": {
                    "strategy": explorer_strategy
                }
            })            

        await self.bus.publish({
            "type": "command.explorer.start.v1",
            "source": self.agent_id,
            "target": self.explorer_id,
            "payload": {
                "x": ox,
                "z": oz,
                "range": scan_range
            }
        })

        # ---------- 4. Configurar Miner ----------
        miner_strategy = payload.get("m_strategy")

        if miner_strategy:
            await self.bus.publish({
                "type": "command.miner.set.v1",
                "source": self.agent_id,
                "target": self.miner_id,
                "payload": {
                    "strategy": miner_strategy
                }
            })

        await self.bus.publish({
            "type": "command.miner.start.v1",
            "source": self.agent_id,
            "target": self.miner_id,
            "payload": {}
        })

        # ---------- 5. Arrancar Builder ----------
        logger.info(f"[{self.agent_id}] Workflow: starting builder")
        await self.start()

    async def _on_generic(self, msg: Dict[str, Any]):
        # Debug tap for other messages
        return

    # ------------------ PDA ---------------------
    async def perceive(self):
        return {
            "map": self._valid_area,
            "bom": list(self._bom) if self._bom else None,
            "template": self._template_name,
            "build_progress": self._build_progress,
        }

    async def decide(self, percept):

        if percept["map"] is None:
            tpl = TEMPLATES[percept["template"]]

            req_area = {
                "width": tpl["width"],
                "depth": tpl["depth"]
            }

            existing_area = await self.request_free_area_clean(req_area)

            if existing_area:
                logger.info(f"[{self.agent_id}] ¡Zona encontrada en WorldState! No hace falta explorar.")
                self._valid_area = existing_area
                return {"action": "compute_bom"}
            
            # Calculamos el tamaño que necesitamos escanear
            # (El ancho o profundidad máximo del edificio + margen de 5 bloques)

            # Nos ponemos a esperar. El Explorer enviará "map.v1" cuando termine.
            self.set_state(AgentState.WAITING, "Waiting for Explorer map")
            return {"action": "wait_for_map"}

        if percept["bom"] is None:
            return {"action": "compute_bom"}

        if not self._materials_reserved:
            result = await self.check_and_consume_materials(percept["bom"])

            if result["status"] == "INSUFFICIENT":
                # pedir SOLO lo que falta
                self._bom = result["missing"]

                # CAMBIO AQUÍ: Usamos self.miner_id
                logger.info(f"[{self.agent_id}] Pidiendo materiales a {self.miner_id}...")

                await self.bus.publish({
                    "type": "bom.v1",
                    "source": self.agent_id,
                    "target": self.miner_id, # <--- ¡IMPORTANTE! Variable dinámica
                    "payload": {
                        "bom": self._bom
                    },
                })

                self.set_state(AgentState.WAITING, "Waiting for materials")
                return {"action": "wait_for_materials"}

            if result["status"] != "OK":
                self.set_state(AgentState.WAITING, "Material check failed")
                return {"action": "wait"}

            self._materials_reserved = True

        if self._build_plan is None:
            await self._make_build_plan()

        if self._build_progress >= len(self._build_plan):
            return {"action": "finish_building"}

        self.set_state(AgentState.RUNNING, "Building")
        return {"action": "build_layer"}

    async def act(self, decision):
        action = decision["action"]

        if action == "wait_for_map":
            logger.info(f"[{self.agent_id}] Waiting for map (bus event)…")

            # limpiar el evento por si acaso
            self._map_event.clear()

            # dormir hasta que llegue map.v1
            await self._map_event.wait()

            logger.info(f"[{self.agent_id}] Map arrived! Resuming work.")
            return

        if action == "compute_bom":
            return await self._compute_and_send_bom()

        if action == "wait_for_materials":
            logger.info(f"[{self.agent_id}] Waiting for materials")
            # limpiar el evento por si acaso
            self._bom_event.clear()

            # dormir hasta que llegue inventory.v1
            await self._bom_event.wait()

            logger.info(f"[{self.agent_id}] Inventory arrived! Resuming work.")
            return

        if action == "build_layer":
            return await self._build_next_layer()

        if action == "finish_building":
            await self._publish_build_status("COMPLETED", final=True)
            self._reset_after_build()
            await self.idle()

    # ---------------------------------------------------------
    # Helpers 
    # ---------------------------------------------------------

    async def _compute_and_send_bom(self):
        tpl = TEMPLATES[self._template_name]
        full_bom = list(tpl["materials"])

        result = await self.check_and_consume_materials(full_bom)

        if result["status"] == "OK":
            logger.info(f"[{self.agent_id}] All materials available")
            self._bom = full_bom
            return

        self._bom = result["missing"]

        logger.info(f"[{self.agent_id}] Pidiendo materiales a {self.miner_id}...")

        await self.bus.publish({
            "type": "bom.v1",
            "source": self.agent_id,
            "target": self.miner_id, 
            "payload": {
                "bom": self._bom
            }
        })

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

        logger.info(f"[{self.agent_id}] Build plan ready ({len(self._build_plan)} layers)")

    async def _build_next_layer(self):
        if not self._build_plan or self._build_progress >= len(self._build_plan):
            return

        layer = self._build_plan[self._build_progress]

        # Obtener coordenadas base del mapa de forma segura
        if not self._valid_area:
            logger.warning(f"[{self.agent_id}] No map available, cannot build layer")
            return

        base = self._get_base_coords()
        if base is None:
            logger.warning(f"[{self.agent_id}] No map available for building")
            return

        base_x, base_y, base_z = base

        for block_info in layer["blocks"]:
            bx, by, bz, block_name = block_info["x"], block_info["y"], block_info["z"], block_info["material"]

            block = self.get_block_from_name(block_name)

            try:
                mc.setBlock(base_x + bx, base_y + by, base_z + bz, block.id, block.data)
            except Exception as e:
                logger.warning(f"[{self.agent_id}] Failed to place block {block_name} at {(bx, by, bz)}: {e}")

            await asyncio.sleep(self.BUILD_INTERVAL)

        self._build_progress += 1
        logger.info(f"[{self.agent_id}] Layer {self._build_progress}/{len(self._build_plan)} built")


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
        self._valid_area = None
        self._build_progress = 0
        self._build_plan = None
        self._bom = None
        self._materials_reserved = False


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
            logger.warning(f"[{self.agent_id}] Unknown material {name}, skipping")
            return AIR  # fallback
        return block

    def _get_base_coords(self):
        if not self._valid_area:
            return None

        rect = self._valid_area

        return (
            rect.get("x1", 0),
            rect.get("y", 0),
            rect.get("z1", 0)
        )
    
    def _init_search_origin(self):
        """
        Asigna una zona base al BuilderBot para evitar solapamientos.
        Determinista por agent_id.
        """
        if self._search_origin is not None:
            return

        # Hash estable a partir del agent_id
        seed = abs(hash(self.agent_id)) % 10_000
        random.seed(seed)

        grid = 256  # separación entre builders
        gx = random.randint(-5, 5)
        gz = random.randint(-5, 5)

        self._search_origin = (
            gx * grid,
            gz * grid
        )

        logger.info(
            f"[{self.agent_id}] Search origin set to {self._search_origin}"
        )

    # -----------------------------------------------------
    # Funciones para guardar y cargar checkpoints
    # -----------------------------------------------------
    def get_save_data(self) -> Dict[str, Any]:
        """Extiende BaseAgent para guardar estado completo del BuilderBot."""
        data = super().get_save_data()
        
        data.update({
            "valid_area": self._valid_area,
            "template_name": self._template_name,
            "bom": self._bom,
            "materials_reserved": self._materials_reserved,
            "build_progress": self._build_progress,
            "build_plan": self._build_plan,  # lista de capas con bloques
            "search_origin": self._search_origin,
            "search_radius": self._search_radius,
        })
        
        return data

    def load_save_data(self, data: Dict[str, Any]):
        """Restaura estado desde checkpoint."""
        super().load_save_data(data)
        
        self._valid_area = data.get("valid_area")
        self._template_name = data.get("template_name", list(TEMPLATES.keys())[0])
        self._bom = data.get("bom")
        self._materials_reserved = data.get("materials_reserved", False)
        self._build_progress = data.get("build_progress", 0)
        self._build_plan = data.get("build_plan")
        self._search_origin = data.get("search_origin")
        self._search_radius = data.get("search_radius", 128)

        
        # Eventos no se guardan, se recrean
        self._map_event = asyncio.Event()
        self._bom_event = asyncio.Event()

        # Restaurar estado de espera si había quedado esperando
        if self.state == AgentState.WAITING:
            if self._bom and not self._materials_reserved:
                logger.info(f"[{self.agent_id}] Resuming: waiting for materials")
                self._bom_event.set()
            if self._valid_area is None:
                logger.info(f"[{self.agent_id}] Resuming: waiting for map")
                self._map_event.clear()
    
    # ---------------------------------------------------------
    # Funciones para comunicacion con WorldstateBot
    # ---------------------------------------------------------

    async def request_free_area_clean(self, required: dict, timeout=5.0):
        """
        Envía un mensaje de requestarea a WorldStateBot
        y espera una respuesta worldstate.response SOLO para este agente.
        """

        future = asyncio.get_event_loop().create_future()

        # --- callback temporal ---
        async def _temp(msg):
            if msg.get("type") != "worldstate.response":
                return
            if msg.get("target") not in (self.agent_id, "*"):
                return

            payload = msg.get("payload", {})
            if not future.done():
                future.set_result(payload)

        # registrar callback temporal
        self.bus.subscribe("worldstate.response", _temp)

        # enviar solicitud
        await self.bus.publish({
            "type": "requestarea.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": required
        })

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result.get("rect") or None

        except asyncio.TimeoutError:
            return None
        
        finally:
            # liberar suscripción temporal
            self.bus.unsubscribe("worldstate.response", _temp)
        
    async def check_and_consume_materials(self, bom, timeout=5.0):
        future = asyncio.get_event_loop().create_future()

        async def _temp(msg):
            if msg.get("type") != "worldstate.response":
                return
            if msg.get("target") not in (self.agent_id, "*"):
                return

            payload = msg.get("payload", {})
            if payload.get("kind") != "materials":
                return

            if not future.done():
                future.set_result(payload)

        self.bus.subscribe("worldstate.response", _temp)

        await self.bus.publish({
            "type": "materials.check.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": {
                "bom": bom
            }
        })

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return {"status": "TIMEOUT"}
        finally:
            self.bus.unsubscribe("worldstate.response", _temp)

    # ---------------------------------------------------------
    # Control Overloads
    # ---------------------------------------------------------
    async def stop(self):
        await super().stop()

    async def pause(self):
        logger.info("[BUILDER] Pausing → saving checkpoint")
        await self.save_checkpoint()
        await super().pause()

    async def resume(self):
        await super().resume()

    async def idle(self):
        await super().idle()

    async def status(self):
        """Imprime el estado actual del bot en el logger"""
        info = {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "map": self._valid_area,
            "template": self._template_name,
            "bom": self._bom,
        }
        logger.info(f"[{self.agent_id} STATUS] %s", info)

