import logging
import os
import sys
from datetime import datetime

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS Y ARCHIVOS
# -----------------------------------------------------------------------------

# 1. Crear la carpeta 'Logs' si no existe
if not os.path.exists("Logs"):
    os.makedirs("Logs")

# 2. Generar el timestamp
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 3. Definimos DOS archivos diferentes para no mezclar formatos:

# A) Este guardará la copia exacta de lo que ves en terminal (Texto legible)
CONSOLE_LOG_PATH = f"Logs/console_{timestamp}.log"

# B) Este guardará la trazabilidad JSON obligatoria para la evaluación
TRACE_LOG_PATH = f"Logs/trace_{timestamp}.log"


# -----------------------------------------------------------------------------
# GENERADORES DE LOGGERS
# -----------------------------------------------------------------------------

def get_console_logger(name: str) -> logging.Logger:
    """
    Crea un logger que imprime en terminal Y guarda una copia en archivo de texto.
    """
    logger_name = f"console.{name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Formato legible para humanos
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 1. Salida por PANTALLA (Terminal)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # 2. Salida por ARCHIVO (Copia del terminal)
        fh = logging.FileHandler(CONSOLE_LOG_PATH, mode='a', encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        logger.propagate = False

    return logger

def get_json_file_logger(name: str) -> logging.Logger:
    """
    Crea un logger que SOLO escribe en el archivo de trazabilidad (JSON).
    """
    logger_name = f"json.{name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Formato estándar envoltorio
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Guardar en el archivo de TRAZABILIDAD (JSON)
        fh = logging.FileHandler(TRACE_LOG_PATH, mode='a', encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        logger.propagate = False

    return logger