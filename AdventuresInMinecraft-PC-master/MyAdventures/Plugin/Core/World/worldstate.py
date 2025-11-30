# worldstate.py
import asyncio

class WorldState:
    def __init__(self):
        self.flat_areas = []   # [{rect:{...}, status:"FREE", assigned_to:None}]
        self._lock = asyncio.Lock()

WS = WorldState()

def _normalize_rect(rect):
    """
    Convierte rect en un dict válido aunque llegue como tupla.
    form expected: (x1, z1, x2, z2) OR dict(...)
    """
    if isinstance(rect, dict):
        return rect

    if isinstance(rect, tuple) and len(rect) == 4:
        x1, z1, x2, z2 = rect
        return {
            "x1": x1,
            "z1": z1,
            "x2": x2,
            "z2": z2,
            "width": abs(x2 - x1) + 1,
            "height": abs(z2 - z1) + 1,
            "area": abs((x2 - x1) + 1) * abs((z2 - z1) + 1),
            "y": 63  # fallback (Explorer siempre debería ponerlo)
        }

    raise ValueError(f"Invalid rect format: {rect}")

async def add_flat_area(rect):
    rect = _normalize_rect(rect)

    area = {
        "rect": rect,
        "status": "FREE",
        "assigned_to": None
    }

    async with WS._lock:
        WS.flat_areas.append(area)

async def request_free_area(agent_id: str, required):
    """
    required = {width, height, depth} del schem.
    Devuelve una zona que sea >= que la requerida.
    """
    req_w = required["width"]
    req_h = required["depth"]

    async with WS._lock:
        candidates = []

        for a in WS.flat_areas:
            if a["status"] != "FREE":
                continue

            rect = a["rect"]
            if rect["width"] >= req_w and rect["height"] >= req_h:
                candidates.append(a)

        if not candidates:
            return None

        best = max(candidates, key=lambda a: a["rect"]["area"])

        best["status"] = "RESERVED"
        best["assigned_to"] = agent_id

        return best["rect"]

async def mark_area_status(rect: dict, status: str):
    """
    Cambia estado de una zona (RESERVED → BUILDING → DONE)
    """
    async with WS._lock:
        for a in WS.flat_areas:
            if a["rect"] == rect:
                a["status"] = status
                return
