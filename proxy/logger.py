"""
    logger.py: A logging helper
"""

from typing import Optional, Any
import logging

from .constants import DEFAULT_LOG_FILE, DEFAULT_LOG_LEVEL, DEFAULT_LOG_FORMAT


SINGLE_CHAR_TO_LEVEL = {
    'D': 'DEBUG',
    'I': 'INFO',
    'W': 'WARNING',
    'E': 'ERROR',
    'C': 'CRITICAL',
}


def single_char_to_level(char: str) -> Any:
    return getattr(logging, SINGLE_CHAR_TO_LEVEL[char.upper()[0]])


class Logger:
    """Common logging utilities and setup."""

    @staticmethod
    def setup(
            log_file: Optional[str] = DEFAULT_LOG_FILE,
            log_level: str = DEFAULT_LOG_LEVEL,
            log_format: str = DEFAULT_LOG_FORMAT,
            add_console_logger: bool = False
    ) -> None:
        if log_file:
            logging.basicConfig(
                filename=log_file,
                filemode='a',
                level=single_char_to_level(log_level),
                format=log_format,
            )
        else:
            logging.basicConfig(
                level=single_char_to_level(log_level),
                format=log_format,
            )
        if add_console_logger:
            root_logger = logging.getLogger()
            root_logger.setLevel(single_char_to_level(log_level))
            console = logging.StreamHandler()
            formatter = logging.Formatter(log_format)
            console.setFormatter(formatter)
            root_logger.addHandler(console)
