# core/agent_base.py

import asyncio
from enum import Enum
from typing import Any, Dict, Optional
import datetime

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
    Base class for all Minecraft agents with:
      - PDA loop (perceive -> decide -> act)
      - pause/resume/stop
      - async-safe task lifecycle
      - no deadlocks or self-await errors
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
        """Start the agent loop (safe)."""
        if self._task and not self._task.done():
            logger.warning(f"[START] Agent '{self.agent_id}' already running")
            return

        self._should_stop = False
        self.set_state(AgentState.RUNNING, "start")

        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[START] Agent '{self.agent_id}' started")

    async def stop(self):
        """Stop the agent WITHOUT causing it to await on itself."""
        logger.info(f"[STOP] Stopping agent '{self.agent_id}'...")

        self._should_stop = True

        # If stop() was called from another task → safe await
        if (
            self._task
            and not self._task.done()
            and asyncio.current_task() is not self._task
        ):
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[STOP ERROR] {e}")

        self.set_state(AgentState.STOPPED, "stop command")
        await self.save_checkpoint()

    async def pause(self):
        self.set_state(AgentState.PAUSED, "pause command")

    async def resume(self):
        if self._state == AgentState.PAUSED:
            self.set_state(AgentState.RUNNING, "resume command")

    async def update(self, params: Dict[str, Any]):
        logger.info(f"[UPDATE] {self.agent_id} updated with params={params}")

    # -----------------------------------------------------
    #  PDA LOOP
    # -----------------------------------------------------
    async def _run_loop(self):
        """Core perception-decision-action loop."""
        try:
            while not self._should_stop:
                if self.state == AgentState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue

                if self.state in (AgentState.STOPPED, AgentState.ERROR):
                    break

                # --- Perceive
                percept = await self.perceive()

                # --- Decide
                decision = await self.decide(percept)

                # --- Act
                await self.act(decision)

                await asyncio.sleep(0)  # yield control

        except asyncio.CancelledError:
            # Normal shutdown → no log spam, no await stop()
            return

        except Exception as e:
            logger.exception(f"[ERROR] Agent '{self.agent_id}' crashed: {e}")
            self.set_state(AgentState.ERROR, str(e))
            await self.save_checkpoint()

        finally:
            # Ensure STOPPED state if loop ends
            if not self._should_stop:
                self.set_state(AgentState.STOPPED, "loop finished")
                await self.save_checkpoint()

    # -----------------------------------------------------
    #  PDA abstract methods
    # -----------------------------------------------------
    async def perceive(self) -> Any:
        raise NotImplementedError

    async def decide(self, percept: Any) -> Any:
        raise NotImplementedError

    async def act(self, decision: Any):
        raise NotImplementedError

    # -----------------------------------------------------
    #  Checkpoint
    # -----------------------------------------------------
    async def save_checkpoint(self):
        logger.info(f"[CHECKPOINT] Saved checkpoint for {self.agent_id}")


    # -----------------------------------------------------
    #  Messages
    # -----------------------------------------------------
    def build_message(self, msg_type: str, target: str, payload: dict, status="SUCCESS", context=None):
        return {
            "type": msg_type,
            "source": self.agent_id,
            "target": target,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "payload": payload,
            "status": status,
            "context": context or {}
        }

