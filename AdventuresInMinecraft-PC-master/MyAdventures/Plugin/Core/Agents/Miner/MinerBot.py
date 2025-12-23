# agents/miner/miner_bot.py
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict
from ...Agents.Strategies.miner_strategies import vertical_strategy, vein_strategy, grid_strategy


from ..BaseAgent import BaseAgent, AgentState
from ...Logger.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------
# MinerBot implementation
# ---------------------------
class MinerBot(BaseAgent):
    """
    MinerBot implementation.

    Responsibilities:
    - Receive BOM (materials.requirements.v1) messages from BuilderBot.
    - Validate/accept BOM and start mining until requirements are met.
    - Publish periodic inventory.v1 updates and final report.
    - Support pause/resume/stop/update commands.
    """

    def __init__(self, agent_id: str = "MinerBot", bus=None, mc=None, default_strategy: str = "grid"):
        super().__init__(agent_id, bus=bus)
        self.inventory: Dict[str, int] = defaultdict(int)  # e.g. {'stone': 10}
        self._current_bom: Optional[Dict[str, int]] = None
        self._strategy_name = default_strategy
        self._strategy = None
        self.assigned_area = None
        self._bom_event = asyncio.Event()
        self.mc = mc

        self.bus.subscribe('bom.v1', self._on_materials_request)
        self.bus.subscribe("command.miner.start.v1", self._on_start_cmd)
        self.bus.subscribe("command.miner.set.v1", self._on_update_cmd)
        self.bus.subscribe("command.miner.list.v1", self._on_control)
        self.bus.subscribe("command.miner.status.v1", self._on_control)
        self.bus.subscribe('*', self._on_generic)

    # -----------------------
    # Strategy factory
    # -----------------------
    async def _build_strategy(self, area):
        name = (self._strategy_name or "grid").lower()

        if name == "vertical":
            return await vertical_strategy(area=area)

        if name == "vein":
            return await vein_strategy(area=area)

        # default
        return await grid_strategy(area=area)

    # -----------------------
    # Message handlers
    # -----------------------
    async def _on_materials_request(self, msg: Dict[str, Any]):
        """
        Handle materials.requirements.v1 messages (BOM).
        Expected msg structure:
        {
          "type":"materials.requirements.v1",
          "source":"BuilderBot",
          "target":"MinerBot",
          "payload": {"wood":10, "stone":5},
          "context": {"task_id":"MNR-042"}
        }
        """
        try:
            payload = msg.get('payload') or {}
            if not isinstance(payload, dict):
                logger.error("Invalid BOM payload: %s", payload)
                return
            logger.info("Received BOM from %s: %s", msg.get('source'), payload)
            # accept BOM and start fulfillment
            self._current_bom = dict(payload)
            # if not running, start agent loop (caller may have started already)
            self._bom_event.set()
        except Exception:
            logger.exception("Error handling BOM message")

    async def _on_start_cmd(self, msg: Dict[str, Any]):
        """Handle miner start.`"""
        if msg.get("target") not in (self.agent_id, "*"):
            return
        logger.info("[MINER] Start request")

        # If the bot is running, queue new scan
        if self.state == AgentState.RUNNING:
            logger.info("[MINER] Queuing new request until current finishes")
        await self.start()

    async def _on_update_cmd(self, msg: Dict[str, Any]):
        """Handle `explorer set` command with optional parameters in payload."""
        if msg.get("target") not in (self.agent_id, "*"):
            return

        payload = msg.get("payload", {})

        # Actualizar estrategia si viene en payload
        if "strategy" in payload:
            self._strategy_name(payload["strategy"])

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
        elif cmdtype.endswith(".list.v1"):
            await self.list()
        elif cmdtype.endswith(".status.v1"):
            await self.status()


    async def _on_generic(self, msg: Dict[str, Any]):
        # Optional: listen to other messages (e.g., builder broadcasts)
        return

    # -----------------------
    # PDA cycle implementations
    # -----------------------
    async def perceive(self) -> Dict[str, Any]:
        await asyncio.sleep(0)  # yield
        percept = {
            "bom": dict(self._current_bom) if self._current_bom else None,
            "inventory": dict(self.inventory),
            "strategy": self._strategy_name,
            "state": self.state.value
        }
        return percept

    async def decide(self, percept: Dict[str, Any]) -> Dict[str, Any]:
        if percept["bom"] is None:
            return {"action": "wait_for_bom"}
        
        if self._bom_fulfilled(percept["bom"]):
            return {"action": "report_complete"}

        return {"action": "mine"}

    async def act(self, decision: Dict[str, Any]):
        action = decision.get("action")
        if action == "wait_for_bom":
            logger.info("[MINER] Waiting for bom")

            # limpiar el evento por si acaso
            self._bom_event.clear()

            # dormir hasta que llegue map.v1
            await self._bom_event.wait()

            logger.info("[MINER] Bom arrived! Reasuming work.")
            return
        
        if action == "report_complete":
            await self._publish_inventory(status="SUCCESS", final=True)

            # 👉 NUEVO
            await self.report_materials_to_worldstate()

            # liberar área
            await self.release_assigned_area()

            self._current_bom = None
            return
        
        if action == "mine":
            # perform a mining step according to strategy
            await self._perform_mining_step()
            return

    # -----------------------
    # Mining internals
    # -----------------------
    def _bom_fulfilled(self, bom: Dict[str, int]) -> bool:
        for mat, qty in bom.items():
            if self.inventory.get(mat, 0) < qty:
                return False
        return True

    async def _perform_mining_step(self):
        if not self._current_bom or self.state == AgentState.PAUSED:
            return

        if not hasattr(self, "assigned_area") or not self.assigned_area:
            # solicitar área libre solo si no tenemos ninguna asignada
            success = await self.request_single_area({"width": 16, "depth": 16})
            if not success:
                logger.debug("No se pudo asignar área, esperando próximo ciclo")
                return
            
        # inicializar estrategia después de obtener assigned_area
        if not self._strategy:
            area = self.assigned_area
            self._strategy = await self._build_strategy(area)

            
        rect = self.assigned_area
            
        x1, z1, x2, z2 = rect["x1"], rect["z1"], rect["x2"], rect["z2"]

        try:
            # pasar área a la estrategia
            target = await self._strategy()
            x, _, z = target

            # asegurarse que esté dentro
            x = max(x1, min(x, x2))
            z = max(z1, min(z, z2))

            sector = (x // 16, z // 16)
            logger.info(f"Mining at ({x}, {z}) (sector={sector}) strategy={self._strategy_name})")

            max_y = self.mc.getHeight(x, z)
            if max_y == 0:
                logger.debug(f"No blocks to mine at ({x},{z})")
                return

            # excavar desde arriba hacia abajo
            for y in range(max_y - 1, -1, -1):
                block_type = self.mc.getBlock(x, y, z)
                if block_type != 0:
                    self.mc.setBlock(x, y, z, 0)
                    mat_name = self._simulate_material_from_target((x, y, z))
                    self.inventory[mat_name] += 1
                    logger.info(f"Mined {mat_name} at ({x},{y},{z}) (simulated material, real block broken)")
                    break  # solo un bloque por coordenada

            if self._bom_fulfilled(self._current_bom):
                await self._publish_inventory(status="SUCCESS", final=False)

        except Exception:
            logger.exception("Exception during mining step")

    def _simulate_material_from_target(self, target: Tuple[int, int, int]) -> str:
        """
        Devuelve un material que aún falte en el BOM.
        Simula minería cumpliendo la necesidad exacta del BOM.
        """
        if not self._current_bom:
            return "stone"  # fallback

        pending = [mat for mat, qty in self._current_bom.items() if self.inventory.get(mat, 0) < qty]
        if not pending:
            return list(self._current_bom.keys())[0]

        return pending[0]

    # -----------------------
    # Publishing inventory
    # -----------------------
    async def _publish_inventory(self, status="RUNNING", final: bool = False):
        if not self.bus:
            logger.debug("No bus configured, skipping inventory publish")
            return
        msg = {
            "type": "inventory.v1",
            "source": self.agent_id,
            "target": "BuilderBot",
            "timestamp": None,  # bus may set timestamp
            "payload": dict(self.inventory),
            "status": status,
            "context": {"task_id": "auto", "state": self.state.value}
        }
        await self.bus.publish(msg)
        logger.info("Published inventory (%s): %s", status, self.inventory)
        if final:
            # optionally persist checkpoint on finalization
            await self.save_checkpoint()

    # ---------------------------------------------------------
    # Funciones para comunicacion con WorldstateBot
    # ---------------------------------------------------------
    async def request_single_area(self, required_area, timeout: float = 5.0):
        """
        Solicita un área libre de 16x16 a WorldStateBot y registra su uso.
        Solo pide un área y luego la libera. La minería posterior
        continuará en perceive/decide/act.
        
        mining_callback: async función que ejecuta minería dado (x, y, z)
        timeout: tiempo máximo de espera de WorldState
        """
        future = asyncio.get_event_loop().create_future()

        # callback temporal para recibir respuesta
        async def _temp(msg):
            if msg.get("type") != "worldstate.response":
                return
            if msg.get("target") not in (self.agent_id, "*"):
                return
            payload = msg.get("payload", {})
            if not future.done():
                future.set_result(payload)

        self.bus.subscribe("worldstate.response", _temp)

        # enviar solicitud
        await self.bus.publish({
            "type": "lockarea.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": required_area
        })

        rect = None
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            rect = result.get("rect")  # {x1, z1, x2, z2}
            if not rect:
                logger.debug("WorldState no asignó área libre")
                return False

            logger.debug(f"Área asignada por WorldState: {rect}")

            # marcar coordenadas en la instancia para minería real
            self.assigned_area = rect
            self._strategy = None
            return True

        except asyncio.TimeoutError:
            logger.warning("Timeout esperando área libre de WorldState")
            return False

        finally:
            # desuscribir callback temporal
            self.bus.unsubscribe("worldstate.response", _temp)

    async def release_assigned_area(self, timeout: float = 5.0):
        """
        Libera el área actualmente asignada mediante releasearea.v1,
        esperando confirmación worldstate.response.
        Sigue exactamente el mismo formato que request_single_area().
        """
        if not self.assigned_area:
            logger.debug("[MINER] No assigned area to release.")
            return True  # nada que liberar = éxito

        rect_to_release = self.assigned_area

        future = asyncio.get_event_loop().create_future()

        # Callback temporal para capturar la respuesta
        async def _temp(msg):
            if msg.get("type") != "worldstate.response":
                return
            if msg.get("target") not in (self.agent_id, "*"):
                return

            payload = msg.get("payload", {})
            if not future.done():
                future.set_result(payload)

        # Escuchar respuestas
        self.bus.subscribe("worldstate.response", _temp)

        # Enviar solicitud de liberación de área
        await self.bus.publish({
            "type": "releasearea.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": {"rect": rect_to_release}
        })

        logger.info(f"[MINER] Enviada solicitud de liberación del área: {rect_to_release}")

        try:
            # Esperar ACK
            result = await asyncio.wait_for(future, timeout=timeout)

            status = result.get("status", "UNKNOWN")
            if status != "OK":
                logger.warning(f"[MINER] WorldStateBot devolvió estado no OK al liberar área: {status}")
                return False

            logger.info(f"[MINER] Área liberada correctamente: {rect_to_release}")
            self.assigned_area = None
            return True

        except asyncio.TimeoutError:
            logger.warning("[MINER] Timeout esperando confirmación de liberación del área")
            return False

        finally:
            self.bus.unsubscribe("worldstate.response", _temp)

    async def report_materials_to_worldstate(self, timeout: float = 5.0):
        if not self.inventory:
            logger.info("[MINER] Inventory vacío, no se reporta nada a WorldState")
            return True

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
            "type": "materials.report.v1",
            "source": self.agent_id,
            "target": "WorldStateBot",
            "payload": {
                "materials": dict(self.inventory)
            },
            "context": {
                "task_id": "auto"
            }
        })

        logger.info("[MINER] Reportando materiales a WorldState: %s", dict(self.inventory))

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            status = result.get("status", "UNKNOWN")

            if status != "OK":
                logger.warning("[MINER] WorldState no confirmó materiales: %s", status)
                return False

            logger.info("[MINER] WorldState confirmó guardado de materiales")
            return True

        except asyncio.TimeoutError:
            logger.warning("[MINER] Timeout esperando confirmación de WorldState (materiales)")
            return False

        finally:
            self.bus.unsubscribe("worldstate.response", _temp)

    # -----------------------
    # Control overrides
    # -----------------------
    async def stop(self):
        # On stop, ensure locks released and save state
        logger.info("MinerBot stopping: releasing locks and saving checkpoint")
        await self._locks.release_all()
        await super().stop()

    async def save_checkpoint(self):
        # Minimal checkpoint: dump inventory and BOM (could be serialized to a file)
        logger.info("MinerBot checkpoint: inventory=%s bom=%s", dict(self.inventory), self._current_bom)
        # In a complete implementation, persist to disk / DB here

    async def status(self):
        """Imprime el estado actual del bot en el logger"""
        info = {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "locked_area": self.assigned_area,
            "strategy": self._strategy_name,
        }
        logger.info("[EXPLORER STATUS] %s", info)
