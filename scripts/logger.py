"""Structured logging with verbosity levels."""
import sys
from enum import IntEnum
from datetime import datetime


class LogLevel(IntEnum):
    DEBUG = 0
    INFO = 1
    SUCCESS = 2
    WARN = 3
    ERROR = 4


class Logger:
    """Colored, structured logger with verbosity control."""

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[0m",        # Default
        "SUCCESS": "\033[32m",    # Green
        "WARN": "\033[33m",       # Yellow
        "ERROR": "\033[31m",      # Red
        "RESET": "\033[0m",
    }

    def __init__(self, verbosity=1):
        """
        Initialize logger.

        verbosity: 0=ERROR, 1=INFO+SUCCESS+WARN+ERROR (default),
                   2=DEBUG+all, 3=QUIET (ERROR only)
        """
        if verbosity == 3:
            self.min_level = LogLevel.ERROR
        elif verbosity == 2:
            self.min_level = LogLevel.DEBUG
        elif verbosity == 0:
            self.min_level = LogLevel.ERROR
        else:
            self.min_level = LogLevel.INFO

    def _format(self, level_name, message):
        """Format message with timestamp and color."""
        color = self.COLORS.get(level_name, "")
        reset = self.COLORS["RESET"]
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{color}[{timestamp}] {level_name}: {message}{reset}"

    def _log(self, level, level_name, message):
        """Log if level meets threshold."""
        if level >= self.min_level:
            print(self._format(level_name, message), file=sys.stderr)

    def debug(self, message):
        """Log DEBUG level."""
        self._log(LogLevel.DEBUG, "DEBUG", message)

    def info(self, message):
        """Log INFO level."""
        self._log(LogLevel.INFO, "INFO", message)

    def success(self, message):
        """Log SUCCESS level (green)."""
        self._log(LogLevel.SUCCESS, "SUCCESS", message)

    def warn(self, message):
        """Log WARN level."""
        self._log(LogLevel.WARN, "WARN", message)

    def error(self, message):
        """Log ERROR level."""
        self._log(LogLevel.ERROR, "ERROR", message)
