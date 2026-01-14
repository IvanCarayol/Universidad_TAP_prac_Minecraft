# core/agent_base.py

import asyncio
import json
from enum import Enum
from typing import Any, Dict, Optional
import datetime
from pathlib import Path

from ..Logger.logging_config import get_console_logger, get_json_file_logger

logger = get_console_logger(__name__)

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

        self.logger = get_json_file_logger(name=agent_id)

        self.prev = None
        self._state: AgentState = AgentState.IDLE
        self._task: Optional[asyncio.Task] = None
        self._should_stop = False

        self.logger.info(json.dumps({
            "event": "agent_init", 
            "agent_id": agent_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }))

        self.load_from_disk()
        try:
            asyncio.create_task(self._auto_resume_if_needed())
        except RuntimeError:
            pass


    async def _auto_resume_if_needed(self):
            if self._state in (AgentState.RUNNING, AgentState.WAITING):
                self._should_stop = False
                if self._task is None or self._task.done():
                    self._task = asyncio.create_task(self._run_loop())
                    logger.info(f"[AUTO-RESUME] Agent '{self.agent_id}' resumed from {self._state.value}")
    # -----------------------------------------------------
    #  Directory helpers
    # -----------------------------------------------------
    SAVE_DIR = Path(__file__).resolve().parents[2] / "Saves"

    def _get_save_path(self) -> Path:
        return self.SAVE_DIR / f"{self.agent_id}.json"
    
    # -----------------------------------------------------
    #  State helpers
    # -----------------------------------------------------
    @property
    def state(self) -> AgentState:
        return self._state

    def set_state(self, new_state: AgentState, reason: str = ""):
        self.prev = self._state
        self._state = new_state

        transition_record = {
            "type": "state_change",
            "agent_id": self.agent_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "previous_state": self.prev.value,
            "next_state": new_state.value,
            "reason": reason
        }
        self.logger.info(json.dumps(transition_record))

    # -----------------------------------------------------
    #  Control commands
    # -----------------------------------------------------
    async def start(self):
        """Start the agent loop (safe)."""
        if self._task and not self._task.done():
            logger.warning(f"[START] Agent '{self.agent_id}' already running")
            self.logger.warning(json.dumps({
                "event": "start_failed",
                "reason": "already_running",
                "agent_id": self.agent_id
            }))

            return

        self._should_stop = False
        self.set_state(AgentState.RUNNING, "start")

        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[START] Agent '{self.agent_id}' started")

    async def stop(self):
        """Stop the agent WITHOUT causing it to await on itself."""
        logger.info(f"[STOP] Stopping agent '{self.agent_id}'...")
        self.logger.info(json.dumps({
            "event": "stopping_sequence",
            "agent_id": self.agent_id
        }))

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
                self.logger.error(json.dumps({
                    "event": "stop_error", 
                    "agent_id": self.agent_id,
                    "error": str(e)
                }))
                logger.error(f"[STOP ERROR] {e}")

        self.set_state(AgentState.STOPPED, "stop command")
        await self.save_checkpoint()

    async def pause(self):
        self.set_state(AgentState.PAUSED, "pause command")

    async def idle(self):
        self._should_stop = True
        self.set_state(AgentState.IDLE, "pause command")

    async def resume(self):
        """
        Resume el agente sin modificar el estado lógico cargado.
        Solo reactiva el loop si estaba pausado.
        """
        """
        Resume el agente al estado que tenía antes de pausar.
        """
        if self._state != AgentState.PAUSED:
            logger.warning(f"[RESUME] Agent '{self.agent_id}' not paused, cannot resume")
            return

        if self.prev is None:
            # fallback: si no hay prev definido, usar RUNNING
            target_state = AgentState.RUNNING
        else:
            target_state = self.prev

        self.set_state(target_state, "resume command")
        
        self.logger.info(json.dumps({
            "event": "resume",
            "agent_id": self.agent_id
        }))

        # Reactivar loop si no existe
        if self._task is None or self._task.done():
            self._should_stop = False
            self._task = asyncio.create_task(self._run_loop())

    async def waiting(self):
        self.set_state(AgentState.WAITING, "resume command")

    async def update(self, params: Dict[str, Any]):
        logger.info(f"[UPDATE] {self.agent_id} updated with params={params}")
        self.logger.info(json.dumps({
            "event": "update_params",
            "agent_id": self.agent_id,
            "params": params
        }))

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
            self.logger.exception(json.dumps({
                "event": "crash",
                "agent_id": self.agent_id,
                "error": str(e)
            }))
            
            self.set_state(AgentState.ERROR, str(e))
            await self.save_checkpoint()

        finally:
            """
            Borrar checkpoint solo si la tarea se completó realmente.
            """
            if self.state == AgentState.IDLE:
                # La tarea ya terminó → no necesitamos el checkpoint
                await self.delete_checkpoint()
            else:
                # Todavía activo o interrumpido → guardar checkpoint
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
        try:
            self.SAVE_DIR.mkdir(exist_ok=True)

            data = self.get_save_data()
            path = self._get_save_path()

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info(f"[CHECKPOINT] {self.agent_id} saved to {path}")

            self.logger.info(json.dumps({
                "event": "checkpoint_saved",
                "agent_id": self.agent_id,
                "path": str(path)
            }))

        except Exception as e:
            logger.exception(f"[CHECKPOINT ERROR] {self.agent_id}: {e}")

    async def delete_checkpoint(self):
        path = self._get_save_path()
        if path.exists():
            try:
                path.unlink()
                logger.info(f"[CHECKPOINT DELETE] {self.agent_id} checkpoint deleted")
                self.logger.info(json.dumps({
                    "event": "checkpoint_deleted",
                    "agent_id": self.agent_id,
                    "path": str(path)
                }))
            except Exception as e:
                logger.exception(f"[CHECKPOINT DELETE ERROR] {self.agent_id}: {e}")
    # -----------------------------------------------------
    #  Load checkpoint from disk
    # -----------------------------------------------------
    def load_from_disk(self) -> bool:
        """
        Carga el checkpoint desde disco y restaura el estado del agente.
        Devuelve True si se cargó correctamente, False si no existe.
        """
        path = self._get_save_path()

        if not path.exists():
            logger.info(f"[CHECKPOINT] No checkpoint found for {self.agent_id}")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.load_save_data(data)

            logger.info(f"[CHECKPOINT] {self.agent_id} restored from {path}")

            self.logger.info(json.dumps({
                "event": "checkpoint_loaded",
                "agent_id": self.agent_id,
                "path": str(path)
            }))

            return True

        except Exception as e:
            logger.exception(f"[CHECKPOINT LOAD ERROR] {self.agent_id}: {e}")
            return False

    # -----------------------------------------------------
    #  Serialization API (override in child agents)
    # -----------------------------------------------------
    def get_save_data(self) -> Dict[str, Any]:
        """
        Devuelve un dict JSON-serializable con el estado del agente.
        Las subclases deben extender este dict.
        """
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "prev_state": self.prev.value if self.prev else None,
        }

    def load_save_data(self, data: Dict[str, Any]):
        """
        Restaura el estado del agente desde un dict.
        Maneja correctamente el caso PAUSED + resume.
        """
        state = data.get("state")
        prev_state = data.get("prev_state")
        
        loaded_state = AgentState(state) if state else None
        loaded_prev = AgentState(prev_state) if prev_state else None

        if loaded_state:
            self._state = loaded_state
            self.prev = loaded_prev


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

