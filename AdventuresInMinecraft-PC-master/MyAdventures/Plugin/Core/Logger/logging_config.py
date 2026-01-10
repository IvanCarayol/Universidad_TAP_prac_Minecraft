import logging
import os
from typing import Optional

def get_logger(name: Optional[str] = None, level: int = logging.INFO, log_file: str = "simulation.log") -> logging.Logger:
    """
    Devuelve un logger configurado que escribe en consola y en archivo (Requisito de Trazabilidad).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicar handlers si ya tiene alguno
    if not logger.handlers:
        # Formato estándar legible.
        # NOTA: El contenido JSON irá dentro de %(message)s
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 1. Handler de Consola (Para ver en tiempo real)
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # 2. Handler de Archivo (OBLIGATORIO para persistencia y trazabilidad [cite: 143, 224])
        # Asegúrate de que el archivo se guarde en una ruta accesible, por ejemplo en la raíz
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.propagate = False

    return logger