# agents/miner/miner_bot.py
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict

from ..BaseAgent import BaseAgent, AgentState
from ...Logger.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------
# Simple lock manager by sector (x,z)
# ---------------------------
class SectorLockManager:
    def __init__(self):
        self._locks: Dict[Tuple[int, int], asyncio.Lock] = {}
        self._global = asyncio.Lock()

    async def acquire(self, sector: Tuple[int, int], timeout: Optional[float] = None) -> bool:
        # ensure the lock object exists
        async with self._global:
            if sector not in self._locks:
                self._locks[sector] = asyncio.Lock()
            lock = self._locks[sector]

        try:
            if timeout is None:
                await lock.acquire()
                return True
            else:
                return await asyncio.wait_for(lock.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            return False

    async def release(self, sector: Tuple[int, int]):
        async with self._global:
            lock = self._locks.get(sector)
            if lock and lock.locked():
                lock.release()

    async def release_all(self):
        async with self._global:
            for s, lock in list(self._locks.items()):
                if lock.locked():
                    try:
                        lock.release()
                    except RuntimeError:
                        # already released or not owned
                        pass


# ---------------------------
# Strategy interfaces (minimal examples)
# ---------------------------
class MiningStrategy:
    """Base interface for mining strategies"""
    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}

    async def next_target(self) -> Tuple[int, int, int]:
        """Return next (x, y, z) target to mine"""
        raise NotImplementedError


class VerticalStrategy(MiningStrategy):
    def __init__(self, base_x=0, base_z=0, start_y=64, step=1):
        super().__init__({"base_x": base_x, "base_z": base_z, "start_y": start_y, "step": step})
        self._y = start_y
        self.base_x = base_x
        self.base_z = base_z

    async def next_target(self):
        t = (self.base_x, self._y, self.base_z)
        self._y -= self.params.get("step", 1)
        return t


