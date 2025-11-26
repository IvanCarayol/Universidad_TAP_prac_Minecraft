# core/agent_base.py

import asyncio
from enum import Enum
from typing import Any, Dict, Optional

from ..Logger.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------
#  Unified Agent States
# ---------------------------------------------------------
class AgentState(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING = "WAITING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


# ---------------------------------------------------------
#  BaseAgent
# ---------------------------------------------------------
class BaseAgent:
    """
    Base class for all Minecraft agents.

    Implements:
      - perception → decision → action cycle (PDA)
      - unified state machine
      - pause/resume/stop commands
      - structured logging
      - integration with MessageBus
      - checkpoint (optional override)
    """

    def __init__(self, agent_id: str, bus=None):
        self.agent_id = agent_id
        self.bus = bus
        self._state: AgentState = AgentState.IDLE
        self._task: Optional[asyncio.Task] = None
        self._should_stop = False

        logger.info(f"[INIT] Agent '{agent_id}' created")

    # -----------------------------------------------------
    #  State helpers
    # -----------------------------------------------------
    @property
    def state(self) -> AgentState:
        return self._state

    def set_state(self, new_state: AgentState, reason: str = ""):
        prev = self._state
        self._state = new_state
        logger.info(
            f"[STATE] {self.agent_id}: {prev.value} → {new_state.value} | reason={reason}"
        )

    # -----------------------------------------------------
    #  Control commands
    # -----------------------------------------------------
    async def start(self):
        """Start the agent's PDA cycle asynchronously."""
        if self._task and not self._task.done():
            logger.warning(f"[START] Agent '{self.agent_id}' is already running")
            return

        self._should_stop = False
        self.set_state(AgentState.RUNNING, "start")
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[START] Agent '{self.agent_id}' started")

    async def stop(self):
        """Safely stop the PDA loop and cleanup."""
        self._should_stop = True
        logger.info(f"[STOP] Stopping agent '{self.agent_id}'...")

        if self._task:
            await self._task  # wait for termination

        # final state
        self.set_state(AgentState.STOPPED, "stop command")
        await self.save_checkpoint()

    async def pause(self):
        self.set_state(AgentState.PAUSED, "pause command")

    async def resume(self):
        if self._state == AgentState.PAUSED:
            self.set_state(AgentState.RUNNING, "resume command")

    async def update(self, params: Dict[str, Any]):
        """Update internal configuration dynamically."""
        logger.info(f"[UPDATE] {self.agent_id} updated with params={params}")

    # -----------------------------------------------------
    #  PDA LOOP
    # -----------------------------------------------------
    async def _run_loop(self):
        """Internal execution loop: perceive → decide → act."""
        try:
            while not self._should_stop:
                if self.state == AgentState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue

                if self.state in (AgentState.STOPPED, AgentState.ERROR):
                    break

                # --------------------
                # Perceive
                percept = await self.perceive()

                # --------------------
                # Decide
                decision = await self.decide(percept)

                # --------------------
                # Act
                await self.act(decision)

                await asyncio.sleep(0)  # yield control

        except Exception as e:
            logger.exception(f"[ERROR] Agent '{self.agent_id}' crashed: {e}")
            self.set_state(AgentState.ERROR, str(e))
            await self.save_checkpoint()

        finally:
            if not self._should_stop:
                await self.stop()

    # -----------------------------------------------------
    #  PDA methods (must be implemented)
    # -----------------------------------------------------
    async def perceive(self) -> Any:
        """
        Should gather information from the environment.
        MUST be overridden by child agents.
        """
        raise NotImplementedError

    async def decide(self, percept: Any) -> Any:
        """
        Should process percepts and compute an action.
        MUST be overridden by child agents.
        """
        raise NotImplementedError

    async def act(self, decision: Any):
        """
        Should perform an action in Minecraft or send a message.
        MUST be overridden by child agents.
        """
        raise NotImplementedError

    # -----------------------------------------------------
    #  Checkpoint (optional override)
    # -----------------------------------------------------
    async def save_checkpoint(self):
        """
        Save persistent state (position, context, inventory...).
        Child agents may override.
        """
        logger.info(f"[CHECKPOINT] Saved checkpoint for {self.agent_id}")
