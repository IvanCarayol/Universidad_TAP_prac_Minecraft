import logging
import os
import sys

# --- CAMBIO AQUÍ ---
# Al poner solo el nombre, se guardará en la carpeta raíz desde donde lances el juego
LOG_FILE_PATH = "plugin.log"
# -------------------

def get_console_logger(name: str) -> logging.Logger:
    """
    Crea un logger que SOLO imprime en la terminal (para el humano).
    """
    # Usamos un nombre único para evitar conflictos
    logger_name = f"console.{name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Formato legible para humanos
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # IMPORTANTE: No propagar al root para evitar duplicados
        logger.propagate = False

    return logger

def get_json_file_logger(name: str) -> logging.Logger:
    """
    Crea un logger que SOLO escribe en el archivo (para la evaluación).
    """
    # Usamos un nombre único distinto al de consola
    logger_name = f"json.{name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Formato estándar para el archivo (el mensaje será el JSON)
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        fh = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # IMPORTANTE: No propagar ni imprimir en consola
        logger.propagate = False

    return logger