class GridStrategy(MiningStrategy):
    def __init__(self, x0=0, z0=0, width=5, depth=5, step=1, y=64):
        super().__init__({"x0": x0, "z0": z0, "width": width, "depth": depth, "step": step, "y": y})
        self.x0 = x0
        self.z0 = z0
        self.width = width
        self.depth = depth
        self.step = step
        self.y = y
        self._i = 0

    async def next_target(self):
        xi = (self._i % self.width)
        zi = (self._i // self.width) % self.depth
        x = self.x0 + xi * self.step
        z = self.z0 + zi * self.step
        self._i += 1
        return (x, self.y, z)


class VeinStrategy(MiningStrategy):
    # For demonstration: behaves like grid but would expand recursively on matches.
    def __init__(self, seed_x=0, seed_z=0, radius=3, y=64):
        super().__init__({"seed_x": seed_x, "seed_z": seed_z, "radius": radius, "y": y})
        self.seed_x = seed_x
        self.seed_z = seed_z
        self.radius = radius
        self.y = y
        self._offset = 0

    async def next_target(self):
        # spiral-like
        r = self._offset
        x = self.seed_x + (r % (self.radius * 2)) - self.radius
        z = self.seed_z + ((r // (self.radius * 2)) % (self.radius * 2)) - self.radius
        self._offset += 1
        return (x, self.y, z)


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

    INVENTORY_PUBLISH_INTERVAL = 1.0  # seconds

    def __init__(self, agent_id: str = "MinerBot", bus=None, default_strategy: str = "grid"):
        super().__init__(agent_id, bus=bus)
        self.inventory: Dict[str, int] = defaultdict(int)  # e.g. {'stone': 10}
        self._current_bom: Optional[Dict[str, int]] = None
        self._bom_task: Optional[asyncio.Task] = None
        self._strategy_name = default_strategy
        self._strategy: MiningStrategy = self._create_strategy(default_strategy)
        self._locks = SectorLockManager()
        self._last_publish = 0.0
        self._mining = False
        # subscribe to bus messages if provided
        if self.bus:
            # subscribe to materials.requirements.v1 and command messages
            self.bus.subscribe('materials.requirements.v1', self._on_materials_request)
            self.bus.subscribe('command.*.v1', self._on_command_message)
            # also accept direct control channel wildcard
            self.bus.subscribe('*', self._on_generic_message)

    # -----------------------
    # Strategy factory
    # -----------------------
    def _create_strategy(self, name: str, params: Dict[str, Any] = None) -> MiningStrategy:
        name = (name or "grid").lower()
        if name == "vertical":
            return VerticalStrategy(**(params or {}))
        elif name == "vein":
            return VeinStrategy(**(params or {}))
        else:
            return GridStrategy(**(params or {}))

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
            if self.state != AgentState.RUNNING:
                # don't await here; let the main loop pick up work
                asyncio.create_task(self.start())
        except Exception:
            logger.exception("Error handling BOM message")

    async def _on_command_message(self, msg: Dict[str, Any]):
        # Very small generic command handler; expects control messages formatted already.
        try:
            payload = msg.get('payload', {})
            cmd = msg.get('type', '')
            if msg.get('target') not in (self.agent_id, '*'):
                return
            if cmd.endswith('.pause.v1') or cmd == 'command.pause.v1':
                await self.pause()
            elif cmd.endswith('.resume.v1') or cmd == 'command.resume.v1':
                await self.resume()
            elif cmd.endswith('.stop.v1') or cmd == 'command.stop.v1':
                await self.stop()
            elif cmd.endswith('.update.v1') or cmd == 'command.update.v1':
                await self.update(payload or {})
        except Exception:
            logger.exception("Error handling command message")

    async def _on_generic_message(self, msg: Dict[str, Any]):
        # Optional: listen to other messages (e.g., builder broadcasts)
        return

    # -----------------------
    # PDA cycle implementations
    # -----------------------
    async def perceive(self) -> Dict[str, Any]:
        # Minimal perception: return BOM snapshot and strategy
        await asyncio.sleep(0)  # yield
        percept = {
            "bom": dict(self._current_bom) if self._current_bom else None,
            "inventory": dict(self.inventory),
            "strategy": self._strategy_name,
            "state": self.state.value
        }
        return percept

    async def decide(self, percept: Dict[str, Any]) -> Dict[str, Any]:
        # Decide whether to mine, publish, or wait
        if percept["bom"] is None:
            # nothing to do
            return {"action": "idle"}
        # check if BOM fulfilled
        if self._bom_fulfilled(percept["bom"]):
            return {"action": "report_complete"}
        # else keep mining
        return {"action": "mine"}

    async def act(self, decision: Dict[str, Any]):
        action = decision.get("action")
        if action == "idle":
            # occasionally publish inventory snapshot
            await self._maybe_publish_inventory()
            await asyncio.sleep(0.2)
            return
        if action == "report_complete":
            await self._publish_inventory(status="SUCCESS", final=True)
            # clear BOM to indicate done
            self._current_bom = None
            return
        if action == "mine":
            # perform a mining step according to strategy
            await self._perform_mining_step()
            await self._maybe_publish_inventory()
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
        if not self._current_bom:
            return

        if self.state == AgentState.PAUSED:
            return

        # pick target and attempt to lock sector before mining
        try:
            target = await self._strategy.next_target()
            sector = (int(target[0]) // 16, int(target[2]) // 16)  # example sector granularity
            got = await self._locks.acquire(sector, timeout=0.5)
            if not got:
                logger.debug("Sector %s busy, skipping this target", sector)
                return

            self._mining = True
            logger.info("Mining at %s (sector=%s) using strategy=%s", target, sector, self._strategy_name)

            # simulate mining duration
            await asyncio.sleep(0.05)

            # simulate material found (toy logic: alternating)
            found_mat = self._simulate_material_from_target(target)
            self.inventory[found_mat] = self.inventory.get(found_mat, 0) + 1

            # release lock
            await self._locks.release(sector)

            # If BOM satisfied, publish immediate update
            if self._bom_fulfilled(self._current_bom):
                await self._publish_inventory(status="SUCCESS", final=False)
        except Exception:
            logger.exception("Exception during mining step")
        finally:
            self._mining = False

    def _simulate_material_from_target(self, target: Tuple[int, int, int]) -> str:
        # Toy deterministic mapping for tests: even x → stone, odd x → iron (rare)
        x, y, z = target
        if (int(x) % 7) == 0:
            return "iron"
        if int(x) % 2 == 0:
            return "stone"
        return "wood"

    # -----------------------
    # Publishing inventory
    # -----------------------
    async def _maybe_publish_inventory(self):
        now = time.time()
        if now - self._last_publish >= MinerBot.INVENTORY_PUBLISH_INTERVAL:
            await self._publish_inventory(status="RUNNING", final=False)
            self._last_publish = now

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

    # -----------------------
    # Control overrides
    # -----------------------
    async def update(self, params: Dict[str, Any]):
        # handle dynamic reconfiguration (e.g., change strategy)
        logger.info("MinerBot received update: %s", params)
        if "strategy" in params:
            self._strategy_name = params["strategy"]
            self._strategy = self._create_strategy(self._strategy_name, params.get("strategy_params"))
            logger.info("MinerBot strategy changed to %s", self._strategy_name)
        if "clear_bom" in params and params["clear_bom"]:
            self._current_bom = None
        await super().update(params)

    async def stop(self):
        # On stop, ensure locks released and save state
        logger.info("MinerBot stopping: releasing locks and saving checkpoint")
        await self._locks.release_all()
        await super().stop()

    async def save_checkpoint(self):
        # Minimal checkpoint: dump inventory and BOM (could be serialized to a file)
        logger.info("MinerBot checkpoint: inventory=%s bom=%s", dict(self.inventory), self._current_bom)
        # In a complete implementation, persist to disk / DB here

