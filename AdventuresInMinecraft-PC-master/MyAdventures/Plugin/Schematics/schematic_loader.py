# schematic_loader.py
import nbtlib
from nbtlib import Compound
import logging

logger = logging.getLogger(__name__)


def load_schematic(path: str):
    """Carga un archivo .schem y devuelve su NBT."""
    logger.info(f"[SCHEM] Loading schematic: {path}")

    nbt_file = nbtlib.load(path)  # auto-detects compression

    # En versiones recientes de nbtlib, nbt_file ya es el root
    return nbt_file

def parse_schematic(nbt):
    # Si nbt es un File, acceder a nbt.root
    if hasattr(nbt, "root"):
        nbt = nbt.root

    width = int(nbt["Width"])
    height = int(nbt["Height"])
    length = int(nbt["Length"])

    ox, oy, oz = map(int, nbt.get("Offset", [0, 0, 0]))

    # Paleta (id numérico → bloque minecraft)
    palette_raw = nbt["Palette"]
    palette = {}
    palette_rev = {}

    for blockstate, value in palette_raw.items():
        value = int(value)
        palette[value] = blockstate
        palette_rev[blockstate] = value

    blockdata = list(nbt["BlockData"])
    blockentities = nbt.get("BlockEntities", [])

    logger.info(
        f"[SCHEM] Size: {width}x{height}x{length}, "
        f"Palette: {len(palette)} entries, Blocks: {len(blockdata)}"
    )

    return {
        "size": (width, height, length),
        "offset": (ox, oy, oz),
        "palette": palette,
        "palette_rev": palette_rev,
        "blockdata": blockdata,
        "blockentities": blockentities,
    }

def schematic_to_blocks(struct):
    """
    Convierte la schematica en una lista de bloques (x,y,z,blockstate)
    en coordenadas relativas (0-based).
    """

    width, height, length = struct["size"]
    palette = struct["palette"]
    blockdata = struct["blockdata"]

    blocks = []

    # Recorrer el array 3D que viene comprimido como 1D
    index = 0
    for y in range(height):
        for z in range(length):
            for x in range(width):
                block_id = blockdata[index]
                index += 1

                blockstate = palette.get(block_id, "minecraft:air")

                blocks.append((x, y, z, blockstate))

    return blocks
