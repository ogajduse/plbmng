import logging
import sys

from loguru import logger as base_logger

logger = base_logger


def init_logger():
    global logger
    logger.remove()
    logger.add(
        sink=sys.stdout,
        level=logging.INFO,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | " "<level>{level}</level> | " "<level>{message}</level>",
    )
