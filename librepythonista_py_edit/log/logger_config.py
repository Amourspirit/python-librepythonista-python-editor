from __future__ import annotations
from typing import Any, Dict
import json
import logging


class LoggerConfig:
    """Log configuration"""

    def __init__(self) -> None:
        self._lo_implementation_name = ""
        self._log_file = ""
        self._log_format = "%(asctime)s - %(levelname)s - %(name)s: %(message)s"
        self._log_name = __file__
        self._log_level = logging.getLogger().getEffectiveLevel()
        self._log_ready_event_raised = False
        self._log_add_console = True

    def to_dict(self) -> dict:
        """Convert the LoggerConfig instance to a dictionary."""
        return {
            "log_level": self.log_level,
            "log_format": self.log_format,
            "log_file": self.log_file,
            "log_add_console": self.log_add_console,
            "lo_implementation_name": self.lo_implementation_name,
        }

    def to_json(self) -> str:
        """Convert the LoggerConfig instance to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LoggerConfig:
        """Create a LoggerConfig instance from a dictionary."""
        instance = cls()
        instance.log_level = data.get("log_level", instance.log_level)
        instance.log_format = data.get("log_format", instance.log_format)
        instance.log_file = data.get("log_file", instance.log_file)
        instance.log_add_console = data.get("log_add_console", instance.log_add_console)
        instance.lo_implementation_name = data.get(
            "lo_implementation_name", instance.lo_implementation_name
        )
        return instance

    @classmethod
    def from_json(cls, data: str) -> LoggerConfig:
        """Create a LoggerConfig instance from a JSON string."""
        return cls.from_dict(json.loads(data))

    @property
    def lo_implementation_name(self) -> str:
        return self._lo_implementation_name

    @lo_implementation_name.setter
    def lo_implementation_name(self, value: str) -> None:
        self._lo_implementation_name = value

    @property
    def log_add_console(self) -> bool:
        """Gets/Sets if a console logger should be added to logging."""
        return self._log_add_console

    @log_add_console.setter
    def log_add_console(self, value: bool) -> None:
        """Sets if a console logger should be added to logging."""
        self._log_add_console = value

    @property
    def log_file(self) -> str:
        """
        Gets/Sets the name of the log file.

        The value for this property can be set in pyproject.toml (tool.oxt.token.log_file)
        """
        return self._log_file

    @log_file.setter
    def log_file(self, value: str) -> None:
        """
        Sets the name of the log file.
        """
        self._log_file = value

    @property
    def log_format(self) -> str:
        """
        Gets/Sets the log format.

        The value for this property can be set in pyproject.toml (tool.oxt.token.log_format)
        """
        return self._log_format

    @log_format.setter
    def log_format(self, value: str) -> None:
        """
        Sets the log format.
        """
        self._log_format = value

    @property
    def log_name(self) -> str:
        """
        Gets/Sets the name of the log file.

        The value for this property can be set in pyproject.toml (tool.oxt.token.log_name)
        """
        return self._log_name

    @log_name.setter
    def log_name(self, value: str) -> None:
        """
        Sets the name of the log file.
        """
        self._log_name = value

    @property
    def log_level(self) -> int:
        """
        Gets/Sets the log level.

        The value for this property can be set in pyproject.toml (tool.oxt.token.log_level)
        """
        return self._log_level

    @log_level.setter
    def log_level(self, value: int) -> None:
        """
        Sets the log level.
        """
        self._log_level = value
