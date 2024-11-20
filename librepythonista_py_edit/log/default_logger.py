from __future__ import annotations
import logging
import sys
from typing import TYPE_CHECKING
from logging import Logger
from logging.handlers import TimedRotatingFileHandler

if TYPE_CHECKING:
    from .logger_config import LoggerConfig


# https://stackoverflow.com/questions/13521981/implementing-an-optional-logger-in-code


class DefaultLogger(Logger):
    """Custom Logger Class"""

    def __init__(self, log_config: LoggerConfig) -> None:
        """
        Creates a logger.

        Args:
            log_config (LoggerConfig): Logger Configuration

        Returns:
            None: None
        """
        self._config = log_config
        self.formatter = logging.Formatter(self._config.log_format)

        # logging.addLevelName(logging.ERROR, "ERROR")
        # logging.addLevelName(logging.DEBUG, "DEBUG")
        # logging.addLevelName(logging.INFO, "INFO")
        # logging.addLevelName(logging.WARNING, "WARNING")

        # Logger.__init__(self, name=log_name, level=cfg.log_level)
        super().__init__(name=self._config.log_name, level=self._config.log_level)

        has_handler = False
        has_console_handler = False

        if self._config.log_file and self._config.log_level >= 10:  # DEBUG
            self.addHandler(self._get_file_handler())
            has_handler = True

        if self._config.log_add_console and self._config.log_level > 0:
            self.addHandler(self._get_console_handler())
            has_handler = True
            has_console_handler = True

        if not has_console_handler and log_config.log_add_console:
            self.addHandler(self._get_console_handler())
            has_handler = True
            has_console_handler = True

        if not has_handler:
            self.addHandler(self._get_null_handler())

        # with this pattern, it's rarely necessary to propagate the| error up to parent
        self.propagate = False

    def _get_console_handler(self):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self.formatter)
        console_handler.setLevel(self._config.log_level)
        return console_handler

    def _get_null_handler(self):
        return logging.NullHandler()

    def _get_file_handler(self):
        log_file = self._config.log_file
        file_handler = TimedRotatingFileHandler(
            log_file, when="W0", interval=1, backupCount=3, encoding="utf8", delay=True
        )
        # file_handler = logging.FileHandler(log_file, mode="w", encoding="utf8", delay=True)
        file_handler.setFormatter(self.formatter)
        file_handler.setLevel(self._config.log_level)
        return file_handler

    def debugs(self, *messages: str) -> None:
        """
        Log Several messages debug formatted by tab.

        Args:
            messages (Any):  One or more messages to log.

        Return:
            None:
        """
        data = [str(m) for m in messages]
        self.debug("\t".join(data))
        return

    # region Properties
    @property
    def log_file(self):
        """Log file path."""
        return self._config.log_file

    @property
    def is_debug(self) -> bool:
        """Check if is debug"""
        return self.isEnabledFor(logging.DEBUG)

    @property
    def is_info(self) -> bool:
        """Check if is info"""
        return self.isEnabledFor(logging.INFO)

    @property
    def is_warning(self) -> bool:
        """Check if is warning"""
        return self.isEnabledFor(logging.WARNING)

    @property
    def is_error(self) -> bool:
        """Check if is error"""
        return self.isEnabledFor(logging.ERROR)

    # endregion Properties
