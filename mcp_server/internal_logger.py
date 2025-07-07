"""Internal logger"""

import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.propagate = True


class InternalLogger:
    """Internal logger"""

    @staticmethod
    def LogInfo(msg: str):
        """Log info"""
        logger.info(msg)

    @staticmethod
    def LogDebug(msg: str):
        """Log debug"""
        logger.debug(msg)

    @staticmethod
    def LogError(msg: str):
        """Log error"""
        logger.error(msg)
