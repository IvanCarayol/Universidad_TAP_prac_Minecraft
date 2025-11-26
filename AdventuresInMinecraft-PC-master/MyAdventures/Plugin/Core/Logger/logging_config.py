import logging
from typing import Optional

def get_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Devuelve un logger configurado para el proyecto.

    Args:
        name (str): Nombre del logger (normalmente __name__ del módulo)
        level (int): Nivel de logging (DEBUG, INFO, WARNING, ERROR)

    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicar handlers si ya tiene alguno
    if not logger.handlers:
        ch = logging.StreamHandler()  # salida a consola
        ch.setLevel(level)

        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        ch.setFormatter(formatter)

        logger.addHandler(ch)
        logger.propagate = False  # evitar que se duplique en root logger

    return logger
